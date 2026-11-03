"""Run bounded independent per-profile jobs, without shared numerical writers."""
import argparse
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from capabilities import main_level

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--unit', choices=('mount-a12', 'a12-50', 'a12-28'), required=True)
    ap.add_argument('--indices', required=True)
    ap.add_argument('--nfev', type=int, default=100)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--workers', type=int, choices=(1, 2, 3), default=2)
    ap.add_argument('--level',type=int,choices=(0,1))
    ap.add_argument('--backend',choices=('fast','guarded_normal'),default='guarded_normal')
    args = ap.parse_args()
    indices = []
    for part in args.indices.split(','):
        if ':' in part:
            lo, hi = map(int, part.split(':'))
            indices.extend(range(lo, hi))
        else:
            indices.append(int(part))
    assert len(indices) == len(set(indices)) and indices and all(0 <= i < 35 for i in indices)
    assert len(indices) <= 9, 'Split each batch into at most nine profiles'
    assert Path(args.tag).name == args.tag and '.' not in args.tag
    level = main_level(args.unit) if args.level is None else args.level
    backend=args.backend
    if backend=='guarded_normal' and list((HERE/'local/solver_unit_fallback'/args.unit).glob('*.json')):
        backend='fast'
        print('UNIT FALLBACK',args.unit,'exact',flush=True)
    folder = HERE/'local/batches'/args.tag
    folder.mkdir(parents=True, exist_ok=False)
    authorization = json.loads((HERE/'local/fast_switch_authorization.json').read_text())
    assert authorization['solver'] == 'exact' and authorization['equivalence_passed']
    assert args.workers <= authorization['max_compute_processes']
    start = time.monotonic()
    created = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def one(index):
        command = [sys.executable, '-I', '-B', str(HERE/'fit_one.py'),
                   '--unit', args.unit, '--index', str(index), '--level', str(level),
                   '--nfev', str(args.nfev), '--guarded', '--backend', backend, '--tag', args.tag]
        before = time.monotonic()
        print('START', args.unit, index, 'L'+str(level), flush=True)
        with (folder/f'{index:02d}.log').open('w') as stream:
            try:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1500)
                code, error = result.returncode, None
            except subprocess.TimeoutExpired:
                code, error = -1, 'per-profile 1500-second timeout'
        row = dict(index=index, command=command, exit_code=code, error=error,
                   elapsed_seconds=time.monotonic()-before, log=str((folder/f'{index:02d}.log').relative_to(HERE)))
        print('FINISH', args.unit, index, 'exit', code, 'seconds', round(row['elapsed_seconds'], 2), flush=True)
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(one, indices))
    receipt = dict(created_utc=created, unit=args.unit, level=level, tag=args.tag,
                   workers=args.workers, max_nfev=args.nfev, results=rows,
                   backend=backend,solver_config='guarded_normal' if backend=='guarded_normal' else 'exact',
                   wall_seconds=time.monotonic()-start, all_passed=all(r['exit_code']==0 for r in rows),
                   no_parameter_selection_by_holdout=True, no_dat_built=True)
    (folder/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    assert receipt['all_passed'], 'A profile failed; retain its first log and diagnose before another fresh-tag run'


if __name__ == '__main__':
    main()
