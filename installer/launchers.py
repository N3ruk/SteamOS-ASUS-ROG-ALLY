"""Per-user launcher transactions; no privilege, hardware or session changes.

This module is also copied into each installed component as its uninstaller.
"""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime

IDS = ('return-gaming', 'default-mode')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def guard(path):
    """Reject symlink parents; the final object may itself be a symlink."""
    path = Path(path)
    if not path.is_absolute():
        raise RuntimeError('La ruta debe ser absoluta: ' + str(path))
    for parent in path.parents:
        if parent.is_symlink():
            raise RuntimeError('Directorio enlazado: ' + str(parent))
    if path.exists() and path.is_dir():
        raise RuntimeError('Se esperaba un archivo: ' + str(path))


def snapshot(path):
    guard(path)
    if path.is_symlink():
        return {'kind': 'link', 'target': os.readlink(path)}
    if path.exists():
        if not stat.S_ISREG(path.stat().st_mode):
            raise RuntimeError('Archivo especial no permitido: ' + str(path))
        return {'kind': 'file', 'data': base64.b64encode(path.read_bytes()).decode(),
                'mode': stat.S_IMODE(path.stat().st_mode)}
    return {'kind': 'absent'}


def same(path, state):
    return snapshot(path) == state


def put(path, state):
    guard(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if state['kind'] == 'absent':
        if path.exists() or path.is_symlink():
            path.unlink()
        return
    fd, tmp = tempfile.mkstemp(prefix='.ally-stage-', dir=path.parent)
    tmp = Path(tmp)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if state['kind'] == 'file':
                stream.write(base64.b64decode(state['data']))
                stream.flush()
                os.fsync(stream.fileno())
        if state['kind'] == 'link':
            tmp.unlink()
            tmp.symlink_to(state['target'])
        else:
            tmp.chmod(state['mode'])
        os.replace(tmp, path)
    finally:
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()


def file_state(data, mode=0o644):
    if isinstance(data, str):
        data = data.encode()
    return {'kind': 'file', 'data': base64.b64encode(data).decode(), 'mode': mode}


def quote_exec(value):
    # Desktop-entry Exec quoting is NOT shell quoting; escape reserved characters.
    text = str(value).replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        text = text.replace(char, '\\' + char)
    return '"' + text + '"'


def bases(home=None):
    home = Path(home) if home is not None else Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', str(home / '.local/share')))
    state = Path(os.environ.get('XDG_STATE_HOME', str(home / '.local/state')))
    if not data.is_absolute() or not state.is_absolute():
        raise RuntimeError('Las rutas XDG deben ser absolutas.')
    return home, data, state


def receipt_path(component, state):
    if component not in IDS:
        raise RuntimeError('Componente desconocido')
    path = state / 'steamos-ally-suite' / component / 'receipt.json'
    guard(path)
    if path.is_symlink():
        raise RuntimeError('Recibo enlazado no permitido')
    return path


def desktop_dir(home):
    if shutil.which('xdg-user-dir'):
        result = subprocess.run(['xdg-user-dir', 'DESKTOP'], text=True, capture_output=True)
        if result.returncode == 0 and result.stdout.strip():
            target = Path(result.stdout.strip())
            if target.is_absolute() and target != home:
                return target
    return home / 'Desktop'


def desired(component, source, data, desktop):
    app = data / 'steamos-ally-suite' / component
    if component == 'return-gaming':
        script, icon = 'return-to-gaming.sh', 'GAMEMODE'
        name, filename = 'Return to Gaming Mode', 'Return.desktop'
        comment = 'Volver al modo Gaming con confirmación'
    else:
        script, icon = 'toggle-default-mode.sh', 'steamos-default-mode-toggle'
        name, filename = 'Alternar arranque de SteamOS', 'steamos-default-mode-toggle.desktop'
        comment = 'Alterna el arranque predeterminado: Escritorio / Gaming'
    content = ('[Desktop Entry]\nType=Application\nName=' + name + '\nComment=' + comment +
               '\nExec=/bin/bash ' + quote_exec(app / script) + '\nIcon=' + icon +
               '\nTerminal=false\nCategories=Utility;System;\nStartupNotify=false\n')
    remove = ('[Desktop Entry]\nType=Application\nName=Desinstalar ' + name +
              '\nExec=/usr/bin/python3 ' + quote_exec(app / 'uninstall.py') + ' ' + component +
              '\nIcon=edit-delete\nTerminal=false\nCategories=Utility;System;\n')
    mapping = {
        app / script: file_state((source / script).read_bytes(), 0o755),
        app / 'uninstall.py': file_state(Path(__file__).read_bytes()),
        data / 'applications' / filename: file_state(content, 0o755),
        data / 'applications' / ('ally-suite-uninstall-' + component + '.desktop'): file_state(remove),
        data / 'icons/hicolor' / ('256x256' if component == 'return-gaming' else '512x512') / 'apps' / (icon + '.png'):
            file_state((source / (icon + '.png')).read_bytes()),
    }
    if component == 'return-gaming':
        mapping[desktop / filename] = file_state(content, 0o755)
    return mapping


def transaction(changes):
    before = {p: snapshot(p) for p in changes}
    applied = []
    try:
        for path, state in changes.items():
            put(path, state)
            applied.append(path)
    except Exception:
        for path in reversed(applied):
            put(path, before[path])
        raise


def _install(component, source, home=None, desktop=None):
    home, data, state = bases(home)
    receipt = receipt_path(component, state)
    targets = desired(component, Path(source), data, Path(desktop) if desktop else desktop_dir(home))
    # Validate every path before touching any file.
    for path in targets:
        guard(path)
    old = json.loads(receipt.read_text()) if receipt.exists() else None
    if old and (old.get('component') != component or old.get('schema') != 1):
        raise RuntimeError('Recibo incompatible; no se modifica nada.')
    if old:
        for text, entry in old['files'].items():
            if not same(Path(text), entry['installed']):
                raise RuntimeError('Archivo modificado por el usuario: ' + text)
        if set(old['files']) != {str(p) for p in targets}:
            raise RuntimeError('Las rutas de instalación han cambiado; desinstala primero la versión anterior.')
    record = {'schema': 1, 'component': component, 'files': {}}
    for path, installed in targets.items():
        original = old['files'][str(path)]['original'] if old else snapshot(path)
        record['files'][str(path)] = {'original': original, 'installed': installed}
    changes = dict(targets)
    changes[receipt] = file_state(json.dumps(record, ensure_ascii=False, indent=2), 0o600)
    transaction(changes)
    return receipt


def _uninstall(component, home=None):
    home, data, state = bases(home)
    receipt = receipt_path(component, state)
    if not receipt.exists():
        raise RuntimeError('No hay una instalación gestionada de este lanzador.')
    record = json.loads(receipt.read_text())
    if record.get('component') != component or record.get('schema') != 1:
        raise RuntimeError('Recibo incompatible.')
    changes = {}
    for text, entry in record['files'].items():
        path = Path(text)
        if not same(path, entry['installed']):
            raise RuntimeError('Archivo modificado; se conserva y no se desinstala nada: ' + text)
        changes[path] = entry['original']
    archive = receipt.with_name('removed-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    # Keep a recoverable snapshot of installed files and originals.
    changes[archive] = file_state(receipt.read_bytes(), 0o600)
    changes[receipt] = {'kind': 'absent'}
    transaction(changes)
    return archive


@contextmanager
def locked(component, home):
    state = bases(home)[2]
    lock = receipt_path(component, state).with_name('operation.lock')
    guard(lock)
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Ya hay una operación de este lanzador en curso.')
        yield
    finally:
        os.close(fd)


def install(component, source, home=None, desktop=None):
    with locked(component, home):
        return _install(component, source, home, desktop)


def uninstall(component, home=None):
    with locked(component, home):
        return _uninstall(component, home)


def refresh():
    env = dict(os.environ)
    env.pop('LC_ALL', None)
    env.pop('LC_MESSAGES', None)
    for cmd in (['kbuildsycoca6', '--noincremental'], ['gtk-update-icon-cache', '-f', '-t', str(bases()[1] / 'icons/hicolor')]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, env=env, capture_output=True)


if __name__ == '__main__':
    if os.geteuid() == 0:
        sys.exit('Ejecuta como usuario normal, sin sudo.')
    component = sys.argv[1] if len(sys.argv) == 2 else ''
    if component not in IDS:
        sys.exit('Componente desconocido')
    if shutil.which('kdialog'):
        if subprocess.run(['kdialog', '--yesno', '¿Desinstalar el lanzador y recuperar los archivos originales?']).returncode:
            sys.exit(0)
    elif input('¿Desinstalar y recuperar originales? [s/N] ').lower() != 's':
        sys.exit(0)
    try:
        backup = uninstall(component)
        refresh()
        message = 'Lanzador desinstalado. Copia recuperable: ' + str(backup)
        code = 0
    except Exception as exc:
        message, code = str(exc), 1
    if shutil.which('kdialog'):
        subprocess.run(['kdialog', '--error' if code else '--msgbox', message])
    print(message)
    sys.exit(code)
