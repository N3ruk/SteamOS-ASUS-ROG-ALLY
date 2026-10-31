"""Bounded, read-only startup preference. Late arrival is handled by the plugin."""
import json
from pathlib import Path
import time
from video_selector import parts, resolve, scan


def preferred_outputs(settings, timeout=1, read=scan, clock=time.monotonic, sleep=time.sleep):
    preferred = settings.get('config', {}).get('defaultDisplayIdentity')
    if not preferred:
        return '*,eDP-1'
    deadline = clock()+timeout
    while True:
        found = resolve(read(), preferred)
        if found:
            return parts(found['key'])[1]+',*,eDP-1'
        if clock() >= deadline:
            return '*,eDP-1'
        sleep(.08)


if __name__ == '__main__':
    try:
        settings = json.loads((Path(__file__).resolve().parents[2] / 'settings/output-manager/settings.json').read_text())
        print(preferred_outputs(settings))
    except Exception:
        print('*,eDP-1')
