#!/usr/bin/env python3
"""A: g139 user entry = built-in base + integer Cont/High/Shad/Satu (v1 domain).

Scoring population: the r7 50mm 04 exchange frames (usable rows). Each row's
scene input x comes from the paired 04 inverse, so 04 at x reproduces the
measured GXR 04 JPEG; recipe = DAT entry after the frozen r2 knob math.
Similarity = 1 - median(recipe->target) / median(04->target), pooled over held-out
pages / hue groups; levels are chosen on training rows only (median DeltaE00).
"""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import itertools
import entries as E
from target import DenseTarget

R7 = rt.ROOT / 'research/refit_50mm_r7'
FOLDS = [f'page{i}' for i in range(1, 7)] + [f'hue{i}' for i in range(3)]
V1 = {1: 'Cont', 2: 'High', 3: 'Shad', 5: 'Satu'}
NAMES = ('GRP', 'GRN', 'HCB', 'STD', 'FCC', 'FCN', 'LCH', 'LVI')


def prepare():
    m = rt.model()
    rt.calibration_modules()
    f = rt.module('refit', R7 / 'refit.py')
    rows, good, _ = f.data(m)
    q = [r for r in rows['04'] if r['usable']]
    raw = np.array([np.array(r['raw_rgb']) * r['meta']['white_balance']['gains'] for r in q])
    rgb = np.array([r['jpeg_rgb'] for r in q])
    x, bad = m.inverse04(rgb, raw)
    base_lab = m.fs.lab_from_codes(rgb)
    target, supported, distance = DenseTarget().target(x, base_lab)
    supported &= ~bad
    (rt.LOCAL / 'score').mkdir(exist_ok=True)
    np.savez_compressed(rt.LOCAL / 'score/data.npz', x=x, base_rgb=rgb, base_lab=base_lab, target=target, supported=supported, inverse_failed=bad,
        distance=distance, pages=np.array([r['page'] for r in q]), hue_group=np.array([r['hue_group'] for r in q]))
    rt.dump('score/records.json', [dict(frame=r['frame'], patch_id=r['patch_id'], page=r['page'],
        key=r['sample_key'], hue_group=r['hue_group']) for r in q])
    t = target[supported]
    rt.dump('score/protocol.json', dict(n_rows=len(q), n_supported=int(supported.sum()),
        n_inverse_failed=int(bad.sum()), n_outside_target=int((~supported & ~bad).sum()),
        pages=sorted({int(p) for p in np.array([r['page'] for r in q])}),
        target_L=[float(t[:, 0].min()), float(t[:, 0].max())],
        baseline_04_de00=rt.stats(m.fs.delta_e00(base_lab[supported], t)),
        population='refit_50mm_r7 exchange 04 usable rows; 04 inverse; same dense GR IV paired target',
        camera_acceptance=False))
    print('rows', len(q), 'supported', int(supported.sum()), flush=True)


def load():
    with np.load(rt.LOCAL / 'score/data.npz', allow_pickle=False) as z:
        d = dict(z)
    s = d['supported']
    return {k: v[s] for k, v in d.items() if len(v) == len(s)}


def held_mask(d, fold):
    return d['pages'] == int(fold[4:]) if fold.startswith('page') else d['hue_group'] == int(fold[3:])


class Scorer:
    def __init__(self, unit=0):
        self.m = rt.model()
        self.mods = E.parse()
        self.data = E.table()
        self.unit = unit
        self.stock = self.mods[unit]['entries'][4]
        self.d = load()
        self.baseline = self.m.fs.delta_e00(self.d['base_lab'], self.d['target'])

    def errors(self, slot, levels):
        req = E.request(self.data, self.unit, slot, levels)
        b = E.apply(self.stock, self.mods[self.unit]['entries'][slot], req)
        rgb = E.predict(self.m, b, self.stock, self.d['x'])
        return self.m.fs.delta_e00(self.m.fs.lab_from_codes(rgb), self.d['target'])


def score(err, base):
    return dict(similarity=float(1 - np.median(err) / np.median(base)), de00=rt.stats(err), baseline=rt.stats(base))


