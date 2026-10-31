"""Build the native Decky ZIP; never install or publish."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=root/'release')
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    version = json.loads((root/'package.json').read_text())['version']
    target = out/f'Video-Output-ALLY-for-DOCKs-{version}.zip'
    paths = [root/n for n in ('main.py','video_runtime.py','video_selector.py','video_startup.py',
              'display_names.py','settings_store.py','README.md','NOTICE.md','LICENSE','plugin.json','package.json')]
    for directory in ('dist', 'licenses'):
        paths += [p for p in (root/directory).rglob('*') if p.is_file()]
    if not (root/'dist/index.js').is_file():
        raise RuntimeError('Build the frontend first: npm run build')
    files = {}
    for path in sorted(paths):
        if path.is_symlink():
            raise RuntimeError('Unexpected runtime symlink')
        files[path.relative_to(root).as_posix()] = path.read_bytes()
    manifest = {'schema': 1, 'version': version, 'sha256':
                {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['manifest.json'] = (json.dumps(manifest,indent=2)+'\n').encode()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo('output-manager/'+name, date_time=(2026,10,31,0,0,0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    print(json.dumps({'path':str(target), 'sha256':hashlib.sha256(target.read_bytes()).hexdigest(), 'files':len(files)}))


if __name__ == '__main__':
    main()
