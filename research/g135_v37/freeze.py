"""Freeze (or re-check) SHA-256 of every read-only input of the g135 task."""
from pathlib import Path
import hashlib, json, sys
ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g135_v37'
TREES = ['tools/native_harness', 'firmware/resident_v37', 'firmware/resident_v36',
         'firmware/package_v37_redisplay', 'firmware/package_v36_g120b', 'firmware/package_v36_g127',
         'firmware/package_v36_g129', 'firmware/package_v36_g131',
         'firmware/engine_v48_own', 'firmware/engine_v51_g131', 'firmware/engine_v52_redisplay',
         'firmware/stage2l_switch/tools', 'firmware/kv2_modules/data_ui',
         'research/review_g126', 'research/review_g127', 'research/g122_keep_list',
         'research/g131_merge', 'research/g129_knobs', 'research/redisplay_fix',
         'research/kv2_math/local', 'research/emulator_feasibility_r1/prototype']
FILES = ['research/review_g129/REVIEW.md', 'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
         'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc',
         'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld']
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while c := f.read(1 << 20): h.update(c)
    return h.hexdigest()
def walk():
    out = {}
    for t in TREES:
        base = ROOT / t
        assert base.is_dir(), t
        for p in sorted(base.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and not p.is_symlink():
                out[str(p.relative_to(ROOT))] = None
    for f in FILES: out[f] = None
    return out
if __name__ == '__main__':
    if sys.argv[1:] == ['check']:
        frozen = json.loads((WORK / 'inputs.json').read_text())
        bad = [n for n, d in frozen.items() if not (ROOT / n).is_file() or sha(ROOT / n) != d]
        print(json.dumps({'checked': len(frozen), 'changed': bad})); sys.exit(1 if bad else 0)
    names = walk()
    # outputs of the earlier tasks that may legitimately be re-created are not inputs
    data = {n: sha(ROOT / n) for n in names}
    (WORK / 'inputs.json').write_text(json.dumps(data, indent=0, sort_keys=True) + '\n')
    print(len(data))
