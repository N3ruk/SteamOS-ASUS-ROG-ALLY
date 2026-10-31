"""Decky adapter for Video Output ALLY for DOCKs. Video engine is separate."""
from pathlib import Path
import sys

import decky_plugin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_names import DisplayNames
from settings_store import DEFAULT_CONFIG, SettingsStore
from video_runtime import VideoRuntime
from video_selector import ARCH, parts

store = SettingsStore(Path(decky_plugin.DECKY_PLUGIN_SETTINGS_DIR) / 'settings.json')
names = DisplayNames()
VERSION = '1.0'
video = None


class Plugin:
    async def _main(self):
        global video
        video = VideoRuntime(store.config, decky_plugin.logger)
        await video.start()
        decky_plugin.logger.info('Video Output ALLY for DOCKs loaded: %s', ARCH)

    async def _unload(self):
        if video:
            await video.close()

    async def video_probe(self):
        """Read-only diagnostic; never selects an output."""
        return await video.probe()

    async def get_config(self):
        """Compatibility/maintenance API, not a settings page."""
        config = store.config()
        if video and config.get('defaultDisplayIdentity'):
            config['defaultConnector'] = video.default_hint()
        return config

    async def set_config(self, patch: dict):
        """Preserve the existing video preference API and unrelated saved fields."""
        if not isinstance(patch, dict):
            return {'ok': False, 'error': 'Invalid configuration'}
        settings = store.load()
        config = settings['config']
        for key in ('steamDeckInternalConnector', 'usernameOverride'):
            if key in patch:
                value = str(patch[key] or '').strip()
                config[key] = value or DEFAULT_CONFIG[key]
        if 'targetUid' in patch:
            try:
                config['targetUid'] = int(patch['targetUid'])
            except (ValueError, TypeError):
                return {'ok': False, 'error': 'Target UID must be a number'}
        preference_changed = 'defaultConnector' in patch
        if preference_changed:
            key = patch['defaultConnector']
            node = video.nodes.get(key) if video and isinstance(key, str) else None
            if key and (not node or not node.get('identity') or not node.get('connected')):
                return {'ok': False, 'error': 'Select a connected monitor with a verified EDID'}
            config['defaultConnector'] = key or None  # Hint only; EDID remains authoritative.
            config['defaultDisplayIdentity'] = node['identity'] if key else None
        store.save(settings)
        if preference_changed and video:
            video.cancel()
            video.manual_hold = False
            video.attempt = None
        return {'ok': True}

    async def get_state(self):
        """Use the controller's cached metadata; no subprocess or hardware request."""
        settings = store.load()
        nodes = video.nodes if video else {}
        connectors = names.connectors(nodes, settings['connectors'])
        enabled = [n['id'] for n in connectors if n['enabled']]
        return {'version': VERSION, 'connectors': connectors, 'currentConnector': enabled[0] if enabled else None,
                'video': video.diagnostics() if video else None}

    async def switch_connector(self, connector_string: str):
        try:
            connector = parts(connector_string)
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'Invalid display connector'}
        if not video:
            return {'ok': False, 'error': 'Video controller is not ready'}
        return await video.select(connector, manual=True)
