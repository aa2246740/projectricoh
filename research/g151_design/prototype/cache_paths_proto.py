"""Same observation as cache_paths.py, on the Scratch prototype DAT (g150 + design A + B)."""
import sys, os
from pathlib import Path
S = Path(os.environ['TMPDIR'])
sys.path.insert(0, str(S / 'probe'))
import cache_paths as C
H = C.H
H.PACKAGE = S / 'pkg/local/SD_ROOT'; H.DAT = H.PACKAGE / 'GXRCE.DAT'; H.BODY = H.PACKAGE / 'ilaunch3'
H.ENGINE = S / 'proto/engine_v58_g150/candidate/local/full-r13/engine.elf'
H.LOCAL = S / 'probe/host-proto'
C.OUT = S / 'probe-proto'
def setup():
    sys.dont_write_bytecode = True
    H.LOCAL.mkdir(parents=True, exist_ok=True); H.TMP.mkdir(parents=True, exist_ok=True)
    assert H.sha(H.BODY) == H.BODY_SHA
H.setup = setup
import json
setup()
rows = [C.run('open-ok', 7, [], 'ok'), C.run('nav-ok', 2, ['DOWN', 'DOWN'], 'ok'),
        C.run('nav-menu', 6, ['DOWN', 'UP', 'UP'], 'menu'), C.run('nav-half0d', 4, ['UP'], 'half0d'),
        C.run('nav-raw-half', 3, ['DOWN'], 'raw_half')]
C.OUT.mkdir(parents=True, exist_ok=True)
(C.OUT / 'cache-paths.json').write_text(json.dumps(rows, indent=1) + '\n')
