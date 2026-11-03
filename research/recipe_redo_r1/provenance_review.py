"""Record actual adapter dispatch and gate hashes without relabelling old fits."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text())


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    data=read(HERE/'solver_provenance.json')
    adapters={}
    for name,folder,file in (('exact','fast_engine','fast_backend.py'),('requested_guarded_normal','normal_fast_engine','normal_backend.py')):
        root=HERE/'local'/folder
        adapter=read(root/'adapter_receipt.json')
        gate=root/'equivalence_task.json'
        adapters[name]=dict(requested_config='guarded_normal' if name.startswith('requested') else 'exact',
            actual_colour_solver='GuardedProblem.solve -> direct solver.least_squares -> scipy TRF/SVD',
            actual_greyscale_solver='Problem.solve L0/L1 -> scipy TRF/SVD',
            guarded_normal_factorisation_called=False,delivery_1530_gate_accepts_this_flow=False,
            adapter_file=file,adapter_file_sha256=sha(HERE/file),
            adapter_receipt=str((root/'adapter_receipt.json').relative_to(HERE)),adapter_receipt_sha256=sha(root/'adapter_receipt.json'),
            frozen_adapter_files=adapter['adapter_files'],frozen_backend_fingerprint=adapter['backend_fingerprint'],
            local_equation_record_gate=str(gate.relative_to(HERE)),local_equation_record_gate_sha256=sha(gate),
            frozen_model_file='local/source/research/look_ceiling_r1/ceiling_model.py',
            frozen_model_sha256=sha(HERE/'local/source/research/look_ceiling_r1/ceiling_model.py'),
            start_policy='Saved batch: current and grey-axis, eligible parent integers, original axes; full exact: all feasible candidates and axes plus kept candidate',
            full_start_policy_source='full_confirm_support.py',full_start_policy_sha256=sha(HERE/'full_confirm_support.py'))
    for batch in data['batches']:
        rows=[]
        for index in batch['indices']:
            p=HERE/'local/fits'/batch['unit']/f'{index:02d}'/('L1_'+batch['tag']+'.json')
            doc=read(p)
            branches=doc.get('actual_solver_branches') or ([
                'GuardedProblem.solve -> direct least_squares -> scipy TRF/SVD' if doc.get('optimization_hue_penalty') and not doc.get('gray')
                else 'Problem.solve L0/L1 -> scipy TRF/SVD'] if doc['solver_attempts'] else ['native04; no solver'])
            rows.append(dict(index=index,fit=str(p.relative_to(HERE)),fit_sha256=sha(p),
                task_source_identity=doc['code_snapshot']['identity'],actual_solver_branches=branches,
                dispatch_evidence='instrumented' if doc.get('actual_solver_branches') else 'frozen dispatch source and saved configuration'))
        batch['actual_solver_records']=rows
    data.update(adapters=adapters,actual_solver='scipy TRF/SVD',guarded_normal_factorisation_used=False,
        gate_hashes={name:sha(HERE/name) for name in ('verification.json','guard_derivative_check.json','full_confirm_support.py','fit_one.py')},
        full_review_source_sha256=sha(HERE/'local/solver_review_20261103/REVIEW.md'),
        requested_config_is_not_actual_solver=True)
    (HERE/'solver_provenance.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Actual adapter dispatch recorded for',len(data['batches']),'batches; no guarded_normal factorisation used')


if __name__=='__main__':main()
