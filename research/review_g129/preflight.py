"""Freeze the candidate and check the supplied file list."""
from pathlib import Path
import hashlib
import json
import subprocess
import datetime

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    names = set()
    for folder in ('firmware/engine_v49_knobs', 'firmware/engine_v48_own',
                   'firmware/package_v36_g129/local/SD_ROOT'):
        base = ROOT / folder
        for path in base.rglob('*'):
            if path.is_file() and ('local' not in path.relative_to(base).parts or 'SD_ROOT' in folder):
                names.add(str(path.relative_to(ROOT)))
    for folder in ('research/g129_knobs', 'research/kv2_math', 'research/kv2_data_ui',
                   'research/knobs_v2_engine_design', 'research/heap_headroom'):
        for path in (ROOT/folder).glob('*'):
            if path.is_file(): names.add(str(path.relative_to(ROOT)))
    for name in ('firmware/package_v36_g127/SD_ROOT/GXRCE.DAT',
                 'firmware/engine_v49_knobs/candidate/local/full-r13/engine.elf',
                 'firmware/engine_v49_knobs/candidate/local/full-r13/GXRCE.DAT',
                 'firmware/kv2_modules/data_ui/local/gxkv2r2.bin',
                 'research/kv2_math/local/parity_cases.bin',
                 'research/kv2_math/local/extended_cases.bin',
                 'research/review_g127/REGRESSIONS.md', 'research/review_g127/plan.json',
                 'research/review_g127/REVIEW.md', 'research/review_g127/history122.json',
                 'research/g127_fix/run_existing.py'):
        names.add(name)
    frozen = {name: {'sha256': digest(ROOT/name), 'bytes': (ROOT/name).stat().st_size}
              for name in sorted(names)}
    checks=[]
    for line in (ROOT/'research/g129_knobs/SHA256SUMS').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        path = ROOT/name.lstrip('*')
        checks.append(path.is_file() and digest(path)==expected)
    dat=ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT'
    assert digest(dat)=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
    assert dat.stat().st_size==89308 and len(checks)==372 and all(checks)
    target=WORK/'inputs.json'
    if target.exists():assert json.loads(target.read_text())==frozen,'frozen input list changed'
    else:target.write_text(json.dumps(frozen,indent=2)+'\n')
    result={'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'frozen_files':len(frozen),'supplied_checks':len(checks), 'dat_sha256':digest(dat),
            'dat_bytes':dat.stat().st_size,'write_scope':str(WORK)}
    (WORK/'preflight.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
