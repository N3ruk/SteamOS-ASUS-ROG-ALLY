#!/usr/bin/env python3
"""Read-only end-to-end verification of all seven ZIP/.run distributions."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
from build import NAMES
from installer.engine import CATALOG, PAYLOADS
from installer import rgb_decky

ROOT = Path(__file__).resolve().parent


def verify_embedded_power(extracted, expected, temporary):
    """Check the actual runnable payload, not just the adjacent source copies."""
    if 'ally-power-decky' in expected:
        component = extracted / 'components/ally-power-decky'
        with zipfile.ZipFile(extracted / 'payloads' / PAYLOADS['ally-power-decky']) as archive:
            package = json.loads(archive.read('ally-power-decky/package.json'))
            if package['version'] != CATALOG['ally-power-decky']['version']:
                raise RuntimeError('El ZIP nativo Decky no coincide con la versión del catálogo.')
            for name in ('py_modules/power_backend.py', 'py_modules/manager.py', 'dist/index.js'):
                if archive.read('ally-power-decky/' + name) != (component / name).read_bytes():
                    raise RuntimeError('Payload Decky y fuentes divergen: ' + name)
            if any(Path(name).name == 'cpu-topology.json' for name in archive.namelist()):
                raise RuntimeError('No se debe distribuir la topología CPU de otro equipo.')
    if 'ally-power' in expected:
        destination = temporary / (extracted.name + '-desktop-payload')
        subprocess.run(['/bin/bash', str(extracted / 'payloads' / PAYLOADS['ally-power']),
                        '--extract', str(destination)], check=True, capture_output=True)
        package = destination / 'Ally-Power-1.0.0'
        for name in ('app.py', 'power_backend.py'):
            if (package / 'payload' / name).read_bytes() != (extracted / 'components/ally-power/src' / name).read_bytes():
                raise RuntimeError('Payload escritorio y fuentes divergen: ' + name)
        if (package / 'installer.py').read_bytes() != (extracted / 'components/ally-power/packaging/installer.py').read_bytes():
            raise RuntimeError('El instalador de escritorio incrustado no está actualizado.')
        if list(package.rglob('cpu-topology.json')):
            raise RuntimeError('La topología CPU debe generarse al instalar, nunca empaquetarse.')



def verify_embedded_rgb(extracted, expected):
    if 'ally-rgb' not in expected:
        return
    payload = extracted / 'payloads' / PAYLOADS['ally-rgb']
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    rgb_decky.check_payload(payload, digest, CATALOG['ally-rgb']['version'])
    with zipfile.ZipFile(payload) as archive:
        manifest = json.loads(archive.read('ally-rgb/manifest.json'))
        for name in manifest['sha256']:
            if archive.read('ally-rgb/' + name) != (extracted / 'components/ally-rgb' / name).read_bytes():
                raise RuntimeError('Payload ALLY RGB y fuentes divergen: ' + name)


def main():
    out = ROOT / 'release'
    sums = dict(line.split('  ', 1)[::-1] for line in (out / 'SHA256SUMS').read_text().splitlines())
    if set(sums) != {name + '.zip' for name in NAMES.values()}:
        raise RuntimeError('Se necesitan exactamente siete entradas ZIP en SHA256SUMS.')
    with tempfile.TemporaryDirectory(prefix='suite-artifact-qa-') as temporary:
        temporary = Path(temporary)
        for component, name in NAMES.items():
            zip_path = out / (name + '.zip')
            if hashlib.sha256(zip_path.read_bytes()).hexdigest() != sums[zip_path.name]:
                raise RuntimeError('SHA256 incorrecto: ' + zip_path.name)
            with zipfile.ZipFile(zip_path) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError('ZIP dañado: ' + name)
                for entry in archive.infolist():
                    if not (temporary / entry.filename).resolve().is_relative_to(temporary):
                        raise RuntimeError('Ruta ZIP no segura.')
                archive.extractall(temporary)
            runner = temporary / name / (name + '-SteamOS.run')
            extracted = temporary / (name + '-source')
            subprocess.run(['/bin/bash', str(runner), '--extract', str(extracted)], check=True, capture_output=True)
            subprocess.run(['/usr/bin/python3', str(extracted / 'install.py'), '--verify'], check=True, capture_output=True)
            manifest = json.loads((extracted / 'manifest.json').read_text())
            expected = list(CATALOG) if component == 'central' else [component]
            if manifest['components'] != expected:
                raise RuntimeError('Componentes incorrectos: ' + name)
            verify_embedded_power(extracted, expected, temporary)
            verify_embedded_rgb(extracted, expected)
            for i in expected:
                if not (extracted / 'components' / i).is_dir() or not (extracted / 'docs' / (i + '.md')).is_file():
                    raise RuntimeError('Faltan fuentes/documentación: ' + i)
            if component in ('central', 'ally-power', 'ally-power-decky'):
                vendor_sources = list((extracted / 'components').rglob('*source.tar.gz'))
                if not vendor_sources:
                    raise RuntimeError('Faltan las fuentes correspondientes de RyzenAdj: ' + name)
            # This only invokes original package --check, never installation or device mutation.
            result = subprocess.run(['/bin/bash', str(runner), '--check', '--json'], text=True, capture_output=True, timeout=90)
            if result.returncode not in (0, 1):
                raise RuntimeError(result.stderr)
            report = json.loads(result.stdout)
            if set(report) != set(expected):
                raise RuntimeError('Informe de requisitos incorrecto: ' + name)
            print('OK: ' + zip_path.name + ' — integridad, extracción, fuentes y requisitos sin instalar')
    print('7/7 paquetes verificados. No se han instalado apps ni modificado hardware/arranque/Bluetooth.')


if __name__ == '__main__':
    main()
