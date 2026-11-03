#!/usr/bin/env python3
"""Emit hypothetical byte tables and checksum arithmetic, never firmware."""
import bisect
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import sys
sys.dont_write_bytecode = True

spec=importlib.util.spec_from_file_location('drill',Path(__file__).with_name('inspect.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def interp(x, xs, ys):
    if x<=xs[0]:return ys[0]
    if x>=xs[-1]:return ys[-1]
    i=bisect.bisect_right(xs,x)-1
    return ys[i]+(ys[i+1]-ys[i])*(x-xs[i])/(xs[i+1]-xs[i])


def main():
    b=(m.FW/'jlaunch3').read_bytes()
    assert m.sha(b)=='951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'
    refpath=m.ROOT/'research/color_calibration/reference_analysis.json'
    reference=refpath.read_bytes()
    ref=json.loads(reference)['relative_mappings']['ricoh_gr3_positive']
    xs=[0.0]+ref['tone_input_encoded_luma']+[1.0]
    ys=[0.0]+ref['tone_output_encoded_luma']+[1.0]
    assert all(x<y for x,y in zip(xs,xs[1:]))
    assert all(x<=y for x,y in zip(ys,ys[1:]))
    aoff=m.offset(b,0x2012F40C);boff=m.offset(b,0x2012FF78)
    original=list(b[boff:boff+33]);inputs=list(struct.unpack_from('>31H',b,aoff))
    options={
        'a_square_dark':[(v*v+127)//255 for v in original],
        'b_gr3_positive_relative':[math.floor(255*interp(v/255,xs,ys)+0.5) for v in original],
    }
    c0=m.u32(b,0x16c);source=m.u32(b,0x20)
    payload=b[0x200:]
    assert sum(sum(payload[k::6])*((source+k)%6+2) for k in range(6))&0xFFFFFFFF==c0
    results=[]
    for name,new in options.items():
        assert len(new)==33 and new[0]==0 and new[-1]==255
        assert all(0<=v<=255 for v in new)
        assert all(x<=y for x,y in zip(new,new[1:]))
        delta=sum((v-original[k])*(((source+boff+k-0x200)%6)+2) for k,v in enumerate(new))
        checksum=(c0+delta)&0xFFFFFFFF
        # Independent whole-payload recomputation using sparse overrides. No
        # modified bytes object, image, or package is created or saved.
        overrides={boff+k:v for k,v in enumerate(new)}
        sparse_total=sum(overrides.get(i,b[i])*(((source+i-0x200)%6)+2)
                         for i in range(0x200,len(b)))&0xFFFFFFFF
        assert sparse_total==checksum
        patch=[dict(file=hex(boff+k),vma=hex(0x2012FF78+k),old=f'{old:02X}',new=f'{v:02X}',
                    weight=((source+boff+k-0x200)%6)+2,changed=old!=v)
               for k,(old,v) in enumerate(zip(original,new))]
        chdr=struct.pack('>I',checksum)
        header=[dict(file=hex(0x16c+k),old=f'{b[0x16c+k]:02X}',new=f'{v:02X}')
                for k,v in enumerate(chdr)]
        results.append(dict(option=name,status='BLOCKED conditional proposal; no firmware produced',
            row_1_based=1,input_file_range=[hex(aoff),hex(aoff+62)],
            output_file_range=[hex(boff),hex(boff+33)],
            old_output_hex=bytes(original).hex(' ').upper(),
            proposed_output_hex=bytes(new).hex(' ').upper(),
            old_output=original,proposed_output=new,
            original_checksum=f'0x{c0:08X}',delta=delta,new_checksum=f'0x{checksum:08X}',
            changed_payload_bytes=sum(p['changed'] for p in patch),
            changed_header_bytes=sum(p['old']!=p['new'] for p in header),
            byte_table=patch,checksum_header_bytes=header))
    m.save('curve-proposals.json',dict(
        official_sha256=m.sha(b),input_nodes_unchanged=inputs,
        mapping='node-wise composition on existing B; no assumption that type26 input is encoded luma',
        reference_path=str(refpath.relative_to(m.ROOT)),reference_sha256=m.sha(reference),
        relative_mapping=ref,anchored_x=xs,anchored_y=ys,options=results))
    out=io.StringIO();w=csv.writer(out,delimiter='\t',lineterminator='\n')
    w.writerow(['node_0_based','file_offset','VMA','hypothesized_x_12bit','old_hex','a_hex','b_hex','a_decimal','b_decimal','weight'])
    for k in range(33):
        node_x=0 if k==0 else 4095 if k==32 else inputs[k-1]
        w.writerow([k,f'0x{boff+k:06X}',f'0x{0x2012FF78+k:08X}',node_x,f'{original[k]:02X}',
                    f'{options["a_square_dark"][k]:02X}',f'{options["b_gr3_positive_relative"][k]:02X}',
                    options['a_square_dark'][k],options['b_gr3_positive_relative'][k],
                    ((source+boff+k-0x200)%6)+2])
    m.write(m.OUT/'byte-table.tsv',out.getvalue())
    allrows=[]
    for row in range(22):
        a=list(struct.unpack_from('>31H',b,aoff+row*62));bb=list(b[boff+row*33:boff+(row+1)*33])
        allrows.append(dict(row_1_based=row+1,A_vma=hex(0x2012F40C+row*62),A_file=hex(aoff+row*62),A=a,
                            B_vma=hex(0x2012FF78+row*33),B_file=hex(boff+row*33),B=bb))
    prior=json.loads((m.ROOT/'research/isp_pipeline/decoded_tables.json').read_text())
    for k,row in enumerate(allrows):
        assert row['A']==prior['type26']['input_rows'][k]['values']
        assert row['B']==prior['type26']['output_rows'][k]['values']
    cd=[]
    for va in (0x2013024E,0x2013026F):
        off=m.offset(b,va);v=list(b[off:off+33]);assert v==[0]*33
        cd.append(dict(vma=hex(va),file=hex(off),values=v,sha256=m.sha(bytes(v))))
    row23=m.offset(b,0x20130290)+2*62
    assert list(struct.unpack_from('>31H',b,row23))==list(range(128,4096,128))
    colour=m.offset(b,0x2012C5D4)
    colour_rows=[dict(row_1_based=k+1,file=hex(colour+96*k),vma=hex(0x2012C5D4+96*k),
                      sha256=m.sha(b[colour+96*k:colour+96*(k+1)])) for k in range(29)]
    m.save('table-census.json',dict(type26=allrows,auxiliary_unchanged=cd,
        colour_rows_unchanged=colour_rows,
        type23_input_row2=prior['type23']['input_rows'][2],
        type23_initial_output_banks=[list(struct.unpack_from('>33H',b,m.offset(b,0x20143118)+0x44+k*0x44)) for k in range(3)],
        decoded_tables_crosscheck='22 A rows +22 B rows match ISP pipeline JSON'))
    for r in results:
        print(r['option'],r['proposed_output_hex'],r['new_checksum'],r['delta'],r['changed_payload_bytes'])


if __name__=='__main__':main()
