"""Isolated root pipe worker. Fixed local imports, no user-specified executables."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from py_modules import power_backend as hw
from py_modules.manager import host_support, ryzenadj_path
from py_modules.live_controller import LiveController
from py_modules.session_io import WorkerSessionGuard, SessionBoundary
import json
import os


if __name__ == '__main__':
    try:
        # Parent must enroll this waiting process into user.slice BEFORE any
        # hardware discovery, flock acquisition, controller or RyzenAdj call.
        begin = json.loads(sys.stdin.readline(4097))
        session = WorkerSessionGuard()
        session.check()
        if begin.get('action') != 'begin' or abs(begin['epoch'] - session.baseline) > .25:
            raise RuntimeError('Inicio de otro ciclo de suspensión rechazado.')
        if sys.argv[1:] == ['--session-probe']:
            print(json.dumps({'event': 'probe', 'pid': os.getpid(),
                  'scope': Path('/proc/self/cgroup').read_text().strip(),
                  'hardware_touched': False}), flush=True)
            sys.exit(0)
        if not host_support()['supported']:
            raise RuntimeError(host_support()['reason'])
        hw.RYZENADJ = ryzenadj_path()
        hw.Controller = LiveController
        hw.IO_GUARD = session.check
        hw.serve(session=session, restore_on_exit=False)
    except Exception as exc:
        import json
        print(json.dumps({'event': 'session_ended' if isinstance(exc, SessionBoundary) else 'error',
                          'message': str(exc)}), flush=True)
        sys.exit(1)
