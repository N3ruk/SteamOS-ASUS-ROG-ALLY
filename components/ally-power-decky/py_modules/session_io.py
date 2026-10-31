"""Session-freezer boundary for POWER I/O; no persistent systemd units or inhibitors."""
import asyncio
import contextlib
import json
from pathlib import Path
import re
import time
import uuid

FREEZE = Path('/sys/fs/cgroup/user.slice/cgroup.freeze')


class SessionBoundary(RuntimeError):
    pass


def suspend_offset():
    return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()


def session_frozen():
    try:
        return FREEZE.read_text().strip() != '0'
    except OSError:
        return True  # Missing freezer support must not silently permit POWER I/O.


async def bus_call(*arguments, timeout=2):
    process = await asyncio.create_subprocess_exec(
        '/usr/bin/busctl', '--system', '--json=short', '--timeout=1', *arguments,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={'PATH':'/usr/bin:/usr/sbin','LC_ALL':'C.UTF-8'})
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
        if process.returncode:
            raise SessionBoundary('No se pudo confirmar la sesión mediante systemd/logind.')
        return output
    finally:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            # Process teardown must not become a suspension blocker.
            await asyncio.wait([asyncio.create_task(process.wait())], timeout=.15)


async def session_awake():
    if session_frozen():
        return False
    try:
        output = await bus_call('get-property', 'org.freedesktop.login1',
            '/org/freedesktop/login1', 'org.freedesktop.login1.Manager',
            'PreparingForSleep', 'PreparingForShutdown')
        values = [json.loads(line) for line in output.splitlines()]
        return (len(values) == 2 and all(v.get('type') == 'b' and v.get('data') is False for v in values)
                and not session_frozen())
    except (OSError, ValueError, asyncio.TimeoutError, SessionBoundary):
        return False


async def enroll_session_scope(process):
    """Move our waiting child before sending it *any* hardware request."""
    if process.returncode is not None or session_frozen():
        raise SessionBoundary('La sesión no está disponible para iniciar E/S POWER.')
    unit = f'ally-power-io-{process.pid}-{uuid.uuid4().hex[:8]}.scope'
    await bus_call('call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1',
        'org.freedesktop.systemd1.Manager', 'StartTransientUnit', 'ssa(sv)a(sa(sv))',
        unit, 'fail', '3', 'PIDs', 'au', '1', str(process.pid),
        'Slice', 's', 'user.slice', 'CollectMode', 's', 'inactive-or-failed', '0')
    expected = '/user.slice/' + unit
    try:
        # StartTransientUnit returns a JOB, not proof that the PID has moved yet.
        # Wait boundedly on our own waiting child; still no hardware payload.
        for _ in range(100):
            if process.returncode is not None or session_frozen():
                break
            groups = Path(f'/proc/{process.pid}/cgroup').read_text().splitlines()
            if '0::' + expected in groups:
                return expected
            await asyncio.sleep(.01)
        raise SessionBoundary('El auxiliar POWER no está protegido por el freezer de la sesión.')
    except BaseException:
        # An empty scope from an incomplete job must not be left active.
        with contextlib.suppress(Exception):
            await bus_call('call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1',
                'org.freedesktop.systemd1.Manager', 'StopUnit', 'ss', unit, 'replace')
        raise


class WorkerSessionGuard:
    """Recheck before each operation/report, rejecting queued pre-suspend frames."""
    def __init__(self, offset=suspend_offset):
        self.offset = offset
        self.baseline = offset()

    def check(self):
        groups = Path('/proc/self/cgroup').read_text().splitlines()
        if not any(line.startswith('0::/user.slice/ally-power-io-') and line.endswith('.scope') for line in groups):
            raise SessionBoundary('Auxiliar POWER fuera de su scope de sesión; se rechaza E/S.')
        if session_frozen() or self.offset() - self.baseline > .25:
            raise SessionBoundary('Cambió el ciclo de suspensión; frame antiguo rechazado.')
