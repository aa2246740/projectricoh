"""Separate sampled grey control evidence from envelope-only recipe diagnostics."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import struct
from report import select
from entry_codec import predict,encode
from mount_L1_domain import split_gains


def main():
    source=rt.LOCAL/'ramp_evidence_20261103/analysis'
    handoff=rt.read(source/'recipe_redo_handoff.json')
    points=rt.read(source/'measure-0.5.json')['points']
    assert len(points)==312
    assert all(1927<=int(p['frame'][4:])<=1932 for p in points)
    active=[p for p in points if p['gray'] and not p['excluded'] and p['q_nominal']>.2]
    samples={ch:sorted([p['raw_input'] for p in active if p['channel']==ch]) for ch in 'RGB'}
    assert all(abs(min(samples[ch])-handoff['measured_grey_raw_ranges'][ch][0])<1e-8
               and abs(max(samples[ch])-handoff['measured_grey_raw_ranges'][ch][1])<1e-8 for ch in 'RGB')
    rt.dump(rt.LOCAL/'mount_L1_support/ramp_measured_samples.json',dict(
        active_grey_sample_RAW_WB=samples,all_formal_points=points,
        no_continuous_range_accepted=True,other_nodes_hues_and_gaps_unvalidated=True))
    bounds=np.array([handoff['measured_grey_raw_ranges'][ch] for ch in 'RGB'])
    evidence=[]
    for ch in 'RGB':
        values=np.array(samples[ch]);gaps=np.diff(np.unique(values))
        evidence.append(dict(channel=ch,grey_points_measured=sum(p['gray'] and p['channel']==ch for p in points),
            active_grey_points=len(values),RAW_WB_min=float(values.min()),RAW_WB_max=float(values.max()),
            largest_RAW_WB_gap_between_active_samples=float(gaps.max()),
            continuous_full_colour_accepted_intervals=[]))
    profiles=[]
    for index in range(35):
        p1,d1=select((rt.LOCAL/'fits/mount-a12'/f'{index:02d}').glob('L1_*.json'))
        p0,d0=select((rt.LOCAL/'fits/mount-a12'/f'{index:02d}').glob('L0_*.json'))
        e1,e0=p1.with_suffix('.record552').read_bytes(),p0.with_suffix('.record552').read_bytes()
        x1=np.array([0,*struct.unpack_from('>31H',e1,20),4095]);x0=np.array([0,*struct.unpack_from('>31H',e0,20),4095])
        q1=np.array([list(e1[379:412]),list(e1[82:115]),list(e1[412:445])])
        if not e1[1]&4:q1[:]=list(e1[82:115])
        q0=np.array([list(e0[82:115])]*3)
        shared=encode(e1,d1['parameters'],level=0,gray=d1.get('gray',False)) if d1.get('parameters') else e1
        groups={}
        paths={g:rt.LOCAL/'targets/mount-a12'/f'{index:02d}_{g}.npz'
               for g in ('train','synthetic','photo_iso200','photo_other_iso')}
        active_root=rt.read(rt.HERE/'new7_raw_holdout_summary_L1.json').get('artifact_root','local/new7/recipe_holdout_L1')
        paths['photo_new7_RAW_diagnostic']=rt.HERE/active_root/f'{index:02d}.npz'
        for group,path in paths.items():
            data=rt.arrays(path);x=data['x'];raw=data['raw_codes']
            if not len(x):continue
            inside=(raw>=bounds[:,0])&(raw<=bounds[:,1]);iso200=np.asarray(data['iso'])==200
            a=np.column_stack([np.interp(x[:,ch],x1,q1[ch]) for ch in range(3)])
            b=np.column_stack([np.interp(x[:,ch],x0,q0[ch]) for ch in range(3)])
            changed=abs(a-b)>1e-7
            covered=np.all(inside|~changed,axis=1)&np.any(changed,axis=1)&iso200
            changed_shared=np.column_stack([abs(a[:,0]-np.interp(x[:,0],x1,q1[1]))>1e-7,
                np.zeros(len(x),bool),abs(a[:,2]-np.interp(x[:,2],x1,q1[1]))>1e-7])
            covered_shared=np.all(inside|~changed_shared,axis=1)&np.any(changed_shared,axis=1)&iso200
            prediction=predict(e1,x,2)
            groups[group]=dict(RAW_envelope_only_L1_vs_L0=split_gains(predict(e0,x,2),prediction,data['want'],data['sw'],covered),
                RAW_envelope_only_independent_ablation=split_gains(predict(shared,x,2),prediction,data['want'],data['sw'],covered_shared),
                envelope_membership_does_not_validate_gaps_hues_amplitudes_or_other_nodes=True)
        profiles.append(dict(index=index,name=d1['name'],record_sha256=d1['record']['sha256'],groups=groups,
            quantitatively_accepted_continuous_intervals=[],full_modified_recipe_quantitatively_accepted=False,
            unmodified_native04=index==30,
            scope='Node16 +2, measured grey samples only, ISO200, same manual M lens at f/5.6; all gaps, hues and other nodes remain extrapolation'))
    local=rt.read(source/'local_output_candidate.json')
    chroma={k:{f:v[f] for f in ('n','original_ycc_rmse','fitted_ycc_rmse')} for k,v in
            [('grey_training',local['grey_training']),('chromatic_holdout',local['chromatic_holdout'])]}
    skin=[p for p in points if p['channel']=='R' and p['patch']=='skin']
    opposite=sum(p['observed_ycc'][1]*p['predicted_ycc'][1]<0 for p in skin)
    rt.dump('mount_ramp_scope_summary.json',dict(label='电脑预测覆盖诊断；实测为离散灰点，非全颜色区间验收',
        created_utc=rt.utc(),profiles=profiles,profiles_complete=35,sampled_control_evidence=evidence,
        formal_capture_pairs=8,reference_only_pairs=8,reference_take_used_for_measurements=False,
        tested_node=16,tested_delta=2,tested_iso=200,tested_aperture_f=5.6,
        verified_continuous_full_colour_intervals=[],hardware_interpolator_identified=False,
        working_interpolator='piecewise linear',global_amplitude_or_chroma_update_applied=False,
        skin_R_Cb_opposite_sign_points=opposite,skin_R_points=len(skin),local_correction_holdout=chroma,
        private_sample_points='local/mount_L1_support/ramp_measured_samples.json',
        source_handoff_sha256=rt.sha(source/'recipe_redo_handoff.json')))
    print('RAMP scope',len(profiles),'records; no continuous full-colour range accepted; skin R Cb sign failures',opposite)


if __name__=='__main__':main()
