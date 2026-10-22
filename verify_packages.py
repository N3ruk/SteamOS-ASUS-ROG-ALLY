#!/usr/bin/env python3
"""Read-only end-to-end verification of all six ZIP/.run distributions."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
from build import NAMES
from installer.engine import CATALOG

ROOT = Path(__file__).resolve().parent


def main():
    out = ROOT / 'release'
    sums = dict(line.split('  ', 1)[::-1] for line in (out / 'SHA256SUMS').read_text().splitlines())
    if set(sums) != {name + '.zip' for name in NAMES.values()}:
        raise RuntimeError('Se necesitan exactamente seis entradas ZIP en SHA256SUMS.')
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
    print('6/6 paquetes verificados. No se han instalado apps ni modificado hardware/arranque/Bluetooth.')


if __name__ == '__main__':
    main()
