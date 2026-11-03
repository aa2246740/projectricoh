"""Transfer real-chart residuals through the frozen GR forward model at fixed anchors."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
from score_chart import stats, patch_strata
import json
import numpy as np


def residual_transport(model_at_destination, model_at_source, observed, neutral, method='lch'):
    """No recipe measurements enter this per-patch source residual."""
    if method=='lab':
        return model_at_destination + observed - model_at_source
    source=np.asarray(model_at_source);dest=np.asarray(model_at_destination);obs=np.asarray(observed)
    cs,cd,co=[np.hypot(v[:,1],v[:,2]) for v in (source,dest,obs)]
    active=(cs>=8)&(cd>=8)&(co>=8)&~neutral
    ratio=np.where(active,co/np.maximum(cs,1e-12),1)
    angle=np.where(active,np.angle((obs[:,1]+1j*obs[:,2])/(source[:,1]+1j*source[:,2]+1e-20)),0)
    ab=(dest[:,1]+1j*dest[:,2])*ratio*np.exp(1j*angle)
    return np.column_stack([dest[:,0]+obs[:,0]-source[:,0],ab.real,ab.imag])


def paired_score(r,target,pred,baseline_target,baseline,valid):
    # The historical closed_loop protocol renders the 04's own DNG separately.
    out=r.score(target[valid],pred[valid],baseline[valid])
    den=stats(r.FS.delta_e00(baseline_target[valid],baseline[valid]))
    out['same_target_similarity']=out['similarity']
    out['same_target_stock04']=out['stock04']
    out['stock04']=den
    out['similarity']=1-out['median']/den['median'] if den['median'] and out['n'] else None
    return out


def main():
    s.guard();r=s.runtime();cm=r.P.CM
    frames={f['id']:f for f in s.read(s.ROOT/'research/closed_loop/local/m20261021_r1_gr.json')['frames']}
    oldtargets=s.read(s.ROOT/'research/closed_loop/local/gr_targets_20261021_r1.json')['frames']
    baseline,repeat=frames['screen04'],frames['screen04b']
    ids=np.arange(1,156)
    layout=r.ring.load_layout()['patches']
    hue=np.array([p['lab_h_design_deg'] if p['ring'] else -1 for p in layout])
    neutral=np.array([p['group']=='gray' for p in layout])
    mid=(ids>=147)&(ids<=151)
    out={}
    for slot,ident in (('01','R0003037'),('02','R0003039')):
        mode='positive' if slot=='01' else 'negative'
        f=frames['screen'+slot]
        ref=oldtargets['screen'+slot+':'+slot]
        D=r.P.data_of(slot)
        scale=ref['gxr_scene_anchor']['scene_scale']
        def model(frame,ev=0):
            raw=r.generator.camera_rgb(np.asarray(frame['xyz_camera'])*scale*2**ev@np.linalg.inv(r.FS.M709).T)
            x=np.asarray(frame['input_x'])*2**ev
            b=r.P.rgb04(D,x)
            st=cm.rgb_lab(r.generator.render_raw(raw,'standard'))
            sy=cm.rgb_lab(r.generator.render_raw(raw,mode))
            target=r.P.apply_relative(r.FS.lab_from_codes(b),st,sy,neutral)
            return dict(raw=raw,standard=st,style=sy,base=b,target=target)
        dst=model(f);bmod=model(baseline)
        old=np.asarray(ref['lab']);oldb=np.asarray(oldtargets['screen04:'+slot]['lab'])
        parity=max(float(abs(dst['target']-old).max()),float(abs(bmod['target']-oldb).max()))
        assert parity<1e-9
        with np.load(s.LOCAL/(ident+'_roi_scores.npz'),allow_pickle=False) as z:
            chart=dict(z)
        with np.load(s.LOCAL/(ident+'_generation.npz'),allow_pickle=False) as z:
            gen=dict(z)
        observed=chart['observed']
        srcmodel=gen['fw_style']
        pred=r.FS.lab_from_codes(f['rgb']);base=r.FS.lab_from_codes(baseline['rgb'])
        valid=np.asarray(f['valid'])&chart['quality']&(ids!=50)
        fw_eligible=(dst['raw']>0).all(1)&(dst['raw']<1).all(1)&(bmod['raw']>0).all(1)&(bmod['raw']<1).all(1)
        valid &= fw_eligible
        fixed=paired_score(r,old,pred,oldb,base,valid)
        original=paired_score(r,old,pred,oldb,base,np.asarray(f['valid']))
        correctedstyle=residual_transport(dst['style'],srcmodel,observed,neutral)
        correctedbstyle=residual_transport(bmod['style'],srcmodel,observed,neutral)
        corrected=r.P.apply_relative(r.FS.lab_from_codes(dst['base']),dst['standard'],correctedstyle,neutral)
        correctedb=r.P.apply_relative(r.FS.lab_from_codes(bmod['base']),bmod['standard'],correctedbstyle,neutral)
        score=paired_score(r,corrected,pred,correctedb,base,valid)
        # A single scalar from the RAW grey ramp, never selected by recipe score.
        grey_valid=mid&valid
        assert grey_valid.any(), 'No jointly valid middle grey for normalization'
        rawratio=dst['raw'][grey_valid,1]/gen['raw3'][grey_valid,1]
        scalar=float(np.median(rawratio))
        simple_rgb=np.clip(cm.srgb_encode(cm.srgb_decode(chart['jpeg']/255)*scalar),0,1)*255
        simple=r.FS.lab_from_codes(simple_rgb)
        direct=r.FS.lab_from_codes(chart['jpeg'])
        simpler=r.score(simple[valid],pred[valid],base[valid])
        directr=r.score(direct[valid],pred[valid],base[valid])
        grey_ratio_ev=np.log2(rawratio)
        # Colour disagreement at matched RAW grey exposure measures the combined
        # display/sensor/colour-matrix bridge, not display calibration alone.
        matchedstd=cm.rgb_lab(r.generator.render_raw(dst['raw']/scalar,'standard'))
        display_delta=r.FS.delta_e00(matchedstd,gen['fw_standard'])
        sensitivity=[];variant_arrays={}
        for ev in (-.3,0.,.3):
            dm,bm=model(f,ev),model(baseline,ev)
            for method in ('lch','lab'):
                cs=residual_transport(dm['style'],srcmodel,observed,neutral,method)
                bs=residual_transport(bm['style'],srcmodel,observed,neutral,method)
                tt=r.P.apply_relative(r.FS.lab_from_codes(dm['base']),dm['standard'],cs,neutral)
                bt=r.P.apply_relative(r.FS.lab_from_codes(bm['base']),bm['standard'],bs,neutral)
                rec=paired_score(r,tt,pred,bt,base,valid)
                sensitivity.append(dict(anchor_ev=ev,residual=method,**rec))
                variant_arrays[f'target_{ev:+.1f}_{method}']=tt
                variant_arrays[f'baseline_target_{ev:+.1f}_{method}']=bt
        # Additional diagnostic: uncertainty in the new body's 118 exposure gauge.
        gauge=[]
        for ev in (-.3,0.,.3):
            sm=cm.rgb_lab(r.generator.render_raw(gen['raw3']*2**ev,mode))
            cs=residual_transport(dst['style'],sm,observed,neutral)
            bs=residual_transport(bmod['style'],sm,observed,neutral)
            tt=r.P.apply_relative(r.FS.lab_from_codes(dst['base']),dst['standard'],cs,neutral)
            bt=r.P.apply_relative(r.FS.lab_from_codes(bmod['base']),bmod['standard'],bs,neutral)
            gauge.append(dict(source_gauge_ev=ev,**paired_score(r,tt,pred,bt,base,valid)))
        corrected_strata=patch_strata(r,corrected[valid],pred[valid],base[valid],ids[valid])
        # Supply the historical denominator for every stratum, too.
        for key,rec in corrected_strata.items():
            if key.startswith('h'):
                lo=int(key[1:4]);m=valid&(hue>=lo)&(hue<lo+30)
            elif key=='150-270':m=valid&(hue>=150)&(hue<270)
            elif key=='L45':m=valid&(ids<=72)
            elif key=='L65':m=valid&(ids>=73)&(ids<=144)
            elif key=='grey_ramp':m=valid&(ids>=145)&(ids<=153)
            else:m=valid&(ids>=154)
            rec.update(paired_score(r,corrected,pred,correctedb,base,m))
        # The 04 repeat supplies an independent baseline-drift check.
        rb=r.FS.lab_from_codes(repeat['rgb'])
        repeat_valid=valid&np.array([not p['flags'] for p in repeat['patches']])
        rscore=r.score(corrected[repeat_valid],pred[repeat_valid],rb[repeat_valid])
        targetshift=r.FS.delta_e00(old,corrected)
        record=dict(n=int(valid.sum()),frozen_target_parity_max=parity,old_all_valid=original,old_on_common_mask=fixed,
            corrected=score,corrected_same_target=r.score(corrected[valid],pred[valid],base[valid]),corrected_groups=corrected_strata,
            target_correction_de00=stats(targetshift[valid]),
            target_correction_sectors={str(lo):stats(targetshift[valid&(hue>=lo)&(hue<lo+30)]) for lo in range(0,360,30)},
            simple_chart_referred=simpler,direct_unadjusted=directr,grey_raw_ratio=scalar,
            grey_exposure_EV=float(np.log2(scalar)),grey_EV_spread=stats(grey_ratio_ev),
            normalization_greys=int(grey_valid.sum()),
            display_sensor_bridge_matched_exposure_de00=stats(display_delta[valid]),
            display_sensor_bridge_by_hue={str(lo):stats(display_delta[valid&(hue>=lo)&(hue<lo+30)]) for lo in range(0,360,30)},
            anchor_and_residual_sensitivity=sensitivity,source_gauge_sensitivity=gauge,
            repeat04_same_target_score=rscore,
            baseline_drift_de00=stats(r.FS.delta_e00(base[repeat_valid],rb[repeat_valid])),
            anchor=ref['gxr_scene_anchor'],
            assumptions=['source residual is transferable at the same patch across display and sensor spectra',
                         'LCh residual is constant under re-exposure; Lab alternative reported',
                         'GR III Standard forward model is the reference; no same-scene Standard JPEG',
                         '0 EV is frozen, +/-0.3 EV cases are sensitivity tests, not confidence limits'])
        np.savez_compressed(s.LOCAL/(slot+'_corrected_gxr.npz'),target=corrected,baseline_target=correctedb,
            old_target=old,old_baseline_target=oldb,pred=pred,base=base,valid=valid,ids=ids,
            source_observed=observed,source_model=srcmodel,source_raw=gen['raw3'],destination_raw=dst['raw'],
            simple_target=simple,**variant_arrays)
        s.dump(s.LOCAL/(slot+'_correction.json'),record)
        out[slot]=record
        print(json.dumps(dict(slot=slot,n=int(valid.sum()),old_common=fixed['similarity'],corrected=score['similarity'],
              corrected_median=score['median'],corrected_p90=score['p90'],simple=simpler['similarity'],grey_ev=np.log2(scalar),
              anchor_sensitivity=[(q['anchor_ev'],q['residual'],q['similarity']) for q in sensitivity])))
    s.dump(s.LOCAL/'correction.json',out)


if __name__=='__main__':
    main()
