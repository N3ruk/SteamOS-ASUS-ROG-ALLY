"""Decky entry point; restore at startup only with saved user consent."""
import asyncio
from pathlib import Path
import sys
import decky
sys.path.insert(0, str(Path(__file__).resolve().parent))
from py_modules.rgb import Manager


class Plugin:
    async def _main(self):
        self.manager = Manager(Path(decky.DECKY_PLUGIN_SETTINGS_DIR))
        self.manager.startup_task = asyncio.create_task(self.manager.restore_startup())

    async def get_state(self):
        return await self.manager.state()

    async def apply_config(self, config):
        return await self.manager.apply(config)

    async def select_zone(self, zone):
        return await self.manager.select_zone(zone)

    async def release_control(self):
        return await self.manager.release()

    async def pause(self):
        return await self.manager.pause()

    async def resume(self):
        return await self.manager.resume()

    async def _unload(self):
        await self.manager.release()
