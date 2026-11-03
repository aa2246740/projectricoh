"""Frozen round5 holdouts, quality summaries and GR III model checks. No fit."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
import json
import numpy as np
from scipy.stats import spearmanr


def stats(v):
    v=np.asarray(v,float)
    if not v.size:
        return dict(n=0,median=None,p90=None,max=None)
    assert np.isfinite(v).all()
    return dict(n=int(v.size),median=float(np.median(v)),p90=float(np.percentile(v,90)),max=float(v.max()))


def patch_strata(r,target,pred,base,ids):
    layout=r.ring.load_layout()['patches']
    ring=np.array([layout[i-1]['ring'] or 0 if i>0 else -1 for i in ids])
    hue=np.array([layout[i-1]['lab_h_design_deg'] if i>0 and layout[i-1]['ring'] else -1 for i in ids])
    masks=[('L45',ring==1),('L65',ring==2),('grey_ramp',(ids>=145)&(ids<=153)),
           ('reference_white',ids>=154),('150-270',(hue>=150)&(hue<270))]
    masks += [(f'h{lo:03d}-{lo+30:03d}',(hue>=lo)&(hue<lo+30)) for lo in range(0,360,30)]
    return {key:r.score(target[m],pred[m],base[m]) for key,m in masks}


def evaluate(r,ident,kind,uc,jpeg,quality,ids,xy=None):
    md=s.read(s.LOCAL/(ident+'_quality.json'))
    slot='02' if ident.endswith('39') else '01'
    mode='negative' if slot=='02' else 'positive'
    transfer=r.P.Transfer('gr4_hdf',mode,r.P.G,r.generator)
    T,u118,info=r.web.bridge({'raw':md['raw']},'gr4')
    x=uc@np.linalg.inv(T).T*(320/u118)
    D=r.P.data_of(slot,200)
    rgb04=r.P.rgb04(D,x)
    base=r.FS.lab_from_codes(rgb04)
    standard,_,_,support,_=transfer.labs(x)
    styled=r.P.CM.rgb_lab(jpeg/255)
    target=r.P.apply_relative(base,standard,styled)
    eligible=quality&(x>0).all(1)&(x<4095).all(1)&(rgb04>2).all(1)&(rgb04<253).all(1)
    valid=eligible&support
    gr3=r.P.Transfer('gr3',mode,r.P.G,r.generator)
    raw3=gr3.gr3bridge.to_gr(x)*(gr3.fw_neutral/gr3.gr3bridge.u118)*gr3.neutral
    fw_standard=r.P.CM.rgb_lab(r.generator.render_raw(raw3,'standard'))
    fw_target=r.P.apply_relative(base,fw_standard,styled)
    arrays=dict(x=x,base=base,target=target,observed=styled,standard=standard,valid=valid,
                eligible=eligible,quality=quality,standard_supported=support,ids=ids,uc=uc,jpeg=jpeg,
                fw_standard=fw_standard,fw_target=fw_target)
    if xy is not None:
        arrays['xy']=xy
    summary=dict(kind=kind,total=len(x),quality_valid=int(quality.sum()),physically_eligible=int(eligible.sum()),
                 standard_supported=int(valid.sum()),excluded_standard=int((eligible&~support).sum()),bridge=info,models={})
    for iso in (200,1600):
        DD=r.P.data_of(slot,iso)
        pred=r.P.prediction(DD,DD.current,x)
        arrays['pred'+str(iso)]=pred
        summary['models'][str(iso)]=dict(score=r.score(target[valid],pred[valid],base[valid]),
            chart_groups=patch_strata(r,target[valid],pred[valid],base[valid],ids[valid]),
            gxr04_groups=r.web.strata(r,target[valid],pred[valid],base[valid]),
            unsupported_standard_diagnostic=r.score(target[eligible&~support],pred[eligible&~support],base[eligible&~support]),
            all_eligible_mixed_standard_diagnostic=r.score(target[eligible],pred[eligible],base[eligible]),
            uniform_firmware_standard_proxy=dict(score=r.score(fw_target[eligible],pred[eligible],base[eligible]),
                chart_groups=patch_strata(r,fw_target[eligible],pred[eligible],base[eligible],ids[eligible]),
                gxr04_groups=r.web.strata(r,fw_target[eligible],pred[eligible],base[eligible])))
    np.savez_compressed(s.LOCAL/(ident+'_'+kind+'_scores.npz'),**arrays)
    s.dump(s.LOCAL/(ident+'_'+kind+'_scores.json'),summary)
    print(json.dumps(dict(id=ident,kind=kind,**summary['models']['200']['score'])))
    return arrays,summary


def quality(r,ident):
    d=s.read(s.LOCAL/(ident+'_quality.json'))
    pp=d['patches']
    gg=np.asarray(s.read(s.LOCAL/(ident+'_gaps.json')))
    # A slope is a glare diagnostic, not an identification of HDF state.
    A=np.column_stack([np.ones(len(gg)),gg[:,1]])
    fit=np.linalg.lstsq(A,gg[:,0],rcond=None)[0]
    layout=r.ring.load_layout()['patches']
    lookup={(p['row'],p['col']):p for p in layout}
    positions=[]
    for p in layout:
        for dr,dc in ((0,1),(1,0)):
            other=lookup.get((p['row']+dr,p['col']+dc))
            if other is not None and 50 not in (p['id'],other['id']):
                positions.append((np.array(p['center_px'])+np.array(other['center_px']))/2)
    positions=np.asarray(positions)/np.array([3456.,2234.])-.5
    xx,yy=positions.T
    surface=np.column_stack([np.ones(len(gg)),xx,yy,xx*xx,yy*yy,xx*yy])
    controlled=np.linalg.lstsq(np.column_stack([surface,gg[:,1]]),gg[:,0],rcond=None)[0][-1]
    low=gg[gg[:,1]<=np.quantile(gg[:,1],.25),0]
    high=gg[gg[:,1]>=np.quantile(gg[:,1],.75),0]
    white=s.read(s.LOCAL/(ident+'_white.json'))
    return dict(usable=sum(not p['flags'] for p in pp),excluded_ids=[p['id'] for p in pp if p['flags']],
        moire_count=sum('moire' in p['flags'] for p in pp if p['id']!=50),
        raw_clip_patch_count=sum('raw-clip' in p['flags'] for p in pp),
        jpeg_clip_patch_ids=[p['id'] for p in pp if 'jpeg-clip' in p['flags']],
        corner_rms_full_px=2*d['geometry']['corner_rms_px'],corners_used=d['geometry']['corners_used'],
        raw_patch_max=max(p['raw_max'] for p in pp),
        raw_noise_sigma=stats(np.asarray([p['raw_noise_sigma'] for p in pp if p['id']!=50])),
        raw_snr=stats(np.asarray([p['raw_snr'] for p in pp if p['id']!=50])),
        centre_annulus_de00=stats([p['centre_annulus_de00'] for p in pp if p['id']!=50]),
        centre_annulus_L=stats([p['centre_annulus_delta_lab'][0] for p in pp if p['id']!=50]),
        moire_amplitude_codes=stats([max(v['peak_amp'] for v in p['moire'].values()) for p in pp if p['moire'] and p['id']!=50]),
        gap=dict(n=len(gg),green_raw_median=float(np.median(gg[:,0])),brightness_slope=float(fit[1]),
                 brightness_slope_after_quadratic_position=float(controlled),
                 spearman=float(spearmanr(gg[:,0],gg[:,1]).statistic),
                 low_neighbour_green_median=float(np.median(low)),high_neighbour_green_median=float(np.median(high))),
        white=white)


def generation(r,ident,a):
    mode='negative' if ident.endswith('39') else 'positive'
    tr=r.P.Transfer('gr3',mode,r.P.G,r.generator)
    u3=tr.gr3bridge.to_gr(a['x'])
    raw3=u3*(tr.fw_neutral/tr.gr3bridge.u118)*tr.neutral
    fw_std=r.P.CM.rgb_lab(r.generator.render_raw(raw3,'standard'))
    fw_style=r.P.CM.rgb_lab(r.generator.render_raw(raw3,mode))
    empirical_std,empirical_style,style_support,std_support,_=tr.labs(a['x'])
    valid=a['quality']&a['eligible']
    # Compare absolute renders as well as the relative transform after removing
    # the empirical Standard's difference. Neither is a paired GR III capture.
    relative_fw=r.P.apply_relative(a['base'],fw_std,fw_style)
    relative_emp=r.P.apply_relative(a['base'],empirical_std,empirical_style)
    delta=fw_style-a['observed']
    de=r.FS.delta_e00(fw_style,a['observed'])
    _,co,ho=r.FS.lch(a['observed']); _,cp,hp=r.FS.lch(fw_style)
    dh=(ho-hp+180)%360-180
    layout=r.ring.load_layout()['patches']
    h=np.array([p['lab_h_design_deg'] if p['ring'] else -1 for p in layout])
    def record(m):
        return dict(absolute_fw_de00=stats(de[m]),
                    share_under_2=float(np.mean(de[m]<2)) if m.any() else None,
                    relative_fw_de00=stats(r.FS.delta_e00(relative_fw[m],a['target'][m])),
                    observed_minus_model_L_median=float(np.median(-delta[m,0])) if m.any() else None,
                    observed_minus_model_C_median=float(np.median((co-cp)[m])) if m.any() else None,
                    observed_minus_model_hue_deg_median=float(np.median(dh[m])) if m.any() else None)
    out=dict(all=record(valid),sectors30={str(lo):record(valid&(h>=lo)&(h<lo+30)) for lo in range(0,360,30)},
             hue5={str(lo):record(valid&(h==lo)) for lo in range(0,360,5)},
             empirical_gr3_supported=stats(r.FS.delta_e00(empirical_style[valid&style_support&std_support],a['observed'][valid&style_support&std_support])),
             missing_5deg_bins=[lo for lo in range(0,360,5) if not (valid&(h==lo)).any()],
             raw_in_range=int(((raw3>0).all(1)&(raw3<1).all(1)&valid).sum()),
             interpretation='model compatibility only; same-chart same-settings GR III/IIIx capture absent')
    np.savez_compressed(s.LOCAL/(ident+'_generation.npz'),raw3=raw3,fw_standard=fw_std,fw_style=fw_style,
                        empirical_std=empirical_std,empirical_style=empirical_style,valid=valid,
                        relative_fw=relative_fw,relative_empirical=relative_emp)
    s.dump(s.LOCAL/(ident+'_generation.json'),out)
    return out


def main():
    s.guard();r=s.runtime();out={}
    for ident in ('R0003037','R0003039'):
        with np.load(s.LOCAL/(ident+'_roi.npz'),allow_pickle=False) as z:
            d=dict(z)
        a,roi=evaluate(r,ident,'roi',d['uc'],d['jpeg'],d['valid'],d['ids'])
        gen=generation(r,ident,a)
        with np.load(s.LOCAL/'samples'/(ident+'.npz'),allow_pickle=False) as z:
            w=dict(z)
        keep=~w['mouse_mask']
        # Exclude entire chart patches which fail the ROI gate; outside-chart
        # samples retain the original gr_pairs flat-area gate.
        patchok=np.r_[True,d['valid']]
        keep &= patchok[w['patch_id']]
        w={k:v[keep] for k,v in w.items()}
        take=r.web.selected(w)
        aa,whole=evaluate(r,ident,'whole_flat',w['uc'][take],w['jpeg'][take],np.ones(len(take),bool),
                         w['patch_id'][take],w['xy'][take])
        # Equal-area diagnostic before feature thinning, for chart interiors.
        interior=(w['patch_id']>0)
        wi={k:v[interior] for k,v in w.items()}
        ti=r.web.selected(wi)
        _,chartflat=evaluate(r,ident,'chart_flat',wi['uc'][ti],wi['jpeg'][ti],np.ones(len(ti),bool),wi['patch_id'][ti],wi['xy'][ti])
        out[ident]=dict(quality=quality(r,ident),roi=roi,whole_flat=whole,chart_flat=chartflat,generation=gen)
    s.dump(s.LOCAL/'analysis.json',out)


if __name__=='__main__':
    main()
