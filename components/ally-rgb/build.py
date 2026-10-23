"""Native Decky ZIP with sources/tests and a positive file list."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parent

def build():
    version=json.loads((ROOT/'package.json').read_text())['version']
    names=['main.py','plugin.json','package.json','package-lock.json','rollup.config.js','tsconfig.json',
           'README.md','LICENSE','THIRD-PARTY.md','VERIFICACION.md','build.py']
    for directory in ('py_modules','src','tests','licenses','dist'):
        names += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/directory).rglob('*'))
                  if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    data={name:(ROOT/name).read_bytes() for name in names}
    for name in names:
        if (ROOT/name).is_symlink(): raise RuntimeError('No se empaquetan enlaces.')
    manifest={name:hashlib.sha256(content).hexdigest() for name,content in sorted(data.items())}
    data['manifest.json']=(json.dumps({'version':version,'sha256':manifest},indent=2)+'\n').encode()
    out=ROOT/'release';out.mkdir(exist_ok=True)
    target=out/f'ALLY-RGB-{version}.zip'
    with zipfile.ZipFile(target,'w') as archive:
        for name,content in sorted(data.items()):
            info=zipfile.ZipInfo('ally-rgb/'+name,date_time=(2026,10,23,0,0,0))
            info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,content)
    checksum=hashlib.sha256(target.read_bytes()).hexdigest()
    (out/'SHA256SUMS').write_text(checksum+'  '+target.name+'\n')
    print(target.name,target.stat().st_size,'bytes; SHA256',checksum)
    return target

if __name__=='__main__':build()
