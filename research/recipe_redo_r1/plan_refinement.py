"""Allocate extra solve budget by training/solver evidence only."""
from pathlib import Path
import argparse
import datetime
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from capabilities import main_level

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--unit', required=True, choices=('mount-a12','a12-50','a12-28'))
    ap.add_argument('--nfev', type=int, default=250)
    ap.add_argument('--tag', required=True)
    args = ap.parse_args()
    level = main_level(args.unit)
    rows = []
    for index in range(35):
        if index==30:
            continue
        paths = (HERE/'local/fits'/args.unit/f'{index:02d}').glob(f'L{level}_*.json')
        docs = [(p,json.loads(p.read_text())) for p in paths]
        valid = [(p,d) for p,d in docs if d['quality']['passes']]
        assert valid, (args.unit,index,'Missing completed first-pass record')
        p,d = min(valid,key=lambda x:(x[1]['objective'],str(x[0])))
        limited = any(not a['success'] and a['status']==0 for _,doc in docs for a in doc['solver_attempts'])
        held_current = d['origin']=='retained_current'
        if limited or held_current:
            rows.append(dict(index=index, name=d['name'], selected_training_objective=d['objective'],
                             source_fit=str(p.relative_to(HERE)), reached_solver_limit=limited,
                             retained_current=held_current))
    path = HERE/'local/refinement_plans'/(args.tag+'.json')
    path.parent.mkdir(exist_ok=True)
    assert not path.exists()
    result = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), unit=args.unit,
                  level=level, nfev=args.nfev, criterion='any first-pass start reached its limit or no feasible improved training solution',
                  photo_or_synthetic_holdout_read=False, profiles=rows,
                  batches=[[r['index'] for r in rows[i:i+6]] for i in range(0,len(rows),6)])
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'unit':args.unit,'count':len(rows),'batches':result['batches']},ensure_ascii=False))


if __name__=='__main__':
    main()
