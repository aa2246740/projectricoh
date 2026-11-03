#!/usr/bin/env python3
"""PIC/relocation measurement. Outputs engine segments only under local/."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE,ROOT,LOCAL,guard,load,run,sha
GCC=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD=ROOT/'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
def main():
    p=argparse.ArgumentParser(); p.add_argument('--data-bytes',type=int,default=24960); p.add_argument('--profile',choices=['standard','compact','lto'],default='standard'); a=p.parse_args()
    guard()
    out=LOCAL if a.profile=='standard' else LOCAL/a.profile
    out.mkdir(exist_ok=True)
    flags=['-std=c11','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-common',
           '-fpic','-m32r','-mmodel=medium','-msdata=none','-G0','-Wall','-Wextra','-Werror',
           '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fstack-usage',
           '-fvisibility=hidden','-ffunction-sections','-fdata-sections','-falign-functions=4']
    if a.profile=='compact': flags += ['-fno-inline-small-functions','-fno-inline-functions-called-once']
    if a.profile=='lto': flags += ['-flto']
    sources=[HERE/'eng_data.c',HERE/'eng_crc_compat.c',HERE/'eng_semantic.c',HERE/'eng_pin_stub.c',ROOT/'firmware/card_container_v2/common.c',HERE/'eng_core.c',HERE/'eng_grain.c',HERE/'eng_entries.c',HERE/'eng_mem.c',ROOT/'research/recipe_tweak/r2/tweak_int.c']
    objects=[]
    for src in sources:
        obj=out/(src.stem+'.o'); objects.append(obj)
        run([GCC,*flags,*(['-fno-lto'] if src.name=='eng_mem.c' else []),'-c',src,'-o',obj],'compile-'+src.stem)
    elfmod=load(ROOT/'firmware/stage2l_switch/tools/build.py','readonly_elf_reader')
    def link(start,label,base=0):
        elf=out/(label+'.elf')
        options=['--no-undefined','--orphan-handling=error','--emit-relocs','--gc-sections','-Bsymbolic',
             '--defsym=BSS_START='+str(start),'--defsym=IMAGE_BASE='+str(base),'-T',HERE/'engine.ld',
             '-Map='+str(out/(label+'.map')),'-o',elf,*objects]
        if a.profile=='lto':
            args=[GCC,'-Os','-flto','-m32r','-nostdlib']
            args += ['-Wl,'+str(x) for x in options[:9]]
            args += ['-Wl,-Map='+str(out/(label+'.map')),'-o',elf,*objects]
        else: args=[LD,*options]
        run(args,a.profile+'-'+label)
        return elfmod.Elf(elf)
    first=link(49152,'layout-probe')
    def engine(e): return next(s for s in e.sections if s['name']=='.engine')
    def relocations(e):
        rows=[]
        for s in e.sections:
            if s['type']!=4: continue
            symbols=e.symbol_tables[s['link']]
            for pos in range(0,s['size'],12):
                patch,info,addend=struct.unpack_from('>IIi',e.bytes,s['offset']+pos)
                rows.append(dict(patch=patch,kind=info&255,symbol=symbols[info>>8]['name'],addend=addend))
        return rows
    # Only complete BE32 pointer cells become container relocations. PIC GOTPC,
    # GOTOFF and PC-relative relocations are static offsets and remain fixed.
    initial=relocations(first)
    absolute=[r for r in initial if r['kind'] in (2,34)]
    # Actual M32R relocation numbers are audited against objdump below; any
    # unexpected absolute or dynamic type is a hard error, never ignored.
    total=256+engine(first)['size']+8*len(absolute)+a.data_bytes
    final=link(total,'engine')
    blob=final.content(engine(final)); rel=[]
    rows=relocations(final)
    supported={0,2,34,49,60,61,63,64}
    # Keep a textual audit too: the linked ELF is never the runtime segment.
    asm=run([OBJDUMP,'-dr',out/'engine.elf'],a.profile+'-engine-disassembly')
    for r in rows:
        if r['kind'] not in supported: raise RuntimeError('unsupported relocation '+str(r))
        if r['kind'] in (2,34):
            patch=r['patch']; target=struct.unpack_from('>I',blob,patch-256)[0]
            if patch%4 or patch<256 or patch>256+len(blob)-4 or target<256 or target>=total+4096:
                raise RuntimeError('non-internal aligned pointer '+str(r))
            rel.append((patch,target))
    rel=sorted(set(rel))
    if len(rel)!=len(absolute) or len(rel)>256: raise RuntimeError('relocation count mismatch')
    if any(s['section']==0 and s['name'] for s in final.symbols.values()): raise RuntimeError('undefined symbol')
    if any('sha256' in name.lower() or name.lower().startswith('sha_') for name in final.symbols): raise RuntimeError('SHA implementation/import in runtime ELF')
    entry_symbols={}
    for name in ('eng_bootstrap','eng_entry_init','eng_entry_menu','eng_entry_event','eng_entry_apply','panel_unlinked','engine_stop'):
        candidates=[s for k,s in final.symbols.items() if k==name or k.startswith(name+'.')]
        if len(candidates)!=1: raise RuntimeError('ambiguous/missing entry symbol '+name)
        address=candidates[0]['value']
        if address%4 or address<256 or address>256+len(blob)-4: raise RuntimeError('entry out of engine '+name)
        entry_symbols[name]=address
    bss=next(s for s in final.sections if s['name']=='.bss')
    # Replay the only permitted relocation operation at two unrelated bases.
    for base in (0x21004000,0x24008000):
        memory=bytearray(blob)
        for patch,target in rel:
            if target>=total+bss['size']: raise RuntimeError('pointer outside final BSS')
            struct.pack_into('>I',memory,patch-256,base+target)
        for patch,target in rel:
            assert struct.unpack_from('>I',memory,patch-256)[0]==base+target
    got_start=final.symbols['__got_start']['value']; got_end=final.symbols['__got_end']['value']
    for pos in range(got_start,got_end,4):
        target=struct.unpack_from('>I',blob,pos-256)[0]
        if (pos,target) not in rel: raise RuntimeError('untracked GOT pointer')
    # Relink the exact objects at unrelated addresses and compare every byte.
    # PIC constants and branches must be translation invariant.
    translated=link(total,'translated-proof',0x21004000)
    if translated.content(engine(translated))!=blob: raise RuntimeError('PIC translation changed engine bytes')
    (out/'engine-measurement.bin').write_bytes(blob)
    (out/'reloc.bin').write_bytes(b''.join(struct.pack('>II',*r) for r in rel))
    contributions={}
    if a.profile!='lto':
        for line in (out/'engine.map').read_text().splitlines():
            m=re.fullmatch(r'\s+(?:\S+\s+)?0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(.+\.o)\s*',line)
            if not m: continue
            address,size=int(m[1],16),int(m[2],16)
            if size and 256<=address and address+size<=256+len(blob):
                name=Path(m[3]).name;contributions[name]=contributions.get(name,0)+size
        if not contributions or sum(contributions.values())>len(blob): raise RuntimeError('invalid linked-object measurement')
    components=None
    if contributions:
        semantic=sum(contributions.get(name,0) for name in ('eng_semantic.o','eng_crc_compat.o','common.o'))
        tweak=contributions.get('tweak_int.o',0)
        components=dict(core=sum(contributions.values())-semantic-tweak,container_semantic_crc=semantic,
            recipe_tweak=tweak,link_padding=len(blob)-sum(contributions.values()))
    result=dict(engine_bytes=len(blob),core_delivery_engine_bytes=len(blob),target_bytes=32768,within_target=len(blob)<=32768,
        format_engine_limit=32768,within_format_limit=len(blob)<=32768,bss_bytes=bss['size'],
        linked_components=['core','container_semantic_crc','recipe_tweak'],
        excluded_components=['panel','GXTS','engine_services'],combined_engine_measured=False,
        object_engine_bytes=contributions,component_engine_bytes=components,
        bss_offset=total,data_bytes=a.data_bytes,relocations=len(rel),relocation_bytes=8*len(rel),
        projected_container_bytes=total,container_fits=total<=49152,entry=final.symbols['eng_bootstrap']['value'],
        entry_symbols=entry_symbols,static_relocation_kinds=sorted({r['kind'] for r in rows}),flags=flags,
        source_hashes={str(s.relative_to(ROOT)):sha(s) for s in sources},
        upstream_hashes={str(s.relative_to(ROOT)):sha(s) for s in [ROOT/'firmware/card_container_v2/gxrce.h',ROOT/'firmware/card_container_v2/internal.h',ROOT/'firmware/card_container_v2/semantic.c',HERE/'eng_crc_bindings.h',ROOT/'firmware/resident_v2/abi.h']},
        tools={str(t.relative_to(ROOT)):sha(t) for t in (GCC,LD,OBJDUMP)},
        engine_sha256=sha(out/'engine-measurement.bin'),pic_relink_byte_identical=True,no_sha_runtime=True,profile=a.profile,measurement_only=True)
    (out/'size.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'relocation-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('engine_bytes','bss_bytes','relocations','projected_container_bytes','within_target','within_format_limit')},ensure_ascii=False))
if __name__=='__main__': main()
