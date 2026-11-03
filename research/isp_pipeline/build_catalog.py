#!/usr/bin/env python3
"""Decode register-write shapes and retain byte-checked evidence, without target execution."""
import csv
import json
import re
import runpy
import struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
M=runpy.run_path(str(HERE/'analyze.py'))
im=M['Image']()
save=M['save']
inventory=json.loads((HERE/'hardware_types.json').read_text())
writers=sorted({int(r['writer'],16) for r in inventory})
catalog=[]
for row in inventory:
    kind=row['type']; start=int(row['writer'],16)
    end=next((x for x in writers if x>start),0x20257DE4)
    descriptor=int(row['descriptor'],16)
    actions=[]
    if start==0x20256988:
        actions=[('G',None,start)]
    elif kind==38:
        actions=[('L',64,0x20257DC0)]*3
    else:
        for a,v in sorted(im.lines.items()):
            if start<=a<end:
                if 'or3 r0,r0,#0x69a0' in v[3]: actions.append(('G',None,a))
                q=re.search(r'cmpui r\d+,#(\d+)',v[3])
                if q: actions.append(('L',int(q[1]),a))
        if kind==13:
            actions=[('G',None,0x20256B9C)]+[('L',128,0x20256BDC)]*8
        if kind==14:
            actions=[('G',None,0x20256C38)]+[('L',486,0x20256C78)]*4
    index=0; groups=[]; words=[]
    for action,n,pc in actions:
        if action=='G':
            regs=[]
            while im.u32(descriptor+index*4):
                address=im.u32(descriptor+index*4)
                assert address>=0xF0000000, (kind,hex(address))
                regs.append(address); index+=1
            groups.append({'kind':'null_terminated_address_list','count':len(regs),
                           'addresses':[f'0x{x:08X}' for x in regs], 'evidence_vma':f'0x{pc:X}'})
            words.extend(regs)
        else:
            base=im.u32(descriptor+index*4)
            assert base>=0xF0000000,(kind,index,hex(base))
            regs=[base+j*4 for j in range(n)]
            groups.append({'kind':'contiguous_u32_loop','base':f'0x{base:08X}','count':n,
                           'last':f'0x{regs[-1]:08X}','evidence_vma':f'0x{pc:X}'})
            words.extend(regs)
        index+=1
    row.update({'evidence_level':'静态确认: descriptor and writer loop shape; semantic names are separate',
                'payload_u32_count':len(words),'write_groups':groups,
                'payload_registers':[f'0x{x:08X}' for x in words]})
    controls={8:[('0xF0311027','u8',[1,0])],13:[('0xF0320007','u8',[0,1])],
              14:[('0xF0322007','u8',[1,0])],16:[('0xF032C003','u8',[0])],
              17:[('0xF032A00F','u8',[1,0])],29:[('0xF0350004','u32',[65536,0])],
              38:[('0xF023404C','u32',[1,0])]}
    row['non_payload_control_writes']=[{'register':a,'width':w,'values_in_order':v}
                                       for a,w,v in controls.get(kind,[])]
    catalog.append(row)
    if start!=0x20256988:
        im.window(start,end,f'writer-{start:08x}')
