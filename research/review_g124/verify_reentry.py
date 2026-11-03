"""Validate the 210 independent native re-entry records and all 35 H07 witnesses."""
from pathlib import Path
import argparse
import json
import hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
PIN='ebf07faa3c5b8dcec411da7f7217fb58488adafb942045999bd2cdf7ce98f803'
p=argparse.ArgumentParser();p.add_argument('--unit',default='50mm');args=p.parse_args()
folder=OUT/'local'/('reentry-all-keys-final' if args.unit=='50mm' else 'reentry-all-keys')
views=('L1','card','items','value','groups','entries','ERR')
cuts=('entry','bind','after_restore','before_redraw','row_draw');keys=('UP','DOWN','DISP','OK','ADJ','HALF')
records=[];half=0
for view in views:
    for cut in cuts:
        for key in keys:
            path=folder/(args.unit+'-'+view+'-'+cut+'-'+key+'.json')
            r=json.loads(path.read_text());n=r['nested']
            assert r['status']=='PASS' and r['dat_sha256']==PIN
            assert n['rows']==8 and n['psw']&0x40
            assert not n['Image_setters'] and not n['Image_mode_stores'] and n['extra_RPC']==0
            assert not r['native_UI']['host_ui_writes'] and not r['native_UI']['getter_callback_present']
            assert not any(r['file_mutations'].values())
            if key=='HALF':
                assert any(x.get('hook')==7 and x.get('inflight')==1 for x in n['resident_hooks'])
                assert all(x['offset']!=0x36e for x in n['S_changes']);half+=1
            else:assert not n['S_changes']
            records.append(dict(view=view,cut=cut,key=key,file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
result=dict(status='PASS',unit=args.unit,dat_sha256=PIN,actual_cases=len(records),raw_half_H07_witnesses=half,
    Image_setter_calls=0,Image_mode_stores=0,native_hand_seed_writes=0,records=records,
    scope='Five explicit IRQ-enabled cuts per view. Numeric outer event is DISP; transaction-bearing movement is a separate inherited arrow matrix.')
(OUT/('evidence/reentry-verified-'+args.unit+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print('PASS',args.unit,len(records),'actual cases,',half,'raw H07 witnesses; no Image setter or mode store')
