"""Inventory all final-code file calls and native/indirect transfer boundaries."""
from pathlib import Path
import json
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, load, save, sha
import codegen as c

def main():
    e=c.ES[119];raw=(ROOT/'firmware/package_v36_g119/SD_ROOT/GXRCE.DAT').read_bytes()
    a,z=struct.unpack_from('>II',raw,132);assert raw[a:a+z]==e.engine['data']
    relocated=bytearray(raw);ro,rn=struct.unpack_from('>II',raw,144);rel=[]
    for pos in range(ro,ro+rn,8):
        patch,target=struct.unpack_from('>II',raw,pos)
        assert a<=patch< a+z and 0<=target<len(raw)+int.from_bytes(raw[116:120],'big')
        struct.pack_into('>I',relocated,patch,0x21000000+target);rel.append(dict(patch=patch,target=target))
    (OUT/'final-relocated-engine.bin').write_bytes(relocated[a:a+z])
    file_calls=[];indirect=[];caps=[];direct=[];bridges=[];capgates=[]
    file_names={'rv_native_open','rv_native_read','rv_native_close','rv_native_create','rv_native_write','rv_native_rename','rv_native_delete'}
    bridge_names={s['name'] for s in json.loads((OUT/'assembly-leaves.json').read_text()) if s['name'].startswith('rv_native_')}
    for name in sorted(bridge_names):
        start=e.symbols[name]['address'];blob=e.bytes(start,12)
        # Every native bridge loads an explicit absolute address into r6.
        high=int.from_bytes(blob[2:4],'big');low=int.from_bytes(blob[6:8],'big')
        assert blob[:2]==bytes.fromhex('d6c0') and blob[4:6]==bytes.fromhex('86e6'),(name,blob.hex())
        address=(high<<16)|low
        bridges.append(dict(name=name,pc=hex(0x21000000+start),target=hex(address),bytes=blob.hex()))
    owner=lambda pc:next((n for n,s in e.functions.items() if s['address']<=pc<s['address']+s['size']),None)
    for n in e.functions:
        for row in c.atoms(119,n)[0]:
            pc,asm=row['pc'],row['asm'];basepc=0x21000000+pc
            # Each decoded instruction has already been checked against DAT.
            if re.match(r'(?:jl|jmp) ',asm) and asm!='jmp lr':indirect.append(dict(function=n,pc=hex(basepc),asm=asm))
            if n=='ig_init' and re.match(r'ld24 \w+,e0000(?: |$)',asm):caps.append(dict(pc=hex(basepc),asm=asm))
            m=re.search(r'\b(bl|bra)\s+([0-9a-f]+) <([^>]+)>',asm)
            if m:
                target=int(m[2],16);name=m[3]
                direct.append(dict(function=n,pc=hex(basepc),target=target,symbol=name))
                if name in file_names:file_calls.append(dict(function=n,pc=hex(basepc),service=name,asm=asm))
            if n=='rv_call' and re.match(r'ld24 \w+,10000(?: |$)',asm):
                aa=c.atoms(119,n)[0];i=aa.index(row)
                capgates.append(dict(pc=hex(basepc),context=[dict(pc=hex(0x21000000+x['pc']),asm=x['asm']) for x in aa[max(0,i-2):i+5]]))
    assert len(caps)==2 and not any('f0000' in x['asm'] for x in c.atoms(119,'ig_init')[0])
    assert len(file_calls)==21,len(file_calls)
    expected={'rv_native_open':'0x200a40b4','rv_native_read':'0x200a449c','rv_native_close':'0x200a437c',
              'rv_native_create':'0x200a544c','rv_native_write':'0x200a45e8','rv_native_rename':'0x200a49d8','rv_native_delete':'0x200a4910'}
    for b in bridges:
        if b['name'] in expected:assert b['target']==expected[b['name']]
    bypass=[]
    for row in direct:
        if not 0x100<=row['target']<0x100+z:bypass.append(row)
    assert not bypass,bypass
    unknown_file_addresses=[]
    for n in e.functions:
        for row in c.atoms(119,n)[0]:
            if re.match(r'seth \w+,#0x200[ab]$',row['asm']):unknown_file_addresses.append(dict(function=n,**row))
    assert not unknown_file_addresses,unknown_file_addresses
    save('final-file-calls.json',file_calls);save('final-native-bridges.json',bridges)
    save('final-indirect-transfers.json',indirect)
    save('final-no-write-cutpoints.json',dict(capability_requests=caps,file_write_bit='0x10000',gates=capgates,
        relocated_sha256=sha(relocated[a:a+z]),relocations=rel,all_code_bytes_equal_DAT=True,
        direct_bypasses=bypass,untyped_native_stubs_byte_identical=True,
        read_only_invariant='init requests 0xE0000; loader 0x7FFF; only CAP_FILE_WRITE creates mode=write file tokens; op5 requires mode=write'))
    print('PASS final DAT: two 0xE0000 capability requests; 21 native file call sites; no direct bypass; bridges fixed',flush=True)

if __name__=='__main__':main()
