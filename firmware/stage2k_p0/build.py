#!/usr/bin/env python3
"""Build an offline-only P0 experiment; refuse invalid layout or cache claims."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
BUILD = LOCAL / 'build'
RESEARCH = ROOT / 'research/stage2k_p0'
PACKAGE = ROOT / 'artifacts/stage2k-p0-packages'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
BIN = ROOT / 'research/tooling_m32r_asm/prefix/bin'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def zero_crc(data):
    """Set the helper's reserved 4-byte word so its ordinary CRC32 is zero."""
    patched=bytearray(data)
    assert patched[12:16] == bytes(4)
    origin=zlib.crc32(patched)
    basis={}
    for i in range(32):
        trial=patched[:]
        trial[12+i//8] ^= 1 << (i%8)
        value=zlib.crc32(trial)^origin
        mask=1<<i
        while value:
            pivot=value.bit_length()-1
            if pivot not in basis:
                basis[pivot]=(value,mask)
                break
            value ^= basis[pivot][0]
            mask ^= basis[pivot][1]
    value=origin
    mask=0
    while value:
        pivot=value.bit_length()-1
        value ^= basis[pivot][0]
        mask ^= basis[pivot][1]
    for i in range(32):
        if (mask>>i)&1:
            patched[12+i//8] ^= 1<<(i%8)
    assert zlib.crc32(patched) == 0
    return bytes(patched)


def run(argv, name, check=True):
    env = dict(os.environ, TMPDIR=str(RESEARCH / 'local/tmp'), PYTHONDONTWRITEBYTECODE='1')
    p = subprocess.run([str(x) for x in argv], cwd=BUILD, env=env,
                       text=True, capture_output=True, timeout=60)
    (BUILD / (name+'.txt')).write_text(p.stdout+p.stderr)
    if check and p.returncode:
        raise RuntimeError(f'{name}: {p.returncode}; see {BUILD / (name+".txt")}')
    return p


def main():
    capture = load_file('p0_capture', RESEARCH/'capture.py')
    capture.preflight()
    BUILD.mkdir(parents=True, exist_ok=True)
    (RESEARCH/'local/tmp').mkdir(exist_ok=True)
    elfmod = load_file('readonly_stage2j_elf', ROOT/'firmware/stage2j/tools/build.py')
    old = elfmod.Elf(ROOT/'firmware/stage2j/build/payload.elf')
    assert old.symbols['rfw_select']['value'] == 0x20053240
    assert old.symbols['rfw_ui_active']['value'] == 0x20052a44
    assert old.symbols['rv1_crc32']['value'] == 0x20053920
    cflags = ['-Os','-fno-pic','-fvisibility=hidden','-fno-common','-ffreestanding',
              '-fno-builtin','-fno-stack-protector','-fstack-usage','-msdata=none',
              '-mmodel=small','-m32r','-Wall','-Wextra','-Werror']
    run([GCC,*cflags,'-c',HERE/'module.c','-o',BUILD/'module.o'],'compile-module')
    run([BIN/'m32r-elf-as',HERE/'module.S','-o',BUILD/'module-asm.o'],'assemble-module')
    run([BIN/'m32r-elf-ld','--orphan-handling=error','-T',HERE/'module.ld',
         '-Map',BUILD/'module.map','-o',BUILD/'module.elf',
         BUILD/'module-asm.o',BUILD/'module.o'],'link-module')
    module_elf = elfmod.Elf(BUILD/'module.elf')
    assert module_elf.entry == 16
    assert all(s['size'] == 0 for s in module_elf.sections if s['name'] in ('.got','.got.plt','.data','.bss'))
    run([BIN/'m32r-elf-objcopy','-O','binary',BUILD/'module.elf',BUILD/'P0.BIN'],'module-objcopy')
    run([OBJDUMP,'-dr',BUILD/'module.elf'],'module-disasm')
    module = zero_crc((BUILD/'P0.BIN').read_bytes())
    (BUILD/'P0.BIN').write_bytes(module)
    assert len(module) <= 4096
    crc = zlib.crc32(module)
    (BUILD/'constants.inc').write_text(f'.equ MODULE_BYTES,{len(module)}\n.equ MODULE_CRC,0x{crc:08x}\n')
    imports = {'p0_current':'current','rfw_ui_active':'rfw_ui_active',
        'gxr_open':'gxr_open','gxr_read':'gxr_read','gxr_close':'gxr_close',
        'gxr_alloc':'gxr_alloc',
        'rv1_crc32':'rv1_crc32'}
    definitions = [f'{name} = 0x{old.symbols[source]["value"]:08x};'
                   for name,source in imports.items()]
    (BUILD/'imports.ld').write_text('\n'.join(definitions)+'\n')
    run([BIN/'m32r-elf-as','-I',BUILD,HERE/'probe.S','-o',BUILD/'probe.o'],'assemble-probe')
    run([OBJDUMP,'-dr',BUILD/'probe.o'],'probe-object-disasm')
    probe = elfmod.Elf(BUILD/'probe.o')
    sizes = {s['name']:s['size'] for s in probe.sections if s['name'] in ('.early','.late','.probe')}
    linked = run([BIN/'m32r-elf-ld','--orphan-handling=error','-T',BUILD/'imports.ld',
        '-T',HERE/'probe.ld','-Map',BUILD/'probe.map','-o',BUILD/'probe.elf',BUILD/'probe.o'],
        'link-probe',check=False)
    report = dict(status='OFFLINE_ONLY',camera_handoff_ready=False,
        camera_executed=False, cache_contract_proven=False, tick_seconds_proven=False,
        module_bytes=len(module), module_sha256=sha(module), module_crc32=f'{crc:08x}',
        resident_sections=sizes, resident_used=sum(sizes.values()), resident_available=284,
        resident_linked=linked.returncode == 0,
        imports={k:hex(old.symbols[v]['value']) for k,v in imports.items()},
        build_tools={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [GCC,OBJDUMP,BIN/'m32r-elf-as',BIN/'m32r-elf-ld',BIN/'m32r-elf-objcopy']},
        sync='MCCR 0xFFFFFFFC: if bit0 set, OR 0x101; returns non-zero on success',
        instructions='A=49 B=82 via heap return stub after sync; then module entry at +16 measures ticks')
    (BUILD/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if linked.returncode:
        print(json.dumps(report,ensure_ascii=False))
        return
    run([OBJDUMP,'-dr',BUILD/'probe.elf'],'probe-disasm')
    for section in ('.early','.late','.probe'):
        run([BIN/'m32r-elf-objcopy','-O','binary','-j',section,
            BUILD/'probe.elf',BUILD/(section[1:]+'.bin')],'extract-'+section[1:])
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
