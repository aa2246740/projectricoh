"""Trace which repo files the research prediction path imports and reads (read-only).

Run with the interpreter the research code was written for:
    /usr/bin/python3 -B research/studio_engine_e0/tools/trace_closure.py
Output: research/studio_engine_e0/local/closure_trace.json (ignored directory).
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'research/knobs_v2_r2/src'
OUT = ROOT / 'research/studio_engine_e0/local/closure_trace.json'
sys.path.insert(0, str(SRC))

phase = ['start']
opened = {}
active = [True]


def hook(event, args):
    if event == 'socket.connect':
        raise PermissionError('network forbidden')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        mode, flags = args[1], args[2]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        p = Path(os.fsdecode(args[0])).absolute()
        if writing and active[0]:
            raise PermissionError('trace is read-only: ' + str(p))
        try:
            rel = str(p.resolve().relative_to(ROOT))
        except ValueError:
            return
        opened.setdefault(phase[0], set()).add(rel)


sys.addaudithook(hook)
before = set(sys.modules)
import numpy as np  # noqa: E402
import model_adapter  # noqa: E402  (imports support, knobs)
import knobs  # noqa: E402
import menu  # noqa: E402
phase[0] = 'import'
after_import = set(sys.modules)
phase[0] = 'Model()'
m = model_adapter.Model()
phase[0] = 'predict'
data = menu.load()
modules = __import__('support').parse() if False else None  # parse() needs the g123 DAT; traced separately
with np.load(ROOT / 'research/knobs_v2_r2/local/apple_input.npz', allow_pickle=False) as z:
    x = z['x'].copy()
base = bytearray(552)  # unused: predict needs a real entry; use DEEPTBL-free stock from the g123 DAT below
phase[0] = 'parse(g123 DAT)'
import support  # noqa: E402
mods = support.parse()
stock, b1 = mods[0]['entries'][4], mods[0]['entries'][1]
phase[0] = 'predict'
rgb = m.predict(b1, x, quantize=True)
phase[0] = 'masks'
model_adapter.masks(m, b1, x[:500], 'contrast')
phase[0] = 'provenance'
prov = m.provenance()


def mods_in_repo():
    out = {}
    for name, mod in sys.modules.items():
        f = getattr(mod, '__file__', None)
        if not f:
            continue
        try:
            rel = str(Path(f).resolve().relative_to(ROOT))
        except ValueError:
            continue
        out[name] = rel
    return out


active[0] = False
sha = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
result = {
    'python': sys.version,
    'numpy': np.__version__,
    'repo_modules_imported': mods_in_repo(),
    'files_read_by_phase': {k: sorted(v) for k, v in opened.items()},
    'provenance_used': prov,
    'sha256': {p: sha(p) for p in sorted(set().union(*opened.values())) if (ROOT / p).is_file()},
}
OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + '\n')
print('traced', sum(len(v) for v in opened.values()), 'reads')
