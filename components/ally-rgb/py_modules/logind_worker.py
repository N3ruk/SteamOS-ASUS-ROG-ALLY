"""Read-only typed logind subscription, isolated from Decky's frozen Python."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'vendor'))
from dbus_next.aio import MessageBus
from dbus_next import BusType, Message, MessageType

DEST = 'org.freedesktop.login1'
OBJECT = '/org/freedesktop/login1'
INTERFACE = 'org.freedesktop.login1.Manager'


def emit(**values):
    print(json.dumps(values), flush=True)


async def observe():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        node = await bus.introspect(DEST, OBJECT)
        proxy = bus.get_proxy_object(DEST, OBJECT, node)
        manager = proxy.get_interface(INTERFACE)
        properties = proxy.get_interface('org.freedesktop.DBus.Properties')
        observed = {'sleeping': None, 'shutdown': None}
        def sleep(value):
            if type(value) is bool:
                observed['sleeping'] = value
                emit(sleeping=value)
        def shutdown(value):
            if type(value) is bool:
                observed['shutdown'] = value
                emit(shutdown=value)
        manager.on_prepare_for_sleep(sleep)
        manager.on_prepare_for_shutdown(shutdown)
        # Synchronize AddMatch requests before reading the initial properties.
        reply = await bus.call(Message(destination='org.freedesktop.DBus', path='/org/freedesktop/DBus',
                                       interface='org.freedesktop.DBus', member='GetId'))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError('No se pudo sincronizar logind.')
        values = await properties.call_get_all(INTERFACE)
        # Never overwrite a newer signal delivered while GetAll was in flight.
        emit(ready=True, sleeping=observed['sleeping'] if observed['sleeping'] is not None else values['PreparingForSleep'].value,
             shutdown=observed['shutdown'] if observed['shutdown'] is not None else values['PreparingForShutdown'].value)
        await bus.wait_for_disconnect()
    finally:
        bus.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(observe())
    except (Exception, KeyboardInterrupt):
        sys.exit(1)
