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
from .session_io import enroll_session_scope, session_awake, session_frozen, suspend_offset, SessionBoundary
from .session_lease import SessionLease
from .sleep_guard import SleepGuard
from .recovery import Recovery

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
    def __init__(self, settings_dir=None):
        self.proc = None
        self.reader = None
        self.state = None
        self.error = ''
        self.guard = asyncio.Lock()
        self.waiter = None
        self.closing = False
        self.session = SessionLease()
        self.scope = None
        self.loader_eof_guard = False
        self.cpu_owned_config = None
        self.sleep_guard = SleepGuard(self._on_prepare, self._on_resume)
        self.recovery = Recovery(settings_dir)
        self.front_context = None
        self.front_seen = 0
        self.cpu_intent = None

    def _on_prepare(self):
        context = self.front_context if time.monotonic()-self.front_seen <= 4 else None
        previous = self.state or {}
        tdp = previous.get('tdp_target') if previous.get('tdp_enabled') else None
        if not context or context['native_tdp'] is not False:
            tdp = None
        self.recovery.arm(self.cpu_intent if self.cpu_owned_config else None,
                          tdp, context, suspend_offset())
        self.session.set_preparing(True)
        protected = self.sleep_guard.fd is not None
        async def prepare():
            if not protected:
                return
            async with self.guard:
                if self.cpu_owned_config:
                    if not self.proc or self.proc.returncode is not None:
                        # Recover CPU ownership from this Manager's last explicit
                        # successful transaction, not from disk or an old boot.
                        await self._start(safety=True)
                    result = await self._request({'action': 'prepare_sleep', 'owned_cpu': self.cpu_owned_config},
                                                 {'sleep_prepared'}, timeout=2)
                    actual = result['state']['cpu']
                    self.recovery.prepared({'smt': actual['smt'], 'online': actual['online']})
                    self.cpu_owned_config = None
                    print('POWER pre-sleep: CPU/SMT online; no TDP write; no automatic resume profile.', flush=True)
                    await self._stop('yield')
        return prepare()

    def _on_resume(self):
        self.session.set_preparing(False)
        self.recovery.resume(suspend_offset())
        print('POWER resume: waiting for fresh session pulses; recovery=' + self.recovery.phase, flush=True)

    async def _write_gate(self, lease, recovery_id=None):
        self.session.check(lease)
        if recovery_id: self.recovery.check(recovery_id, suspend_offset())
        if not await session_awake():
            raise SessionBoundary('SteamOS está preparando suspensión/apagado; no se escribe hardware.')
        self.session.check(lease)
        if recovery_id: self.recovery.check(recovery_id, suspend_offset())

    @staticmethod
    def valid_context(context):
        if (not isinstance(context, dict) or type(context.get('awake')) is not bool
                or not isinstance(context.get('game_id'), str) or not context['game_id'].isdigit()
                or len(context['game_id']) > 24 or type(context.get('native_tdp')) not in (bool, type(None))
                or not isinstance(context.get('tdp_key'), str) or len(context['tdp_key']) > 256):
            raise ValueError('Pulso de sesión no válido.')
        return {key: context[key] for key in ('awake', 'game_id', 'native_tdp', 'tdp_key')}

    async def frontend_ready(self, context):
        context = self.valid_context(context)
        state = await self.get_state()
        self.front_context, self.front_seen = context, time.monotonic()
        self.recovery.pulse(context, suspend_offset(), self.session.ready,
                            state['gaming'], state['desktop_busy'], state['competitors'])
        state['recovery'] = self.recovery.state()
        return state

    async def set_recovery(self, enabled):
        self.recovery.set_enabled(enabled)  # Synchronous cancellation, no hardware write.
        if enabled and self.state and self.state.get('tdp_enabled'):
            await self.sleep_guard.watch()
        elif not enabled and self.sleep_guard.fd is None and not self.cpu_owned_config:
            await self.sleep_guard.close()
        return await self.get_state()

    async def recover_pending(self, identity, lease, context):
        # Recover TDP while CPU is still complete. A slow SMU command must not
        # stand between a reduced CPU and its pre-sleep safety normalization.
        acquired = False
        async with self.guard:
            try:
                state = await self.frontend_ready(context)
                await self._write_gate(lease)
                plan = self.recovery.claim(identity)
                if plan['cpu']:
                    actual = await asyncio.to_thread(hw.cpu_state)
                    if {'smt': actual['smt'], 'online': actual['online']} != plan['baseline']:
                        raise RuntimeError('CPU modificada después de despertar; no se sobrescribe.')
                if plan['tdp'] is not None:
                    await self._write_gate(lease, identity)
                    await self._start()
                    await self.sleep_guard.watch()
                    await self._write_gate(lease, identity)
                    await self._request({'action': 'tdp_mode', 'enabled': True}, {'tdp_mode'})
                    acquired = True
                    await self._write_gate(lease, identity)
                    watts = max(3, min(round(plan['tdp']), hw.power_source()['max_watts']))
                    await self._request({'action': 'apply_tdp', 'watts': watts}, {'tdp_applied'})
                await self._write_gate(lease, identity)
                if plan['cpu']:
                    self.recovery.await_cpu(identity)
                else:
                    self.recovery.finish(identity)
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
                self.recovery.finish(identity, self.error)
                if (acquired and self.proc and self.proc.returncode is None
                        and self.session.ready and not self.session.preparing and not session_frozen()):
                    try: await self._request({'action': 'tdp_mode', 'enabled': False}, {'tdp_mode'}, timeout=1)
                    except Exception: pass
            return await self.get_state()

    async def recover_cpu(self, identity, lease, context):
        async with self.guard:
            try:
                context = self.valid_context(context)
                plan = self.recovery.claim_cpu(identity, suspend_offset())
                if not context['awake'] or context['game_id'] != plan['context']['game_id']:
                    raise RuntimeError('Cambió la sesión; recuperación CPU omitida.')
                # The frontend reads Steam again after the awaited TDP stage.
                if plan['tdp'] is not None and (context['native_tdp'] is not False
                        or context['tdp_key'] != plan['context']['tdp_key']):
                    if self.proc and self.proc.returncode is None and not session_frozen():
                        await self._request({'action': 'tdp_mode', 'enabled': False}, {'tdp_mode'}, timeout=1)
                    raise RuntimeError('Steam retomó sus ajustes durante la recuperación; se cede el control.')
                await self._write_gate(lease, identity)
                actual = await asyncio.to_thread(hw.cpu_state)
                if {'smt': actual['smt'], 'online': actual['online']} != plan['baseline']:
                    raise RuntimeError('CPU modificada por otro gestor; no se sobrescribe.')
                await self._apply_cpu_locked(plan['cpu'], lease, identity)
                self.recovery.finish(identity)
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
                self.cpu_intent = None
                self.recovery.finish(identity, self.error)
            return await self.get_state()

    async def session_probe(self):
        """Diagnostic of the exact worker and enrollment, with NO hardware access."""
        if not await session_awake():
            raise SessionBoundary('Sesión no disponible para comprobar el scope.')
        proc = await asyncio.create_subprocess_exec(
            '/usr/bin/python3', '-I', str(ROOT / 'worker.py'), '--session-probe',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C.UTF-8'})
        try:
            scope = await enroll_session_scope(proc)
            payload = json.dumps({'action': 'begin', 'epoch': suspend_offset()}) + '\n'
            output, _ = await asyncio.wait_for(proc.communicate(payload.encode()), 3)
            result = json.loads(output)
            if proc.returncode or result.get('event') != 'probe':
                raise RuntimeError('El auxiliar no confirmó el aislamiento.')
            result['expected_scope'] = scope
            return result
        finally:
            if proc.returncode is None and not session_frozen():
                try: proc.kill()
                except ProcessLookupError: pass
                await asyncio.wait([asyncio.create_task(proc.wait())], timeout=.15)

    async def sleep_guard_probe(self):
        """Acquire/release a logind delay FD; never modifies CPU, TDP or sleep."""
        async def noop():
            pass
        guard = SleepGuard(noop, lambda: None)
        try:
            await guard.arm()
            return {'armed': guard.fd is not None, 'mode': 'delay', 'hardware_touched': False}
        finally:
            await guard.close()

    async def get_state(self):
        self.session.observe(pulse=True)
        fresh = await asyncio.to_thread(snapshot)
        if self.state and self.proc and self.proc.returncode is None:
            fresh.update(self.state)
            # These identities must be freshly detected, never from a worker cache.
            rows = await asyncio.to_thread(processes)
            fresh.update(competitors=competitors(rows), gaming=in_gaming(rows))
        owned = bool(self.proc and self.proc.returncode is None)
        fresh.update(active=owned, desktop_busy=not owned and await asyncio.to_thread(lock_busy),
                     error=self.error, version='1.2', session_ready=self.session.ready,
                     session_lease=self.session.token, recovery_arch='session-lease-v2-recovery',
                     loader_eof_guard=self.loader_eof_guard,
                     cpu_sleep_guard=self.sleep_guard.fd is not None,
                     recovery=self.recovery.state())
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
                    if event.get('event') in ('cpu_applied', 'sleep_prepared', 'error') and 'cpu_owned' in self.state:
                        self.cpu_owned_config = (self.state.get('cpu_owned_state')
                                                 if self.state['cpu_owned'] else None)
                kind = event.get('event')
                if kind == 'error':
                    self.error = event.get('message', 'Error del controlador')
                    print('POWER worker: ' + self.error, flush=True)
                elif kind == 'session_ended':
                    self.state = None
                    print('POWER worker ended at session boundary; pending recovery preserved.', flush=True)
                elif kind in ('cpu_applied', 'tdp_applied', 'tdp_mode', 'sleep_prepared', 'closed'):
                    print('POWER decision: ' + json.dumps(event, ensure_ascii=False), flush=True)
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
        self.proc.stdin.write((json.dumps(dict(request, epoch=suspend_offset())) + '\n').encode())
        await self.proc.stdin.drain()

    async def _request(self, request, events, timeout=25):
        if request.get('action') == 'prepare_sleep':
            request = dict(request, deadline=time.monotonic() + 1.8)
        future = asyncio.get_running_loop().create_future()
        self.waiter = (set(events), future)
        try:
            await self._send(request)
            return await asyncio.wait_for(future, timeout)
        finally:
            if self.waiter and self.waiter[1] is future:
                self.waiter = None

    async def _start(self, safety=False):
        state = await self.get_state()
        if not state['host']['supported']:
            raise RuntimeError(state['host']['reason'])
        if not state['gaming'] and not (safety and self.cpu_owned_config):
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
        try:
            self.scope = await enroll_session_scope(self.proc)
            # The worker is waiting on stdin until its exact scope is verified.
            await self._send({'action': 'begin'})
            self.reader = asyncio.create_task(self._read())
            print('POWER worker enrolled: ' + self.scope, flush=True)
            await asyncio.wait_for(future, 15)
        except BaseException:
            await self._stop('quit')
            raise
        finally:
            self.waiter = None

    async def apply_cpu(self, config, lease=None):
        self.recovery.cancel('Ajuste manual de CPU.')
        async with self.guard:
            try:
                await self._apply_cpu_locked(config, lease)
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
            return await self.get_state()

    async def _apply_cpu_locked(self, config, lease, recovery_id=None):
        await self._write_gate(lease, recovery_id)
        if not isinstance(config, dict) or set(config) != {'smt', 'cores', 'threads'}:
            raise ValueError('Configuración de CPU no válida.')
        wanted = await asyncio.to_thread(hw.target_cpus, hw.topology(), config['cores'], config['threads'], config['smt'])
        await self._start()
        reduced = (not config['smt'] or config['cores'] != len(hw.topology())
                   or config['threads'] != sum(map(len, hw.topology())))
        if reduced:
            # If logind cannot guarantee pre-sleep notification, never
            # put the Ally into the documented unsafe CPU state.
            await self.sleep_guard.arm()
        await self._write_gate(lease, recovery_id)
        self.cpu_owned_config = {'smt': config['smt'], 'online': sorted(wanted)}
        await self._request({'action': 'apply_cpu', 'config': config}, {'cpu_applied'})
        self.cpu_owned_config = {'smt': config['smt'], 'online': sorted(wanted)} if reduced else None
        if not reduced:
            self.sleep_guard.release()
        self.cpu_intent = dict(config)

    async def set_tdp_mode(self, enabled, lease=None):
        self.recovery.cancel('Cesión o ajuste manual de TDP.')
        async with self.guard:
            try:
                if type(enabled) is not bool:
                    raise ValueError('Estado de control TDP no válido.')
                if enabled:
                    await self._write_gate(lease)
                    await self._start()
                    if self.recovery.enabled:
                        await self.sleep_guard.watch()
                    await self._write_gate(lease)
                if self.proc and self.proc.returncode is None:
                    await self._request({'action': 'tdp_mode', 'enabled': enabled}, {'tdp_mode'})
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
            return await self.get_state()

    async def apply_tdp(self, watts, lease=None):
        self.recovery.cancel('Ajuste manual de TDP.')
        async with self.guard:
            try:
                await self._write_gate(lease)
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
        if proc.returncode is None and session_frozen():
            # Do not time out or signal an intentionally frozen process. Its
            # independent epoch guard will exit write-free after thaw.
            self.state = None
            return
        try:
            if proc.returncode is None:
                await self._send({'action': action})
                await asyncio.wait_for(proc.wait(), 2)
        except (OSError, RuntimeError, asyncio.TimeoutError):
            if proc.returncode is None and not session_frozen():
                try:
                    proc.kill()  # No signal-handler restoration in this worker.
                except ProcessLookupError:
                    pass
                await asyncio.wait([asyncio.create_task(proc.wait())], timeout=.15)
        finally:
            self.state = None
            # A D-state process retains the flock; never launch over it.
            if proc.returncode is not None:
                if self.reader:
                    await asyncio.wait([self.reader], timeout=.15)
                self.proc = None
                self.reader = None
                self.scope = None

    async def release(self):
        async with self.guard:
            await self._stop('yield')
            return await self.get_state()

    async def monitor(self):
        while not self.closing:
            await asyncio.sleep(2)
            async with self.guard:
                self.session.observe()
                if not self.session.ready:
                    if (self.proc and self.proc.returncode is None
                            and not self.session.preparing and not session_frozen()):
                        # Keep CPU ownership and its pre-sleep guard on UI gaps,
                        # but disable the worker's automatic battery clamp.
                        try:
                            await self._send({'action': 'ping', 'live': False})
                        except (OSError, RuntimeError) as exc:
                            self.error = str(exc)
                            await self._stop('yield')
                    continue
                if not self.proc or self.proc.returncode is not None:
                    continue
                rows = await asyncio.to_thread(processes)
                other = competitors(rows)
                if not in_gaming(rows) or other:
                    # Yield without restoring over a new manager's settings.
                    normalized = False
                    failure = ''
                    if not other and self.cpu_owned_config:
                        try:
                            await self._request({'action': 'prepare_sleep', 'owned_cpu': self.cpu_owned_config},
                                                {'sleep_prepared'}, timeout=2)
                            self.cpu_owned_config = None
                            normalized = True
                        except Exception as exc:
                            failure = 'No se pudo liberar CPU reducida: ' + str(exc)
                    await self._stop('yield')
                    if other or not self.cpu_owned_config:
                        self.cpu_owned_config = None
                        await self.sleep_guard.close()
                    self.error = failure or ('Control cedido: ' + ', '.join(other) if other else
                        'Control cedido al salir de Gaming. ' +
                        ('CPU completa por seguridad; ' if normalized else '') + 'sin reaplicación automática.')
                else:
                    try:
                        await self._send({'action': 'ping', 'live': True})
                    except Exception as exc:
                        self.error = str(exc)
                        await self._stop('quit')

    async def close(self):
        self.recovery.cancel('Plugin descargado.')
        self.closing = True
        async with self.guard:
            if (self.cpu_owned_config and not session_frozen() and not self.session.preparing
                    and await session_awake()):
                try:
                    if not self.proc or self.proc.returncode is not None:
                        await self._start(safety=True)
                    await self._request({'action': 'prepare_sleep', 'owned_cpu': self.cpu_owned_config},
                                        {'sleep_prepared'}, timeout=2)
                    self.cpu_owned_config = None
                except Exception as exc:
                    print('POWER unload: CPU safety normalization failed: ' + str(exc), flush=True)
            await self._stop('yield')
        await self.sleep_guard.close()
