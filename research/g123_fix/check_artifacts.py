"""Verify the final thirty-file package, source deltas, and unchanged rows."""
from pathlib import Path
import difflib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,PACKAGE,DAT,file_sha,sha,save

def main():
    sd=PACKAGE/'SD_ROOT';fixed=ROOT/'firmware/package_v36_g120b/SD_ROOT'
    assert {p.name for p in sd.iterdir()}=={p.name for p in fixed.iterdir()}
    assert len(list(sd.iterdir()))==30 and all(p.is_file() for p in sd.iterdir())
    files=[]
    for p in sorted(sd.iterdir()):
        same=p.read_bytes()==(fixed/p.name).read_bytes()
        assert same if p.name!='GXRCE.DAT' else not same,p.name
        files.append(dict(name=p.name,sha256=file_sha(p),bytes=p.stat().st_size,equals_gen120b=same))
    raw=DAT.read_bytes();assert int.from_bytes(raw[28:32],'big')==123
    built=TREE/'candidate/local/full-r13';assert raw==(built/'GXRCE.DAT').read_bytes()
    base=ROOT/'firmware/engine_v43_fix/candidate/local/full-r13'
    assert (built/'effective-rows.bin').read_bytes()==(base/'effective-rows.bin').read_bytes()
    expanded=[]
    for p in sorted((built/'expanded').rglob('*.entry')):
        old=base/'expanded'/p.relative_to(built/'expanded')
        assert p.read_bytes()==old.read_bytes()
        expanded.append(dict(path=str(p.relative_to(built)),sha256=file_sha(p)))
    assert len(expanded)==48
    shadow=Path('candidate/containers/product/src/firmware/engine/panel/panel_ui.c')
    assert (TREE/shadow).read_bytes()==(ROOT/'firmware/engine_v44_keep'/shadow).read_bytes()
    assert 'Shadow' in (TREE/shadow).read_text()
    patches=[]
    for generation,oldtree in ((122,ROOT/'firmware/engine_v44_keep'),(121,ROOT/'firmware/engine_v43_fix')):
        selected={}
        for tree in (oldtree,TREE):
            for p in tree.rglob('*'):
                if not p.is_file():continue
                rel=p.relative_to(tree)
                if 'local' in rel.parts or rel.parts[0]=='native':continue
                if p.suffix in ('.c','.h','.S','.ld','.py','.md') or rel==Path('STATUS.txt'):
                    selected[rel]=True
        diff='';changed=[]
        for rel in sorted(selected):
            before=(oldtree/rel).read_text() if (oldtree/rel).exists() else ''
            after=(TREE/rel).read_text() if (TREE/rel).exists() else ''
            if before==after:continue
            changed.append(str(rel))
            diff+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
                fromfile=f'gen{generation}/'+str(rel),tofile='gen123/'+str(rel)))
        name=f'source-change-vs-g{generation}.patch';(OUT/name).write_text(diff)
        patches.append(dict(baseline=generation,file=name,sha256=file_sha(OUT/name),changed_files=changed))
    card=''.join(file_sha(p)+'  SD_ROOT/'+p.name+'\n' for p in sorted(sd.iterdir()))
    assert (PACKAGE/'CARD_SHA256SUMS').read_text()==card
    runtime=[]
    for name,reference in (
        ('ilaunch3',ROOT/'firmware/image_v36/local/package/SD_ROOT/ilaunch3'),
        ('jlaunch3',ROOT/'artifacts/firmware/gxr-1.51/jlaunch3'),
        ('qlaunch3',ROOT/'artifacts/firmware/gxr-1.51/qlaunch3'),
        ('l08firm3',ROOT/'firmware/package_v36_g117/SD_ROOT/l08firm3')):
        assert (sd/name).read_bytes()==reference.read_bytes()
        runtime.append(dict(file=name,model_input=str(reference.relative_to(ROOT)),sha256=file_sha(reference),equals_packaged_file=True))
    save('evidence/package-check.json',dict(status='PASS',generation=123,dat_sha256=file_sha(DAT),bytes=len(raw),
        runtime_artifacts=runtime,files=files,fixed_files_identical=29,expanded_entries_identical=48,expanded=expanded,
        effective_rows_sha256=file_sha(built/'effective-rows.bin'),resident_build_id=raw[80:112].hex(),
        shadow_source_equals_gen122=True,source_patches=patches,camera_acceptance=False))
    print('PASS package: 30 files, 29 fixed equal, 48 entries equal; two source patches')
if __name__=='__main__':main()
