#!/usr/bin/python3
"""Build offline .run and source-bearing tarball from explicitly allowed files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
VERSION = '1.0.0'
NAME = 'Ally-Power-' + VERSION
VENDOR_HASH = 'd04547f111c6af3e40d3f210468adb884561618ddade0b640d90e50c88d03444'
SOURCE_HASH = 'd1998b6c2d1b564f5d43c786cbf764ca9a1d8bb213e2001f98f611ead3087c7e'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def populate(destination):
    for name, expected in [('ryzenadj-manylinux_2_28-x86_64.tar.gz', VENDOR_HASH),
                           ('RyzenAdj-v0.19.0-source.tar.gz', SOURCE_HASH)]:
        if digest(ROOT / 'vendor' / name) != expected:
            raise RuntimeError('Hash de dependencia incorrecto: ' + name)
    (destination / 'payload').mkdir(parents=True)
    for name in ('app.py', 'power_backend.py', 'tray.py', 'icon-gaming.png', 'icon.svg', 'status-notifier.xml'):
        shutil.copyfile(ROOT / 'src' / name, destination / 'payload' / name)
    with tarfile.open(ROOT / 'vendor/ryzenadj-manylinux_2_28-x86_64.tar.gz') as archive:
        member = archive.extractfile('ryzenadj-manylinux_2_28-x86_64/ryzenadj')
        (destination / 'payload/ryzenadj').write_bytes(member.read())
    (destination / 'payload/ryzenadj').chmod(0o755)
    shutil.copyfile(ROOT / 'packaging/installer.py', destination / 'installer.py')
    for name in ('LEEME.md', 'THIRD-PARTY.md'):
        shutil.copyfile(ROOT / name, destination / name)
    shutil.copytree(ROOT / 'licenses', destination / 'licenses')
    (destination / 'source').mkdir()
    shutil.copyfile(ROOT / 'vendor/RyzenAdj-v0.19.0-source.tar.gz', destination / 'source/RyzenAdj-v0.19.0-source.tar.gz')
    for directory in ('src', 'tests', 'packaging'):
        shutil.copytree(ROOT / directory, destination / 'source' / directory,
                        ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(ROOT / 'build.py', destination / 'source/build.py')
    shutil.copyfile(ROOT / 'REBUILD.md', destination / 'source/REBUILD.md')
    hashes = {str(p.relative_to(destination)): digest(p) for p in sorted(destination.rglob('*')) if p.is_file()}
    (destination / 'manifest.json').write_text(json.dumps({'version': VERSION, 'sha256': hashes}, indent=2) + '\n')


def main():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ally-power-build-') as temporary:
        stage = Path(temporary) / NAME
        populate(stage)
        tar_path = output / (NAME + '-SteamOS-x86_64.tar.gz')
        with tarfile.open(tar_path, 'w:gz') as archive:
            archive.add(stage, arcname=NAME)
        template = (ROOT / 'packaging/self-extract.sh').read_text()
        header = template.replace('@PAYLOAD_LINE@', str(template.count('\n') + 1))
        header = header.replace('@PAYLOAD_SHA256@', digest(tar_path))
        run_path = output / (NAME + '-SteamOS-x86_64.run')
        run_path.write_bytes(header.encode() + tar_path.read_bytes())
        run_path.chmod(0o755)
        (output / 'SHA256SUMS').write_text(''.join(digest(p) + '  ' + p.name + '\n' for p in (run_path, tar_path)))
        print(run_path)
        print(tar_path)


if __name__ == '__main__':
    main()
