"""Freeze the accepted inputs and copy the generation 127 source tree."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g129_knobs'
ENGINE = ROOT / 'firmware/engine_v49_knobs'
BASE = ROOT / 'firmware/engine_v48_own'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert not ENGINE.exists()
    files = set()
    for folder in ('candidate/containers/product', 'candidate/engine_services', 'resident'):
        for p in (BASE / folder).rglob('*'):
            if p.is_file() and 'local' not in p.parts and '__pycache__' not in p.parts:
                files.add(p)
    files.update(BASE / ('candidate/' + n) for n in
                 ('common.py', 'service_build.py', 'build127.py', 'ui_data.py'))
    frozen = {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}
    for folder in ('research/knobs_v2_engine_design', 'research/kv2_math', 'research/kv2_data_ui'):
        for line in (ROOT / folder / 'SHA256SUMS').read_text().splitlines():
            expected, name = line.split(None, 1)
            p = ROOT / name.strip()
            assert digest(p) == expected, str(p)
            frozen[str(p.relative_to(ROOT))] = expected
    for folder in ('firmware/package_v36_g127/SD_ROOT', 'firmware/package_v36_g120b/SD_ROOT',
                   'tools/native_harness'):
        for p in (ROOT / folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                frozen[str(p.relative_to(ROOT))] = digest(p)
    for p in files:
        q = ENGINE / p.relative_to(BASE)
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
    modules = ENGINE / 'candidate/containers/product/kv2'
    modules.mkdir()
    for family, names in [('math', ('kv_math.c', 'kv_math.h', 'kv_i64.c')),
                          ('data_ui', ('kv_data.c', 'kv_data.h', 'kv_ui.c', 'kv_ui.h'))]:
        for name in names:
            p = ROOT / 'firmware/kv2_modules' / family / name
            frozen[str(p.relative_to(ROOT))] = digest(p)
            shutil.copyfile(p, modules / name)
    (ENGINE / '.gitignore').write_text('local/\n**/local/\n__pycache__/\n')
    (WORK / '.gitignore').write_text('local/\n__pycache__/\n')
    (WORK / 'inputs.json').write_text(json.dumps(frozen, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'frozen_inputs': len(frozen), 'copied_files': len(files)}))

if __name__ == '__main__':
    main()
