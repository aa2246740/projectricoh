#!/usr/bin/python3
"""Compile real resident/service C; run a single variant at a time."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-reclaim-r2')
records = []
for variant in ('r6a', 'r7'):
    work = TEMP / ('boundaries-' + variant)
    work.mkdir(exist_ok=True)
    resident = work / 'resident'; service = work / 'engine_services'
    resident.mkdir(exist_ok=True); service.mkdir(exist_ok=True)
    source = HERE / 'local/rebuild/v' / variant
    for p in source.iterdir():
        if p.suffix in ('.c', '.h'): shutil.copy2(p, resident / p.name)
    original = ROOT / 'firmware/resident_v38/engine_services'
    for name in ('services.c', 'api.c', 'engine_services.h'):
        text = (original / name).read_text()
        (service / name).write_text(text.replace('r->grain=0;', ''))
    args = ['/usr/bin/clang', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Wno-unused-function',
            '-Wno-unknown-attributes', '-fno-builtin', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
            '-fno-omit-frame-pointer', '-DRV_HOST', '-I'+str(resident), '-I'+str(service),
            str(HERE / 'host_boundaries.c')]
    args += [str(resident / (name+'.c')) for name in ('resident', 'shared', 'hooks', 'loader', 'validate_envelope.inc')]
    args += [str(service / (name+'.c')) for name in ('services', 'api')]
    binary = work / 'boundaries'
    args += ['-o', str(binary)]
    for name, argv in [('compile', args), ('run', [str(binary)])]:
        start = time.monotonic()
        log = HERE / 'local' / f'boundaries-{variant}-{name}.log'
        with log.open('w') as stream:
            p = subprocess.run(['/usr/bin/nice', '-n', '10', *argv], stdout=stream, stderr=subprocess.STDOUT,
                               timeout=600, env=os.environ.copy())
        records.append(dict(variant=variant, phase=name, returncode=p.returncode,
                            elapsed_seconds=round(time.monotonic()-start,3), timeout_seconds=600, log=str(log.relative_to(HERE))))
        if p.returncode:
            print(log.read_text()[-5000:]); raise SystemExit(p.returncode)
assert (HERE/'local/boundaries-r6a-run.log').read_bytes() == (HERE/'local/boundaries-r7-run.log').read_bytes()
(HERE/'local/boundaries-result.json').write_text(json.dumps(dict(records=records, outputs_equal=True),indent=2)+'\n')
print((HERE/'local/boundaries-r7-run.log').read_text())
