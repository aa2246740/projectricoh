#!/usr/bin/env python3
"""Audit final artifacts, frozen input identities, source deltas, and link maps."""
import difflib
import json
from pathlib import Path
import re
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE, ROOT, LOCAL, SRC, guard, load, sha
import build
import pack

def main():
    guard();inputs={};artifacts=[]
    for name,expected in pack.v1.SOURCE_HASHES.items():
        source=(pack.v1.OFFICIAL if name.endswith('3') else pack.v1.DAILY)/name
        assert sha(source)==expected
        inputs[str(source.relative_to(ROOT))]=expected
    for variant in ('base','huzi'):
        folder=LOCAL/'candidates'/variant
        manifest=json.loads((folder/'manifest.json').read_text());layout=json.loads((folder/'layout.json').read_text())
        blob=(folder/'GXRCE.DAT').read_bytes()
        assert sha(folder/'GXRCE.DAT')==manifest['sha256']
        assert pack.u32(blob,12)==0 and pack.u32(blob,16)==len(blob) and blob[256:272]!=pack.STUB
        code=pack.sections(blob)[0];assert code[1]==layout['engine_bytes']<=49152
        assert blob[code[0]:sum(code)]==(folder/'engine.bin').read_bytes()
        assert sha(folder/'engine.bin')==layout['engine_sha256']
        assert len(blob)<=65536 and len(blob)+layout['bss_bytes']<=81920
        assert layout['pic_translation_verified'] and layout['no_sha_runtime']
        for path,expected in layout['sources'].items():assert sha(HERE/path)==expected
        for source in manifest['huzi']:
            assert sha(ROOT/source['source'])==source['source_sha256']
            inputs[source['source']]=source['source_sha256']
        artifacts.append(dict(variant=variant,**{k:manifest[k] for k in ('build','file_bytes','engine_bytes','bss_bytes','image_bss_bytes','sha256')}))
    (LOCAL/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    changes=[];patch=[]
    snapshot=json.loads((HERE/'UPSTREAM.json').read_text())
    for row in snapshot:
        before=ROOT/row['source'];after=HERE/row['copy']
        if sha(before)==sha(after):continue
        changes.append(dict(source=row['source'],copy=row['copy'],current_upstream_sha256=sha(before),copy_sha256=sha(after),original_snapshot_sha256=row['sha256']))
        patch.extend(difflib.unified_diff(before.read_text().splitlines(keepends=True),after.read_text().splitlines(keepends=True),fromfile='a/'+row['source'],tofile='b/firmware/engine/integrated/'+row['copy']))
    (LOCAL/'source-differences.patch').write_text(''.join(patch))
    (LOCAL/'source-differences.json').write_text(json.dumps(changes,indent=2)+'\n')
    # Non-LTO strict link intentionally fails the 48 KiB assertion. Its map
    # still measures each linked input. No oversized container is emitted.
    text=(LOCAL/'m32r-standard/probe.map').read_text()
    match=re.search(r'^\.engine\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)',text,re.M);assert match
    start,size=[int(x,16) for x in match.groups()];by_object={};occupied=bytearray(size);raw_input_bytes=0
    engine_map=text[match.end():text.index('__engine_end',match.end())]
    for line in engine_map.splitlines():
        m=re.fullmatch(r'\s+(?:\S+\s+)?0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(.+\.o)\s*',line)
        if not m:continue
        address,n=int(m[1],16),int(m[2],16)
        if n and start<=address and address+n<=start+size:
            raw_input_bytes+=n
            # GNU mergeable strings can share addresses across input objects.
            # Count each linked byte once, crediting its first map owner.
            begin=address-start;credited=occupied[begin:begin+n].count(0)
            occupied[begin:begin+n]=bytes([1])*n
            name=Path(m[3]).name;by_object[name]=by_object.get(name,0)+credited
    groups={}
    for name,n in by_object.items():
        source=build.sources()[int(name[:2])][0]
        rel=str(source.relative_to(HERE))
        if '/engine/core/' in rel:key='core'
        elif '/engine/panel/' in rel:key='panel_and_storage'
        elif '/card_container_v2/' in rel:key='container_gate_semantics_GXTS'
        elif '/resident_slim/' in rel:key='engine_services'
        elif '/recipe_tweak/' in rel:key='R2'
        else:key='integration_shared_native_adapter'
        groups[key]=groups.get(key,0)+n
    assert sum(groups.values())<=size
    groups['link_padding']=size-sum(groups.values())
    elf=load(ROOT/'firmware/stage2l_switch/tools/build.py','final_elf_reader').Elf(LOCAL/'m32r-lto/engine.elf')
    top=sorted((v for v in elf.symbols.values() if v.get('size') and v['section'] and v['info']&15==2),key=lambda r:r['size'],reverse=True)[:15]
    symbols=[dict(name=r['name'],bytes=r['size']) for r in top]
    assert sum(1 for name in elf.symbols if name=='memcpy')==1 and sum(1 for name in elf.symbols if name=='memset')==1
    assert not any('sha256' in name.lower() for name in elf.symbols)
    acceptance=json.loads((LOCAL/'acceptance.json').read_text())
    assert len(acceptance)==51 and all(r['output'].startswith('OK') for r in acceptance)
    result=dict(artifacts=artifacts,checks=len(acceptance),e2e_cases=sum(r['kind']=='e2e' for r in acceptance),
                full_validator_cases=sum(r['kind']=='full-c-validator' for r in acceptance),
                non_lto_engine_bytes=size,non_lto_components=groups,non_lto_objects=by_object,
                non_lto_raw_input_bytes=raw_input_bytes,non_lto_shared_string_bytes=raw_input_bytes-sum(by_object.values()),
                lto_largest_functions=symbols,source_differences=len(changes),inputs_verified=len(inputs),
                lto_function_attribution='Named final symbols only; inlined code is not attributed to source files',
                sanitizer='ASan/UBSan; LeakSanitizer unsupported by macOS',
                target_40k_met=all(r['engine_bytes']<=40960 for r in artifacts))
    (LOCAL/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('checks','non_lto_engine_bytes','source_differences','inputs_verified')}))

if __name__=='__main__':main()
