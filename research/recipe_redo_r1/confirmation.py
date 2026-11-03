"""Bounded exact confirmation fits and reviewable solver provenance."""
import argparse
import concurrent.futures
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
UNITS = ('mount-a12', 'a12-50', 'a12-28')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def selected(unit, index):
    # The same training-only ordering as report.select, including its shared encoding.
    docs = [(p, read(p)) for p in (HERE/'local/fits'/unit/f'{index:02d}').glob('L1_*.json')]
    docs = [(p, d) for p, d in docs if d['quality']['passes']]
    originals = [(p, d) for p, d in docs if not d.get('canonical_equivalence_parent')]
    best = min(originals, key=lambda pair: (pair[1]['objective'], str(pair[0])))
    parent = str(best[0].relative_to(HERE))
    equivalent = [(p, d) for p, d in docs if d.get('canonical_equivalence_parent') == parent
                  and d['objective'] == best[1]['objective']]
    return min(equivalent, key=lambda pair: str(pair[0])) if equivalent else best


def plan(unit, tag):
    rows = []
    new7 = {r['index']: r for r in read(HERE/'new7_raw_holdout_summary_L1.json')['profiles']}
    for index in range(35):
        path, doc = selected(unit, index)
        if index == 30 or not doc['recommend_next_dat_build']:
            continue
        scenes = doc['per_scene'].get('photo_iso200', {}).values()
        if any(v['candidate']['de00'][k] > v['current']['de00'][k]+1e-10
               for v in scenes for k in ('median', 'p95')):
            continue
        if unit == 'mount-a12':
            assert new7[index]['record_sha256'] == doc['record']['sha256']
            if not new7[index]['scene_gate_pass']:
                continue
        rows.append(dict(unit=unit, index=index, source=str(path.relative_to(HERE)),
                         source_sha256=sha(path), record_sha256=doc['record']['sha256']))
    priority={31:0,32:1,33:2,34:3,29:4,27:5,28:6}
    rows.sort(key=lambda r:(priority.get(r['index'],7),r['index']))
    destination = HERE/'local/confirmations'/tag/'plan.json'
    assert not destination.exists(), 'Keep prior plans and use a fresh tag'
    dump(destination, dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
         unit=unit, profiles=rows, training_selection_only=True, photo_gate_only=True))
    print('Planned exact confirmations', unit, len(rows), flush=True)


def run(tag, lo, hi, workers, nfev, full=False):
    assert workers in (1, 2) and 0 <= lo < hi and hi-lo <= 9
    root = HERE/'local/confirmations'/tag
    data = read(root/'plan.json')
    rows = data['profiles'][lo:hi]
    assert rows
    batch = root/f'batch_{lo:02d}_{hi:02d}'
    batch.mkdir(exist_ok=False)
    before = time.monotonic()

    def one(row):
        source = HERE/row['source']
        assert sha(source) == row['source_sha256']
        fit_tag = f'{tag}_{row["index"]:02d}'
        command = [sys.executable, '-I', '-B', str(HERE/'fit_one.py'), '--unit', row['unit'],
                   '--index', str(row['index']), '--level', '1', '--nfev', str(nfev),
                   '--guarded', '--backend', 'fast', '--confirm-from', row['source'], '--tag', fit_tag]
        if full:command.append('--full-confirmation')
        print('CONFIRM START', row['unit'], row['index'], flush=True)
        start = time.monotonic()
        with (batch/f'{row["index"]:02d}.log').open('w') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1500)
        print('CONFIRM FINISH', row['unit'], row['index'], result.returncode,
              round(time.monotonic()-start, 2), flush=True)
        return dict(**row, exit_code=result.returncode, command=command,
                    fit_receipt=f'local/fits/{row["unit"]}/{row["index"]:02d}/L1_{fit_tag}.json')

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        completed = list(pool.map(one, rows))
    receipt = dict(unit=data['unit'], solver='exact', workers=workers, nfev=nfev,
                   elapsed_seconds=time.monotonic()-before, profiles=completed,
                   status='PASS' if all(r['exit_code'] == 0 for r in completed) else 'FAIL')
    dump(batch/'receipt.json', receipt)
    assert receipt['status'] == 'PASS'


