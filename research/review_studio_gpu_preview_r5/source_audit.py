"""Recreate the production card-read inventory and compare the frozen colour sources."""
import ast
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
SOURCE = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r5/source')
manifest = json.loads((OUT/'source-before.json').read_text())
old = json.loads((OUT.parent/'review_studio_gpu_preview_r4/source-before.json').read_text())
changed = [name for name in old if manifest.get(name) != old[name]]
added = sorted(set(manifest)-set(old))
assert changed == ['src/gxr_studio/api/camdata_routes.py', 'src/gxr_studio/camdata/intake.py', 'tests/test_clone_coverage.py']
assert added == ['tests/test_dat_card_identity.py']
prefixes = ('frontend/', 'src/gxr_studio/gpu/', 'src/gxr_studio/engine/', 'src/gxr_studio/raw/',
            'src/gxr_studio/render/', 'src/gxr_studio/lut/', 'src/gxr_studio/finish/',
            'web/assets/gpu', 'tests/test_gpu_', 'tests/support/gpu_')
colour = {name: digest for name, digest in manifest.items() if name.startswith(prefixes)}
assert all(old[name] == digest for name, digest in colour.items())
(OUT/'colour-source-stability.json').write_text(json.dumps({'unchanged_files': len(colour), 'files': colour, 'all_prior_files_unchanged': len(old)-len(changed), 'changed': changed, 'added': added}, indent=2)+'\n')
calls = []
for p in sorted((SOURCE/'src').rglob('*.py')):
    text = p.read_text()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('open_rb', 'read_dat_from_card', 'read_head'):
            calls.append({'file': str(p.relative_to(SOURCE)), 'line': node.lineno, 'function': node.func.attr,
                          'keywords': {kw.arg: ast.unparse(kw.value) for kw in node.keywords},
                          'expression': ast.get_source_segment(text, node)})
opened = [c for c in calls if c['function'] == 'open_rb']
assert len(opened) == 3 and all('root' in c['keywords'] and 'expect' in c['keywords'] for c in opened)
dat = [c for c in calls if c['function'] == 'read_dat_from_card']
assert len(dat) == 1 and dat[0]['keywords']['expect'] == '(fingerprint.root_dev, fingerprint.root_ino)'
entries = [
 {'read': 'camdata/intake.py:119', 'origin': 'api/camdata_routes.py:163-197', 'identity': 'selected MountSession fingerprint', 'required_keyword': True},
 {'read': 'cards/importer.py:239', 'origin': 'cards/importer.py:370-375,429,517-522', 'identity': 'run.ident.expect fixed before scan'},
 {'read': 'cards/coverage.py:129', 'origin': 'cards/coverage.py:160-184', 'identity': 'ident.expect or root identity fixed before strict scan'},
 {'read': 'cards/discovery.py:141-147', 'origin': 'cards/discovery.py:342-444', 'identity': 'directory descriptors checked during strict scan'},
]
(OUT/'card-read-call-sites.json').write_text(json.dumps({'calls': calls, 'identity_flow': entries, 'content_open_calls': len(opened)}, indent=2)+'\n')
print(json.dumps({'card_content_calls': len(opened), 'colour_sources_unchanged': len(colour), 'prior_files_unchanged': len(old)-len(changed)}))
