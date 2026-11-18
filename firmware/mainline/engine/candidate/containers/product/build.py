#!/usr/bin/env python3
"""Link the complete PIC engine; audit pointers and translated bytes."""
import argparse
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime import HERE, ROOT, LOCAL, SRC, GCC, LD, OBJDUMP, guard, load, run, sha

FLAGS = ['-std=c11','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-common',
         '-fpic','-m32r','-mmodel=medium','-msdata=none','-G0','-Wall','-Wextra','-Werror',
         '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fstack-usage',
         '-fvisibility=hidden','-ffunction-sections','-fdata-sections','-falign-functions=4']

## Size-only tuning; the resident and all product checks keep their C semantics.
XDATA = False  # optional: .rodata leaves the code section for DAT section 3

SIZE_OPTIONS = ['-fno-partial-inlining','-fipa-sra','-fno-inline-small-functions','-fomit-frame-pointer']

def receipt_path(path):
    """Receipt key: relative to the public tree, else the private root, else absolute."""
    path = Path(path)
    public = getattr(sys.modules['runtime'], 'PUBLIC', None)
    for base in (public, ROOT):
        if not base:
            continue
        try:
            return str(path.relative_to(Path(base)))
        except ValueError:
            continue
    return str(path)

def sources():
    core = SRC/'firmware/engine/core'
    panel = SRC/'firmware/engine/panel'
    container = SRC/'firmware/card_container_v2'
    resident = ROOT/'firmware/resident_v34c/resident'
    service = HERE.parents[1]/'engine_services'
    rows = [(HERE/'adapter.c',False), (HERE/'ui_v2_data.c',False), (HERE/'memory.c',False), (HERE/'diagnostic.c',False), (HERE/'fx_pool.c',False)]
    rows += [(core/n,False) for n in ('eng_core.c','eng_data.c','eng_crc_compat.c','eng_semantic.c','eng_pin_stub.c','eng_mem.c')]
    rows += [(panel/n,False) for n in ('panel.c','panel_ui.c','panel_native.c','panel_port.c','panel_store.c','panel_gxts.c','panel_gxts_bind.c')]
    rows += [(container/n,False) for n in ('gate.c','common.c','api.c','gxts.c','gxts_io.c')]
    rows += [(HERE/'kv2'/n,False) for n in ('kv_data.c','kv_ui.c','kv_math.c','kv_i64.c')]
    rows += [(service/n,True) for n in ('services.c','api.c','runtime.c','crc.c','bridges.S','mark.c','native_seed.c')]
    rows += [(resident/'shared.c',True)]
    return rows

