"""Read-only typed logind observer and conservative suspend-clock fallback.

No inhibitors, units, HID operations or unbounded process joins.
"""
import asyncio
import contextlib
import json
import logging
from pathlib import Path
import time
from .io_process import reap


def suspend_offset():
    return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()


class SleepMonitor:
    def __init__(self, callback, logger=None, offset=suspend_offset, clock=time.monotonic):
        self.callback = callback
        self.logger = logger or logging.getLogger('ally-rgb')
        self.offset, self.clock = offset, clock
        self.baseline = offset()
        self.last_wake = float('-inf')
        self.sleeping = False
        self.preparing = None
        self.shutdown = None
        self.tasks = []
        self.process = None
        self.logind = 'starting'
        self.warned = False
        self.closing = False

    @property
    def ready(self):
        return self.logind == 'connected' and self.preparing is False and self.shutdown is False

    def start(self):
        if not self.tasks:
            self.tasks = [asyncio.create_task(self.listen()), asyncio.create_task(self.watch_clock())]

    async def event(self, sleeping, source):
        self.baseline = self.offset()
        if source == 'logind':
            self.preparing = sleeping
        if sleeping:
            if self.sleeping:
                return
            self.sleeping = True
        else:
            if source == 'logind' and not self.sleeping and self.last_wake != float('-inf'):
                return
            self.sleeping = False
            self.last_wake = self.clock()
        # Callback only invalidates/enqueues. It never performs hardware I/O.
        self.logger.info('RGB power event: %s (%s)', 'suspend' if sleeping else 'wake', source)
        await self.callback(sleeping)

    async def check_clock(self):
        current = self.offset()
        if current - self.baseline > .5:
            await self.event(False, 'suspend-clock')
        self.baseline = current

    async def watch_clock(self):
        while True:
            await asyncio.sleep(1)
            await self.check_clock()

    async def stop_process(self):
        process, self.process = self.process, None
        return await reap(process)

    async def listen(self):
        while not self.closing:
            try:
                self.process = await asyncio.create_subprocess_exec(
                    '/usr/bin/python3', '-I', str(Path(__file__).with_name('logind_worker.py')),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=4096,
                    env={'PATH':'/usr/bin:/usr/sbin','LC_ALL':'C.UTF-8'})
                while line := await self.process.stdout.readline():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError('Invalid observer event')
                    if type(value.get('shutdown')) is bool:
                        self.shutdown = value['shutdown']
                        if self.shutdown:
                            await self.callback(True)
                    if value.get('ready') is True:
                        self.logind = 'connected'
                    if type(value.get('sleeping')) is bool:
                        await self.event(value['sleeping'], 'logind')
                raise OSError('Observer disconnected')
            except (OSError, ValueError):
                self.logind = 'unavailable'
                self.preparing = self.shutdown = None
                await self.callback(True)
                if not self.warned:
                    self.warned = True
                    self.logger.warning('RGB logind no disponible: recuperación omitida hasta reconectar.')
            finally:
                exited = await self.stop_process()
            if not exited:
                return  # Never multiply stuck helper processes.
            await asyncio.sleep(5)

    async def close(self):
        self.closing = True
        tasks, self.tasks = self.tasks, []
        for task in tasks:
            task.cancel()
        await self.stop_process()
        if tasks:
            await asyncio.wait(tasks, timeout=.35)
        self.logind = 'stopped'
