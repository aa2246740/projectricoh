"""Final resident/body instruction, byte-boundary and stack evidence."""
import ast
import importlib.util
import itertools
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local/evidence-v34b'
IMAGE=ROOT/'firmware/image_v34b/local/body-final-v34b/candidate'

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def save(name,value):
    LOCAL.mkdir(parents=True,exist_ok=True);(LOCAL/name).write_text(json.dumps(value,indent=2)+'\n')
def sha(b):
    import hashlib
    return hashlib.sha256(b).hexdigest()
def image_at(b,va,n):
    for i in range(16):
        off,start,size,_,_=struct.unpack_from('>5I',b,32+20*i)
        if start<=va and va+n<=start+size:return b[512+off+va-start:512+off+va-start+n]
    raise AssertionError((va,n))

def body():
    official=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    prior=(ROOT/'firmware/image_v33/local/package_final/SD_ROOT/ilaunch3').read_bytes()
    b=(IMAGE/'SD_ROOT/ilaunch3').read_bytes();assert len(b)==len(prior)==len(official)
    allowed=set(range(0x16c,0x174));window_start=None
    assert image_at(official,0x2005276c,8340)==b'\xff'*8340
    # Derive the offset rather than accepting a hard-coded file-to-VA relationship.
    for i in range(16):
        off,va,n,_,_=struct.unpack_from('>5I',official,32+20*i)
        if va<=0x2005276c<va+n:window_start=512+off+0x2005276c-va
    allowed.update(range(window_start,window_start+8340))
    hooks=json.loads((HERE/'local/hooks.json').read_text())
    for h in hooks:
        if h['number'] in (1,2,5,6,7,8,9):allowed.update(range(int(h['file_offset'],16),int(h['file_offset'],16)+h['length']))
        elif h['number']>=10:assert image_at(b,int(h['va'],16),h['length'])==bytes.fromhex(h['original_bytes'])
    differences=[i for i,(x,y) in enumerate(zip(prior,b)) if x!=y]
    assert all(i in allowed for i in differences)
    windows=json.loads((ROOT/'research/review_flash_v33/local/recovery.json').read_text())['update_windows']
    for w in windows:
        p=image_at(b,int(w['va'],16),w['bytes']);assert p==image_at(official,int(w['va'],16),w['bytes']) and sha(p)==w['sha256']
    trial=ROOT/'artifacts/v32-trial/full-r3-20261024/SD_ROOT'
    if not trial.exists():
        matches=list((ROOT/'artifacts/v32-trial/full-r3-20261024').rglob('ilaunch3'));assert len(matches)==1
        trial=matches[0].parent
    policy=json.loads((ROOT/'firmware/image_v34b/policy.json').read_text())
    for n,digest in policy['official'].items():
        if n=='ilaunch3':continue
        assert (IMAGE/'SD_ROOT'/n).read_bytes()==(trial/n).read_bytes()
        assert sha((IMAGE/'SD_ROOT'/n).read_bytes())==digest
    save('body.json',dict(status='PASS',sha256=sha(b),differences_from_v33=len(differences),
        allowed='resident window, existing seven hooks, header checksums',official_update_windows=len(windows),
        official_siblings_identical_to_v32_trial=28,H10_H37_official=True))
    print('PASS body',len(differences),'bytes; official update windows',len(windows))

def constructor():
    LOCAL.mkdir(parents=True,exist_ok=True)
    p=load(HERE/'policy_machine.py','current_policy');p.LOCAL=LOCAL
    def disasm(name,raw,va):
        source=LOCAL/(name+'.bin');source.write_bytes(raw)
        text=subprocess.check_output([str(p.OBJDUMP),'-D','-EB','-b','binary','-m','m32r','--adjust-vma='+str(va),str(source)],text=True)
        (LOCAL/(name+'.disasm')).write_text(text);return text,source
    def load_policy():return p
    a=SimpleNamespace(PACKAGE=IMAGE,image_at=image_at,disasm=disasm)
    c=SimpleNamespace(write=lambda name,value:save(name,value))
    source=(ROOT/'research/review_flash_v33/machine.py').read_text()
    tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='constructor')
    ns=dict(load_policy=load_policy,RES=HERE,a=a,c=c,json=json,re=re,itertools=itertools)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen_constructor_check>','exec'),ns)
    ns['constructor']()

