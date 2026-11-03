"""One continuation for iteration-limited fits; selection uses training only.

Keep both candidates and original files. Never select by a held-out score.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pipeline import *
import argparse
import datetime
import json


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--slot',required=True,choices=SLOTS)
    ap.add_argument('--deadline-utc',help='Optional ISO-8601 stop time for this foreground batch')
    args=ap.parse_args();m=rt.model();records=[];data={}
    deadline=datetime.datetime.fromisoformat(args.deadline_utc).astimezone(datetime.timezone.utc) if args.deadline_utc else None
    runner=rt.module('second_pass_runner_for_continuation',rt.HERE/'run.py')
    for path in sorted((rt.LOCAL/f'fits/{args.slot}').glob('*/*.json')):
        previous=rt.read(path)
        if previous['solver']['success'] or 'continuation' in previous:continue
        if deadline is not None and datetime.datetime.now(datetime.timezone.utc)>=deadline:
            print('TIMEBOX_STOP',flush=True);break
        fold=previous['fold']
        if fold not in data:data[fold]=old.prepare_data(m,args.slot,fold)
        d=data[fold]
        P=Pair(m,args.slot,d,previous['tier'],previous['order'],previous['mode'])
        start=np.array(previous['theta_continuous'])
        old_objective=P.integer_objective(np.array(previous['theta']))
        original_json=path.read_bytes();original_npz=path.with_suffix('.npz').read_bytes()
        relative=path.relative_to(rt.LOCAL/'fits')
        before=rt.LOCAL/'continuation_before'/relative
        before.parent.mkdir(parents=True,exist_ok=True)
        before.write_bytes(original_json);before.with_suffix('.npz').write_bytes(original_npz)
        runner.seeds=lambda problem,slot,fold,p=start:(p.copy(),dict(continuation_from_previous_continuous=True,heldout_used=False))
        candidate=runner.one(m,args.slot,fold,d,previous['mode'],previous['order'],previous['tier'],40,True)
        candidate_objective=P.integer_objective(np.array(candidate['theta']))
        dest=rt.LOCAL/'continuation_candidates'/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(path.read_bytes());dest.with_suffix('.npz').write_bytes(path.with_suffix('.npz').read_bytes())
        take=candidate_objective<=old_objective+1e-8
        note=dict(old_training_integer_objective=old_objective,new_training_integer_objective=candidate_objective,
                  candidate_selected=take,heldout_used=False,candidate_converged=candidate['solver']['success'],
                  additional_attempts=candidate['attempts'])
        if take:
            final=candidate;final['attempts']=previous['attempts']+candidate['attempts']
        else:
            final=previous;path.with_suffix('.npz').write_bytes(original_npz)
        final['continuation']=note
        rt.dump(path,final)
        records.append(dict(slot=args.slot,route=previous['route'],fold=fold,**note))
        print(json.dumps(dict(slot=args.slot,route=previous['route'],fold=fold,selected=take,
                              converged=final['solver']['success'],training_gain=old_objective-candidate_objective)),flush=True)
    rt.dump(f'verification/continuation_{args.slot}.json',records)
    rt.finish('continuation_'+args.slot)
    print(json.dumps(dict(slot=args.slot,continued=len(records),selected=sum(r['candidate_selected'] for r in records))),flush=True)


if __name__=='__main__':main()