def summarize():
    rows = []
    legacy=[]
    for path in sorted((HERE/'local/fits').rglob('L1_*.json')):
        doc = read(path)
        if not doc.get('exact_confirmation_of') or doc.get('canonical_equivalence_parent'):
            continue
        source = read(HERE/doc['exact_confirmation_of'])
        if not doc.get('full_start_confirmation'):
            legacy.append(str(path.relative_to(HERE)))
            continue
        assert doc['backend'] == 'fast' and doc['all_original_starts_axes_and_feasible_candidates']
        assert len(doc['solver_attempts']) == doc['exact_confirmation_solver_attempts'] and doc['quality']['passes']
        assert sha(HERE/doc['start_manifest'])==doc['start_manifest_sha256']
        assert len(read(HERE/doc['start_manifest'])['starts'])==len(doc['solver_attempts'])
        assert doc['objective'] <= source['objective']+1e-9
        rows.append(dict(unit=doc['unit'], index=doc['index'], name=doc['name'],
            source_fit=doc['exact_confirmation_of'], source_fit_sha256=sha(HERE/doc['exact_confirmation_of']),
            source_backend=source.get('backend', 'reference'), source_config=source.get('solver_config', 'exact'),
            source_actual_solver_branches=source.get('actual_solver_branches') or [
                'GuardedProblem direct least_squares -> scipy TRF/SVD' if source.get('optimization_hue_penalty') and not source.get('gray')
                else 'Problem.solve L0/L1 -> scipy TRF/SVD'],
            source_record_sha256=source['record']['sha256'], source_objective=source['objective'],
            exact_fit=str(path.relative_to(HERE)), exact_fit_sha256=sha(path),
            exact_record_sha256=doc['record']['sha256'], exact_objective=doc['objective'],
            source_scores=source['scores'], exact_scores=doc['scores'],
            exact_confirmation_solver_attempts=len(doc['solver_attempts']),target_sha256=doc['target_sha256'],
            full_start_confirmation=True,start_manifest=doc['start_manifest'],start_manifest_sha256=doc['start_manifest_sha256'],
            selection_reason='kept existing feasible integer record' if doc.get('retained_feasible_parent') else 'integer objective over original and additional exact starts',
            retained_feasible_parent=doc.get('retained_feasible_parent'),
            reviewed_holdout_gate=doc['reviewed_holdout_gate'],reference_reduction_noise=doc['reference_reduction_noise'],
            actual_solver_branches=doc['actual_solver_branches']))
    summary = dict(label='电脑预测', profiles=rows, exact_confirmation_fits=len(rows),
                   source_config_is_adapter_request_not_actual_solver=True,
                   all_declared_starts_required=True,iteration_only_single_start_fits=legacy,
                   separate_exact_fit_per_candidate=True,final_selected_record_binding_required=True)
    dump(HERE/'exact_confirmation_summary.json', summary)
    flat = []
    for row in rows:
        for group, value in row['source_scores'].items():
            if not value:
                continue
            exact = row['exact_scores'][group]['candidate']
            source = value['candidate']
            flat.append(dict(label='电脑预测', unit=row['unit'], index=row['index'], name=row['name'],
                group=group,candidate_solver='scipy_TRF_SVD',candidate_requested_adapter_config=row['source_config'],
                candidate_actual_solver_branch=' / '.join(row['source_actual_solver_branches']),candidate_percent=source['similarity_percent'],
                exact_confirmation_percent=exact['similarity_percent'],
                candidate_median_de00=source['de00']['median'], exact_median_de00=exact['de00']['median'],
                candidate_objective=row['source_objective'], exact_objective=row['exact_objective'],
                source_record_sha256=row['source_record_sha256'], exact_record_sha256=row['exact_record_sha256']))
    if flat:
        with (HERE/'exact_confirmation_scores.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
            writer.writeheader()
            writer.writerows(flat)
    batches = []
    for path in sorted((HERE/'local/batches').glob('*/receipt.json')):
        data = read(path)
        if not path.parent.name.startswith('lens_'):
            continue
        configs = {r['command'][r['command'].index('--backend')+1] for r in data['results']}
        assert len(configs) == 1
        backend = next(iter(configs))
        batches.append(dict(tag=path.parent.name, unit=data['unit'], indices=[r['index'] for r in data['results']],
            requested_adapter_config='guarded_normal' if backend=='guarded_normal' else 'exact',
            config='exact_TRF_SVD',effective_path='GuardedProblem direct least_squares / grey Problem.solve L1 -> scipy TRF/SVD',
            delivery_1530_gate_covers_this_full_flow=False,
            status='PASS' if data['all_passed'] else 'FAIL', receipt=str(path.relative_to(HERE)), sha256=sha(path)))
    fallback = [dict(read(p), unit=p.parent.name, receipt=str(p.relative_to(HERE)), sha256=sha(p))
                for p in sorted((HERE/'local/solver_unit_fallback').glob('*/*.json'))]
    dump(HERE/'solver_provenance.json', dict(label='电脑预测', batches=batches, unit_fallbacks=fallback,
        guarded_factor='normal', finished_batches_preserved=True, approximate_L1_factorization_used=False))
    print('Exact confirmation summary', len(rows), 'fits;', len(batches), 'main batch receipts', flush=True)


def binding(row, summary):
    matches = [r for r in summary['profiles'] if (r['unit'], r['index']) == (row['unit'], row['index'])
               and row['record_sha256'] in (r['source_record_sha256'], r['exact_record_sha256'])]
    if not matches:
        return None
    result = min(matches, key=lambda r: (r['exact_objective'], r['exact_fit']))
    assert result['exact_objective'] <= result['source_objective']+1e-9
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=('plan', 'run', 'summarize'))
    ap.add_argument('--unit', choices=UNITS)
    ap.add_argument('--tag')
    ap.add_argument('--range', dest='span')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--nfev', type=int, default=500)
    ap.add_argument('--full',action='store_true')
    args = ap.parse_args()
    if args.stage != 'summarize':
        assert args.tag and Path(args.tag).name == args.tag and '.' not in args.tag
    if args.stage == 'plan':
        assert args.unit
        plan(args.unit, args.tag)
    elif args.stage == 'run':
        lo, hi = map(int, args.span.split(':'))
        run(args.tag,lo,hi,args.workers,args.nfev,args.full)
    else:
        summarize()


if __name__ == '__main__':
    main()