def exhaustive(base_slot):
    sc = Scorer()
    knobs_here = [c for c in V1 if c != 5 or base_slot != 3]
    grid = list(itertools.product(range(-5, 6), repeat=len(knobs_here)))
    err = np.empty((len(grid), len(sc.baseline)), np.float32)
    for i, combo in enumerate(grid):
        err[i] = sc.errors(base_slot, dict(zip(knobs_here, combo)))
    folds = {}
    for fold in FOLDS + ['full']:
        held = held_mask(sc.d, fold) if fold != 'full' else np.zeros(len(sc.baseline), bool)
        train_median = np.median(err[:, ~held], axis=1)
        best = int(np.argmin(train_median))
        folds[fold] = dict(levels=dict(zip([V1[c] for c in knobs_here], grid[best])), train_median=float(train_median[best]),
                           held_errors=err[best, held].tolist(), held_baseline=sc.baseline[held].tolist())
    out = dict(base=base_slot, group=NAMES[base_slot - 1], knobs=[V1[c] for c in knobs_here], grid=len(grid),
               zero=score(err[grid.index(tuple([0] * len(knobs_here)))], sc.baseline), full=folds['full'],
               full_in_sample=score(err[grid.index(tuple(folds['full']['levels'].values()))], sc.baseline))
    for scheme, names in (('page', FOLDS[:6]), ('hue', FOLDS[6:])):
        e = np.concatenate([folds[n]['held_errors'] for n in names])
        b = np.concatenate([folds[n]['held_baseline'] for n in names])
        out[scheme] = dict(score(e, b), folds={n: folds[n]['levels'] for n in names})
    rt.dump(f'user/v1_base{base_slot:02d}.json', out)
    print(NAMES[base_slot - 1], 'zero', round(out['zero']['similarity'] * 100, 1), 'full', folds['full']['levels'],
          round(out['full_in_sample']['similarity'] * 100, 1), 'page', round(out['page']['similarity'] * 100, 1),
          'hue', round(out['hue']['similarity'] * 100, 1), flush=True)


def descent(sc, slot, start, train, controls):
    """Greedy coordinate descent on the training median; deterministic order."""
    current = dict(start)
    best = float(np.median(sc.errors(slot, current)[train]))
    improved = True
    while improved:
        improved = False
        for c in controls:
            item = next(it for it in E.items(sc.data, 0, slot) if it['control'] == c)
            for p in item['points']:
                trial = dict(current); trial[c] = p['level']
                if trial == current:
                    continue
                v = float(np.median(sc.errors(slot, trial)[train]))
                if v < best - 1e-9:
                    best, current, improved = v, trial, True
    return current, best


def all_knobs(base_slot, four=False):
    """Reference only: every r2 control (or the four v1 controls) over the full r2 range; not storable in g139."""
    sc = Scorer()
    v1 = rt.read(f'user/v1_base{base_slot:02d}.json')
    controls = [it['control'] for it in E.items(sc.data, 0, base_slot) if not four or it['control'] in V1]
    label = {c['id']: c['label'] for c in sc.data['controls']}
    out = dict(base=base_slot, group=NAMES[base_slot - 1], controls=[label[c] for c in controls],
               storable_in_g139=False, folds={})
    held_err, held_base = {'page': [], 'hue': []}, {'page': [], 'hue': []}
    for fold in FOLDS + ['full']:
        held = held_mask(sc.d, fold) if fold != 'full' else np.zeros(len(sc.baseline), bool)
        lv = v1['full']['levels'] if fold == 'full' else v1['page' if fold.startswith('page') else 'hue']['folds'][fold]
        start = {c: lv[V1[c]] for c in V1 if V1[c] in lv}
        levels, train_median = descent(sc, base_slot, start, ~held, controls)
        e = sc.errors(base_slot, levels)
        out['folds'][fold] = dict(levels={label[c]: v for c, v in levels.items()}, train_median=train_median)
        if fold == 'full':
            out['full_in_sample'] = score(e, sc.baseline)
        else:
            scheme = 'page' if fold.startswith('page') else 'hue'
            held_err[scheme].append(e[held]); held_base[scheme].append(sc.baseline[held])
        print(fold, out['folds'][fold], flush=True)
    for scheme in ('page', 'hue'):
        out[scheme] = score(np.concatenate(held_err[scheme]), np.concatenate(held_base[scheme]))
    rt.dump(f'user/{"four9" if four else "all"}_base{base_slot:02d}.json', out)
    print('all-knob', NAMES[base_slot - 1], {k: round(out[k]['similarity'] * 100, 1) for k in ('full_in_sample', 'page', 'hue')}, flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--base', type=int, choices=range(1, 9))
    ap.add_argument('--all-knobs', type=int, choices=range(1, 9))
    ap.add_argument('--four-wide', type=int, choices=range(1, 9))
    ap.add_argument('--time', type=int)
    a = ap.parse_args()
    if a.prepare:
        prepare()
    if a.time:
        import time
        sc = Scorer(); t = time.time()
        for i in range(a.time):
            sc.errors(4, {1: i % 5, 2: 1, 3: -1, 5: -2})
        print('per eval s', (time.time() - t) / a.time, 'points', len(sc.baseline))
    if a.base:
        exhaustive(a.base)
    if a.all_knobs:
        all_knobs(a.all_knobs)
    if a.four_wide:
        all_knobs(a.four_wide, four=True)
