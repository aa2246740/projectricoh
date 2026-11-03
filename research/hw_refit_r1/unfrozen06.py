"""Check all existing ordinary controls for 06, including its previously frozen sectors."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import *
import run
import report
from integer_refine import refine
from verify import packed_predict


class UnfrozenProblem(Problem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.slot != '06' or not self.daily or 'sector' in self.blocks:
            return
        previous = self.np
        self.add('sector', 48, 32., .04)
        self.R = np.pad(self.R, ((0, 0), (0, 48)))
        eye = np.eye(self.np)
        self.R = np.vstack([self.R, .04 * eye[previous:]])
        for base in (previous, previous + 24):
            self.R = np.vstack([self.R, *[(.10 * (eye[base + i] - eye[base + (i + 1) % 24]))[None] for i in range(24)]])
        self.cache = None


def main():
    m = rt.model()
    data = {fold: prepare_data(m, '06', fold) for fold in run.FOLDS}
    original_local = rt.LOCAL
    rt.LOCAL = original_local / 'unfrozen06'
    rt.LOCAL.mkdir(exist_ok=True)
    run.Problem = UnfrozenProblem
    selected = ['baseline'] + [name for name, (_, daily) in run.routes().items() if daily]
    direction_checks, maximum_replay, completed = [], 0., 0
    for fold in run.FOLDS:
        d = data[fold]
        for name in selected:
            features, daily = run.routes()[name]
            doc = run.run_one(m, '06', fold, name, d, max_nfev=80)
            path = rt.LOCAL / f'fits/06/{name}/{fold}.json'
            doc['scope_variant'] = '06 existing symmetric sectors free; same pixel equations and bounds'
            doc['scope_model_sha256'] = rt.sha(Path(__file__))
            rt.dump(path, doc)
            P = UnfrozenProblem(m, '06', d, features, daily)
            if fold == 'page1' and name == 'joint_C120_Y':
                rng = np.random.default_rng(8)
                p = rng.normal(size=P.np) * .05
                v = rng.normal(size=P.np)
                v /= np.linalg.norm(v)
                _, J = P.evaluate(p)
                fd = (P.evaluate(p + 1e-6 * v)[0] - P.evaluate(p - 1e-6 * v)[0]) / 2e-6
                relative = float(np.linalg.norm(fd - J @ v) / np.linalg.norm(fd))
                assert relative < 3e-4, relative
                direction_checks.append(dict(route=name, parameters=P.np, relative_error=relative))
            if any(k in features for k in ('offsets', 'tint_add', 'tint_Y', 'gain_Y', 'gain_C', 'gain_C2', 'rlut')):
                dest = rt.LOCAL / f'integer_refined/06/{name}/{fold}.json'
                if dest.exists():
                    rd = rt.read(dest)
                    ra = rt.arrays(dest.with_suffix('.npz'))
                    pred = ra['prediction_integer']
                else:
                    rd, pred, error = refine(m, d, doc, problem=P)
                    rt.dump(dest, rd)
                    np.savez_compressed(dest.with_suffix('.npz'), prediction_integer=pred, error_integer=error)
                independent = packed_predict(m, '06', d, rd)
            else:
                a = rt.arrays(path.with_suffix('.npz'))
                pred = a['prediction_integer']
                independent = packed_predict(m, '06', d, doc)
            error = float(np.max(abs(independent - pred)))
            assert error < 1e-8
            maximum_replay = max(maximum_replay, error)
            completed += 1
    rows = []
    for name in selected:
        for scheme, folds in [('page', run.FOLDS[:6]), ('hue', run.FOLDS[6:9]), ('full', ['full'])]:
            row = report.collect('06', name, folds)
            row['route'] = 'u06_' + name
            row['scheme'] = scheme
            row['scope_variant'] = '06 symmetric sectors free'
            rows.append(row)
    rt.dump(rt.HERE / 'unfrozen06_summary.json', dict(rows=rows, fits=completed,
            jacobian_checks=direction_checks, independent_packed_max_rgb=maximum_replay,
            note='06 primary legacy-policy fit freezes sectors; this alternative covers all existing ordinary sector controls'))
    rt.dump('verification/final.json', dict(fits=completed, jacobians=direction_checks,
                                          independent_packed_max_rgb=maximum_replay))
    rt.finish('unfrozen06')
    print('06 all-current-control sensitivity complete', completed, maximum_replay, flush=True)


if __name__ == '__main__':
    main()
