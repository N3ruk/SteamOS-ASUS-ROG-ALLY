#!/usr/bin/python3
"""Per-user installer; never changes Bluetooth or uses administrator privileges."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

VERSION = '1.0.0'
APP_ID = 'local.BluetoothTrustManager'
MARKER = 'confianza-bluetooth-v1'
PACKAGE = Path(__file__).resolve().parent


def verify(package):
    manifest = json.loads((package / 'manifest.json').read_text())
    if manifest['version'] != VERSION:
        raise RuntimeError('Versión de paquete incorrecta.')
    required = {'payload/app.py', 'payload/bluetooth_backend.py', 'payload/controller.svg', 'installer.py'}
    if not required.issubset(manifest['files']):
        raise RuntimeError('Paquete incompleto.')
    for name, expected in manifest['files'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise RuntimeError('Ruta no válida en el manifiesto.')
        target = package / path
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Archivo dañado o modificado: ' + name)


def requirements():
    errors = []
    if platform.freedesktop_os_release().get('ID') != 'steamos':
        errors.append('Este instalador está preparado para SteamOS.')
    check = subprocess.run(['/usr/bin/python3', '-c',
        "import gi;gi.require_version('Gtk','4.0');from gi.repository import Gtk,Gio,Gdk,Pango"],
        capture_output=True, text=True)
    if check.returncode:
        errors.append('Faltan dependencias: Python 3, python-gobject y GTK4.\n' + check.stderr[-250:])
    if not shutil.which('kbuildsycoca6'):
        errors.append('Falta KDE Plasma 6 / kbuildsycoca6.')
    return errors


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('No se sobrescriben enlaces simbólicos: ' + str(path))


def atomic(path, contents, mode=0o644):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.confianza-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contents)
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def quote_argument(value):
    value = str(value).replace('%', '%%').replace('\\', '\\\\').replace('"', '\\"')
    return '"' + value.replace('$', '\\$').replace('`', '\\`') + '"'


def launcher(directory, uninstall=False):
    command = '/usr/bin/python3 ' + quote_argument(directory / ('installer.py' if uninstall else 'app.py'))
    if uninstall:
        command += ' --uninstall'
    return ('[Desktop Entry]\nType=Application\nName=' + ('Desinstalar Confianza Bluetooth' if uninstall else 'Confianza Bluetooth')
            + '\nComment=Gestionar dispositivos Bluetooth de confianza\nExec=' + command
            + '\nIcon=' + str(directory / 'controller.svg')
            + '\nTerminal=false\nCategories=Settings;HardwareSettings;\nKeywords=Bluetooth;PS3;mando;confianza;\n'
            + 'StartupNotify=true\nStartupWMClass=' + APP_ID + '\nX-ConfianzaBluetooth-Managed=true\n').encode()


def locations(data):
    return (data / 'bluetooth-trust-manager', data / 'applications' / (APP_ID + '.desktop'),
            data / 'applications' / (APP_ID + '.Uninstall.desktop'),
            data / 'icons/hicolor/scalable/apps' / (APP_ID + '.svg'))


def install(package, data):
    verify(package)
    directory, desktop, uninstaller, icon = locations(data)
    for path in (directory, desktop, uninstaller, icon):
        safe(path)
    if directory.exists() and not ((directory / 'app.py').is_file() and (directory / 'bluetooth_backend.py').is_file()):
        raise RuntimeError('La carpeta de destino no corresponde a esta app. No se ha sobrescrito.')
    data.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.confianza-stage-', dir=data))
    backup = data / ('bluetooth-trust-manager.backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    previous = {path: path.read_bytes() if path.exists() else None for path in (desktop, uninstaller, icon)}
    old_moved = False
    new_moved = False
    try:
        for name in ('app.py', 'bluetooth_backend.py', 'controller.svg', 'test_app.py', 'README.md'):
            shutil.copyfile(package / 'payload' / name, stage / name)
        for name in ('installer.py', 'LEEME.md', 'LICENSE.txt'):
            shutil.copyfile(package / name, stage / name)
        (stage / 'PACKAGE-ID').write_text(MARKER)
        (stage / 'VERSION').write_text(VERSION)
        stage.chmod(0o755)
        if directory.exists() or any(value is not None for value in previous.values()):
            backup.mkdir()
            if directory.exists():
                os.replace(directory, backup / 'app')
                old_moved = True
            for index, (path, contents) in enumerate(previous.items()):
                if contents is not None:
                    (backup / (str(index) + '-' + path.name)).write_bytes(contents)
        os.replace(stage, directory)
        new_moved = True
        atomic(desktop, launcher(directory))
        atomic(uninstaller, launcher(directory, True))
        atomic(icon, (directory / 'controller.svg').read_bytes())
        return backup if backup.exists() else None
    except Exception:
        if new_moved:
            shutil.rmtree(directory)
        if old_moved:
            os.replace(backup / 'app', directory)
        for path, contents in previous.items():
            if contents is not None:
                atomic(path, contents)
            elif path.exists():
                path.unlink()
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def uninstall(data):
    directory, desktop, uninstaller, icon = locations(data)
    for path in (directory, desktop, uninstaller, icon):
        safe(path)
    if not (directory / 'PACKAGE-ID').is_file() or (directory / 'PACKAGE-ID').read_text() != MARKER:
        raise RuntimeError('No hay una instalación gestionada por este paquete. No se borra nada.')
    backup = data / ('bluetooth-trust-manager.removed-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir()
    svg = (directory / 'controller.svg').read_bytes()
    os.replace(directory, backup / 'app')
    for path in (desktop, uninstaller):
        if path.exists() and 'X-ConfianzaBluetooth-Managed=true' in path.read_text():
            os.replace(path, backup / path.name)
    if icon.exists() and icon.read_bytes() == svg:
        os.replace(icon, backup / icon.name)
    return backup


def refresh_cache():
    environment = dict(os.environ)
    environment.pop('LC_ALL', None)
    environment.pop('LC_MESSAGES', None)
    subprocess.run(['kbuildsycoca6', '--noincremental'], env=environment, capture_output=True)


def dialog(text, confirm=False):
    print(text, flush=True)
    if shutil.which('kdialog') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return subprocess.run(['kdialog', '--title', 'Confianza Bluetooth ' + VERSION,
                               '--yesno' if confirm else '--msgbox', text]).returncode == 0
    return input('¿Continuar? [s/N] ').strip().lower() == 's' if confirm else True


def running():
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    reply = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                         'NameHasOwner', GLib.Variant('(s)', (APP_ID,)), None,
                         Gio.DBusCallFlags.NONE, 2000, None)
    return reply.unpack()[0]


def main():
    parser = argparse.ArgumentParser(description='Instalar Confianza Bluetooth en SteamOS sin sudo')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise RuntimeError('Ejecuta con tu usuario normal, sin sudo. No necesita administrador.')
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    if not data.is_absolute():
        raise RuntimeError('XDG_DATA_HOME debe ser una ruta absoluta.')
    if not args.uninstall:
        verify(PACKAGE)
        errors = requirements()
        if errors:
            raise RuntimeError('\n'.join(errors))
        if args.check:
            print('CHECK OK: integridad y dependencias. Sin instalar ni modificar Bluetooth.')
            return
    if running():
        raise RuntimeError('Cierra Confianza Bluetooth antes de instalar o desinstalar.')
    question = ('¿Desinstalar Confianza Bluetooth? Se guardará una copia recuperable.' if args.uninstall else
                '¿Instalar Confianza Bluetooth para tu usuario?\n\nSin sudo, sin tocar el sistema de solo lectura '
                'y sin cambiar ningún dispositivo Bluetooth.')
    if not dialog(question, confirm=True):
        return
    backup = uninstall(data) if args.uninstall else install(PACKAGE, data)
    refresh_cache()
    text = ('Desinstalación completada.' if args.uninstall else 'Instalado. Busca Confianza Bluetooth en el menú de KDE.')
    if backup:
        text += '\nCopia recuperable: ' + str(backup)
    dialog(text)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if '--check' in sys.argv:
            print('ERROR: ' + str(exc), file=sys.stderr)
        else:
            dialog('No se ha completado la operación:\n' + str(exc))
        sys.exit(1)
