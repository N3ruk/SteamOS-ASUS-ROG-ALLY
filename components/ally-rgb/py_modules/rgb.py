"""Ally-only RGB: sysfs and strictly RGB-only hidraw compatibility transport."""
import asyncio
import colorsys
import contextlib
import errno
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile
import time

LED = Path('/sys/class/leds/ally:rgb:joystick_rings')
EFFECTS = ('solid', 'breath', 'rainbow', 'wave', 'gradient', 'battery')
ZONES = {'all': (0, 1, 2, 3), 'pair12': (0, 1), 'pair34': (2, 3),
         'zone1': (0,), 'zone2': (1,), 'zone3': (2,), 'zone4': (3,)}
LEGACY_DEFAULT = dict(enabled=True, brightness=50, speed=50, effect='solid',
               colors=['#00ddbb'] * 4, resume=True, zone='all',
               transition_colors=['#00ddbb', '#a43aff'])

ZONE_DEFAULT = dict(effect='solid', speed=50, color='#00ddbb',
                    transition_colors=['#00ddbb', '#a43aff'])
DEFAULT = dict(enabled=True, brightness=50, resume=True, zone='all',
               zones=[dict(ZONE_DEFAULT, transition_colors=list(ZONE_DEFAULT['transition_colors'])) for _ in range(4)])


class RGBError(RuntimeError):
    pass


def read(path):
    return Path(path).read_text().strip()


