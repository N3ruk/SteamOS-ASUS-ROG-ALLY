"""Selection, local preflight, integrity, and explicit component dispatch."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from . import decky, launchers

CATALOG = {
    'return-gaming': {
        'name': 'Volver al modo Gaming', 'version': '1.0.0',
        'description': 'Sustituye el lanzador y su icono por los personalizados. Pide confirmación antes de cerrar el escritorio. Conserva el original para desinstalar.',
        'requirements': 'SteamOS con KDE, kdialog, steamosctl y qdbus6/qdbus. Sin administrador.'},
    'default-mode': {
        'name': 'Alternar arranque de SteamOS', 'version': '1.0.0',
        'description': 'Instala un lanzador para alternar Escritorio/Gaming como modo predeterminado del próximo arranque. Instalarlo no cambia el modo actual ni el predeterminado.',
        'requirements': 'SteamOS con steamosctl y kdialog. Sin administrador.'},
    'ally-power': {
        'name': 'Ally Power — Escritorio', 'version': '1.0.0',
        'description': 'Control manual de TDP, SMT, núcleos e hilos en escritorio. No necesita PowerTools. Requiere cerrar Ally Power si ya está abierto y autorización del sistema al instalar.',
        'requirements': 'Solo Ally/Ally X RC71L/RC72LA con Ryzen Z1/Z1 Extreme, SteamOS x86_64. Python GTK4 y pkexec.'},
    'ally-power-decky': {
        'name': 'Ally Power — Decky Gaming', 'version': '1.1.0',
        'description': 'Plugin para Gaming: cambios en tiempo real; TDP del plugin solo al activar «TDP de Steam desactivado». SMT independiente. No añade botones Aplicar, Liberar ni Restaurar.',
        'requirements': 'Mismo hardware que Ally Power; Decky instalado y activo, API local compatible y python3-aiohttp. No instala Decky.'},
    'bluetooth-trust-manager': {
        'name': 'Confianza Bluetooth', 'version': '1.0.0',
        'description': 'Lista dispositivos de confianza y permite retirar solo esa confianza, previa confirmación. Especialmente útil con mandos PS3 cuando, tras desvincularlos, no vuelve a aparecer la autorización USB. No borra claves de emparejamiento.',
        'requirements': 'SteamOS KDE, Python GTK4/PyGObject, BlueZ. Sin administrador.'},
}
PAYLOADS = {
    'ally-power': 'Ally-Power-1.0.0-SteamOS-x86_64.run',
    'ally-power-decky': 'Ally-Power-Decky-1.1.0.zip',
    'bluetooth-trust-manager': 'Confianza-Bluetooth-1.0.0-SteamOS.run',
}


def read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ''


def host_errors():
    try:
        os_id = platform.freedesktop_os_release().get('ID')
    except OSError:
        os_id = None
    return [] if os_id == 'steamos' else ['Este instalador está preparado para SteamOS, no para otras distribuciones.']


def ally_errors():
    product = read('/sys/devices/virtual/dmi/id/product_name')
    if platform.machine() != 'x86_64' or not any(x in product for x in ('RC71L', 'RC72LA')) or 'AMD Ryzen Z1' not in read('/proc/cpuinfo'):
        return ['Ally Power requiere ROG Ally/Ally X Z1 o Z1 Extreme (RC71L/RC72LA), SteamOS x86_64.']
    return []


def available(root):
    manifest = json.loads((Path(root) / 'manifest.json').read_text())
    ids = manifest.get('components', [])
    if not ids or any(i not in CATALOG for i in ids):
        raise RuntimeError('Catálogo de componentes inválido.')
    return ids


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest.get('schema') != 1:
        raise RuntimeError('Formato de paquete desconocido.')
    for text, expected in manifest['sha256'].items():
        path = root / text
        if Path(text).is_absolute() or '..' in Path(text).parts or not path.resolve().is_relative_to(root):
            raise RuntimeError('Ruta de manifiesto no segura: ' + text)
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Integridad incorrecta: ' + text)
    available(root)
    return manifest


def requirements(component, root, delegate=True):
    errors = host_errors()
    if component in ('ally-power', 'ally-power-decky'):
        errors += ally_errors()
    if component in launchers.IDS:
        for cmd in ('kdialog', 'steamosctl'):
            if not shutil.which(cmd):
                errors.append('Falta ' + cmd)
        if component == 'return-gaming' and not (shutil.which('qdbus6') or shutil.which('qdbus')):
            errors.append('Falta qdbus6 o qdbus.')
    if component == 'ally-power-decky':
        ok, reason = decky.availability()
        if not ok:
            errors.append(reason)
    if not errors and delegate and component in ('ally-power', 'bluetooth-trust-manager'):
        result = subprocess.run(['/bin/bash', str(Path(root) / 'payloads' / PAYLOADS[component]), '--check'],
                                text=True, capture_output=True, timeout=90)
        if result.returncode:
            errors.append((result.stderr or result.stdout).strip() or 'El comprobador propio del paquete ha fallado.')
    return errors


def install(component, root):
    root = Path(root).resolve()
    manifest = verify(root)
    if component not in available(root):
        raise RuntimeError('Este ZIP no contiene el componente seleccionado.')
    errors = requirements(component, root)
    if errors:
        raise RuntimeError('\n'.join(errors))
    if component in launchers.IDS:
        receipt = launchers.install(component, root / 'components' / component)
        launchers.refresh()
        return 'Instalado para tu usuario. Copia original: ' + str(receipt)
    if component == 'ally-power-decky':
        rel = 'payloads/' + PAYLOADS[component]
        return asyncio.run(decky.install(root / rel, manifest['sha256'][rel], CATALOG[component]['version']))
    result = subprocess.run(['/bin/bash', str(root / 'payloads' / PAYLOADS[component])])
    if result.returncode:
        raise RuntimeError('El instalador propio no terminó correctamente (código %s).' % result.returncode)
    # Original installers treat a declined native dialog as a successful process exit.
    return 'El instalador propio terminó. Si cancelaste su diálogo, no se ha instalado.'
