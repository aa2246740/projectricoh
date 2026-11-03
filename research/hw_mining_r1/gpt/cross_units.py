#!/usr/bin/env python3
"""Compare factory driver descriptors and shipped parameter scripts, no execution."""
import importlib.util
import json
import struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mine',HERE/'mine.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def vma(im, off):
    s=next(s for s in im.segments if s['file_offset']<=off<s['file_offset']+s['size'])
    return s['vma']+off-s['file_offset']

def hits(data, pattern):
    result=[]; start=0
    while True:
        off=data.find(pattern,start)
        if off<0: return result
        result.append(off);start=off+1

def main():
    j=m.Image('jlaunch3')
    layouts=json.loads((m.ROOT/'research/isp_pipeline/register_layouts.json').read_text())
    begin=0x2029C230
    end=max(int(r['descriptor'],16)+4*len(r['descriptor_words_to_next_descriptor']) for r in layouts)
    pattern=j.read(begin,end-begin)
    images={}
    for stem in m.NAMES:
        im=m.Image(stem+'3')
        found=hits(im.data,pattern)
        assert len(found)==1,(stem,found)
        desc0=vma(im,found[0]); delta=desc0-begin
        funcs=desc0-156
        descptr_candidates=hits(im.data,struct.pack('>I',desc0))
        ptrbase=None
        for off in descptr_candidates:
            if off+156>len(im.data): continue
            vals=struct.unpack_from('>39I',im.data,off)
            if all(v==int(r['descriptor'],16)+delta for v,r in zip(vals,layouts)):
                ptrbase=vma(im,off)
        assert ptrbase is not None,stem
        entries=[]
        for r in layouts:
            typ=r['type']
            writer=struct.unpack('>I',im.read(funcs+4*typ,4))[0]
            # Code body relative targets vary; descriptor identity is separately proven.
            entries.append(dict(type=typ,writer=hex(writer),descriptor=hex(int(r['descriptor'],16)+delta),
                 descriptor_file_offset=hex(im.offset(int(r['descriptor'],16)+delta)),
                 payload_u32_count=r['payload_u32_count'],registers=r['payload_registers']))
        images[im.name]=dict(descriptor_data_sha256=m.sha(pattern),descriptor_bytes=len(pattern),
             descriptor_start=hex(desc0),writer_table=hex(funcs),descriptor_pointer_table=hex(ptrbase),entries=entries)
        print(im.name,'descriptor bytes',len(pattern),'writer table',hex(funcs),'pointer table',hex(ptrbase))
    m.save(m.EVIDENCE/'cross-unit-drivers.json',images)
    params={}
    ranges=[(0x1262,0x1300),(0x1400,0x14c4),(0x2410,0x244a),(0x3092,0x3114)]
    for stem in m.NAMES:
        p=m.parse_params(stem+'8')
        params[stem]={f'{a:04x}-{b:04x}':dict(defined=sum(k in p for k in range(a,b)),
                         bytes_hex=bytes(p.get(k,0) for k in range(a,b)).hex()) for a,b in ranges}
    m.save(m.EVIDENCE/'cross-unit-parameter-ranges.json',params)

if __name__=='__main__':main()
