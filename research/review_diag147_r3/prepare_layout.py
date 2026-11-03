"""Compile the diagnostic field-offset probe with at most one child process."""
from pathlib import Path
import ast
import json
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
source = scope.ROOT / 'research/diag147/accept_diag147.py'
tree = ast.parse(source.read_text())
fields = next(ast.literal_eval(x.value) for x in tree.body
              if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FIELDS' for t in x.targets))
out = HERE / 'local/layout147'
out.mkdir(parents=True, exist_ok=True)
product = scope.ROOT / 'firmware/engine_diag_v38_g147/candidate/containers/product'
probe = out / 'offsets.c'
probe.write_text('#include "' + str(product / 'diag.c') + '"\nconst uint32_t diag_offsets[]={' +
                 ','.join('offsetof(Diagnostic,%s)' % name for name in fields) + '};\n')
gcc = scope.ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
args = [str(gcc), '-###', '-std=c11', '-Os', '-ffreestanding', '-fpic', '-m32r', '-mmodel=medium',
        '-msdata=none', '-G0', '-fno-builtin', '-c', str(probe), '-o', str(out / 'offsets.o')]
plan = subprocess.run(args, text=True, capture_output=True, check=True, timeout=1800)
commands = []
for line in plan.stderr.splitlines():
    parts = shlex.split(line)
    if parts and Path(parts[0]).name in ('cc1', 'as', 'm32r-elf-as'):
        commands.append(parts)
assert len(commands) == 2, commands
old_assembly = commands[0][commands[0].index('-o')+1]
assembly = str(out / 'offsets.s')
commands = [[assembly if x == old_assembly else x for x in command] for command in commands]
for command in commands:
    subprocess.run(command, check=True, cwd=scope.ROOT, timeout=1800)
scope.save(HERE / 'layout-build.json', dict(status='PASS', commands=commands, fields=fields,
           source_sha256=scope.sha(probe), object_sha256=scope.sha(out / 'offsets.o'),
           compiler_sha256=scope.sha(gcc), maximum_child_processes=1))
print('LAYOUT PASS', len(fields), 'fields')
