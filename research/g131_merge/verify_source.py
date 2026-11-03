"""Check the delivered source against the single permitted behavior change."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'
OLD = ROOT / 'firmware/engine_v49_knobs'
NEW = ROOT / 'firmware/engine_v51_g131'

def files(tree):
    return {str(p.relative_to(tree)): p for p in tree.rglob('*') if p.is_file()
            and 'local' not in p.relative_to(tree).parts and '__pycache__' not in p.relative_to(tree).parts}

def main():
    before, after = files(OLD), files(NEW)
    assert set(after) - set(before) == {'candidate/build131.py'}
    assert set(before) - set(after) == {'candidate/build129.py'}
    changed = sorted(name for name in before.keys() & after.keys()
                     if before[name].read_bytes() != after[name].read_bytes())
    expected = ['candidate/common.py', 'candidate/containers/product/adapter.c',
        'candidate/containers/product/pack.py',
        'candidate/containers/product/src/firmware/card_container_v2/gate.c',
        'candidate/containers/product/src/firmware/engine/core/eng_data.c',
        'candidate/containers/product/ui_v2_data.c', 'candidate/engine_services/engine_services.h',
        'candidate/engine_services/native_seed.c', 'candidate/engine_services/services.c']
    assert changed == sorted(expected)
    same = {name: hashlib.sha256(after[name].read_bytes()).hexdigest()
            for name in before.keys() & after.keys() if name not in changed}
    assert all(name in same for name in after if '/kv2/' in name or name.startswith('resident/'))
    origin_manifest = {line.split(None, 1)[1].strip(): line.split(None, 1)[0]
                       for line in (ROOT / 'research/g130_fix/SHA256SUMS').read_text().splitlines()}
    for name in ('services.c', 'native_seed.c', 'engine_services.h'):
        relative = 'candidate/engine_services/' + name
        origin = ROOT / 'firmware/engine_v50_h07' / relative
        assert hashlib.sha256(origin.read_bytes()).hexdigest() == origin_manifest[str(origin.relative_to(ROOT))]
        assert after[relative].read_bytes() == origin.read_bytes()
    result = dict(status='PASS_STATIC', changed_files=changed,
        renamed_build=['candidate/build129.py', 'candidate/build131.py'],
        unchanged_files=len(same), unchanged_sha256=dict(sorted(same.items())),
        knobs_and_resident_unchanged=True, service_sources_equal_g130=True)
    (WORK / 'evidence/source-scope.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(name='source-scope', returncode=0, counts=dict(
        changed_files=len(changed), renamed_builds=1, unchanged_files=len(same)))))

if __name__ == '__main__':
    main()
