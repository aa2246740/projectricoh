import hashlib
import json
from pathlib import Path
import sys

MAIN = Path('/Users/wu/.t3/projects/projectricoh')
WT = Path('/Users/wu/.t3/worktrees/projectricoh/t3-cecf5e85')
TREES = [MAIN/'artifacts/firmware/gxr-1.51', WT/'artifacts/firmware/gxr-1.51',
         WT/'artifacts/stage1c-brand-pack', WT/'firmware/recipe_v1', WT/'firmware/recipe_fw']
FILES = [WT/'research/stage1c_brand_pack/REPORT.md', WT/'research/stage1c_brand_pack/SOURCE_CHANGES.patch',
         MAIN/'artifacts/stage1b-candidate/packages/stage1b-16-recipes-012bcd24e77b/candidate/SD_ROOT/ilaunch3',
         MAIN/'firmware/recipe_fw/build/payload.elf']
for root in TREES:
    assert root.is_dir() and not root.is_symlink(), root
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink(), path
        if path.is_file():
            FILES.append(path)
result = {}
for path in sorted(FILES):
    assert not path.is_symlink(), path
    data = path.read_bytes()
    result[str(path)] = {'size':len(data), 'sha256':hashlib.sha256(data).hexdigest()}
target = Path(sys.argv[1])
assert target.parent == Path('/tmp/gxr_stage1c_review')
target.write_text(json.dumps(result, indent=2)+'\n')
print(f'{len(result)} files hashed to {target}')
for path in [MAIN/'artifacts/firmware/gxr-1.51/ilaunch3',
             WT/'artifacts/stage1c-brand-pack/pack-b-v2/firmware/candidate/SD_ROOT/ilaunch3',
             WT/'firmware/recipe_fw/build/payload.bin']:
    print(path, result[str(path)])
if len(sys.argv)>2:
    before = json.loads(Path(sys.argv[2]).read_text())
    changed = [p for p in sorted(set(result)|set(before)) if result.get(p)!=before.get(p)]
    print('changed:', changed)
    assert not changed
