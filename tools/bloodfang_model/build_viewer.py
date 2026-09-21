"""Create an offline preview of the authored model, including skeletal animation."""
import argparse
import base64
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('model', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
document = json.loads(args.model.read_text(encoding='utf-8'))
if 'texture' in document:
    texture = (args.model.parent / document['texture']['path']).resolve()
    if not texture.is_relative_to(args.model.parent.resolve()):
        raise ValueError('Authored texture must be alongside the model')
    document['texture']['data_url'] = 'data:image/png;base64,' + base64.b64encode(texture.read_bytes()).decode('ascii')
args.output.mkdir(parents=True, exist_ok=True)
source = Path(__file__).resolve().parent
for file in ('viewer.html', 'viewer.css', 'viewer.js'):
    shutil.copyfile(source / file, args.output / file)
# Script data works under file:// without a server or cross-origin file fetch.
payload = 'window.BLOODFANG_MODEL=' + json.dumps(document, separators=(',', ':')) + ';\n'
(args.output / 'viewer-data.js').write_text(payload, encoding='utf-8')
print(json.dumps({'viewer': str(args.output / 'viewer.html'), 'network_dependencies': 0,
                  'triangles': len(document['triangles']), 'animations': len(document['actions'])}))
