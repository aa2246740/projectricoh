"""Freeze product files and verify the same receipt at the end. No product writes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, ROOT, file_info, save

p = argparse.ArgumentParser()
p.add_argument('--verify', action='store_true')
a = p.parse_args()
baseline = HERE/'evidence/inputs-before.json'
if not a.verify:
    assert not baseline.exists()
    files = set()
    for folder in ('firmware/engine_v67_g155c', 'firmware/package_v310_g155c',
                   'firmware/package_v310_g155c_test', 'firmware/image_v310',
                   'firmware/resident_v310_g155'):
        files.update(path for path in (ROOT/folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    for folder in ('tools/native_harness_c', 'tools/gxr_emulator_standby',
                   'firmware/engine_v66_g155b', 'firmware/engine_v63_g154'):
        files.update(path for path in (ROOT/folder).rglob('*') if path.is_file() and
                     not set(('local', '__pycache__')) & set(path.relative_to(ROOT/folder).parts))
    files.update((ROOT/'research/tweak_memory_r1').glob('*.py'))
    files.update((ROOT/'research/tweak_memory_r1/emulator').glob('*.py'))
    for name in ('.gitignore', 'README.md', 'decisions.tsv', 'docs/HANDOFF.md',
                 'research/tweak_memory_r1/REPORT.md', 'research/review_v310_body_r1/REVIEW.md',
                 'research/review_v310_body_r1/evidence/inputs-before.json',
                 'research/v310_resident/ABI.md', 'tools/native_harness_c/local/ccore/build.json',
                 'tools/gxr_emulator_standby/build/libgxr_m32r.dylib'):
        files.add(ROOT/name)
    build=json.loads((ROOT/'tools/native_harness_c/local/ccore/build.json').read_text())
    files.add(Path(build['library']))
    rows = [file_info(path) for path in sorted(files)]
    status = subprocess.check_output(['git','status','--porcelain=v1','-uno'], cwd=ROOT, text=True)
    save('inputs-before', dict(status='FROZEN', files=rows, total_bytes=sum(r['bytes'] for r in rows),
                              git_status=status, nice=15, max_compute_processes=2))
else:
    before=json.loads(baseline.read_text())
    mismatches=[]
    for row in before['files']:
        path=ROOT/row['path']
        if not path.exists() or file_info(path)!=row:
            mismatches.append(row['path'])
    status=subprocess.check_output(['git','status','--porcelain=v1','-uno'], cwd=ROOT, text=True)
    save('inputs-after', dict(status='PASS' if not mismatches and status==before['git_status'] else 'FAIL',
                             checked_files=len(before['files']), mismatches=mismatches,
                             git_status_same=status==before['git_status'], git_status=status))
    assert not mismatches and status==before['git_status']
