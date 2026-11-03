"""Check the operating-system write fence before running reused checks."""
import json
import os
from pathlib import Path
import socket

OUT = Path(__file__).resolve().parent
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g138')
checks = {}
for name, path in [('review', OUT / 'local/scope-probe'), ('temporary', TMP / 'scope-probe')]:
    path.write_text('scope-check\n')
    path.unlink()
    checks[name] = 'ALLOWED'
path = TMP.parent / '.review-g138-denied-probe'
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except PermissionError:
    checks['outside_write'] = 'DENIED'
else:
    os.close(descriptor)
    path.unlink()
    raise AssertionError('The operating-system write fence allowed an outside write')
try:
    with socket.socket() as stream:
        stream.connect(('127.0.0.1', 9))
except PermissionError:
    checks['network'] = 'DENIED'
else:
    raise AssertionError('The operating-system network fence did not deny the connection')
(OUT / 'evidence/scope-check.json').write_text(json.dumps(checks, indent=2) + '\n')
print(json.dumps(checks), flush=True)
