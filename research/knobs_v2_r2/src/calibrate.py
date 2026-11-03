"""Deterministic visible steps measured on the unchanged r1 chart and masks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import support as s
s.dependencies()
import csv
import hashlib
import time
import numpy as np
import knobs as k
from bridge import C, compare
from model_adapter import Model, recipe_chart, masks

THRESHOLD = 1.0
COLOUR = ('amount', 'contrast', 'highlight', 'shadow', 'fade', 'saturation', 'warmth', 'tint', 'split')
BW = ('contrast', 'highlight', 'shadow', 'fade', 'filter')


def controls(slot):
    return BW if slot == 3 else tuple(p for p in COLOUR if not (slot == 4 and p == 'amount'))


class Meter:
    def __init__(self, model, c, stock, base, param, x):
        self.model, self.c, self.stock, self.base, self.param = model, c, stock, base, param
        regions = masks(model, base, x, param, chart=True)
        assert all(int(r.sum()) >= 16 for r in regions)
        union = np.logical_or.reduce(regions)
        self.x = x[union]
        self.regions = [r[union] for r in regions]
        self.cache = {}

    def output(self, dose):
        if dose not in self.cache:
            rq = k.Request(dose) if self.param == 'amount' else k.request_for(self.param, dose)
            b, stats = self.c.apply(self.stock, self.base, rq)
            rgb = self.model.predict(b, self.x, quantize=True)
            self.cache[dose] = (b, self.model.lab(rgb), stats)
        return self.cache[dose]

    def pair(self, a, b):
        aa, la, _ = self.output(a)
        bb, lb, _ = self.output(b)
        de = self.model.de(la, lb)
        med = [float(np.median(de[r])) for r in self.regions]
        return dict(dose_from=a, dose_to=b, region_medians=med,
                    region_counts=[int(r.sum()) for r in self.regions],
                    min_median_de00=min(med), byte_dead=aa == bb,
                    visible=min(med) >= THRESHOLD and aa != bb)

    def metric(self, a, b):
        return self.pair(a, b)['min_median_de00']


def tune(meter, param):
    levels = {0: 0}
    caps = []
    end = k.MAX_DOSES[k.PARAMS.index(param)]
    for sign in ((1,) if param == 'fade' else (-1, 1)):
        previous = 0
        for level in range(1, 10):
            # Search actual generated integer states. No convexity budget or
            # increasing perceptual target consumes the remaining range.
            target = THRESHOLD
            chosen = None
            left = previous + 1
            for right in range(min(end, left + 63), end + 64, 64):
                right = min(end, right)
                if meter.metric(sign * previous, sign * right) >= target:
                    lo, hi = left, right
                    while lo < hi:
                        mid = (lo + hi) // 2
                        if meter.metric(sign * previous, sign * mid) >= target:
                            hi = mid
                        else:
                            lo = mid + 1
                    # Quantized medians need not be strictly monotone.
                    # Check the complete preceding bracket before accepting.
                    chosen = next(d for d in range(left, lo + 1)
                                  if meter.metric(sign * previous, sign * d) >= target)
                    break
                if right == end:
                    break
                left = right + 1
            if chosen is None:
                remaining = [(d, meter.metric(sign * previous, sign * d))
                             for d in range(previous + 1, end + 1)]
                visible = [(d, v) for d, v in remaining if v >= target]
                if visible:
                    chosen = visible[0][0]
                else:
                    best = max(remaining, key=lambda z: z[1], default=(previous, 0.0))
                    caps.append(dict(direction=sign, last_level=sign * (level - 1),
                                     last_dose=sign * previous, domain_end=sign * end,
                                     exhaustive_remaining_count=len(remaining),
                                     remaining_best_dose=sign * best[0], remaining_best_de00=best[1],
                                     endpoint_de00=meter.metric(sign * previous, sign * end),
                                     endpoint_stats=meter.output(sign * end)[2],
                                     reason='pending evidence classification'))
                    break
            levels[sign * level] = sign * chosen
            previous = chosen
        if param == 'filter':
            # Preserve fixed green/red semantic endpoints. All stretched
            # adjacent pairs are remeasured; no interpolation claim is used.
            last = max(abs(a) for a in levels if a * sign > 0)
            endpoint = abs(levels[sign * last])
            for i in range(1, last + 1):
                levels[sign * i] = sign * k.rd(abs(levels[sign * i]) * k.Q, endpoint)
    pairs = []
    ordered = sorted(levels)
    for a, b in zip(ordered, ordered[1:]):
        pairs.append(dict(from_level=a, to_level=b, **meter.pair(levels[a], levels[b])))
    return levels, pairs, caps


def amount(meter):
    attempts = []
    for step in (10, 20, 25):
        ticks = list(range(0, 151, step))
        if ticks[-1] != 150:
            ticks.append(150)
        pairs = [dict(from_level=a, to_level=b, **meter.pair(a, b)) for a, b in zip(ticks, ticks[1:])]
        attempts.append(dict(step=step, ticks=ticks, pairs=pairs))
        if all(p['visible'] for p in pairs):
            return {a: a for a in ticks}, pairs, step, attempts
    raise ValueError('Amount cannot pass at 10/20/25 percent: ' + str(attempts))


def main():
    s.guard()
    s.freeze_inputs()
    modules = s.parse()
    c, model = C(), Model()
    groups, variants, caps, rows = [], [], [], []
    binary = bytearray()
    start = time.monotonic()
    for module in modules:
        unit, stock = module['name'], module['entries'][4]
        for slot in range(1, 9):
            base = module['entries'][slot]
            regenerated = recipe_chart(model, base)
            with np.load(s.ROOT / f'research/knobs_v2_r1/local/chart-{unit}-{slot:02d}.npz', allow_pickle=False) as z:
                x = z['x'].copy()
                assert np.max(np.abs(regenerated-x)) < 1e-9, 'r1 chart changed'
            np.savez_compressed(s.LOCAL / f'chart-{unit}-{slot:02d}.npz', x=x)
            for param in controls(slot):
                meter = Meter(model, c, stock, base, param, x)
                if param == 'amount':
                    doses, pairs, step, attempts = amount(meter)
                    limited = []
                else:
                    doses, pairs, limited = tune(meter, param)
                    step, attempts = 0, []
                group = dict(unit=unit, unit_index=module['unit'], slot=slot, param=param,
                             wb_method=0, tone_method=0, doses={str(a): d for a, d in sorted(doses.items())},
                             pairs=pairs, cap_lower=int(any(z['direction'] < 0 for z in limited)),
                             cap_upper=int(any(z['direction'] > 0 for z in limited)),
                             amount_step=step, amount_attempts=attempts)
                groups.append(group)
                for limited_direction in limited:
                    caps.append(dict(unit=unit, slot=slot, param=param, **limited_direction))
                for level, dose in sorted(doses.items()):
                    rq = k.Request(level) if param == 'amount' else k.request_for(param, dose)
                    b, stats = compare(c, stock, base, rq)
                    variants.append(dict(unit=unit, slot=slot, param=param, level=level, dose=dose,
                                         offset=len(binary), sha256=hashlib.sha256(b).hexdigest(), stats=stats))
                    binary.extend(b)
                    rows.append(dict(unit=unit, slot=slot, param=param, level=level, dose=dose))
                print(unit, f'{slot:02d}', param, 'levels', min(doses), max(doses),
                      'minDE', round(min(p['min_median_de00'] for p in pairs), 4),
                      'caps', len(limited), f'{time.monotonic()-start:.1f}s', flush=True)
            # Checkpoint is local and complete only for processed recipes.
            s.dump(s.LOCAL / 'calibration_checkpoint.json', dict(groups=groups, caps=caps))
    (s.LOCAL / 'variants.bin').write_bytes(binary)
    s.dump(s.LOCAL / 'variants.json', variants)
    s.dump(s.LOCAL / 'caps.json', caps)
    failures = [dict(unit=g['unit'], slot=g['slot'], param=g['param'], **p)
                for g in groups for p in g['pairs'] if not p['visible']]
    s.dump(s.LOCAL / 'calibration_failures.json', failures)
    s.dump(s.LOCAL / 'calibration.json', dict(schema='knobs-v2-r2/calibration/1', threshold=THRESHOLD,
           sample_kind='unchanged r1 recipe chart and fixed baseline masks', groups=groups,
           groups_count=len(groups), variants_count=len(variants), elapsed_seconds=time.monotonic()-start))
    with (s.HERE / 'tables/steps.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    s.dump(s.LOCAL / 'model_inputs_calibration.json', model.provenance())
    s.verify_inputs()
    print('DONE', len(groups), 'groups', len(variants), 'states', len(failures), 'failures', len(caps), 'caps', flush=True)
    if failures:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
