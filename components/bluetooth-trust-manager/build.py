#!/usr/bin/python3
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
NAME = 'Confianza-Bluetooth-1.0.0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def populate(target):
    target.mkdir(parents=True)
    shutil.copytree(ROOT / 'payload', target / 'payload', ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('installer.py', 'build.py', 'self-extract.sh', 'test_installer.py', 'LEEME.md', 'LICENSE.txt'):
        shutil.copyfile(ROOT / name, target / name)
    files = {str(p.relative_to(target)): sha(p) for p in sorted(target.rglob('*')) if p.is_file()}
    (target / 'manifest.json').write_text(json.dumps({'version': '1.0.0', 'files': files}, indent=2) + '\n')


def main():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='confianza-build-') as temporary:
        stage = Path(temporary) / NAME
        populate(stage)
        archive = output / (NAME + '-SteamOS.tar.gz')
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(stage, arcname=NAME)
        template = (ROOT / 'self-extract.sh').read_text()
        header = template.replace('@LINE@', str(template.count('\n') + 1)).replace('@HASH@', sha(archive))
        executable = output / (NAME + '-SteamOS.run')
        executable.write_bytes(header.encode() + archive.read_bytes())
        executable.chmod(0o755)
        (output / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in (executable, archive)))
        print(executable)


if __name__ == '__main__':
    main()
