"""Record the final machine-code latch stores and excluded host reset entry."""
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import codegen as c
from common import DAT, DAT_SHA, save, file_sha

assert file_sha(DAT) == DAT_SHA
e = c.ES[120]
assert 'ig_host_reset' not in e.symbols
rows = []
for name in e.functions:
    atoms = c.atoms(120, name)[0]
    for index, row in enumerate(atoms):
        if not re.search(r'\bstb \w+,@\(3712,', row['asm']):
            continue
        context = atoms[max(0,index-3):index+2]
        assert atoms[index-1]['asm'] == 'ldi r4,#1', (name,context)
        rows.append(dict(function=name, pc=hex(row['pc']), context=context))
assert {row['function'] for row in rows} == {'finish', 'ui_finish'}
save('latch-static.json', dict(status='PASS', dat_sha256=DAT_SHA,
    latch_offset=3712, object_address=e.symbols['n']['address'], stores=rows,
    native_host_reset_present=False,
    scope='The two direct byte stores to this latch set it to one. Source review excludes whole-object reset from the native build; runtime API cases verify that ordinary entries preserve it. Loader BSS initialization is the cold reset boundary.'))
print('PASS final latch stores: both set one; host reset absent', flush=True)
