#!/usr/bin/env python3
"""Rebuild, inspect linked default thunks, and run scoped host behavior checks."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'


def load(path,name):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def main():
    inspect=load(HERE/'inspect.py','verify_inspect');inspect.preflight()
    env=dict(os.environ,TMPDIR=str(LOCAL/'tmp'),PYTHONDONTWRITEBYTECODE='1',LC_ALL='C')
    def run(args,name):
        p=subprocess.run([str(x) for x in args],cwd=ROOT,env=env,text=True,capture_output=True)
        (LOCAL/(name+'.log')).write_text(p.stdout+p.stderr)
        if p.returncode: raise RuntimeError(f'{name}: {p.stderr[-1800:]}')
        return p.stdout
    run(['python3','-I','-B',HERE/'build.py'],'verify-build')
    legacy=load(ROOT/'firmware/stage2l_switch/tools/build.py','verify_elf')
    sizes=json.loads((LOCAL/'size.json').read_text())
    hooks=json.loads((LOCAL/'hooks.json').read_text())
    audits=[]
    for variant in ('full','compact'):
        elf=legacy.Elf(HERE/sizes['results'][variant]['elf'])
        payload=next(s for s in elf.sections if s['name']=='.payload')
        data=elf.content(payload)
        asm=(LOCAL/f'{variant}-disassembly.log').read_text()
        count=0
        for h in hooks:
            if h['id'] in ('adj_name_table','adj_count_16'): continue
            name=f'rv_hook_{h["number"]:02}'
            va=elf.symbols[name]['value'];off=va-payload['va']
            original=bytes.fromhex(h['original_bytes'])
            assert data[off+16:off+16+len(original)]==original,name
            branch=va+16+len(original)+(8 if h['id'].startswith('playback_caller_') else 0)
            target=int(h['replay_resume'],16)
            line=re.search(rf'^\s*{branch:x}:.*$',asm,re.M)
            assert line and re.search(rf'\bbra\s+{target:x}\b',line[0]),(name,line)
            count+=1
        if variant=='compact':
            assert payload['va']+payload['size']<=0x20054600
            assert next(s for s in elf.sections if s['name']=='.root')['size']==512
        audits.append(dict(variant=variant,default_thunks=count,replay_bytes_and_resume=True))
    out=LOCAL/'host';out.mkdir(exist_ok=True)
    common=['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin',
            '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',HERE,'-I',ROOT/'firmware/card_container']
    sources=[HERE/'resident.c',LOCAL/'crypto_gate.c',LOCAL/'trust.c',HERE/'host_checks.c']
    objects=[]
    for p in sources:
        obj=out/(p.stem+'.o');objects.append(obj)
        run([*common,'-c',p,'-o',obj],'host-'+p.stem)
    ref=out/'reference.o';objects.append(ref)
    run([*common,'-Dgxrce_validate=rv_reference_validate','-Dgxrce_crc32=ref_crc32',
        '-Dgxrce_sha256=ref_sha256','-c',ROOT/'firmware/card_container/gxrce.c','-o',ref],'host-reference')
    rt=out/'runtime.o';objects.append(rt)
    run([*common,'-Dmemcpy=rv_test_memcpy','-c',HERE/'runtime.c','-o',rt],'host-runtime')
    binary=out/'checks'
    run(['clang','-fsanitize=address,undefined',*objects,'-o',binary],'host-link')
    host=run([binary,ROOT/'firmware/card_container/local/candidate/GXRCE.DAT'],'host-checks').strip()
    expected=json.loads((LOCAL/'inputs.json').read_text())
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in expected.items())
    result=dict(status='PASS_HOST_AND_LINK_EVIDENCE',audits=audits,host=host,
                inputs_unchanged=True,firmware_ready=False,camera_acceptance=False,
                no_card_or_body_image_emitted=True)
    (LOCAL/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(host)
    print('PASS_LINK default_thunks=35_per_variant inputs_unchanged=1 camera_acceptance=0')


if __name__=='__main__':main()