def validate_legacy(config):
    # Migrate the former configuration without inventing an equal-color transition.
    legacy = set(LEGACY_DEFAULT) - {'zone', 'transition_colors'}
    if isinstance(config, dict) and set(config) == legacy:
        config = dict(config, zone='all', transition_colors=list(LEGACY_DEFAULT['transition_colors']))
        colors = config['colors']
        if isinstance(colors, list) and len(colors) == 4 and colors[0] != colors[3]:
            config['transition_colors'] = [colors[0], colors[3]]
    if not isinstance(config, dict) or set(config) != set(LEGACY_DEFAULT):
        raise RGBError('Configuración RGB incompleta o desconocida.')
    for field in ('enabled', 'resume'):
        if type(config[field]) is not bool:
            raise RGBError('Estado RGB no válido.')
    for field, low, high in [('brightness', 0, 100), ('speed', 10, 100)]:
        if type(config[field]) is not int or not low <= config[field] <= high:
            raise RGBError(f'{field} debe estar entre {low} y {high}.')
    if config['effect'] not in EFFECTS:
        raise RGBError('Efecto no disponible.')
    if not isinstance(config['zone'], str) or config['zone'] not in ZONES:
        raise RGBError('Selección de zonas no válida.')
    colors = config['colors']
    if not isinstance(colors, list) or len(colors) != 4 or not all(
            isinstance(c, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in colors):
        raise RGBError('Se necesitan cuatro colores hexadecimales RGB válidos.')
    transition = config['transition_colors']
    if not isinstance(transition, list) or len(transition) != 2 or not all(
            isinstance(c, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in transition):
        raise RGBError('La transición necesita dos colores RGB válidos.')
    return dict(config, colors=[c.lower() for c in colors],
                transition_colors=[c.lower() for c in transition])



def validate(config):
    if isinstance(config, dict) and 'zones' not in config:
        old = validate_legacy(config)
        selected = ZONES[old['zone']]
        config = dict(enabled=old['enabled'], brightness=old['brightness'],
                      resume=old['resume'], zone=old['zone'], zones=[
            dict(effect=old['effect'] if i in selected else 'solid', speed=old['speed'],
                 color=c, transition_colors=list(old['transition_colors']))
            for i, c in enumerate(old['colors'])])
    if not isinstance(config, dict) or set(config) != set(DEFAULT):
        raise RGBError('Configuración RGB incompleta o desconocida.')
    if any(type(config[k]) is not bool for k in ('enabled', 'resume')):
        raise RGBError('Estado RGB no válido.')
    if type(config['brightness']) is not int or not 0 <= config['brightness'] <= 100:
        raise RGBError('brightness debe estar entre 0 y 100.')
    if not isinstance(config['zone'], str) or config['zone'] not in ZONES:
        raise RGBError('Selección de zonas no válida.')
    zones = config['zones']
    if not isinstance(zones, list) or len(zones) != 4:
        raise RGBError('Se necesitan cuatro configuraciones de zona.')
    updated = []
    for zone in zones:
        if not isinstance(zone, dict) or set(zone) != set(ZONE_DEFAULT):
            raise RGBError('Configuración de zona incompleta o desconocida.')
        if zone['effect'] not in EFFECTS:
            raise RGBError('Efecto no disponible.')
        if type(zone['speed']) is not int or not 10 <= zone['speed'] <= 100:
            raise RGBError('speed debe estar entre 10 y 100.')
        colors = [zone['color']]
        transition = zone['transition_colors']
        if not isinstance(transition, list) or len(transition) != 2:
            raise RGBError('La transición necesita dos colores RGB válidos.')
        colors += transition
        if not all(isinstance(c, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in colors):
            raise RGBError('Colores de zona no válidos.')
        updated.append(dict(zone, color=zone['color'].lower(),
                            transition_colors=[c.lower() for c in transition]))
    return dict(config, zones=updated)


def frame(config, seconds, battery=None):
    """Compose four independently animated zones into one atomic kernel frame.

    A scalar time is useful for pure tests; runtime supplies four elapsed times.
    Editor selection never participates in rendering.
    """
    brightness = round(config['brightness'] * 255 / 100) if config['enabled'] else 0
    elapsed = [seconds] * 4 if isinstance(seconds, (int, float)) else seconds
    colors = []
    for i, zone in enumerate(config['zones']):
        color = int(zone['color'][1:], 16)
        if config['enabled']:
            phase = elapsed[i] * (0.15 + zone['speed'] / 100 * 1.85)
            effect = zone['effect']
            if effect == 'breath':
                factor = 0.08 + 0.92 * (1 - math.cos(phase * math.tau)) / 2
                color = sum(round(((color >> shift) & 255) * factor) << shift for shift in (16, 8, 0))
            elif effect in ('rainbow', 'wave'):
                hue = (phase * 0.15 + (i / 4 if effect == 'wave' else 0)) % 1
                r, g, b = [round(v * 255) for v in colorsys.hsv_to_rgb(hue, 1, 1)]
                color = (r << 16) | (g << 8) | b
            elif effect == 'gradient':
                a, b = [int(c[1:], 16) for c in zone['transition_colors']]
                blend = (1 - math.cos(phase * math.tau)) / 2
                color = sum(round(((a >> shift) & 255) * (1 - blend) + ((b >> shift) & 255) * blend) << shift
                            for shift in (16, 8, 0))
            elif effect == 'battery':
                if battery is None:
                    raise RGBError('No se puede leer la batería; no se mostrará un porcentaje inventado.')
                fraction = max(0, min(100, battery)) / 100
                r = round(255 * min(1, 2 * (1 - fraction)))
                g = round(255 * min(1, 2 * fraction))
                color = (r << 16) | (g << 8)
        colors.append(color)
    return colors, brightness


def battery_level(root=Path('/sys/class/power_supply')):
    """Read the internal BAT* supply, never a controller/peripheral battery.

    ASUS BAT0 does not expose scope on every kernel. Its standard system battery
    name is accepted without scope; an explicit Device/unknown scope is not.
    """
    try:
        supplies = sorted(root.glob('BAT[0-9]*'), key=lambda p: (p.name != 'BAT0', p.name))
    except OSError:
        return None
    for supply in supplies:
        if not re.fullmatch(r'BAT[0-9]+', supply.name):
            continue
        try:
            if read(supply / 'type') != 'Battery':
                continue
            scope = supply / 'scope'
            if scope.exists() and read(scope) != 'System':
                continue
            present = supply / 'present'
            if present.exists() and read(present) != '1':
                continue
            value = int(read(supply / 'capacity'))
            if 0 <= value <= 100:
                return value
        except (OSError, ValueError):
            pass
    return None


def writers():
    found = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            comm = read(proc / 'comm')
            args = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace').lower()
            if comm.lower() == 'huesync' or '/plugins/huesync/' in args:
                found.add('HueSync')
            if comm.lower() in ('hhd', 'hhd-ui') or '/bin/hhd ' in args:
                found.add('HHD')
            if comm.lower() == 'ally center' or '/plugins/ally center/' in args or '/plugins/allycenter/' in args:
                found.add('Ally Center')
            if comm.lower() in ('asusd', 'openrgb'):
                found.add(comm)
        except OSError:
            pass
    return sorted(found)


class Hardware:
    def __init__(self, path=LED, product_path=Path('/sys/class/dmi/id/product_name'), transport=None):
        self.path = path
        self.product_path = product_path
        self.transport = transport
        self.hid_last = None
        self.hid_observed = None

    def close(self):
        if self.transport is not None:
            self.transport.close()
        self.hid_last = self.hid_observed = None

    @staticmethod
    def observation(state):
        return state['device'], tuple(state['colors']), state['brightness'], state['trigger']

    def state(self):
        product = read(self.product_path)
        if 'ROG Ally' not in product or 'RC71L' not in product:
            raise RGBError('Esta versión está validada para ROG Ally RC71L. Ally X aún no está validada.')
        if read(self.path / 'multi_index').split() != ['rgb'] * 4:
            raise RGBError('El kernel no expone las cuatro zonas RGB empaquetadas esperadas.')
        maximum = int(read(self.path / 'max_brightness'))
        colors = [int(v) for v in read(self.path / 'multi_intensity').split()]
        brightness = int(read(self.path / 'brightness'))
        if maximum != 255 or len(colors) != 4 or any(not 0 <= c <= 0xffffff for c in colors) or not 0 <= brightness <= 255:
            raise RGBError('Lectura RGB no válida; no se escribirán colores.')
        trigger = read(self.path / 'trigger') if (self.path / 'trigger').exists() else '[none]'
        active = re.search(r'\[([^]]+)\]', trigger)
        sleep = None
        if (self.path / 'sleep_animation').exists() and (self.path / 'sleep_animation_index').exists():
            choices = read(self.path / 'sleep_animation_index').split()
            value = read(self.path / 'sleep_animation')
            if set(choices) == {'0', '1'} and value in choices:
                sleep = value == '1'
        result = dict(product=product, colors=colors, brightness=brightness, sleep=sleep,
                    trigger=active.group(1) if active else 'unknown', device=str(self.path.resolve()))
        result['identity'] = [result['device'], self.path.resolve().stat().st_ino]
        limits_path = self.path / 'multi_max_intensity'
        limits = [int(v) for v in read(limits_path).split()] if limits_path.exists() else [0xffffff]*4
        if limits == [255]*4:
            from .rgb_hid import RGBTransport
            if self.transport is None:
                self.transport = RGBTransport()
            try:
                node, linked, device_number = self.transport.locator((self.path/'device').resolve(strict=True))
                if Path(node).exists():
                    metadata = Path(node).stat()
                    result['identity'] += [str(node), linked, device_number, metadata.st_ino, metadata.st_ctime_ns]
                else:
                    result['identity'] += [str(node), linked, device_number]
            except ValueError as exc:
                raise RGBError('Este kernel recorta colores y no se puede usar RGB directo: ' + str(exc)) from exc
            result.update(backend='hid-rgb', verification='transport-accepted', kernel_observed=self.observation(result))
            if self.hid_last is not None:
                if self.observation(result) != self.hid_observed:
                    raise RGBError('Cambió el dispositivo o su estado sysfs; ALLY RGB ha cedido el control.')
                result.update(colors=list(self.hid_last[0]), brightness=self.hid_last[1])
            else:
                result['verification'] = 'kernel-cache-only'
        elif len(limits) == 4 and all(v >= 0xffffff for v in limits):
            result.update(backend='sysfs', verification='kernel-readback')
            if self.hid_last is not None:
                raise RGBError('Cambió la interfaz del controlador RGB; vuelve a adquirir el control.')
        else:
            raise RGBError('El kernel anuncia límites RGB no compatibles.')
        return result

    def write(self, colors, brightness):
        if (not isinstance(colors, list) or len(colors) != 4
                or any(type(c) is not int or not 0 <= c <= 0xffffff for c in colors)
                or type(brightness) is not int or not 0 <= brightness <= 255):
            raise RGBError('Frame RGB no válido.')
        before = self.state()
        if before['trigger'] != 'none':
            raise RGBError('Otro disparador del kernel controla las luces: ' + before['trigger'])
        if before['backend'] == 'hid-rgb':
            try:
                self.transport.write((self.path/'device').resolve(strict=True), colors, brightness)
                self.hid_observed = before['kernel_observed']
                self.hid_last = (list(colors), brightness)
                return self.state()
            except Exception:
                # HID has no physical color readback. Do not invent rollback or
                # send cached colors over an unknown/reconnected device.
                self.close()
                raise
        try:
            (self.path / 'multi_intensity').write_text(' '.join(map(str, colors)))
            (self.path / 'brightness').write_text(str(brightness))
            actual = self.state()
            if actual['device'] != before['device'] or actual['colors'] != colors or actual['brightness'] != brightness:
                raise RGBError('El controlador no confirmó los valores RGB solicitados.')
        except Exception:
            # Same kernel device only; never restore across disconnect/rebind.
            with contextlib.suppress(Exception):
                if self.state()['device'] == before['device']:
                    (self.path / 'multi_intensity').write_text(' '.join(map(str, before['colors'])))
                    (self.path / 'brightness').write_text(str(before['brightness']))
            raise
        return actual

    def set_sleep(self, enabled):
        if type(enabled) is not bool:
            raise RGBError('Estado de suspensión no válido.')
        state = self.state()
        if state['sleep'] is None:
            raise RGBError('El kernel no ofrece este ajuste de suspensión.')
        path = self.path / 'sleep_animation'
        try:
            path.write_text('1' if enabled else '0')
            if read(path) != ('1' if enabled else '0'):
                raise RGBError('El controlador no confirmó la animación de suspensión.')
        except Exception:
            with contextlib.suppress(OSError):
                path.write_text('1' if state['sleep'] else '0')
            raise


class Settings:
    """The last successfully applied configuration, atomically saved across boots."""
    def __init__(self, path):
        self.path = path
        self.config = None
        self.warning = ''
        if path.exists():
            try:
                self.config = validate(json.loads(path.read_text()))
            except (OSError, ValueError, TypeError, RGBError) as exc:
                self.warning = 'No se ha recuperado la configuración guardada: ' + str(exc)

    def save(self, config):
        updated = validate(config)
        if updated == self.config:
            return
        if any(p.is_symlink() for p in [self.path, *self.path.parents]):
            raise RGBError('La ruta de ajustes contiene un enlace simbólico.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.rgb-settings-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(updated, stream, ensure_ascii=False, indent=2)
                os.fchmod(stream.fileno(), 0o600)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.config = updated
        self.warning = ''


class RGBLock:
    def __init__(self, path=Path('/run/ally-rgb.lock'), owner=0):
        self.path, self.owner, self.file = path, owner, None

    def acquire(self):
        if self.file is not None:
            return
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            if os.fstat(fd).st_uid != self.owner:
                raise RGBError('El bloqueo RGB no pertenece al usuario esperado.')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(fd)
            raise
        self.file = fd

    def release(self):
        if self.file is not None:
            os.close(self.file)
            self.file = None


class Manager:
    def __init__(self, settings, hardware=None, lock=None, competitors=writers, battery=battery_level,
                 clock=time.monotonic, logger=None, *, recovery_delay=10., stable_time=2.,
                 wait_limit=60., poll=.5, off_gap=.25, monitor_factory=None):
        from .io_process import HardwareProcess, SimulatedIO
        self.hw = hardware
        self.lock = lock or RGBLock()
        self.io = SimulatedIO(hardware) if hardware is not None else HardwareProcess(self.lock)
        self.settings = Settings(settings / 'settings.json')
        self.startup_task = self.recovery_task = self.power_monitor = None
        self.logger = logger or logging.getLogger('ally-rgb')
        self.competitors, self.battery, self.clock = competitors, battery, clock
        self.monitor_factory = monitor_factory
        self.recovery_delay, self.stable_time = recovery_delay, stable_time
        self.wait_limit, self.poll, self.off_gap = wait_limit, poll, off_gap
        self.frontend_seen = float('-inf')
        self.require_frontend = hardware is None
        self.guard = asyncio.Lock()
        self.target = self.task = None
        self.paused = self.sleeping = self.closing = self.disarmed = False
        self.generation = 0
        self.last_frame = self.last_actual = None
        self.error = ''
        self.apply_error = None
        self.started = [0.] * 4
        self.changed = asyncio.Event()
        self.loader_eof_guard = False
        self.phase = 'idle'
        self.seconds_left = None
        self.editor_zone = self.settings.config['zone'] if self.settings.config else 'all'

    def frontend_ready(self):
        self.frontend_seen = self.clock()
        return dict(phase=self.phase, seconds=self.seconds_left)

    async def start(self):
        await self.sync_monitor()
        self.startup_task = asyncio.create_task(self.restore_startup())

    async def sync_monitor(self):
        config = self.target or self.settings.config
        needed = not self.closing and bool(config and (config['resume'] or self.lock.file is not None))
        if needed and self.power_monitor is None and self.monitor_factory:
            self.power_monitor = self.monitor_factory(self.power_event, logger=self.logger)
            self.power_monitor.start()
        elif not needed and self.power_monitor is not None:
            monitor, self.power_monitor = self.power_monitor, None
            await monitor.close()

    def cancel_pending(self):
        self.generation += 1
        for task in (self.startup_task, self.recovery_task):
            if task and task is not asyncio.current_task():
                task.cancel()
        self.startup_task = self.recovery_task = None
        self.phase, self.seconds_left = 'idle', None

    async def cancel_startup(self):
        self.cancel_pending()

    async def cancel_recovery(self):
        self.cancel_pending()

    async def restore_startup(self):
        try:
            task = await self.request_resume(source='startup')
            if task:
                await task
        finally:
            if self.startup_task is asyncio.current_task():
                self.startup_task = None

    def ready(self):
        return (not self.sleeping and not self.closing
                and (self.power_monitor is None or self.power_monitor.ready)
                and (not self.require_frontend or self.clock() - self.frontend_seen < 6))

    def valid(self, generation):
        return generation == self.generation and not self.sleeping and not self.closing and not self.disarmed

    async def state(self):
        error = self.error
        actual = self.last_actual
        if not self.sleeping and not self.closing:
            try:
                actual = self.last_actual = await self.io.state()
            except (OSError, ValueError, RuntimeError) as exc:
                actual, error = None, str(exc)
        if actual:
            actual = dict(actual, hex=['#%06x' % c for c in actual['colors']])
        conflicts = await asyncio.to_thread(self.competitors)
        return dict(version='1.2', supported=actual is not None, actual=actual,
                    active=self.lock.file is not None, paused=self.paused,
                    config=self.target or self.settings.config, editor_zone=self.editor_zone,
                    conflicts=conflicts, error=error, warning=self.settings.warning, battery=self.battery(),
                    recovery=dict(pending=self.recovery_task is not None, phase=self.phase,
                                  seconds=self.seconds_left, delay=self.recovery_delay,
                                  logind=self.power_monitor.logind if self.power_monitor else 'disabled',
                                  suspend_clock=self.power_monitor is not None,
                                  isolated_io=True, io_blocked=self.io.blocked, loader_eof_guard=self.loader_eof_guard))

    async def gate(self):
        others = await asyncio.to_thread(self.competitors)
        if others:
            raise RGBError('Desactiva el otro gestor RGB antes de aplicar: ' + ', '.join(others))
        if self.sleeping or self.closing:
            raise RGBError('RGB en suspensión; no se escribe hardware.')
        return await self.io.state()

    async def stop_task(self):
        task, self.task = self.task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.wait([task], timeout=.2)

    def save_settings(self, config):
        try:
            self.settings.save(config)
        except Exception as exc:
            self.settings.warning = 'No se pudo guardar para el próximo encendido: ' + str(exc)

    async def select_zone(self, zone):
        async with self.guard:
            if not isinstance(zone, str) or zone not in ZONES:
                self.error = 'Selección de zonas no válida.'
            else:
                self.editor_zone = zone
                if self.target:
                    self.target = dict(self.target, zone=zone)
                    self.save_settings(self.target)
                elif self.settings.config:
                    self.save_settings(dict(self.settings.config, zone=zone))
                self.error = ''
        return await self.state()

    async def apply(self, config, *, automatic=False, cycle=False, generation=None, identity=None):
        if not automatic:
            was_applying = self.phase == 'applying'
            self.cancel_pending()
            # Stop an in-flight automatic helper before a manual edit can win.
            if was_applying:
                self.io.abort()
                await self.io.close()
            self.disarmed = False
        async with self.guard:
            self.apply_error = None
            try:
                config = validate(config)
                if self.sleeping or self.closing:
                    raise RGBError('RGB en suspensión; no se escribe hardware.')
                self.io.suspended = False
                old = self.target
                saved = self.settings.config
                preference_only = not automatic and saved and all(config[k] == saved[k] for k in ('enabled', 'brightness', 'zones')) and config != saved
                same_lighting = old and all(config[k] == old[k] for k in ('enabled', 'brightness', 'zones'))
                if preference_only and self.lock.file is None:
                    if old is not None:
                        self.target = config
                    if not config['resume']:
                        self.paused = False
                elif same_lighting and self.task is not None and not self.paused and not cycle:
                    self.target = config
                else:
                    actual = await self.gate()
                    if automatic and (not self.valid(generation) or not self.ready()):
                        raise RGBError('Recuperación cancelada antes de escribir.')
                    if identity is not None and self.device_identity(actual) != identity:
                        raise RGBError('El dispositivo RGB cambió durante la espera; se omite este ciclo.')
                    self.lock.acquire()
                    now = self.clock()
                    started = [now if old is None or config['zones'][i] != old['zones'][i]
                               else self.started[i] for i in range(4)]
                    colors, brightness = frame(config, [now - t for t in started], self.battery())
                    if cycle:
                        self.phase = 'applying'
                        await self.io.write(colors, 0)
                        await asyncio.sleep(self.off_gap)
                        if not self.valid(generation) or not self.ready():
                            raise RGBError('Recuperación cancelada; no se fuerza encendido.')
                        await self.gate()
                    actual = await self.io.write(colors, brightness)
                    self.last_actual = actual
                    self.last_frame = (actual['colors'], actual['brightness'])
                    self.target, self.started = config, started
                    self.paused = False
                    self.changed.set()
                    if self.task is None:
                        self.task = asyncio.create_task(self.animate())
                    # Static frames need no persistent privileged I/O helper.
                    if not any(z['effect'] not in ('solid', 'battery') for z in config['zones']):
                        await self.io.close(clear=False)
                self.editor_zone = config['zone']
                self.error = ''
                if not automatic:
                    self.save_settings(config)
            except asyncio.CancelledError:
                self.lock.release()
                await self.io.close()
                raise
            except Exception as exc:
                self.apply_error, self.error = exc, str(exc)
                if self.task is None:
                    self.lock.release()
                    await self.io.close()
                    self.target = None
                    self.paused = False
        if not automatic:
            await self.sync_monitor()
            if not self.apply_error and preference_only and config['resume'] and not saved['resume']:
                await self.request_resume(source='enabled')
        return await self.state()

    async def animate(self):
        checked = 0
        try:
            while True:
                config = self.target
                if config is None or self.sleeping or self.paused:
                    return
                animated = config['enabled'] and any(z['effect'] not in ('solid', 'battery') for z in config['zones'])
                self.changed.clear()
                try:
                    await asyncio.wait_for(self.changed.wait(), .05 if animated else 1)
                except asyncio.TimeoutError:
                    pass
                async with self.guard:
                    config = self.target
                    if config is None or self.sleeping or self.paused:
                        return
                    now = self.clock()
                    if now - checked >= 1:
                        observed = await self.gate()
                        if self.last_frame and (observed['colors'], observed['brightness']) != self.last_frame:
                            raise RGBError('Otro controlador cambió las luces; ALLY RGB ha cedido el control.')
                        checked = now
                    colors, brightness = frame(config, [now - t for t in self.started], self.battery())
                    if (colors, brightness) != self.last_frame:
                        self.last_actual = await self.io.write(colors, brightness)
                        self.last_frame = (colors, brightness)
                    if not animated:
                        await self.io.close(clear=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = str(exc)
            self.lock.release()
            await self.io.close()
            self.target = None
        finally:
            if self.task is asyncio.current_task():
                self.task = None

    async def release(self):
        self.disarmed = True
        self.cancel_pending()
        await self.stop_task()
        await self.io.close()
        self.lock.release()
        self.target = self.last_frame = None
        self.paused = False
        await self.sync_monitor()
        return await self.state()

    async def pause(self):
        await self.power_event(True)
        return await self.state()

    async def resume(self):
        self.sleeping = False
        self.io.suspended = False
        task = await self.request_resume()
        if task:
            await task
        return await self.state()

    async def power_event(self, sleeping):
        # Intentionally no await of hardware, locks or process joins here.
        # Cancellation/kill just requests teardown; the I/O task reaps boundedly.
        if sleeping:
            self.cancel_pending()
            self.sleeping = True
            self.frontend_seen = float('-inf')
            self.paused = self.target is not None
            if self.task:
                self.task.cancel()
                self.task = None
            self.io.abort()
            self.lock.release()
            self.last_frame = None
        else:
            self.sleeping = False
            self.io.suspended = False
            if not self.recovery_task:
                self.frontend_seen = float('-inf')
                await self.request_resume()

    async def request_resume(self, source='wake'):
        if self.recovery_task:
            return self.recovery_task
        config = self.target or self.settings.config
        if self.closing or self.disarmed or not config or not config['resume']:
            return None
        # Duplicate wake notifications must not queue a second application.
        self.cancel_pending()
        if self.task:
            self.task.cancel()
            self.task = None
        self.io.abort()
        self.io.suspended = False
        self.lock.release()
        self.last_frame = None
        self.paused = True
        generation = self.generation
        self.recovery_task = asyncio.create_task(self.recover(generation, source))
        return self.recovery_task

    @staticmethod
    def device_identity(actual):
        return actual['device'], actual['backend'], actual.get('identity')

    async def recover(self, generation, source):
        try:
            await self.io.close()
            config = self.target or self.settings.config
            if not config or not config['enabled'] or config['brightness'] == 0:
                self.phase = 'skipped'
                self.paused = False
                return
            deadline = self.clock() + self.wait_limit
            identity, stable_since = None, None
            self.phase = 'waiting'
            self.logger.info('RGB %s: esperando Steam/logind/dispositivo; después %gs.', source, self.recovery_delay)
            while self.valid(generation) and self.clock() <= deadline:
                if await asyncio.to_thread(self.competitors):
                    raise RGBError('Recuperación cancelada: otro gestor RGB está activo.')
                if self.ready():
                    try:
                        actual = await self.io.state()  # Metadata/sysfs only; never HID ioctls.
                    except (OSError, RuntimeError, ValueError):
                        actual = None
                    if actual and actual['trigger'] != 'none':
                        raise RGBError('Recuperación cancelada: otro disparador controla las luces.')
                    current = self.device_identity(actual) if actual else None
                    if current != identity or current is None:
                        identity, stable_since = current, self.clock() if current else None
                    if identity and stable_since is not None and self.clock() - stable_since >= self.stable_time:
                        break
                else:
                    identity = stable_since = None
                await asyncio.sleep(self.poll)
            else:
                if self.valid(generation):
                    raise RGBError('Recuperación omitida: preparación no confirmada en 60 s.')
                return
            self.phase = 'countdown'
            end = self.clock() + self.recovery_delay
            while self.clock() < end:
                self.seconds_left = max(0, math.ceil(end - self.clock()))
                await asyncio.sleep(min(self.poll, max(0, end - self.clock())))
                if not self.valid(generation) or not self.ready():
                    raise RGBError('Recuperación cancelada: la sesión dejó de estar preparada.')
                actual = await self.io.state()
                if self.device_identity(actual) != identity:
                    raise RGBError('Recuperación cancelada: cambió el dispositivo RGB.')
            if not self.valid(generation):
                return
            config = self.target or self.settings.config
            await self.apply(dict(config, zone=self.editor_zone), automatic=True, cycle=True,
                             generation=generation, identity=identity)
            if self.apply_error:
                raise self.apply_error
            self.phase = 'restored'
            self.logger.info('RGB: restauración única completada, sin guardar ni reintentar.')
        except asyncio.CancelledError:
            self.logger.info('RGB: recuperación cancelada.')
            raise
        except Exception as exc:
            self.error = str(exc)
            self.phase = 'skipped'
            self.lock.release()
            await self.io.close()
            self.logger.warning('RGB: se omite este ciclo: %s', exc)
        finally:
            if self.recovery_task is asyncio.current_task():
                self.recovery_task = None
                self.seconds_left = None

    async def shutdown(self):
        self.closing = True
        self.cancel_pending()
        self.io.abort()
        await self.stop_task()
        if self.power_monitor:
            monitor, self.power_monitor = self.power_monitor, None
            await monitor.close()
        await self.io.close()
        self.lock.release()
        self.target = None

    async def set_sleep(self, enabled):
        self.cancel_pending()
        async with self.guard:
            acquired = self.lock.file is not None
            try:
                await self.gate()
                self.lock.acquire()
                await self.io.set_sleep(enabled)
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
            finally:
                if not acquired:
                    await self.io.close()
                    self.lock.release()
        return await self.state()
