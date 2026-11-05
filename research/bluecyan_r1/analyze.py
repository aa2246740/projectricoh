#!/usr/bin/env python3
"""Read-only blue/cyan model research. Derived values only go into local/."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
if not sys.flags.isolated:
    raise SystemExit('Run with Python -I -B')
if os.getpriority(os.PRIO_PROCESS, 0) < 15:
    os.nice(15 - os.getpriority(os.PRIO_PROCESS, 0))
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS',
            'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[key] = '1'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
NOON = ROOT / 'research/noon_sweep_r1/local/noon-20261104-r2'
LOCAL.mkdir(exist_ok=True)
os.environ['MPLCONFIGDIR'] = str(LOCAL / 'mpl')

import argparse
import hashlib
import importlib.util
import json
import struct
import numpy as np


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain(x):
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [plain(v) for v in x]
    if isinstance(x, (np.ndarray, np.generic)):
        return plain(x.tolist())
    if isinstance(x, complex):
        return [x.real, x.imag]
    if isinstance(x, Path):
        return str(x)
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


def dump(name, x):
    p = LOCAL / name
    p.parent.mkdir(parents=True, exist_ok=True)
    temporary=p.with_name(p.name+f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(plain(x), ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    temporary.replace(p)


def read(p):
    return json.loads(Path(p).read_text())


def stats(v):
    v = np.asarray(v)
    return dict(n=len(v), median=float(np.median(v)), p95=float(np.percentile(v, 95)),
                max=float(np.max(v)), rmse=float(np.sqrt(np.mean(v*v))))


def colour_math():
    return module('blue_colour_math', ROOT/'research/color_references/colour_math.py')


def de(a, b):
    cm=colour_math()
    return cm.delta_e00(cm.rgb_lab(np.asarray(a)/255),cm.rgb_lab(np.asarray(b)/255))


def load():
    noon = module('blue_noon', ROOT/'research/noon_sweep_r1/run_noon.py')
    ref = noon.Reference()
    rows = [r for r in read(NOON/'all-patches.json') if r['ROI'] == .4 and r['valid']]
    # Native JPEG chroma is a separate diagnostic; RGB is the DE00 scoring path.
    for r in rows:
        b = ref.entries[r['setting']]
        x = np.array([r['conditioned_input']])
        pre = ref.model.pre(b, x)
        y, ci = ref.mm.MatrixRow.from_bytes(b[216:244]).apply(pre)
        r['pre'] = pre[0]
        r['y'] = y[0]
        r['ci'] = ci[0]
        r['input_hue'] = np.angle(ci[0], deg=True) % 360
        r['input_chroma'] = abs(ci[0])
        r['split'] = ('T' if r['page'].startswith('T') else 'V') if r['kind']=='screen' else 'card'
    return noon, ref, rows


def inspect():
    noon, ref, rows = load()
    b0 = ref.entries['04 Std']
    fields = {'flags':(0,2), 'curve_x':(20,82), 'curve_G':(82,115),
              'sectors':(115,211), 'matrix0':(216,244), 'matrix1':(244,272),
              'secondary_curve_x':(284,346), 'secondary_curve_y':(346,379), 'curve_R':(379,412),
              'curve_B':(412,445), 'type26_control':(445,447), 'iso100':(456,551)}
    all_fields = {}
    for setting,b in ref.entries.items():
        z = ref.fs.Z_of_words(*np.array([ref.fs.decode_word(b[i:i+4])
                    if b[0]!=3 else (0,0) for i in range(115,211,4)]).T, ref.model.engine.ctx)
        all_fields[setting] = dict(sha256=sha(NOON/'records'/(setting.replace(' ','_')+'.record552')),
            flags=b[1], deltas={f:sum(a!=c for a,c in zip(b[lo:hi],b0[lo:hi])) for f,(lo,hi) in fields.items()},
            matrix=ref.mm.MatrixRow.from_bytes(b[216:244]).describe(),
            z=z, max_sector_angle=float(np.max(abs(np.angle(z,deg=True)))),
            max_sector_scale=float(np.max(abs(z))),min_sector_scale=float(np.min(abs(z))))
        print(setting, 'flags',b[1],all_fields[setting]['deltas'],
              'sector angle max',round(all_fields[setting]['max_sector_angle'],2))
    dump('field_inventory.json',all_fields)
    arrays = {}
    baseline = {}
    for setting in ref.entries:
        selected = [r for r in rows if r['setting']==setting]
        if not selected: continue
        x=np.array([r['conditioned_input'] for r in selected]);obs=np.array([r['observed_rgb'] for r in selected])
        pred=ref.predict(setting,x); saved=np.array([r['predicted_rgb'] for r in selected])
        assert np.max(abs(pred-saved))<1e-8
        for split in ('T','V','card'):
            ix=np.array([r['split']==split for r in selected])
            if ix.any():baseline[setting+' '+split]=stats(de(obs[ix],pred[ix]))
        arrays[setting]=dict(rows=selected,x=x,obs=obs,pred=pred)
    dump('baseline.json',baseline)
    dump('patches.json',rows)
    provenance=ref.provenance
    provenance['bluecyan_sources']={str(p.relative_to(ROOT)):sha(p) for p in [
        NOON/'all-patches.json',NOON/'intake-confirmed.json',NOON/'summary.json',
        NOON/'physical-patch-effects.json',HERE/'analyze.py']}
    dump('inputs.json',provenance)
    print(json.dumps(baseline,ensure_ascii=False,indent=1))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['inspect'])
    args=parser.parse_args()
    inspect()
