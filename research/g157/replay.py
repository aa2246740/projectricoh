"""The field report's exact 48-replay matrix, preserving raw and checksum twins."""
from pathlib import Path
import argparse
import json
import os
import struct
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=('control','model'),default='control');p.add_argument('--tag',default='r1');p.add_argument('--sources',action='store_true');p.add_argument('--prepare-replays',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args()
    C.setup();C.DATASET=a.dataset;prefix=a.tag+'-'+('' if a.dataset=='control' else 'model-')
    directory=C.LOCAL/('persistence-'+a.tag+'-'+a.dataset);directory.mkdir(exist_ok=True)
    cases=(('hcbw',2),('portra',11),('lowsat',14))
    sources=[dict(profile=p,name=n,row=r,close=c,label=prefix+f'session-{p}-{n}-{c}') for p in ('test','release') for n,r in cases for c in ('OK','ADJ')]
    if a.sources:
        queue=[]
        for row in sources:
            label=row['label'];args=['--dataset',C.DATASET,'--version',row['profile'],'--unit','mount','--backend','native','--label',label,'--action','session','--session-row',str(row['row']),'--close-key',row['close']]
            queue.append(dict(label=label,args=args,log=str(C.LOCAL/'logs'/(label+'.log'))))
        C.save(directory/'sources.queue.json',queue)
    if a.prepare_replays:
        queue=[];inputs=[]
        for row in sources:
            src=C.LOCAL/'runs'/row['label'];result=json.loads((src/'result.json').read_text());assert result['status']=='OBSERVED'
            raw=(src/'final-S.bin').read_bytes();assert len(raw)==4096
            checksum=(sum(struct.unpack('>2046H',raw[:4092]))&0xffffffff).to_bytes(4,'big');fixed=raw[:4092]+checksum
            twin=directory/(row['label']+'-checksum-only-S.bin');twin.write_bytes(fixed)
            assert bytes.fromhex(result['after_close']['record'])==raw[0xfd4:0xffc]
            for target in ('test','release'):
                for mode,path in (('raw',src/'final-S.bin'),('checksum',twin)):
                    label=prefix+f"replay-{row['profile']}-{row['name']}-{row['close']}-to-{target}-{mode}"
                    args=['--dataset',C.DATASET,'--version',target,'--unit','mount','--backend','native','--label',label,'--action','menu','--settings',str(path)]
                    if (mode=='checksum' or raw[-4:]==checksum) and row['profile']==target=='test':
                        args+=['--expected',str(src/'final-live-552.bin')]
                    queue.append(dict(label=label,args=args,log=str(C.LOCAL/'logs'/(label+'.log'))))
                    inputs.append(dict(source=row['label'],target=target,mode=mode,label=label,input=str(path.relative_to(C.ROOT)),sha256=C.sha(path.read_bytes()),raw_source_sha256=C.sha(raw),raw_checksum_valid=raw[-4:]==checksum,changed_offsets=[i for i,(x,y) in enumerate(zip(raw,path.read_bytes())) if x!=y],record=raw[0xfd4:0xffc].hex()))
        assert len(queue)==48
        C.save(directory/'replays.queue.json',queue);C.save(directory/'inputs.json',inputs)
    if a.verify:
        rows=json.loads((directory/'inputs.json').read_text());verified=[]
        for row in rows:
            run=C.LOCAL/'runs'/row['label'];doc=json.loads((run/'result.json').read_text())
            assert doc['status']=='OBSERVED' and doc['actual_backend']=='native'
            assert doc['cold_start'] and not doc['snapshots'] and doc['settings_sha256']==row['sha256']
            after=doc.get('list_after_diagnostic',doc['first_menu']);assert after['rows']==8 and after['screen']==0 and after['root_state']==3
            assert after['cached']==after['cursor']==after['physical']+1
            cold=(run/'cold-S.bin').read_bytes();record=bytes.fromhex(row['record'])
            preserved=cold[0xfd4:0xffc]==record
            if row['mode']=='checksum':assert preserved
            # Raw captures with stale stock checksums must not count as valid record recovery.
            if row['mode']=='raw' and not row['raw_checksum_valid']:assert not any(cold[0xfd4:0xffc])
            target_raw=C.artifact(row['target'])['dat'].read_bytes()
            binding_matches=record[28:36]==target_raw[20:28]
            if preserved and binding_matches:
                assert after['memory_result']==1
                if row['target']=='test':
                    assert doc['BOOT_expected_552_equal'] and doc['BOOT_unit_readback']['complete_552_equal']
                    assert doc['after_boot']['boot_committed']==1
            elif not preserved:assert after['memory_result']==2
            else:assert after['memory_result']==3
            if row['target']=='release':assert not doc['after_boot']['boot_committed'] and doc['unit_W']==0
            diag=doc.get('diagnostic_page')
            if row['target']=='release' or doc['after_boot']['memory_result']!=1:
                assert diag and diag['screen']==5 and diag['text'][0].startswith('G157B')
            verified.append(dict(**row,status='PASS',binding_matches=binding_matches,record_preserved=preserved,remembered=after['memory_result'],diagnostic=bool(diag),boot_active=doc['after_boot']['current'],boot_levels=doc['after_boot']['levels']))
        C.save(directory/'verification.json',dict(status='PASS',cases=len(verified),rows=verified,boundary='Full logical S replay into a new MAIN; not real shutdown, NAND flush, unit persistence or LCD scanout.'))
        print(json.dumps(dict(status='PASS',replays=len(verified))))
if __name__=='__main__':main()
