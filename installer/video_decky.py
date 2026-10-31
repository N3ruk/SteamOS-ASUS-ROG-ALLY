"""Video plugin distribution through Decky; never selects a monitor to test it."""
import asyncio
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile
from . import decky
from .rgb_decky import ConnectionLost, Client as ReconnectingClient

NAME = 'Video Output ALLY for DOCKs'
FOLDER = 'output-manager'  # Keep existing settings/startup-helper compatibility.
KNOWN = ('1.0', '1.4.0')


def plugin_folder():
    return Path(os.environ.get('DECKY_PLUGIN_DIR', str(Path.home() / 'homebrew/plugins'))) / FOLDER


def check_payload(payload, expected, version):
    if hashlib.sha256(Path(payload).read_bytes()).hexdigest() != expected:
        raise RuntimeError('El ZIP de vídeo no supera su SHA256.')
    with zipfile.ZipFile(payload) as archive:
        names = archive.namelist()
        if (len(set(names)) != len(names) or any(
            not n.startswith(FOLDER+'/') or '..' in Path(n).parts or '\\' in n
            for n in names) or any(stat.S_ISLNK(i.external_attr >> 16) for i in archive.infolist())):
            raise RuntimeError('Estructura de ZIP de vídeo no válida.')
        meta = json.loads(archive.read(FOLDER+'/plugin.json'))
        package = json.loads(archive.read(FOLDER+'/package.json'))
        manifest = json.loads(archive.read(FOLDER+'/manifest.json'))
        if meta.get('name') != NAME or meta.get('author') != 'N3ruk' or package.get('version') != version or manifest.get('version') != version or manifest.get('schema') != 1:
            raise RuntimeError('La identidad o versión del plugin de vídeo no coincide.')
        checks = manifest['sha256']
        if set(names) != {FOLDER+'/'+n for n in checks} | {FOLDER+'/manifest.json'}:
            raise RuntimeError('El manifiesto de vídeo no cubre todos los archivos.')
        for name, digest in checks.items():
            if hashlib.sha256(archive.read(FOLDER+'/'+name)).hexdigest() != digest:
                raise RuntimeError('Archivo de vídeo alterado: '+name)


class Client(ReconnectingClient):
    async def prompt(self):
        async def wait():
            while True:
                matches = [e['args'] for e in self.events if e.get('event') == 'loader/add_plugin_install_prompt'
                           and len(e.get('args', [])) >= 5 and e['args'][0] == NAME]
                if len(matches) == 1:
                    return matches[0]
                if len(matches) > 1:
                    raise RuntimeError('Varias solicitudes de vídeo; ninguna confirmada.')
                await self.receive()
        return await asyncio.wait_for(wait(), 45)

    async def prepare(self, payload, digest, version):
        if any(p.is_symlink() for p in (plugin_folder(), *plugin_folder().parents)):
            raise RuntimeError('La ruta del plugin contiene enlaces; no se actualiza.')
        plugins = await self.call('loader/get_plugins')
        if any(p.get('name') == 'Output Manager' for p in plugins):
            raise RuntimeError('Retira primero Output Manager desde Decky, conservando sus ajustes. No se ejecutan dos controladores ni se renombra durante una instalación pendiente.')
        previous = next((p for p in plugins if p.get('name') == NAME), None)
        backup = None
        if previous:
            if previous.get('disabled') or previous.get('version') not in KNOWN:
                raise RuntimeError('Plugin de vídeo desactivado o versión no reconocida; usa la gestión de Decky.')
            state = await self.call('loader/call_plugin_method', NAME, 'get_state')
            video = state.get('video') if isinstance(state, dict) else None
            if not isinstance(video, dict) or video.get('architecture') != 'edid-mst-nudge-v1':
                raise RuntimeError('Backend de vídeo no reconocido; no se sustituye.')
            if video.get('gaming') or video.get('owned') or video.get('busy'):
                raise RuntimeError('El plugin está en Gaming o controla salidas. Vuelve al escritorio y espera a que libere las pantallas antes de actualizar.')
            backup = decky.backup_previous(previous['version'], folder_name=FOLDER, plugin_name=NAME,
                                           author='N3ruk', backup_name='Video-Output-ALLY-for-DOCKs')
        elif plugin_folder().exists() or plugin_folder().is_symlink():
            raise RuntimeError('La carpeta output-manager ya existe sin un plugin reconocido; no se sobrescribe.')
        install_type = 2 if previous else 0
        await self.call('utilities/install_plugin', Path(payload).resolve().as_uri(), NAME, version, digest, install_type)
        prompt = await self.prompt()
        if prompt[0] != NAME or prompt[1] != version or prompt[3] != digest or prompt[4] != install_type or not isinstance(prompt[2], str) or not prompt[2]:
            raise RuntimeError('La confirmación Decky no coincide con el plugin de vídeo.')
        return prompt[2], backup


