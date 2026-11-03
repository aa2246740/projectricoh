"""Exercise the standard-library user-entry CLI, deterministic binding and rejection paths."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from decode_error import encode,decode,ENTRIES

def main():
    data=load(TREE/'candidate/ui_data.py','ui_data_test')
    raw=DAT.read_bytes()
    data.parse_dat(raw)
    folder=OUT/'local'/('user-fixture-'+sha(raw)[:12])
    folder.mkdir(parents=True,exist_ok=True)
    users=[dict(base=i,levels={}) for i in range(1,9) if i!=5]
    users += [dict(base=5,levels={'Cont':0 if i==0 else 1}) for i in range(25)]
    manifest=OUT/'user_entries_example.json'
    manifest.write_text(json.dumps(dict(entries=users),indent=2)+'\n')
    fixture=folder/'GXRCE.DAT'
    tool=TREE/'user_entries.py'
    if not fixture.exists():
        run(['/usr/bin/python3','-I','-B',tool,'build',DAT,'--manifest',manifest,'--output',fixture], 'user-tool-build')
    listed=run(['/usr/bin/python3','-I','-B',tool,'list',fixture], 'user-tool-list')
    result=json.loads(listed.stdout)
    assert result['count']==32 and result['entries'][-1]['name']=='FCC*025'
    output=fixture.read_bytes()
    _,ext,_,parsed=data.parse_dat(output)
    assert len(output)==len(raw)
    assert output[256:256+int.from_bytes(raw[136:140],'big')]==raw[256:256+int.from_bytes(raw[136:140],'big')]
    expected=data.replace_users(raw,data.read_manifest(manifest.read_text()))
    assert expected==output
    assert data.replace_users(output,[])==raw
    simple='5 Cont=1 High=-1 Shad=2 Satu=-2\n3 Cont=1\n'
    equivalent=json.dumps([{'base':5,'levels':{'Cont':1,'High':-1,'Shad':2,'Satu':-2}}, {'base':3,'levels':{'Cont':1}}])
    assert data.replace_users(raw,data.read_manifest(simple))==data.replace_users(raw,data.read_manifest(equivalent))
    rejected=[]
    bad=[('capacity',[dict(base=5,levels=[0]*11)]*33),('base-low',[dict(base=0,levels=[0]*11)]),
         ('base-high',[dict(base=9,levels=[0]*11)]),('base-bool',[dict(base=True,levels=[0]*11)])]
    for param in range(11):
        for value in range(-9,10):
            allowed=(-5<=value<=5) if param<4 else value==0
            if allowed:
                continue
            levels=[0]*11;levels[param]=value
            bad.append((f'param-{param}-{value}',[dict(base=5,levels=levels)]))
    levels=[0]*11;levels[3]=1
    bad.append(('BW-saturation',[dict(base=3,levels=levels)]))
    for name,items in bad:
        try:data.replace_users(raw,items)
        except ValueError:rejected.append(name)
        else:raise AssertionError(('accepted bad user entry',name))
    mutations=[]
    def reseal(p):
        struct.pack_into('>I',p,24,data.crc(p[256:]));struct.pack_into('>I',p,20,data.zero_crc(p[:256],20))
        return p
    section_starts=[data.u32(raw,132+12*i) for i in range(7)]
    meta,_,_,_=data.parse_dat(raw)
    for name,offset,inner in (
        ('header',40,False),('data_region',300,False),('record',section_starts[4]+40,True),
        ('pool',section_starts[5]+1000,True),('ui-crc',meta+data.LEGACY_BYTES+20,True)):
        p=bytearray(raw);p[offset]^=1
        if inner:reseal(p)
        try:data.parse_dat(p)
        except (ValueError,struct.error):mutations.append(name)
        else:raise AssertionError(('accepted broken CRC/binding',name))
    code_checks=0
    for entry in ENTRIES:
        for stage in range(7):
            for status in range(6):
                for sequence in range(256):
                    label=encode(entry,stage,status,sequence);decoded=decode(label)
                    assert len(label)==8 and (decoded['E'],decoded['S'],decoded['P'],int(decoded['QQ'],16))==(entry,stage,status,sequence)
                    code_checks+=1
    save('evidence/user-tool.json',dict(status='PASS',base_dat_sha256=sha(raw),fixture_sha256=sha(output),fixture=str(fixture.relative_to(ROOT)),
         user_entries=32,fixed_file_length=True,engine_bytes_unchanged=True,roundtrip_empty_exact=True,
         manifest_formats_equivalent=True,rejected_entries=len(rejected),rejected_cases=rejected,
         rejected_mutations=mutations,error_code_roundtrips=code_checks,entries=result['entries']))
    print('PASS user CLI and bindings',len(rejected),'rejections;',code_checks,'ERR tuples;',fixture)

if __name__=='__main__':main()
