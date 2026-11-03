"""Run one unit's remaining cases and retain each foreground command result."""
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, file_sha
from run_queue import commands

unit = sys.argv[1]
assert unit in ('50mm', '28mm', 'mount')
rows = []
selected = [parts for parts in commands() if unit in parts and
            parts[0] != 'fn2_all.py' and parts[:2] != ('run_native.py', 'matrix')]
folder = OUT/'commands'
folder.mkdir(exist_ok=True)
for index, parts in enumerate(selected):
    label = 'remaining-'+unit+'-'+str(index+1).zfill(2)+'-'+parts[0].removesuffix('.py')
    log = folder/(label+'.log')
    print('RUN', unit, index+1, '/', len(selected), parts, flush=True)
    started = time.monotonic()
    with log.open('w') as output:
        result = subprocess.run(['/usr/bin/python3','-I','-B',str(OUT/parts[0]),*parts[1:]],
                                cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
    rows.append(dict(command=parts, returncode=result.returncode,
                     seconds=time.monotonic()-started, log=str(log.relative_to(OUT)),
                     source_script_sha256=file_sha(OUT/parts[0])))
    save('remaining-'+unit+'.json', dict(status='RUNNING', unit=unit, commands=rows, total=len(selected)))
    print('DONE', unit, index+1, result.returncode, flush=True)
save('remaining-'+unit+'.json',dict(status='PASS' if all(x['returncode']==0 for x in rows) else 'FAIL',
                                  unit=unit, commands=rows, total=len(selected)))
