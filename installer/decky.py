"""Decky 3.3 local API adapter. Tokens stay in memory; no service restarts."""
import asyncio
import hashlib
import importlib.util
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
import subprocess
import time


def availability():
    try:
        active = subprocess.run(['systemctl', 'is-active', '--quiet', 'plugin_loader.service'],
                                capture_output=True, timeout=5).returncode == 0
        unit = subprocess.run(['systemctl', 'show', 'plugin_loader.service', '-p', 'ExecStart', '--value'],
                              capture_output=True, text=True, timeout=5)
        # A loaded unit with a configured running executable is evidence of installation.
        installed = unit.returncode == 0 and bool(unit.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False, 'Decky Loader no está instalado y activo (plugin_loader.service).'
    if not installed or not active:
        return False, 'Decky Loader debe estar instalado y activo; no se instala ni activa automáticamente.'
    if importlib.util.find_spec('aiohttp') is None:
        return False, 'Se necesita python3-aiohttp para usar la API local de Decky; no se descarga automáticamente.'
    return True, 'Decky Loader instalado y activo. API local compatible comprobada con Decky 3.3.0.'


def backup_previous(version, folder_name='ally-power-decky', plugin_name='Ally Power',
                    author='Ally Power', backup_name='Ally-Power-Decky'):
    # An update must not discard an existing plugin without a recoverable copy.
    folder = Path(os.environ.get('DECKY_PLUGIN_DIR', str(Path.home() / 'homebrew/plugins'))) / folder_name
    if not folder.is_dir() or folder.is_symlink():
        raise RuntimeError('No se localiza la instalación para guardar una copia. Configura DECKY_PLUGIN_DIR si Decky usa una ruta no estándar.')
    meta = json.loads((folder / 'plugin.json').read_text())
    package = json.loads((folder / 'package.json').read_text())
    if meta.get('name') != plugin_name or meta.get('author') != author or package.get('version') != version:
        raise RuntimeError('El plugin local no coincide con la versión registrada; no se sustituye.')
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    if not state.is_absolute():
        raise RuntimeError('XDG_STATE_HOME debe ser absoluto.')
    out = state / 'steamos-ally-suite' / folder_name
    from .launchers import guard
    target = out / (backup_name + '-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.zip')
    guard(target)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('La instalación contiene enlaces; no se actualiza automáticamente.')
        if path.is_file() and '__pycache__' not in path.parts:
            paths.append(path)
    try:
        with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(paths):
                archive.write(path, folder.name + '/' + path.relative_to(folder).as_posix())
    except Exception:
        if target.exists():
            target.unlink()  # Incomplete newly-created backup, never a user file.
        raise
    return target


class Client:
    def __init__(self, ws, aiohttp):
        self.ws, self.aiohttp = ws, aiohttp
        self.counter = int(time.time() * 1000)
        self.events = []

    async def receive(self):
        msg = await asyncio.wait_for(self.ws.receive(), 45)
        if msg.type != self.aiohttp.WSMsgType.TEXT:
            raise RuntimeError('Decky cerró la conexión local; no se reinicia el servicio automáticamente.')
        data = json.loads(msg.data)
        if data.get('type') == 5:
            self.events.append(data)
        return data

    async def call(self, route, *args):
        self.counter += 1
        ident = self.counter
        await self.ws.send_json({'type': 0, 'id': ident, 'route': route, 'args': list(args)})
        while True:
            data = await self.receive()
            if data.get('id') == ident and data.get('type') in (1, -1):
                await self.ws.send_json({'type': 3, 'id': ident})
                if data.get('type') == -1:
                    raise RuntimeError('La API de Decky rechazó la operación: ' + str(data.get('error')))
                return data.get('result')

    async def prompt(self):
        async def wait():
            while True:
                prompts = [e for e in self.events if e.get('event') == 'loader/add_plugin_install_prompt'
                           and len(e.get('args', [])) >= 5 and e['args'][0] == 'Ally Power']
                if len(prompts) == 1:
                    return prompts[0]['args']
                if len(prompts) > 1:
                    raise RuntimeError('Varias solicitudes Decky inesperadas; no se confirma ninguna.')
                await self.receive()
        return await asyncio.wait_for(wait(), 45)

    async def install(self, payload, digest, version):
        plugins = await self.call('loader/get_plugins')
        previous = next((p for p in plugins if p.get('name') == 'Ally Power'), None)
        if previous:
            state = await self.call('loader/call_plugin_method', 'Ally Power', 'get_state')
            if not isinstance(state, dict) or state.get('version') not in ('1.0.0', '1.0.1', '1.1.0', '1.1.1', '1.1.2'):
                raise RuntimeError('Ally Power existente no reconocido; no se sustituye.')
            if state.get('active'):
                raise RuntimeError('El plugin controla el hardware. Sal de Gaming antes de actualizarlo.')
        backup = backup_previous(previous.get('version')) if previous else None
        install_type = 2 if previous else 0
        await self.call('utilities/install_plugin', Path(payload).resolve().as_uri(),
                        'Ally Power', version, digest, install_type)
        prompt = await self.prompt()
        if prompt[1] != version or prompt[3] != digest or prompt[4] != install_type:
            raise RuntimeError('La confirmación Decky no coincide con el paquete solicitado.')
        await self.call('utilities/confirm_plugin_install', prompt[2])
        plugins = await self.call('loader/get_plugins')
        if not any(p.get('name') == 'Ally Power' and p.get('version') == version for p in plugins):
            raise RuntimeError('Decky no ha registrado la versión esperada. Consulta el panel de plugins.')
        state = await self.call('loader/call_plugin_method', 'Ally Power', 'get_state')
        if not isinstance(state, dict) or state.get('version') != version:
            raise RuntimeError('Decky registra el plugin pero su backend no responde con la versión esperada.')
        return ('Ally Power ' + version + ' registrado y backend comprobado. No se han aplicado ajustes de potencia.'
                + (' Copia anterior: ' + str(backup) if backup else ''))


async def install(payload, expected, version):
    available, reason = availability()
    if not available:
        raise RuntimeError(reason)
    if hashlib.sha256(Path(payload).read_bytes()).hexdigest() != expected:
        raise RuntimeError('El ZIP Decky no supera su comprobación SHA256.')
    import aiohttp
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
        async with session.get('http://127.0.0.1:1337/auth/token') as response:
            response.raise_for_status()
            token = (await response.text()).strip()
        if not token:
            raise RuntimeError('Decky no ha autorizado la conexión local.')
        async with session.ws_connect('http://127.0.0.1:1337/ws', params={'auth': token}) as ws:
            return await asyncio.wait_for(Client(ws, aiohttp).install(payload, expected, version), 150)
