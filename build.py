#!/usr/bin/env python3
"""Build six self-contained ZIPs, each with a checksummed offline .run and sources.

Uses only Python stdlib. Third-party binary inputs remain pinned by manifest.
"""
import gzip
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import zipfile
from installer.engine import CATALOG, PAYLOADS

ROOT = Path(__file__).resolve().parent
VERSION = '1.0.0'
EPOCH = 1792627200  # Fixed release date, 2026-10-22 UTC.
NAMES = {
    'central': 'SteamOS-ASUS-ROG-ALLY-' + VERSION,
    'return-gaming': 'Volver-al-Modo-Gaming-1.0.0',
    'default-mode': 'Alternar-Arranque-SteamOS-1.0.0',
    'ally-power': 'Ally-Power-Escritorio-1.0.0',
    'ally-power-decky': 'Ally-Power-Decky-1.1.0',
    'bluetooth-trust-manager': 'Confianza-Bluetooth-1.0.0',
}
EXCLUDED = {'.git', '__pycache__', 'node_modules', '.reference', 'backups', 'release'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def collect(ids, central):
    files = {}
    for name in ('install.py', 'Instalar.sh', 'LICENSE', 'THIRD-PARTY.md', 'README.md'):
        files[name] = (ROOT / name).read_bytes()
    for path in sorted((ROOT / 'installer').glob('*.py')):
        files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for component in ids:
        directory = ROOT / 'components' / component
        for path in sorted(directory.rglob('*')):
            rel = path.relative_to(directory)
            if any(part in EXCLUDED for part in rel.parts) or path.suffix == '.pyc' or (component != 'ally-power-decky' and 'dist' in rel.parts):
                continue
            if path.is_symlink():
                raise RuntimeError('No se empaquetan enlaces: ' + str(path))
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
        doc = 'docs/' + component + '.md'
        files[doc] = (ROOT / doc).read_bytes()
        if component in PAYLOADS:
            rel = 'payloads/' + PAYLOADS[component]
            files[rel] = (ROOT / rel).read_bytes()
    for name in ('INSTALLATION.md', 'BUILD.md', 'VERIFICATION.md'):
        files['docs/' + name] = (ROOT / 'docs' / name).read_bytes()
    if central:
        files['build.py'] = (ROOT / 'build.py').read_bytes()
        files['publish.py'] = (ROOT / 'publish.py').read_bytes()
        files['verify_packages.py'] = (ROOT / 'verify_packages.py').read_bytes()
        files['self-extract.sh'] = (ROOT / 'self-extract.sh').read_bytes()
        for path in sorted((ROOT / 'tests').glob('*.py')):
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    if not central:
        item = CATALOG[ids[0]]
        files['README.md'] = ('# ' + item['name'] + ' ' + item['version'] + '\n\n' + item['description'] + '\n\n' + item['requirements'] + '\n\n[Documentación](docs/' + ids[0] + '.md) · [Instalación](docs/INSTALLATION.md) · [Fuentes y build](docs/BUILD.md)\n').encode()
    if central:
        files['docs/RELEASE.md'] = (ROOT / 'docs/RELEASE.md').read_bytes()
    files['payloads/SHA256SUMS'] = ''.join(digest(files['payloads/' + PAYLOADS[i]]) + '  ' + PAYLOADS[i] + '\n' for i in ids if i in PAYLOADS).encode()
    manifest = {'schema': 1, 'version': VERSION, 'components': ids,
                'sha256': {name: digest(data) for name, data in sorted(files.items())}}
    files['manifest.json'] = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode()
    return files


def mode(name):
    return 0o755 if name.endswith(('.sh', '.run')) or name.endswith('/bin/ryzenadj') else 0o644


def runner(files, folder):
    stream = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=EPOCH) as gz:
        with tarfile.open(fileobj=gz, mode='w') as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(folder + '/' + name)
                info.size = len(data)
                info.mode, info.mtime = mode(name), EPOCH
                archive.addfile(info, io.BytesIO(data))
    payload = stream.getvalue()
    template = (ROOT / 'self-extract.sh').read_text()
    header = (template.replace('@PAYLOAD_LINE@', str(template.count('\n') + 1))
              .replace('@PAYLOAD_SHA256@', digest(payload)).replace('@FOLDER@', folder))
    return header.encode() + payload


def zip_add(archive, name, data, permissions=0o644):
    info = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | permissions) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+', choices=list(NAMES),
                        help='Reconstruir solo estas piezas y conservar los demás ZIP existentes.')
    selected = parser.parse_args().only
    for line in (ROOT / 'payloads/SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        if Path(name).name != name or digest((ROOT / 'payloads' / name).read_bytes()) != expected:
            raise RuntimeError('Entrada binaria alterada: ' + name)
    out = ROOT / 'release'
    out.mkdir(exist_ok=True)
    products = []
    for component, folder in NAMES.items():
        if selected and component not in selected:
            continue
        central = component == 'central'
        ids = list(CATALOG) if central else [component]
        files = collect(ids, central)
        executable = runner(files, folder)
        if central:
            # Allow source checkout preflight without building an installed app.
            (ROOT / 'manifest.json').write_bytes(files['manifest.json'])
        title = 'Instalador centralizado' if central else CATALOG[component]['name']
        guide = ('# ' + title + '\n\n'
                 '1. Extrae este ZIP completo en modo escritorio.\n'
                 '2. En Propiedades → Permisos, marca el archivo `.run` como ejecutable si fuera necesario.\n'
                 '3. Ejecuta `' + folder + '-SteamOS.run` sin sudo y selecciona lo que quieras instalar.\n\n'
                 'No instala nada al extraer. Todo el código, documentación y licencias están dentro del .run.\n'
                 'Para leerlos sin instalar: `bash ' + folder + '-SteamOS.run --extract fuentes`\n\n'
                 'Comprobar sin instalar: `bash ' + folder + '-SteamOS.run --check`\n'
                 'El ZIP individual contiene únicamente este componente; el central contiene los cinco.\n\n' +
                 ('' if central else CATALOG[component]['description'] + '\n\n' + CATALOG[component]['requirements'] + '\n'))
        path = out / (folder + '.zip')
        with zipfile.ZipFile(path, 'w') as archive:
            zip_add(archive, folder + '/' + folder + '-SteamOS.run', executable, 0o755)
            zip_add(archive, folder + '/LEEME.md', guide.encode())
            zip_add(archive, folder + '/LICENSE', (ROOT / 'LICENSE').read_bytes())
            zip_add(archive, folder + '/THIRD-PARTY.md', (ROOT / 'THIRD-PARTY.md').read_bytes())
        products.append(path)
        print(path.name + ': ' + str(path.stat().st_size) + ' bytes')
    products = [out / (folder + '.zip') for folder in NAMES.values()]
    (out / 'SHA256SUMS').write_text(''.join(digest(p.read_bytes()) + '  ' + p.name + '\n' for p in products))


if __name__ == '__main__':
    main()
