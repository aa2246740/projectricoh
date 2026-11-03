"""Run the gen 146 host acceptance cases one after another (one test process at a time).

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/unit28-r5 \
       /usr/bin/python3 -I -B research/unit28_stock/run_accept146.py <out-dir-under-TMPDIR> [case ...]
Each case gets 600 s (history: 35-60 s per case). Writes <out>/summary.json and <out>/DONE.
Two accumulating sequences use one card file each, like the real card:
  boots: 50mm (session 1), 28mm notready (no write), 50mm again (session 2, other half)
  three-units: 28mm-refuse, mount, 50mm (one file with three slots)
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = Path(os.environ['TMPDIR'])
assert SCRATCH == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/unit28-r5')
OUT = SCRATCH / sys.argv[1]
CASES = ['50mm', 'mount', '28mm', '28mm-refuse', '28mm-retire', 'notready', 'nofile', 'badheader', 'short', 'busy',
         'busyall', 'partial', 'cuts', 'noreadback', 'closefail', 'allwritefail', 'svcfail', 'ingress-I', 'name-zero',
         'name-qlaunchX', 'name-l08firmX', 'seq:boots', 'seq:three-units']
SEQUENCES = {'boots': [('50mm', '50mm'), ('notready', 'notready'), ('50mm', '50mm-again')],
             'three-units': [('28mm-refuse', '28mm'), ('mount', 'mount'), ('50mm', '50mm')]}


def run(case, label, card=None):
    log = OUT / (label + '.log')
    started = time.monotonic()
    args = ['/usr/bin/python3', '-I', '-B', str(HERE / 'accept_diag146.py'), case]
    if card:
        args.append(str(card))
    with log.open('w') as stream:
        try:
            rc = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, timeout=600,
                                cwd=HERE.parents[1]).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    tail = log.read_text().strip().splitlines()[-1:] or ['']
    return dict(case=case, label=label, rc=rc, seconds=round(time.monotonic() - started, 1), last=tail[0][:300])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in (sys.argv[2:] or CASES):
        if case.startswith('seq:'):
            name = case[4:]
            card = OUT / (name + '.bin')
            if card.exists():
                card.unlink()
            for sub, label in SEQUENCES[name]:
                rows.append(run(sub, name + '-' + label, card))
                print(json.dumps(rows[-1]), flush=True)
        else:
            rows.append(run(case, case))
            print(json.dumps(rows[-1]), flush=True)
    ok = all(r['rc'] == 0 for r in rows)
    (OUT / 'summary.json').write_text(json.dumps(dict(ok=ok, rows=rows), indent=1) + '\n')
    (OUT / 'DONE').write_text(('PASS' if ok else 'FAIL') + '\n')


if __name__ == '__main__':
    main()
