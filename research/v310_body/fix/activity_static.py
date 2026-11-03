#!/usr/bin/python3
"""Resolve native activity dispatch tables from the frozen body bytes."""
import hashlib
import json
from pathlib import Path
import re
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    path=ROOT/'firmware/image_v310/local/ilaunch3';raw=path.read_bytes()
    sections=[struct.unpack_from('>5I',raw,32+20*i) for i in range(16)]
    def memory(at,n):
        for offset,base,size,_,_ in sections:
            if base<=at and at+n<=base+size:
                return raw[512+offset+at-base:512+offset+at-base+n]
        raise ValueError(hex(at))
    source=ROOT/'research/tooling_m32r/disasm/ilaunch3-sec09-load-2025d800.disasm.txt'
    instructions={}
    for line in source.read_text().splitlines():
        match=re.match(r'^([0-9a-f]{8}):\s+[0-9a-f ]+\t(.*)$',line)
        if match:instructions[int(match[1],16)]=match[2]
    def jump(at,base,index):return base+struct.unpack('>h',memory(at+2*index,2))[0]
    conversion=[]
    for config in range(1,22):
        arm=jump(0x2037738c,0x202ba12c,config-1)
        instruction=instructions.get(arm,'')
        value=re.search(r'ldi r1,#([0-9]+)',instruction)
        conversion.append(dict(config=config,arm=hex(arm),activity=int(value[1]) if value else None))
    targets=[jump(0x20377434,0x202ba72c,i) for i in range(22)]
    limits=sorted(set(targets)|{0x202ba9e8})
    dispatch=[]
    for activity,arm in enumerate(targets,1):
        end=next((x for x in limits if x>arm),arm+4)
        r0=None;calls=[]
        for at,ins in instructions.items():
            if not arm<=at<end:continue
            high=re.search(r'seth r0,#0x([0-9a-f]+)',ins)
            low=re.search(r'or3 r0,r0,#0x([0-9a-f]+)',ins)
            if high:r0=int(high[1],16)<<16
            if low and r0 is not None:r0|=int(low[1],16)
            if 'jl r0' in ins:
                calls.append(dict(at=hex(at),callee=hex(r0) if r0 is not None else None))
                r0=None
        dispatch.append(dict(activity=activity,arm=hex(arm),calls=calls,
            meaning='Image Settings' if activity==8 else 'native UI function; identified by dispatch arm and callees'))
    references=json.loads((ROOT/'research/boot_early_sources_r1/references/globals.json').read_text())
    writers=[]
    for row in references:
        if row.get('address')!='0x205d9bf8' or row['kind']!='写':continue
        item={key:value for key,value in row.items() if key not in ('bytes','value')}
        item['linear_reference_hint']=row['value']
        if row['pc'] in ('0x202ba174','0x202ba23c','0x202ba300','0x202ba3c4'):
            item['possible_activity_from_ADJ_conversion']=sorted({x['activity'] for x in conversion if x['activity'] is not None})
            item['linear_hint_is_not_a_unique_value']=True
        writers.append(item)
    assert dispatch[7]['arm']=='0x202ba764' and dispatch[7]['calls'][0]['callee']=='0x20287080'
    assert conversion[2]['activity']==8
    result=dict(address='0x205d9bf8',body_sha256=hashlib.sha256(raw).hexdigest(),
        meaning='Current native UI function, separate from the main state at 0x205d9c00',
        idle=dict(value=0,bulk_clear_writer='0x20055068',runtime_evidence='activity-*-activity.json'),
        ADJ_configuration_conversion=conversion,open_dispatch=dispatch,direct_writes=writers,
        cautions=['Shared stores have multiple incoming constants; a linear last constant is not their unique value',
                  'The reference map does not prove absence of indirect or bulk writes',
                  'Physical camera first-state-5 activity remains unmeasured'])
    (HERE/'evidence/activity-static.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(direct_writers=len(writers),activities=len(dispatch),image_activity=8,idle_activity=0)))


if __name__=='__main__':main()
