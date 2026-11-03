"""Copy the frozen gen118 tree and retarget only new-tree build scripts."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
old=ROOT/'firmware/engine_v39_ux'
new=ROOT/'firmware/engine_v40_ux'
assert not new.exists()
assert not any(p.is_symlink() for p in old.rglob('*'))
shutil.copytree(old,new)
for p in new.rglob('*.py'):
    rel=p.relative_to(new)
    if 'local' in rel.parts or rel.parts[0]=='resident':continue
    text=p.read_text()
    text=text.replace('engine_v39_ux','engine_v40_ux')
    p.write_text(text)
src=new/'candidate/build118.py'
text=src.read_text().replace('generation 118','generation 119').replace(',118',',119').replace('generation=118','generation=119')
(new/'candidate/build119.py').write_text(text)
print('COPIED and retargeted',new)
