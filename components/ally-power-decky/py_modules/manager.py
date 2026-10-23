"""Decky lifecycle and read-only discovery. Hardware writes live in the pipe worker."""
import asyncio
import fcntl
import json
import os
from pathlib import Path
import platform
import stat
import time

from . import power_backend as hw

ROOT = Path(__file__).resolve().parent.parent
LOCK = Path('/run/desktop-power.lock')


def host_support():
    product = hw.read('/sys/devices/virtual/dmi/id/product_name')
    cpu = hw.read('/proc/cpuinfo')
    os_release = hw.read('/etc/os-release')
    supported = (platform.machine() == 'x86_64'
                 and ('RC71L' in product or 'RC72LA' in product)
                 and ('AMD Ryzen Z1' in cpu)
                 and ('ID=steamos' in os_release or 'ID="steamos"' in os_release))
    return {'supported': supported, 'product': product,
            'reason': '' if supported else 'Compatible con SteamOS en ROG Ally/Ally X Z1 o Z1 Extreme.'}


def processes(proc_root=Path('/proc')):
    """Only retain process identities; never report command arguments or environment."""
    result = []
    for path in proc_root.iterdir():
        if not path.name.isdigit():
            continue
        try:
            comm = (path / 'comm').read_text().strip()
            args = (path / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            result.append((comm, args))
        except OSError:
            continue
    return result


def competitors(rows=None):
    rows = processes() if rows is None else rows
    found = set()
    for comm, args in rows:
        lower = args.lower()
        if comm == 'PowerTools' or '/plugins/powertools/bin/backend' in lower:
            found.add('PowerTools')
        if '/plugins/powercontrol/' in lower:
            found.add('PowerControl')
        if '/plugins/simpledeckytdp/' in lower or '/plugins/simpletdp/' in lower:
            found.add('SimpleDeckyTDP')
        if comm in ('hhd', 'hhd-adjustor', 'adjustor') or '/bin/hhd ' in lower:
            found.add('Handheld Daemon / Adjustor')
        if comm in ('ryzenadj', 'ryzenadj-controller', 'ryzen-controller'):
            found.add('RyzenAdj externo')
    return sorted(found)


def in_gaming(rows=None):
    rows = processes() if rows is None else rows
    # Gamescope renames its main Wayland thread via pthread_setname_np.
    # /proc/PID/comm therefore reports gamescope-wl on current SteamOS.
    # Match exact compositor names, not helpers such as gamescope-session.
    return any(comm in ('gamescope', 'gamescope-wl') for comm, _ in rows)


def lock_busy(path=LOCK):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    try:
        if os.fstat(fd).st_uid != 0:
            return True
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True
    finally:
        os.close(fd)


def secure_executable(path):
    try:
        s = path.stat()
        return (not path.is_symlink() and stat.S_ISREG(s.st_mode)
                and s.st_uid == 0 and not s.st_mode & 0o022 and os.access(path, os.X_OK))
    except OSError:
        return False


def ryzenadj_path():
    # Prefer the exact binary already validated with the desktop app on this host.
    installed = Path('/usr/local/lib/desktop-power/ryzenadj')
    bundled = ROOT / 'bin/ryzenadj'
    for path in (installed, bundled):
        if secure_executable(path):
            return str(path)
    raise RuntimeError('RyzenAdj debe estar instalado como archivo propiedad de root y no modificable por otros.')


def snapshot():
    rows = processes()
    values = hw.remembered_limits() or hw.asus_limits()
    return {'power': hw.power_source(), 'cpu': hw.cpu_state(),
            'tdp_enabled': False, 'tdp_target': None, 'cpu_target': None,
            'limits': values, 'target': None, 'temperature': hw.temperature(),
            'tdp_verified': False,
            'tdp_note': 'Límite configurado/recordado; no es el consumo real medido de la APU.',
            'warning': '', 'host': host_support(), 'gaming': in_gaming(rows),
            'competitors': competitors(rows)}


class Manager:
    def __init__(self):
        self.proc = None
        self.reader = None
        self.state = None
        self.error = ''
        self.guard = asyncio.Lock()
        self.waiter = None
        self.closing = False

    async def get_state(self):
        fresh = await asyncio.to_thread(snapshot)
        if self.state and self.proc and self.proc.returncode is None:
            fresh.update(self.state)
            # These identities must be freshly detected, never from a worker cache.
            rows = await asyncio.to_thread(processes)
            fresh.update(competitors=competitors(rows), gaming=in_gaming(rows))
        owned = bool(self.proc and self.proc.returncode is None)
        fresh.update(active=owned, desktop_busy=not owned and await asyncio.to_thread(lock_busy),
                     error=self.error, version='1.1.2')
        return fresh

    async def _read(self):
        proc = self.proc
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                event = json.loads(line)
                if 'state' in event:
                    self.state = event['state']
                kind = event.get('event')
                if kind == 'error':
                    self.error = event.get('message', 'Error del controlador')
                waiter = self.waiter
                if waiter and not waiter[1].done() and (kind in waiter[0] or kind == 'error'):
                    if kind == 'error':
                        waiter[1].set_exception(RuntimeError(self.error))
                    else:
                        waiter[1].set_result(event)
        except (ValueError, OSError) as exc:
            self.error = str(exc)
        finally:
            waiter = self.waiter
            if waiter and not waiter[1].done():
                waiter[1].set_exception(RuntimeError(self.error or 'El controlador se ha detenido.'))

    async def _send(self, request):
        if not self.proc or self.proc.returncode is not None:
            raise RuntimeError('No hay un controlador activo.')
        self.proc.stdin.write((json.dumps(request) + '\n').encode())
        await self.proc.stdin.drain()

    async def _request(self, request, events, timeout=25):
        future = asyncio.get_running_loop().create_future()
        self.waiter = (set(events), future)
        try:
            await self._send(request)
            return await asyncio.wait_for(future, timeout)
        finally:
            if self.waiter and self.waiter[1] is future:
                self.waiter = None

    async def _start(self):
        state = await self.get_state()
        if not state['host']['supported']:
            raise RuntimeError(state['host']['reason'])
        if not state['gaming']:
            raise RuntimeError('Activa el control desde el modo Gaming. En escritorio utiliza la app Ally Power.')
        if state['competitors']:
            raise RuntimeError('Desactiva primero en Decky/ajustes: ' + ', '.join(state['competitors']))
        if state['desktop_busy']:
            raise RuntimeError('La app de escritorio tiene el control. Ciérrala conservando los ajustes antes de continuar.')
        if state['active']:
            return
        await asyncio.to_thread(ryzenadj_path)
        # Register the waiter before the reader, since ready can arrive immediately.
        future = asyncio.get_running_loop().create_future()
        self.waiter = ({'ready'}, future)
        self.proc = await asyncio.create_subprocess_exec(
            '/usr/bin/python3', '-I', str(ROOT / 'worker.py'),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=32768,
            env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C.UTF-8'})
        self.reader = asyncio.create_task(self._read())
        try:
            await asyncio.wait_for(future, 15)
        except BaseException:
            await self._stop('quit')
            raise
        finally:
            self.waiter = None

    async def apply_cpu(self, config):
        async with self.guard:
            try:
                if not isinstance(config, dict) or set(config) != {'smt', 'cores', 'threads'}:
                    raise ValueError('Configuración de CPU no válida.')
                await asyncio.to_thread(hw.target_cpus, hw.topology(), config['cores'], config['threads'], config['smt'])
                await self._start()
                await self._request({'action': 'apply_cpu', 'config': config}, {'cpu_applied'})
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
            return await self.get_state()

    async def set_tdp_mode(self, enabled):
        async with self.guard:
            try:
                if type(enabled) is not bool:
                    raise ValueError('Estado de control TDP no válido.')
                if enabled:
                    await self._start()
                if self.proc and self.proc.returncode is None:
                    await self._request({'action': 'tdp_mode', 'enabled': enabled}, {'tdp_mode'})
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
            return await self.get_state()

    async def apply_tdp(self, watts):
        async with self.guard:
            try:
                maximum = hw.power_source()['max_watts']
                if type(watts) is not int or not 3 <= watts <= maximum:
                    raise ValueError(f'El TDP debe estar entre 3 y {maximum} W.')
                if not self.proc or self.proc.returncode is not None or not self.state or not self.state.get('tdp_enabled'):
                    raise RuntimeError('El control de TDP del plugin está desactivado.')
                await self._request({'action': 'apply_tdp', 'watts': watts}, {'tdp_applied'})
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
            return await self.get_state()

    async def _stop(self, action='yield'):
        proc = self.proc
        if not proc:
            return
        try:
            if proc.returncode is None:
                await self._send({'action': action})
                await asyncio.wait_for(proc.wait(), 15)
        except (OSError, RuntimeError, asyncio.TimeoutError):
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), 12)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
        finally:
            if self.reader:
                await self.reader
            self.proc = None
            self.reader = None
            self.state = None

    async def release(self):
        async with self.guard:
            await self._stop('yield')
            return await self.get_state()

    async def monitor(self):
        while not self.closing:
            await asyncio.sleep(2)
            async with self.guard:
                if not self.proc or self.proc.returncode is not None:
                    continue
                rows = await asyncio.to_thread(processes)
                other = competitors(rows)
                if not in_gaming(rows) or other:
                    # Yield without restoring over a new manager's settings.
                    await self._stop('yield')
                    self.error = ('Control cedido: ' + ', '.join(other) if other else
                                  'Control cedido al salir de Gaming. Ajustes conservados; sin reaplicación automática.')
                else:
                    try:
                        await self._send({'action': 'ping'})
                    except Exception as exc:
                        self.error = str(exc)
                        await self._stop('quit')

    async def close(self):
        self.closing = True
        async with self.guard:
            await self._stop('yield')
