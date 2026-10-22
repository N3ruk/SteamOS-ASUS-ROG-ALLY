#!/usr/bin/python3
"""Offline reproducible-layout ZIP; only explicit runtime files are packaged."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent


def build():
    version = json.loads((ROOT / 'package.json').read_text())['version']
    files = [ROOT / name for name in ['main.py', 'worker.py', 'plugin.json', 'package.json', 'README.md', 'VERIFICACION.md', 'THIRD-PARTY.md']]
    for directory in ['py_modules', 'dist', 'bin', 'licenses']:
        files += sorted(p for p in (ROOT / directory).rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts)
    if not (ROOT / 'dist/index.js').is_file():
        raise RuntimeError('Compila primero la interfaz con npm run build.')
    out = ROOT / 'release'
    out.mkdir(exist_ok=True)
    target = out / f'Ally-Power-Decky-{version}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            archive.write(p, 'ally-power-decky/' + p.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (out / 'SHA256SUMS').write_text(f'{digest}  {target.name}\n')
    print(f'{target} ({target.stat().st_size:,} bytes)')
    print(f'SHA256 {digest}')
    return target


if __name__ == '__main__':
    build()
