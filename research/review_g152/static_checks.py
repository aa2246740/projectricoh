"""Inspect final DAT bytes, linked code, candidate history and frozen receipts."""
from pathlib import Path
import difflib
import hashlib
import importlib.util
import itertools
import json
import struct
import subprocess
import time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=ROOT/'research/review_g152'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g152/static')
PRODUCT=ROOT/'firmware/engine_v60_g152/candidate/containers/product'
SOURCE=ROOT/'research/looks_g152'
sha=lambda b:hashlib.sha256(b).hexdigest()
u32=lambda b,o:struct.unpack_from('>I',b,o)[0]


def elf_sections(path):
    raw=path.read_bytes()
    assert raw[:6]==b'\x7fELF\x01\x02'
    start=u32(raw,32)
    width,count,names=struct.unpack_from('>3H',raw,46)
    headers=[struct.unpack_from('>10I',raw,start+i*width) for i in range(count)]
    name_header=headers[names]
    strings=raw[name_header[4]:name_header[4]+name_header[5]]
    result={}
    for row in headers:
        name=strings[row[0]:].split(b'\0',1)[0].decode()
        result[name]=dict(size=row[5],bytes=raw[row[4]:row[4]+row[5]],address=row[3])
    return result


def main():
    from dat_format import sections,expand,expand_effect,strict_effects,CRC_FIELDS
    tick=time.monotonic()
    started=time.time_ns()
    release=ROOT/'firmware/package_v38_g152/local/SD_ROOT'
    test=ROOT/'firmware/package_v38_g152_test/local/SD_ROOT'
    old=ROOT/'firmware/package_v38_g150/local/SD_ROOT'
    raw=(release/'GXRCE.DAT').read_bytes()
    tested=(test/'GXRCE.DAT').read_bytes()
    se=sections(raw)
    sections(tested)
    assert len(raw)==len(tested)==90156 and u32(raw,28)==152
    assert strict_effects(raw)==strict_effects(tested)
    assert se[0][0]==256
    linked=elf_sections(ROOT/'firmware/engine_v60_g152/candidate/local/full-r13/engine.elf')
    at,n=se[0]
    assert raw[at:at+n]==tested[at:at+n]==linked['.engine']['bytes']
    assert n==63896 and u32(raw,116)==linked['.bss']['size']==9252
    assert 7504+((len(raw)+u32(raw,116)+3)&~3)==106912<=107612
    bodies=[]
    for p in sorted(old.iterdir()):
        if p.is_file() and p.name!='GXRCE.DAT':
            assert p.read_bytes()==(release/p.name).read_bytes()==(test/p.name).read_bytes()
            bodies.append(dict(name=p.name,sha256=sha(p.read_bytes())))
    assert len(bodies)==29
    for i in (0,1,2,3,4,5):
        a,z=se[i]
        assert raw[a:a+z]==tested[a:a+z]
    mount=[]
    oldraw=(old/'GXRCE.DAT').read_bytes()
    for slot in range(1,9):
        current=expand(raw,2,slot)
        assert current==expand(oldraw,2,slot)
        actual=[current[a:a+n] for a,n,_ in CRC_FIELDS]
        ref=expand(raw,0,slot)
        fifty=[ref[a:a+n] for a,n,_ in CRC_FIELDS]
        if slot not in (4,6): assert actual==fifty
        if slot==6:
            assert all(a==b for i,(a,b) in enumerate(zip(actual,fifty)) if i!=6)
            assert current[1]==1 and current[445:447]==b'\0\2'
            assert current[379:445]==expand(raw,2,4)[379:445]
        mount.append(dict(slot=slot,unchanged_from_g150=True,rows_equal_50mm=actual==fifty,
                          entry_sha256=sha(current)))
    effects=[]
    for i in range(10):
        entry=expand_effect(raw,i)
        assert entry==expand_effect(tested,i)
        assert entry[20:115]==entry[456:551]
        for a,n,field in CRC_FIELDS:
            import zlib
            assert u32(entry,field)==zlib.crc32(entry[a:a+n])&0xffffffff
        if i==2: assert entry[115:211]==bytes(96)
        effects.append(dict(effect=i+1,base=entry[0],entry_sha256=sha(entry),A14_B14_equal_A5_B5=True))
    earlier=SOURCE/'local/earlier-candidate-159d'
    archive_files=0
    for line in (earlier/'SHA256SUMS').read_text().splitlines():
        value,name=line.split(maxsplit=1)
        assert sha((earlier/name.lstrip('* ')).read_bytes())==value
        archive_files+=1
    assert archive_files==354
    older_core=(earlier/'eng_core.c').read_text()
    final_core=(PRODUCT/'src/firmware/engine/core/eng_core.c').read_text()
    normalized=final_core.replace('    /* A boot may hold stock rows with T=0. Validate observed row structure\n     * independently from the target recipe\'s T/C/D relationship. */\n','')
    normalized=normalized.replace('fx_row_valid(g.live+at[row],row,0)','fx_row_valid(g.live+at[row],row,g.live[1])')
    assert normalized==older_core
    changes=list(difflib.unified_diff(older_core.splitlines(True),final_core.splitlines(True),fromfile='earlier/eng_core.c',tofile='final/eng_core.c'))
    (OUT/'candidate-change.diff').write_text(''.join(changes))
    oldlayout=json.loads((earlier/'build/layout.json').read_text())
    newlayout=json.loads((ROOT/'firmware/engine_v60_g152/candidate/local/full-r13/layout.json').read_text())
    for key in ('flags','tools','profile','lto','no_sha_runtime','service_archive_sha256'):
        assert oldlayout[key]==newlayout[key],key
    changed_sources=[]
    for group in ('sources','headers'):
        assert oldlayout[group].keys()==newlayout[group].keys()
        changed_sources.extend(k for k in oldlayout[group] if oldlayout[group][k]!=newlayout[group][k])
        for k,v in newlayout[group].items(): assert sha((ROOT/k).read_bytes())==v
    assert changed_sources==['firmware/engine_v60_g152/candidate/containers/product/src/firmware/engine/core/eng_core.c']
    old_locks=[json.loads(p.read_text()) for p in (earlier/'evidence').glob('lock-*.json')
               if p.name not in ('lock-matrix-50mm.json','lock-matrix-mount.json')]
    old_locks=[v for v in old_locks if 'transition' in v]
    assert len(old_locks)==144 and all(v['status']=='PASS' for v in old_locks)
    transitions=('builtin-effect','effect-same-base','effect-other-base','effect-builtin')
    timings=('held','race-at-s','transient','record-busy','after-check-held','during-rows-release')
    assert {(v['unit'],v['transition'],v['timing'],v['exit']) for v in old_locks}==set(itertools.product(
        ('50mm','mount'),transitions,timings,('ok','half','menu')))
    old_ids={v['dat_sha256'] for v in old_locks}
    assert old_ids=={'eb04787df5a62807fd5980e81717207285c637265d97f8a09e29486072eedbb3'}
    current_locks=[json.loads(p.read_text()) for p in (SOURCE/'evidence').glob('lock-testcard-*.json')]
    cases=[v for v in current_locks if 'transition' in v]
    assert len(cases)==48 and all(v['status']=='PASS' and v['dat_sha256']==sha(tested) for v in cases)
    assert {(v['unit'],v['transition'],v['timing'],v['exit']) for v in cases}==set(itertools.product(
        ('50mm','mount'),transitions,('held','race-at-s','transient'),('ok','half')))
    for v in cases:
        for key in ('rows','T','S_sha256','ref_sha256'):
            assert v['before'][key]==v['after_key'][key]==v['after_exit'][key]==v['after_reopen'][key]
    # Save disassembly from both linked artifacts. Final code, rather than
    # source comments, remains available for checking the changed call site.
    TMP.mkdir(parents=True,exist_ok=True)
    fields={
        'session':'sizeof(RvSession)', 'overhead':'RV_BLOCK_OVERHEAD',
        'ref.bytes':'sizeof(EngRecipeRef)', 'ui':'offsetof(Integrated,ui)',
        'ui.text':'offsetof(UvState,text)', 'ui.frame':'offsetof(UvState,frame)',
        'adapter_text_bytes':'sizeof(((UvState *)0)->text)',
        'frame_text_bytes':'sizeof(((KvUiFrame *)0)->text)',
        'line_bytes':'sizeof(((KvUiFrame *)0)->text[0])',
    }
    for key in ('current','confirmed','live','staging','baseline','committed','uncertain','live_verified','snapshot_fault'):
        fields['g.'+key]='offsetof(Engine,'+key+')'
    source='#include <stddef.h>\n#include "'+str(PRODUCT/'adapter.c')+'"\n#include "'+str(PRODUCT/'src/firmware/engine/core/eng_core.c')+'"\n'
    source+='const unsigned review_dimensions[]={'+','.join(fields.values())+'};\n'
    (TMP/'dimensions.c').write_text(source)
    compiler=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    subprocess.run([str(compiler),'-std=c11','-Oz','-ffreestanding','-fno-builtin','-fpic','-m32r','-I',str(PRODUCT),
                    '-c',str(TMP/'dimensions.c'),'-o',str(TMP/'dimensions.o')],capture_output=True,check=True,timeout=2400)
    spec=importlib.util.spec_from_file_location('review_elf',ROOT/'firmware/stage2l_switch/tools/build.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    obj=module.Elf(TMP/'dimensions.o')
    symbol=obj.symbols['review_dimensions']
    values=obj.content(obj.sections[symbol['section']])[symbol['value']:symbol['value']+symbol['size']]
    dimensions=dict(zip(fields,struct.unpack('>'+str(len(fields))+'I',values)))
    assert (dimensions['session'],dimensions['overhead'],dimensions['ref.bytes'])==(1104,7504,56)
    assert (dimensions['adapter_text_bytes'],dimensions['frame_text_bytes'],dimensions['line_bytes'])==(112,112,14)
    reported=json.loads((SOURCE/'layout.json').read_text())
    for key in set(dimensions)&set(reported): assert dimensions[key]==reported[key]
    objdump=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    for label,path in (('earlier',earlier/'build/engine.elf'),('final',ROOT/'firmware/engine_v60_g152/candidate/local/full-r13/engine.elf')):
        proc=subprocess.run([str(objdump),'-d',str(path)],capture_output=True,text=True,check=True,timeout=2400)
        (TMP/(label+'.asm')).write_text(proc.stdout)
    result=dict(status='PASS',started_ns=started,ended_ns=time.time_ns(),seconds=time.monotonic()-tick,
                dat_sha256=sha(raw),test_dat_sha256=sha(tested),code_equals_linked_ELF=True,
                dimensions=dict(file_bytes=len(raw),code_bytes=se[0][1],bss_bytes=9252,main_request=106912,main_limit_margin=700),
                body_files=bodies,effects=effects,mount=mount,changed_sources=changed_sources,
                previous_candidate_lock_cases=len(old_locks),final_candidate_lock_cases=len(cases),
                previous_archive_files_verified=archive_files,target_structure_constants=dimensions,
                compiler_flags_tools_and_service_archive_unchanged=True,
                old_candidate_DATs=sorted(old_ids),scope='Independent final bytes and receipt consistency. Existing native receipts are not new executions.')
    (OUT/'static_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('body_files','effects','mount')}),flush=True)


if __name__=='__main__': main()
