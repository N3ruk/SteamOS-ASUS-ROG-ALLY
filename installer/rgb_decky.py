"""ALLY RGB installation through Decky; never applies colors or stops other managers."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import zipfile
from . import decky

NAME = 'ALLY RGB'
KNOWN = ('1.0.0', '1.1.0', '1.2.0')


class ConnectionLost(RuntimeError):
    pass


def check_payload(payload, expected, version):
    payload = Path(payload)
    if hashlib.sha256(payload.read_bytes()).hexdigest() != expected:
        raise RuntimeError('El ZIP de ALLY RGB no supera su SHA256.')
    with zipfile.ZipFile(payload) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or any(not n.startswith('ally-rgb/') or '..' in Path(n).parts for n in names):
            raise RuntimeError('Estructura de ZIP ALLY RGB no válida.')
        meta = json.loads(archive.read('ally-rgb/plugin.json'))
        package = json.loads(archive.read('ally-rgb/package.json'))
        if meta.get('name') != NAME or meta.get('author') != 'SteamOS Ally contributors' or package.get('version') != version:
            raise RuntimeError('La identidad o versión de ALLY RGB no coincide con el catálogo.')
        manifest = json.loads(archive.read('ally-rgb/manifest.json'))
        if manifest.get('version') != version:
            raise RuntimeError('Manifiesto ALLY RGB de otra versión.')
        checks = manifest['sha256']
        if set(names) != {'ally-rgb/' + n for n in checks} | {'ally-rgb/manifest.json'}:
            raise RuntimeError('El manifiesto ALLY RGB no cubre todos sus archivos.')
        for name, digest in checks.items():
            if hashlib.sha256(archive.read('ally-rgb/' + name)).hexdigest() != digest:
                raise RuntimeError('Archivo ALLY RGB alterado: ' + name)


class Client(decky.Client):
    async def receive(self):
        msg = await asyncio.wait_for(self.ws.receive(), 45)
        if msg.type != self.aiohttp.WSMsgType.TEXT:
            raise ConnectionLost('Decky ha reconectado su frontend.')
        data = json.loads(msg.data)
        if data.get('type') == 5:
            self.events.append(data)
        if data.get('type') == 2:
            raise ConnectionLost('El backend está reiniciándose.')
        return data

    async def prompt(self):
        async def wait():
            while True:
                matches = [e['args'] for e in self.events if e.get('event') == 'loader/add_plugin_install_prompt'
                           and len(e.get('args', [])) >= 5 and e['args'][0] == NAME]
                if len(matches) == 1:
                    return matches[0]
                if len(matches) > 1:
                    raise RuntimeError('Varias solicitudes ALLY RGB inesperadas; ninguna confirmada.')
                await self.receive()
        return await asyncio.wait_for(wait(), 45)

    async def prepare(self, payload, digest, version):
        plugins = await self.call('loader/get_plugins')
        previous = next((p for p in plugins if p.get('name') == NAME), None)
        backup = None
        if previous:
            if previous.get('disabled'):
                raise RuntimeError('ALLY RGB está desactivado. No se sustituye sin poder comprobar su estado; usa Decky para gestionarlo.')
            state = await self.call('loader/call_plugin_method', NAME, 'get_state')
            if (not isinstance(state, dict) or state.get('version') not in KNOWN
                    or state.get('version') != previous.get('version')):
                raise RuntimeError('ALLY RGB existente no reconocido; no se sustituye.')
            if state.get('active') or state.get('paused'):
                raise RuntimeError('ALLY RGB controla el hardware o tiene una recuperación pendiente. Desactívalo desde Decky y utiliza su instalador manual para sustituirlo; la suite no lo detiene.')
            backup = decky.backup_previous(previous['version'], folder_name='ally-rgb', plugin_name=NAME,
                                           author='SteamOS Ally contributors', backup_name='ALLY-RGB')
        install_type = 2 if previous else 0
        await self.call('utilities/install_plugin', Path(payload).resolve().as_uri(), NAME, version, digest, install_type)
        prompt = await self.prompt()
        if prompt[0] != NAME or prompt[1] != version or prompt[3] != digest or prompt[4] != install_type or not isinstance(prompt[2], str) or not prompt[2]:
            raise RuntimeError('La confirmación Decky no coincide con ALLY RGB; ninguna solicitud confirmada.')
        return prompt[2], backup


def installed_matches(payload):
    """Version alone cannot distinguish a silent replacement using the same name."""
    folder = Path(os.environ.get('DECKY_PLUGIN_DIR', str(Path.home() / 'homebrew/plugins'))) / 'ally-rgb'
    if not folder.is_dir() or folder.is_symlink():
        return False
    try:
        with zipfile.ZipFile(payload) as archive:
            for name in archive.namelist():
                relative = Path(name).relative_to('ally-rgb')
                target = folder / relative
                if target.is_symlink() or not target.is_file() or target.read_bytes() != archive.read(name):
                    return False
    except OSError:
        return False
    return True


async def inspect_ready(session, token, version, payload, attempts=45, interval=1):
    """Reconnect/read only. Never replay a confirmation after an uncertain response."""
    import aiohttp
    last_error = ''
    for attempt in range(attempts):
        try:
            async with session.ws_connect('http://127.0.0.1:1337/ws', params={'auth': token}) as ws:
                client = Client(ws, aiohttp)
                plugins = await client.call('loader/get_plugins')
                if any(p.get('name') == NAME and p.get('version') == version and not p.get('disabled') for p in plugins):
                    state = await client.call('loader/call_plugin_method', NAME, 'get_state')
                    if isinstance(state, dict) and state.get('version') == version and installed_matches(payload):
                        return state
        except (ConnectionLost, aiohttp.ClientError, RuntimeError, asyncio.TimeoutError) as exc:
            last_error = type(exc).__name__
        if attempt + 1 < attempts:
            await asyncio.sleep(interval)
    raise RuntimeError('No se pudo verificar el backend ALLY RGB después de la solicitud. Revisa Decky antes de repetir; no se ha reenviado la confirmación. ' + last_error)


async def install(payload, expected, version):
    ok, reason = decky.availability()
    if not ok:
        raise RuntimeError(reason)
    check_payload(payload, expected, version)
    import aiohttp
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
        async with session.get('http://127.0.0.1:1337/auth/token') as response:
            response.raise_for_status()
            token = (await response.text()).strip()
        if not token:
            raise RuntimeError('Decky no ha autorizado la conexión local.')
        request_id = None
        backup = None
        try:
            async with session.ws_connect('http://127.0.0.1:1337/ws', params={'auth': token}) as ws:
                client = Client(ws, aiohttp)
                request_id, backup = await client.prepare(payload, expected, version)
                try:
                    await client.call('utilities/confirm_plugin_install', request_id)
                except (ConnectionLost, aiohttp.ClientError, asyncio.TimeoutError):
                    pass  # It may already be installing; verify without replaying it.
        except (ConnectionLost, aiohttp.ClientError, asyncio.TimeoutError):
            if request_id is None:
                # aiohttp errors can include the authenticated URL. Never render it.
                raise RuntimeError('No se pudo preparar la conexión local de Decky; ninguna solicitud confirmada.') from None
        state = await inspect_ready(session, token, version, payload)
    note = 'ALLY RGB ' + version + ' registrado y backend comprobado. No se han enviado órdenes de iluminación.'
    if isinstance(state.get('config'), dict) and state['config'].get('resume'):
        note += ' El plugin conserva su recuperación automática previamente configurada.'
    if state.get('error') or state.get('warning'):
        note += ' Aviso del plugin: ' + str(state.get('error') or state.get('warning'))
    if backup:
        note += ' Copia anterior: ' + str(backup)
    return note