save('register_layouts.json',catalog)
with (HERE/'register_payloads.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['type','payload_word','register','writer'])
    for r in catalog:
        for i,a in enumerate(r['payload_registers']):w.writerow([r['type'],i,a,r['writer']])

windows=[
    (0x20111FD0,0x20112098,'type7-wrapper-packer'),
    (0x20111C84,0x20111E24,'type8-config'),
    (0x20112988,0x20112AB4,'type13-wrapper'),
    (0x20112AB4,0x20113024,'type13-config'),
    (0x20113024,0x201130E8,'type12-wrapper'),
    (0x201135E8,0x201136D0,'type15-wrapper'),
    (0x20125918,0x20125A34,'isp-global-control'),
    (0x201080B8,0x201084B0,'lens-shading-packer'),
    (0x20196378,0x20196408,'lens-shading-still-caller'),
    (0x20118468,0x20118788,'type26-packer'),
    (0x201188B4,0x20119528,'type27-packer-full'),
    (0x201195A4,0x20119EAC,'type23-packers-full'),
    (0x2011396C,0x20113FB4,'sector-adjuster'),
    (0x20114FB8,0x20115638,'type28-packer-full'),
    (0x2010D9FC,0x2010E528,'type28-config-full'),
    (0x2010EC98,0x2010ECC4,'cross-curve-enum'),
    (0x2010E544,0x2010EBEC,'tone-selectors-full'),
    (0x20195004,0x20195114,'still-scene-dispatch'),
    (0x201961EC,0x20196300,'still-grain-caller'),
    (0x2018DC40,0x2018DCF0,'glut-still-caller-a'),
    (0x2018E4F0,0x2018E580,'glut-still-caller-b'),
    (0x20121074,0x201211C0,'image-request-wrapper'),
    (0x2011C63C,0x2011C7DC,'still-image-processor'),
    (0x201A9DA0,0x201A9EC0,'monitor-isp-caller'),
    (0x201A9EC0,0x201A9F80,'monitor-isp-continuation'),
    (0x201859D0,0x20185A20,'still-main-isp-caller'),
    (0x201857F0,0x20185824,'still-main-isp-caller-34'),
    (0x20186250,0x201862EC,'still-buffer-operations'),
    (0x2019B110,0x2019B19C,'full-size-getter-default'),
    (0x201159D8,0x20115B30,'hue-delta-table-selector'),
    (0x20197F68,0x201981D8,'shoot-command-parser'),
    (0x20199760,0x20199810,'parameter-normalizer'),
    (0x201999C8,0x20199E10,'q-configuration-builder'),
    (0x20199F60,0x2019A00C,'q-scene-overrides'),
    (0x201AB80C,0x201ABBD0,'unit-command-dispatch'),
]
for a,b,name in windows: im.window(a,b,name)
save('catalog_windows.json',[{'start':hex(a),'end_exclusive':hex(b),'name':n} for a,b,n in windows])

matrix_base=0x2012D0C0
matrices=[]
for i in range(8):
    a=matrix_base+i*28
    values=struct.unpack('>14H',im.read(a,28))
    coeff=[-(x&0x7FF) if x&0x800 else x for x in values[:9]]
    matrices.append({'row_1_based':i+1,'vma':hex(a),'file_offset':hex(im.offset(a)),
                     'raw_u16':list(values),'candidate_3x3_Q10_sign_magnitude_bit11':[x/1024 for x in coeff],
                     'row_sums_raw':list(map(sum,(coeff[0:3],coeff[3:6],coeff[6:9]))),
                     'format_evidence_level':'推断: numeric match to standard conversion; no chip register specification'})
save('matrix_candidates.json',matrices)

defaults=json.loads((HERE/'parameter_defaults.json').read_text())
param=lambda a,n:bytes(defaults['bytes'][f'0x{k:04X}'] for k in range(a,a+n))
sector={'evidence_level':'静态确认: source bytes; sector geometry is unknown',
        'd0_sources':[{'vma':hex(a),'file_offset':hex(im.offset(a)),
                       'values_s8':list(struct.unpack('>24b',im.read(a,24)))}
                      for a in (0x2012D362,0x2012D302,0x2012D28A,0x2012D22A)],
        'd1_sources':[{'T_offset':hex(a),'values_s8':list(struct.unpack('>24b',param(a,24)))}
                      for a in (0xF60,0xF78,0xF90,0xFA8)],
        'k_sources':[{'T_offset':hex(a),'values_u8':list(param(a,24))}
                     for a in (0xF00,0xF18,0xF30,0xF48)],
        'masks':[{'T_offset':hex(0x129C+i*4),'u32':int.from_bytes(param(0x129C+i*4,4),'big')}
                 for i in range(5)]}
old=json.loads((M['ROOT']/'research/color_calibration/firmware_parameters.json').read_text())
avg=lambda a,b:[int((x+y)/2) for x,y in zip(a,b)]
for key,sources,neutral,target in (
    ('d0_levels',sector['d0_sources'],0,'normal_sector_hue_d0'),
    ('d1_levels',sector['d1_sources'],0,'normal_sector_hue_d1'),
    ('k_levels',sector['k_sources'],100,'normal_sector_saturation_k_percent')):
    a,b,c,d=[r.get('values_s8',r.get('values_u8')) for r in sources]
    levels=[a,avg(a,b),b,avg(b,[neutral]*24),[neutral]*24,
            avg(d,[neutral]*24),d,avg(d,c),c]
    assert levels==old[target],key
    sector[key]=levels
assert [r['u32'] for r in sector['masks']]==[0x780,0x1F000,0x7C0000,0x60,0x1E]
save('sector_sources.json',sector)

dng_matrices=[[8781,-2991,96,-6913,14193,2997,-990,1441,7617],
              [7665,-1873,-562,-8232,15804,2586,-1797,2074,7667]]
hits=[]
for p in M['INPUTS'][:4]:
    data=p.read_bytes()
    for i,row in enumerate(dng_matrices,1):
        for endian in ('>','<'):
            patterns={'9_s32':struct.pack(endian+'9i',*row),
                      '9_s16':struct.pack(endian+'9h',*row),
                      '9_srational':b''.join(struct.pack(endian+'ii',x,10000) for x in row),
                      '9_f32':struct.pack(endian+'9f',*(x/10000 for x in row))}
            for name,pattern in patterns.items():
                pos=data.find(pattern)
                if pos>=0:
                    hit={'file':str(p.relative_to(M['ROOT'])),'matrix':i,'pattern':name,
                         'endian':endian,'file_offset':hex(pos),'raw_hex':pattern.hex(' ')}
                    if p.name=='jlaunch3':
                        hit['vma']=next((hex(s['load_address']+pos-s['file_offset']) for s in im.sections
                                         if s['file_offset']<=pos<s['file_offset']+s['initialized_size']),None)
                    hits.append(hit)
save('dng_matrix_binary_hits.json',{'evidence_level':'静态确认: exact bytes only, no data-flow identity inferred',
                                  'patterns':'entire 9 coefficients in s16, s32, SRATIONAL and float32, BE and LE',
                                  'hits':hits})

pixels=4288*2848
cost={'evidence_level':'推断: conditional arithmetic scenarios, not a benchmark; CPU frequency and cycles/pixel unknown',
      'output_width':4288,'output_height':2848,'pixels':pixels,'raw_pixels':4304*2862,
      'candidate_YCC_2_bytes_per_pixel':pixels*2,'minimum_inplace_read_write_bytes':pixels*4,
      'RGB_u8_buffer_bytes':pixels*3,'lut17_RGB_u8_bytes':17**3*3,'lut33_RGB_u8_bytes':33**3*3,
      'formula':'seconds = pixels * cycles_per_pixel / (frequency_MHz * 1000000)',
      'scenarios':[{'cycles_per_pixel':c,'frequency_MHz':f,'seconds':pixels*c/(f*1e6)}
                   for c in (100,300,1000) for f in (100,200,300)]}
save('software_cost_model.json',cost)

table=json.loads((HERE/'decoded_tables.json').read_text())
out=[]
for family,d in table.items():
    if family=='type23':
        for i,row in enumerate(d['input_rows']):
            out.append({'family':family,'bank':'input','row':i,'vma':row['vma'],'values':row['values']})
        for bank,rows in enumerate(d['output_banks']):
            for i,row in enumerate(rows):out.append({'family':family,'bank':f'output{bank}','row':i,'vma':row['vma'],'values':row['values']})
with (HERE/'channel_curves.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['family','bank','row_zero_based','vma','node','value'])
    for r in out:
        for i,v in enumerate(r['values']): w.writerow([r['family'],r['bank'],r['row'],r['vma'],i,v])

print('type payload_words groups')
for r in catalog:
    print(r['type'],r['payload_u32_count'],[(g['kind'][0],g.get('base'),g['count']) for g in r['write_groups']])
print('Matrix candidates:')
for r in matrices:print(r['row_1_based'],r['raw_u16'],r['row_sums_raw'])
