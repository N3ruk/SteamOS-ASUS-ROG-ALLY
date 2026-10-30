"""Decky entry point; restore at startup only with saved user consent."""
import asyncio
from pathlib import Path
import sys
import decky
sys.path.insert(0, str(Path(__file__).resolve().parent))
from py_modules.rgb import Manager
from py_modules.loader_compat import guard_decky_socket


class Plugin:
    async def _main(self):
        self.manager = Manager(Path(decky.DECKY_PLUGIN_SETTINGS_DIR), logger=decky.logger)
        self.manager.loader_eof_guard = guard_decky_socket()
        decky.logger.info("RGB process-local Decky EOF guard: %s", self.manager.loader_eof_guard)
        await self.manager.start()

    async def frontend_ready(self):
        return await self.manager.frontend_ready()

    async def session_probe(self):
        if self.manager.task or self.manager.pending:
            return {'error':'Espera a que no haya recuperación ni animación.'}
        from py_modules.session_io import retire_abandoned_scopes
        await retire_abandoned_scopes()
        result = await self.manager.io.session_probe()
        await self.manager.io.close(clear=False)
        return result

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
        await self.manager.shutdown()
