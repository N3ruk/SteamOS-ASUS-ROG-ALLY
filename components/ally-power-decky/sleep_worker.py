"""Root metadata-only logind guardian. No CPU/TDP/HID imports or writes here."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from py_modules.sleep_logind import LogindLease


def emit(event, **values):
    print(json.dumps({'event': event, **values}), flush=True)


async def serve():
    released = asyncio.Event()
    def preparing():
        released.clear()
        emit('sleep', value=True)
        return released.wait()
    class Lease(LogindLease):
        def release(self):
            held = self.fd is not None
            super().release()
            if held: emit('released')
    lease = Lease(preparing, lambda: emit('sleep', value=False))
    emit('ready')
    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline, 1025)
            if not line or len(line) > 1024: break
            try:
                request = json.loads(line)
                if request['action'] == 'arm':
                    await lease.arm()
                    emit('armed')
                elif request['action'] == 'watch':
                    await lease.watch()
                    emit('watching')
                elif request['action'] in ('release', 'close'):
                    released.set()
                    lease.release()
                    if request['action'] == 'close': break
                else:
                    raise ValueError('Operación logind no válida.')
            except Exception as exc:
                emit('error', message=str(exc))
    finally:
        released.set()
        await lease.close()


if __name__ == '__main__':
    try: asyncio.run(serve())
    except Exception as exc:
        emit('error', message=str(exc))
