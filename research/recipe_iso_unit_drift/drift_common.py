"""Shared helpers for recipe_iso_unit_drift. Run scripts with python3 -I -B from this directory."""
import importlib.util, json, os, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/iso-drift')
for k in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[k] = '2'
os.environ['TMPDIR'] = str(TMP)
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=float) + '\n')


def safe_rationals(ac):
    """Patch analyze_capture.Tiff so 0/0 rationals (MOUNT has no lens EXIF) read as None."""
    import struct as _st
    _orig = ac.Tiff.ifd
    def _safe_ifd(self, offset, endian=None):
        # same reader, but rationals with zero denominators (MOUNT has no lens data) become None
        e = endian or self.endian
        old = _st.unpack
        def unpack(fmt, raw):
            return old(fmt, raw)
        try:
            return _orig(self, offset, endian)
        except ZeroDivisionError:
            count = _st.unpack_from(e + 'H', self.data, offset)[0]; res = {}
            for i in range(count):
                p = offset + 2 + i * 12; tag, typ, n = _st.unpack_from(e + 'HHI', self.data, p)
                if typ not in self.TYPES: continue
                fmt, size = self.TYPES[typ]; length = n * size
                o = p + 8 if length <= 4 else _st.unpack_from(e + 'I', self.data, p + 8)[0]
                raw = self.data[o:o + length]
                if typ == 2: v = raw.rstrip(b'\0 ').decode('ascii', 'replace')
                elif fmt is None: v = raw
                elif typ in (5, 10):
                    a = _st.unpack(e + fmt * n, raw); v = [a[j] / a[j + 1] if a[j + 1] else None for j in range(0, len(a), 2)]
                else: v = list(_st.unpack(e + fmt * n, raw))
                res[tag] = {'offset': o, 'raw': raw, 'value': v, 'type': typ, 'count': n}
            return res
    ac.Tiff.ifd = _safe_ifd
