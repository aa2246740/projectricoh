"""Create generation-bound settings and rerunnable acceptance drivers."""
from pathlib import Path
import json,re,shutil,struct,sys,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('acceptance-prepare')
out=C.LOCAL;old=C.ROOT/'research/g157';(out/'settings').mkdir(exist_ok=True)
shutil.copyfile(old/'math_reference.py',C.HERE/'math_reference.py')
# Capture the field dials exactly once at the original BOOT dispatch boundary.
p=C.HERE/'run.py';text=(old/'local/fix-r1/final/run.py').read_text().replace('g157','g158').replace('G157','G158')
anchor="p.add_argument('--challenge',"
pos=text.index(anchor)
text=text[:pos]+'''p.add_argument('--dial',choices=('AUTO','P','A','M','S'),default='M')
p.add_argument('--raw-mode',type=lambda x:int(x,0))
p.add_argument('--submode',type=lambda x:int(x,0))
p.add_argument('--selection',type=lambda x:int(x,0))
p.add_argument('--my',type=int,default=0)
p.add_argument('--pending',type=int,default=0)
'''+text[pos:]
text=text.replace('    challenge_at=None','    challenge_at=resident[\'rv_engine\'] if a.challenge==\'none\' else None')
text=text.replace("            raw_mode=u(0x205d9a7f,1),MY=", "            raw_mode=u(0x205d9a7f,1),submode=u(0x205d9a9f,1),MY=")
anchor="                if a.challenge=='boot-activity6':"
insert='''                if a.challenge=='none':
                    mode,sub,selection={'AUTO':(0,0,0x8001),'P':(4,0,0x8010),'A':(4,1,0x8020),'M':(4,2,0x8008),'S':(4,3,0x8800)}[a.dial]
                    if a.raw_mode is not None:mode=a.raw_mode
                    if a.submode is not None:sub=a.submode
                    if a.selection is not None:selection=a.selection
                    c.write(0x205d9a7f,bytes([mode]));c.write(0x205d9a9f,bytes([sub]))
                    c.write(0x205d9aa3,bytes([a.my]));c.write(0x205da00b,bytes([a.pending]))
                    c.write(u(0x200c0dac)+0x2fc,selection.to_bytes(4,'big'))
                    result['declared_dial']=dict(dial=a.dial,mode=mode,submode=sub,N=selection,MY=a.my,pending=a.pending,
                        source='PASM mode/submode/N measured on g157 MOUNT. Emulated RAM boundary declaration; no physical dial or camera claim.')
'''
assert anchor in text;text=text.replace(anchor,insert+anchor)
p.write_text(text)
# Rebind only DAT/record/whole-S checksums. Recipe bytes and levels are untouched.
def bound(block,raw):
    b=bytearray(block);assert len(b)==4096
    if b[0xfd4:0xfd8]==b'GXR2':
        b[0xff0:0xff8]=raw[20:28];b[0xff8:0xffc]=zlib.crc32(b[0xfd4:0xff8]).to_bytes(4,'big')
    b[-4:]=(sum(struct.unpack('>2046H',b[:4092]))&0xffffffff).to_bytes(4,'big');return bytes(b)
settings=[]
for profile in C.PACKAGES:
    raw=C.artifact(profile)['dat'].read_bytes()
    for unit in C.UNITS:
        label='sweep-'+profile+'-'+unit+('-r2' if unit=='mount' else '')
        source=old/'local/fix-r1/final/runs'/label;doc=json.loads((source/'result.json').read_text())
        acros=next(r for r in doc['samples'] if r['name']=='Acros');assert acros['state']['levels']==[100]+[0]*9
        S=(source/('look-'+str(acros['ordinal'])+'-S.bin')).read_bytes();new=bound(S,raw)
        if unit=='mount':
            g157=(out/'before'/profile/'GXRCE.DAT').read_bytes()
            (out/'settings'/(profile+'-mount-old-g157-high.bin')).write_bytes(bound(S,g157))
        dest=out/'settings'/(profile+'-'+unit+'-Acros.bin');dest.write_bytes(new)
        (out/'settings'/(profile+'-'+unit+'-Acros.expected552')).write_bytes(C.D.expand_effect(raw,acros['index']))
        settings.append(dict(profile=profile,unit=unit,source=str(source),sha256=C.sha(new),changed_offsets=[i for i,(a,b) in enumerate(zip(S,new)) if a!=b]))
    S=(old/'local/fix-r1/settings'/(profile+'-mount-vivid09.bin')).read_bytes();new=bound(S,raw)
    (out/'settings'/(profile+'-mount-vivid09.bin')).write_bytes(new)
    neutral=bytearray(new);neutral[0x36e]=1;neutral[0x6dd:0x6df]=b'\x09\x09'
    (out/'settings'/(profile+'-mount-HC1.bin')).write_bytes(bound(neutral,raw))
    for name in ('HNCS LowSat',):
        area,_=C.D.effect_area(raw)
        index=next(i for i in range(C.D.u16(raw,area+10)) if raw[area+32+32*i+18]>>2&1 and raw[area+32+32*i+20:area+64+32*i].split(b'\0')[0].decode()==name)
        block=bytearray(neutral);record=b'GXR2'+bytes((3,64+index,2,1))+struct.pack('>10h',100,0,0,0,0,0,0,0,0,0)+raw[20:28]
        block[0xfd4:0xffc]=record+zlib.crc32(record).to_bytes(4,'big')
        (out/'settings'/(profile+'-mount-LowSat.bin')).write_bytes(bound(block,raw))
        (out/'settings'/(profile+'-mount-LowSat.expected552')).write_bytes(C.D.expand_effect(raw,index))
    # Existing HC+1 expected unit state from the reviewed counterexample.
    shutil.copyfile(old/'local/fix-r1/settings/test-mount-HC1.record552',out/'settings'/(profile+'-mount-HC1.record552'))
    # Native cold startup may begin at T=0. The logical record target stays exact.
    g157=(out/'before'/profile/'GXRCE.DAT').read_bytes()
    assert raw[20:28]!=g157[20:28]
    (out/'settings'/(profile+'-mount-old-g157.bin')).write_bytes(bound(neutral,g157))
    (out/'settings'/(profile+'-mount-04.expected552')).write_bytes(C.D.expand(raw,2,4))
