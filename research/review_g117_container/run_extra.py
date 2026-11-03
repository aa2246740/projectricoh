"""Reuse this review's exact sanitized product objects, replace only test driver."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_review as rr

OUT = Path(__file__).resolve().parent
C = OUT / 'isolated/candidate'
calls = [json.loads(row) for row in (C / 'local/commands.jsonl').read_text().splitlines()]
source = str(C / 'host_v34c.c')
compile_call = next(row['argv'] for row in reversed(calls) if row['label'].startswith('v34c-compile-') and source in row['argv'])
link_call = next(row['argv'] for row in reversed(calls) if row['label'] == 'v34c-link')
old = compile_call[compile_call.index('-o') + 1]
obj = str(OUT / 'extra_host.o')
binary = str(OUT / 'extra_host')
compile_call = [str(OUT / 'extra_host.c') if arg == source else obj if arg == old else arg for arg in compile_call]
assert rr.run('extra-compile', compile_call) == 0
link_call = [obj if arg == old else arg for arg in link_call]
link_call[link_call.index('-o') + 1] = binary
assert rr.run('extra-link', link_call) == 0
for unit in range(3):
    assert rr.run('extra-' + str(unit), [binary, 'extra', unit, C / 'local/full-r13/GXRCE.DAT',
                  C / 'local/full-r13/trust.bin', C / 'local/full-r13/effective-rows.bin',
                  rr.ROOT / 'firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT', '0']) == 0
old_paths = {
    105: 'firmware/engine_fix_r2/local/product/candidates/full-r3/GXRCE.DAT',
    109: 'firmware/engine_v33d/local/full-r7/GXRCE.DAT',
    111: 'firmware/resident_v33/acceptance/local/full-r9/GXRCE.DAT',
    113: 'firmware/resident_v34c/acceptance/local/full-r11/GXRCE.DAT',
    114: 'firmware/engine_v36_r28/local/reproduced114/GXRCE.DAT',
}
for gen, path in old_paths.items():
    for unit in range(3):
        assert rr.run('stale-' + str(gen) + '-' + str(unit), [binary, 'stale-only', unit,
                      C / 'local/full-r13/GXRCE.DAT', C / 'local/full-r13/trust.bin',
                      C / 'local/full-r13/effective-rows.bin', rr.ROOT / path, '0']) == 0
