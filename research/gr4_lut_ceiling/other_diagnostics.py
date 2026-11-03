"""Fixed metadata/radial alternatives for the unexplained natural Standard gap."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from style import Dense,feature
from PIL import Image


def main():
    d=Dense('positive')
    quality=rt.read('research/gr4_dense_returns_r1/local/target/quality.json')
    gains=np.median([v['modes']['standard']['radial']['gain_ev'] for v in quality.values()],axis=0)
    radii=next(iter(quality.values()))['modes']['standard']['radial']['radius']
    oldcoef=rt.read('research/gr4_modes/local/tone_curves.json')['radial']['gr4_coef_natural_log']
    rows=[];pooled={k:[] for k in ('existing_dense_radial','no_radial','old_shared_radial')}
    for path in sorted((rt.ROOT/'research/gr4_dense_returns_r1/local/natural').glob('*.json')):
        doc=rt.read(path);points=doc['points'];raw=np.array([p['raw_wb'] for p in points]);actual=np.array([p['observed_lab'] for p in points])
        with Image.open(rt.inp(rt.ROOT/'captures/contrib/2026-10-25-gr4-wechat/extracted/GR4/Other'/(path.stem+'.JPG'))) as im:
            w,h=im.size
            if im.getexif().get(274,1) in (5,6,7,8):w,h=h,w
        xy=np.array([[p['x'],p['y']] for p in points]);radius=np.hypot(xy[:,0]-w/2,xy[:,1]-h/2)/np.hypot(w/2,h/2)
        new_gain=2**np.interp(radius,radii,gains)
        original=raw/new_gain[:,None]
        modes={
            'existing_dense_radial':raw,
            'no_radial':original,
            'old_shared_radial':original*np.exp(-sum(c*radius**(2*(i+1)) for i,c in enumerate(oldcoef)))[:,None],
        }
        result=[];predictions={};supports={}
        for name,value in modes.items():
            p,valid,_=d.raw_function(feature(value));e=rt.cm.delta_e00(p[valid,:3],actual[valid])
            predictions[name]=p[:,:3];supports[name]=valid
            result.append(dict(profile=name,supported=int(valid.sum()),error=rt.stats(e),
                               L_bias=float(np.median(p[valid,0]-actual[valid,0])) if valid.any() else None))
        common=np.logical_and.reduce(list(supports.values()))
        for row in result:
            e=rt.cm.delta_e00(predictions[row['profile']][common],actual[common])
            row['paired_common_error']=rt.stats(e);pooled[row['profile']].extend(e)
            if common.sum()>2:
                row['L_residual_radius_correlation']=float(np.corrcoef(predictions[row['profile']][common,0]-actual[common,0],radius[common])[0,1])
        np.savez_compressed(rt.LOCAL/f'natural/Other_{path.stem}_radial.npz',
                            raw_unadjusted=original,actual_lab=actual,radius=radius,common=common,
                            **{name:predictions[name] for name in predictions})
        rows.append(dict(id=path.stem,points=len(points),common_support=int(common.sum()),median_radius=float(np.median(radius)),
                         median_existing_gain_ev=float(np.median(np.log2(new_gain))),profiles=result))
        print(path.stem,[(r['profile'],round(r['error'].get('median',-1),3)) for r in result],flush=True)
    rt.dump('natural/other_radial_diagnostics.json',dict(images=rows,paired_common_pooled={k:rt.stats(v) for k,v in pooled.items()},profile_selection_by_score=False,
               no_exposure_refit=True,no_WB_refit=True,target_changed=False))


if __name__=='__main__':main()
