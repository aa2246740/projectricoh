"""Record a foreground quality command and its exact result."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, ROOT, save, file_sha

label = sys.argv[1]
args = sys.argv[2:]
assert label.replace('-', '').replace('_', '').isalnum() and args
destination = OUT / 'commands' / label
destination.mkdir(parents=True, exist_ok=False)
start = time.monotonic()
sources = {q.name: file_sha(q) for q in sorted(OUT.glob('*.py'))}
with (destination / 'stdout.txt').open('w') as stdout, (destination / 'stderr.txt').open('w') as stderr:
    p = subprocess.Popen(args, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0'),
                         stdout=subprocess.PIPE, stderr=stderr, text=True)
    save('commands/' + label + '/owner.json', dict(pid=p.pid, started_utc=datetime.now(timezone.utc).isoformat(), argv=args, sources=sources))
    for line in p.stdout:
        stdout.write(line)
        stdout.flush()
        print(line, end='', flush=True)
    code = p.wait()
save('commands/' + label + '/command.json', dict(argv=args, cwd=str(ROOT), returncode=code,
    seconds=time.monotonic()-start, sources=sources))
if code:
    print((destination / 'stderr.txt').read_text(), file=sys.stderr)
raise SystemExit(code)
