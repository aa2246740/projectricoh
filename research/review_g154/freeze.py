"""只核对本轮使用的输入，不重跑实现方 872 项封存清单。"""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def inputs():
    paths = set()
    for tree in ('engine_v62_g153', 'engine_v63_g154'):
        base = ROOT / 'firmware' / tree
        paths.update(p for p in base.rglob('*') if p.is_file() and 'local' not in p.relative_to(base).parts
                     and p.suffix in ('.c', '.h', '.S', '.ld', '.py'))
        paths.add(base / 'candidate/local/full-r13/engine.elf')
    for package in ('package_v39_g153', 'package_v39_g153_test', 'package_v39_g154', 'package_v39_g154_test'):
        paths.update(p for p in (ROOT/'firmware'/package/'local/SD_ROOT').iterdir() if p.is_file())
    for folder in ('research/g154', 'tools/native_harness_c'):
        paths.update(p for p in (ROOT/folder).glob('*.py'))
    for name in ('research/g154/REPORT.md', 'research/g154/OWNER_STEPS.md', 'research/g154/evidence/source.diff',
                 'research/g154/layout.json', 'research/review_g153/REVIEW.md', 'research/g151_design/DESIGN.md',
                 'research/review_fixes_design/REVIEW.md', 'research/pitfalls/CHECKLIST_NEUTRAL.md',
                 'research/v39_g153/local/body/local/resident/build/resident.elf'):
        paths.add(ROOT/name)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    p = argparse.ArgumentParser();p.add_argument('--verify', action='store_true');a=p.parse_args()
    path = HERE/'evidence/inputs-before.json';path.parent.mkdir(exist_ok=True)
    current=inputs()
    if a.verify:
        before=json.loads(path.read_text())
        changed=[name for name in before.keys()|current.keys() if before.get(name)!=current.get(name)]
        result=dict(status='PASS' if not changed else 'FAIL', files=len(current), changed=changed)
        (HERE/'evidence/inputs-after.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result));assert not changed
    else:
        assert not path.exists()
        path.write_text(json.dumps(current,indent=2)+'\n')
        print(json.dumps(dict(status='FROZEN',files=len(current))))


if __name__=='__main__':main()
