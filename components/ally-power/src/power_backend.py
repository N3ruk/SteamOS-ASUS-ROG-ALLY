#!/usr/bin/python3
"""Privileged, pipe-only controller. No shell commands or caller-supplied paths."""
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time

CPU = Path('/sys/devices/system/cpu')
RYZENADJ = '/usr/local/lib/desktop-power/ryzenadj'
ASUS_ATTRIBUTES = Path('/sys/class/firmware-attributes/asus-armoury/attributes')
FALLBACK_LIMITS = None
STATE_FILE = Path('/run/desktop-power/last-limits.json')


def asus_limits():
    names = {'stapm': 'ppt_pl1_spl', 'fast': 'ppt_pl3_fppt', 'slow': 'ppt_pl2_sppt'}
    return {key: float(read(ASUS_ATTRIBUTES / name / 'current_value', '0'))
            for key, name in names.items()}


def remembered_limits():
    """Last acknowledgement in this boot, not telemetry or a boot-time preset."""
    try:
        stat = STATE_FILE.stat()
        if stat.st_uid != 0 or stat.st_mode & 0o022:
            return None
        state = json.loads(STATE_FILE.read_text())
        values = state['limits']
        if (state['asus'] == asus_limits() and set(values) == {'stapm', 'fast', 'slow'}
                and all(type(v) in (int, float) and 0 < v < 200 for v in values.values())):
            return values
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def remember_limits(values):
    directory = STATE_FILE.parent
    directory.mkdir(mode=0o755, exist_ok=True)
    stat = directory.lstat()
    if directory.is_symlink() or stat.st_uid != 0 or stat.st_mode & 0o022:
        raise RuntimeError('Directorio de estado inseguro.')
    import tempfile
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix='limits-')
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump({'limits': values, 'asus': asus_limits()}, stream)
            os.fchmod(stream.fileno(), 0o644)
        os.replace(temporary, STATE_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read(path, default=''):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def cpu_list(text):
    result = set()
    for item in text.split(','):
        if not item:
            continue
        ends = item.split('-')
        result.update(range(int(ends[0]), int(ends[-1]) + 1))
    return result


def topology():
    groups = {}
    for cpu in cpu_list(read(CPU / 'present')):
        base = CPU / f'cpu{cpu}/topology'
        package = read(base / 'physical_package_id')
        core = read(base / 'core_id')
        if package not in ('', '-1') and core not in ('', '-1'):
            key = (package, core)
        else:
            key = ('siblings', read(base / 'thread_siblings_list', str(cpu)))
        groups.setdefault(key, []).append(cpu)
    return sorted((tuple(sorted(group)) for group in groups.values()),
                  key=lambda group: (0 not in group, group[0]))


def power_source():
    sources = []
    battery = None
    for supply in Path('/sys/class/power_supply').glob('*'):
        kind = read(supply / 'type')
        if kind == 'Battery':
            capacity = read(supply / 'capacity')
            if capacity.isdigit():
                battery = int(capacity)
        elif (supply / 'online').exists():
            sources.append(read(supply / 'online') == '1')
    # Unknown sources get the conservative battery ceiling.
    ac = any(sources)
    return {'ac': ac, 'max_watts': 30 if ac else 25, 'battery': battery}


def cpu_state(groups=None):
    online = cpu_list(read(CPU / 'online'))
    groups = topology() if groups is None else groups
    return {
        'smt': read(CPU / 'smt/control') == 'on',
        'smt_control': read(CPU / 'smt/control'),
        'online': sorted(online),
        'cores': sum(bool(set(group) & online) for group in groups),
        'threads': len(online),
        'max_cores': len(groups),
        'max_threads': sum(map(len, groups)),
    }


def target_cpus(groups, cores, threads, smt):
    if type(cores) is not int or not 1 <= cores <= len(groups):
        raise ValueError('Número de núcleos no válido.')
    if type(smt) is not bool:
        raise ValueError('Estado SMT no válido.')
    selected = groups[:cores]
    maximum = sum(map(len, selected)) if smt else cores
    if type(threads) is not int or not cores <= threads <= maximum:
        raise ValueError('El número de hilos no corresponde a los núcleos y SMT.')
    primary = [group[0] for group in selected]
    extra = [cpu for group in selected for cpu in group[1:]] if smt else []
    target = set(primary + extra[:threads - cores])
    if 0 not in target:
        raise ValueError('El procesador principal debe permanecer activo.')
    return target


def validate(config, source, groups):
    if not isinstance(config, dict) or set(config) != {'watts', 'smt', 'cores', 'threads'}:
        raise ValueError('Configuración no válida.')
    watts = config['watts']
    if type(watts) is not int or not 3 <= watts <= source['max_watts']:
        raise ValueError(f"El TDP debe estar entre 3 y {source['max_watts']} W.")
    target_cpus(groups, config['cores'], config['threads'], config['smt'])
    return dict(config)


def limits():
    global FALLBACK_LIMITS
    if FALLBACK_LIMITS is not None:
        return dict(FALLBACK_LIMITS)
    result = subprocess.run([RYZENADJ, '--info'], capture_output=True, text=True, timeout=8,
                            env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C'})
    names = {'STAPM LIMIT': 'stapm', 'PPT LIMIT FAST': 'fast', 'PPT LIMIT SLOW': 'slow'}
    found = {}
    for label, key in names.items():
        match = re.search(r'\|\s*' + label + r'\s*\|\s*([0-9.]+)', result.stdout)
        if match:
            found[key] = float(match.group(1))
    if result.returncode or len(found) != 3:
        diagnostic = result.stderr + result.stdout
        if 'Unable to get memory access' in diagnostic or 'failed to map /dev/mem' in diagnostic:
            # ASUS values are the driver's configured limits, NOT SMU telemetry.
            # Use them only as the starting configuration for restoration.
            baseline = remembered_limits() or asus_limits()
            if all(0 < value < 200 for value in baseline.values()):
                FALLBACK_LIMITS = baseline
                return dict(baseline)
        raise RuntimeError('No se pueden leer los límites de la APU: ' +
                           (result.stderr or result.stdout)[-450:])
    if any(not 0 < value < 200 for value in found.values()):
        raise RuntimeError('La APU ha devuelto límites no válidos.')
    return found


def write_limits(values):
    global FALLBACK_LIMITS
    args = [RYZENADJ, f"--stapm-limit={round(values['stapm'] * 1000)}",
            f"--fast-limit={round(values['fast'] * 1000)}",
            f"--slow-limit={round(values['slow'] * 1000)}"]
    result = subprocess.run(args, capture_output=True, text=True, timeout=8,
                            env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError('La APU rechazó el ajuste: ' + (result.stderr or result.stdout)[-450:])
    if FALLBACK_LIMITS is not None:
        # Require the explicit SMU acknowledgements, but do not call them telemetry.
        for name in ('stapm', 'fast', 'slow'):
            if not re.search(r'(?:Sucessfully|Successfully) set ' + name + r'_limit to\s+'
                             + str(round(values[name] * 1000)) + r'\b', result.stdout):
                raise RuntimeError('RyzenAdj no confirmó el ajuste de ' + name + '.')
        FALLBACK_LIMITS = dict(values)
        remember_limits(values)
        return dict(values)
    actual = limits()
    if any(abs(actual[key] - values[key]) > 0.6 for key in values):
        raise RuntimeError('El firmware no mantuvo el TDP solicitado. No se ha confirmado el cambio.')
    remember_limits(actual)
    return actual


def write_cpus(smt, wanted):
    control = read(CPU / 'smt/control')
    if control not in ('on', 'off'):
        raise RuntimeError(f'El sistema no permite cambiar SMT ({control}).')
    if 0 not in wanted:
        raise ValueError('CPU 0 no se puede apagar.')
    if (control == 'on') != smt:
        (CPU / 'smt/control').write_text('on' if smt else 'off')
    online = cpu_list(read(CPU / 'online'))
    for number in sorted(wanted - online):
        (CPU / f'cpu{number}/online').write_text('1')
    online = cpu_list(read(CPU / 'online'))
    for number in sorted(online - wanted, reverse=True):
        if number == 0:
            raise ValueError('CPU 0 no se puede apagar.')
        (CPU / f'cpu{number}/online').write_text('0')
    if cpu_list(read(CPU / 'online')) != set(wanted):
        raise RuntimeError('No se pudo confirmar el número de hilos activos.')


def temperature():
    for hwmon in Path('/sys/class/hwmon').glob('*'):
        if read(hwmon / 'name') == 'k10temp':
            value = read(hwmon / 'temp1_input')
            if value.isdigit():
                return round(int(value) / 1000)
    return None


class Controller:
    def __init__(self):
        self.groups = topology()
        self.original = {'cpu': cpu_state(self.groups), 'limits': limits()}
        self.target = None
        self.changed = False
        self.last_limits = self.original['limits']
        self.last_check = 0
        self.warning = ''

    def restore_state(self, state):
        errors = []
        try:
            write_cpus(state['cpu']['smt'], set(state['cpu']['online']))
        except Exception as exc:
            errors.append(str(exc))
        try:
            values = state['limits']
            if not power_source()['ac']:
                values = {key: min(value, 25) for key, value in values.items()}
            self.last_limits = write_limits(values)
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise RuntimeError('Restauración incompleta: ' + '; '.join(errors))

    def apply(self, config):
        config = validate(config, power_source(), self.groups)
        before = {'cpu': cpu_state(self.groups), 'limits': limits()}
        previous_target = self.target
        self.changed = True
        try:
            wanted = target_cpus(self.groups, config['cores'], config['threads'], config['smt'])
            # Recheck power immediately before writing (unplug during an Apply).
            config['watts'] = min(config['watts'], power_source()['max_watts'])
            self.last_limits = write_limits(dict.fromkeys(('stapm', 'fast', 'slow'), config['watts']))
            write_cpus(config['smt'], wanted)
            self.target = config
            self.warning = ''
        except Exception:
            self.target = previous_target
            self.restore_state(before)
            raise

    def restore(self):
        if self.changed:
            self.restore_state(self.original)
        self.target = None
        self.changed = False
        self.warning = ''

    def tick(self):
        source = power_source()
        if self.target and self.target['watts'] > source['max_watts']:
            config = dict(self.target, watts=source['max_watts'])
            self.apply(config)
        if time.monotonic() - self.last_check > 3:
            self.last_limits = limits()
            self.last_check = time.monotonic()
            if self.target:
                conflict = FALLBACK_LIMITS is None and any(
                    abs(value - self.target['watts']) > 0.6 for value in self.last_limits.values())
                current = cpu_state(self.groups)
                conflict |= any(current[key] != self.target[key] for key in ('smt', 'cores', 'threads'))
                self.warning = ('Otro controlador ha cambiado los ajustes. Pulsa Aplicar para recuperarlos.'
                                if conflict else '')
                # Can detect competing TDP writes only with working SMU telemetry.
                if not source['ac'] and max(self.last_limits.values()) > 25.6:
                    self.last_limits = write_limits(dict.fromkeys(('stapm', 'fast', 'slow'),
                                                                  self.target['watts']))
        return self.status(source)

    def status(self, source=None):
        return {'power': source or power_source(), 'cpu': cpu_state(self.groups),
                'limits': self.last_limits, 'target': self.target,
                'tdp_verified': FALLBACK_LIMITS is None,
                'tdp_note': ('' if FALLBACK_LIMITS is None else
                             'SMU acepta el ajuste; lectura real de TDP no disponible en SteamOS.'),
                'temperature': temperature(), 'warning': self.warning}


def serve():
    if os.geteuid() != 0:
        raise RuntimeError('Se necesitan permisos de administrador.')
    # Prevent simultaneous controllers, without exposing a network or D-Bus API.
    import fcntl
    descriptor = os.open('/run/desktop-power.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    lock = os.fdopen(descriptor, 'w')
    if os.fstat(lock.fileno()).st_uid != 0:
        lock.close()
        raise RuntimeError('El archivo de bloqueo no pertenece a root.')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    controller = Controller()
    requests = queue.Queue()

    def reader():
        while True:
            line = sys.stdin.readline(4097)
            if not line or len(line) > 4096:
                requests.put({'action': 'quit'})
                return
            try:
                requests.put(json.loads(line))
            except ValueError:
                requests.put({'action': 'invalid'})

    def emit(kind, **values):
        print(json.dumps({'event': kind, **values}), flush=True)

    def stop(*_):
        requests.put({'action': 'quit'})

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    threading.Thread(target=reader, daemon=True).start()
    emit('ready', state=controller.status(), capabilities=['quit_keep'])
    contact = time.monotonic()
    keep_settings = False
    try:
        while time.monotonic() - contact < 20:
            try:
                request = requests.get(timeout=1)
            except queue.Empty:
                request = None
            if request is not None:
                contact = time.monotonic()
                try:
                    action = request.get('action')
                    if action == 'quit_keep':
                        # Final battery check; normal exit must not undo successful Apply.
                        controller.tick()
                        keep_settings = True
                        break
                    if action == 'quit':
                        break
                    if action == 'apply':
                        controller.apply(request.get('config'))
                        emit('applied', state=controller.status())
                    elif action == 'restore':
                        controller.restore()
                        emit('restored', state=controller.status())
                    elif action != 'ping':
                        raise ValueError('Acción no válida.')
                except Exception as exc:
                    emit('error', message=str(exc), state=controller.status())
            try:
                emit('status', state=controller.tick())
            except Exception as exc:
                emit('error', message=str(exc))
    finally:
        if not keep_settings:
            controller.restore()
        try:
            emit('closed', state=controller.status(), kept=keep_settings)
        except BrokenPipeError:
            pass


if __name__ == '__main__':
    try:
        serve()
    except Exception as exc:
        print(json.dumps({'event': 'error', 'message': str(exc)}), flush=True)
        sys.exit(1)
