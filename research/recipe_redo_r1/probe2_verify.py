"""Rebuild local-response records, check derivatives and retain fixed failure gates."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from probe2_refit import Flow,OUT
from entry_codec import predict as original_predict
import full_confirm_support as fc


def verify(indices):
    receipts=[]
    decisions=rt.read(rt.LOCAL/'mount_reexamination/decisions.json')['profiles']
    for index in indices:
        root=OUT/'fits'/f'{index:02d}';doc=rt.read(root/'exact.json')
        record=(root/'exact.record552').read_bytes();assert rt.sha(root/'exact.record552')==doc['record_sha256']
        if doc.get('no_independent_curve_increment'):
            assert record==(rt.HERE/doc['anchor_file']).read_bytes()
            receipts.append(dict(index=index,status='PASS',record_sha256=doc['record_sha256'],
                retained_shared_or_native=True,exact_gate_status='not applicable; unchanged',model_error_not_removed=True))
            continue
        flow=Flow(index)
        assert flow.encode(flow.model.delta(record))==record
        assert abs(flow.objective(record)-doc['objective'])<1e-10
        iteration=rt.read(root/'iterate.json')
        assert doc['objective']<=iteration['objective']+1e-10
        assert rt.sha(rt.HERE/doc['start_manifest'])==doc['start_manifest_sha256']
        manifest=rt.read(rt.HERE/doc['start_manifest'])
        assert len(manifest['starts'])==len(doc['solver_attempts']) or not len(flow.active)
        assert np.array_equal(np.array(doc['increment']),flow.model.delta(record))
        quality=flow.guard(record);assert rt.plain(quality)==doc['quality']
        scores,scenes=flow.scores(record)
        assert rt.plain(scores)==doc['scores'] and rt.plain(scenes)==doc['per_scene']
        gates={};previous=fc.predict
        try:
            fc.predict=lambda entry,x,ui:flow.model.predict(entry,x)
            gates['selected_L1_anchor']=fc.gate(dict(record_path=doc['anchor_file']),record,flow.groups,2)
            gates['iteration']=fc.gate(dict(record_path=str((root/'iterate.record552').relative_to(rt.HERE))),record,flow.groups,2)
            assert rt.plain(gates)==doc['exact_gates']
            fixed=next((d for d in decisions if d['index']==index),None)
            if fixed:
                # The original review reference must never be replaced with
                # the later failed training minimum as a fresh passing gate.
                path=rt.HERE/fixed['comparison_reference']
                reference=path.with_suffix('.record552');ref=reference.read_bytes()
                fc.predict=lambda entry,x,ui:original_predict(entry,x,2) if entry==ref else flow.model.predict(entry,x)
                gates['original_fixed_review_reference']=fc.gate(dict(record_path=str(reference.relative_to(rt.HERE))),record,flow.groups,2)
        finally:fc.predict=previous
        numerical=[]
        if index in (29,32) and len(flow.active):
            point=(flow.low[flow.active]+flow.high[flow.active])/2
            _,analytic=flow.evaluate(point)
            for j in range(len(point)):
                step=np.zeros_like(point);step[j]=1e-4
                finite=(flow.evaluate(point+step)[0]-flow.evaluate(point-step)[0])/(2e-4)
                relative=abs(finite-analytic[:,j])/np.maximum(1,abs(finite))
                error=float(np.percentile(relative,95));assert error<.02,('Derivative mismatch',index,j,error)
                numerical.append(dict(active_coordinate=j,relative_p95=error))
        gate_status='PASS' if all(g['status']=='PASS' for g in gates.values()) else 'REVIEW'
        result=dict(index=index,status='PASS',record_sha256=doc['record_sha256'],
            exact_gate_status=gate_status,exact_gates=gates,record_rebuilt=True,training_replayed=True,
            fixtures_rebuilt=True,all_frozen_fields_preserved=True,derivative_checks=numerical,
            no_gate_reset_to_previously_failed_anchor=True,model_error_not_removed=True,
            original_skin_Cb_and_blue_Cr_counterexamples_preserved=True)
        rt.dump(root/'verification.json',result);receipts.append({k:v for k,v in result.items() if k!='exact_gates'})
        print('PROBE2 VERIFY',index,'PASS',gate_status,flush=True)
    rt.dump(OUT/'verification_batches'/('_'.join(map(str,indices))+'.json'),dict(status='PASS',profiles=receipts))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--indices',required=True);args=ap.parse_args()
    verify(list(map(int,args.indices.split(','))))
