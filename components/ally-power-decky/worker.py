"""Isolated root pipe worker. Fixed local imports, no user-specified executables."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from py_modules import power_backend as hw
from py_modules.manager import host_support, ryzenadj_path
from py_modules.live_controller import LiveController


if __name__ == '__main__':
    try:
        if not host_support()['supported']:
            raise RuntimeError(host_support()['reason'])
        hw.RYZENADJ = ryzenadj_path()
        hw.Controller = LiveController
        hw.serve()
    except Exception as exc:
        import json
        print(json.dumps({'event': 'error', 'message': str(exc)}), flush=True)
        sys.exit(1)
