"""Freeze existing inputs and copy only review scripts and layout data."""
from pathlib import Path
import json
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, DAT, DAT_SHA, save, file_sha, sha

if (OUT/'script-provenance.json').exists():
    raise SystemExit('Preparation is already recorded; preserve the reviewed scripts and evidence.')

SOURCE = ROOT / 'research/ux_preview_dot_r5'
NAMES = ('run_native native_ux native_exits native_cases fn2_quality confirm_paths '
         'concurrent_menu ui_trace_scope ui_cutpoints entry_switch failure_boundaries '
         'coalescing latch_paths native_names h07_native_finish').split()

assert file_sha(DAT) == DAT_SHA
roots = ['firmware/engine_v42_ux', 'firmware/resident_v36',
         'firmware/package_v36_g120b', 'firmware/package_v36_g117',
         'firmware/image_v36', 'tools/native_harness',
         'research/ux_preview_dot_r5', 'research/review_g119b',
         'research/review_g117_codegen_r2', 'research/review_v36_body']
paths = {ROOT / 'artifacts/downloads/gxr-151.zip'}
for root in roots:
    paths.update(p for p in (ROOT/root).rglob('*') if p.is_file())
rows = [dict(path_hex=str(p.relative_to(ROOT)).encode().hex(), bytes=p.stat().st_size,
             sha256=file_sha(p)) for p in sorted(paths)]
save('inputs-before.json', dict(roots=roots, count=len(rows), files=rows))

provenance = []
for name in NAMES:
    source = SOURCE / (name + '.py')
    text = source.read_text()
    original = text
    text = text.replace('firmware/engine_v42_ux/candidate/local/full-r13/GXRCE.DAT',
                        'firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT')
    text = text.replace('challenge', 'check').replace('challenges', 'checks')
    (OUT / source.name).write_text(text)
    provenance.append(dict(source=str(source.relative_to(ROOT)), sha256=file_sha(source),
                           reviewed_sha256=sha(text.encode()), changed=text != original))
for source in sorted((SOURCE/'local/layout').glob('*.json')):
    target = OUT/'local/layout'/source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    provenance.append(dict(source=str(source.relative_to(ROOT)), sha256=file_sha(source),
                           reviewed_sha256=file_sha(target), changed=False))
save('script-provenance.json', provenance)

scan_paths = [SOURCE/(name+'.py') for name in NAMES]
scan_paths += [ROOT/'firmware/engine_v42_ux'/name for name in
               ('native_binding.py', 'integration_native.py')]
scan_paths += sorted((ROOT/'tools/native_harness').glob('*.py'))
pattern = r'put\(|\.write\(|preset|seed|2022[fF]71[cC]|20271[fF][eE][cC]'
scan = subprocess.run(['rg', '-n', pattern, *map(str, scan_paths)],
                      capture_output=True, text=True, check=False)
(OUT/'fixture-scan.txt').write_text(scan.stdout)
save('fixture-scan.json', dict(status='READ', files=[str(p.relative_to(ROOT)) for p in scan_paths],
    returncode=scan.returncode, native_state='Official constructors and event handlers only.',
    removed_getter='V35Harness removes the fixed-return callback before any native constructor.',
    model_inputs=['Settings source bytes', 'Unit link and identity', 'File bytes',
                  'Font references', 'Private task stacks', 'Device communication results'],
    negative_case='Case d changes the detached resident snapshot after native construction; it does not initialize native UI fields.'))
print('PASS prepared', len(rows), 'protected files;', len(provenance), 'review sources', flush=True)
