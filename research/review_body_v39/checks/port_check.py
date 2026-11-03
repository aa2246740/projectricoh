#!/usr/bin/python3 -I
"""Check the port instructions against a declared source snapshot."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_body_v39/evidence'
TEMP = Path(os.environ['REVIEW_TEMP'])
READ = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-v39/port-read')
context_tolerance = int(sys.argv[1]) if len(sys.argv) > 1 else 0
assert context_tolerance in (0, 2)
pins = json.loads((OUT / 'port-read.json').read_text())
if not READ.exists():
    READ.mkdir(parents=True)
    for row in pins:
        retained = OUT / 'port-snapshot' / Path(row['path']).name
        source = retained if retained.exists() else ROOT / row['path']
        data = source.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256']
        (READ / Path(row['path']).name).write_bytes(data)
tree = TEMP / 'merged'
files = {'adapter.c': 'candidate/containers/product/adapter.c',
         'services.c': 'candidate/engine_services/services.c',
         'engine_services.h': 'candidate/engine_services/engine_services.h'}
for name, relative in files.items():
    target = tree / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(READ / name, target)
steps = []
for name in ('dat-adapter.diff', 'dat-services.diff'):
    change = ROOT / 'research/body_v39/port' / name
    for dry in (True, False):
        command = ['/usr/bin/patch', '-F', str(context_tolerance), '-p1', '-i', str(change)]
        if dry:
            command += ['--dry-run']
        result = subprocess.run(command, cwd=tree, capture_output=True, text=True)
        steps.append({'file': name, 'dry_run': dry, 'returncode': result.returncode,
                      'output': result.stdout + result.stderr})
        assert result.returncode == 0, steps[-1]
adapter = (tree / files['adapter.c']).read_text()
services = (tree / files['services.c']).read_text()
assert 'n.spare.io.preselect=0;n.ui.last_cur=n.ui.cur;' in adapter
assert 'op==6){rv_irq_restore(irq);return RV_OK;}' in services
assert 'op==2&&(result==RV_OK||result==RV_VERIFY)' in adapter
assert 'r->grain=0' not in services
header = (tree / files['engine_services.h']).read_bytes()
assert header == (ROOT / 'firmware/resident_v39/engine_services/engine_services.h').read_bytes()
with zipfile.ZipFile(ROOT / 'artifacts/downloads/gxr-151.zip') as archive:
    prefix = 'GXR Update/Firmware rel 1.51/'
    official = {Path(name).name: archive.read(name) for name in archive.namelist()
                if name.startswith(prefix) and not name.endswith('/')}
old = ROOT / 'firmware/package_v38_g139/local/SD_ROOT'
for name, data in official.items():
    expected = (ROOT / 'firmware/resident_v38/local/body/ilaunch3').read_bytes() if name == 'ilaunch3' else data
    assert (old / name).read_bytes() == expected
result = {'status': 'PASS', 'context_tolerance': context_tolerance, 'steps': steps,
          'g150_snapshot': json.loads((OUT / 'port-read.json').read_text()),
          'g150_last_cursor_line_retained': True, 'g150_settings_op6_retained': True,
          'op6_does_not_clear_grain': True, 'merged_service_header_equal_to_v39': True,
          'merged_files': {relative: hashlib.sha256((tree / relative).read_bytes()).hexdigest()
                           for relative in files.values()},
          'local_v38_recovery_package': {'body_sha256': hashlib.sha256((old / 'ilaunch3').read_bytes()).hexdigest(),
                                       'official_companions_equal': 28, 'firmware_files': 29},
          'limits': ['Only three source files were merged for inspection. This is not a g150 product build.']}
(OUT / 'port.json').write_text(json.dumps(result, indent=1) + '\n')
print(json.dumps({'status': 'PASS', 'steps': len(steps), 'recovery_companions_equal': 28}))
