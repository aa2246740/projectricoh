"""Assemble a research reference without building any product image."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study

prefix = study.ROOT/'research/tooling_m32r_asm/prefix/bin'
source = HERE/'record_try.S'
obj = study.OUT/'record-try.o'
elf = study.OUT/'record-try.elf'
binary = study.OUT/'record-try.bin'
commands = [
    [str(prefix/'m32r-elf-as'), '-o', str(obj), str(source)],
    [str(prefix/'m32r-elf-ld'), '-Ttext=0x206e0000', '-e', 'record_try', '-o', str(elf), str(obj)],
    [str(prefix/'m32r-elf-objcopy'), '-O', 'binary', str(elf), str(binary)],
]
for command in commands:
    subprocess.run(command, check=True, capture_output=True)
assembly = subprocess.check_output([str(study.OBJDUMP),'-d',str(elf)], text=True)
(study.OUT/'record-try.asm.txt').write_text(assembly)
study.save('record-try-build.json', dict(source_sha256=study.sha(source),
           binary_sha256=study.sha(binary), bytes=binary.stat().st_size,
           entry='0x206e0000', product_build=False))
print('Research reference assembled: '+str(binary.stat().st_size)+' B.')
