"""Private, RGB-only pipe helper. Never accepts paths, executables or HID packets."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from py_modules.rgb import Hardware
from py_modules.session_io import WorkerSessionGuard, suspend_offset, SessionBoundary


def serve(read_only=False):
    session = WorkerSessionGuard()
    hardware = Hardware(write_guard=session.check)
    try:
        for line in sys.stdin:
            if len(line) > 8192:
                return
            try:
                request = json.loads(line)
                action = request['action']
                if action not in ('state', 'write', 'set_sleep', 'session_probe') or (read_only and action not in ('state', 'session_probe')):
                    raise ValueError('Operación RGB no permitida.')
                session.check()
                if abs(suspend_offset()-request['epoch'])>.25:
                    raise SessionBoundary('Comando de un ciclo de suspensión anterior rechazado.')
                if action == 'session_probe':
                    import os
                    actual = {'pid':os.getpid(), 'scope':Path('/proc/self/cgroup').read_text().strip(), 'hardware_touched':False}
                    print(json.dumps({'actual':actual}),flush=True)
                    return
                cache = request.get('cache')
                if cache and hardware.hid_last is None:
                    if hardware.state().get('identity') != cache.get('identity'):
                        raise ValueError('Cambió la identidad RGB; no se reutiliza el estado anterior.')
                    observation = cache['kernel_observed']
                    hardware.hid_observed = (observation[0], tuple(observation[1]), *observation[2:])
                    hardware.hid_last = (cache['colors'], cache['brightness'])
                action = request['action']
                if action == 'state':
                    actual = hardware.state()
                elif action == 'write' and not read_only:
                    actual = hardware.write(request['colors'], request['brightness'])
                elif action == 'set_sleep' and not read_only:
                    hardware.set_sleep(request['enabled'])
                    actual = hardware.state()
                else:
                    raise ValueError('Operación RGB no permitida.')
                print(json.dumps({'actual': actual}), flush=True)
            except Exception as exc:
                print(json.dumps({'error': str(exc), 'kind': type(exc).__name__}), flush=True)
            if read_only:
                return
    finally:
        hardware.close()


if __name__ == '__main__':
    serve(read_only=sys.argv[1:] == ['--read-only'])
