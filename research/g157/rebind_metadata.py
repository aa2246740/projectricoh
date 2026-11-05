"""Correct inherited Acros annotations; prove the final DAT bytes stay identical."""
from pathlib import Path
import json
import copy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import build as B
import records as R
C.setup();C.compute_gate('Acros-metadata-binding');C.DATASET='model'
stage=C.LOCAL/'stages/before-Acros-metadata-label';stage.mkdir(exist_ok=True)
handoff=json.loads((C.LOCAL/'inputs/research/film_looks_r2/local/acros_official_handoff.json').read_text())
if (C.LOCAL/'metadata-rebind.json').exists() and not (stage/'quant-label-proof.json').exists():C.save(stage/'quant-label-proof.json',json.loads((C.LOCAL/'metadata-rebind.json').read_text()))
rows=[]
for profile in ('test','release'):
    a=C.artifact(profile,'model');before=a['dat'].read_bytes();manifest=json.loads(a['records'].read_text())
    old_sha=C.sha(a['records'].read_bytes())
    if not (stage/(profile+'-records.json')).exists():
        C.save(stage/(profile+'-records.json'),manifest)
        C.save(stage/(profile+'-MANIFEST'),json.loads(a['manifest'].read_text()))
    for unit,name in zip(manifest['units'],('a12-50','a12-28','mount-a12')):
        dep=next(r for r in handoff['profiles'] if r['unit']==name)['base_dependencies'][profile]
        row=next(r for r in unit['looks'] if r['name']=='Acros')
        row['quantization_passes']=128
        row['requires']=dict(builtins={'3':dep['base03_sha256'],'5':dep['slot05_sha256']},looks={'Tri-X 400':dep['compatible_TriX_sha256']})
    C.save(a['records'],manifest);B.package(profile,a['records'],reuse=True)
    assert a['dat'].read_bytes()==before
    rows.append(dict(profile=profile,old_manifest_sha256=old_sha,new_manifest_sha256=C.sha(a['records'].read_bytes()),DAT_sha256=C.sha(before),DAT_byte_changes=0))
manifest=json.loads(C.artifact('test','model')['records'].read_text());negatives=[]
for key in ('03','05','Tri-X'):
    bad=copy.deepcopy(manifest);unit=bad['units'][2]
    if key in ('03','05'):
        slot=int(key);source=next(r for r in bad['units'][1]['builtins'] if r['slot']==slot)
        target=next(r for r in unit['builtins'] if r['slot']==slot)
    else:
        source=next(r for r in json.loads((C.LOCAL/'records.json').read_text())['units'][1]['looks'] if r['name']=='Tri-X 400')
        target=next(r for r in unit['looks'] if r['name']=='Tri-X 400')
    target.update(file=source['file'],sha256=source['sha256'])
    fixture=C.LOCAL/'tmp'/('wrong-dependency-'+key+'.json');C.save(fixture,bad)
    try:R.read_manifest(fixture)
    except AssertionError as error:
        assert str(error).startswith('dependency:'),str(error)
        negatives.append(dict(case=key,status='PASS',same_flags_wrong_dependency_rejected=True))
    else:raise AssertionError('dependency accepted: '+key)
for script,args in (('static.py',['--dataset','control']),('static.py',['--dataset','model']),('audit.py',[]),('publish.py',[])):
    C.run([sys.executable,'-I','-B',C.HERE/script,*args],'metadata-'+script[:-3])
C.save(C.LOCAL/'metadata-rebind.json',dict(status='PASS',reason='Official Acros uses its handoff 128/128 annotation and exact 03/05/Tri-X dependency guards.',rows=rows,negative_dependency_cases=negatives))
print(json.dumps(dict(status='PASS',DAT_byte_changes=0)))
