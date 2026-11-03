"""Try strict whole-function A before carrying any B branch obligation.

Adds gen117's frozen final engine to the same byte-checked decoder. A negative
instruction/CFG/stack comparison already refutes A, without guessing how much
of an anonymous data object a function reads.
"""
from pathlib import Path
import json
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codegen as c
from common import OUT, ROOT, save, sha


def main():
    e = c.audit.Elf(ROOT / 'firmware/engine_v38_b36/candidate/local/full-r13/engine.elf')
    c.ES[117] = e
    asm = subprocess.run([str(c.audit.TC / 'm32r-elf-objdump'), '-dr', str(e.path)],
                         capture_output=True, text=True, check=True).stdout
    (OUT / 'engine117.asm').write_text(asm)
    c.DEC[117] = {int(pc): r for pc, r in c.audit.rows(asm).items()}
    c.RELOC[117] = {int(m[1], 16): (m[2], m[3]) for m in re.finditer(
        r'^\s*([0-9a-f]+): (R_M32R_[A-Z0-9_]+)\s+(.+)$', asm, re.M)}
    source = json.loads((OUT / 'inherited/codegen-selfcheck.json').read_text())
    names = [x['function'] for x in source['functions'] if x['open_outcomes']]
    rows = []
    for short in names:
        n = 'panel_render.constprop.0' if short == 'panel_render' else short
        for g in (117, 118):
            old = n
            if g == 117 and n == 'panel_render.constprop.0':
                old = 'pn_ui_render.constprop.0'
            if old not in c.ES[g].functions:
                rows.append(dict(function=short, baseline=g, strict_A=False,
                                 reason='No corresponding typed function in the frozen baseline.'))
                continue
            a, b = c.atoms(g, old)[0], c.atoms(119, n)[0]
            x, bx, _ = c.symbolic(g, old, a)
            y, by, _ = c.symbolic(119, n, b)
            diff = next((dict(atom=i, old=xv, new=yv)
                         for i, (xv, yv) in enumerate(zip(x, y)) if xv != yv), None)
            if diff is None and len(x) != len(y):
                diff = dict(old_atoms=len(x), new_atoms=len(y))
            # Strict instruction identity is a necessary A condition. Every
            # requested B function fails it; no data/packet test can repair it.
            assert diff is not None, (g, old, 'A needs complete data-target verification')
            rows.append(dict(function=short, baseline=g, strict_A=False,
                             old_atoms=len(a), new_atoms=len(b), first_mismatch=diff,
                             reason='Non-NOP instructions differ after relocation and branch normalization; use B/C.'))
    save('A-first-attempts.json', dict(gen117_elf_sha256=sha(e.raw), functions=names,
                                    attempts=rows, closed_by_whole_function_A=0))
    print('Strict whole-function A tried against 117 and 118:', len(names),
          'functions; all require explicit B/C, none waived.', flush=True)


if __name__ == '__main__':
    main()
