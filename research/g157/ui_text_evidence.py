"""Export actual published UI text/glyphs and compare the original converter."""
from pathlib import Path
import argparse
import json
import os
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import accept_r2 as A
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--name',required=True);a=p.parse_args()
C.setup();C.compute_gate('UI-text-'+a.name)
run=C.LOCAL/'runs'/a.run;result=A.read(run/'result.json')
assert result['status']=='OBSERVED' and result['dat_sha256']==A.EXPECTED['test']
assert result['actual_backend']=='reference' and result['cold_start'] and not result['snapshots']
fixture=A.read(run/'service-fixture/manifest.json');assert fixture['DAT_sha256']==A.EXPECTED['test']
os.environ['GXR_HARNESS_BACKEND']='python'
sys.path.insert(0,str(C.ROOT/'tools/native_harness_c'));import python_backend as P
P.CACHE=A.DIR/'glyph-decode'/a.name
cpu=P.PythonBackend()
for region in fixture['regions']:
    raw=(C.ROOT/region['file']).read_bytes();assert C.sha(raw)==region['sha256'];cpu.map(region['address'],raw,True)
cpu.map(0x22000000,bytes(0x20000),True);cpu.set_reg('psw',0x80);cpu.set_reg('r15',0x2201fff0)
def u(address,n=4):return int.from_bytes(cpu.read(address,n),'big')
Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g157_r2_glyph_elf').Elf
symbols=Elf(C.artifact('test','model')['build']/'engine.elf').symbols
offsets=A.read(C.LOCAL/'layout.json')['offsets'];base=fixture['image_base'];state=base+symbols['n']['value']
ascii_rows=struct.unpack('14s'*8,cpu.read(state+offsets['n.ui.text'],112));table=u(0x2022f5a8)
assert u(0x2022f5ac,1)==8
frames=[dict(name='first-adj',screen=u(state+offsets['n.ui.screen'],1),rows=[])]
for i,data in enumerate(ascii_rows):
    raw=data.split(b'\0')[0];descriptor=u(table+4*i);pointer=u(descriptor);glyphs=cpu.read(pointer,70).split(b'\0')[0]
    assert len(glyphs)==2*len(raw)
    frames[0]['rows'].append(dict(row=i,text=raw.decode('ascii'),ascii_hex=raw.hex(),glyphs_hex=glyphs.hex(),
        row_descriptor=descriptor,lcd_text_pointer=pointer,source='Captured native UI descriptor and glyph buffer from first ADJ.'))
capture=run/'ui-first-adj.json'
if capture.exists():
    actual=A.read(capture)
    assert actual['DAT_sha256']==A.EXPECTED['test']
    assert [(r['text'],r['glyphs_hex']) for r in actual['rows']]==[(r['text'],r['glyphs_hex']) for r in frames[0]['rows']]
extra=run/'ui-list-after-diagnostic.json'
if extra.exists():
    doc=A.read(extra);assert doc['DAT_sha256']==A.EXPECTED['test']
    frames.append(dict(name='list-after-diagnostic',screen=doc['screen'],rows=doc['rows']))
stop=cpu.call(0x201dc180,[],0x7ffffff0,10000);assert stop.reason=='return';language=cpu.get_reg('r0')
def convert(raw):
    cpu.write(0x22000200,raw+b'\0');cpu.write(0x22001000,bytes(128))
    for i,value in enumerate((0x22000200,len(raw),0x22001000,language),4):cpu.set_reg('r'+str(i),value)
    stopped=cpu.call(0x201d73e0,[],0x7ffffff0,300000);assert stopped.reason=='return'
    return cpu.read(0x22001000,70).split(b'\0')[0]
mapping={};tsv=['frame\trow\tcolumn\tcharacter_json\tascii_hex\tpublished_glyph_hex\toriginal_converter_equal']
for frame in frames:
    assert len(frame['rows'])==8
    for row in frame['rows']:
        raw=bytes.fromhex(row['ascii_hex']);glyphs=bytes.fromhex(row['glyphs_hex'])
        assert raw.decode('ascii')==row['text'] and convert(raw)==glyphs
        chars=[]
        for column,value in enumerate(raw):
            glyph=glyphs[2*column:2*column+2];assert convert(bytes([value]))==glyph
            char=chr(value)
            if char in mapping:assert mapping[char]==glyph.hex()
            mapping[char]=glyph.hex();chars.append(dict(column=column,character=char,ascii_hex=f'{value:02x}',published_glyph_hex=glyph.hex(),original_converter_equal=True))
            tsv.append('\t'.join((frame['name'],str(row['row']),str(column),json.dumps(char),f'{value:02x}',glyph.hex(),'true')))
        row.update(characters=chars,original_converter_equal=True)
doc=dict(status='PASS',run=a.run,DAT_sha256=A.EXPECTED['test'],source_fixture=str(run/'service-fixture/manifest.json'),
    reference_MAIN=True,language=language,frames=frames,glyph_mapping=mapping,converter=dict(address=0x201d73e0,backend='independent Python ISA'),
    pixel_screenshot=False,boundary='Actual published UI rows and glyph buffers. This is text evidence, not LCD scanout or a pixel screenshot.')
C.save(A.DIR/('ui-text-'+a.name+'.json'),doc)
(A.DIR/('ui-text-'+a.name+'.tsv')).write_text('\n'.join(tsv)+'\n')
lines=['# 实际 UI 文本与 glyph 导出','','这不是 LCD 像素截图。文本来自新 MAIN 首次 ADJ 的实际八行描述符和 glyph 缓冲区，已逐字符用原厂转换器的独立 Python 指令执行复核。','',
       'DAT SHA-256：`'+A.EXPECTED['test']+'`。回执：`'+a.run+'`。','']
for frame in frames:
    lines+=['## '+frame['name'],'','```text',*[r['text'] for r in frame['rows']],'```','']
lines+=['## glyph 映射','','| 字符 JSON | ASCII | glyph |','| --- | --- | --- |']
lines += ['| `'+json.dumps(char)+'` | `'+f'{ord(char):02x}'+'` | `'+glyph+'` |' for char,glyph in sorted(mapping.items())]
(A.DIR/('ui-text-'+a.name+'.md')).write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(status='PASS',run=a.run,frames=len(frames),rows=sum(len(f['rows']) for f in frames),glyphs=len(mapping),pixels=False)))
