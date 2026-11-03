"""Bind the gen 124 DAT, ELF, source delta and safety-critical inherited functions."""
from pathlib import Path
import difflib
import json
import re
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

def functions(text):
    text=text.replace('__attribute__((noinline)) ','')
    found={}
    pattern=r'^(?:static )?(?:int32_t|uint32_t|unsigned|int|void|EngStatus|Gxr2Status|const uint8_t \*)\s*(\w+)\([^;{}]*\)\s*\{'
    for match in re.finditer(pattern,text,re.M):
        start=text.index('{',match.start());depth=1;end=start+1
        while depth:
            depth+=(text[end]=='{')-(text[end]=='}');end+=1
        found[match.group(1)]=(text[match.start():end],text[:match.start()].count('\n')+1)
    return found

def symbols(path):
    raw=path.read_bytes();header=struct.unpack_from('>16sHHIIIIIHHHHHH',raw)
    assert header[2]==88
    sections=[struct.unpack_from('>10I',raw,header[6]+i*header[11]) for i in range(header[12])]
    result={}
    for section in sections:
        if section[1]!=2:continue
        strings=sections[section[6]];names=raw[strings[4]:strings[4]+strings[5]]
        for at in range(section[4],section[4]+section[5],section[9]):
            name,value,size,info,other,index=struct.unpack_from('>IIIBBH',raw,at)
            name=names[name:].split(b'\0',1)[0].decode()
            if info&15==2 and size:result[name]=dict(address=value,size=size,section=index)
    return result

def main():
    layout=json.loads((TREE/'candidate/local/full-r13/layout.json').read_text())
    raw=DAT.read_bytes();engine=(TREE/'candidate/local/full-r13/engine.bin').read_bytes()
    reader=load(ROOT/'tools/native_harness/image_loader.py','audit_elf')
    elf=reader.Elf(ELF)
    assert next(s['data'] for s in elf.sections if s['name']=='.engine')==engine==raw[256:256+len(engine)]
    assert sha(engine)==layout['engine_sha256']
    sources={name:file_sha(ROOT/name)==value for name,value in layout['sources'].items()}
    headers={name:file_sha(ROOT/name)==value for name,value in layout.get('headers',{}).items()}
    tools={name:file_sha(ROOT/name)==value for name,value in layout['tools'].items()}
    assert all(sources.values()) and all(headers.values()) and all(tools.values())
    previous=ROOT/'firmware/engine_v45_verify/candidate'
    current=TREE/'candidate'
    source_files=[]
    for base in (previous,current):
        source_files.extend(p.relative_to(base) for p in base.rglob('*') if p.is_file() and
                            'local' not in p.relative_to(base).parts and p.suffix in ('.c','.h','.S','.ld','.py'))
    delta=[];patch=[]
    for relative in sorted(set(source_files)):
        a=(previous/relative).read_text() if (previous/relative).exists() else ''
        b=(current/relative).read_text() if (current/relative).exists() else ''
        if a==b:continue
        patch.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),
                     fromfile='firmware/engine_v45_verify/candidate/'+str(relative),tofile='firmware/engine_v46_ui/candidate/'+str(relative)))
        if relative.suffix not in ('.c','.h'):continue
        old,new=functions(a),functions(b)
        for name,(body,line) in new.items():
            if name not in old or body!=old[name][0]:
                delta.append(dict(file=str(relative),function=name,line=line,source_sha256=sha(body.encode())))
    # Include the Mac entry tool and inherited root scripts in the source
    # handoff as well; compiled-function accounting remains candidate-only.
    old_tree=previous.parent;new_tree=current.parent
    extra=set()
    for base in (old_tree,new_tree):
        for path in base.rglob('*'):
            relative=path.relative_to(base)
            if path.is_file() and 'local' not in relative.parts and relative.parts[0]!='candidate' and path.suffix in ('.c','.h','.S','.ld','.py'):
                extra.add(relative)
    for relative in sorted(extra):
        a=(old_tree/relative).read_text() if (old_tree/relative).exists() else ''
        b=(new_tree/relative).read_text() if (new_tree/relative).exists() else ''
        if a!=b:patch.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),
            fromfile='firmware/engine_v45_verify/'+str(relative),tofile='firmware/engine_v46_ui/'+str(relative)))
    (OUT/'source-change-vs-g123.patch').write_text(''.join(patch))
    core=Path('containers/product/src/firmware/engine/core/eng_core.c')
    a,b=functions((previous/core).read_text()),functions((current/core).read_text())
    critical=('deep','rpc','t_read','t_store','write_word','apply_impl','recover_confirmed','make_plan','settings_match','validate_live','rebind_impl','eng_require_recheck')
    preserved={name:a[name][0]==b[name][0] for name in critical}
    assert all(preserved.values()),preserved
    # Legacy row mathematics is unchanged, with its output buffer made explicit.
    old_compute=a['compute'][0].replace('static EngStatus compute(', 'static EngStatus compute_legacy(')
    old_compute=old_compute.replace('const EngTweak *t,uint8_t wb[2])','const EngTweak *t,uint8_t wb[2],uint8_t out[552])').replace('g.staging','out')
    assert old_compute==b['compute_legacy'][0]
    service=(current/'engine_services/services.c').read_text()
    assert 'u->rows!=8' in service and 'if(!rv_view_owned(r,u,0))return RV_STALE;' in service
    adapter=(current/'containers/product/adapter.c').read_text()
    assert 'list_bind(2)' not in adapter and 'n.list.rows=UV_PHYSICAL' in adapter
    assert not re.search(r'\b(?:ps_load|ps_install|ps_save|pn_gxts_bind|workspace_open)\s*\(',adapter)
    listing=subprocess.run([str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-dr','-z',str(ELF)],capture_output=True,text=True,check=True).stdout
    (OUT/'local/engine124.disasm').write_text(listing)
    syms=symbols(ELF)
    spans={}
    for name,item in syms.items():
        lines=[]
        for line in listing.splitlines():
            match=re.match(r'\s*([0-9a-f]+):\s',line)
            if match and item['address']<=int(match[1],16)<item['address']+item['size']:lines.append(line)
        path=OUT/'local/compiled'/(name+'.txt');path.parent.mkdir(exist_ok=True)
        path.write_text('\n'.join(lines)+'\n')
        spans[name]=dict(**item,disassembly_sha256=sha(path.read_bytes()),
            anomalies=[line.strip().split(':',1)[0] for line in lines if any(t in line for t in ('unknown','(bad)','.short','.word'))])
    header_paths=set((TREE/'resident').glob('*.h'))|set((current/'engine_services').glob('*.h'))|set((current/'containers/product').rglob('*.h'))
    header_binding={str(p.relative_to(ROOT)):file_sha(p) for p in sorted(header_paths) if 'local' not in p.relative_to(current.parent).parts}
    save('evidence/static-audit.json',dict(status='PASS_ARTIFACT_AND_SOURCE_BINDING',dat_sha256=sha(raw),elf_sha256=file_sha(ELF),
      engine_bytes=len(engine),dat_engine_elf_equal=True,source_hashes=sources,tool_hashes=tools,compiled_header_checks=headers,
      current_header_binding=header_binding,changed_functions=delta,compiled_spans=spans,critical_functions_preserved=preserved,
      legacy_math_only_output_argument_changed=True,physical_rows_enforced=8,old_update_caller_removed=True,
      camera_acceptance=False))
    print('PASS artifact/source binding',len(delta),'changed C functions;',len(spans),'compiled function symbols')

if __name__=='__main__':main()