C.save(out/'settings/manifest.json',settings)
# Reuse the proven final C transaction harness, execute the actual new gate body.
h=(old/'local/fix-r1/fault_harness.c').read_text().replace('engine_v69_g157','engine_v70_g158')
gate=(C.PRODUCT/'boot_adapter.inc.c').read_text();gate=gate[gate.index('static uint32_t boot_fail_bits'):gate.index('static int boot_native_ready')]
support='''static unsigned dial_sub;
static const unsigned nativeN[4]={0x8010,0x8020,0x8008,0x8800};
static uint32_t fieldword(uint32_t a){if(a==0x200c0dac)return 0x20100000;if(a==0x200c0db0)return 4096;if(a==0x205d9bf8)return 0;if(a==0x205d9c00)return 5;if(a==0x201002fc)return b32(S+0x2fc);assert(0);return 0;}
static uint8_t fieldbyte(uint32_t a){if(a==0x205d9a7f)return 4;if(a==0x205d9a9f)return dial_sub;if(a==0x205d9aa3||a==0x205da00b)return 0;assert(0);return 0;}
#undef RV_WORD
#undef RV_BYTE
#define RV_WORD(a) fieldword(a)
#define RV_BYTE(a) fieldbyte(a)
'''
support+=gate
h=h.replace('int eng_boot_check(void){return check_ok;}',support+'\nint eng_boot_check(void){return check_ok&&!boot_fail_bits();}')
h=h.replace('assert(argc==8);','assert(argc==9);dial_sub=(unsigned)atoi(argv[8]);assert(dial_sub<4);')
h=h.replace('fclose(s_file);','fclose(s_file);for(unsigned k=0;k<4;k++)S[0x2fc+k]=(uint8_t)(nativeN[dial_sub]>>(24-8*k));assert(!boot_fail_bits());')
h=h.replace('status,unit_number,kind,when,mode,triggered', 'status,unit_number,kind,when,mode,triggered')
(out/'fault_harness.c').write_text(h)
source=(old/'fix_r1_c_matrix.py').read_text()
start=source.index('source=(review/');end=source.index("file=out/'fault_harness.c'")
source=source[:start]+"source=(C.LOCAL/'fault_harness.c').read_text()\n"+source[end:]
source=source.replace("out=C.LOCAL/'fix-r1'",'out=C.LOCAL')
source=source.replace("settings=out/'settings/test-mount-vivid09.bin'", "settings=out/'settings/test-mount-vivid09.bin'")
source=source.replace('import json, subprocess, sys, time','import argparse, json, subprocess, sys, time')
source=source.replace("        C.compute_gate('C-'+profile+'-'+str(u))", "        while True:\n            try:C.compute_gate('C-'+profile+'-'+str(u));break\n            except RuntimeError as e:\n                if 'LOAD_DEFERRED' not in str(e):raise\n                time.sleep(5)")
source=source.replace("C.setup();C.DATASET='model';C.compute_gate", "p=argparse.ArgumentParser();p.add_argument('--submode',type=int,required=True);a=p.parse_args()\nC.setup();C.DATASET='model';C.compute_gate")
source=source.replace("out/'fault-harness'","out/('fault-harness-'+str(a.submode))")
source=source.replace("file=out/'fault_harness.c'", "file=out/('fault_harness-'+str(a.submode)+'.c')")
source=source.replace("out/'fault-build.log'", "out/('fault-build-'+str(a.submode)+'.log')")
source=source.replace("str(review/'parser/parsers.dylib')","str(C.LOCAL/'parser/parsers.dylib')")
source=source.replace('str(entry),str(settings),str(target)]','str(entry),str(settings),str(target),str(a.submode)]')
source=source.replace('row.update(profile=profile,', 'row.update(submode=a.submode,raw_mode=4,native_selection=(0x8010,0x8020,0x8008,0x8800)[a.submode],profile=profile,')
source=source.replace("out/'C-progress.json'", "out/('C-progress-'+str(a.submode)+'.json')")
source=source.replace("out/'C-matrix.json'", "out/('C-matrix-'+str(a.submode)+'.json')")
(C.HERE/'fault_matrix.py').write_text(source)
print(json.dumps(dict(status='PREPARED',settings=len(settings),gate_source_sha256=C.sha(gate.encode()))))
