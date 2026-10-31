"""logind delay lease, armed BEFORE reducing CPU; no installed service or hook.

Unlike RGB, CPU hotplug needs a pre-sleep operation: Ally can fail suspension
with SMT disabled. Never use this channel to write TDP or recover old profiles.
"""
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'vendor'))
from dbus_next.aio import MessageBus
from dbus_next import BusType

DEST = 'org.freedesktop.login1'
OBJECT = '/org/freedesktop/login1'
INTERFACE = 'org.freedesktop.login1.Manager'


class LogindLease:
    def __init__(self, on_prepare, on_resume):
        self.on_prepare, self.on_resume = on_prepare, on_resume
        self.bus = None
        self.manager = None
        self.fd = None
        self.task = None
        self.preparing = False

    def signal(self, sleeping):
        if type(sleeping) is not bool:
            return
        self.preparing = sleeping
        if sleeping:
            if self.task is None or self.task.done():
                # on_prepare invalidates the UI lease synchronously, before
                # yielding for either the operation lock or an IPC response.
                work = self.on_prepare()
                self.task = asyncio.create_task(self.prepare(work))
        else:
            self.on_resume()

    async def prepare(self, work):
        try:
            await asyncio.wait_for(work, 2.5)
        except Exception as exc:
            print('POWER pre-sleep FAILED (no retry/restore): ' + str(exc), file=sys.stderr, flush=True)
        finally:
            self.release()

    async def watch(self):
        if self.bus is None:
            self.bus = await asyncio.wait_for(MessageBus(
                bus_type=BusType.SYSTEM, negotiate_unix_fd=True).connect(), 2)
            node = await asyncio.wait_for(self.bus.introspect(DEST, OBJECT), 2)
            proxy = self.bus.get_proxy_object(DEST, OBJECT, node)
            self.manager = proxy.get_interface(INTERFACE)
            self.manager.on_prepare_for_sleep(self.signal)
        if self.preparing or not self.bus.connected:
            raise RuntimeError('logind no está disponible para observar la suspensión.')
        if (await asyncio.wait_for(self.manager.get_preparing_for_sleep(), 1)
                or await asyncio.wait_for(self.manager.get_preparing_for_shutdown(), 1)):
            raise RuntimeError('SteamOS está preparando suspensión/apagado.')

    async def arm(self):
        try:
            await self.watch()
            if self.preparing or not self.bus.connected:
                raise RuntimeError('logind no está disponible para proteger la CPU.')
            maximum = await asyncio.wait_for(self.manager.get_inhibit_delay_max_u_sec(), 1)
            if type(maximum) is not int or maximum < 3_000_000:
                raise RuntimeError('El margen logind para preparar la CPU es insuficiente (mínimo 3 s).')
            if self.fd is None:
                self.fd = await asyncio.wait_for(self.manager.call_inhibit(
                    'sleep', 'Ally Power CPU', 'Activar CPU/SMT antes de suspender la Ally', 'delay'), 2)
            # A signal can arrive while Inhibit/GetProperties are in flight.
            sleeping = await asyncio.wait_for(self.manager.get_preparing_for_sleep(), 1)
            shutdown = await asyncio.wait_for(self.manager.get_preparing_for_shutdown(), 1)
            if self.preparing or sleeping or shutdown:
                raise RuntimeError('La CPU no se reduce durante suspensión/apagado.')
        except BaseException:
            self.release()
            raise

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    async def close(self):
        if self.task and not self.task.done():
            await asyncio.wait([self.task], timeout=2.6)
        self.release()
        if self.bus:
            self.bus.disconnect()
            self.bus = self.manager = None
