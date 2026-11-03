#!/usr/bin/python3 -I
"""Measure target layouts and a small record-code subset, one command at a time."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/autoapply')
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert HERE == ROOT / 'research/poweron_autoapply'
    assert TMP.is_dir() and TMP.resolve() == TMP
    tmpdir = TMP / 'compiler-tmp'
    tmpdir.mkdir(exist_ok=True)
    source = HERE / 'layout_prototype.c'
    obj = TMP / 'layout_prototype.o'
    flags = ['-std=c11', '-Os', '-ffreestanding', '-fno-builtin', '-fno-common',
             '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
             '-fpic', '-m32r', '-mmodel=medium', '-msdata=none', '-G0',
             '-Wall', '-Wextra', '-Werror', '-fstack-usage', '-ffunction-sections', '-fdata-sections']
    env = dict(os.environ, TMPDIR=str(tmpdir), PYTHONDONTWRITEBYTECODE='1', LC_ALL='C')
    commands = [
        ['/usr/bin/nice', '-n', '10', str(GCC), *flags, '-c', str(source), '-o', str(obj)],
        ['/usr/bin/nice', '-n', '10', str(OBJDUMP), '-h', '-t', str(obj)],
    ]
    results = []
    for command in commands:
        p = subprocess.run(command, cwd=TMP, env=env, capture_output=True, text=True, timeout=60)
        results.append(dict(argv=command, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr))
        if p.returncode:
            raise RuntimeError(p.stderr + p.stdout)
    output = results[-1]['stdout']
    sizes = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0].isdigit() and parts[1].startswith('.'):
            sizes[parts[1]] = int(parts[2], 16)
    evidence = dict(source_sha256=digest(source), gcc_sha256=digest(GCC), objdump_sha256=digest(OBJDUMP),
                    object_sha256=digest(obj), sections=sizes,
                    code_bytes=sum(n for name, n in sizes.items() if name.startswith('.text')),
                    bss_bytes=sum(n for name, n in sizes.items() if name.startswith('.bss')),
                    stack_report=(TMP / 'layout_prototype.su').read_text(), commands=results,
                    scope='layouts_and_level_codec_only_no_camera_services',
                    combined_firmware_link=False, product_acceptance=False)
    destination = HERE / 'evidence' / 'prototype-build.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps({k: evidence[k] for k in ('code_bytes', 'bss_bytes', 'sections', 'stack_report', 'scope')}, indent=2))


if __name__ == '__main__':
    main()
