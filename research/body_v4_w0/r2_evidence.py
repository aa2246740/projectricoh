"""Collect/verify W0 r2 compile/link evidence and seal both authorized trees.

Run with /usr/bin/python3 -I -B from the repository root. This script emits no
body image, DAT, card output or network requests. Ricoh bytes stay under local/.
"""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import struct
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FW=ROOT/'firmware/resident_v4'
spec=importlib.util.spec_from_file_location('w0_r2_builder',FW/'build.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
LOCAL=HERE/'local/r2-evidence'


def load(path):return json.loads(path.read_text())


def protected():
    original=load(HERE/'local/inputs-before.json')
    extra=load(HERE/'local/r2-extra-inputs.json')['files']
    wanted={**original,**extra};changed=[p for p,h in wanted.items() if b.sha(ROOT/p)!=h]
    assert not changed,('protected inputs changed',changed)
    snapshot=load(HERE/'local/r1-snapshot.json')['files']
    for p,h in snapshot.items():
        path=ROOT/p;base=FW if path.is_relative_to(FW) else HERE
        saved=base/'local/r1'/path.relative_to(base)
        assert b.sha(saved)==h,('r1 snapshot altered',saved)
    return dict(registered_inputs=len(wanted),changed=[],r1_files_preserved=len(snapshot))


def image(path):
    raw=path.read_bytes();sections=[struct.unpack_from('>5I',raw,0x20+i*20) for i in range(16)]
    def read(address,n):
        for source,base,size,_,_ in sections:
            if base<=address and address+n<=base+size:
                off=source+0x200+address-base;return raw[off:off+n],off
        raise AssertionError(('not file-backed',hex(address),n))
    return raw,read


def native_evidence():
    official=ROOT/'artifacts/firmware/gxr-1.51/ilaunch3'
    fixed=ROOT/'firmware/image_v36/local/body-v36/candidate/SD_ROOT/ilaunch3'
    raw,read=image(official);_,read_fixed=image(fixed);assert len(raw)==3993340
    windows=[('heap-config',0x200c0dc0,64),('heap-init',0x2005bf00,92),
             ('heap-alloc',0x2005bf5c,220),('heap-free-window',0x2005c038,144),
             ('storage-task-boot-window',0x2010ddc4,128),('media-init-window',0x2010e14c,128)]
    LOCAL.mkdir(parents=True,exist_ok=True);(LOCAL/'tmp').mkdir(exist_ok=True)
    b.LOCAL=LOCAL;b.commands=[];rows=[]
    for name,address,n in windows:
        data,offset=read(address,n);other,other_offset=read_fixed(address,n);assert other==data
        path=LOCAL/(name+'.bin');path.write_bytes(data)
        if name!='heap-config':
            disassembly=b.run([b.OBJDUMP,'-EB','-D','-b','binary','-m','m32r',f'--adjust-vma={address}',path],name)
            if name.startswith('heap-'):assert '*unknown*' not in disassembly.stdout,name
        rows.append(dict(window=name,address=hex(address),bytes=n,official_file_offset=hex(offset),
                         fixed_file_offset=hex(other_offset),sha256=hashlib.sha256(data).hexdigest(),
                         official_equals_fixed=True,raw=str(path.relative_to(ROOT))))
    config,_=read(0x200c0dc0,8);begin,size=struct.unpack('>2I',config)
    assert (begin,size)==(0x20704800,0x40000)
    result=dict(status='STATIC_CURRENT_INPUT_WINDOWS_ONLY',official_file_bytes=len(raw),
        official_sha256=b.sha(official),fixed_sha256=b.sha(fixed),windows=rows,
        main_heap=dict(begin=hex(begin),end=hex(begin+size),total_bytes=size,
                       allocation='0x2005bf5c',free='0x2005c038',initialize='0x2005bf00'),
        permanent_heap_lifetime_proven=False,other_raw_writers_excluded=False,
        early_hook_barrier_proven=False,free_space_or_maximum_contiguous_block_measured=False,
        previous_camera_evidence='decisions.tsv:295, user-reported P0 one-shot execution, not repeated')
    b.write(HERE/'ram-evidence.json',result)
    return result


def compression():
    names=['local/r1/size.json','local/a-iterations/a1-tables/size.json',
           'local/a-iterations/a2-validation/size.json','size.json']
    results=[load(HERE/n) for n in names]
    obligations=[
        '只比较 -Os/-Oz/inline 选项；未删除代码、门禁或预算。',
        '元数据保留全部 36 个地址与目录顺序；所有 32 B 桩和安全续程保留。事件表保留同一失效集合；DAT 调用仍由 rv4_call 在入口和返回后校验。',
        '固定版本字段改为表驱动；连续 80 B 身份一次比较；十六入口一次解码，失败时清空结果。长度、CRC、重定位和保留字段检查保留。',
        'DAT 调用与 host 服务共用 wire 身份检查；owner、IRQ、pin、状态和返回检查留在原边界。固定且对齐的三个 unit-info 字用 M32R 大端 word 读取。'
    ]
    rows=[]
    for index,name in enumerate(('r1','a1-tables','a2-validation','a3-final')):
        now=results[index];previous=results[index-1] if index else now
        changed={key:previous['linked_objects'].get(key,0)-now['linked_objects'].get(key,0)
                 for key in set(previous['linked_objects'])|set(now['linked_objects'])}
        rows.append(dict(iteration=name,payload_bytes=now['payload_bytes'],
            saved_bytes=previous['payload_bytes']-now['payload_bytes'],
            object_savings={k:v for k,v in sorted(changed.items()) if v},
            obligation=obligations[index],evidence=names[index]))
    result=dict(initial_payload=results[0]['payload_bytes'],final_payload=results[-1]['payload_bytes'],
        saved_total=results[0]['payload_bytes']-results[-1]['payload_bytes'],iterations=rows,
        compiler_profiles=load(HERE/'compiler-sweep.json'),selected_flags=results[-1]['flags'],
        unimplemented_gates_moved_to_DAT=False,reserve_consumed=False)
    b.write(HERE/'compression.json',result)
    return result


def artifacts():
    a=load(HERE/'size.json');c=load(HERE/'arch-b-size.json')
    ae=b.Elf(FW/'local/resident.elf');ce=b.Elf(FW/'arch_b/local/window.elf')
    for data,elf,path in ((a,ae,FW/'local/resident.elf'),(c,ce,FW/'arch_b/local/window.elf')):
        payload=next(s for s in elf.sections if s['name']=='.payload')
        assert payload['size']==data['payload_bytes'] and b.sha(path)==data['elf_sha256']
        assert sum(data['linked_objects'].values())+data['padding']==payload['size']
        assert 8340-data['root_bytes']-data['mandatory_reserve']-payload['size']==data['margin_after_reserve']
        assert data['mandatory_reserve']==200 and data['root_bytes']==512
        assert data['unresolved']==[] and data['relocations']==[] and data['extra_writable']==[]
        assert len(data['thunks'])==36 and set(data['thunks'].values())=={32}
    assert a['strict_link_returncode']==1 and a['status']=='FAIL_SIZE' and not a['installable']
    assert c['strict_link_returncode']==0 and c['status']=='PASS_SIZE_MINIMAL_WINDOW' and not c['installable']
    assert 'payload exceeds 7628B' in (FW/'local/strict-link.log').read_text()
    assert (FW/'arch_b/local/strict-link.log').read_text()==''
    assert load(FW/'generated/target-layout.json')==load(FW/'local/r1/generated/target-layout.json')
    assert a['flags']==b.FLAGS and c['flags']==b.FLAGS,'compiler profile changed since target build'
    retained={n:ce.symbols[n]['size'] for n in ('bv4_boot_native','bv4_boot','bv4_header','bv4_relocate','bv4_sha256','bv4_hook_observe','bv4_native_scope','bv4_native_lifetime')}
    assert all(retained.values())
    for n,expect in (('bv4_platform',bytes(16)),):
        s=ce.symbols[n];section=ce.sections[s['section']];offset=s['value']-section['address']
        assert ce.content(section)[offset:offset+s['size']]==expect
    trust=ce.symbols['bv4_trust'];section=ce.sections[trust['section']]
    offset=trust['value']-section['address'];raw=ce.content(section)[offset:offset+trust['size']]
    assert raw[80:]==bytes(36),'target extension pin must remain unapproved'
    assert not any(x.startswith('-flto') for x in c['flags']) and '-Os' in c['flags']
    tests={}
    for name,elf_sha in (('host-tests.json',None),('machine-tests.json',b.sha(FW/'local/resident-host-machine.elf')),
                         ('arch-b-host-tests.json',c['elf_sha256']),('arch-b-machine-tests.json',c['elf_sha256'])):
        result=load(HERE/name);assert result['status'].startswith('PASS'),name
        if name=='machine-tests.json':assert result['elf_sha256']==elf_sha
        if name=='arch-b-host-tests.json':assert result['target_window_elf_sha256']==elf_sha
        if name=='arch-b-machine-tests.json':assert result['exact_window_elf_sha256']==elf_sha
        for p,h in result.get('inputs',{}).items():assert b.sha(ROOT/p)==h,('stale test input',name,p)
        for p,h in result.get('sources',{}).items():assert b.sha(ROOT/p)==h,('stale test source',name,p)
        if 'host-tests' in name:
            driver=FW/'arch_b/test_host.py' if name.startswith('arch-b') else FW/'test_host.py'
            assert result['driver_sha256']==b.sha(driver),('stale test driver',name)
        else:
            driver=FW/'arch_b/test_machine.py' if name.startswith('arch-b') else FW/'test_machine.py'
            assert result['inputs'][str(driver.relative_to(ROOT))]==b.sha(driver),('stale machine driver',name)
        tests[name]=dict(status=result['status'],total=result.get('total'),hardware=False)
    assert load(HERE/'host-tests.json')['target_identity']==load(FW/'generated/identity.json')
    for p,h in c['sources'].items():assert b.sha(ROOT/p)==h,('stale B target source',p)
    return dict(architecture_a=dict(payload=a['payload_bytes'],margin_after_reserve=a['margin_after_reserve'],strict_link_returncode=1),
                architecture_b=dict(payload=c['payload_bytes'],margin_after_reserve=c['margin_after_reserve'],strict_link_returncode=0,retained_symbols=retained),
                a_target_abi_layout_unchanged=True,tests=tests)


def collect():
    b.preflight();native_evidence();compression()
    result=dict(task='body-v4-w0-size-r2',status='PASS_EVIDENCE_WITH_A_SIZE_FAILURE_AND_B_INTEGRATION_OPEN',
        driver_sha256=b.sha(Path(__file__)),
        protected=protected(),artifacts=artifacts(),
        boundaries=dict(body_image_generated=False,DAT_generated=False,camera_access=False,card_access=False,
                        network_access=False,subagents_started=False),
        tool_corrections=['compiler sweep initially narrowed its own write fence; fixed to the two authorized directory roots',
                          'B interpreter test initially expected stop reason returned; corrected to the backend return value',
                          'raw-binary native disassembly initially used tool default endian; corrected to explicit -EB and reject unknown heap instructions',
                          'B native boot wrapper had misaligned 32-bit replay; bounded M32R test caught the invalid pair; explicit nop and alignment added, failed artifact retained under arch_b/local/history'],
        verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    b.write(HERE/'verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))


def seal():
    protected();artifacts();assert (HERE/'REPORT.md').exists()
    assert load(HERE/'verification.json')['driver_sha256']==b.sha(Path(__file__)),'rerun collect after evidence-driver changes'
    entries=[]
    for base in (FW,HERE):
        for path in sorted(base.rglob('*')):
            assert not path.is_symlink(),('symlink in delivery',path)
            if path.is_file() and path!=HERE/'SHA256SUMS':
                entries.append((str(path.relative_to(ROOT)),b.sha(path)))
    (HERE/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(entries)))
    print('SEALED',len(entries),'files; paths relative to repository root')


def verify():
    entries=(HERE/'SHA256SUMS').read_text().splitlines();seen=set()
    for row in entries:
        h,p=row.split('  ',1);path=ROOT/p
        assert not Path(p).is_absolute() and '..' not in Path(p).parts
        assert path.is_relative_to(FW) or path.is_relative_to(HERE)
        assert p not in seen;seen.add(p);assert b.sha(path)==h,('hash mismatch',p)
    expected={str(p.relative_to(ROOT)) for base in (FW,HERE) for p in base.rglob('*')
              if p.is_file() and p!=HERE/'SHA256SUMS'}
    assert seen==expected,('manifest coverage mismatch',seen^expected)
    assert load(HERE/'verification.json')['driver_sha256']==b.sha(Path(__file__))
    print('PASS',len(entries),'SHA256 entries;',protected());print(json.dumps(artifacts(),ensure_ascii=False,indent=2))


if __name__=='__main__':
    {'collect':collect,'seal':seal,'verify':verify}[sys.argv[1]]()
