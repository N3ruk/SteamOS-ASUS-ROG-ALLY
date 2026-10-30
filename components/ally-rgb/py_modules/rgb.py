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
         'pair23': (1, 2), 'pair14': (0, 3),
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
    def __init__(self, path=LED, product_path=Path('/sys/class/dmi/id/product_name'), transport=None, write_guard=None):
        self.write_guard = write_guard or (lambda:None)
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
        self.write_guard()
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
                self.transport = RGBTransport(gate=self.write_guard)
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
            self.write_guard()
            (self.path / 'multi_intensity').write_text(' '.join(map(str, colors)))
            self.write_guard()
            (self.path / 'brightness').write_text(str(brightness))
            actual = self.state()
            if actual['device'] != before['device'] or actual['colors'] != colors or actual['brightness'] != brightness:
                raise RGBError('El controlador no confirmó los valores RGB solicitados.')
        except Exception:
            # Same kernel device only; never restore across disconnect/rebind.
            with contextlib.suppress(Exception):
                if self.state()['device'] == before['device']:
                    self.write_guard()
                    (self.path / 'multi_intensity').write_text(' '.join(map(str, before['colors'])))
                    self.write_guard()
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
            self.write_guard()
            path.write_text('1' if enabled else '0')
            if read(path) != ('1' if enabled else '0'):
                raise RGBError('El controlador no confirmó la animación de suspensión.')
        except Exception:
            with contextlib.suppress(Exception):
                self.write_guard()
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
    CANDIDATE = 'session-scope-v2'

    def __init__(self, settings, hardware=None, lock=None, competitors=writers, battery=battery_level,
                 clock=time.monotonic, logger=None, *, recovery_delay=10., stable_time=2.,
                 wait_limit=60., poll=.5, off_gap=.25, monitor_factory=None,
                 offset=None, awake=None, frozen=None):
        from .io_process import HardwareProcess, SimulatedIO
        from .session_io import suspend_offset, session_awake, session_frozen
        self.hw = hardware
        self.lock = lock or RGBLock()
        self.io = SimulatedIO(hardware) if hardware is not None else HardwareProcess(self.lock)
        self.settings = Settings(settings / 'settings.json')
        self.logger = logger or logging.getLogger('ally-rgb')
        self.competitors, self.battery, self.clock = competitors, battery, clock
        self.offset = offset or suspend_offset
        self.baseline = self.offset()
        self.frozen = frozen or (session_frozen if hardware is None else lambda:False)
        async def simulated_awake(): return True
        self.awake = awake or (session_awake if hardware is None else simulated_awake)
        self.recovery_delay, self.wait_limit = recovery_delay, wait_limit
        self.frontend_seen = None
        self.guard = asyncio.Lock()
        self.target = self.task = None
        self.pending = None
        self.startup_task = self.recovery_task = self.power_monitor = None
        self.paused = self.sleeping = self.closing = self.disarmed = False
        self.generation = 0
        self.last_frame = None
        self.last_actual = hardware.state() if hardware is not None else None
        # VFS presence only. Never read LED attributes from status/heartbeat.
        self.supported = hardware is not None or LED.is_dir()
        self.error = ''
        self.apply_error = None
        self.started = [0.] * 4
        self.changed = asyncio.Event()
        self.loader_eof_guard = False
        self.phase = 'idle'
        self.seconds_left = None
        self.editor_zone = self.settings.config['zone'] if self.settings.config else 'all'

    async def start(self):
        self.arm('startup')

    async def sync_monitor(self):
        # Deliberately no logind subscriptions, clock watchers or timers.
        return

    def cancel_pending(self):
        self.generation += 1
        self.pending = None
        self.phase, self.seconds_left = 'idle', None
        task, self.startup_task = self.startup_task, None
        if task and task is not asyncio.current_task(): task.cancel()

    async def cancel_startup(self): self.cancel_pending()
    async def cancel_recovery(self): self.cancel_pending()

    def arm(self, source):
        config = self.target or self.settings.config
        if self.closing or self.disarmed or not config or not config['resume']:
            return
        self.cancel_pending()
        self.pending = dict(generation=self.generation, source=source, end=None,
                            expires=self.clock()+self.wait_limit, last=None)
        self.phase = 'waiting'
        self.logger.info('RGB candidate=%s: %s armed; waiting for session pulses, no RGB polling.', self.CANDIDATE, source)

    async def restore_startup(self):
        self.arm('startup')
        if self.hw is not None:
            await self.frontend_ready()  # Simulated test clock only; production waits for Steam.

    async def frontend_ready(self):
        if self.frozen():
            if self.pending:
                self.pending['end'], self.pending['last'] = None, None
                self.phase, self.seconds_left = 'waiting', None
            return dict(phase=self.phase, seconds=self.seconds_left)
        now, offset = self.clock(), self.offset()
        if offset - self.baseline > .25:
            self.cancel_pending()
            await self.stop_task()
            await self.io.close()
            self.lock.release()
            self.io.suspended = False
            self.last_frame = None
            self.paused = self.sleeping = False
            self.baseline = offset
            self.arm('session-resumed')
        self.frontend_seen = now
        pending = self.pending
        if not pending or self.closing:
            return dict(phase=self.phase, seconds=self.seconds_left)
        config = self.target or self.settings.config
        if not config or not config['resume'] or self.disarmed:
            self.cancel_pending()
        elif not config['enabled'] or config['brightness'] == 0:
            self.pending, self.phase = None, 'skipped-off'
        elif now > pending['expires']:
            self.pending, self.phase = None, 'skipped'
            self.error = 'Recuperación omitida: no llegaron pulsos continuos de Steam.'
        elif self.frozen():
            # A pulse already queued before the freezer must not advance anything.
            pending['end'], pending['last'] = None, None
            self.phase = 'waiting'
        else:
            if pending['last'] is None or now - pending['last'] > 4:
                pending['end'] = now + self.recovery_delay
            pending['last'] = now
            self.phase = 'countdown'
            self.seconds_left = max(0, math.ceil(pending['end']-now))
            if now >= pending['end']:
                # Consume BEFORE awaiting anything: duplicate pulses cannot launch twice.
                self.pending = None
                self.seconds_left = None
                generation = pending['generation']
                self.phase = 'applying'
                await self.apply(dict(config,zone=self.editor_zone),automatic=True,generation=generation)
                if generation != self.generation:
                    return dict(phase=self.phase,seconds=self.seconds_left)
                if self.apply_error:
                    self.phase = 'skipped'
                    self.logger.warning('RGB candidate=%s: one-shot skipped: %s', self.CANDIDATE, self.error)
                elif generation == self.generation:
                    self.phase = 'restored'
                    self.logger.info('RGB candidate=%s: profile restored ONCE; no off/on cycle; session scope=%s', self.CANDIDATE, getattr(self.io,'last_scope',None))
        return dict(phase=self.phase, seconds=self.seconds_left)

    async def state(self):
        # Cache only: a 2 s UI poll must never create helpers or access LED sysfs/HID.
        actual = self.last_actual
        if actual:
            actual = dict(actual,hex=['#%06x'%c for c in actual['colors']])
        conflicts = await asyncio.to_thread(self.competitors)
        return dict(version='1.2', supported=self.supported, actual=actual,
                    active=self.lock.file is not None, applied=self.target is not None,
                    paused=self.paused,config=self.target or self.settings.config,
                    editor_zone=self.editor_zone,conflicts=conflicts,error=self.error,
                    warning=self.settings.warning,battery=self.battery(),
                    recovery=dict(pending=self.pending is not None,phase=self.phase,
                                  seconds=self.seconds_left,delay=self.recovery_delay,
                                  candidate=self.CANDIDATE,logind='on-demand-only',suspend_clock=False,
                                  background_rgb_poll=False,session_scoped=True,
                                  scope=getattr(self.io,'last_scope',None),isolated_io=True,
                                  io_blocked=self.io.blocked,loader_eof_guard=self.loader_eof_guard))

    async def gate(self):
        others = await asyncio.to_thread(self.competitors)
        if others:
            raise RGBError('Desactiva el otro gestor RGB antes de aplicar: '+', '.join(others))
        if self.sleeping or self.closing or self.frozen() or not await self.awake():
            raise RGBError('Sesión no preparada; se omite E/S RGB.')

    async def stop_task(self):
        task, self.task = self.task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.wait([task],timeout=.2)

    def save_settings(self,config):
        try: self.settings.save(config)
        except Exception as exc:
            self.settings.warning = 'No se pudo guardar para el próximo encendido: '+str(exc)

    async def select_zone(self,zone):
        async with self.guard:
            if not isinstance(zone,str) or zone not in ZONES:
                self.error = 'Selección de zonas no válida.'
            else:
                self.editor_zone = zone
                if self.target:
                    self.target = dict(self.target,zone=zone)
                    self.save_settings(self.target)
                elif self.settings.config:
                    self.save_settings(dict(self.settings.config,zone=zone))
                self.error = ''
        return await self.state()

    @staticmethod
    def dynamic(config):
        return config['enabled'] and any(z['effect']!='solid' for z in config['zones'])

    async def apply(self,config,*,automatic=False,generation=None,**unused):
        if not automatic:
            self.cancel_pending()
            self.disarmed = False
        enable_after = False
        async with self.guard:
            self.apply_error = None
            try:
                config = validate(config)
                old, saved = self.target, self.settings.config
                same = old and all(config[k]==old[k] for k in ('enabled','brightness','zones'))
                preference_only = not automatic and saved and config!=saved and all(config[k]==saved[k] for k in ('enabled','brightness','zones'))
                if preference_only or (same and not self.paused and not automatic):
                    if self.target is not None: self.target = config
                else:
                    await self.gate()
                    if automatic and (generation!=self.generation or self.disarmed or self.offset()-self.baseline>.25):
                        raise RGBError('Recuperación cancelada antes de escribir.')
                    self.io.suspended = False
                    self.lock.acquire()
                    now = self.clock()
                    started = [now if old is None or config['zones'][i]!=old['zones'][i] else self.started[i] for i in range(4)]
                    colors,brightness = frame(config,[now-t for t in started],self.battery())
                    # Fresh descriptor sends desired brightness + colors; zero/off is unnecessary.
                    actual = await self.io.write(colors,brightness)
                    self.last_actual = actual
                    self.last_frame = (actual['colors'],actual['brightness'])
                    self.target,self.started = config,started
                    self.paused = False
                    self.changed.set()
                    if self.dynamic(config):
                        if self.task is None: self.task = asyncio.create_task(self.animate())
                    else:
                        await self.stop_task()
                        await self.io.close(clear=False)
                        self.lock.release()  # A static profile needs no permanent ownership/worker.
                self.editor_zone = config['zone']
                self.error = ''
                if not automatic:
                    enable_after = bool(saved and not saved['resume'] and config['resume'])
                    self.save_settings(config)
            except asyncio.CancelledError:
                await self.io.close()
                self.lock.release()
                raise
            except Exception as exc:
                self.apply_error,self.error = exc,str(exc)
                if self.task is None:
                    await self.io.close()
                    self.lock.release()
        if enable_after and not self.apply_error:
            self.arm('enabled')
        return await self.state()

    async def animate(self):
        from .session_io import SessionBoundary
        checked = 0
        try:
            while self.target and self.dynamic(self.target):
                self.changed.clear()
                try:
                    await asyncio.wait_for(self.changed.wait(),1 if all(z['effect'] in ('solid','battery') for z in self.target['zones']) else .05)
                except asyncio.TimeoutError: pass
                if self.frozen() or self.offset()-self.baseline>.25:
                    self.paused,self.phase = True,'awaiting-session'
                    return  # Do NOT kill/close an I/O helper at PrepareForSleep.
                async with self.guard:
                    config = self.target
                    if config is None or not self.dynamic(config): return
                    now = self.clock()
                    if now-checked>=1:
                        others = await asyncio.to_thread(self.competitors)
                        if others: raise RGBError('Otro gestor RGB activo: '+', '.join(others))
                        checked = now
                    colors,brightness = frame(config,[now-t for t in self.started],self.battery())
                    if (colors,brightness)!=self.last_frame:
                        self.last_actual = await self.io.write(colors,brightness)
                        self.last_frame = (colors,brightness)
        except asyncio.CancelledError:
            raise
        except SessionBoundary:
            self.paused,self.phase = True,'awaiting-session'
        except Exception as exc:
            self.error = str(exc)
            self.target = None
            await self.io.close()
            self.lock.release()
        finally:
            if self.task is asyncio.current_task(): self.task = None

    async def release(self):
        self.disarmed = True
        self.cancel_pending()
        await self.stop_task()
        await self.io.close()
        self.lock.release()
        self.target = self.last_frame = None
        self.paused = False
        return await self.state()

    async def pause(self):
        self.cancel_pending()
        await self.stop_task()
        self.paused = self.target is not None
        self.sleeping = True
        # Manual API/test pause, not registered as a sleep callback.
        if not self.frozen(): await self.io.close()
        self.lock.release()
        return await self.state()

    async def request_resume(self,source='wake'):
        self.sleeping = False
        await self.stop_task()
        await self.io.close()
        self.lock.release()
        self.io.suspended = False
        self.last_frame = None
        self.baseline = self.offset()
        self.arm(source)
        return None

    async def resume(self):
        await self.request_resume()
        if self.hw is not None: await self.frontend_ready()
        return await self.state()

    async def power_event(self,sleeping):
        # Compatibility for tests/manual calls only. Production subscribes to nothing.
        if sleeping:
            self.cancel_pending()
            self.sleeping = True
            self.paused = self.target is not None
        else:
            await self.request_resume()

    async def shutdown(self):
        self.closing = True
        self.cancel_pending()
        await self.stop_task()
        await self.io.close()
        self.lock.release()
        self.target = None

    async def set_sleep(self,enabled):
        self.cancel_pending()
        async with self.guard:
            try:
                await self.gate()
                self.lock.acquire()
                await self.io.set_sleep(enabled)
                self.error = ''
            except Exception as exc: self.error = str(exc)
            finally:
                if self.task is None:
                    await self.io.close()
                    self.lock.release()
        return await self.state()
