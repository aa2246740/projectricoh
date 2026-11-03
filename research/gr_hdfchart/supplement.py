"""Settings cross-checks, white-frame diagnostics and a simple grey-referred check."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
from score_chart import stats
import argparse
import json
import numpy as np


def grey_normalized(r,rgb,design,mid):
    linear=r.P.CM.srgb_decode(np.asarray(rgb)/255)
    Y=linear@np.array([.2126729,.7151522,.0721750])
    Ydesign=r.P.CM.srgb_decode(design/255)@np.array([.2126729,.7151522,.0721750])
    gain=float(np.exp(np.median(np.log(Ydesign[mid]/Y[mid]))))
    normalized=np.clip(r.P.CM.srgb_encode(linear*gain),0,1)*255
    return normalized,gain


def main(white_paths):
    s.guard();r=s.runtime();cm=r.P.CM
    out=dict(white_frames=[],settings={})
    for path in white_paths:
        path=path.resolve();assert path.is_relative_to(s.ROOT/'captures')
        ident=path.stem[-8:]
        f=dict(id=ident,family='gr4',dng=str(path.relative_to(s.ROOT)),jpg=None)
        raw,md=r.extract.raw_frame(f)
        tags={int(k):v for k,v in md['tags'].items()}
        rgb=raw['rgb'];hh,ww=rgb.shape[:2]
        block=rgb[int(hh*.28):int(hh*.6),int(ww*.40):int(ww*.70)]
        white=np.median(block.reshape(-1,3),axis=0)
        temp=6504.
        for _ in range(20):
            M,_=cm.camera_matrix_at_temperature(tags,temp);xyz=np.linalg.solve(M,white);temp=cm.cct_mccamy(xyz)
        # Fit no new coefficients. Only compare existing radial correction on
        # broad central screen tiles; panel/room nonuniformity remains confounded.
        coef=s.read(s.ROOT/'research/gr4_modes/local/tone_curves.json')['radial']['gr4_coef_natural_log']
        tiles=[]
        for yf in np.linspace(.12,.70,8):
            for xf in np.linspace(.20,.86,10):
                y,x=int(hh*yf),int(ww*xf)
                green=float(np.median(rgb[y-10:y+10,x-10:x+10,1]))
                r2=((y-(hh-1)/2)**2+(x-(ww-1)/2)**2)/((hh/2)**2+(ww/2)**2)
                gain=np.exp(-sum(c*r2**(i+1) for i,c in enumerate(coef)))
                tiles.append([green,green*gain])
        tiles=np.array(tiles)
        out['white_frames'].append(dict(id=ident,metadata=sys.modules['common'].metadata(path),
              xy=(xyz[:2]/xyz.sum()).tolist(),cct_K=temp,raw_central_max=float(block.max()),
              raw_clip_fraction=float(raw['clip'].mean()),
              tile_relative_sd_before=float(tiles[:,0].std()/tiles[:,0].mean()),
              tile_relative_sd_after=float(tiles[:,1].std()/tiles[:,1].mean()),
              radial_validation='not identified separately from display nonuniformity'))
        s.dump(s.LOCAL/(ident+'_white_raw.json'),md)
    old=s.read(s.ROOT/'research/gr_webpairs/metadata.json')
    out['settings']['dpreview']={q['id']:dict(shadow=q['metadata']['decoded']['shadow_correction_0x0079'],
             dr=q['metadata']['decoded']['dynamic_range_0x0069']) for q in old if q['id'] in ('SC0134','SC0434')}
    old=s.read(s.ROOT/'research/gr_pairs/local/inventory.json')
    out['settings']['hdf_set']={q['id']:dict(shadow=q['metadata']['shadow'],dr=q['metadata']['dr_tag'])
               for q in old if q['id'] in ('hdf_standard','hdf_positive','hdf_negative')}
    # A transparent, model-free chart-colour diagnostic: one log-luminance gain
    # per JPEG from L30..L70 greys. This removes tone/exposure information and is
    # expressly not a full recipe-fidelity score.
    layout=r.ring.load_layout()['patches'];ids=np.arange(1,156)
    design=np.array([p['srgb8'] for p in layout]);mid=(ids>=147)&(ids<=151)
    frames={f['id']:f for f in s.read(s.ROOT/'research/closed_loop/local/m20261021_r1_gr.json')['frames']}
    for slot,ident in (('01','R0003037'),('02','R0003039')):
        with np.load(s.LOCAL/(ident+'_roi.npz'),allow_pickle=False) as z:source=dict(z)
        with np.load(s.LOCAL/(slot+'_corrected_gxr.npz'),allow_pickle=False) as z:d=dict(z)
        clean_mid=mid&d['valid']
        assert clean_mid.any()
        tr,gt=grey_normalized(r,source['jpeg'],design,clean_mid)
        pr,gp=grey_normalized(r,frames['screen'+slot]['rgb'],design,clean_mid)
        br,gb=grey_normalized(r,frames['screen04']['rgb'],design,clean_mid)
        valid=d['valid']&(ids<=144)
        labt,labp,labb=[r.FS.lab_from_codes(q) for q in (tr,pr,br)]
        out['grey_referred_'+slot]=dict(score=r.score(labt[valid],labp[valid],labb[valid]),
            target_gain=gt,recipe_gain=gp,baseline_gain=gb,
            normalization_greys=int(clean_mid.sum()),
            scope='chart colours after independent grey-ramp normalization; tone is removed; no 95% acceptance')
        np.savez(s.LOCAL/(slot+'_simple_grey.npz'),target=labt,pred=labp,base=labb,valid=valid)
    # The negative residual is only a diagnostic control for shared model and
    # capture errors. It is not a new Standard observation or a fitted model.
    from correct_targets import residual_transport
    with np.load(s.LOCAL/'R0003037_generation.npz',allow_pickle=False) as z:gp=dict(z)
    with np.load(s.LOCAL/'R0003039_generation.npz',allow_pickle=False) as z:gn=dict(z)
    with np.load(s.LOCAL/'R0003037_roi_scores.npz',allow_pickle=False) as z:op=dict(z)
    with np.load(s.LOCAL/'R0003039_roi_scores.npz',allow_pickle=False) as z:on=dict(z)
    neutral=np.array([p['group']=='gray' for p in layout])
    calibrated=residual_transport(gp['fw_style'],gn['fw_style'],on['observed'],neutral)
    valid=gp['valid']&gn['valid']
    _,co,ho=r.FS.lch(op['observed']);_,cp,hp=r.FS.lch(calibrated)
    delta_h=(ho-hp+180)%360-180
    hue=np.array([p['lab_h_design_deg'] if p['ring'] else -1 for p in layout])
    de=r.FS.delta_e00(calibrated,op['observed'])
    def rec(m):
        return dict(de00=stats(de[m]),delta_h_median=float(np.median(delta_h[m])) if m.any() else None,
                    delta_C_median=float(np.median((co-cp)[m])) if m.any() else None)
    out['positive_after_negative_control']=dict(all=rec(valid),
           sectors30={str(lo):rec(valid&(hue>=lo)&(hue<lo+30)) for lo in range(0,360,30)},
           hue5={str(lo):rec(valid&(hue==lo)) for lo in range(0,360,5)})
    np.savez(s.LOCAL/'positive_control.npz',pred=calibrated,target=op['observed'],valid=valid)
    # Assert the actual control settings on all four captures.
    controls=[q['metadata'] for q in out['white_frames']]
    controls += [s.read(s.LOCAL/(ident+'_quality.json'))['frame']['metadata'] for ident in ('R0003037','R0003039')]
    for md in controls:
        sliders=md['sliders']
        expected=(-1,3,-1,-2) if md['image_tone']['value']==262 else (1,1,0,-1)
        assert tuple(sliders[k] for k in ('high_low_key','contrast','contrast_highlight','contrast_shadow'))==expected
        assert all(sliders[k]==0 for k in ('saturation','hue','sharpness','clarity','shading'))
        assert md['shadow']==[2,4] and md['dr_tag']=='01010000'
    out['settings']['new_four_default_sliders_asserted']=True
    s.dump(s.LOCAL/'supplement.json',out)
    print(json.dumps(out,ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--white-dng',type=Path,action='append',required=True)
    a=ap.parse_args();main(a.white_dng)
