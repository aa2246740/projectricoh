#!/usr/bin/env python3
"""Run the public analyzer command on three/five-frame inputs and rejected inputs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location('t3_cli_core', Path(__file__).with_name('t3_core.py'))
p = importlib.util.module_from_spec(sp); sp.loader.exec_module(p)


def main():
    p.preflight()
    c = p.CAP
    cases = [
        ('no_change', [c/'R8051179.JPG', c/'R8051179.JPG', c/'R8051182.JPG'], 0, 'no_effect'),
        ('full_synthetic', [c/'R8051179.JPG', p.LOCAL/'tests/images/H1/probe.JPG', c/'R8051182.JPG',
                           p.ROOT/'research/t1_probe/probe2/local/tests/images/absolute_BCD/probe.JPG',
                           c/'R8051182.JPG'], 0, 'compatible'),
        ('bad_count', [c/'R8051179.JPG', c/'R8051182.JPG'], 2, 'abnormal'),
        ('missing_pair', [c/'R8051179.JPG', p.LOCAL/'tests/missing.JPG', c/'R8051182.JPG'], 2, 'abnormal'),
    ]
    results = []
    for name, frames, exitcode, verdict in cases:
        out = p.LOCAL/'tests/cli'/name
        argv = [sys.executable, '-I', '-B', str(p.HERE/'analyze_t3.py'), *map(str, frames), '--out', str(out)]
        run = subprocess.run(argv, cwd=p.ROOT, capture_output=True, text=True, timeout=90)
        p.save(out/'command.log', run.stdout + run.stderr, private=True)
        doc = json.loads((out/'verdict.json').read_text())
        p.require(run.returncode == exitcode and doc['result'] == verdict, 'CLI case failed: ' + name)
        if name == 'full_synthetic':
            p.require(doc['probe2']['result'] == 'functional_pass', 'CLI full sequence lost probe2 delegation')
        results.append({'case': name, 'exit_code': run.returncode, 'result': doc['result'],
                        'pass': True})
    p.dump(p.LOCAL/'tests/cli.json', {'cases': results, 'pass': True}, private=True)
    print('CLI: 3-frame no-change, 5-frame T3+T1, bad count, missing JPEG+DNG pair: 4/4 PASS')


if __name__ == '__main__':
    main()
