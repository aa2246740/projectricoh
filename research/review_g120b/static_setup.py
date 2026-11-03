"""Route existing instruction decoders to read-only reference evidence."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, sha, file_sha

source = ROOT/'research/ux_preview_dot_r5'
rows = []
for name in ('codegen.py', 'machine_static.py', 'file_gate_cfg.py', 'machine_gates.py'):
    original = (source/name).read_text()
    text = original
    if name == 'codegen.py':
        text = text.replace('DEC={g:', "REFERENCE=ROOT/'research/ux_preview_dot_r5'\nDEC={g:")
        text = text.replace("(OUT/f'decode", "(REFERENCE/f'decode")
        text = text.replace("(OUT/f'engine", "(REFERENCE/f'engine")
        text = text.replace("OUT/'labels119/engine.elf'", "REFERENCE/'labels119/engine.elf'")
    if name == 'machine_static.py':
        text = text.replace("OUT/'assembly-leaves.json'", "ROOT/'research/ux_preview_dot_r5/assembly-leaves.json'")
    (OUT/name).write_text(text)
    rows.append(dict(source=str((source/name).relative_to(ROOT)), sha256=file_sha(source/name),
                     reviewed_sha256=sha(text.encode()), changed=text != original))
save('static-source-routing.json', dict(status='PASS', sources=rows,
    scope='Final DAT file capability checks only. Compilation comparison obligations are outside this review.'))
print('PASS static decoder setup', flush=True)
