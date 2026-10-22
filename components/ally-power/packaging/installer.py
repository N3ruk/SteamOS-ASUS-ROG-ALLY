#!/usr/bin/python3
"""Offline installer. UI stays unprivileged; pkexec performs fixed-path installation."""
import argparse
import ctypes.util
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile

VERSION = '1.0.0'
PACKAGE = Path(__file__).resolve().parent
LIB = Path('/usr/local/lib/desktop-power')
HELPER = Path('/usr/local/libexec/desktop-power-helper')
COMMAND = Path('/usr/local/bin/ally-power')
MARKER = 'ally-power-package-v1'
APP_ID = 'local.AllyPower'


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ''


def compatibility(os_id, product, cpu, machine):
    errors = []
    if os_id != 'steamos':
        errors.append('Este paquete solo admite SteamOS.')
    if machine != 'x86_64':
        errors.append('Se necesita arquitectura x86_64.')
    if not ('ROG Ally' in product and ('RC71L' in product or 'RC72LA' in product)):
        errors.append('Modelo no validado: se admiten ROG Ally RC71L y Ally X RC72LA.')
    if 'AMD Ryzen Z1' not in cpu:
        errors.append('APU no validada: solo Ryzen Z1 y Z1 Extreme; no Z2 ni otras APUs.')
    return errors


def preflight():
    release = platform.freedesktop_os_release()
    product = read('/sys/class/dmi/id/product_name')
    cpu = read('/proc/cpuinfo')
    errors = compatibility(release.get('ID'), product, cpu, platform.machine())
    checks = ['Equipo: ' + product, 'Sistema: ' + release.get('PRETTY_NAME', '?')]
    for command in ('pkexec', 'kbuildsycoca6', 'steamos-readonly'):
        if not shutil.which(command):
            errors.append('Falta el comando ' + command)
    if not ctypes.util.find_library('pci'):
        errors.append('Falta libpci (paquete pciutils).')
    probe = subprocess.run(['/usr/bin/python3', '-c',
        "import gi; gi.require_version('Gtk','4.0'); gi.require_version('GdkPixbuf','2.0'); "
        "from gi.repository import Gtk,GdkPixbuf,Gio"], capture_output=True, text=True)
    if probe.returncode:
        errors.append('Faltan GTK4/PyGObject: paquetes gtk4, python-gobject, gdk-pixbuf2. ' + probe.stderr[-250:])
    if read('/sys/devices/system/cpu/smt/control') not in ('on', 'off'):
        errors.append('El kernel no permite controlar SMT en este equipo.')
    fields = ('ppt_pl1_spl', 'ppt_pl3_fppt', 'ppt_pl2_sppt')
    if not all(Path('/sys/class/firmware-attributes/asus-armoury/attributes', x, 'current_value').is_file()
               for x in fields):
        checks.append('AVISO: sin registro ASUS; el control necesitará telemetría RyzenAdj funcional.')
    checks.append('No se cambia TDP, SMT ni núcleos durante la instalación.')
    return checks, errors


