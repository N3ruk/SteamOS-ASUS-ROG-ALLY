"""One video controller inside Output Manager; only metadata is observed here."""
import asyncio
import contextlib
import json
from pathlib import Path
import os
import subprocess
import time
import uuid

from video_selector import ARCH, epoch, parts, resolve, scan, topology


def gaming_context():
    if subprocess.run(['/usr/bin/pgrep', '-x', 'plasmashell'], capture_output=True).returncode == 0:
        return None
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if (entry/'comm').read_text().strip() not in ('gamescope', 'gamescope-wl'):
                continue
            if os.readlink(entry/'exe') != '/usr/bin/gamescope':
                continue
            arguments = (entry/'cmdline').read_bytes().split(b'\0')
            if b'-e' not in arguments or b'--backend' in arguments:
                continue
            start = (entry/'stat').read_text().split(') ', 1)[1].split()[19]
            return {'pid': int(entry.name), 'start': start}
        except (OSError, ValueError):
            continue
    return None


async def bus(*args):
    p = await asyncio.create_subprocess_exec('/usr/bin/busctl', '--system', '--timeout=1', *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C'})
    try:
        data, _ = await asyncio.wait_for(p.communicate(), 1.5)
        if p.returncode:
            raise RuntimeError('Cannot enroll video helper in session scope')
        return data
    finally:
        if p.returncode is None:
            p.kill()
            await asyncio.wait([asyncio.create_task(p.wait())], timeout=.2)


class VideoRuntime:
    def __init__(self, config, logger):
        self.config, self.log = config, logger
        self.nodes, self.owned = {}, {}
        self.operation = asyncio.Lock()
        self.task = self.process = None
        self.offset = epoch()
        self.context = None
        self.session_since = self.changed_since = time.monotonic()
        self.signature = ()
        self.attempt = self.cleanup_attempt = None
        self.manual_hold = False
        self.revision = 0
        self.error = ''
        self.last = None
        self.closed = False

    def cancel(self):
        self.revision += 1
        if self.process and self.process.returncode is None and self.process.stdin:
            with contextlib.suppress(Exception):
                self.process.stdin.write(b'{"cancel":true}\n')

    def observe(self, now=None, current=None):
        now = time.monotonic() if now is None else now
        offset = epoch()
        self.nodes = scan(cache=self.nodes)
        context = gaming_context() if current is None else current
        if context != self.context or abs(offset-self.offset) > .25:
            self.cancel()
            self.context, self.offset = context, offset
            self.session_since = self.changed_since = now
            self.manual_hold = False
            self.attempt = self.cleanup_attempt = None
        signature = topology(self.nodes)
        if signature != self.signature:
            self.signature, self.changed_since = signature, now
        return context

    def preferred(self):
        identity = self.config().get('defaultDisplayIdentity')
        return resolve(self.nodes, identity) if identity else None

    def default_hint(self):
        node = self.preferred()
        return node['key'] if node else self.config().get('defaultConnector')

    def diagnostics(self):
        return {'architecture': ARCH, 'gaming': bool(self.context), 'preferredIdentity': self.config().get('defaultDisplayIdentity'),
            'preferredConnector': self.default_hint(), 'manualHold': self.manual_hold,
            'owned': list(self.owned), 'busy': bool(self.process and self.process.returncode is None),
            'error': self.error, 'last': self.last}

    async def start(self):
        self.observe()
        self.task = asyncio.create_task(self.monitor())

    async def monitor(self):
        while not self.closed:
            try:
                current = self.observe()
                if current:
                    now = time.monotonic()
                    target = self.preferred()
                    key = (tuple(current.items()), self.offset, self.signature,
                           self.config().get('defaultDisplayIdentity'))
                    if (target and not self.manual_hold and now-self.session_since >= 10
                            and now-self.changed_since >= 2 and key != self.attempt):
                        self.attempt = key  # Consume before awaiting; no infinite retry loop.
                        result = await self.select(parts(target['key']), manual=False)
                        self.log.info('AOC video selection: %s', result)
                    elif (not target and self.owned and not self.manual_hold
                          and now-self.session_since >= 10 and now-self.changed_since >= 2
                          and key != self.cleanup_attempt):
                        self.cleanup_attempt = key
                        await self.release()
                elif self.owned:
                    key = (self.offset, tuple(sorted((k,v['id']) for k,v in self.owned.items())))
                    if key != self.cleanup_attempt:
                        self.cleanup_attempt = key
                        await self.release()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = str(exc)
                self.log.warning('Video observation: %s', exc)
            await asyncio.sleep(2)

    async def select(self, connector, manual=True):
        if manual:
            self.cancel()
            self.manual_hold = True
        revision = self.revision
        async with self.operation:
            self.observe()
            if revision != self.revision or not self.context:
                return {'ok': False, 'error': 'Video selection is available only in a stable Gaming session'}
            key = str(connector[0])+':'+connector[1]
            target = self.nodes.get(key)
            if not target or not target['connected'] or not target['identity']:
                return {'ok': False, 'error': 'No verified monitor identity on that connector'}
            result = await self.run('switch', target)
            self.error = '' if result.get('ok') else result.get('error', 'Video selection failed')
            self.last = {k:v for k,v in result.items() if k != 'owned'}
            return result

    async def release(self):
        async with self.operation:
            result = await self.run('release')
            if not result.get('ok'):
                self.error = result.get('error', 'Video release failed')
            return result

    async def probe(self):
        async with self.operation:
            return await self.run('probe')

    async def run(self, action, target=None):
        if self.process and self.process.returncode is None:
            return {'ok': False, 'error': 'Previous video helper is still exiting; no second writer'}
        config = self.config()
        context = self.context or {'pid': 0, 'start': ''}
        request = {'action': action, 'epoch': epoch(), **context, 'uid': config.get('targetUid', 1000),
                   'cache': self.nodes, 'owned': self.owned, 'target': target}
        p = await asyncio.create_subprocess_exec('/usr/bin/python3', str(Path(__file__).with_name('video_selector.py')),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C.UTF-8'})
        self.process = p
        scope = f'output-video-{p.pid}-{uuid.uuid4().hex[:8]}.scope'
        reader = None
        try:
            await bus('call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1',
                'org.freedesktop.systemd1.Manager', 'StartTransientUnit', 'ssa(sv)a(sa(sv))',
                scope, 'fail', '3', 'PIDs', 'au', '1', str(p.pid), 'Slice', 's', 'user.slice',
                'CollectMode', 's', 'inactive-or-failed', '0')
            expected = '0::/user.slice/'+scope
            for _ in range(60):
                if p.returncode is not None:
                    raise RuntimeError('Video helper exited before scope enrollment')
                if expected in Path(f'/proc/{p.pid}/cgroup').read_text().splitlines():
                    break
                await asyncio.sleep(.01)
            else:
                raise RuntimeError('Video helper scope enrollment was not confirmed')
            p.stdin.write((json.dumps(request)+'\n').encode())
            await p.stdin.drain()
            async def read():
                result = None
                while line := await p.stdout.readline():
                    item = json.loads(line)
                    if 'progress' in item:
                        self.owned = item['progress']
                    else:
                        result = item
                        if 'owned' in item:
                            self.owned = item['owned']
                await p.wait()
                return result or {'ok': False, 'error': 'Video helper returned no confirmation'}
            reader = asyncio.create_task(read())
            return await asyncio.wait_for(asyncio.shield(reader), 12)
        except asyncio.CancelledError:
            if p.stdin and p.returncode is None:
                with contextlib.suppress(Exception):
                    p.stdin.write(b'{"cancel":true}\n')
            if reader:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(asyncio.shield(reader), 2)
            raise
        except Exception as exc:
            return {'ok': False, 'error': str(exc), 'owned': self.owned}
        finally:
            if p.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    p.kill()
                await asyncio.wait([asyncio.create_task(p.wait())], timeout=.3)
            if reader and not reader.done():
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(reader, .3)

    async def close(self):
        self.closed = True
        self.cancel()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.owned:
            await self.release()
