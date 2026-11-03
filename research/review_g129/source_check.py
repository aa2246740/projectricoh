"""Compare frozen ownership code, final symbols, data gates, and heap models."""
from pathlib import Path
import hashlib
import json
import re
import runpy
import struct

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
OLD=ROOT/'firmware/engine_v48_own/candidate'
NEW=ROOT/'firmware/engine_v49_knobs/candidate'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def function(path,name):
    text=path.read_text()
    match=re.search(r'\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',text)
    assert match,(path.name,name)
    start=match.start();at=match.end();depth=1
    while depth:
        if text[at]=='{':depth+=1
        elif text[at]=='}':depth-=1
        at+=1
    return text[start:at]

def main():
    frozen=[]
    services='engine_services/services.c'
    assert (OLD/services).read_bytes()==(NEW/services).read_bytes()
    frozen.append({'file':services,'sha256':sha(NEW/services),'comparison':'byte_equal'})
    selected={
        'containers/product/adapter.c':('view_owned','eng_settings_owned','start_view','core_call','ingress','release_view'),
        'containers/product/src/firmware/engine/core/eng_core.c':('fresh','begin','end','deep','make_plan','settings_match','rebind_impl','validate_live'),
    }
    for file,names in selected.items():
        for name in names:
            before=function(OLD/file,name);after=function(NEW/file,name)
            if before!=after:
                raise AssertionError((file,name,'frozen_function_changed'))
            frozen.append({'file':file,'function':name,'sha256':hashlib.sha256(after.encode()).hexdigest(),'comparison':'byte_equal'})
    additional=[]
    checks={
        'containers/product/adapter.c':('record_failure','finish','keep_view','ui_finish','retry_view','deferred_menu'),
        'containers/product/src/firmware/engine/core/eng_core.c':('apply_impl','eng_confirm_live','eng_apply','eng_preview_saved','eng_select_saved','eng_check_settings'),
    }
    for file,names in checks.items():
        for name in names:
            before=function(OLD/file,name);after=function(NEW/file,name)
            normalized=before.replace('EngTweak','UvLevels')
            if name=='keep_view':
                normalized=normalized.replace('if(n.ui.screen==UV_VALUE)n.ui.cur=(uint8_t)(uv_max(n.ui.param)-n.ui.levels.v[n.ui.param]);','uv_value_realign();')
            assert normalized==after,(file,name,'ownership_body_changed')
            additional.append({'file':file,'function':name,'byte_equal':before==after,
                               'vector_type_name_only':before!=after and name!='keep_view',
                               'point_table_cursor_only':name=='keep_view',
                               'before_sha256':hashlib.sha256(before.encode()).hexdigest(),
                               'after_sha256':hashlib.sha256(after.encode()).hexdigest()})
    Elf=runpy.run_path(str(ROOT/'firmware/stage2l_switch/tools/build.py'))['Elf']
    elf=Elf(NEW/'local/full-r13/engine.elf')
    sections={item['name']:item['size'] for item in elf.sections if item['name'] in ('.engine','.bss','.data')}
    old_symbols=[name for name in elf.symbols if name.startswith(('rt_','compute_legacy','uv_from_tweak','uv_levels'))]
    assert not old_symbols and sections['.engine']==60388 and sections['.bss']==10684
    g=elf.symbols['g'];assert g['value']>=89308 and g['value']+g['size']<=89308+10684
    core=(NEW/'containers/product/src/firmware/engine/core/eng_core.c').read_text()
    assert core.count('KvWork work;')==1 and 'static Engine g;' in core
    math=(NEW/'containers/product/kv2/kv_math.c').read_text()
    writable_statics=[line.strip() for line in math.splitlines() if re.search(r'\bstatic\b',line) and ';' in line and '{' not in line and '(' not in line and 'const' not in line]
    assert not writable_statics
    build=(NEW/'containers/product/build.py').read_text()
    assert 'tweak_int.c' not in build and "'kv_math.c'" in build
    dat=(ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes()
    seventh=struct.unpack_from('>II',dat,128+12*6+4)
    assert seventh[1]==20776
    block=dat[seventh[0]+3392:seventh[0]+20776]
    assert len(block)==17384 and hashlib.sha256(block).hexdigest()=='43405f6c5f63050505e958882dcd260f2a9e1f707d3b407860041787964992f9'
    for name in ('current','confirmed','tweak','confirmed_tweak','live','staging','ready'):
        assert name in core
    assert 'g.confirmed_tweak=*t' in core and 'g.tweak=*t' in core and 't=g.confirmed_tweak' in core
    loader=(ROOT/'firmware/resident_v36/resident/loader.c').read_text()
    assert 's->image_address=address+RV_SESSION_BYTES' in loader and 'rv_clear(work+n,bytes-RV_SESSION_BYTES-n)' in loader
    budget=runpy.run_path(str(ROOT/'research/heap_headroom/budget.py'))
    Heap=budget['Heap'];baseline=budget['baseline']
    heap,allocations=baseline(107496)
    assert heap.summary()['free_extent_total']==152036
    census=json.loads((ROOT/'research/heap_headroom/call-census.json').read_text())
    isolated=[]
    for call in census['calls']:
        if call['name']!='system_alloc':continue
        model,_=baseline(107496);before=model.summary();pointer=model.alloc(call['r4'],tracked=True)
        assert pointer
        remaining=model.summary()['free_extent_total'];assert model.release(pointer) and model.summary()==before
        isolated.append({'call':call['pc'],'request':call['r4'],'remaining_extent':remaining})
    assert len(isolated)==12
    retained=[]
    for request in (75124,107496):
        model,_=baseline(request)
        for _ in range(3):assert model.alloc(32768,tracked=True)
        before=model.summary();succeeded=bool(model.alloc(77312,tracked=True))
        retained.append({'main_request':request,'before_large_request':before,'large_success':succeeded})
    assert retained[0]['large_success'] and not retained[1]['large_success']
    scenarios=[]
    for label,requests in [('events',[8560,8560,8560,16384,938,77312,4608,12368]),
                           ('adjustment',[32768,16384,938,77312,4608,12368]),
                           ('reader',[32768,16384,938,77312,4608,12368,32768])]:
        model,_=baseline(107496);steps=[]
        for request in requests:steps.append({'request':request,'success':bool(model.alloc(request,tracked=True)),**model.summary()})
        scenarios.append({'name':label,'steps':steps})
    assert scenarios[1]['steps'][-1]['free_extent_total']==7512 and not scenarios[2]['steps'][-1]['success']
    fragment=Heap();arrangement=[(77312,False),(8560,True),(32768,False),(16384,True),(25452,False),(938,True),(32768,True),(4608,False),(8560,True)]
    held=[]
    for request,keep in arrangement:
        pointer=fragment.alloc(request,tracked=True);assert pointer;held.append((pointer,keep))
    for pointer,keep in held:
        if not keep:assert fragment.release(pointer)
    assert fragment.alloc(608)
    fragmented=fragment.summary();new=fragment.alloc(107496);old=fragment.alloc(75124)
    assert not new and old and fragmented['largest_free_extent']==76716
    value={'status':'PASS','dat_sha256':hashlib.sha256(dat).hexdigest(),'frozen_functions':frozen,
           'additional_ownership_checks':additional,
           'sections':sections,'engine_global':g,'old_math_symbols':len(old_symbols),
           'kvwork_declarations':1,'math_writable_statics':len(writable_statics),
           'seventh_section':{'offset':seventh[0],'bytes':seventh[1],'integer_block_bytes':len(block)},
           'main_request':107496,'request_delta_from_g127':32372,'format_margin':14696,
           'continuous_heap':{'allocations':allocations,**heap.summary()},'conditional_models':scenarios,
           'isolated_native_calls':isolated,'three_retained_buffers':retained,
           'fragmented_heap':fragmented,'fragmented_new_success':bool(new),'fragmented_old_success':bool(old),
           'evidence_scope':'Static source, final ELF, packaged DAT, and host allocator model.'}
    (WORK/'source-results.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'name':'source_and_heap','returncode':0,'frozen_functions':len(frozen),'old_math_symbols':0}))

if __name__=='__main__':main()
