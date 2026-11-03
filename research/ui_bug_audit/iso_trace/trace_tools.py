#!/usr/bin/env python3
"""Read-only firmware evidence queries. All generated files stay in this directory."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
CANDIDATE = ROOT / 'artifacts/stage1b-candidate/packages/stage1b-16-recipes-012bcd24e77b/candidate/SD_ROOT/ilaunch3'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
DISASM = ROOT / 'research/tooling_m32r/disasm'

def segments(data):
    result = []
    for i, record in enumerate(range(0x20,0x160,20)):
        offset,va,size,bss,bss_size = struct.unpack_from('>IIIII',data,record)
        if not any((offset,va,size,bss,bss_size)): break
        if not size or offset+0x200+size>len(data): break
        result.append({'index':i,'offset':offset+0x200,'va':va,'size':size})
    return result

def at(data,va,length):
    for s in segments(data):
        if s['va']<=va and va+length<=s['va']+s['size']:
            offset=s['offset']+va-s['va']
            return offset,data[offset:offset+length]
    raise ValueError(hex(va))

def lines():
    for path in sorted(DISASM.glob('ilaunch3-sec*.disasm.txt')):
        for number,line in enumerate(path.read_text().splitlines(),1):
            m=re.match(r'^([0-9a-f]{8}):\s+((?:[0-9a-f]{2} )+)\s*(.*)$',line)
            if m:
                yield path.name,number,int(m[1],16),bytes.fromhex(m[2]),m[3],line

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('range','refs','table','identity'))
    parser.add_argument('start',nargs='?',type=lambda x:int(x,0))
    parser.add_argument('end',nargs='?',type=lambda x:int(x,0))
    args=parser.parse_args()
    original=OFFICIAL.read_bytes(); candidate=CANDIDATE.read_bytes()
    if args.mode=='identity':
        print(json.dumps({str(p.relative_to(ROOT)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in (OFFICIAL,CANDIDATE)},indent=2))
    elif args.mode=='range':
        start=args.start; end=args.end or start+0x100
        offset,content=at(original,start,end-start)
        candidate_offset,changed=at(candidate,start,end-start)
        path=OUT/f'official-{start:08x}-{end:08x}.bin'
        path.write_bytes(content)
        proc=subprocess.run([str(OBJDUMP),'-D','-b','binary','-m','m32r','-EB',f'--adjust-vma=0x{start:x}',str(path)],check=True,capture_output=True,text=True)
        disasm=OUT/f'official-{start:08x}-{end:08x}.disasm.txt'
        disasm.write_text(proc.stdout)
        print(f'VA {start:#x}..{end:#x}, file {offset:#x}..{offset+len(content):#x}; candidate identical={content==changed}')
        for filename,number,va,raw,text,line in lines():
            if start<=va<end:
                _,actual=at(original,va,len(raw)); assert actual==raw,(filename,number)
                _,patched=at(candidate,va,len(raw))
                print(f'{filename}:{number} | {line}'+(' [candidate='+patched.hex()+']' if actual!=patched else ''))
    elif args.mode=='refs':
        target=args.start; high=target>>16;low=target&0xffff
        all_lines=list(lines())
        for i,line in enumerate(all_lines):
            filename,number,va,raw,asm,_=line
            m=re.match(r'seth (r\d+|lr|sp),#0x([0-9a-f]+)',asm)
            if m and int(m[2],16)==high:
                reg=m[1]
                for j in range(i+1,min(i+5,len(all_lines))):
                    next_line=all_lines[j]
                    if next_line[0]!=filename:break
                    if re.search(rf'or3 {reg},{reg},#0x{low:x}(?:\W|$)',next_line[4]):
                        for show in all_lines[max(0,i-1):j+3]:
                            _,actual=at(original,show[2],len(show[3]));assert actual==show[3]
                            print(f'{show[0]}:{show[1]} | {show[5]}')
                        print()
                        break
        needle=struct.pack('>I',target)
        for s in segments(original):
            content=original[s['offset']:s['offset']+s['size']]
            pos=0
            while True:
                pos=content.find(needle,pos)
                if pos<0:break
                print(f'BE32 reference file={s["offset"]+pos:#x}, VA={s["va"]+pos:#x}, aligned={pos%4==0}')
                pos+=1
    elif args.mode=='table':
        start=args.start;end=args.end or start+0x40
        offset,raw=at(original,start,end-start);_,patched=at(candidate,start,end-start)
        print(f'file={offset:#x}, candidate identical={raw==patched}')
        for i in range(0,len(raw),16):
            print(f'{start+i:08x}: {raw[i:i+16].hex(" ")}')

if __name__=='__main__':main()
