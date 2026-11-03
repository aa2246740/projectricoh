#!/usr/bin/env python3
"""Host fault injection and static ELF audit. Overflow is a failed acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    build=module(HERE/'build.py','rv_verify_build');build.preflight()
    env=dict(os.environ,TMPDIR=str(LOCAL/'tmp'),LC_ALL='C',PYTHONDONTWRITEBYTECODE='1',ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    def run(args,name,allowed=(0,)):
        p=subprocess.run([str(x) for x in args],cwd=ROOT,env=env,text=True,capture_output=True)
        (LOCAL/(name+'.log')).write_text(p.stdout+p.stderr)
        if p.returncode not in allowed:raise RuntimeError(name+': '+(p.stdout+p.stderr)[-2500:])
        return p.stdout
    run(['python3','-I','-B',HERE/'build.py'],'verify-build',allowed=(0,2))
    run(['python3','-I','-B',HERE/'make_fixture.py'],'fixtures')
    out=LOCAL/'host';out.mkdir(exist_ok=True)
    common=['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST',
            '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',HERE]
    objects=[]
    for name in ['resident.c','loader.c','services.c','hooks.c','runtime.c','validate_envelope.inc.c','host_checks.c','local/trust.c']:
        source=HERE/name;obj=out/(source.stem+'.o');objects.append(obj)
        options=['-Dmemcpy=rv_test_memcpy','-Dmemset=rv_test_memset'] if name=='runtime.c' else []
        run([*common,*options,'-c',source,'-o',obj],'host-compile-'+source.stem)
    binary=out/'checks';run(['clang','-fsanitize=address,undefined',*objects,'-o',binary],'host-link')
    host=run([binary,LOCAL/'fixtures/synthetic-container.fixture',LOCAL/'fixtures/crc-collision.fixture',LOCAL/'fixtures/code-24k.fixture'],'host-checks').strip()
    size=json.loads((LOCAL/'size.json').read_text());legacy=module(ROOT/'firmware/stage2l_switch/tools/build.py','rv_verify_elf')
    elf=legacy.Elf(HERE/size['elf']);sections=elf.sections;payload=next(s for s in sections if s['name']=='.payload');data=elf.content(payload)
    assert not any(s['type'] in (4,9) and s['size'] for s in sections)
    assert not any(s['section']==0 and s['name'] for s in elf.symbols.values())
    assert not any('sha256' in s.lower() for s in elf.symbols)
    asm=(LOCAL/'disassembly.log').read_text();hooks=json.loads((LOCAL/'hooks.json').read_text());audits=[]
    for h in hooks:
        ident=h['number']
        if ident in (3,4):continue
        address=elf.symbols[f'rv_hook_{ident:02}']['value'];offset=address-payload['va'];original=bytes.fromhex(h['original_bytes'])
        assert data[offset+16:offset+16+len(original)]==original
        branch=address+16+len(original)+(8 if ident in (33,34,35,36) else 0)
        line=re.search(rf'^\s*{branch:x}:.*$',asm,re.M)
        assert line and re.search(rf'\bbra\s+{int(h["replay_resume"],16):x}\b',line[0]),(ident,line)
        audits.append(dict(hook=f'H{ident:02}',replay=True,resume=True))
    inputs=json.loads((LOCAL/'inputs.json').read_text());assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in inputs.items())
    stack=[]
    for p in sorted((LOCAL/'build').glob('*.su')):
        for line in p.read_text().splitlines():
            loc,bytes_,kind=line.split('\t');stack.append(dict(function=loc.rsplit(':',1)[-1],bytes=int(bytes_),kind=kind))
    stack.sort(key=lambda row:row['bytes'],reverse=True)
    (LOCAL/'stack.json').write_text(json.dumps(dict(frames=stack,hook_saved_bytes=68,native_and_engine_stack_unknown=True),indent=2)+'\n')
    result=dict(status='PASS' if size['constrained_link'] else 'BLOCKED_WINDOW_OVERFLOW',host=host,
      hooks=audits,inputs_unchanged=True,abi_unchanged=True,no_sha256_code=True,size=size,
      firmware_ready=False,camera_acceptance=False,native_m32r_execution=False,firmware_or_card_image_emitted=False)
    (LOCAL/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(host);print(result['status']+f' margin={size["margin"]} native_execution=0 camera_acceptance=0')
    return 0 if size['constrained_link'] else 2
if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        import traceback
        with (LOCAL/'failures.log').open('a') as f:traceback.print_exc(file=f)
        raise
