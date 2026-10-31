"""Decky API v1 entry point. Loading this plugin never applies a power setting."""
from pathlib import Path
import os
import stat
import sys
import decky

# Decky imports main.py by filename, not as a Python package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from py_modules.manager import Manager
from py_modules.loader_compat import guard_decky_socket


class Plugin:
    def __init__(self):
        self.manager = Manager(Path(decky.DECKY_PLUGIN_SETTINGS_DIR))

    async def get_state(self):
        return await self.manager.get_state()

    async def frontend_ready(self, context):
        return await self.manager.frontend_ready(context)

    async def set_recovery(self, enabled):
        return await self.manager.set_recovery(enabled)

    async def recover_pending(self, identity, lease, context):
        return await self.manager.recover_pending(identity, lease, context)

    async def recover_cpu(self, identity, lease, context):
        return await self.manager.recover_cpu(identity, lease, context)

    async def session_probe(self):
        return await self.manager.session_probe()

    async def sleep_guard_probe(self):
        return await self.manager.sleep_guard_probe()

    async def _migration(self):
        # Decky's ZIP extractor may omit Unix execute bits. Only adjust our
        # root-owned, regular bundled binary, never a caller-provided path.
        binary = Path(__file__).resolve().parent / 'bin/ryzenadj'
        metadata = binary.lstat()
        if (os.geteuid() != 0 or metadata.st_uid != 0 or binary.is_symlink()
                or not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o022):
            raise RuntimeError('Instalación insegura: el plugin debe pertenecer a root.')
        binary.chmod(0o755)

    async def set_cpu(self, config, lease=None):
        return await self.manager.apply_cpu(config, lease)

    async def set_tdp_mode(self, enabled, lease=None):
        return await self.manager.set_tdp_mode(enabled, lease)

    async def set_tdp(self, watts, lease=None):
        return await self.manager.apply_tdp(watts, lease)

    async def _main(self):
        self.manager.loader_eof_guard = guard_decky_socket()
        print('POWER architecture=session-lease-v2-recovery; EOF guard=' + str(self.manager.loader_eof_guard), flush=True)
        await self.manager.monitor()

    async def _unload(self):
        await self.manager.close()
