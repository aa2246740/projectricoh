"""Freeze the g156-record control and prepare profile-specific C040 manifests."""
from pathlib import Path
import argparse
import copy
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
def control():
    for profile,package in C.PACKAGES.items():
        dest=C.artifact(profile,'control');dest['package'].mkdir(parents=True,exist_ok=True)
        (dest['package']/'SD_ROOT').mkdir(exist_ok=True)
        raw=(package/'local/GXRCE.DAT').read_bytes();manifest=json.loads((package/'MANIFEST').read_text())
        assert C.sha(raw)==manifest['dat_sha256']
        (dest['dat']).write_bytes(raw);C.save(dest['manifest'],dict(manifest,dataset='control'))
        old=C.ENGINE/'candidate/local'/('boot-on' if profile=='test' else 'boot-off')
        shutil.copytree(old,dest['build'],dirs_exist_ok=True)
    C.save(C.LOCAL/'control-freeze.json',dict(profiles={p:json.loads(C.artifact(p,'control')['manifest'].read_text()) for p in C.PACKAGES},source_C={str(p.relative_to(C.ENGINE)):C.sha(p.read_bytes()) for p in C.ENGINE.rglob('*') if p.is_file() and p.suffix in ('.c','.h','.S','.ld') and 'local' not in p.relative_to(C.ENGINE).parts}))
def model():
    source=C.ROOT/'research/model_c040_r1';handoff=json.loads((source/'local/g157_handoff.json').read_text())
    control=json.loads((C.LOCAL/'records.json').read_text())
    base_slots,base_looks=R.parse(R.frozen(Path(control['base'])))
    names={'a12-50':0,'a12-28':1,'mount-a12':2}
    frozen=[]
    files=[source/'REPORT.md',source/'local/g157_handoff.json',source/'local/verification.json',source/'local/final-seal.json']
    files += [Path(r['record_file']) for r in handoff['candidates']]
    files += [Path(r) for r in handoff['layout_manifests'].values()]
    for p in files:
        raw=p.read_bytes();rel=p.relative_to(C.ROOT);target=C.LOCAL/'inputs'/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        frozen.append(dict(path=str(rel),sha256=C.sha(raw),bytes=len(raw)))
    for profile in ('release','test'):
        manifest=copy.deepcopy(control);manifest.update(dataset='model',profile=profile)
        # Retain the approved hybrid's three other 50mm release improvements.
        # Reject the four superseded library candidates as a group. 08 returns to g156.
        for row in manifest['units'][1]['builtins']:
            if row['slot'] in (1,6,8):
                raw=base_slots[1][row['slot']];path=C.LOCAL/'records'/(C.sha(raw)+'.bin');path.write_bytes(raw)
                row.update(file=str(path.relative_to(C.ROOT)),sha256=C.sha(raw),source='g156 baseline; superseded library candidate removed')
        for row in manifest['units'][1]['looks']:
            if row['name']=='HNCS LowSat':
                raw=base_looks[1][row['name']];path=C.LOCAL/'records'/(C.sha(raw)+'.bin');path.write_bytes(raw)
                row.update(file=str(path.relative_to(C.ROOT)),sha256=C.sha(raw),source='g156 baseline; superseded library candidate removed',exact_identity=False)
        chosen=[r for r in handoff['candidates'] if profile=='test' or r['release_robust_candidate']]
        assert len(chosen)==(13 if profile=='test' else 5)
        for r in chosen:
            assert r['fits_unified_safe_profile'] and (profile=='test' or r['quantization_passes']==128)
            u=names[r['unit']];raw=Path(r['record_file']).read_bytes();assert C.sha(raw)==r['record_sha256'] and len(raw)==552
            name=r['name'];kind='builtins' if name[:2].isdigit() else 'looks'
            row=next(x for x in manifest['units'][u][kind] if (x['slot']==int(name[:2]) if kind=='builtins' else x['name']==name))
            target=C.LOCAL/'records'/(C.sha(raw)+'.bin');target.write_bytes(raw)
            row.update(file=str(target.relative_to(C.ROOT)),sha256=C.sha(raw),source='model_c040_r1 frozen reference-exact handoff',quantization_passes=r['quantization_passes'])
            if kind=='looks':row['exact_identity']=True
        manifest.update(changed_model_records=len(chosen),model_handoff_sha256=C.sha((source/'local/g157_handoff.json').read_bytes()),
            tradeoff=control['tradeoff']+'; 08 L-Viv uses g156 baseline, rejected library candidate removed; model robust 5 for release / nominal 13 for test')
        C.save(C.artifact(profile,'model')['records'],manifest)
        R.read_manifest(C.artifact(profile,'model')['records'])
    C.save(C.LOCAL/'model-inputs.json',dict(files=frozen))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('control','model'));a=p.parse_args();C.setup()
    if a.action=='control':control()
    else:C.compute_gate('model-manifests');model()
