#!/usr/bin/python3
"""Independently check retained source bytes and acceptance receipts."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BODY=ROOT/'research/v310_body'
sys.path.insert(0,str(HERE))
from audit import snapshot,memory,file_digest


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    result=dict(status='ERROR',NAND_sources=[],image_lineage=[],colour_entries=[],manifest_checks={})
    target=HERE/'evidence/retained-receipts.json';assert not target.exists()
    try:
        for flow in ('official','v310'):
            source=BODY/'fix/r3/local'/('recovery-fixed-'+flow+'-TAA-20261103-final-state.pkl.z')
            state=snapshot(source)['cpu']
            nand=next(d for t,d in zip(state['device_types'],state['devices']) if t in ('NAND','WordColumnNAND'))
            raw_path=BODY/'fix/r3/local'/('recovery-fixed-'+flow+'-TAA-20261103-nand.json')
            declared={int(k):bytes.fromhex(v) for k,v in json.loads(raw_path.read_text()).items()}
            assert declared=={int(k):bytes(v) for k,v in nand['pages'].items()}
            result['NAND_sources'].append(dict(flow=flow,snapshot_sha256=file_digest(source),
                JSON_sha256=file_digest(raw_path),all_pages_equal=True,pages=len(declared)))
            initial=BODY/'fix/r2/local'/('recovery-fixed-'+flow+'-part1-final-state.pkl.z')
            s=snapshot(initial);cpu=s['cpu'];n=next(d for t,d in zip(cpu['device_types'],cpu['devices']) if t in ('NAND','WordColumnNAND'))
            def u(at):return int.from_bytes(memory(cpu,at,4),'big')
            first=u(0x200c0d54)+35;last=first+u(0x200c0d50)-1;tail=u(0x200c0d60)
            def sector(lba):
                page,part=divmod(lba,4)
                return n['pages'].get(page,b'\xff'*2112)[512*part:512*(part+1)]
            header=sector(last*256+tail);size=int.from_bytes(header[0x168:0x16c],'big')
            actual=header+b''.join(sector(first*256+i) for i in range((size-512+511)//512))[:size-512]
            expected=(ROOT/('artifacts/firmware/gxr-1.51/ilaunch3' if flow=='official' else 'firmware/image_v310/local/ilaunch3')).read_bytes()
            assert actual==expected
            prior=s.get('reference',{});counts=prior.get('counts',{})
            hits={k:v for k,v in counts.items() if k.startswith(('resident ','hook-word ')) and v}
            assert not hits
            prefix=BODY/'fix/r3/local'/('recovery-fixed-'+flow+'-part14-final-state.pkl.z')
            cp=snapshot(prefix)
            hits={k:v for k,v in cp['reference']['counts'].items() if k.startswith(('resident ','hook-word ')) and v}
            assert not hits and cp['cpu']['steps']==7000000000
            result['image_lineage'].append(dict(flow=flow,initial_snapshot_sha256=file_digest(initial),
                initial_step=cpu['steps'],initial_MAIN_sha256=sha(actual),initial_MAIN_equal=True,
                part14_sha256=file_digest(prefix),part14_step=cp['cpu']['steps'],
                retained_prefix_hook_counts=hits,model_corrections=['nand-word','sd-long-response'],
                prefix_scope='Retained formal batch execution; not rerun from cold in this review'))
        provenance=json.loads((BODY/'fix/r3/evidence/declared-T-input.json').read_text())
        original=(ROOT/provenance['source']).read_bytes();declared=(ROOT/provenance['output']).read_bytes()
        assert [(i,a,b) for i,(a,b) in enumerate(zip(original,declared)) if a!=b]==[(0,0xbb,0xaa)]
        final=(HERE/'local/recovered-v310-T.bin').read_bytes()
        limit=int.from_bytes(final[0xf8:0xfa],'big');limit=limit if 0x2aab<=limit<0x4000 else 0x3ffc
        checksum=sum(int.from_bytes(final[i:i+2],'big') for i in range(0,limit,2))&0xffffffff
        assert checksum==int.from_bytes(final[-4:],'big')
        result['T_input']=dict(source_sha256=sha(original),declared_sha256=sha(declared),
            only_change=[0,187,170],input_stored_checksum=int.from_bytes(declared[-4:],'big'),
            final_sha256=sha(final),final_stored_checksum=checksum,
            final_changed_offsets=[i for i,(a,b) in enumerate(zip(declared,final)) if a!=b],
            camera_dump=False,old_checksum_validity_not_required_by_this_commit_path=True)
        maps=json.loads((BODY/'fix/evidence/studio-compatibility.json').read_text())['results'][1]['maps']
        dat=(ROOT/'firmware/package_v310_g155b_test/GXRCE.DAT').read_bytes()
        for number in (2,3):
            source=BODY/'fix/r2/local'/('h52-success-time-key-'+str(number)+'.pkl.z')
            saved=snapshot(source);cpu=saved['cpu'];base=saved['dat_base'];g=saved['symbols']['g']
            target_colour=(BODY/'fix/local/mount-look-target.bin').read_bytes()
            cache=memory(cpu,base+g+1461,552)
            assert cache==target_colour
            peer=next(d for t,d in zip(cpu['device_types'],cpu['devices']) if t=='StartupRegisters')['rpc_state']
            mapping=bytes.fromhex(maps[2]);overlay={int(k):v for k,v in peer['overlay'].items()}
            raw=(ROOT/'artifacts/firmware/gxr-1.51/l08firm3').read_bytes()
            sections=[struct.unpack_from('>5I',raw,32+20*i) for i in range(16)]
            def actual_byte(at):
                aligned=at&~1
                if aligned in overlay:return (overlay[aligned]>>(0 if at&1 else 8))&255
                for pos,lo,n,_,_ in sections:
                    if lo<=at<lo+n:return raw[512+pos+at-lo]
                raise ValueError(hex(at))
            rows=[]
            for i in range(9):
                at,n,offset=struct.unpack_from('>IHH',mapping,32+12*i)
                data=bytes(actual_byte(at+j) for j in range(n))
                assert data==target_colour[offset:offset+n]
                rows.append(dict(index=i,bytes=n,sha256=sha(data),equal=True))
            S=int.from_bytes(memory(cpu,0x200c0dac,4),'big');settings=memory(cpu,S,4096)
            assert (settings[0x36e],settings[0x6dd],settings[0x6de])==(1,9,9)
            assert peer['t']==int.from_bytes(target_colour[445:447],'big')
            assert int.from_bytes(memory(cpu,0x200547ec,4),'big')==2
            result['colour_entries'].append(dict(source_sha256=file_digest(source),step=cpu['steps'],
                raw=int.from_bytes(memory(cpu,cpu['registers']['r4']+12,4),'big'),word=2,
                cache_sha256=sha(cache),target_sha256=sha(target_colour),rows=rows,T_equal=True,S_equal=True))
        c=json.loads((BODY/'fix/r2/evidence/first-menu-check-c.json').read_text())
        p=json.loads((BODY/'fix/r2/evidence/first-menu-check-python.json').read_text())
        assert c['status']==p['status']=='PASS' and c['cases']==p['cases'] and len(c['cases'])==5
        result['menu_receipts']=dict(backends_equal=True,cases=5,rows=[v['rows'] for v in c['cases']],
            scope='Receipt and source-snapshot consistency; ASCII conversion executions retained from implementation')
        frozen=json.loads((HERE/'evidence/inputs-before.json').read_text())['files']
        checked=0;missing=[];different=[]
        for line in (BODY/'SHA256SUMS').read_text().splitlines():
            wanted,name=line.split('  ',1)
            if name not in frozen:missing.append(name);continue
            checked+=1
            if frozen[name]['sha256']!=wanted:different.append(name)
        assert not different
        result['manifest_checks']=dict(checked=checked,outside_initial_review_freeze=missing,mismatches=different)
        result['status']='PASS'
    except BaseException as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        target.write_text(json.dumps(result,indent=2)+'\n')
        counts=result['manifest_checks']
        print(json.dumps(dict(status=result['status'],checked=counts.get('checked',0),
            outside_freeze=len(counts.get('outside_initial_review_freeze',[])),mismatches=counts.get('mismatches',[]))))


if __name__=='__main__':main()