def build(data_bytes, lto=True, profile='final'):
    guard()
    out = LOCAL/(('m32r-lto' if lto else 'm32r-standard')+('' if profile=='final' else '-'+profile))
    out.mkdir(exist_ok=True)
    extra={'final':[], 'oz':['-Oz','-flto-partition=one'],
           'one':['-flto-partition=one'],
           'tinyinline':['-Oz','-flto-partition=one','--param=max-inline-insns-auto=20','--param=max-inline-insns-single=20']}[profile]
    objects = []
    for index,(src,service) in enumerate(sources()):
        if service:continue
        obj=out/(f'{index:02}-'+src.stem+'.o');objects.append(obj)
        flags=FLAGS+SIZE_OPTIONS+extra+(['-flto'] if lto and src.suffix=='.c' and src.name not in ('eng_mem.c','kv_i64.c') else [])
        if src.name=='memory.c':flags+=['-fno-tree-loop-distribute-patterns']
        flags += ['-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER','-I',str(HERE)]
        if service:flags+=['-DRV_ENGINE_SERVICES']
        if src.name=='gxts.c':flags+=['-include',str(SRC/'firmware/engine/core/eng_crc_bindings.h')]
        run([GCC,*flags,'-c',src,'-o',obj],out.name+'-compile-'+str(index))
    reader=load(ROOT/'firmware/stage2l_switch/tools/build.py','integrated_elf_reader')
    def link(total,label,base=0,xstart=0):
        elf=out/(label+'.elf')
        script=HERE/('engine_x.ld' if XDATA else 'engine.ld')
        options=['--no-undefined','--orphan-handling=error','--emit-relocs','--gc-sections','-Bsymbolic','-u','eng_project_compute',
                 '--defsym=BSS_START='+str(total),'--defsym=IMAGE_BASE='+str(base),'-T',str(script),'-Map='+str(out/(label+'.map'))]
        if XDATA:options.insert(-3,'--defsym=XDATA_START='+str(xstart))
        if lto:args=[GCC,'-save-temps=obj','-Wa,-L','-Wl,--discard-none','-Os','-fstack-usage',*SIZE_OPTIONS,*extra,'-flto','-m32r','-nostdlib',*['-Wl,'+x for x in options],'-o',elf,*objects]
        else:args=[LD,*options,'-o',elf,*objects]
        args += [HERE.parents[1]/'local/resident/engine-services/libgxr_services.a']
        run(args,out.name+'-'+label)
        return reader.Elf(elf)
    def section(e,name):return next(s for s in e.sections if s['name']==name)
    def relocations(e):
        rows=[]
        for sec in e.sections:
            if sec['type']!=4:continue
            syms=e.symbol_tables[sec['link']]
            for pos in range(0,sec['size'],12):
                patch,info,addend=struct.unpack_from('>IIi',e.bytes,sec['offset']+pos)
                rows.append(dict(patch=patch,kind=info&255,symbol=syms[info>>8]['name'],addend=addend))
        return rows
    if XDATA:
        first=link(98304,'probe',0,90112)
        count=sum(r['kind'] in (2,34) for r in relocations(first))
        xbytes=section(first,'.xdata')['size']
        xstart=256+section(first,'.engine')['size']+8*count
        total=xstart+xbytes+data_bytes
    else:
        first=link(98304,'probe')
        count=sum(r['kind'] in (2,34) for r in relocations(first))
        total=256+section(first,'.engine')['size']+8*count+data_bytes
        xstart=0
    e=link(total,'engine',0,xstart);blob=e.content(section(e,'.engine'));rows=relocations(e)
    allowed={0,2,34,48,49,60,61,63,64};rel=[]
    bss=section(e,'.bss')['size']
    main_request=7628+((total+bss+3)&~3)
    assert main_request<=107612, f'main_request exceeds engineering limit 107612: {main_request}'
    for r in rows:
        assert r['kind'] in allowed, r
        if r['kind'] in (2,34):
            patch=r['patch'];target=struct.unpack_from('>I',blob,patch-256)[0]
            assert patch%4==0 and 256<=patch<=256+len(blob)-4 and 256<=target<total+bss,r
            rel.append((patch,target))
    rel=sorted(set(rel));assert len(rel)==count and count<=256
    for pos in range(e.symbols['__got_start']['value'],e.symbols['__got_end']['value'],4):
        assert (pos,struct.unpack_from('>I',blob,pos-256)[0]) in rel
    assert not any(s['section']==0 and s['name'] for s in e.symbols.values())
    assert not any('sha256' in name.lower() or name.lower().startswith('sha_') for name in e.symbols)
    translated=link(total,'translated',0x21004000,xstart)
    translated_blob=bytearray(translated.content(section(translated,'.engine')))
    # Absolute runtime pointer cells translate; all other instruction/data bytes must agree.
    for patch,target in rel:
        assert struct.unpack_from('>I',translated_blob,patch-256)[0]==0x21004000+target
        struct.pack_into('>I',translated_blob,patch-256,target)
    assert bytes(translated_blob)==blob, 'untracked translation-dependent instruction/data'
    xblob=b''
    if XDATA:
        xs=section(e,'.xdata');assert xs['va']==xstart and xs['size']==xbytes,(xs,xstart,xbytes)
        xblob=e.content(xs);assert translated.content(section(translated,'.xdata'))==xblob,'xdata differs after translation'
        assert not any(p>=xstart for p,_ in rel)
    entries={name:e.symbols[name]['value'] for name in ('ig_bootstrap','ig_init','ig_menu','ig_event','ig_panel_open','ig_panel_event','ig_panel_abort','ig_apply','ig_stop')}
    assert all(v%4==0 and 256<=v<=256+len(blob)-4 for v in entries.values())
    (out/'engine.bin').write_bytes(blob)
    (out/'reloc.bin').write_bytes(b''.join(struct.pack('>II',*r) for r in rel))
    if XDATA:(out/'xdata.bin').write_bytes(xblob)
    run([OBJDUMP,'-dr',out/'engine.elf'],out.name+'-disassembly')
    result=dict(engine_bytes=len(blob),bss_bytes=bss,file_bytes=total,image_bss_bytes=total+bss,main_request=main_request,
                relocations=len(rel),relocation_bytes=len(rel)*8,data_bytes=data_bytes,xdata_bytes=len(xblob),xdata_start=xstart,entries=entries,
                target_40k=len(blob)<=40960,no_sha_runtime=True,pic_translation_verified=True,
                static_relocation_kinds=sorted({r['kind'] for r in rows}),lto=lto,flags=FLAGS+SIZE_OPTIONS+extra,profile=profile,
                service_archive_sha256=sha(HERE.parents[1]/'local/resident/engine-services/libgxr_services.a'),engine_sha256=sha(out/'engine.bin'),sources={receipt_path(s):sha(s) for s,_ in sources()},
                tools={receipt_path(s):sha(s) for s in (GCC,LD,OBJDUMP)},
                headers={receipt_path(p):sha(p) for p in sorted(set(SRC.rglob('*.h')) | set((HERE.parents[2]/'resident').glob('*.h')) | set((HERE.parents[1]/'engine_services').glob('*.h')) | {HERE/'ui_v2_data.h'}) if p.exists()})
    (out/'size.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'relocations.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('engine_bytes','bss_bytes','file_bytes','relocations','target_40k')}))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-bytes',type=int,required=True);p.add_argument('--standard',action='store_true');a=p.parse_args()
    build(a.data_bytes,not a.standard)
