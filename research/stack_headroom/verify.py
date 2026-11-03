#!/usr/bin/env python3
"""Verify research artifacts only; never compile or execute camera code."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import struct
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
spec=importlib.util.spec_from_file_location('headroom_inspect',HERE/'inspect.py')
ins=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ins)


def main():
    # macOS /usr/bin/python3 may launch Apple's Command Line Tools interpreter.
    assert sys.flags.isolated==1 and sys.dont_write_bytecode
    ins.preflight()
    frozen=json.loads((LOCAL/'inputs-frozen.json').read_text())
    mismatches=[p for p,h in frozen.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert not mismatches,mismatches
    assert hashlib.sha256(ins.TOOL.read_bytes()).hexdigest()=='8d3712c11cac0ffc63b790148c49a916f25d96fceabbb3c1daa125cf4904368a'
    logs=[]
    for script,args in [('analyze.py',[]),('inspect.py',['verify'])]:
        result=subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/script),*args],text=True,capture_output=True)
        logs.append({'script':script,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        assert result.returncode==0,logs[-1]
    (LOCAL/'verification-log.json').write_text(json.dumps(logs,indent=2)+'\n')
    # Read and disassemble the existing resident ELF. No assembly or linking occurs.
    elf=ROOT/'firmware/resident_v31/local/resident/build/resident.elf'
    blob=elf.read_bytes()
    assert hashlib.sha256(blob).hexdigest()=='3e178354b3086fa8e9ac2af09fc5434ff013c5e760a7ecbf3689b689c0714160'
    assert blob[:6]==b'\x7fELF\x01\x02'
    shoff=struct.unpack_from('>I',blob,32)[0]
    entsize,count=struct.unpack_from('>HH',blob,46)
    lo,hi=0x20053ff8,0x20054010
    native=None
    for i in range(count):
        sec=struct.unpack_from('>10I',blob,shoff+i*entsize)
        _,_,_,va,off,size,*_=sec
        if va<=lo and hi<=va+size and sec[1]!=8:
            native=blob[off+lo-va:off+hi-va]
            break
    assert native is not None and len(native)==24
    asm=subprocess.check_output([str(ins.TOOL),'-d',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(elf)],text=True)
    (LOCAL/'v31-rv-invoke.asm.txt').write_text(asm)
    (LOCAL/'v31-rv-invoke.bin').write_bytes(native)
    n=0
    for pc,code,_ in ins.instructions(asm):
        assert native[pc-lo:pc-lo+len(code)]==code
        n+=len(code)
    assert n==24,n
    model=json.loads((LOCAL/'model.json').read_text())
    assert all(not r['global_upper_bound_proven'] for r in model['rows'])
    assert len(model['rows'])==7
    assert not any(p.suffix.lower() in {'.elf','.o','.dat','.ipa'} for p in HERE.rglob('*') if p.is_file())
    report=(HERE/'REPORT.md').read_text()
    for phrase in ('已核实','推断','未知','15,968','15,540','0x2042C030','76 B','4 KiB','H02、H05、H09','不改常驻层'):
        assert phrase in report,phrase
    ignore=subprocess.check_output(['git','-C',str(ROOT),'check-ignore','-v',str(LOCAL/'model.json')],text=True).strip()
    assert 'research/stack_headroom/.gitignore:1:/local/' in ignore,ignore
    result=dict(status='PASS_STATIC_RESEARCH',frozen_inputs=len(frozen),input_mismatches=[],
        byte_verification=json.loads((LOCAL/'verification.json').read_text()),
        modeled_functions=len(model['functions']),checked_direct_calls=len(model['direct_links']),
        checked_pointer_words=len(model['checked_pointer_words']),resident_invoke_bytes_checked=24,
        ignore=ignore,python_executable=sys.executable,isolated=True,dont_write_bytecode=True,
        global_safety_proven=False,absolute_task6_base_known=False,
        native_api_deepest_stack_known=False,firmware_built=False,camera_access=False,
        sd_media_access=False,private_stack_implemented=False,watermark_implemented=False)
    (LOCAL/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    lines=[f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE)}' for p in paths]
    (HERE/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    for line in lines:
        h,name=line.split('  ',1)
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==h,name
    print(json.dumps(dict(status=result['status'],frozen_inputs=len(frozen),
        firmware_windows=result['byte_verification']['windows'],
        decoded_bytes=result['byte_verification']['decoded_bytes_checked'],
        sha256_entries=len(lines),global_safety_proven=False),indent=2))


if __name__=='__main__':
    main()
