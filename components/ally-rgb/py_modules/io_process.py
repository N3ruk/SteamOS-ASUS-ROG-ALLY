"""Bounded async RPC. All real sysfs/HID access occurs outside Decky's loop."""
import asyncio
import contextlib
import json
from pathlib import Path


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
    def __init__(self, lock, timeout=2., executable='/usr/bin/python3', worker=None):
        self.lock, self.timeout = lock, timeout
        self.executable = executable
        self.worker = worker or Path(__file__).with_name('io_worker.py')
        self.process = None
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
        if not await reap(process):
            self.blocked = True
        elif self.process is process:
            self.process = None
        if clear:
            self.cache = None

    async def _call(self, action, **values):
        async with self.guard:
            if self.suspended:
                raise RuntimeError('RGB en suspensión; operación omitida.')
            if self.blocked:
                raise RuntimeError('RGB detenido tras un helper que no terminó; no se reintenta.')
            process = self.process
            read_only = action == 'state' and (process is None or process.returncode is not None)
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
                    if self.suspended:
                        raise RuntimeError('RGB suspendido durante la apertura; se cancela.')
                payload = dict(action=action, **values)
                if self.cache and self.cache.get('backend') == 'hid-rgb':
                    payload['cache'] = self.cache
                process.stdin.write((json.dumps(payload)+'\n').encode())
                await asyncio.wait_for(process.stdin.drain(), self.timeout)
                line = await asyncio.wait_for(process.stdout.readline(), self.timeout)
                result = json.loads(line)
                if 'error' in result:
                    raise RuntimeError(result['error'])
                self.cache = result['actual']
                if read_only:
                    await self.close(clear=False)
                return dict(self.cache)
            except BaseException:
                await self.close()
                raise

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