def installed_matches(payload):
    folder = plugin_folder()
    if folder.is_symlink() or not folder.is_dir():
        return False
    try:
        with zipfile.ZipFile(payload) as archive:
            for name in archive.namelist():
                path = folder / Path(name).relative_to(FOLDER)
                if (not path.is_file() or path.is_symlink() or
                    any(p.is_symlink() for p in path.parents) or
                    path.read_bytes() != archive.read(name)):
                    return False
    except OSError:
        return False
    return True


async def inspect_ready(session, token, version, payload, attempts=45, interval=1):
    import aiohttp
    for attempt in range(attempts):
        try:
            async with session.ws_connect('http://127.0.0.1:1337/ws', params={'auth': token}) as ws:
                client = Client(ws, aiohttp)
                plugins = await client.call('loader/get_plugins')
                if any(p.get('name') == NAME and p.get('version') == version and not p.get('disabled') for p in plugins):
                    state = await client.call('loader/call_plugin_method', NAME, 'get_state')
                    if isinstance(state, dict) and state.get('version') == version and state.get('video', {}).get('architecture') == 'edid-mst-nudge-v1' and installed_matches(payload):
                        return state
        except (ConnectionLost, aiohttp.ClientError, RuntimeError, asyncio.TimeoutError):
            pass
        if attempt+1 < attempts:
            await asyncio.sleep(interval)
    raise RuntimeError('No se pudo verificar el plugin de vídeo. Revisa Decky antes de repetir; no se ha reenviado la confirmación.')


async def _install(payload, expected, version):
    ok, reason = decky.availability()
    if not ok:
        raise RuntimeError(reason)
    check_payload(payload, expected, version)
    import aiohttp
    request_id = backup = None
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
            async with session.get('http://127.0.0.1:1337/auth/token') as response:
                response.raise_for_status()
                token = (await response.text()).strip()
            if not token:
                raise RuntimeError('Decky no ha autorizado la conexión local.')
            try:
                async with session.ws_connect('http://127.0.0.1:1337/ws', params={'auth': token}) as ws:
                    client = Client(ws, aiohttp)
                    request_id, backup = await client.prepare(payload, expected, version)
                    try:
                        await client.call('utilities/confirm_plugin_install', request_id)
                    except (ConnectionLost, aiohttp.ClientError, asyncio.TimeoutError):
                        pass  # Inspect read-only; never confirm twice.
            except (ConnectionLost, aiohttp.ClientError, asyncio.TimeoutError):
                if request_id is None:
                    raise RuntimeError('No se pudo preparar Decky; ninguna solicitud confirmada.') from None
            await inspect_ready(session, token, version, payload)
    except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionLost):
        raise RuntimeError('Falló la conexión local de Decky; no se muestran datos de autenticación. Revisa su estado antes de repetir.') from None
    return (NAME+' '+version+' registrado y backend comprobado. No se ha enviado ninguna orden de selección de pantalla.'
            + (' Copia anterior: '+str(backup) if backup else ''))


@contextmanager
def installation_lock():
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))
    if not state.is_absolute():
        raise RuntimeError('XDG_STATE_HOME debe ser absoluto.')
    path = state/'steamos-ally-suite'/FOLDER/'install.lock'
    from .launchers import guard
    guard(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Ya hay una instalación de vídeo en curso.') from None
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


async def install(payload, expected, version):
    with installation_lock():
        return await _install(payload, expected, version)
