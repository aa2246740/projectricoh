#!/usr/bin/python3
"""Bind the source change and four review categories to the final engine."""
from pathlib import Path
import difflib,hashlib,json,re,struct,subprocess
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
OLD=ROOT/'firmware/engine_v47_fix/candidate'
NEW=ROOT/'firmware/engine_v48_own/candidate'
FULL=NEW/'local/full-r13'
DAT=ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
OUT=WORK/'local/release127/review_g126'
OUT.joinpath('evidence').mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def functions(text):
    masked=re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:''.join('\n' if x=='\n' else ' ' for x in m.group()),text,flags=re.S)
    result={}
    for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(',masked):
        name=m.group(1)
        if name in ('if','for','while','switch','sizeof','__attribute__'):continue
        at=masked.index('(',m.start());depth=1;end=at+1
        while end<len(masked) and depth:
            depth+=(masked[end]=='(')-(masked[end]==')');end+=1
        while end<len(masked) and masked[end].isspace():end+=1
        if end>=len(masked) or masked[end]!='{':continue
        depth=1;stop=end+1
        while stop<len(masked) and depth:
            depth+=(masked[stop]=='{')-(masked[stop]=='}');stop+=1
        start=masked.rfind('\n',0,m.start())+1
        result[name]=(text[start:stop],text.count('\n',0,start)+1)
    return result

changes=[];patch=[];old_functions={};new_functions={}
for p in sorted(NEW.rglob('*')):
    rel=p.relative_to(NEW)
    if 'local' in rel.parts or p.suffix not in ('.c','.h'):continue
    previous=OLD/rel
    if not p.is_file() or not previous.is_file():continue
    a=previous.read_text();b=p.read_text()
    if p.suffix=='.c':
        old=functions(a);new=functions(b)
        old_functions.update({(str(rel),k):v[0] for k,v in old.items()})
        new_functions.update({(str(rel),k):v[0] for k,v in new.items()})
        for name,(body,line) in new.items():
            if name not in old or body!=old[name][0]:
                changes.append({'file':str(rel),'function':name,'line':line,'source_sha256':hashlib.sha256(body.encode()).hexdigest()})
    if a!=b:patch.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='firmware/engine_v47_fix/candidate/'+str(rel),tofile='firmware/engine_v48_own/candidate/'+str(rel),n=2))
(WORK/'source-change-vs-g126.patch').write_text(''.join(patch))
expected={'eng_settings_owned','eng_check_settings','apply_impl','rv_settings_owned','settings','rv_service','gxr2_tweak_layout','eng_data_accept','uv_validate'}
assert {x['function'] for x in changes}==expected,{x['function'] for x in changes}
preserved={}
for name in ('deep','rpc','t_read','t_store','write_word','recover_confirmed','make_plan','settings_match','rebind_impl','eng_require_recheck','record_failure','storage','validate_live','list_bind_impl','ig_event','ig_init'):
    keys=[k for k in old_functions if k[1]==name]
    assert keys,name
    preserved[name]=all(old_functions[k]==new_functions.get(k) for k in keys)
    assert preserved[name],name
elf=(FULL/'engine.elf').read_bytes()
assert elf[:6]==b'\x7fELF\x01\x02'
shoff=struct.unpack_from('>I',elf,32)[0]
entsize,count,names=struct.unpack_from('>HHH',elf,46)
sections=[struct.unpack_from('>10I',elf,shoff+i*entsize) for i in range(count)]
strings=elf[sections[names][4]:sections[names][4]+sections[names][5]]
def label(data,offset):return data[offset:data.index(0,offset)].decode()
engine_index=next(i for i,s in enumerate(sections) if label(strings,s[0])=='.engine')
engine=sections[engine_index]
assert elf[engine[4]:engine[4]+engine[5]]==(FULL/'engine.bin').read_bytes()
raw=DAT.read_bytes();assert int.from_bytes(raw[28:32],'big')==127
assert raw.count((FULL/'engine.bin').read_bytes())==1
symbols={}
for s in sections:
    if s[1]!=2:continue
    st=sections[s[6]];text=elf[st[4]:st[4]+st[5]]
    for at in range(s[4],s[4]+s[5],s[9]):
        name,value,size,info,other,index=struct.unpack_from('>IIIBBH',elf,at)
        if info&15==2 and index==engine_index and size:
            symbols[label(text,name)]={'address':value,'size':size,'section':index}
tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
assembly=subprocess.check_output([str(tool),'-d','-j','.engine',str(FULL/'engine.elf')],text=True)
(WORK/'local/final-engine-disassembly.txt').write_text(assembly)
spans={}
for name,row in symbols.items():
    lines=[];anomalies=[]
    for line in assembly.splitlines():
        match=re.match(r'\s*([0-9a-f]+):\s+(.*)',line)
        if match and row['address']<=int(match.group(1),16)<row['address']+row['size']:
            lines.append(line)
            if '(bad)' in line or '.word' in line or '.short' in line:anomalies.append(match.group(1))
    spans[name]={**row,'disassembly_sha256':hashlib.sha256('\n'.join(lines).encode()).hexdigest(),'anomalies':anomalies}
frames={}
for p in (NEW/'local/product-r13/m32r-lto').glob('*.su'):
    for line in p.read_text().splitlines():
        cells=line.split('\t')
        if len(cells)>=3 and cells[1].isdigit():frames[cells[0].rsplit(':',1)[-1]]={'bytes':int(cells[1]),'kind':cells[2]}
assert frames and all(x['kind']=='static' for x in frames.values())
manifest=json.loads((FULL/'manifest.json').read_text())
size=json.loads((NEW/'local/product-r13/m32r-lto/size.json').read_text())
binding={'status':'PASS','dat_sha256':sha(DAT),'elf_sha256':sha(FULL/'engine.elf'),'engine_bytes':engine[5],
         'dat_engine_elf_equal':True,'changed_functions':changes,'compiled_spans':spans,
         'critical_functions_preserved':preserved,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in NEW.rglob('*') if p.is_file() and 'local' not in p.relative_to(NEW).parts and p.suffix in ('.c','.h','.S','.ld')},
         'baseline_generation':126,'camera_acceptance':False}
(OUT/'evidence/static-audit.json').write_text(json.dumps(binding,indent=2)+'\n')
(WORK/'evidence/source-and-binary.json').write_text(json.dumps(binding,indent=2)+'\n')
carriers={'eng_settings_owned':['eng_settings_owned','eng_check_settings','apply_impl.constprop.0'],'eng_check_settings':['eng_check_settings'],'apply_impl':['apply_impl.constprop.0'],
          'rv_settings_owned':['rv_settings_owned'],'settings':['rv_call'],'rv_service':['rv_call'],
          'gxr2_tweak_layout':['ig_init'],'eng_data_accept':['ig_init'],'uv_validate':['ig_init']}
categories={
 'address_length':'既有 settings 租约、最多 16 个计划字段及 S 偏移保持不变。新归属函数只读列表、会话、view epoch、activity 8 和 state 56。临时列表为固定 40 B。',
 'file_operations':'storage 和文件调用函数逐字不变。新增检查及延后分支没有存储服务调用。运行记录另核对文件计数。',
 'native_UI':'settings 最终写入前在原 IRQ 区间核对请求的 view epoch 及原生归属。preview 在原生入口前核对。未归属时只留待核对标记；列表发布及 H07 共用核对入口。末端 preview 调度窗口单列。',
 'loops_memory':'新增归属检查及延后分支没有循环和分配。原 16 字段、九行、导航及 4+2 次补偿界限不变。新标记沿用私有 BSS。静态帧来自本次编译。'}
review=[]
for row in changes:
    targets=carriers[row['function']]
    found=[]
    for target in targets:
        found.extend({'symbol':k,**v} for k,v in spans.items() if k==target or k.split('.constprop.')[0]==target.split('.constprop.')[0])
    assert found,row
    review.append({**row,'compiled':found,**categories})
result={'status':'STATIC_CATEGORIES_CLOSED_RUNTIME_REQUIRED','dat_sha256':sha(DAT),'baseline_generation':126,
        'reviews':review,'stack':frames,'maximum_static_frame':max(x['bytes'] for x in frames.values()),
        'engine_bytes':engine[5],'file_bytes':len(raw),'build_size':size,
        'unchanged_source_functions':preserved,'runtime_acceptance':'see acceptance.json',
        'scope':'最终源码与最终 ELF 的四类静态检查。运行结果、通信及保留窗口分别列明；不代表相机或 RTOS 验收。'}
(WORK/'evidence/codegen-four-categories.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'PASS','functions':len(changes),'engine_bytes':engine[5],'maximum_static_frame':result['maximum_static_frame'],'dat_sha256':sha(DAT)}))
