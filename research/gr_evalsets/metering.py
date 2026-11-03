#!/usr/bin/env python3
"""Test saved AE-grid/RAW bridges; keep conditional anchors explicitly unapproved."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import engine as e
import numpy as np
from scipy.optimize import least_squares

T=550.8179931640625
LOG_T=float(np.log2(T)-9)
U118_GR3=0.08577678165824383
U320_GXR=320/4095


def grid_fit(name,data,md):
    b=(e.LOCAL/f'{name}_0405.bin').read_bytes()
    w,h=np.frombuffer(b[:4],'<u2').astype(int)
    assert (w,h)==(64,62)
    grid=np.stack([np.frombuffer(b[o:o+16384],'<u4').reshape(64,64)[:h] for o in (0x2004,0x6004,0xa004)],-1).astype(float)
    counts=np.frombuffer(b[0xe004:0xe004+16384],'<u4').reshape(64,64)[:h]
    saved_log=np.log2(np.maximum((247*grid[...,0]+179*grid[...,1])/256,1))-9
    weights=np.load(e.VENDOR/'gr_ae_target/local/gr3_center_weights.npy',allow_pickle=False)[:h]
    mean_log=float(saved_log.mean());center_log=float((saved_log*weights).sum()/weights.sum())
    raw=data['rgb'].astype(float)*float(data['range'])
    integral=np.pad(raw.cumsum(0).cumsum(1),((1,0),(1,0),(0,0)))
    yy,xx=np.mgrid[1:61,1:63]
    observed=grid[1:61,1:63].reshape(-1,3)
    def candidate(ox,oy,full=False):
        x0=ox+xx*47;x1=x0+47;y0=oy+yy*32;y1=y0+32
        pred=(integral[y1,x1]-integral[y0,x1]-integral[y1,x0]+integral[y0,x0])/1504
        flat=pred.reshape(-1,3);mx=flat.mean(0);my=observed.mean(0)
        slopes=((flat-mx)*(observed-my)).sum(0)/((flat-mx)**2).sum(0)
        intercept=my-slopes*mx;residual=observed-(flat*slopes+intercept)
        score=float(np.mean((residual/observed.std(0))**2))
        result=dict(offset_half_xy=[ox,oy],slopes=slopes,intercepts=intercept,score=score,
                    rms=np.sqrt((residual**2).mean(0)),relative_rms=np.sqrt((residual**2).mean(0))/observed.mean(0))
        if full:result.update(pred=pred,saved=grid[1:61,1:63])
        return result
    coarse=[candidate(x,y) for x in range(-24,25,4) for y in range(-24,25,4)]
    best=min(coarse,key=lambda r:r['score']);ox,oy=best['offset_half_xy']
    best=min((candidate(x,y) for x in range(ox-3,ox+4) for y in range(oy-3,oy+4)),key=lambda r:r['score'])
    chosen=candidate(*best['offset_half_xy'],full=True)
    pred,saved=chosen.pop('pred'),chosen.pop('saved')
    e.dump(e.LOCAL/f'{name}_grid_fit.json',chosen)
    np.savez_compressed(e.LOCAL/f'{name}_grid_fit.npz',raw_grid_means=pred,saved_grid=saved,log_grid=saved_log)
    ae=md['dng']['ae'];mean_delta=ae['fields']['85']-mean_log
    aR,aG=chosen['slopes'][:2];bR,bG=chosen['intercepts'][:2];nR,nG=data['neutral'][:2]
    coefficient=float(data['range'])*(247*aR*nR+179*aG*nG)/256
    intercept=(247*bR+179*bG)/256
    # These equations assume one global correction applies to a hypothetical centre neutral.
    conditional=(T/2**mean_delta-intercept)/coefficient*2**float(data['be'])
    conditional_no_intercept=T/2**mean_delta/coefficient*2**float(data['be'])
    return dict(grid_wh=[int(w),int(h)],count_values=np.unique(counts),saved_mean_log=mean_log,
                saved_center_log=center_log,ae_mean_minus_grid_ev=mean_delta,
                ae_center_minus_grid_ev=ae['fields']['89']-center_log,
                ae_selected_minus_T_EC_ev=ae['fields']['95']-LOG_T-ae['ec_internal'],
                fit=chosen,conditional_u_be=float(conditional),
                conditional_no_intercept_u_be=float(conditional_no_intercept),
                conditional_delta_from_GR118_ev=float(np.log2(conditional/U118_GR3)),
                conditional_gray_jpeg=float(e.render(np.array(data['neutral'])*conditional/2**float(data['be']),data['neutral'])@e.pm.RGB_LUMA*255))


def relative_target(rgb04,raw,neutral,mode,is_neutral=None):
    standard=e.cm.rgb_lab(e.render(raw,neutral,'standard'))
    styled=e.cm.rgb_lab(e.render(raw,neutral,mode))
    # Match gr_round5 exactly: GR relative effect in D50, GXR base/target in D65.
    lab04=e.cm.xyz_lab(e.cm.srgb_decode(np.array(rgb04)/255)@e.cm.SRGB_XYZ.T,e.cm.D65)
    cS=np.hypot(standard[:,1],standard[:,2]);cT=np.hypot(styled[:,1],styled[:,2]);c04=np.hypot(lab04[:,1],lab04[:,2])
    dh=(np.arctan2(styled[:,2],styled[:,1])-np.arctan2(standard[:,2],standard[:,1])+np.pi)%(2*np.pi)-np.pi
    active=(cS>=8)&(cT>=8)&(c04>=8)
    if is_neutral is not None:active &= ~np.asarray(is_neutral)
    ab=(lab04[:,1]+1j*lab04[:,2])*np.where(active,cT/np.maximum(cS,1e-12),1)*np.exp(1j*np.where(active,dh,0))
    return np.stack([lab04[:,0]+styled[:,0]-standard[:,0],ab.real,ab.imag],-1)


def target_sensitivity(grid_results):
    data,_=e.load_scene('bastibe');ref=e.read(e.VENDOR/'color_references/gr3_reference_measurements.json')
    measured={r['chart_label']:r for r in ref['variants']['standard']['patches']}
    estimated=[r['conditional_delta_from_GR118_ev'] for n,r in grid_results.items() if n.startswith('gr3_')]
    shifts=[-.3,.3,min(estimated),max(estimated)]
    out={}
    for slot,mode in [('01','positive'),('02','negative')]:
        doc=e.read(e.VENDOR/f'color_fit_v2/gr_round5/local/inputs/state{slot}.json')
        samples=doc['models']['200']['samples'] if slot=='01' else doc['datasets']['iso200']['samples']
        raw=np.array([measured[r['label']]['camera_RGB_black_white_normalized'] for r in samples])
        base=np.array([r['rgb04'] for r in samples]);actual=np.array([r['target'] for r in samples])
        is_neutral=np.array([r['group']=='neutral' for r in samples])
        reference=relative_target(base,raw,data['neutral'],mode,is_neutral)
        out[slot]=dict(frozen_generator_vs_current_targets_colour=e.stats(e.cm.delta_e00(reference[~is_neutral],actual[~is_neutral])),shifts=[])
        for delta in shifts:
            moved=relative_target(base,raw*2**delta,data['neutral'],mode,is_neutral)
            out[slot]['shifts'].append(dict(delta_ev=float(delta),linear_ratio=float(2**delta),
                target_movement_all=e.stats(e.cm.delta_e00(moved,reference)),
                target_movement_colours=e.stats(e.cm.delta_e00(moved[~is_neutral],reference[~is_neutral])),
                L_change=e.stats(np.abs(moved[:,0]-reference[:,0]))))
        e.dump(e.LOCAL/f'anchor_sensitivity_{slot}.json',dict(summary=out[slot],labels=[r['label'] for r in samples],reference=reference))
    return out


def main():
    results={};observed={}
    for name in e.SCENES:
        data,md=e.load_scene(name)
        r=grid_fit(name,data,md);results[name]=r
        chart=e.read(e.LOCAL/f'{name}_samples.json')['chart']
        n5=next(x for x in chart if x['label']==('D4' if name=='bastibe' else 'neutral_5'))
        observed[name]=dict(program=md['dng']['program'],exposure_mode=md['dng']['exposure_mode'],
                            exposure_s=md['dng']['exposure_s'],iso=md['dng']['iso'],ec_exif=md['dng']['ec_ev'],ae=md['dng']['ae'],
                            gray_patch=dict(label=n5['label'],u_be=n5['u'],u_no_be=n5['u_no_be'],u_be_12bit=n5['u']*4095,
                                            jpeg_luma=n5['jpeg_luma'],delta_from_GR118_ev=float(np.log2(n5['u']/U118_GR3))))
        print(name,e.jsonable(r),flush=True)
    sens=target_sensitivity(results)
    ir=[r['conditional_u_be'] for n,r in results.items() if n.startswith('gr3_')]
    output=dict(evidence_level='conditional_inference_not_a_metering_calibration',
                trusted_metering_anchor_available=False,point_metering_u_be=None,point_metering_jpeg=None,
                reference_T=T,reference_log_ev=LOG_T,GR3_empirical_standard118_u_be=U118_GR3,
                empirical118_reference_convention='Existing centre-normalized radial/curve fit; current ROI u_BE is spatially uncorrected. Ratios are numerical reference comparisons, not measured spot exposure offsets.',
                GXR_nominal_curve_118_input_u=U320_GXR,observations=observed,grid_bridges=results,
                conditional_ir_spread_u_be=[min(ir),max(ir)],target_sensitivity=sens,
                assumptions=['saved grid and RAW share a geometrically inferred capture domain',
                             'affine per-channel fit extrapolates to a uniform neutral',
                             'mean AEInfo/grid ratio equals the centre point correction',
                             'GR III 2.10 AE reference applies to firmware1.00',
                             'stage1 and stage2 global/centre fields have the same semantics'],
                unresolved=['factory R/G and spatial calibration','LV/capture gain and timing',
                            'nonuniform multi-segment to spot relation','exposure program/mode conflicts'])
    e.dump(e.LOCAL/'metering_summary.json',output)
    e.dump(e.LOCAL/'anchor_diagnostic.json',dict(schema='gr-evalsets-anchor-diagnostic/1',
        approved_for_gr_round6=False,credible_anchor=False,anchor_u_be=None,anchor_jpeg_standard=None,
        units='u_BE = 2**BaselineExposure * (cR/nR+2*cG/nG+cB/nB)/4',
        applicability='conditional GR III ISO100, fixed WB; not a spot-meter measurement',
        conditional_ir_spread_u_be=[min(ir),max(ir)],
        uncertainty='scatter of conditional fits only; no defensible statistical or physical bounds'))
    print('sensitivity',e.jsonable(sens),flush=True)


if __name__=='__main__':main()
