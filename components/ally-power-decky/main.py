"""Decky API v1 entry point. Loading this plugin never applies a power setting."""
from pathlib import Path
import os
import stat
import sys

# Decky imports main.py by filename, not as a Python package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from py_modules.manager import Manager


class Plugin:
    def __init__(self):
        self.manager = Manager()

    async def get_state(self):
        return await self.manager.get_state()

    async def _migration(self):
        # Decky's ZIP extractor may omit Unix execute bits. Only adjust our
        # root-owned, regular bundled binary, never a caller-provided path.
        binary = Path(__file__).resolve().parent / 'bin/ryzenadj'
        metadata = binary.lstat()
        if (os.geteuid() != 0 or metadata.st_uid != 0 or binary.is_symlink()
                or not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o022):
            raise RuntimeError('Instalación insegura: el plugin debe pertenecer a root.')
        binary.chmod(0o755)

    async def set_cpu(self, config):
        return await self.manager.apply_cpu(config)

    async def set_tdp_mode(self, enabled):
        return await self.manager.set_tdp_mode(enabled)

    async def set_tdp(self, watts):
        return await self.manager.apply_tdp(watts)

    async def _main(self):
        await self.manager.monitor()

    async def _unload(self):
        await self.manager.close()
