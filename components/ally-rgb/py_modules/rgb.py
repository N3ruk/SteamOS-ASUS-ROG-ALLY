"""Ally-only RGB sysfs backend. No serial, termios, HID, EC or power controls."""
import asyncio
import colorsys
import contextlib
import fcntl
import json
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
    def __init__(self, path=LED, product_path=Path('/sys/class/dmi/id/product_name')):
        self.path = path
        self.product_path = product_path

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
        return dict(product=product, colors=colors, brightness=brightness, sleep=sleep,
                    trigger=active.group(1) if active else 'unknown', device=str(self.path.resolve()))

    def write(self, colors, brightness):
        if (not isinstance(colors, list) or len(colors) != 4
                or any(type(c) is not int or not 0 <= c <= 0xffffff for c in colors)
                or type(brightness) is not int or not 0 <= brightness <= 255):
            raise RGBError('Frame RGB no válido.')
        before = self.state()
        if before['trigger'] != 'none':
            raise RGBError('Otro disparador del kernel controla las luces: ' + before['trigger'])
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
    def __init__(self, settings, hardware=None, lock=None, competitors=writers, battery=battery_level, clock=time.monotonic):
        self.hw = hardware or Hardware()
        self.lock = lock or RGBLock()
        self.settings = Settings(settings / 'settings.json')
        self.startup_task = None
        self.competitors, self.battery, self.clock = competitors, battery, clock
        self.guard = asyncio.Lock()
        self.target = None
        self.task = None
        self.paused = False
        self.last_frame = None
        self.error = ''
        self.started = [0.] * 4
        self.changed = asyncio.Event()
        self.editor_zone = self.settings.config['zone'] if self.settings.config else 'all'

    async def cancel_startup(self):
        task, self.startup_task = self.startup_task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def restore_startup(self, attempts=30, interval=1):
        """Restore once, only with saved consent. Retry a late kernel device briefly.

        Never retry against another controller, a kernel trigger, or after an edit.
        """
        config = self.settings.config
        if not config or not config['resume']:
            return
        try:
            for attempt in range(attempts):
                if self.competitors():
                    self.error = 'Recuperación cancelada: otro gestor RGB está activo.'
                    return
                try:
                    actual = self.hw.state()
                except FileNotFoundError:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(interval)
                        continue
                    self.error = 'No se encontró la iluminación al encender.'
                    return
                except (OSError, ValueError, RGBError) as exc:
                    self.error = str(exc)
                    return
                if actual['trigger'] != 'none':
                    self.error = 'Recuperación cancelada: otro disparador controla las luces.'
                    return
                await self.apply(dict(config, zone=self.editor_zone), automatic=True)
                return
        finally:
            if self.startup_task is asyncio.current_task():
                self.startup_task = None

    async def state(self):
        try:
            actual = self.hw.state()
            actual['hex'] = ['#%06x' % c for c in actual['colors']]
            supported = True
            error = self.error
        except (OSError, ValueError, RGBError) as exc:
            actual, supported, error = None, False, str(exc)
        conflicts = await asyncio.to_thread(self.competitors)
        return dict(version='1.0.0', supported=supported, actual=actual,
                    active=self.lock.file is not None, paused=self.paused, config=self.target or self.settings.config,
                    editor_zone=self.editor_zone,
                    conflicts=conflicts, error=error, warning=self.settings.warning, battery=self.battery())

    def gate(self):
        others = self.competitors()
        if others:
            raise RGBError('Desactiva el otro gestor RGB antes de aplicar: ' + ', '.join(others))
        self.hw.state()

    async def stop_task(self):
        if self.task:
            task, self.task = self.task, None
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def save_settings(self, config):
        try:
            self.settings.save(config)
        except Exception as exc:
            self.settings.warning = 'No se pudo guardar para el próximo encendido: ' + str(exc)

    async def select_zone(self, zone):
        # Editor-only operation: no LED writes, locks, timer resets or worker changes.
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

    async def apply(self, config, *, automatic=False):
        if not automatic:
            await self.cancel_startup()
        async with self.guard:
            try:
                config = validate(config)
                old = self.target
                # Same lighting, including a queued editor change: no phase reset
                # or extra hardware write. Recovery preference is metadata too.
                same_lighting = old and all(config[k] == old[k] for k in ('enabled', 'brightness', 'zones'))
                if same_lighting and self.task is not None and not self.paused:
                    self.target = config
                else:
                    self.gate()
                    self.lock.acquire()
                    now = self.clock()
                    started = [now if old is None or config['zones'][i] != old['zones'][i]
                               else self.started[i] for i in range(4)]
                    colors, brightness = frame(config, [now - t for t in started], self.battery())
                    actual = self.hw.write(colors, brightness)
                    self.last_frame = (actual['colors'], actual['brightness'])
                    self.target = config
                    self.started = started
                    self.paused = False
                    self.changed.set()
                    if self.task is None:
                        self.task = asyncio.create_task(self.animate())
                self.editor_zone = config['zone']
                self.error = ''
                if not automatic:
                    self.save_settings(config)
            except Exception as exc:
                self.error = str(exc)
                if self.task is None:
                    self.lock.release()
                    self.target = None
                    self.paused = False
        return await self.state()

    async def animate(self):
        checked = 0
        try:
            while True:
                config = self.target
                if config is None:
                    return
                animated = config['enabled'] and any(z['effect'] not in ('solid', 'battery') for z in config['zones'])
                self.changed.clear()
                try:
                    await asyncio.wait_for(self.changed.wait(), .05 if animated else 1)
                except asyncio.TimeoutError:
                    pass
                async with self.guard:
                    config = self.target
                    if config is None:
                        return
                    now = self.clock()
                    if now - checked >= 1:
                        self.gate()
                        observed = self.hw.state()
                        if self.last_frame and (observed['colors'], observed['brightness']) != self.last_frame:
                            raise RGBError('Otro controlador cambió las luces; ALLY RGB ha cedido el control.')
                        checked = now
                    colors, brightness = frame(config, [now - t for t in self.started], self.battery())
                    if (colors, brightness) != self.last_frame:
                        self.hw.write(colors, brightness)
                        self.last_frame = (colors, brightness)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = str(exc)
            self.lock.release()
            self.target = None
        finally:
            if self.task is asyncio.current_task():
                self.task = None

    async def release(self):
        await self.cancel_startup()
        async with self.guard:
            await self.stop_task()
            self.lock.release()
            self.target = None
            self.paused = False
            self.last_frame = None
        return await self.state()

    async def pause(self):
        await self.cancel_startup()
        async with self.guard:
            await self.stop_task()
            self.paused = self.target is not None
            self.lock.release()
        return await self.state()

    async def resume(self):
        if self.paused and self.target and self.target['resume']:
            return await self.apply(self.target, automatic=True)
        if self.paused:
            return await self.release()
        return await self.state()

    async def set_sleep(self, enabled):
        async with self.guard:
            acquired = self.lock.file is not None
            try:
                self.gate()
                self.lock.acquire()
                self.hw.set_sleep(enabled)
                self.error = ''
            except Exception as exc:
                self.error = str(exc)
            finally:
                if not acquired:
                    self.lock.release()
        return await self.state()
