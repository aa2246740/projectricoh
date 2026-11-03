"""Obtain diagnostic offsets from the same M32R compiler, not Host sizeof."""
import json
from pathlib import Path
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools/native_harness'))
from image_loader import Elf

fields = ['current','confirmed','tweak','confirmed_tweak','list','live','staging',
          'busy','committed','uncertain','stage','confirmed_valid','previewing']
out = HERE / 'local/layout'
out.mkdir(parents=True, exist_ok=True)
source = ROOT / 'firmware/engine_v39_ux/candidate/containers/product/src/firmware/engine/core/eng_core.c'
code = '#include "' + str(source) + '"\n'
code += 'const unsigned ux_layout[] = {' + ','.join('offsetof(Engine,'+f+')' for f in fields) + '};\n'
(out / 'layout.c').write_text(code)
cmd = [str(ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'),
       '-std=c11','-Os','-m32r','-ffreestanding','-ffunction-sections','-fdata-sections',
       '-c',str(out / 'layout.c'),'-o',str(out / 'layout.o')]
run = subprocess.run(cmd, capture_output=True, text=True)
(out / 'stdout.txt').write_text(run.stdout)
(out / 'stderr.txt').write_text(run.stderr)
assert run.returncode == 0, run.stderr
e = Elf(out / 'layout.o')
b = next(s['data'] for s in e.sections if s['name']=='.rodata.ux_layout')
layout = dict(zip(fields,struct.unpack('>'+str(len(fields))+'I',b)))
(out / 'layout.json').write_text(json.dumps(layout,indent=2)+'\n')
print(json.dumps(layout))
