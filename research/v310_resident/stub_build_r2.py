#!/usr/bin/python3
"""在指定 scratch 生成仅测试使用的最小 BOOT DAT。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_resident'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-resident-r1')
GCC=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD=ROOT/'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJCOPY=ROOT/'research/tooling_m32r_asm/prefix/bin/m32r-elf-objcopy'
BASE=ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT'


def build(variant,kind):
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    work=TEMP/'r2-stub'/variant/str(kind);work.mkdir(parents=True,exist_ok=True)
    old=BASE.read_bytes();off,length=struct.unpack_from('>II',old,132)
    ld=work/'stub.ld'
    ld.write_text('OUTPUT_FORMAT("elf32-m32r")\nOUTPUT_ARCH(m32r)\nENTRY(stub_entry)\nSECTIONS {\n'
        f' .engine {off:#x} : {{ KEEP(*(.text.stub_entry)) *(.text .text.* .rodata .rodata.*) . = {length}; }}\n'
        ' .forbidden : { *(.data* .bss* COMMON .sdata* .sbss* .got*) }\n'
        ' /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }\n'
        ' ASSERT(SIZEOF(.forbidden)==0,"no mutable stub globals")\n}\n')
    obj=work/'stub.o';elf=work/'stub.elf';code=work/'stub-code.bin'
    commands=[
        [GCC,'-std=c11','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector',
         '-fno-common','-m32r','-mmodel=medium','-msdata=none','-G0',
         '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror',
         '-I'+str(ROOT/'firmware/resident_v310_thin/resident'),'-DSTUB_KIND='+str(kind),
         '-c',HERE/'tests_r2/stub_dat.c','-o',obj],
        [LD,'--no-undefined','--orphan-handling=error','-T',ld,'-Map='+str(work/'stub.map'),'-o',elf,obj],
        [OBJCOPY,'-O','binary','-j','.engine',elf,code]]
    logs=[]
    for args in commands:
        p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=1800,check=True)
        logs.append(p.stdout+p.stderr)
    raw=bytearray(old);new=code.read_bytes();assert len(new)==length
    raw[off:off+length]=new
    struct.pack_into('>I',raw,112,off)
    struct.pack_into('>H',raw,120,0)
    struct.pack_into('>I',raw,148,0)
    trust=json.loads((HERE/'evidence_r2'/variant/'trust.json').read_text())
    raw[80:112]=bytes.fromhex(trust['resident_build_id'])
    raw[212:228]=bytes.fromhex(trust['resident_abi_id'])
    struct.pack_into('>I',raw,24,zlib.crc32(raw[256:]))
    struct.pack_into('>I',raw,20,zlib.crc32(raw[:20]+bytes(4)+raw[24:256]))
    dat=work/'stub-test.dat';dat.write_bytes(raw)
    evidence=HERE/'evidence_r2'/'stub-builds';evidence.mkdir(exist_ok=True)
    record=dict(test_only=True,variant=variant,kind=kind,engine=str(elf),dat=str(dat),
        engine_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),dat_sha256=hashlib.sha256(raw).hexdigest(),
        code_bytes=length,behaviour='minimal fixed-word responder; no unit, S or T writes',
        commands=[[str(x) for x in args] for args in commands])
    (evidence/(variant+'-'+str(kind)+'.json')).write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    print(json.dumps(build(sys.argv[1],int(sys.argv[2]))))
