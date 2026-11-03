"""Separate narrow measured input support from MOUNT L1 model extrapolation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from entry_codec import predict,encode
from report import select
import struct


def errors(prediction,want):
    return rt.delta_e00(rt.lab_from_codes(prediction),rt.lab_from_codes(want))


def split_gains(before,after,want,weight,inside):
    old,new=errors(before,want),errors(after,want)
    delta=weight*(old*old-new*new)
    positive=np.maximum(delta,0)
    total=float(positive.sum())
    supported=float(positive[inside].sum())
    extrapolated=float(positive[~inside].sum())
    assert abs(total-supported-extrapolated)<1e-8*max(1,total)
    return dict(points=len(old),input_support_points=int(inside.sum()),
        input_support_fraction=float(inside.mean()),
        positive_error_square_reduction=total,positive_reduction_in_support=supported,
        positive_reduction_outside_support=extrapolated,
        outside_support_fraction_of_positive_reduction=None if total<1e-12 else min(1.,max(0.,extrapolated/total)),
        error_square_increases=float(-np.minimum(delta,0).sum()),
        signed_error_square_reduction=float(delta.sum()),
        old_median_de00=float(np.median(old)),new_median_de00=float(np.median(new)))


def main():
    probe=rt.LOCAL/'probe_evidence_20261103'
    assignments=rt.read(probe/'assignments.json')['frames']
    baseline={r['frame'] for r in assignments if r['label']=='A'}
    predictions={r['frame']:r for r in rt.read(probe/'predictions.json')}
    model=rt.read(probe/'model.json')
    support,public_ranges={},{}
    # R was excited only in toolbar_aux; G and B in the designed light grey.
    for channel,(ch,patch) in enumerate((('R',6),('G',2),('B',2))):
        xs=np.array([predictions[name]['conditioned_x'][patch][channel] for name in sorted(baseline)])
        jpg=np.array([next(r for r in assignments if r['frame']==name)['jpeg_mean'][patch][channel]
                      for name in sorted(baseline)])
        support[ch]=dict(model_input_min=float(xs.min()),model_input_max=float(xs.max()),
            baseline_jpeg_channel_min=float(jpg.min()),baseline_jpeg_channel_max=float(jpg.max()),
            area='toolbar_aux' if patch==6 else 'designed_light_grey',frames=sorted(baseline),
            input_coordinate_status='inverted baseline JPG under the field model; not independent RAW-axis calibration')
        public_ranges[ch]={k:v for k,v in support[ch].items() if not k.startswith('model_input_')}
    rt.dump(rt.LOCAL/'mount_L1_support/intervals.json',dict(support=support,
        probe_source_sha256=rt.sha(probe/'predictions.json'),
        iso=200,node=16,delta=2,full_curve_amplitude_validated=False))
    bounds=np.array([[support[ch]['model_input_min'],support[ch]['model_input_max']] for ch in 'RGB'])
    bracket = rt.LOCAL/'bracket_evidence_20261103/analysis/recipe_redo_handoff.json'
    latest = rt.read(bracket) if bracket.exists() else None
    combined_bounds = None
    if latest:
        combined_bounds = np.array([[min(p['conditioned'] for p in row['activated_contexts']),
            max(p['conditioned'] for p in row['activated_contexts'])] for row in latest['RAW_WB_sample_ranges']])
        rt.dump(rt.LOCAL/'mount_L1_support/combined_activated_envelopes.json',dict(
            conditional_input_bounds=combined_bounds,source_handoff_sha256=rt.sha(bracket),
            endpoints_do_not_validate_intervening_brightness_or_response_amplitude=True))
    rows=[]
    for index in range(35):
        p1,d1=select((rt.LOCAL/'fits/mount-a12'/f'{index:02d}').glob('L1_*.json'))
        p0,d0=select((rt.LOCAL/'fits/mount-a12'/f'{index:02d}').glob('L0_*.json'))
        assert d1 and d0
        e1,e0=p1.with_suffix('.record552').read_bytes(),p0.with_suffix('.record552').read_bytes()
        x1=np.array([0,*struct.unpack_from('>31H',e1,20),4095])
        x0=np.array([0,*struct.unpack_from('>31H',e0,20),4095])
        q1=np.array([list(e1[379:412]),list(e1[82:115]),list(e1[412:445])])
        if not e1[1]&4:q1[:]=list(e1[82:115])
        q0=np.array([list(e0[82:115])]*3)
        if d1.get('parameters'):
            shared=encode(e1,d1['parameters'],level=0,gray=d1.get('gray',False))
        else:
            shared=e1
        groups={}
        datasets={g:rt.arrays(rt.LOCAL/'targets/mount-a12'/f'{index:02d}_{g}.npz')
                  for g in ('train','synthetic','photo_iso200','photo_other_iso')}
        extra=rt.LOCAL/'new7/recipe_holdout'/f'{index:02d}.npz'
        if extra.exists():datasets['photo_new7_RAW_diagnostic']=rt.arrays(extra)
        for group,data in datasets.items():
            x=data['x']
            if not len(x):continue
            tested=(x>=bounds[:,0])&(x<=bounds[:,1])
            iso200=np.asarray(data['iso'])==200
            a=np.column_stack([np.interp(x[:,ch],x1,q1[ch]) for ch in range(3)])
            b=np.column_stack([np.interp(x[:,ch],x0,q0[ch]) for ch in range(3)])
            active=abs(a-b)>1e-7
            inside=np.all(tested|~active,axis=1)&np.any(active,axis=1)&iso200
            pred1,pred0=predict(e1,x,2),predict(e0,x,2)
            control=predict(shared,x,2)
            # Shared-G ablation freezes the other L1 fields. It is conditional,
            # and its effect is not an additive causal budget for all features.
            active_shared=np.column_stack([abs(a[:,0]-np.interp(x[:,0],x1,q1[1]))>1e-7,
                                          np.zeros(len(x),bool),
                                          abs(a[:,2]-np.interp(x[:,2],x1,q1[1]))>1e-7])
            supported_shared=np.all(tested|~active_shared,axis=1)&np.any(active_shared,axis=1)&iso200
            groups[group]=dict(L1_vs_L0=split_gains(pred0,pred1,data['want'],data['sw'],inside),
                independent_curves_conditional_ablation=split_gains(control,pred1,data['want'],data['sw'],supported_shared),
                channel_input_support_fraction={ch:float((tested[:,i]&iso200).mean()) for i,ch in enumerate('RGB')},
                all_changed_channels_in_measured_input_support=float(inside.mean()),
                quantitative_response_still_unclosed_inside_support=True)
            if combined_bounds is not None:
                covered=(x>=combined_bounds[:,0])&(x<=combined_bounds[:,1])
                combined=np.all(covered|~active,axis=1)&np.any(active,axis=1)&iso200
                combined_shared=np.all(covered|~active_shared,axis=1)&np.any(active_shared,axis=1)&iso200
                groups[group]['combined_activated_envelope_L1_vs_L0']=split_gains(
                    pred0,pred1,data['want'],data['sw'],combined)
                groups[group]['combined_activated_envelope_conditional_ablation']=split_gains(
                    control,pred1,data['want'],data['sw'],combined_shared)
        changed=(q1!=np.asarray(model['curves']['A']))
        outside_node=changed.copy();outside_node[:,16]=False
        probe_shape=not changed.any() or any(np.array_equal(q1,np.asarray(model['curves'][ch])) for ch in 'RGB')
        primary=groups['photo_iso200']['L1_vs_L0']
        fraction=primary['outside_support_fraction_of_positive_reduction']
        rows.append(dict(label='电脑预测，局部实测支持与模型外推',index=index,name=d1['name'],
            record_sha256=d1['record']['sha256'],L0_record_sha256=d0['record']['sha256'],
            groups=groups,primary_positive_gain_mostly_outside_measured_support=fraction is not None and fraction>.5,
            nodes_changed_outside_the_single_probed_node=int(outside_node.sum()),
            parameters_exceed_single_node_positive_two_probe_shape=not probe_shape,
            iso200_only_hardware_evidence=True,full_curve_amplitude_calibrated=False,
            global_RGB_gain_correction_applied=False))
        print(index,d1['name'],'positive gain outside measured input support',fraction,flush=True)
    summary=dict(label='电脑预测；实测域覆盖不等于定量幅度已标定',created_utc=rt.utc(),profiles=rows,
        measured_baseline_JPG_channel_ranges=public_ranges,
        support_coordinate_details='local/mount_L1_support/intervals.json',
        hardware_evidence='ISO200, one node, +2, R auxiliary grey and G/B light grey only',
        quantitative_model_accepted=False,all_measured_domain_scores_are_still_model_predictions=True,
        attribution='Sum positive weighted DE00-square reductions by fixed input-domain membership; signed increases retained separately',
        input_support_is_necessary_not_sufficient=True,no_global_gain_correction=True,
        source_authorization_sha256=rt.sha(rt.LOCAL/'mount_L1_authorization.json'))
    if latest:
        summary.update(latest_bracket_handoff_sha256=rt.sha(bracket),
            working_interpolator=latest['working_interpolator'],
            G_luma_chroma_diagnostic=latest['G_luma_chroma_diagnostic'],
            support_partition_scope='morning A-conditioned and combined activated envelopes separated; neither validates their interior or amplitudes',
            bracket_baseline_coverage_does_not_validate_all_curve_freedoms=True)
    rt.dump('mount_L1_domain_summary.json',summary)


if __name__=='__main__':main()
