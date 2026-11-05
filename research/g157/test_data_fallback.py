"""Use the design's test-data fallback; preserve every slot and requested name."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
C.setup()
stage=C.LOCAL/'stages/rejected-pool-promotion'
if not stage.exists():
    stage.mkdir(parents=True)
    for profile in ('test','release'):
        item=C.artifact(profile,'model')
        shutil.copytree(item['package'],stage/profile/'package')
        shutil.copytree(item['build'],stage/profile/'build')
        shutil.copyfile(item['records'],stage/profile/'records.json')
test_slots,test_looks=R.parse(R.frozen(Path('firmware/package_v310_g156_test/GXRCE.DAT')))
for profile in ('test','release'):
    file=C.artifact(profile,'model')['records'];m=json.loads(file.read_text())
    m.pop('balance_pool_alignment',None)
    if profile=='test':
        unit=m['units'][0]
        replacements=[(next(r for r in unit['looks'] if r['name']=='HNCS HiCon'),test_looks[0]['HNCS HiCon'])]
        replacements += [(next(r for r in unit['builtins'] if r['slot']==s),test_slots[0][s]) for s in (7,8)]
        for entry,raw in replacements:
            digest=C.sha(raw);dest=C.LOCAL/'records'/(digest+'.bin');dest.write_bytes(raw)
            entry.update(file=str(dest.relative_to(C.ROOT)),sha256=digest,source='design-approved test-data capacity fallback')
            if 'name' in entry:entry['exact_identity']=False
        m['tradeoff']='Design test-data capacity fallback: 50mm HNCS HiCon, 07 L-Chr, 08 L-Viv use g156 test data; names/slots, Metropolis and three users retained; official Acros and C040 replacements retained; rejected library 08 excluded'
        m['capacity_fallback']=['50mm HNCS HiCon','50mm 07 L-Chr','50mm 08 L-Viv']
    C.save(file,m);R.read_manifest(file)
print(json.dumps(dict(status='PASS',fallback='test only',slots_changed=0,engine_changes=0)))
