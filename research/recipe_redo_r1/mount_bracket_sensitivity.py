"""Local chroma calibration and output-quantization hypotheses, never recipe edits."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import itertools
import signal
from entry_codec import predict
from report import select

EVIDENCE = rt.LOCAL/'bracket_evidence_20261103/analysis'


def codes(rgb):
    y, c = rt.mm.ycbcr(np.asarray(rgb))
    return np.stack((y, c.real+128, c.imag+128), axis=-1)


def from_codes(ycc):
    return rt.mm.rgb_from_ycc(ycc[:, 0], (ycc[:, 1]-128)+1j*(ycc[:, 2]-128))


def phase_output(rgb, phase, order):
    # Both orders are output-stage hypotheses. Neither asserts an ISP position.
    if order == 'RGB8_then_YCbCr8':
        rgb = np.rint(rgb)
    ycc = codes(rgb)
    nearest = np.rint(ycc)
    ycc = np.where(abs(ycc-nearest)<1e-9, nearest, ycc)
    quantized = np.clip(np.floor(ycc+phase), 0, 255)
    return np.rint(np.clip(from_codes(quantized), 0, 255))


def rmse(a, b):
    return np.sqrt(np.mean((np.asarray(a)-np.asarray(b))**2, axis=0)).tolist()


def calibrate(tag):
    out = rt.LOCAL/'chroma_sensitivity'/tag
    assert not out.exists(), 'Use a fresh calibration tag'
    out.mkdir(parents=True)
    snapshot = rt.freeze_task_code()
    native = rt.read(EVIDENCE/'native_Y_checks.json')
    points = rt.read(EVIDENCE/'kernel_points.json')
    point_map = {(p['frame'],p['patch']):p for p in points}
    all_rows = native['morning']+native['bracket']
    active = [p for p in all_rows if p['q_nominal']>.2 and p['q_projection']>.2]
    assert len(active)==13
    observed = np.array([p['native_ycc_delta'] for p in active])
    nominal = np.array([p['predicted_ycc_delta'] for p in active])
    session = np.array([p['session'] for p in active])
    reproduction = []
    for ch in 'RGB':
        keep = np.array([p['channel']==ch for p in active])
        gain = (observed[keep]*nominal[keep]).sum(0)/(nominal[keep]**2).sum(0)
        original = next(r for r in native['component_fits'] if r['scope']=='combined' and r['channel']==ch)
        assert np.max(abs(gain-original['native_component_gains']))<1e-12
        reproduction.append(dict(channel=ch,points=int(keep.sum()),component_ratio_check_pass=True))
    rows, models = [], []
    histogram_scale = []
    for p in active:
        detail = point_map[p['frame'],p['patch']]
        mean = detail['kernel_bases_mean_input']['linear_tent']
        assert mean>1e-10
        histogram_scale.append(detail['kernel_bases']['linear_tent']/mean)
    for distribution, factors in [('mean_input',np.ones(len(active))),
                                    ('RAW_histogram_proxy',np.array(histogram_scale))]:
        x = nominal*factors[:, None]
        for training in ('combined','morning','bracket'):
            keep = np.ones(len(active),bool) if training=='combined' else session==training
            matrix, _, rank, singular = np.linalg.lstsq(x[keep, 1:], observed[keep, 1:], rcond=None)
            assert rank==2
            model_id = distribution+'_'+training
            model_file = out/(model_id+'.json')
            result = x.copy()
            result[:, 1:] = x[:, 1:]@matrix
            rt.dump(model_file, dict(model_id=model_id,training_scope=training,
                distribution=distribution,chroma_differential_matrix=matrix,
                luma_kept_at_original_model=True,no_intercept=True,
                raw_histogram_is_not_a_measured_ISP_input_distribution=True,
                parameters_not_applied_to_main_candidates=True,
                train_points=int(keep.sum()),matrix_rank=int(rank),singular_values=singular,
                active_points=active,predicted_components=x,calibrated_components=result,
                component_residuals=result-observed,mean_input_residuals=nominal-observed,
                source_sha256=rt.sha(EVIDENCE/'native_Y_checks.json')))
            models.append(dict(file=str(model_file.relative_to(rt.HERE)),sha256=rt.sha(model_file)))
            for evaluation in ('morning','bracket'):
                test = session==evaluation
                rows.append(dict(model_id=model_id,training_scope=training,
                    evaluation_scope=evaluation,distribution=distribution,points=int(test.sum()),
                    role='holdout' if training!='combined' and training!=evaluation else 'train_or_combined',
                    nominal_component_rmse=rmse(x[test],observed[test]),
                    calibrated_component_rmse=rmse(result[test],observed[test]),
                    main_record_or_model_updated=False))
    # Keep every unexcited point and its measured components in the evidence.
    rt.dump(out/'all_component_points.json',dict(points=all_rows,
        active_point_keys=[[r['frame'],r['patch']] for r in active],
        no_unexcited_rows_dropped_from_evidence=True,
        component_fields=['Y','Cb','Cr']))
    rt.assert_task_code(snapshot)
    handoff = rt.read(EVIDENCE/'recipe_redo_handoff.json')
    summary = dict(label='电脑预测，局部后级色度校准及输入分布敏感性',created_utc=rt.utc(),
        active_points=13,all_component_points=len(all_rows),held_out_by_whole_session=True,
        models=models,evaluations=rows,component_gain_reproduction=reproduction,
        G_luma_chroma_diagnostic=handoff['G_luma_chroma_diagnostic'],
        measured_RAW_proxy_ranges=[{k:r[k] for k in ('channel','baseline_raw_min','baseline_raw_max',
            'activated_main_raw_min','activated_main_raw_max','activated_main_count','activated_new_main_count')}
            for r in handoff['RAW_WB_sample_ranges']],
        private_conditioned_coordinates='local/bracket_evidence_20261103/analysis/recipe_redo_handoff.json',
        main_model_updated=False,main_records_updated=False,global_RGB_curve_gain_applied=False,
        hardware_interpolation_identified=False,full_curve_amplitudes_accepted=False,
        JPEG_quantization_and_IDCT_not_removed=True,
        no_global_chroma_calibration_claim=True,
        source_handoff_sha256=rt.sha(EVIDENCE/'recipe_redo_handoff.json'),
        code_snapshot=snapshot)
    rt.dump('mount_chroma_calibration_summary.json',summary)
    print('Local chroma calibration',len(models),'models,',len(rows),'session evaluations; main records unchanged')


def quantize(indices, tag):
    snapshot = rt.freeze_task_code()
    out = rt.LOCAL/'quantization_sensitivity'/tag
    out.mkdir(parents=True,exist_ok=True)
    phases = list(itertools.product((0.,.25,.5,.75),repeat=3))
    branches = [(order,np.array(phase)) for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8') for phase in phases]
    neutral = np.repeat(np.array([0.,128.,255.])[:,None],3,axis=1)
    assert np.max(abs(from_codes(codes(neutral))-neutral))<1e-6
    for order,phase in branches:
        assert np.array_equal(phase_output(neutral,phase,order),neutral)
    for index in indices:
        path,doc = select((rt.LOCAL/'fits/mount-a12'/f'{index:02d}').glob('L1_*.json'))
        assert doc
        target = out/f'{index:02d}.json'
        assert not target.exists(), 'Use a fresh tag; preserve the first output'
        record = path.with_suffix('.record552')
        entry = record.read_bytes()
        meta = rt.read(rt.LOCAL/'targets/mount-a12'/f'{index:02d}.json')
        current = bytes.fromhex(meta['template_hex'])
        groups = {}
        paths = {g:rt.LOCAL/'targets/mount-a12'/f'{index:02d}_{g}.npz'
                 for g in ('synthetic','photo_iso200')}
        active_holdout=rt.read(rt.HERE/'new7_raw_holdout_summary_L1.json').get('artifact_root','local/new7/recipe_holdout_L1')
        paths['photo_new7_RAW_diagnostic'] = rt.HERE/active_holdout/f'{index:02d}.npz'
        for group,data_path in paths.items():
            data = rt.arrays(data_path)
            x,want,base = data['x'],data['want'],data['base']
            a,b = predict(current,x,2,round_output=False),predict(entry,x,2,round_output=False)
            assert np.array_equal(np.rint(a),data['current'])
            if group=='photo_new7_RAW_diagnostic':saved=data['prediction']
            else:saved=rt.arrays(path.parent/(path.stem+'_'+group+'.npz'))['prediction']
            assert np.array_equal(np.rint(b),saved)
            lab = rt.lab_from_codes(want)
            denom = float(np.median(rt.delta_e00(rt.lab_from_codes(base),lab)))
            def score(rgb):
                error = rt.delta_e00(rt.lab_from_codes(rgb),lab)
                middle,tail = float(np.median(error)),float(np.percentile(error,95))
                return dict(median_de00=middle,p95_de00=tail,
                    similarity_percent=None if denom<.25 else 100*(1-middle/denom)),error
            baseline_a, _ = score(np.rint(a))
            baseline_b, _ = score(np.rint(b))
            results = []
            limits = {key:np.full(len(x),val) for key,val in
                [('candidate_error_min',np.inf),('candidate_error_max',-np.inf),
                 ('current_error_min',np.inf),('current_error_max',-np.inf)]}
            for order,phase in branches:
                sa,ea = score(phase_output(a,phase,order))
                sb,eb = score(phase_output(b,phase,order))
                delta = None if sa['similarity_percent'] is None else sb['similarity_percent']-sa['similarity_percent']
                results.append(dict(order=order,phase=phase,current=sa,candidate=sb,gain_pp=delta,
                    median_or_p95_regression=(sb['median_de00']>sa['median_de00']+1e-10
                        or sb['p95_de00']>sa['p95_de00']+1e-10)))
                for who,error in [('candidate',eb),('current',ea)]:
                    limits[who+'_error_min']=np.minimum(limits[who+'_error_min'],error)
                    limits[who+'_error_max']=np.maximum(limits[who+'_error_max'],error)
            envelope = out/f'{index:02d}_{group}.npz'
            np.savez_compressed(envelope,**limits)
            percent = [r['candidate']['similarity_percent'] for r in results if r['candidate']['similarity_percent'] is not None]
            gains = [r['gain_pp'] for r in results if r['gain_pp'] is not None]
            groups[group]=dict(points=len(x),branches=results,original_RGB8_current=baseline_a,
                original_RGB8_candidate=baseline_b,
                candidate_percent_min=min(percent) if percent else None,
                candidate_percent_max=max(percent) if percent else None,
                gain_pp_min=min(gains) if gains else None,gain_pp_max=max(gains) if gains else None,
                candidate_p95_min=min(r['candidate']['p95_de00'] for r in results),
                candidate_p95_max=max(r['candidate']['p95_de00'] for r in results),
                regression_branches=sum(r['median_or_p95_regression'] for r in results),
                point_envelope_file=str(envelope.relative_to(rt.HERE)),point_envelope_sha256=rt.sha(envelope),
                envelope_extrema_may_come_from_different_branches=True,input_file_sha256=rt.sha(data_path))
        rt.dump(target,dict(label='电脑预测，输出量化假设',index=index,name=doc['name'],
            record_file=str(record.relative_to(rt.HERE)),record_sha256=rt.sha(record),
            groups=groups,phase_count=len(phases),orders=2,branches_per_group=len(branches),
            no_parameter_selection=True,no_record_changes=True,code_snapshot=snapshot))
        print('Quantization sensitivity',index,doc['name'],len(branches),'branches',flush=True)
    rt.assert_task_code(snapshot)


def summarize(tag):
    root = rt.LOCAL/'quantization_sensitivity'/tag
    rows = []
    for index in range(35):
        path = root/f'{index:02d}.json'
        row = rt.read(path)
        assert row['index']==index and rt.sha(rt.HERE/row['record_file'])==row['record_sha256']
        groups = {}
        for name,values in row['groups'].items():
            assert len(values['branches'])==128
            assert rt.sha(rt.HERE/values['point_envelope_file'])==values['point_envelope_sha256']
            groups[name] = {k:v for k,v in values.items() if k not in ('branches','point_envelope_file','point_envelope_sha256')}
        rows.append(dict(index=index,name=row['name'],record_sha256=row['record_sha256'],groups=groups,
            private_detail=str(path.relative_to(rt.HERE)),private_detail_sha256=rt.sha(path)))
    rt.dump('mount_quantization_sensitivity_summary.json',dict(label='电脑预测，Y/Cb/Cr取整及量化相位假设',
        created_utc=rt.utc(),profiles=rows,profiles_complete=35,
        orders=['YCbCr8_then_RGB8','RGB8_then_YCbCr8'],phases_per_component=[0.,.25,.5,.75],
        quantizer='clip(floor(component+phase),0,255); final RGB uses round-to-even',
        branches_per_group=128,all_scores_use_frozen_target_and_04_denominator=True,
        original_RGB8_branch_retained_separately=True,
        main_parameters_and_recommendations_not_changed=True,
        no_hardware_rounding_order_asserted=True,no_JPEG_DCT_or_IDCT_simulation=True))
    print('Quantization summary PASS',len(rows),'records')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage',required=True,choices=('calibrate','quantize','summarize'))
    ap.add_argument('--tag',required=True)
    ap.add_argument('--indices')
    args = ap.parse_args()
    assert Path(args.tag).name==args.tag and '.' not in args.tag
    if args.stage=='calibrate':calibrate(args.tag)
    elif args.stage=='summarize':summarize(args.tag)
    else:
        lo,hi = map(int,args.indices.split(':'))
        assert 0<=lo<hi<=35 and hi-lo<=9
        quantize(list(range(lo,hi)),args.tag)


if __name__=='__main__':
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Split sensitivity after 25 minutes')))
    signal.alarm(1500)
    main()
