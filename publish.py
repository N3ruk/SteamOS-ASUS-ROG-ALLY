#!/usr/bin/env python3
"""Publish the reviewed local checkout. Requires authenticated GitHub CLI.

Visibility is mandatory; no default-public behavior, force pushes or asset clobber.
"""
import argparse
import hashlib
import tempfile
import json
import os
from pathlib import Path
import shutil
import subprocess
from build import NAMES

ROOT = Path(__file__).resolve().parent
REPO = 'SteamOS-ASUS-ROG-ALLY'
TAG = 'v1.0.0'


def run(args, *, check=True, env=None):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--visibility', choices=('public', 'private'), required=True)
    parser.add_argument('--owner', help='Must match the authenticated GitHub login')
    args = parser.parse_args()
    gh = shutil.which('gh')
    if not gh:
        raise RuntimeError('Se necesita GitHub CLI oficial (gh) autenticada; no forma parte del instalador de usuario.')
    run([gh, 'auth', 'status', '--hostname', 'github.com'])
    login = run([gh, 'api', 'user', '--jq', '.login']).stdout.strip()
    if args.owner and args.owner.lower() != login.lower():
        raise RuntimeError('La cuenta autenticada no coincide con el propietario solicitado.')
    owner = args.owner or login
    full = owner + '/' + REPO
    if run(['git', 'status', '--porcelain']).stdout.strip():
        raise RuntimeError('Hay cambios sin commit. Revisa, prueba y confirma antes de publicar.')
    if run(['git', 'branch', '--show-current']).stdout.strip() != 'main':
        raise RuntimeError('La publicación requiere la rama main revisada.')
    subprocess.run(['/usr/bin/python3', 'verify_packages.py'], cwd=ROOT, check=True)
    assets = [ROOT / 'release' / (name + '.zip') for name in NAMES.values()] + [ROOT / 'release/SHA256SUMS']
    existing = run([gh, 'api', 'repos/' + full], check=False)
    if existing.returncode == 0:
        meta = json.loads(existing.stdout)
        expected_private = args.visibility == 'private'
        if meta['private'] != expected_private:
            raise RuntimeError('El repositorio existente tiene otra visibilidad; no se cambia automáticamente.')
    else:
        if '404' not in existing.stderr:
            raise RuntimeError('No se pudo comprobar el repositorio: ' + existing.stderr.strip())
        run([gh, 'repo', 'create', full, '--' + args.visibility,
             '--description', 'Instalador centralizado y seis utilidades independientes para SteamOS y ASUS ROG Ally'])
    url = 'https://github.com/' + full + '.git'
    remote = run(['git', 'remote', 'get-url', 'origin'], check=False)
    if remote.returncode == 0:
        if remote.stdout.strip() not in (url, 'git@github.com:' + full + '.git'):
            raise RuntimeError('origin apunta a otro repositorio; se conserva sin cambios.')
    else:
        run(['git', 'remote', 'add', 'origin', url])
    # Use gh's credential helper only for this command, never modify global git config.
    env = dict(os.environ)
    env['PATH'] = str(Path(gh).parent) + os.pathsep + env.get('PATH', '')
    run(['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
         'push', 'origin', 'main'], env=env)
    previous = run([gh, 'release', 'view', TAG, '--repo', full], check=False)
    if previous.returncode == 0:
        raise RuntimeError('La release ya existe. No se reemplaza ni se sobrescriben sus assets automáticamente.')
    commit = run(['git', 'rev-parse', 'HEAD']).stdout.strip()
    result = run([gh, 'release', 'create', TAG, '--repo', full, '--target', commit,
                  '--title', 'SteamOS ASUS ROG ALLY 1.0.0', '--notes-file', 'docs/RELEASE.md',
                  *map(str, assets)])
    info = json.loads(run([gh, 'release', 'view', TAG, '--repo', full, '--json', 'assets,url']).stdout)
    if {a['name'] for a in info['assets']} != {p.name for p in assets}:
        raise RuntimeError('La release existe pero sus assets no coinciden con los ocho esperados; revisa antes de darla por terminada.')
    with tempfile.TemporaryDirectory(prefix='ally-release-download-') as temporary:
        run([gh, 'release', 'download', TAG, '--repo', full, '--dir', temporary])
        for path in assets:
            downloaded = Path(temporary) / path.name
            if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(downloaded.read_bytes()).digest():
                raise RuntimeError('El asset publicado no coincide con el local: ' + path.name)
    print('Repositorio: https://github.com/' + full)
    print('Release: ' + info['url'])
    print('Verificados: siete ZIP y SHA256SUMS descargados de nuevo y comparados con los locales; sin sobrescribir assets.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr if isinstance(exc.stderr, str) else str(exc)
        else:
            detail = str(exc)
        raise SystemExit(detail)
