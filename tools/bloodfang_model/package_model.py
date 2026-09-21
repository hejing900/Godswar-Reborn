"""Package a staged authored model and its previews without client mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory',type=Path)
parser.add_argument('--name',default='Bloodfang-vampiric-dragon.zip')
parser.add_argument('--prefix', default='bloodfang-original',
                    help='Basename of authored Blender, GLB and mesh JSON files')
args=parser.parse_args()
root=args.directory.resolve()
if Path(args.name).name!=args.name or not args.name.endswith('.zip'):
    raise ValueError('Provide a plain ZIP filename')
if Path(args.prefix).name != args.prefix:
    raise ValueError('Provide a plain authored model basename')
files=[root/p for p in ('README.md', args.prefix+'.blend', args.prefix+'.glb',
    args.prefix+'.mesh.json', 'model-summary.json','native-x-templates.bin',
    'viewer-validation.json')]
files+=sorted(root.glob('bloodfang-*.png'))
files+=sorted(root.glob('portrait-prompt.txt'))
files+=sorted((root/'native').glob('*'))
files+=sorted((root/'preview').glob('*'))
files+=sorted(p for p in (root/'source').glob('*') if p.is_file())
if any(not p.is_file() for p in files):
    raise ValueError('A required authored deliverable is missing')
manifest=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,
    'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
manifest_path=root/'manifest.json'
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
destination=root/args.name
with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for p in files+[manifest_path]:archive.write(p,p.relative_to(root).as_posix())
with zipfile.ZipFile(destination) as archive:
    if archive.testzip() is not None:raise ValueError('Package CRC failed')
    for row in manifest:
        if hashlib.sha256(archive.read(row['path'])).hexdigest()!=row['sha256']:
            raise ValueError('Package differs from reviewed manifest')
print(json.dumps({'archive':str(destination),'verified_files':len(manifest),
    'bytes':destination.stat().st_size,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}))
