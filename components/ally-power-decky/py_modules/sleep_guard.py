"""Metadata-only logind IPC; Decky's embedded Python need not import D-Bus/XML."""
import asyncio
import json
from pathlib import Path


class SleepGuard:
    def __init__(self, on_prepare, on_resume):
        self.on_prepare, self.on_resume = on_prepare, on_resume
        self.proc = self.reader = self.pending = self.task = None
        self.fd = None  # Boolean acknowledgement; actual FD stays in system Python.
        self.preparing = False
        self.guard = asyncio.Lock()

    def signal(self, value):
        if type(value) is not bool:
            return
        self.preparing = value
        if value:
            if self.task is None or self.task.done():
                work = self.on_prepare()
                self.task = asyncio.create_task(self.prepare(work))
        else:
            self.on_resume()

    async def prepare(self, work):
        try:
            await asyncio.wait_for(work, 2.2)
        except Exception as exc:
            print('POWER pre-sleep FAILED (no retry/restore): ' + str(exc), flush=True)
        finally:
            self.release()

    def send(self, action):
        if not self.proc or self.proc.returncode is not None:
            raise RuntimeError('El guardián logind no está activo.')
        self.proc.stdin.write((json.dumps({'action': action}) + '\n').encode())

    async def read(self):
        try:
            while True:
                line = await self.proc.stdout.readline()
                if not line: break
                event = json.loads(line)
                kind = event.get('event')
                if kind == 'sleep': self.signal(event['value'])
                elif kind == 'armed': self.fd = True
                elif kind == 'released': self.fd = None
                waiter = self.pending
                if waiter and not waiter[1].done() and kind in (waiter[0], 'error'):
                    if kind == 'error': waiter[1].set_exception(RuntimeError(event['message']))
                    else: waiter[1].set_result(event)
        except (OSError, ValueError) as exc:
            print('POWER logind guardian: ' + str(exc), flush=True)
        finally:
            self.fd = None
            if self.pending and not self.pending[1].done():
                self.pending[1].set_exception(RuntimeError('El guardián logind se ha detenido.'))

    async def watch(self):
        await self.arm(action='watch', expected='watching')

    async def arm(self, action='arm', expected='armed'):
        async with self.guard:
            if not self.proc or self.proc.returncode is not None:
                ready = asyncio.get_running_loop().create_future()
                self.pending = ('ready', ready)
                self.proc = await asyncio.create_subprocess_exec(
                    '/usr/bin/python3', '-I', str(Path(__file__).resolve().parent.parent / 'sleep_worker.py'),
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C.UTF-8'})
                self.reader = asyncio.create_task(self.read())
                try: await asyncio.wait_for(ready, 3)
                finally: self.pending = None
            armed = asyncio.get_running_loop().create_future()
            self.pending = (expected, armed)
            try:
                self.send(action)
                await asyncio.wait_for(armed, 7)
                if self.preparing or (action == 'arm' and self.fd is None):
                    raise RuntimeError('Suspensión iniciada durante la protección CPU.')
            except BaseException:
                self.fd = None
                try: self.send('release')
                except (OSError, RuntimeError): pass
                raise
            finally:
                self.pending = None

    def release(self):
        # Also acknowledge watch-only PrepareForSleep events (no inhibitor FD).
        # Otherwise the native observer's old wait could survive into a new cycle.
        self.fd = None
        if self.proc and self.proc.returncode is None:
            try: self.send('release')
            except (OSError, RuntimeError): pass

    async def close(self):
        if self.task and not self.task.done():
            await asyncio.wait([self.task], timeout=2.3)
        self.release()
        if self.proc and self.proc.returncode is None:
            try:
                self.send('close')
                await asyncio.wait_for(self.proc.wait(), 1)
            except (OSError, RuntimeError, asyncio.TimeoutError):
                if self.proc.returncode is None:
                    try: self.proc.kill()
                    except ProcessLookupError: pass
                    await asyncio.wait([asyncio.create_task(self.proc.wait())], timeout=.15)
        if self.reader:
            await asyncio.wait([self.reader], timeout=.15)
