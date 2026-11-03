"""Classify every embedded switch word using retained assembly labels and linked bytes."""
from pathlib import Path
import json
import re
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from static_audit import symbols

def main():
    reader=load(ROOT/'tools/native_harness/image_loader.py','tables_elf')
    elf=reader.Elf(ELF);labels=elf.symbols
    engine=next(s['data'] for s in elf.sections if s['name']=='.engine')
    compiled=symbols(ELF);tables=[]
    for source in (TREE/'candidate/local/product-r13/m32r-lto').glob('engine.elf.ltrans*.s'):
        text=source.read_text()
        for match in re.finditer(r'^(\.L\d+):\n((?:\s*\.word\s+\.L\d+-\.L\d+\s*\n)+)',text,re.M):
            name=match[1];start=labels[name]
            expressions=re.findall(r'\.word\s+(\.L\d+)-(\.L\d+)',match[2])
            owners=[(n,v) for n,v in compiled.items() if v['address']<=start<v['address']+v['size']]
            assert owners,(name,hex(start));owner,item=min(owners,key=lambda x:x[1]['size'])
            targets=[]
            for index,(target,base) in enumerate(expressions):
                word=struct.unpack_from('>I',engine,start-256+4*index)[0]
                assert word==(labels[target]-labels[base])&0xffffffff,(name,index)
                assert item['address']<=labels[target]<item['address']+item['size'],(name,target,owner)
                targets.append(dict(label=target,address=hex(labels[target])))
            tables.append(dict(label=name,start=hex(start),end=hex(start+4*len(expressions)),
                               bytes=4*len(expressions),owner=owner,targets=targets))
    assert tables and sum(len(t['targets']) for t in tables)==45,tables
    spans=[(int(t['start'],16),int(t['end'],16)) for t in tables]
    for table in tables:
        assert all(not any(lo<=int(target['address'],16)<hi for lo,hi in spans) for target in table['targets'])
    audit=json.loads((OUT/'evidence/static-audit.json').read_text())
    anomalies=[dict(function=name,pc=pc) for name,row in audit['compiled_spans'].items() for pc in row['anomalies']]
    assert all(any(lo<=int(row['pc'],16)<hi for lo,hi in spans) for row in anomalies),anomalies
    save('evidence/compiled-tables.json',dict(status='PASS',dat_sha256=file_sha(DAT),elf_sha256=file_sha(ELF),
        tables=tables,switch_words=45,classified_table_bytes=sum(t['bytes'] for t in tables),
        decode_anomalies=anomalies,unclassified_executable_anomalies=0,
        scope='Linked words equal retained assembler target-minus-base expressions. Every destination lies in its owning function and outside the table spans. Executable-byte decoding and PIC rebinding are separate checks.'))
    print('PASS',len(tables),'tables;',45,'switch words; all decode anomalies classified')

if __name__=='__main__':main()
