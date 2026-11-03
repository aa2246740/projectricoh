#!/usr/bin/env python3
"""Extract confirmed fixed LUT banks and the conditional nine-level selection.

No pixel-axis assumptions: sample_index is a stored knot number, not a linear
input value. Ordinary selection needs the runtime parameter block at T.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from trace import FW, sections, offset, instructions

def main():
    data=(FW/'jlaunch3').read_bytes();secs=sections(data)
    ins={va:op for va,b,op,p,no,line in instructions()}
    def read(va,n):
        o=offset(va,secs);return data[o:o+n]
    def jump(table,base,key):
        return base+struct.unpack('>h',read(table+key*2,2))[0]
    def retval(va):
        m=re.search(r'ldi r\d+,#(-?\d+)',ins[va]);assert m,(hex(va),ins[va]);return int(m[1])
    raw_order=[7,6,1,2,3,4,5,8,9]
    rows=[]
    for display,raw in enumerate(raw_order,1):
        normal=retval(jump(0x2021efc6,0x20199784,raw-1))
        assert normal==display,(display,raw,normal)
        select_va=jump(0x2012b2d4,0x2010e854,normal-1)
        load_va=select_va+12
        m=re.search(r'lduh r10,@\((\d+),r\d+\)',ins[load_va]);assert m,(hex(load_va),ins[load_va])
        t_offset=int(m[1])
        alternate_id=retval(jump(0x2012b2e6,0x2010e930,normal-1))
        lut_id=retval(jump(0x2012bff4,0x20118410,alternate_id))
        rows.append({'display_level':display,'raw':f'{raw:02x}','normalized':normal,
                     'normal_selector_offset':hex(t_offset),'normal_selector_load_vma':hex(load_va),
                     'conditional_branch':'Q+0x64 == 1 (C+0x24 == 11)',
                     'conditional_enum':alternate_id,'conditional_lut_id':lut_id})
    def write_csv(name,records):
        with (HERE/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    write_csv('level-selection.csv',rows)
    banks={}
    all_records=[];selected=[];raw_tables=[];decoded={}
    for label,base,count,n,fmt in [('stage1',0x2012f40c,22,31,'H'),('stage2',0x2012ff78,22,33,'B'),
                                  ('aux3',0x2013024e,1,33,'B'),('aux4',0x2013026f,1,33,'B')]:
        width=struct.calcsize(fmt);raw=read(base,count*n*width)
        banks[label]={'vma':hex(base),'file_offset':hex(offset(base,secs)),'rows':count,
                      'entries_per_row':n,'format':'u16BE' if width==2 else 'u8',
                      'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        raw_tables.append({'label':label,**banks[label],'hex':raw.hex()})
        records=[]
        decoded[label]={}
        for row in range(1,count+1):
            values=struct.unpack('>'+fmt*n,raw[(row-1)*n*width:row*n*width])
            decoded[label][row]=values
            for idx,value in enumerate(values):
                va=base+((row-1)*n+idx)*width
                rec={'bank':label,'lut_id':row,'sample_index':idx,'value':value,
                     'vma':hex(va),'file_offset':hex(offset(va,secs))}
                records.append(rec);all_records.append(rec)
                if label in ['stage1','stage2']:
                    for level in rows:
                        if level['conditional_lut_id']==row:
                            selected.append({'display_level':level['display_level'],'raw':level['raw'],
                                             'condition':level['conditional_branch'],**rec})
        write_csv(label+'-all.csv',records)
    write_csv('conditional-nine-levels.csv',selected)
    # The 31 internal input knots plus two endpoints align with 33 output
    # samples. This interpretation is an inference; hardware interpolation
    # and the two implicit endpoints have not been observed at runtime.
    paired=[]
    for level in rows:
        row=level['conditional_lut_id']
        xs=[0,*decoded['stage1'][row],4095];ys=decoded['stage2'][row]
        for i,(x,y) in enumerate(zip(xs,ys)):
            paired.append({'display_level':level['display_level'],'raw':level['raw'],
                           'condition':level['conditional_branch'],'lut_id':row,'knot_index':i,
                           'input_candidate':x,'output_u8':y,
                           'input_interpretation':'inferred implicit endpoint' if i in [0,32] else 'inferred input knot, stored u16BE',
                           'interpolation':'unknown hardware rule'})
    write_csv('conditional-nine-paired-candidate.csv',paired)
    (HERE/'table-bytes.json').write_text(json.dumps(raw_tables,indent=2)+'\n')
    descriptors={}
    for label,va,n in [('T_initial_pointer',0x200b2cf0,4),('type26_callback',0x2029c1fc,4),
                       ('type26_descriptor_pointer',0x2029daf4,4),('type26_descriptor',0x2029c65c,32),
                       ('type28_callback',0x2029c204,4),('type28_descriptor_pointer',0x2029dafc,4),
                       ('type32_callback',0x2029c214,4),('type32_descriptor_pointer',0x2029db0c,4),
                       ('stage1_register_map',0x2012bfdc,24),('raw_normalization_jump',0x2021efc6,18),
                       ('contrast_normal_jump',0x2012b2d4,18),('contrast_conditional_jump',0x2012b2e6,18),
                       ('conditional_enum_to_id',0x2012bff4,48)]:
        raw=read(va,n);descriptors[label]={'vma':hex(va),'file_offset':hex(offset(va,secs)),'hex':raw.hex(' ')}
    for kind in [26,28,32]:
        ptr=struct.unpack('>I',read(0x2029da8c+4*kind,4))[0]
        descriptors[f'type{kind}_register_descriptor']={'vma':hex(ptr),
              'file_offset':hex(offset(ptr,secs)),'hex':read(ptr,32).hex(' ')}
    result={'banks':banks,'levels':rows,'descriptors':descriptors,
            'ordinary_nine_levels_resolved':False,
            'conditional_nine_levels_resolved':True,
            'pixel_input_axis_resolved':False,'input_knot_pairing':'strong inference, not silicon specification'}
    (HERE/'tables.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'banks':banks,'conditional_ids':[r['conditional_lut_id'] for r in rows],
                      'descriptors':descriptors},indent=2))

if __name__=='__main__':main()
