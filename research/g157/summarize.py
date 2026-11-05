"""Summarize only completed evidence whose SHA matches the final artifact."""
from pathlib import Path
import datetime
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def doc(file):
    try:return json.loads(file.read_text())
    except FileNotFoundError:return None
def main():
    C.setup();C.compute_gate('acceptance-summary')
    result=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),datasets={},LCD=dict(status='OPEN',screenshot=None,reason='Neither strict_r4 nor reference models implement video scanout/pixels.'))
    runs=[(f.parent.name,doc(f)) for f in (C.LOCAL/'runs').glob('*/result.json')]
    for dataset in ('control','model'):
        sha={p:json.loads(C.artifact(p,dataset)['manifest'].read_text())['dat_sha256'] for p in ('test','release')}
        directory=C.LOCAL/'acceptance'/dataset
        host=[];service=[];static=doc(directory/'static.json')
        for backend in ('c','python'):
            h=doc(directory/('host-'+backend+'.json'))
            good=bool(h and h['status']=='PASS' and len(h['rows'])==108 and all(r['DAT_sha256']==sha[r['profile']] and r['owned_record']==1 and r['memory_build_literal_equal'] for r in h['rows']))
            host.append(dict(backend=backend,status='PASS' if good else 'PENDING',cases=108 if good else 0))
            for profile in ('test','release'):
                s=doc(directory/f'service-{profile}-{backend}.json')
                good=bool(s and s['status']=='PASS' and s['DAT_sha256']==sha[profile] and len(s['rows'])==54 and all(r['op5']==0 and r['full_40_equal'] and r['S_write_fence'] and len(r['readbacks'])==3 for r in s['rows']) and len(s['decoder'])>=10)
                service.append(dict(profile=profile,backend=backend,status='PASS' if good else 'PENDING',op5=54 if good else 0,readbacks=162 if good else 0,decoder_cases=len(s['decoder']) if good else 0))
        native=[];reference=[];diagnostics=[];boots=[];old_generation=[];explicit=[];invalid_stimulus=[]
        valid=[(name,r) for name,r in runs if r and r.get('dataset')==dataset and r.get('dat_sha256')==sha.get(r.get('version')) and r.get('cold_start') and not r.get('snapshots')]
        for profile in ('test','release'):
            for unit in C.UNITS:
                samples=[(n,r) for n,r in valid if r['unit']==unit and r['version']==profile and r['action']=='sweep' and r.get('actual_backend')=='native' and r['status']=='OBSERVED' and len(r['samples'])==18 and len(r.get('builtin_samples',[]))==8 and len(r.get('user_samples',[]))==3]
                good=bool(samples)
                if good:
                    name,r=samples[-1]
                    good=all(s['full_40_equal'] and s['unit_readback']['complete_552_equal'] for s in r['samples']+r['builtin_samples']+r['user_samples'])
                    good &= r['DISP_card']['screen']==1 and r['DISP_back']['screen']==0 and r['after_close']['state']==5 and r['ADJ_closed']['state']==5
                    good &= bytes.fromhex(r['before_DISP']['record'])==(C.LOCAL/'runs'/name/'final-S.bin').read_bytes()[0xfd4:0xffc]
                native.append(dict(profile=profile,unit=unit,status='PASS' if good else 'PENDING',run=samples[-1][0] if samples else None))
                refs=[n for n,r in valid if r['unit']==unit and r['version']==profile and r.get('actual_backend')=='reference' and r['status']=='OBSERVED' and r['challenge']=='none']
                reference.append(dict(profile=profile,unit=unit,status='PASS' if refs else 'PENDING',runs=refs))
        for name,r in valid:
            if r['status']!='OBSERVED':continue
            if r['challenge']=='boot-vivid' and (r['after_boot'].get('selector')!=2 or r['after_boot'].get('boot_committed') or r.get('first_menu',{}).get('selector')!=2):
                invalid_stimulus.append(dict(run=name,status='NOT_COVERED',reason='Native initialization overwrote the Vivid stimulus before BOOT or before the first menu; not persistent Vivid UI coverage.'))
                continue
            if name.endswith('-old-g156'):
                assert r['after_boot']['memory_result']==3 and not r['after_boot']['boot_committed'] and r['unit_W']==0
                assert r['first_menu']['rows']==8 and r['first_menu']['root_state']==3
                source=C.LOCAL/'boot-fixtures/old-g156-S.bin'
                assert (C.LOCAL/'runs'/name/'cold-S.bin').read_bytes()[0xfd4:0xffc]==source.read_bytes()[0xfd4:0xffc]
                old_generation.append(dict(run=name,profile=r['version'],status='PASS',source_preserved=True,colour_W=0))
            if r.get('explicit_expected_552_equal'):
                assert r['explicit_unit_readback']['complete_552_equal'] and not r['after_boot']['boot_committed']
                assert r['after_close']['levels']==[100,1,0,0,0,0,0,0,0,0]
                assert r['after_close']['record']==r['after_boot']['record']
                explicit.append(dict(run=name,status='PASS',remembered_nondefault_levels=True,explicit_552_equal=True))
            if r.get('BOOT_expected_552_equal'):
                assert r['BOOT_unit_readback']['complete_552_equal'] and r['after_boot']['boot_committed']==1
                boots.append(dict(run=name,status='PASS',unit=r['unit'],backend=r['actual_backend']))
            if r['challenge']!='none' and r.get('diagnostic_page'):
                page=r['diagnostic_page'];d=page['diagnostic'];challenge=r['challenge']
                expected={'boot-activity6':(10,2),'boot-mode4':(11,4),'boot-both':(10,6),'no-dispatch':(1,1),'boot-vivid':(20,128),'boot-wb':(20,128)}.get(challenge)
                if expected and r['action']=='menu':
                    reason,bits=expected;assert d['reason']==reason and d['failed']&bits==bits,(name,d,expected)
                    assert page['memory_result']==1 and page['text'][0].endswith('R03')
                    if challenge=='boot-both':assert d['activity']==6 and d['mode']==4
                    if challenge in ('boot-vivid','boot-wb'):assert not any(t.startswith('>04') for t in r['list_after_diagnostic']['text'])
                    assert r['unit_W']==0
                    diagnostics.append(dict(run=name,status='PASS',reason=reason,failed=d['failed'],backend=r['actual_backend'],text=page['text']))
        tag='r2' if dataset=='model' else 'r1'
        replay=doc(C.LOCAL/('persistence-'+tag+'-'+dataset)/'verification.json')
        audit=[doc(directory/('byte-audit-'+p+'.json')) for p in ('test','release')]
        result['datasets'][dataset]=dict(DAT=sha,static='PASS' if static and static['status']=='PASS' else 'PENDING',host=host,service=service,native=native,reference=reference,diagnostics=diagnostics,BOOT=boots,old_generation=old_generation,explicit_remembered_apply=explicit,invalid_stimulus=invalid_stimulus,S48='PASS' if replay and replay['status']=='PASS' and replay['cases']==48 else 'PENDING',audit=audit)
    result['verdict']='有缺陷'
    C.save(C.LOCAL/'ACCEPTANCE.json',result)
    print(json.dumps(dict(verdict=result['verdict'],datasets={d:dict(native_pass=sum(r['status']=='PASS' for r in v['native']),native_total=6,reference_pass=sum(r['status']=='PASS' for r in v['reference']),S48=v['S48']) for d,v in result['datasets'].items()},LCD='OPEN')))
if __name__=='__main__':main()
