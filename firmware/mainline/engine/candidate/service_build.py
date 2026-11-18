"""Rebuild only the container's service archive with approved v3.2 flags."""
from pathlib import Path
import json
import re
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
GCC, LD, OBJDUMP = c.GCC, c.LD, c.OBJDUMP
run, sha = c.run, c.sha
LOCAL = c.LOCAL / 'resident'
HERE = c.RESIDENT
_upstream = c.load(c.RESIDENT / 'build.py', 'approved_service_profile')
# Fat objects preserve the standalone ld audit and let the final GCC link use LTO.
FLAGS = _upstream.FLAGS + ['-flto','-ffat-lto-objects']
ENGINE_SOURCES = [str(c.HERE / 'engine_services' / Path(n).name) if n.startswith('../engine_services/')
                  else str(c.RESIDENT / n) for n in _upstream.ENGINE_SOURCES]

def engine_library(legacy):
    out=LOCAL/'engine-services';out.mkdir(exist_ok=True)
    objects=[]
    for index,name in enumerate(ENGINE_SOURCES):
        src=Path(name);obj=out/(f'{index:02}-'+src.stem+'.o');objects.append(obj)
        run([GCC,*FLAGS,'-frandom-seed='+str(src.relative_to(c.ROOT)),'-fpic','-fvisibility=hidden','-DRV_ENGINE_SERVICES',*(['-mmodel=medium'] if src.suffix=='.c' else []),'-I',HERE,'-I',HERE/'../engine_services','-c',src,'-o',obj],'engine-compile-'+src.stem)
    archive=out/'libgxr_services.a'
    # The existing cross toolchain ships GCC/ld/objdump, without ar. Emit the
    # standard indexed GNU archive directly; ld below verifies the result.
    def member(name,data):
        h=f'{name:<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n'.encode('ascii')
        assert len(h)==60
        return h+data+(b'\n' if len(data)&1 else b'')
    exports=[]
    for i,obj in enumerate(objects):
        for symbol in legacy.Elf(obj).symbols.values():
            if symbol['section'] and symbol['info']>>4 in (1,2):exports.append((symbol['name'],i))
    names=b''.join(name.encode('ascii')+b'\0' for name,_ in exports)
    index_bytes=4+4*len(exports)+len(names)
    offset=8+60+index_bytes+(index_bytes&1);offsets=[];members=[]
    for obj in objects:
        offsets.append(offset);data=member(f'{len(members):02}.o/',obj.read_bytes());members.append(data);offset+=len(data)
    index=struct.pack('>I',len(exports))+b''.join(struct.pack('>I',offsets[i]) for _,i in exports)+names
    archive.write_bytes(b'!<arch>\n'+member('/',index)+b''.join(members))
    elf=out/'services-linkcheck.elf'
    run([LD,'--gc-sections','--emit-relocs','-Bsymbolic','--defsym=IMAGE_BASE=0','-u','rv_call','-u','rv_services_init','-u','es_ui_abort','-u','rv_native_seed','--no-undefined','--orphan-handling=error','-T',c.HERE/'engine_services/library.ld',f'-Map={out/"services.map"}','-o',elf,archive],'engine-library-link')
    parsed=legacy.Elf(elf);image_data=next(s for s in parsed.sections if s['name']=='.image_data')
    run([OBJDUMP,'-d',elf],'engine-disassembly')
    relocations=[];absolute=[];blob=parsed.content(image_data)
    for section in parsed.sections:
        if section['type']!=4:continue
        symbols=parsed.symbol_tables[section['link']]
        for pos in range(0,section['size'],12):
            patch,info,addend=struct.unpack_from('>IIi',parsed.bytes,section['offset']+pos)
            kind=info&255
            assert kind in {0,2,34,48,49,60,61,63,64},(kind,symbols[info>>8]['name'])
            relocations.append(dict(patch=patch,kind=kind,symbol=symbols[info>>8]['name'],addend=addend))
            if kind in (2,34):
                target=struct.unpack_from('>I',blob,patch-256)[0]
                assert patch%4==0 and 256<=patch<=256+len(blob)-4 and 256<=target<256+len(blob)
                absolute.append(dict(patch=patch,target=target))
    for patch in range(parsed.symbols['__got_start']['value'],parsed.symbols['__got_end']['value'],4):
        target=struct.unpack_from('>I',blob,patch-256)[0]
        assert 256<=target<256+len(blob)
        if not any(row['patch']==patch for row in absolute):absolute.append(dict(patch=patch,target=target))
    assert len(absolute)<=256
    translated=out/'services-translated.elf'
    run([LD,'--gc-sections','-Bsymbolic','--defsym=IMAGE_BASE=0x21004000','-u','rv_call','-u','rv_services_init','-u','es_ui_abort','-u','rv_native_seed','--no-undefined','--orphan-handling=error','-T',c.HERE/'engine_services/library.ld',f'-Map={out/"services-translated.map"}','-o',translated,archive],'engine-translation-link')
    moved=legacy.Elf(translated);section=next(s for s in moved.sections if s['name']=='.image_data')
    normalized=bytearray(moved.content(section))
    for row in absolute:
        assert struct.unpack_from('>I',normalized,row['patch']-256)[0]==0x21004000+row['target']
        struct.pack_into('>I',normalized,row['patch']-256,row['target'])
    assert normalized==blob,'non-PIC instruction or untracked pointer'
    assert not any(s['name'] and s['section']==0 for s in parsed.symbols.values())
    (out/'relocations.json').write_text(json.dumps(dict(link=relocations,container=absolute,translation_proof=True),indent=2)+'\n')
    linked={};covered=set();mapping=(out/'services.map').read_text().split('.image_data ',1)[1].split('.forbidden',1)[0]
    for address,amount,name in re.findall(r'^\s+(?:\.\S+\s+)?(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+.+libgxr_services\.a\(([^()]+\.o)\)\s*$',mapping,re.M):
        cells=set(range(int(address,16),int(address,16)+int(amount,16)))
        linked[name]=linked.get(name,0)+len(cells-covered);covered|=cells
    adjustment=image_data['size']-sum(linked.values());assert 0<=adjustment<128
    result=dict(archive=str(archive.relative_to(c.HERE)),elf=str(elf.relative_to(c.HERE)),elf_sha256=sha(elf),archive_sha256=sha(archive),bytes=image_data['size'],linked_objects=linked,link_adjustment_bytes=adjustment,max_engine_code=69632,remaining_engine_bytes=69632-image_data['size'],container_relocations=len(absolute),translation_proof=True,flags=FLAGS,lto=True,native_execution=False)
    (LOCAL/'engine-library.json').write_text(json.dumps(result,indent=2)+'\n')

def main():
    c.guard();LOCAL.mkdir(exist_ok=True)
    reader=c.load(c.ROOT/'firmware/stage2l_switch/tools/build.py','service_elf_reader')
    engine_library(reader)
    print('PASS engine services archive: '+('fat LTO' if '-flto' in FLAGS else 'baseline')+' and PIC translation audit')

if __name__=='__main__':main()
