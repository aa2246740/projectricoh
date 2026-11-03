"""Refit C/C-squared at alternative normalizations; no new data or hardware action."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import *
import run
import report
from integer_refine import refine
from verify import packed_predict

CURRENT_RADIUS = 128.


class RadiusProblem(Problem):
    def forward(self, state, pre, details=False, skip_rlut=False):
        factor = CURRENT_RADIUS / (128 * np.sqrt(2))
        power = 2 if 'gain_C2' in self.blocks else 1
        normalized = dict(state, gain_nodes=state['gain_nodes'] * factor ** power)
        return super().forward(normalized, pre, details, skip_rlut)


def main():
    global CURRENT_RADIUS
    original_local = rt.LOCAL
    m = rt.model()
    data = {(slot,fold):prepare_data(m,slot,fold) for slot in run.SLOTS for fold in run.FOLDS}
    rows, max_error, count = [], 0., 0
    selected = ['solo_C120_C','joint_C120_C','solo_C120_C2','joint_C120_C2']
    run.Problem = RadiusProblem
    for radius in (96.,128.):
        CURRENT_RADIUS = radius
        rt.LOCAL = original_local / f'c120_radius/R{int(radius)}'
        rt.LOCAL.mkdir(parents=True, exist_ok=True)
        for slot in run.SLOTS:
            for fold in run.FOLDS:
                d = data[slot,fold]
                for name in selected:
                    doc = run.run_one(m,slot,fold,name,d,max_nfev=80)
                    doc['c120_radius_max'] = radius
                    path = rt.LOCAL / f'fits/{slot}/{name}/{fold}.json'
                    rt.dump(path,doc)
                    features,daily = run.routes()[name]
                    P = RadiusProblem(m,slot,d,features,daily)
                    dest = rt.LOCAL / f'integer_refined/{slot}/{name}/{fold}.json'
                    if dest.exists():
                        rd=rt.read(dest); pred=rt.arrays(dest.with_suffix('.npz'))['prediction_integer']
                    else:
                        rd,pred,error=refine(m,d,doc,problem=P)
                        rd['c120_radius_max']=radius
                        rt.dump(dest,rd)
                        np.savez_compressed(dest.with_suffix('.npz'),prediction_integer=pred,error_integer=error)
                    independent=packed_predict(m,slot,d,rd)
                    difference=float(np.max(abs(independent-pred)))
                    assert difference<1e-8
                    max_error=max(max_error,difference);count+=1
        for slot in run.SLOTS:
            for name in selected:
                for scheme,folds in [('page',run.FOLDS[:6]),('hue',run.FOLDS[6:9]),('full',['full'])]:
                    row=report.collect(slot,name,folds)
                    row['route']=f'r{int(radius)}_'+name
                    row['scheme']=scheme
                    row['c120_radius_max']=radius
                    rows.append(row)
        rt.finish('radius')
    rt.dump(rt.HERE/'c120_radius_sensitivity.json',dict(rows=rows,fits=count,independent_packed_max_rgb=max_error,
             normalization_main=128*np.sqrt(2),normalization_alternatives=[96,128],
             note='same frozen priors and baseline; refitted both solo and joint C/C-squared, 06 follows primary frozen-sector policy'))
    rt.LOCAL=original_local
    rt.finish('radius_all')
    print('radius sensitivity complete',count,max_error,flush=True)


if __name__=='__main__':main()