def stack():
    LOCAL.mkdir(parents=True,exist_ok=True)
    s=load(HERE/'stack_checks.py','final_stack');s.LOCAL=LOCAL
    resident=s.artifact('resident',HERE/'local/resident/build/resident.elf',[HERE/'local/resident/build'])
    engine=s.artifact('engine',HERE/'acceptance/local/full-r10/engine.elf',[
        HERE/'acceptance/local/product-r10/m32r-lto',HERE/'acceptance/local/resident/engine-services'])
    for name,targets in (('svc',['core_call']),('pn_call',['rv_call']),('core_call',['rv_call']),('rv_call',['rv_service']),
            ('disarm',['grain_snapshot']),('eng_apply',['grain_snapshot']),('read_object',['io_open','io_read','io_close']),
            ('gxts_load',['io_open','io_read','io_close']),('gxts_save',['io_open','io_read','io_write','io_close','io_remove','io_rename']),
            ('inspect',['verify','last_verify']),('ps_install',['verify']),('pn_ui_render',['pn_native_from_seed']),('rpc',['rv_call']),('pn_address',['address'])):
        s.add(engine,name,targets)
    entries={n:dict(zip(('bytes','chain'),s.peak(engine,n))) for n in ('ig_bootstrap','ig_init','ig_menu','ig_panel_open','ig_event','ig_apply','ig_bx_flush')}
    frames=resident['frames'];prefix=68+sum(frames[n] for n in ('rv_hook_observe','rv_engine','rv_invoke'))
    hooks={1:max(prefix+entries['ig_menu']['bytes'],prefix+frames['rv_load']+max(entries[n]['bytes'] for n in ('ig_bootstrap','ig_init'))),
        6:prefix+entries['ig_panel_open']['bytes'],7:prefix+entries['ig_event']['bytes'],8:prefix+entries['ig_apply']['bytes']}
    hooks[2]=68+s.peak(resident,'rv_hook_observe',blocked=('rv_load','rv_engine'))[0]
    for h,n in ((5,'owned'),(9,'rv_grain')):hooks[h]=68+frames['rv_hook_observe']+s.peak(resident,n)[0]
    save('stack.json',dict(status='PASS_MODEL',entries=entries,modeled_hooks=hooks,
        unresolved=[n for n,v in engine['indirect'].items() if v],native_frames_and_IRQ_included=False,global_safety_proven=False))
    print('PASS stack model',hooks)

def loader():
    LOCAL.mkdir(parents=True,exist_ok=True)
    p=load(HERE/'policy_machine.py','loader_policy');p.LOCAL=LOCAL
    program=p.Program('resident-loader',HERE/'local/resident/build/resident.elf')
    base=program.symbols['rv_load'];first=base+0x194;full=base+0x528
    assert program.code[first][0]==('mv',('r11','r0'))
    assert program.code[full][0]==('addi',('r9','#-2'))
    program.symbols['probe_result']=first;program.symbols['full_result']=full
    def stop(cpu):cpu.r[14]=p.END
    cases=0
    for flags,status in itertools.product(range(256),(-12,-10,-8,-6,-5,-4,-2,-1,0,1,2)):
        cpu=p.Cpu(program);cpu.r[8]=p.ROOT_ADDRESS;cpu.r[0]=status&0xffffffff
        cpu.seed(p.ROOT_ADDRESS+212,flags);cpu.stubs={base+0x19c:stop,base+0x224:stop}
        cpu.run('probe_result',bound=32)
        assert cpu.read(p.ROOT_ADDRESS+212)==flags|(64 if status else 0)
        cases+=1
    for flags,source in itertools.product(range(256),range(3)):
        cpu=p.Cpu(program);cpu.r[8]=p.ROOT_ADDRESS;cpu.r[9]=source
        cpu.seed(p.ROOT_ADDRESS+212,flags);cpu.stubs={base+0x53c:stop}
        cpu.run('full_result',bound=16)
        assert cpu.read(p.ROOT_ADDRESS+212)==flags|(64 if source==2 else 0)
        cases+=1
    save('loader-machine.json',dict(status='PASS',cases=cases,actual_compiled_blocks=True,
        boundary='probe/read validation results are supplied; other loader work covered by real C',native_execution=False))
    print('PASS changed loader instructions',cases)

if __name__=='__main__':{'body':body,'constructor':constructor,'stack':stack,'loader':loader}[sys.argv[1]]()
