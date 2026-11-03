#!/usr/bin/python3
"""Compare completed cold results with target bytes and the actual RPC state."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
E=HERE/'evidence'


def read(name):return json.loads((E/(name+'.json')).read_text())
def sha(data):return hashlib.sha256(data).hexdigest()
def u16(data,at):return int.from_bytes(data[at:at+2],'big')
def u32(data,at):return int.from_bytes(data[at:at+4],'big')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    p.add_argument('--recipe')
    p.add_argument('--expect',choices=('apply','bad-crc','cross-unit'),required=True)
    a=p.parse_args()
    main=read(a.name);detail=read(a.name+'-detail');record=read(a.name+'-record')
    assert not main['error'],main['error']
    assert main['first_state5'] and record['native_state_presets']==[]
    assert record['source_events']
    boot=[row for row in detail['calls'] if row['op']==257]
    assert len(boot)==1 and boot[0]['result']==1
    reply=bytes.fromhex(boot[0]['reply'])
    assert int.from_bytes(reply[4:8],'big',signed=True)==0
    assert record['root_state']==3 and record['word']==2
    checks=[row for row in record['gate_events'] if row['label']=='eng_boot_check' and row.get('result')==1]
    assert checks,'The native BOOT qualification did not pass'
    native=detail['final']['rpc_state']
    writes=[row for row in native.get('log',[]) if row['cmd']==22]
    unit=('50mm','28mm','mount').index(a.unit)
    stored=bytes.fromhex(record['record'])
    dat=(ROOT/'firmware/package_v310_g155b_test/GXRCE.DAT').read_bytes()
    assert stored[28:36]==dat[20:28]
    result=dict(name=a.name,unit=a.unit,expect=a.expect,colour_source='declared unit-link RPC state and native S',
        dat_sha256=sha(dat),qualification_passed=True,native_state_presets=[],
        boot_return=boot[0]['return_step'],steps_from_first5=boot[0]['return_step']-main['first_state5']['step'],
        W=sum(row['page']!=0x12c0 for row in writes),T=sum(row['page']==0x12c0 for row in writes),
        S=len(detail['all_boot_settings_writes']))
    if a.expect!='apply':
        assert reply[31]==2 and not writes and detail['all_boot_settings_writes']==[]
        if a.expect=='bad-crc':assert zlib.crc32(stored[:36])!=u32(stored,36)
        else:assert stored[6]!=unit and zlib.crc32(stored[:36])==u32(stored,36)
        result.update(status='PASS',independent_record_gate=True)
    else:
        assert reply[31]==1 and record['target_equal']
        assert a.recipe
        target=(HERE/'local'/f'{a.recipe}-target.bin').read_bytes()
        live=(HERE/'local'/f'{a.name}-live.bin').read_bytes()
        assert len(target)==552 and live==target
        compatibility=read('studio-compatibility')['results'][1]
        assert compatibility['sha256']==sha(dat)
        mapping=bytes.fromhex(compatibility['maps'][unit])
        unit_name=('jlaunch3','qlaunch3','l08firm3')[unit]
        image=(ROOT/'artifacts/firmware/gxr-1.51'/unit_name).read_bytes()
        sections=[struct.unpack_from('>5I',image,32+20*i) for i in range(16)]
        overlay={int(k):v for k,v in native.get('overlay',{}).items()}
        def original(at):
            for offset,base,size,_,_ in sections:
                if base<=at<base+size:return image[512+offset+at-base]
            raise ValueError(hex(at))
        def actual(at):
            aligned=at&~1
            return (overlay[aligned]>>(0 if at&1 else 8))&255 if aligned in overlay else original(at)
        rows=[];owned=set()
        for index in range(9):
            descriptor=mapping[32+12*index:44+12*index]
            address,n,offset=u32(descriptor,0),u16(descriptor,4),u16(descriptor,6)
            row=bytes(actual(address+i) for i in range(n));expected=target[offset:offset+n]
            assert row==expected,(index,address)
            owned.update(range(address,address+n))
            rows.append(dict(index=index,address=hex(address),bytes=n,sha256=sha(row),equal=True))
        for at in overlay:
            for byte in (at,at+1):
                if byte not in owned:assert actual(byte)==original(byte),hex(byte)
        assert native['t']==u16(target,445)
        directory=u32(dat,156);d=directory+64*unit
        kind,number=a.recipe.rsplit('-',1)[-1],0
        source=next(x for x in read('declared-records') if x['name']==a.recipe)
        number=source['number'];kind=source['kind']
        slot=number if kind=='builtin' else compatibility['look_bases'][number-1] if kind=='look' else compatibility['user_bases'][number-1]
        at=u32(dat,d+16)+32+64*(slot-1);row=dat[at:at+64]
        colour=(0x36f,0x370,0x371,0x8ac,0x8ad,0x8ae,0x8af,0x8b0,0x8b1,0x8b2,0x8b3,0x8b4,0x8b5)
        offsets=colour if row[3]==4 else (0x645,0x646) if row[3]==3 else (0x641,0x642,0x644,0x643) if row[3]==6 else ()
        plan={offset:row[36+i] for i,offset in enumerate(offsets)}
        plan.update({0x36e:row[3],0x6dd:((row[49]+128)%256-128)+9,0x6de:((row[50]+128)%256-128)+9})
        S=(HERE/'local'/f'{a.name}-S.bin').read_bytes()
        assert all(S[offset]==value for offset,value in plan.items()),plan
        flags=detail['fixed_word_changes'];dirty=next((i for i,x in enumerate(flags) if x['word']==6),None)
        complete=next((row for row in flags[dirty+1:] if row['word']==2),None) if dirty is not None else None
        result.update(status='PASS',target_bytes=552,cache_sha256=sha(live),target_sha256=sha(target),
            nine_rows=rows,T_value=native['t'],S_plan={hex(k):v for k,v in plan.items()},S_plan_equal=True,
            adjacent_rpc_bytes_unchanged=True,completion_word_event=complete)
    (E/(a.name+'-acceptance.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if a.expect=='apply' and (HERE/'local'/f'{a.name}-session.pkl.z').exists():
        import sys
        sys.path.insert(0,str(HERE))
        from continue_run import run
        try:
            follow=run(a.name,a.name+'-first-menu')
        except Exception as exc:
            follow=dict(status='OPEN',error=dict(type=type(exc).__name__,message=str(exc)),native_state_presets=[])
            (E/(a.name+'-first-menu.json')).write_text(json.dumps(follow,indent=2)+'\n')
        print(json.dumps(dict(menu_status=follow['status'],menu_error=follow['error'])))
        from recovery_reassemble import inspect
        for recovery_name in ('restore-v310-word','restore-v39-word'):
            try:
                recovery=inspect(recovery_name)
                print(json.dumps(dict(recovery_name=recovery_name,readback=recovery)))
            except Exception as exc:
                print(json.dumps(dict(recovery_name=recovery_name,readback_error=str(exc))))


if __name__=='__main__':main()
