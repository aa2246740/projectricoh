"""Verify existing results; optionally calculate missing fits, never install."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import s
import argparse
import hashlib
import json
import subprocess


def run_file(script,args=()):
    subprocess.run([sys.executable,'-I','-B',str(rt.HERE/script),*args],cwd=rt.ROOT,check=True)


def fit_missing():
    import refit
    import direct_fit
    folds=[f'page{i}'for i in range(1,7)]+[f'hue{i}'for i in range(3)]+['full']
    if any(not(rt.LOCAL/f'folds/{fold}/calibration.json').exists()for fold in folds):
        run_file('refit.py',['--prepare'])
    common=['--patches',str(rt.DATA/'patches.jsonl'),'--frames',str(rt.DATA/'frames.json'),
            '--unit','50mm','--iso','200']
    cal=rt.LOCAL/'cli/50mm_iso200.json'
    if not cal.exists():
        run_file('calibrate_cli.py',['fit-04',*common,'--holdout-page','6','--output',str(cal)])
    for slot in refit.SLOTS:
        prior=rt.LOCAL/f'cli/50mm_{slot}_residual.json'
        result=rt.LOCAL/f'cli/50mm_{slot}_recipe.json'
        base=[*common,'--slot',slot,'--calibration',str(cal)]
        if not prior.exists():
            run_file('calibrate_cli.py',['learn-50mm-residual',*base,'--output',str(prior)])
        if not result.exists():
            run_file('calibrate_cli.py',['fit-recipe',*base,'--targets',str(rt.DATA/'targets_for_04.json'),
                '--residual-prior',str(prior),'--output',str(result)])
    for fold in folds:
        for slot in refit.SLOTS:
            if not(rt.LOCAL/f'direct/daily/{fold}/{slot}.json').exists():
                direct_fit.run(slot,fold,'daily')
        for slot,variant in [('01','guarded'),('02','guarded'),('05','guarded'),('06','tone')]:
            if not(rt.LOCAL/f'direct/{variant}/{fold}/{slot}.json').exists():
                direct_fit.run(slot,fold,variant)
    for fold in folds[:-1]:
        for variant in ('d8','four','t2'):
            for slot in ('05','06'):
                path=rt.LOCAL/f'direct/{variant}/{fold}/{slot}.json'
                if not path.exists():
                    direct_fit.run(slot,fold,variant)
                if not json.loads(path.read_text())['candidate']['solver_success']:
                    direct_fit.run(slot,fold,variant,max_nfev=240)


def seal():
    files=sorted(p for p in rt.HERE.rglob('*')if p.is_file()and p.name!='SHA256SUMS')
    assert all(not p.is_symlink()for p in files)
    lines=[]
    for path in files:
        h=hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f'{h}  {path.relative_to(rt.HERE)}\n')
    (rt.HERE/'SHA256SUMS').write_text(''.join(lines))
    assert all(hashlib.sha256((rt.HERE/line.split('  ',1)[1].rstrip('\n')).read_bytes()).hexdigest()==line[:64]for line in lines)
    return len(lines)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--fit-missing',action='store_true')
    a=ap.parse_args()
    if a.fit_missing:
        fit_missing()
    before=s.digest(rt.LOCAL/'v6/candidate_v6.DEEPTBL')if(rt.LOCAL/'v6/candidate_v6.DEEPTBL').exists()else None
    run_file('metrics.py')
    run_file('build_v6.py')
    run_file('verify.py')
    after=s.digest(rt.LOCAL/'v6/candidate_v6.DEEPTBL')
    assert before is None or before==after,'regenerated candidate changed'
    rt.dump('verification/reproduction.json',{'candidate_before_sha256':before,
        'candidate_after_sha256':after,'byte_identical':before==after,'all_passed':True})
    run_file('render_report.py')
    print('SHA256SUMS verified:',seal(),'files; no task-external writes or installation.')


if __name__=='__main__':
    main()
