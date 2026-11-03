"""Read-only delta inventory, final-byte checks, and retained receipt checks."""
from pathlib import Path
import argparse
import difflib
import hashlib
import importlib.util
import json
import struct
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/review_g153'
sha = lambda b: hashlib.sha256(b).hexdigest()

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def snapshot():
    paths = set()
    for engine in ('engine_v60_g152', 'engine_v62_g153'):
        base = ROOT / 'firmware' / engine
        for tail in ('candidate/containers/product', 'candidate/engine_services', 'resident'):
            paths.update(p for p in (base / tail).rglob('*') if p.is_file() and
                         not any(x in p.parts for x in ('local', '__pycache__', 'build')))
    for name in ('package_v39_g153', 'package_v39_g153_test', 'package_v39_body_only',
                 'package_v39_g151', 'package_v38_g152_test'):
        paths.update(p for p in (ROOT / 'firmware' / name / 'local/SD_ROOT').glob('*') if p.is_file())
    for directory in ('research/v39_g153', 'research/review_body_v39/checks'):
        paths.update((ROOT / directory).glob('*.py'))
    for name in ('research/v39_g153/FLASH.md', 'research/body_v39/FLASH.md',
                 'research/pitfalls/CHECKLIST_NEUTRAL.md', 'research/looks_g152/review_fix/engine-change.diff',
                 'firmware/engine_v62_g153/candidate/local/full-r13/engine.elf',
                 'firmware/resident_v39/local/resident/build/resident.elf',
                 'research/v39_g153/local/body/local/resident/build/resident.elf'):
        paths.add(ROOT / name)
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(paths)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--finish', action='store_true')
    args = parser.parse_args()
    if args.finish:
        before = json.loads((OUT / 'results/inputs-before.json').read_text())
        after = snapshot()
        changes = {p: [before.get(p), after.get(p)] for p in before.keys() | after.keys()
                   if before.get(p) != after.get(p)}
        result = dict(status='PASS' if not changes else 'FAIL', files=len(after), changes=changes)
        (OUT / 'results/inputs-after.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        assert not changes
        return
    tick = time.monotonic()
    (OUT / 'results/inputs-before.json').write_text(json.dumps(snapshot(), indent=2) + '\n')
    old = ROOT / 'firmware/engine_v60_g152'
    new = ROOT / 'firmware/engine_v62_g153'
    changed, diffs = [], []
    for tail in ('candidate/containers/product', 'candidate/engine_services', 'resident'):
        files = lambda base: {p.relative_to(base / tail) for p in (base / tail).rglob('*')
                              if p.is_file() and not any(x in p.parts for x in ('local', '__pycache__', 'build'))}
        left, right = files(old), files(new)
        for name in sorted(left | right):
            a = (old / tail / name).read_bytes() if name in left else b''
            b = (new / tail / name).read_bytes() if name in right else b''
            if a == b:
                continue
            changed.append(dict(path=str(Path(tail) / name), old=sha(a), new=sha(b)))
            try:
                diffs.extend(difflib.unified_diff(a.decode().splitlines(True), b.decode().splitlines(True),
                             fromfile='g152/' + str(Path(tail)/name), tofile='g153/' + str(Path(tail)/name)))
            except UnicodeDecodeError:
                diffs.append('Binary difference: ' + str(Path(tail)/name) + '\n')
    (OUT / 'results/engine-delta.diff').write_text(''.join(diffs))
    core = 'candidate/containers/product/src/firmware/engine/core/eng_core.c'
    assert (old / core).read_bytes() == (new / core).read_bytes()
    assert sha((new / core).read_bytes()) == 'c62ca5337493c3ce974a30e8e7ca4b8bc68d593a0b965d1600dcc0fdeee7482d'
    sys.path.insert(0, str(ROOT / 'research/review_body_v39/checks'))
    gate = load('review_identity_compare', ROOT / 'research/review_body_v39/checks/identity_compare.py')
    elf = ROOT / 'research/v39_g153/local/body/local/resident/build/resident.elf'
    body = ROOT / 'firmware/package_v39_g153_test/local/SD_ROOT/ilaunch3'
    identities = []
    c0 = ROOT / 'research/body_v39/local/c0/ilaunch3'
    # The original reviewed resident is retained by the body review.
    candidates = [p for p in (ROOT / 'research/body_v39/local/c0').rglob('resident.elf')
                  if not p.is_symlink()]
    c0_elf = next((p for p in candidates if sha(p.read_bytes()) ==
                   'bb1fd856181937d32f6eed0bcacfc38b462af14ef2273bd0a9988fe52c9b743b'), None)
    assert c0_elf
    identities.append(dict(reference='c0', **gate.compare(c0_elf, elf, c0, body)))
    identities.append(dict(reference='g151', **gate.compare(
        ROOT / 'firmware/resident_v39/local/resident/build/resident.elf', elf,
        ROOT / 'firmware/package_v39_g151/local/SD_ROOT/ilaunch3', body)))
    S = load('review_dat_format', ROOT / 'research/v39_g153/dat_format.py')
    E = load('review_elf', ROOT / 'research/review_body_v39/checks/static_check.py')
    engine = E.Elf(ROOT / 'firmware/engine_v62_g153/candidate/local/full-r13/engine.elf')
    package_rows = []
    with zipfile.ZipFile(ROOT / 'artifacts/downloads/gxr-151.zip') as archive:
        official = {Path(n).name: archive.read(n) for n in archive.namelist()
                    if n.startswith('GXR Update/Firmware rel 1.51/') and not n.endswith('/')}
    assert len(official) == 29
    old_dat = (ROOT / 'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    for name, expected_sha in (
        ('package_v39_g153_test', '5afc388902c9931d55c831e5afc27684d032193c9775e77a8509e9098e65ba7b'),
        ('package_v39_g153', 'e6dab16235dd6fad870c6c6f4935a078351de10334e2145cc94e940598b7083b')):
        base = ROOT / 'firmware' / name / 'local/SD_ROOT'
        raw = (base / 'GXRCE.DAT').read_bytes()
        assert sha(raw) == expected_sha
        assert sha((base/'ilaunch3').read_bytes()) == '8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
        sections = S.sections(raw)
        fx = S.strict_effects(raw)
        assert fx['count'] == 10
        for n in official:
            if n != 'ilaunch3':
                assert (base/n).read_bytes() == official[n], n
        at, count = sections[0]
        assert raw[at:at+count] == engine.sections['.engine']['data']
        bss = engine.sections['.bss']['bytes']
        request = 7628 + S.align4(len(raw)+bss)
        assert request == 107072 <= 107612
        assert len(raw) == 90164 <= 98304
        matches = []
        for u in range(3):
            for index in (0, 2, 9):
                actual, previous = S.expand_effect(raw,index), S.expand_effect(old_dat,index)
                assert actual == previous
                matches.append(dict(unit=u, effect=index+1, bytes=len(actual), sha256=sha(actual)))
        stock = [S.expand(raw,u,4) for u in range(3)]
        assert stock[2] != stock[0] and stock[2] == S.expand(old_dat,2,4)
        package_rows.append(dict(name=name, sha256=sha(raw), bytes=len(raw), code=count,
                                 bss=bss, request=request, effects=fx, looks_matches=matches,
                                 companions_equal=28, stock_04_sha256=[sha(x) for x in stock]))
    result = dict(status='PASS', changed_files=changed, core_exact=True,
                  core_sha256=sha((new/core).read_bytes()), identities=identities,
                  c0_elf_found=bool(c0_elf), packages=package_rows,
                  official_zip_sha256=sha((ROOT/'artifacts/downloads/gxr-151.zip').read_bytes()),
                  seconds=time.monotonic()-tick)
    (OUT / 'results/static.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status='PASS', changed_files=[x['path'] for x in changed],
                         identities=identities, c0_elf_found=bool(c0_elf), seconds=result['seconds'])))

if __name__ == '__main__':
    main()
