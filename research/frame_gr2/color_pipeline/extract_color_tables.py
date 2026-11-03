#!/usr/bin/env python3
"""Reconstruct observed colour tables as data; no target code is executed."""
from pathlib import Path
import csv
import hashlib
import json
import struct

H=Path(__file__).resolve().parent
E=H/'evidence'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    b=(E/'wn3-b01firm8.dec.bin').read_bytes()
    old=(E/'official-b01firm8.dec.bin').read_bytes()
    assert sha(b)=='763ab802f0eceb3450312ce81f84f54140cf05bb4f18f25fdb7681c78198d725'
    sources={}
    def read(name,offset,size,vma):
        d=b[offset:offset+size]
        sources[name]=dict(file_offset=hex(offset),runtime_vma=hex(vma),size=size,
                           sha256=sha(d),exact_sequence_in_official=old.find(d))
        return d
    delta=read('negative_curve_delta_2bit',0xb95d0,256,0xa01b4e9c)
    curve=[];acc=0
    for v in delta:
        for shift in [6,4,2,0]:
            acc+=(v>>shift)&3
            curve.append(acc)
    assert len(curve)==1024 and curve[0]==0 and curve[-1]==255
    m0=list(struct.unpack('>9h',read('negative_default_matrix',0xb94a0,18,0xa015a6d0)))
    malt=list(struct.unpack('>9h',read('alternate_matrix_sentinel_fffe',0xb94b8,18,0xa015a6e8)))
    base=list(struct.unpack('>9h',read('negative_saturation_minus4',0xad1bc,18,0xa07a05bc)))
    ds=read('negative_saturation_steps',0xacd5c,72,0xa07a015c)
    satdelta=[list(struct.unpack_from('9b',ds,i*9)) for i in range(8)]
    sat=[]
    for strength in range(-4,5):
        m=[base[j]+sum(x[j] for x in satdelta[:strength+4]) for j in range(9)]
        assert [sum(m[i:i+3]) for i in [0,3,6]]==[256]*3
        sat.append(dict(value=strength,matrix_q8=m))
    assert sat[4]['matrix_q8']==m0
    hd=read('negative_hue_delta',0xac714,72,0xa079fb14)
    hue=[]
    for value in range(-4,5):
        if value==0:m=[256,0,0,0,256,0,0,0,256]
        else:
            row=value+4 if value<0 else value+3
            m=list(struct.unpack_from('9b',hd,row*9))
            m=[v+(256 if j%4==0 else 0) for j,v in enumerate(m)]
        assert [sum(m[i:i+3]) for i in [0,3,6]]==[256]*3
        hue.append(dict(value=value,matrix_q8=m))
    result=dict(sources=sources,curve_u8=curve,negative_default_matrix_q8=m0,
        alternate_matrix_q8=malt,saturation=sat,hue=hue,
        source_code=dict(curve='0xA0799C82..0xA0799D4C',tone_adjust='0xA079E1A0..0xA079E1EC',
                         matrix_adjust='0xA079F7F4..0xA079F90A'),
        limits=['Static reconstruction only; input colour domain and complete ISP are not established.',
                'The alternate sentinel matrix is not identified as Positive Film.'])
    (E/'negative-tables.json').write_text(json.dumps(result,indent=2)+'\n')
    with (E/'negative-curve.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['index_10bit','value_8bit']);w.writerows(enumerate(curve))
    manifest=[]
    gallery=json.loads((H/'assets/apk/assets/gallery.json').read_text())
    with (E/'preset-curves.csv').open('w') as cf,(E/'preset-matrices.csv').open('w') as mf:
        cw=csv.writer(cf);mw=csv.writer(mf);cw.writerow(['preset','channel','index','u8']);mw.writerow(['preset','bank','m00','m01','m02','m10','m11','m12','m20','m21','m22'])
        for p in sorted((H/'assets/apk/assets/flutter_assets/assets/profiles').glob('*.json')):
            raw=p.read_bytes();r=json.loads(raw)
            assert r['format']=='GR2-NATIVE-BALANCED-1'
            assert len(r['input_matrix_q8'])==9
            assert [sum(r['input_matrix_q8'][i:i+3]) for i in [0,3,6]]==[256]*3
            assert len(r['local_matrices_q10'])==12 and len(r['selectors'])==20
            for m in r['local_matrices_q10']:
                assert len(m)==9 and min(m)>=-2048 and max(m)<=2047
                assert [sum(m[i:i+3]) for i in [0,3,6]]==[1024]*3
            for c in r['rgb_curves_u8']:
                assert len(c)==1024 and min(c)>=0 and max(c)<=255
                assert all(x<=y for x,y in zip(c,c[1:]))
            body=bytearray(4384)
            struct.pack_into('>II9h',body,0,0x47325032,0x00040000,*r['input_matrix_q8'])
            body[32:1056]=bytes((i*255+511)//1023 for i in range(1024))
            for c,values in enumerate(r['rgb_curves_u8']):
                body[1056+c*1024:2080+c*1024]=bytes(values)
                cw.writerows((p.stem,c,i,v) for i,v in enumerate(values))
            struct.pack_into('>IHBB',body,4128,0x47324c4d,14,12,20)
            body[4136:4156]=bytes(r['selectors'])
            for bank,m in enumerate(r['local_matrices_q10']):
                struct.pack_into('>9h',body,4160+bank*18,*m);mw.writerow([p.stem,bank,*m])
            (E/(p.stem+'.profile.bin')).write_bytes(body)
            g=next(g for g in gallery if g['id']==p.stem)
            cube=H/'assets/apk/assets'/g['sourceAsset'];cube_raw=cube.read_bytes()
            assert sha(cube_raw)==g['sourceSha256']
            counts={};headers=[]
            for line in cube_raw.decode('utf-8-sig').splitlines():
                x=line.strip()
                if not x:continue
                try:
                    nums=[float(t) for t in x.split()]
                    if len(nums)==3:counts['triples']=counts.get('triples',0)+1;continue
                except ValueError:pass
                headers.append(x)
            mac=H/'assets/macos/profiles'/p.name
            assert mac.read_bytes()==raw
            knots=[0,64,128,256,512,768,1023]
            manifest.append(dict(name=r['name'],profile_json_sha256=sha(raw),profile_wire_sha256=sha(body),
                profile_wire_bytes=len(body),mac_android_profiles_equal=True,
                source_cube_sha256=sha(cube_raw),cube_header_lines=headers[:20],cube_numeric_triples=counts['triples'],
                cameraVerified=g['cameraVerified'],conversionVersion=g['conversionVersion'],
                input_matrix_q8=r['input_matrix_q8'],selectors=r['selectors'],
                curve_knots=dict(indices=knots,rgb=[[c[i] for i in knots] for c in r['rgb_curves_u8']]),
                profile_curves_exact_in_firmware=[b.find(bytes(c)) for c in r['rgb_curves_u8']],
                profile_curves_exact_in_official=[old.find(bytes(c)) for c in r['rgb_curves_u8']]))
    (E/'preset-summary.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(curve_knots=[curve[i] for i in [0,64,128,256,512,768,1023]],
        default_matrix=m0,profiles=[dict(name=x['name'],triples=x['cube_numeric_triples'],
        equal=x['mac_android_profiles_equal']) for x in manifest]),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
