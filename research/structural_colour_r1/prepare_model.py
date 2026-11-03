"""Copy the previous study's model and frozen data into this task, without refitting."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as r
import shutil

SOURCE = r.ROOT / 'research/look_ceiling_r1'
INDICES = list(range(27)) + list(range(43,51))
manifest = []

def copy(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        assert destination.read_bytes()==source.read_bytes(),destination
    else:
        shutil.copyfile(source,destination)
    manifest.append(dict(source=str(source.relative_to(r.ROOT)),source_sha256=r.sha(source),
        copy=str(destination.relative_to(r.HERE)),copy_sha256=r.sha(destination)))

code = r.HERE / 'model_copy'
code.mkdir(exist_ok=True)
for name in ('ceiling_model.py','two_pass.py','run.py','quality.py'):
    copy(SOURCE/name,code/name)
source=SOURCE/'runtime.py'
text=source.read_text()
replacements={
    "HERE = Path(__file__).resolve().parent":"HERE = Path(__file__).resolve().parents[1]",
    "/Volumes/Workspace/Scratch/tmp/projectricoh/look-ceiling-r1":"/Volumes/Workspace/Scratch/tmp/projectricoh/structural-colour-r1",
    "['diskutil', 'info'":"['/usr/sbin/diskutil', 'info'",
}
for a,b in replacements.items():
    assert text.count(a)==1,(a,text.count(a))
    text=text.replace(a,b)
(code/'runtime.py').write_text(text)
manifest.append(dict(source=str(source.relative_to(r.ROOT)),source_sha256=r.sha(source),
    copy='model_copy/runtime.py',copy_sha256=r.sha(code/'runtime.py'),path_only_replacements=replacements))
for name in ('hardware_constants.json','studio_source_snapshot.tar.gz'):
    copy(SOURCE/'local'/name,r.LOCAL/name)
files=set()
for index in INDICES:
    for suffix in ('json','npz'):
        files.add(Path(f'target_{index:02d}.{suffix}'))
    meta=r.json.loads((SOURCE/'local'/f'target_{index:02d}.json').read_text())
    for group in ('train','a12-50','mount-a12'):
        files.add(Path(meta.get('group_files',{}).get(group,'samples_'+group+'.npz')))
    for axis in ('Y','C'):
        files.add(Path('fits')/f'{index:02d}'/('L4_'+axis+'_post_add_after_Rbefore_fullfields.json'))
        directory='two_pass_full' + ('_C' if axis=='C' else '')
        for level in (1,4):
            files.add(Path(directory)/f'{index:02d}'/('body_L'+str(level)+'.json'))
for rel in sorted(files):
    copy(SOURCE/'local'/rel,r.LOCAL/rel)
r.dump(r.LOCAL/'model-copy-manifest.json',dict(indices=INDICES,files=manifest,
    purpose='Re-evaluate frozen integer models only. No new hardware pixel equation or optimization.'))
r.finish('prepare_model')
print('Copied',len(manifest),'model/data inputs for 27 Looks and eight MOUNT built-ins.')
