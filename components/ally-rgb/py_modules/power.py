"""Backend sleep observation: logind signals plus a Linux suspend-clock fallback.

No system units, inhibitors, configuration changes or LED access here.
"""
import asyncio
import contextlib
import json
import logging
import time


MATCH = ("type='signal',sender='org.freedesktop.login1',"
         "path='/org/freedesktop/login1',interface='org.freedesktop.login1.Manager',"
         "member='PrepareForSleep'")


def suspend_offset():
    # BOOTTIME includes suspended time; MONOTONIC excludes it. A slow/busy
    # event loop alone does not look like a wake, nor does changing wall time.
    return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()


def sleep_signal(line):
    try:
        event = json.loads(line)
    except (ValueError, UnicodeError):
        return None
    if not isinstance(event, dict):
        return None
    if (event.get('type') != 'signal' or event.get('path') != '/org/freedesktop/login1'
            or event.get('interface') != 'org.freedesktop.login1.Manager'
            or event.get('member') != 'PrepareForSleep'):
        return None
    payload = event.get('payload', {})
    if not isinstance(payload, dict):
        return None
    data = payload.get('data')
    if payload.get('type') == 'b' and isinstance(data, list) and len(data) == 1 and type(data[0]) is bool:
        return data[0]
    return None


class SleepMonitor:
    def __init__(self, callback, logger=None, offset=suspend_offset, clock=time.monotonic):
        self.callback = callback
        self.logger = logger or logging.getLogger('ally-rgb')
        self.offset, self.clock = offset, clock
        self.baseline = offset()
        self.last_wake = float('-inf')
        self.sleeping = False
        self.guard = asyncio.Lock()
        self.tasks = []
        self.process = None
        self.logind = 'starting'

    def start(self):
        if not self.tasks:
            self.tasks = [asyncio.create_task(self.listen()), asyncio.create_task(self.watch_clock())]

    async def event(self, sleeping, source):
        async with self.guard:
            await self._event(sleeping, source)

    async def _event(self, sleeping, source):
        self.baseline = self.offset()
        if sleeping:
            if self.sleeping:
                return
            self.sleeping = True
        else:
            if not self.sleeping and self.clock() - self.last_wake < 2:
                return
            self.sleeping = False
            self.last_wake = self.clock()
        self.logger.info('RGB power event: %s (%s)', 'suspend' if sleeping else 'wake', source)
        await self.callback(sleeping)

    async def check_clock(self):
        async with self.guard:
            current = self.offset()
            if current - self.baseline > .5:
                await self._event(False, 'suspend-clock')
            self.baseline = current

    async def watch_clock(self):
        while True:
            await asyncio.sleep(.5)
            await self.check_clock()

    async def stop_process(self):
        process, self.process = self.process, None
        if process:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await process.wait()

    async def listen(self):
        while True:
            try:
                self.process = await asyncio.create_subprocess_exec(
                    '/usr/bin/busctl', '--system', '--json=short', '--match=' + MATCH,
                    'monitor', 'org.freedesktop.login1', stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL)
                self.logind = 'connected'
                while line := await self.process.stdout.readline():
                    value = sleep_signal(line)
                    if value is not None:
                        await self.event(value, 'logind')
                raise OSError('logind monitor disconnected')
            except (OSError, ValueError) as exc:
                self.logind = 'reconnecting'
                self.logger.warning('RGB logind unavailable; suspend-clock remains active: %s', exc)
            finally:
                await self.stop_process()
            await asyncio.sleep(5)

    async def close(self):
        tasks, self.tasks = self.tasks, []
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.stop_process()
