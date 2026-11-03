"""Small independent Windows runtime cases; not executed on the review host."""
import argparse
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--scratch', type=Path, required=True)
p.add_argument('--case', choices=('io','loop','lut'), required=True)
a = p.parse_args()
if sys.platform != 'win32':
    raise SystemExit('This entry requires Windows; the macOS host does not run it')
a.scratch.mkdir(parents=True, exist_ok=False)
os.environ['TMPDIR'] = os.environ['TEMP'] = os.environ['TMP'] = str(a.scratch)
sys.path.insert(0, str(a.source.resolve()/'src'))
from gxr_studio import audit, osplat
print(json.dumps({'platform':sys.platform,'python':sys.version,'case':a.case,'osplat_sha256':hashlib.sha256(Path(osplat.__file__).read_bytes()).hexdigest()}),flush=True)
faulthandler.dump_traceback_later(120, exit=True)
try:
    if a.case == 'io':
        from gxr_studio.privacy import PrivateDir
        root = a.scratch/'app-data'
        content = bytes(range(256))*16
        with PrivateDir(root,'review') as d:
            one, two = root.stat(), os.fstat(d.fd)
            assert (one.st_dev,one.st_ino)==(two.st_dev,two.st_ino)
            d.write('nested/first.bin',content)
            assert d.read('nested/first.bin')==content
            assert d.names('nested')==['first.bin']
            d.replace_file('nested/first.bin',content[::-1])
            assert d.read('nested/first.bin')==content[::-1]
            d.remove('nested')
            assert not d.exists('nested')
        print('Windows handle primitives passed',flush=True)
    elif a.case == 'loop':
        import asyncio
        audit.forbid_network(True)
        try:
            loop = asyncio.new_event_loop()
            loop.close()
        finally:
            print(json.dumps({'network_attempts':audit.network_attempts()}),flush=True)
            audit.forbid_network(False)
    else:
        import numpy as np
        from gxr_studio.gpu.tables import lut_bytes
        from gxr_studio.lut.cube import Cube
        from gxr_studio.lut.spaces import Target
        v = np.linspace(0,1,17)
        nodes = np.clip(np.array([[r,g,b] for b in v for g in v for r in v])*[.86,.97,1.05],0,1)
        text = 'LUT_1D_SIZE 3\nLUT_3D_SIZE 17\n0 0 0\n0.6 0.55 0.5\n1 1 1\n'+'\n'.join(' '.join(f'{c:.17g}' for c in row) for row in nodes)+'\n'
        data,meta,reason = lut_bytes(Target(Cube.parse(text),'srgb','vlog'))
        assert data is not None and len(data)==67108864 and reason is None
        print(json.dumps({'bytes':len(data),'meta':meta,'sha256':hashlib.sha256(data).hexdigest()}),flush=True)
finally:
    faulthandler.cancel_dump_traceback_later()
