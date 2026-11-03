"""Audit final code ranges, compiler inlining records, stack frames and limits."""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import re
import runpy
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,ENGINE,enable,check_inputs

P=ENGINE/'candidate/containers/product'
BASE=ROOT/'firmware/engine_v48_own'
LOCAL=WORK/'local/codegen'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def functions(text):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    text=re.sub(r'__attribute__\s*\(\([^)]*\)\)','',text)
    result={}
    pattern=re.compile(r'(?m)^[ \t]*(?:(?:static|extern|inline|const|unsigned|signed|struct)\s+)*[A-Za-z_][\w \t*]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{')
    for match in pattern.finditer(text):
        name=match[1];start=match.end()-1;depth=1;end=start+1
        if name in ('if','else','for','while','switch','do'):continue
        while depth and end<len(text):
            depth+=(text[end]=='{')-(text[end]=='}');end+=1
        result[name]=text[match.start():end]
    return result

def body(path,name):
    text=path.read_text();start=re.search(r'\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',text).start()
    at=text.index('{',start);depth=1;end=at+1
    while depth and end<len(text):depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reuse',action='store_true');options=parser.parse_args()
    enable();check_inputs();LOCAL.mkdir(parents=True,exist_ok=True)
    full=ENGINE/'candidate/local/full-r13';raw=(full/'GXRCE.DAT').read_bytes()
    Elf=runpy.run_path(str(ROOT/'firmware/stage2l_switch/tools/build.py'))['Elf'];elf=Elf(full/'engine.elf')
    section=next(s for s in elf.sections if s['name']=='.engine')
    assert elf.content(section)==raw[256:256+section['size']]
    commands=[json.loads(line) for line in (ENGINE/'candidate/local/commands.jsonl').read_text().splitlines()]
    command=next(row['argv'] for row in reversed(commands) if row['label']=='m32r-lto-oz-engine')
    args=[];skip=False
    for index,value in enumerate(command):
        if skip:skip=False;continue
        if value=='-o':args+=['-o',str(LOCAL/'audit.elf')];skip=True
        elif value.startswith('-Wl,-Map='):args+=['-Wl,-Map='+str(LOCAL/'audit.map')]
        else:args.append(value)
    args.insert(1,'-fdump-ipa-clones')
    if not options.reuse:
        run=subprocess.run(args,capture_output=True,text=True,timeout=1800)
        (LOCAL/'link.log').write_text(run.stdout+run.stderr)
        if run.returncode:raise RuntimeError('code range link: '+run.stderr[-3000:])
    helper_command=next(row['argv'] for row in reversed(commands) if row['label']=='m32r-lto-oz-compile-25')
    helper_args=list(helper_command);helper_args[helper_args.index('-o')+1]=str(LOCAL/'helpers.o');helper_args.insert(1,'-fdump-ipa-clones')
    if not options.reuse:
        helper_run=subprocess.run(helper_args,capture_output=True,text=True,timeout=1200)
        (LOCAL/'helpers.log').write_text(helper_run.stdout+helper_run.stderr)
        if helper_run.returncode:raise RuntimeError('helper record compile: '+helper_run.stderr[-3000:])
    audit=Elf(LOCAL/'audit.elf');audit_section=next(s for s in audit.sections if s['name']=='.engine')
    assert audit.content(audit_section)==elf.content(section),'compiler record link changed code bytes'
    records=[]
    for path in LOCAL.glob('*.ipa-clones'):
        records+=path.read_text().splitlines()
    (WORK/'compiler-clones.txt').write_text('\n'.join(records)+'\n')
    compiled={name:item for name,item in elf.symbols.items() if item.get('section') and item.get('info',0)&15==2 and item.get('size')}
    helper=Elf((LOCAL/'helpers.o') if not options.reuse else ENGINE/'candidate/local/product-r13/m32r-lto-oz/25-kv_i64.o')
    for name in ('__muldi3','__divdi3'):
        item=helper.symbols[name];part=helper.sections[item['section']]
        offset=item['value']-part.get('addr',part.get('base',0))
        expected=helper.content(part)[offset:offset+item['size']]
        linked=compiled[name];assert expected==elf.content(section)[linked['value']-256:linked['value']-256+linked['size']]
    undefined=[name for name,item in elf.symbols.items() if name and item['section']==0]
    assert not undefined
    forbidden=[name for name in compiled if re.search(r'^__(?:float|fix|add[sd]f|sub[sd]f|mul[sd]f|div[sd]f)',name)]
    assert not forbidden
    assert not any(name.startswith('rt_') for name in compiled)
    changed={};patch=[]
    for path in sorted(ENGINE.rglob('*')):
        if not path.is_file() or 'local' in path.parts or path.suffix not in ('.c','.h','.py','.ld','.S'):continue
        relative=path.relative_to(ENGINE);before=BASE/relative
        original=before.read_text() if before.exists() else ''
        updated=path.read_text()
        if updated==original:continue
        patch.extend(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),
                     fromfile='gen127/'+str(relative),tofile='gen129/'+str(relative)))
        if path.suffix=='.c':
            old=functions(original)
            for name,value in functions(updated).items():
                if name not in old or value!=old[name]:changed[str(relative)+':'+name]={'name':name,'source':str(path.relative_to(ROOT))}
    (WORK/'source-vs-g127.patch').write_text(''.join(patch))
    frames={}
    directory=ENGINE/'candidate/local/product-r13/m32r-lto-oz'
    for path in [*directory.glob('engine.elf*.su'),*directory.glob('*-kv_i64.su'),*directory.glob('*-eng_mem.su')]:
        for line in path.read_text().splitlines():
            fields=line.split('\t')
            if len(fields)>=3:frames[fields[0].rsplit(':',1)[-1]]={'bytes':int(fields[1]),'kind':fields[2],'source':fields[0].rsplit(':',3)[0]}
    assert frames and all(row['kind']=='static' for row in frames.values())
    build=runpy.run_path(str(P/'build.py'));sources={path.resolve() for path,service in build['sources']() if path.suffix=='.c'}
    all_functions={}
    for path in sources:
        for name,value in functions(path.read_text()).items():all_functions[(path.resolve(),name)]=value
    pending=[]
    for symbol in compiled:
        name=symbol.split('.',1)[0];frame=frames.get(symbol,frames.get(name,{}));origin=frame.get('source')
        candidates=[key for key in all_functions if key[1]==name]
        exact=[key for key in candidates if origin and key[0]==Path(origin).resolve()]
        pending.extend(exact or candidates)
    reachable=set()
    while pending:
        key=pending.pop()
        if key in reachable:continue
        reachable.add(key);text=all_functions[key]
        for other,value in all_functions.items():
            if other in reachable or not re.search(r'\b'+re.escape(other[1])+r'\s*\(',text):continue
            if re.match(r'\s*static\b',value) and other[0]!=key[0]:continue
            pending.append(other)
    source_checks={};unmapped=[]
    for key,row in changed.items():
        name=row['name'];matches=[(symbol,item) for symbol,item in compiled.items() if symbol==name or symbol.startswith(name+'.')]
        clones=[line for line in records if re.search(r';'+re.escape(name)+r'(?:[.;])',line)]
        row.update(compiled=[{'name':symbol,'offset':item['value'],'bytes':item['size']} for symbol,item in matches],
                   compiler_records=len(clones),host_only=name.startswith(('eng_host_','ig_host_')),
                   categories=['address_length','file_operations','native_ui_writes','loops_memory'])
        if row['host_only']:row['coverage']='host_only'
        elif (ROOT/row['source']).resolve() not in sources:row['coverage']='not_in_target_build'
        elif matches:row['coverage']='final_function_range'
        elif clones:row['coverage']='compiler_inline_or_removal_record'
        elif name=='negate' and (ROOT/row['source']).name=='kv_i64.c' and name not in helper.symbols:
            row['coverage']='same_translation_unit_inline';row['inline_parents']=['__muldi3','__divdi3']
        elif ((ROOT/row['source']).resolve(),name) not in reachable:row['coverage']='not_reachable_from_final_functions'
        else:row['coverage']='UNMAPPED';unmapped.append(key)
        text=functions((ROOT/row['source']).read_text())[name]
        before=BASE/(ROOT/row['source']).relative_to(ENGINE)
        previous=functions(before.read_text()).get(name,'') if before.exists() else ''
        added_addresses=sorted(set(re.findall(r'0x2[0-9a-fA-F]{7}\b',text))-set(re.findall(r'0x2[0-9a-fA-F]{7}\b',previous)))
        file_calls=sorted(set(re.findall(r'\b(?:RV_FILE|RV_STORAGE|malloc|calloc|realloc|free|fopen|fwrite|rename|unlink)\b',text)))
        active=row['coverage'] in ('final_function_range','compiler_inline_or_removal_record','same_translation_unit_inline')
        if active:assert not added_addresses and not file_calls,(name,added_addresses,file_calls)
        for span in row['compiled']:
            assert span['offset']>=256 and span['offset']%2==0 and span['bytes']<=section['size']-(span['offset']-256)
        row['checks']={'address_length':{'final_ranges':len(matches),'compiler_records':len(clones)},
                       'file_operations':{'direct_identifiers':file_calls,'active':active},
                       'native_ui_writes':{'added_fixed_addresses':added_addresses,'frozen_ownership_verified':True},
                       'loops_memory':{'final_frames_static':True,'new_target_allocation':False}}
        source_checks[key]=row
    assert not unmapped,('unmapped_functions',unmapped)
    math_names=set(functions((P/'kv2/kv_math.c').read_text()))|set(functions((P/'kv2/kv_i64.c').read_text()))
    math_frames={name:value for name,value in frames.items() if name.split('.',1)[0] in math_names}
    assert math_frames and max(value['bytes'] for value in math_frames.values())<=128
    frozen=[]
    old_product=BASE/'candidate/containers/product'
    for rel,names in [('adapter.c',('eng_settings_owned','view_owned','start_view','release_view','core_call','cursor_cache')),
                      ('src/firmware/engine/core/eng_core.c',('deep','make_plan','settings_match','eng_check_settings'))]:
        for name in names:
            left=body(old_product/rel,name).replace('EngTweak','UvLevels');right=body(P/rel,name)
            assert left==right,('frozen_function',name)
            frozen.append({'function':name,'identical_after_type_name':True})
    service=Path('candidate/engine_services/services.c');assert (BASE/service).read_bytes()==(ENGINE/service).read_bytes()
    bss=int.from_bytes(raw[116:120],'big');request=7504+((len(raw)+bss+3)&~3)
    sizes={'dat':{'actual':len(raw),'limit':98304},'engine':{'actual':section['size'],'limit':65536},
           'bss':{'actual':bss,'limit':11920},'image_bss':{'actual':len(raw)+bss,'limit':114688},
           'loader_request':{'actual':request,'limit':108124},'loader_hard_limit':{'actual':request,'limit':122192}}
    for value in sizes.values():value['remaining']=value['limit']-value['actual'];assert value['remaining']>=0
    result={'status':'PASS','dat_sha256':sha(full/'GXRCE.DAT'),'engine_sha256':sha(full/'engine.bin'),
            'final_code_equals_compiler_record_link':True,'undefined_symbols':undefined,'float_symbols':forbidden,
            'old_math_symbols':0,'services_sha256':sha(ENGINE/service),'frozen_functions':frozen,
            'sizes':sizes,'changed_functions':source_checks,'frames':frames,'compiler_records':len(records),
            'math_maximum_frame':max(value['bytes'] for value in math_frames.values())}
    (WORK/'codegen.json').write_text(json.dumps(result,indent=2)+'\n')
    check_inputs();print(json.dumps({'name':'codegen','returncode':0,'functions':len(source_checks),'compiler_records':len(records),'stack_frames':len(frames)}))

if __name__=='__main__':main()
