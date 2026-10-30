"""Bounded async RPC. All real sysfs/HID access occurs outside Decky's loop."""
import asyncio
import contextlib
import json
from pathlib import Path
from .session_io import enroll_session_scope, session_frozen, suspend_offset, SessionBoundary


async def reap(process, timeout=.15):
    if process is None:
        return True
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
    waiter = getattr(process, '_rgb_waiter', None)
    if waiter is None:
        waiter = process._rgb_waiter = asyncio.create_task(process.wait())
    done, _ = await asyncio.wait([waiter], timeout=timeout)
    # A kernel-uninterruptible helper retains its inherited flock. Never respawn
    # over it. asyncio's process reaper will collect it when the kernel permits.
    return bool(done)


class HardwareProcess:
    def __init__(self, lock, timeout=2., executable='/usr/bin/python3', worker=None, scope_enroller=None):
        self.lock, self.timeout = lock, timeout
        self.executable = executable
        self.worker = worker or Path(__file__).with_name('io_worker.py')
        self.process = None
        self.scope_enroller = scope_enroller or (enroll_session_scope if worker is None else None)
        self.last_scope = None
        self.guard = asyncio.Lock()
        self.cache = None
        self.suspended = False
        self.blocked = False

    def abort(self):
        self.suspended = True
        self.cache = None
        if self.process and self.process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self.process.kill()

    async def close(self, clear=True):
        process = self.process
        if process and process.returncode is None and self.last_scope and session_frozen():
            # Let the freezer own this transition. Reap only after session resumes.
            self.blocked = True
            if clear:
                self.cache = None
            return
        if not await reap(process):
            self.blocked = True
        elif self.process is process:
            self.process = None
            self.blocked = False
        if clear:
            self.cache = None

    async def _call(self, action, **values):
        epoch = suspend_offset()
        async with self.guard:
            if self.suspended:
                raise RuntimeError('RGB en suspensión; operación omitida.')
            if self.blocked and self.process and self.process.returncode is not None:
                self.process = None
                self.blocked = False
            if self.blocked:
                raise RuntimeError('RGB detenido tras un helper que no terminó; no se reintenta.')
            process = self.process
            read_only = action in ('state', 'session_probe') and (process is None or process.returncode is not None)
            try:
                if process is None or process.returncode is not None:
                    args = [self.executable, '-I', str(self.worker)]
                    if read_only:
                        args.append('--read-only')
                    # Keep ownership even if Decky cancels while an ioctl is in
                    # flight: closing the parent's fd cannot unlock this child.
                    descriptors = () if self.lock.file is None else (self.lock.file,)
                    process = await asyncio.create_subprocess_exec(
                        *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL, pass_fds=descriptors,
                        limit=16384, env={'PATH':'/usr/bin:/usr/sbin','LC_ALL':'C.UTF-8'})
                    self.process = process
                    if self.scope_enroller:
                        self.last_scope = await self.scope_enroller(process)
                    if self.suspended:
                        raise RuntimeError('RGB suspendido durante la apertura; se cancela.')
                if self.last_scope and (session_frozen() or suspend_offset()-epoch>.25):
                    raise SessionBoundary('La sesión cambió antes de enviar el comando RGB.')
                payload = dict(action=action, epoch=epoch, **values)
                if self.cache and self.cache.get('backend') == 'hid-rgb':
                    payload['cache'] = self.cache
                process.stdin.write((json.dumps(payload)+'\n').encode())
                await asyncio.wait_for(process.stdin.drain(), self.timeout)
                line = await self.read_reply(process)
                result = json.loads(line)
                if 'error' in result:
                    if result.get('kind') == 'SessionBoundary':
                        raise SessionBoundary(result['error'])
                    raise RuntimeError(result['error'])
                self.cache = result['actual']
                if read_only:
                    await self.close(clear=False)
                return dict(self.cache)
            except BaseException:
                await self.close()
                raise

    async def read_reply(self, process):
        task = asyncio.create_task(process.stdout.readline())
        try:
            while True:
                done, _ = await asyncio.wait([task], timeout=self.timeout)
                if done:
                    return task.result()
                if self.last_scope and session_frozen():
                    continue  # The OS intentionally paused our child; do not kill at the PM boundary.
                raise asyncio.TimeoutError()
        finally:
            if not task.done():
                task.cancel()

    async def session_probe(self):
        return await self._call('session_probe')

    async def state(self):
        return await self._call('state')

    async def write(self, colors, brightness):
        if self.lock.file is None:
            raise RuntimeError('No se posee el bloqueo RGB.')
        return await self._call('write', colors=colors, brightness=brightness)

    async def set_sleep(self, enabled):
        return await self._call('set_sleep', enabled=enabled)


class SimulatedIO:
    """Only for injected temporary devices in tests; never selected in production."""
    def __init__(self, hardware):
        self.hardware = hardware
        self.suspended = False
        self.blocked = False

    async def state(self):
        return self.hardware.state()

    async def write(self, colors, brightness):
        return self.hardware.write(colors, brightness)

    async def set_sleep(self, enabled):
        return self.hardware.set_sleep(enabled)

    def abort(self):
        self.suspended = True
        self.hardware.close()

    async def close(self, clear=True):
        self.hardware.close()
