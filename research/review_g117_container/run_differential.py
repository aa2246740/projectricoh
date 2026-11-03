"""Compare actual live rows/settings from gen116 and gen117 C implementations."""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_review as rr

OUT = Path(__file__).resolve().parent
vectors = {}
for gen, folder in ((116, rr.ROOT / 'firmware/engine_v37/candidate'), (117, rr.CAND)):
    calls = [json.loads(row) for row in (folder / 'local/commands.jsonl').read_text().splitlines()]
    source = str(folder / 'host_v34c.c')
    compile_call = next(row['argv'] for row in reversed(calls) if row['label'].startswith('v34c-compile-') and source in row['argv'])
    link_call = next(row['argv'] for row in reversed(calls) if row['label'] == 'v34c-link')
    old = compile_call[compile_call.index('-o') + 1]
    obj, binary = str(OUT / f'differential-{gen}.o'), str(OUT / f'differential-{gen}')
    compile_call = [str(OUT / 'differential_host.c') if a == source else obj if a == old else a for a in compile_call]
    compile_call.append('-DREVIEW_HOST_SOURCE="' + source + '"')
    assert rr.run(f'differential-compile-{gen}', compile_call) == 0
    link_call = [obj if a == old else a for a in link_call]
    link_call[link_call.index('-o') + 1] = binary
    assert rr.run(f'differential-link-{gen}', link_call) == 0
    for unit in range(3):
        name = f'differential-{gen}-{unit}'
        assert rr.run(name, [binary, 'diff', unit, folder / 'local/full-r13/GXRCE.DAT',
                      folder / 'local/full-r13/trust.bin', folder / 'local/full-r13/effective-rows.bin',
                      rr.ROOT / 'firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT', '0']) == 0
        output = (rr.LOG / (name + '.stdout')).read_text()
        vectors[gen, unit] = [line for line in output.splitlines() if line.startswith('VECTOR ')]
        assert len(vectors[gen, unit]) == 24
rows = []
for unit in range(3):
    assert vectors[116, unit] == vectors[117, unit]
    rows.append(dict(unit=unit, cases=24, live_rows_and_T_and_4096_settings_identical=True,
        output_sha256=hashlib.sha256(('\n'.join(vectors[117, unit]) + '\n').encode()).hexdigest()))
(OUT / 'differential-live-results.json').write_text(json.dumps(dict(status='PASS',
    cases=72, results=rows, gen116_objects='read-only existing sanitized C objects',
    gen117_objects='independently rebuilt in this review', machine_code_equivalence=False), indent=2) + '\n')
print('PASS differential live rows + T + full 4096 settings: 3 units x 8 slots x 3 tweaks = 72')
