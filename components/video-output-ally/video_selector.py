"""Video-only DRM selector. No EDID, audio, power, physical HPD or dock reset."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time

ARCH = 'edid-mst-nudge-v1'
DRM = Path('/sys/class/drm')
DEBUG = Path('/sys/kernel/debug/dri')
KEY = re.compile(r'^(\d+):((?:eDP|DP|HDMI-A|DSI|LVDS)-\d+)$')
FORCES = {'unspecified', 'on', 'on-digital', 'off'}


class Boundary(RuntimeError):
    pass


def epoch():
    return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()


def identity(data):
    if len(data) < 128 or data[:8] != b'\x00\xff\xff\xff\xff\xff\xff\x00' or sum(data[:128]) % 256:
        return None
    return 'edid:' + hashlib.sha256(data[:128]).hexdigest()


def model(data):
    for pos in range(54, min(126, len(data)), 18):
        if data[pos:pos+5] == b'\x00\x00\x00\xfc\x00':
            return data[pos+5:pos+18].decode('ascii', 'replace').strip()
    return ''


def parts(key):
    match = KEY.fullmatch(key)
    if not match:
        raise ValueError('Invalid DRM connector')
    return int(match[1]), match[2]


def scan(base=DRM, debug=DEBUG, cache=None):
    """Read cached kernel metadata; status queries must NEVER reprobe hardware."""
    cache = cache or {}
    result = {}
    for p in sorted(base.glob('card*-*')):
        if '-' not in p.name:
            continue
        card, name = p.name.split('-', 1)
        key = card.removeprefix('card') + ':' + name
        if not KEY.fullmatch(key):
            continue
        try:
            ident = int((p / 'connector_id').read_text())
            status = (p / 'status').read_text().strip()
            enabled = (p / 'enabled').read_text().strip() == 'enabled'
            data = (p / 'edid').read_bytes()
        except (OSError, ValueError):
            continue
        try:
            force = (debug / card.removeprefix('card') / name / 'force').read_text().strip()
        except OSError:
            force = None
        physical = identity(data)
        previous = cache.get(key, {})
        cached = force == 'off' and previous.get('id') == ident
        result[key] = {'key': key, 'id': ident, 'identity': physical or (previous.get('identity') if cached else None),
            'model': model(data) or (previous.get('model', '') if cached else ''),
            'connected': status == 'connected' or (cached and previous.get('connected', False)),
            'enabled': enabled, 'force': force, 'internal': name.startswith(('eDP-', 'DSI-', 'LVDS-'))}
    return result


def resolve(nodes, preferred):
    matches = [n for n in nodes.values() if n['connected'] and n['identity'] == preferred]
    return matches[0] if len(matches) == 1 else None


def topology(nodes):
    return tuple(sorted((n['key'], n['id'], n['identity']) for n in nodes.values() if n['connected']))


def same_node(a, b):
    return bool(a and b and a['id'] == b['id'] and a['identity'] and a['identity'] == b['identity'])


class Guard:
    def __init__(self, request):
        self.request = request
        self.baseline = request['epoch']

    def check(self, session=True):
        try:
            pending = os.read(0, 4096)
        except BlockingIOError:
            pending = None
        if pending is not None:
            raise Boundary('Video request cancelled or parent disconnected')
        groups = Path('/proc/self/cgroup').read_text().splitlines()
        if not any(x.startswith('0::/user.slice/output-video-') and x.endswith('.scope') for x in groups):
            raise Boundary('Video helper outside session freezer')
        if Path('/sys/fs/cgroup/user.slice/cgroup.freeze').read_text().strip() != '0' or abs(epoch()-self.baseline) > .25:
            raise Boundary('Suspension boundary; video request cancelled')
        result = subprocess.run(['/usr/bin/busctl', '--system', '--timeout=1', 'get-property',
            'org.freedesktop.login1', '/org/freedesktop/login1', 'org.freedesktop.login1.Manager',
            'PreparingForSleep', 'PreparingForShutdown'], capture_output=True, text=True, timeout=1.3)
        if result.returncode or result.stdout.splitlines() != ['b false', 'b false']:
            raise Boundary('System preparing for sleep or shutdown')
        if session:
            pid = self.request['pid']
            try:
                start = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()[19]
                executable = os.readlink(f'/proc/{pid}/exe')
            except OSError as exc:
                raise Boundary('Gaming session ended') from exc
            if start != self.request['start'] or executable != '/usr/bin/gamescope':
                raise Boundary('Gaming session replaced')
            if subprocess.run(['/usr/bin/pgrep', '-x', 'plasmashell'], capture_output=True).returncode == 0:
                raise Boundary('Desktop session owns the displays')


class Access:
    def __init__(self, request, guard, progress=lambda _: None):
        self.request, self.guard, self.progress = request, guard, progress
        self.cache = request.get('cache', {})
        self.owned = dict(request.get('owned', {}))
        uid = request['uid']
        if not isinstance(uid, int) or uid <= 0:
            raise ValueError('A non-root session user is required')
        self.user = pwd.getpwuid(uid).pw_name
        self.env = {'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C', 'XDG_RUNTIME_DIR': f'/run/user/{uid}'}

    def nodes(self):
        self.cache = scan(cache=self.cache)
        return self.cache

    def context(self):
        runtime = Path(self.env['XDG_RUNTIME_DIR'])
        data = {}
        for line in (runtime / 'gamescope-environment').read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and key in ('DISPLAY', 'GAMESCOPE_WAYLAND_DISPLAY', 'XAUTHORITY'):
                data[key] = value
        if not re.fullmatch(r':\d+(?:\.\d+)?', data.get('DISPLAY', '')):
            raise Boundary('No Gamescope X display')
        if not re.fullmatch(r'gamescope-[\w.-]+', data.get('GAMESCOPE_WAYLAND_DISPLAY', '')):
            raise Boundary('No Gamescope Wayland socket')
        if not (runtime / data['GAMESCOPE_WAYLAND_DISPLAY']).exists():
            raise Boundary('Gamescope Wayland socket is gone')
        if 'XAUTHORITY' in data and not Path(data['XAUTHORITY']).is_relative_to(runtime):
            raise Boundary('Unexpected X authority path')
        self.env.update(data)
        result = self.command(['/usr/bin/xprop', '-root', 'GAMESCOPE_XWAYLAND_SERVER_ID'])
        if not re.search(r'=\s*0\s*$', result):
            raise Boundary('Not the primary Gamescope X server')
        return self.active()

    def command(self, args):
        result = subprocess.run(['/usr/bin/runuser', '-u', self.user, '--', '/usr/bin/env', '-i',
            *[k+'='+v for k, v in self.env.items()], *args], capture_output=True, text=True, timeout=1.5,
            env={'PATH': '/usr/bin:/usr/sbin', 'LC_ALL': 'C'})
        if result.returncode:
            raise RuntimeError(result.stderr.strip()[:300] or 'Gamescope command failed')
        return result.stdout

    def active(self):
        text = self.command(['/usr/bin/gamescopectl'])
        match = re.search(r'Connector Name:\s*([\w-]+)', text)
        if not match:
            raise RuntimeError('Gamescope did not report its active connector')
        return match[1]

    def set_force(self, node, force, session=True):
        if force not in FORCES:
            raise ValueError('Unknown DRM force value')
        self.guard.check(session)
        fresh = self.nodes().get(node['key'])
        if not same_node(fresh, node):
            raise Boundary('Display identity changed before write')
        card, name = parts(node['key'])
        (DRM / f'card{card}-{name}' / 'status').write_text('detect\n' if force == 'unspecified' else force+'\n')

    def nudge(self):
        self.guard.check()
        self.command(['/usr/bin/xprop', '-root', '-f', 'GAMESCOPE_DISPLAY_MODE_NUDGE', '32c',
                      '-set', 'GAMESCOPE_DISPLAY_MODE_NUDGE', '1'])

    def desktop_notify(self, cards):
        if self.request.get('pid'):
            try:
                self.context()
                self.nudge()
                return
            except (Boundary, OSError, RuntimeError, subprocess.SubprocessError):
                pass  # Gaming ended: notify KWin instead, without touching its layout.
        # KWin handles a normal DRM card change event. No AMD HPD simulation.
        for card in cards:
            self.guard.check(session=False)
            (DRM / f'card{card}' / 'uevent').write_text('change\n')

    def remember(self, node, before, after):
        original = self.owned.get(node['key'], {}).get('before', before)
        if after == original:
            self.owned.pop(node['key'], None)
        else:
            self.owned[node['key']] = {**node, 'before': original, 'after': after}
        self.progress(self.owned)


def release(access, session=False):
    errors = []
    cards = set()
    for key, record in list(access.owned.items()):
        fresh = access.nodes().get(key)
        if not fresh or fresh['id'] != record['id']:
            access.owned.pop(key, None)
            continue
        if fresh['force'] != record['after']:
            access.owned.pop(key, None)  # Another owner changed it. Do not overwrite.
            continue
        try:
            access.set_force(record, record['before'], session=session)
            cards.add(parts(key)[0])
            access.owned.pop(key, None)
        except Exception as exc:
            errors.append(str(exc))
    access.progress(access.owned)
    if cards:
        try:
            access.desktop_notify(cards)
        except Exception as exc:
            errors.append(str(exc))
    return {'ok': not errors, 'owned': access.owned, 'error': '; '.join(errors)}


def switch(access, target, timeout=3):
    changes = []
    try:
        access.guard.check()
        active = access.context()  # Prove native readback BEFORE touching any display.
        nodes = access.nodes()
        node = nodes.get(target['key'])
        if not same_node(node, target) or not node['connected']:
            raise RuntimeError('Selected display is absent or has changed identity')
        if any(n['force'] not in FORCES for n in nodes.values() if n['connected']):
            raise RuntimeError('Cannot snapshot current DRM force state')
        card, name = parts(node['key'])
        competitors = [n for n in nodes.values() if n['key'] != node['key'] and not n['internal']
                       and n['connected'] and n['force'] != 'off']
        if active == name and node['enabled'] and not competitors:
            return {'ok': True, 'active': name, 'owned': access.owned, 'unchanged': True}
        # Enable and revalidate the desired sink BEFORE excluding competing outputs.
        if node['force'] != 'unspecified':
            access.set_force(node, 'unspecified'); changes.append((node, node['force'], 'unspecified'))
            access.remember(node, node['force'], 'unspecified')
        current = access.nodes().get(node['key'])
        if not same_node(current, target) or not current['connected']:
            raise RuntimeError('Selected display did not return after detection')
        for other in access.nodes().values():
            if other['key'] == node['key'] or other['internal'] or not other['connected'] or other['force'] == 'off':
                continue
            if parts(other['key'])[0] != card:
                raise RuntimeError('Multi-GPU output switching is not supported by this repair')
            access.set_force(other, 'off'); changes.append((other, other['force'], 'off'))
            access.remember(other, other['force'], 'off')
        access.nudge()  # Native compositor refresh; NO AMD trigger_hotplug or uevent spoofing.
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            access.guard.check()
            current = access.nodes().get(node['key'])
            selected = access.active()
            if same_node(current, target) and current['enabled'] and selected == name:
                return {'ok': True, 'active': selected, 'owned': access.owned}
            time.sleep(.15)
        raise RuntimeError('Gamescope did not confirm the selected monitor')
    except Exception as exc:
        rollback_errors = []
        for node, before, after in reversed(changes):
            try:
                fresh = access.nodes().get(node['key'])
                if fresh and fresh['id'] == node['id'] and fresh['force'] == after:
                    access.set_force(node, before)
                    access.remember(node, after, before)
            except Exception as rollback:
                rollback_errors.append(str(rollback))
        if changes and not rollback_errors:
            try:
                access.nudge()
            except Exception as rollback:
                rollback_errors.append(str(rollback))
        return {'ok': False, 'error': str(exc), 'owned': access.owned, 'rollback_errors': rollback_errors}


def worker():
    data = b''
    while b'\n' not in data and len(data) <= 65536:
        chunk = os.read(0, 65537-len(data))
        if not chunk:
            raise Boundary('Parent disconnected before video enrollment')
        data += chunk
    line, sep, pending = data.partition(b'\n')
    if not sep or pending.strip():
        raise Boundary('Cancelled or oversized video request')
    request = json.loads(line)
    os.set_blocking(0, False)
    guard = Guard(request)
    guard.check(session=request['action'] == 'switch')
    if request['action'] == 'probe':
        return {'ok': True, 'scope': Path('/proc/self/cgroup').read_text().strip(),
                'hardware_written': False, 'architecture': ARCH, 'connectors': list(scan().values())}
    def progress(owned):
        print(json.dumps({'progress': owned}), flush=True)
    access = Access(request, guard, progress)
    if request['action'] == 'release':
        return release(access)
    if request['action'] != 'switch':
        raise ValueError('Unknown video action')
    return switch(access, request['target'])


if __name__ == '__main__':
    try:
        print(json.dumps(worker()), flush=True)
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}), flush=True)
