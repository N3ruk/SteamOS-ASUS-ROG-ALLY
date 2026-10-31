"""Small, atomic settings adapter; legacy fields are preserved, never applied."""
import json
import os
from pathlib import Path
import tempfile

DEFAULT_CONFIG = {
    'steamDeckInternalConnector': '0:eDP-1',
    'targetUid': 1000,
    'usernameOverride': None,
    'defaultConnector': None,
}


class SettingsStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            data = json.loads(self.path.read_text())
        except FileNotFoundError:
            return {'connectors': {}, 'config': {}}
        # Never silently replace damaged settings with defaults on the next write.
        if not isinstance(data, dict):
            raise ValueError('Plugin settings must be a JSON object')
        for section in ('connectors', 'config'):
            if not isinstance(data.setdefault(section, {}), dict):
                raise ValueError(f'Invalid settings section: {section}')
        return data

    def config(self):
        config = {**DEFAULT_CONFIG, **self.load()['config']}
        # Read-only compatibility with pre-multi-GPU settings.
        for key in ('defaultConnector', 'steamDeckInternalConnector'):
            value = config.get(key)
            if isinstance(value, str) and ':' not in value:
                config[key] = DEFAULT_CONFIG[key]
        return config

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.settings-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write('\n')
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