def verify_package(package=PACKAGE):
    manifest = json.loads((package / 'manifest.json').read_text())
    if manifest.get('version') != VERSION:
        raise RuntimeError('Versión del manifiesto incorrecta.')
    for name, expected in manifest['sha256'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Ruta no válida en el manifiesto.')
        path = package / relative
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Archivo dañado o modificado: ' + name)
    required = ['payload/app.py', 'payload/power_backend.py', 'payload/tray.py',
                'payload/icon-gaming.png', 'payload/icon.svg', 'payload/status-notifier.xml',
                'payload/ryzenadj', 'installer.py', 'LEEME.md']
    if any(name not in manifest['sha256'] for name in required):
        raise RuntimeError('Manifiesto incompleto.')
    return manifest


def wrapper(target):
    isolation = '-I ' if target.name == 'backend.py' else ''
    return '#!/bin/sh\n# ' + MARKER + '\nexec /usr/bin/python3 ' + isolation + str(target) + ' "$@"\n'


def safe_target(path):
    # Fixed system locations only. Never traverse a symlink while privileged.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise RuntimeError('No se sobrescriben enlaces simbólicos: ' + str(part))


def atomic_text(path, text, mode=0o644):
    safe_target(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.ally-power-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def known_install(directory):
    return ((directory / 'PACKAGE-ID').is_file() and read(directory / 'PACKAGE-ID') == MARKER
            or (directory / 'backend.py').is_file() and (directory / 'ryzenadj').is_file())


def install_system(package=PACKAGE, root=Path('/')):
    """root is injectable only for isolated unit tests; no CLI staging override."""
    manifest = verify_package(package)
    destination = root / LIB.relative_to('/')
    helper = root / HELPER.relative_to('/')
    command = root / COMMAND.relative_to('/')
    for path in (destination, helper, command):
        safe_target(path)
    if destination.exists() and not known_install(destination):
        raise RuntimeError('La carpeta de destino existe pero no parece una instalación de Ally Power.')
    for path in (helper, command):
        if path.exists() and MARKER not in read(path) and '/usr/local/lib/desktop-power/' not in read(path):
            raise RuntimeError('No se sobrescribe un archivo ajeno: ' + str(path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.ally-power-stage-', dir=destination.parent))
    backup = destination.with_name('desktop-power.backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    previous = {p: (p.read_bytes(), stat.S_IMODE(p.stat().st_mode)) if p.exists() else None for p in (helper, command)}
    moved = False
    committed = False
    try:
        for name in manifest['sha256']:
            source = package / name
            if name.startswith('payload/'):
                target = stage / Path(name).relative_to('payload')
            elif name.startswith(('licenses/', 'source/')) or name in ('installer.py', 'LEEME.md', 'THIRD-PARTY.md'):
                target = stage / name
            else:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o755 if target.name == 'ryzenadj' else 0o644)
        shutil.copyfile(stage / 'power_backend.py', stage / 'backend.py')
        (stage / 'PACKAGE-ID').write_text(MARKER + '\n')
        (stage / 'VERSION').write_text(VERSION + '\n')
        stage.chmod(0o755)
        if destination.exists():
            os.replace(destination, backup)
            moved = True
        os.replace(stage, destination)
        committed = True
        atomic_text(helper, wrapper(LIB / 'backend.py'), 0o755)
        atomic_text(command, wrapper(LIB / 'app.py'), 0o755)
        return str(backup) if moved else None
    except Exception:
        if committed:
            shutil.rmtree(destination)
        if moved:
            os.replace(backup, destination)
        for path, contents in previous.items():
            if contents:
                atomic_text(path, contents[0].decode(), contents[1])
            elif path.exists():
                path.unlink()
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def uninstall_system(root=Path('/')):
    destination = root / LIB.relative_to('/')
    safe_target(destination)
    if read(destination / 'PACKAGE-ID') != MARKER:
        raise RuntimeError('No se reconoce una instalación de este paquete; no se elimina nada.')
    backup = destination.with_name('desktop-power.removed-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    for path in (root / HELPER.relative_to('/'), root / COMMAND.relative_to('/')):
        safe_target(path)
        if path.exists() and MARKER not in read(path):
            raise RuntimeError('El ejecutable ha sido modificado; no se elimina: ' + str(path))
    os.replace(destination, backup)
    for path in (root / HELPER.relative_to('/'), root / COMMAND.relative_to('/')):
        if path.exists():
            os.replace(path, backup / path.name)
    return str(backup)


def root_action(uninstall=False):
    if os.geteuid() != 0:
        raise RuntimeError('La fase de sistema necesita autorización de administrador.')
    lock_fd = os.open('/run/desktop-power.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        if os.fstat(lock.fileno()).st_uid != 0:
            raise RuntimeError('El archivo de bloqueo no es de root.')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Ally Power está controlando la APU. Ciérralo normalmente y vuelve a intentarlo.')
        if not uninstall:
            _, errors = preflight()
            if errors:
                raise RuntimeError('\n'.join(errors))
            verify_package()
        readonly = subprocess.run(['/usr/bin/steamos-readonly', 'status'], capture_output=True, text=True, check=True)
        was_readonly = readonly.stdout.strip() == 'enabled'
        if readonly.stdout.strip() not in ('enabled', 'disabled'):
            raise RuntimeError('Estado de solo lectura desconocido; no se modifica el sistema.')
        try:
            if was_readonly:
                subprocess.run(['/usr/bin/steamos-readonly', 'disable'], check=True)
            backup = uninstall_system() if uninstall else install_system()
            print('Copia recuperable: ' + str(backup) if backup else 'Instalación de sistema completada.')
        finally:
            if was_readonly:
                subprocess.run(['/usr/bin/steamos-readonly', 'enable'], check=True)


def desktop_entry(uninstall=False):
    if uninstall:
        return ('[Desktop Entry]\nType=Application\nName=Desinstalar Ally Power\n'
                'Exec=/usr/bin/python3 /usr/local/lib/desktop-power/installer.py --uninstall\n'
                'Icon=/usr/local/lib/desktop-power/icon-gaming.png\nTerminal=false\nCategories=Settings;\n')
    return ('[Desktop Entry]\nType=Application\nName=Ally Power\n'
            'Comment=TDP, SMT, núcleos e hilos para ROG Ally\n'
            'Exec=/usr/local/bin/ally-power\nIcon=/usr/local/lib/desktop-power/icon-gaming.png\n'
            'Terminal=false\nCategories=Settings;HardwareSettings;\nStartupNotify=true\nStartupWMClass=local.AllyPower\n')


def refresh_desktop():
    env = dict(os.environ)
    # Use the desktop's language, not an inherited C.UTF-8 tool locale.
    env.pop('LC_ALL', None)
    env.pop('LC_MESSAGES', None)
    env['LANG'] = os.environ.get('LANG', 'es_ES.UTF-8')
    subprocess.run(['kbuildsycoca6', '--noincremental'], env=env, capture_output=True)


def ui(text, ask=False):
    print(text, flush=True)
    if shutil.which('kdialog') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        result = subprocess.run(['kdialog', '--title', 'Ally Power ' + VERSION,
                                 '--yesno' if ask else '--msgbox', text])
        return result.returncode == 0
    if ask:
        return input('¿Continuar? [s/N] ').strip().lower() == 's'
    return True


def app_running():
    probe = subprocess.run(['/usr/bin/python3', '-c',
        "from gi.repository import Gio,GLib; b=Gio.bus_get_sync(Gio.BusType.SESSION,None); "
        "r=b.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus',"
        "'NameHasOwner',GLib.Variant('(s)',('local.AllyPower',)),None,Gio.DBusCallFlags.NONE,2000,None); "
        "raise SystemExit(0 if r.unpack()[0] else 1)"], capture_output=True)
    return probe.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='Instalador offline de Ally Power para SteamOS')
    parser.add_argument('--check', action='store_true', help='Comprobar integridad y requisitos sin instalar')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--root-install', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--root-uninstall', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.root_install or args.root_uninstall:
        root_action(args.root_uninstall)
        return
    if os.geteuid() == 0:
        raise RuntimeError('Ejecuta el instalador con tu usuario, sin sudo. Pedirá autorización cuando corresponda.')
    if not args.uninstall:
        verify_package()
        checks, errors = preflight()
        print('\n'.join(checks + errors), flush=True)
        if errors:
            raise RuntimeError('No se cumplen los requisitos. No se han hecho cambios.\n' + '\n'.join(errors))
        if args.check:
            print('CHECK OK: integridad, modelo y dependencias. No prueba escrituras de hardware.')
            return
    if app_running():
        raise RuntimeError('Cierra Ally Power, también su icono de bandeja, y vuelve a ejecutar el instalador.')
    question = ('¿Desinstalar Ally Power? Se conservará una copia recuperable del programa. '
                'No se modificará el TDP actual.' if args.uninstall else
                '¿Instalar Ally Power ' + VERSION + '?\n\nSe instalarán la app y un ayudante en /usr/local. '
                'Si SteamOS está protegido, se desactivará temporalmente su modo de solo lectura y se restaurará al terminar. '
                'No se instalarán paquetes, módulos ni servicios. No se cambiará TDP/SMT. '
                'Ally X y Z1 no Extreme aún requieren prueba física.\n\nLa clave se solicita en la ventana del sistema.')
    if not ui(question, ask=True):
        return
    subprocess.run(['pkexec', '/usr/bin/python3', str(Path(__file__).resolve()),
                    '--root-uninstall' if args.uninstall else '--root-install'], check=True)
    applications = Path.home() / '.local/share/applications'
    applications.mkdir(parents=True, exist_ok=True)
    for uninstall, name in ((False, 'local.AllyPower.desktop'), (True, 'local.AllyPower.Uninstall.desktop')):
        target = applications / name
        if target.exists():
            backup = target.with_name(name + '.backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            shutil.copy2(target, backup)
        if args.uninstall:
            if target.exists() and '/usr/local/' in read(target):
                target.unlink()
        else:
            atomic_text(target, desktop_entry(uninstall))
    refresh_desktop()
    ui('Ally Power desinstalado. Copia recuperable en /usr/local/lib/desktop-power.removed-*.' if args.uninstall else
       'Instalado. Busca Ally Power en el menú de KDE.\n'
       'El primer Aplicar pedirá autorización. Conserva este instalador por si una actualización de SteamOS borra /usr/local.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if '--root-install' in sys.argv or '--root-uninstall' in sys.argv or '--check' in sys.argv:
            print('ERROR: ' + str(exc), file=sys.stderr)
        else:
            ui('No se ha completado la operación:\n' + str(exc))
        sys.exit(1)
