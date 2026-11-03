"""Signed and absolute residual modes on fixed photo masks; no parameter selection."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,LOCAL
from run import load_arrays

KEYS=['L0','L1','L2_Y_post_fullfields','L3_Y_post_add_after_fullfields','L4_Y_post_add_after_Rbefore_fullfields']

def difference(a,b):return (a-b+180)%360-180
def median(x):return float(np.median(x)) if len(x) else None

def main():
    output=[]
    for i in range(51):
        meta=rt.read(LOCAL/f'target_{i:02d}.json');data=load_arrays(LOCAL/f'target_{i:02d}.npz')
        for group in ('a12-50','mount-a12'):
            base=rt.lab_from_codes(data[group+'_base']);want=rt.lab_from_codes(data[group+'_target'])
            cb=np.linalg.norm(base[:,1:],axis=1);ct=np.linalg.norm(want[:,1:],axis=1)
            hb=np.degrees(np.arctan2(base[:,2],base[:,1]));ht=np.degrees(np.arctan2(want[:,2],want[:,1]))
            masks=dict(all=np.ones(len(base),bool),near_neutral=cb<5,shadow=base[:,0]<25,
                highlight=base[:,0]>75,saturated=cb>40,
                skin_region=(hb%360>=20)&(hb%360<=70)&(cb>=5)&(cb<=45)&(base[:,0]>=20)&(base[:,0]<=85))
            baseline_error=rt.delta_e00(base,want)
            for level,key in enumerate(KEYS):
                with np.load(LOCAL/'fits'/f'{i:02d}'/(key+'.npz'),allow_pickle=False) as z:pred=rt.lab_from_codes(z[group])
                cp=np.linalg.norm(pred[:,1:],axis=1);hp=np.degrees(np.arctan2(pred[:,2],pred[:,1]))
                error=rt.delta_e00(pred,want)
                for subset,mask in masks.items():
                    if not mask.any():continue
                    target_hue_mask=mask&(cb>=5)&(ct>=5)
                    hue_mask=target_hue_mask&(cp>=5)
                    output.append(dict(label='电脑预测',index=i,name=meta['name'],unit=meta.get('unit','shared-50mm-fit'),
                        layer=level,variant=key,group=group,subset=subset,n=int(mask.sum()),overlapping_subsets=True,
                        target_minus_stock=dict(L_median=median((want[:,0]-base[:,0])[mask]),
                            C_median=median((ct-cb)[mask]),hue_deg_median=median(difference(ht,hb)[target_hue_mask])),
                        residual_pred_minus_target=dict(L_median=median((pred[:,0]-want[:,0])[mask]),
                            C_median=median((cp-ct)[mask]),hue_deg_median=median(difference(hp,ht)[hue_mask])),
                        absolute_error=dict(L_median=median(abs(pred[:,0]-want[:,0])[mask]),
                            C_median=median(abs(cp-ct)[mask]),hue_deg_median=median(abs(difference(hp,ht))[hue_mask])),
                        de00=rt.stats(error[mask]),baseline_de00=rt.stats(baseline_error[mask]),
                        hue_defined_n=int(hue_mask.sum()),
                        target_hue_defined_n=int(target_hue_mask.sum()),
                        meaning='Fixed masks from stock04. Components/masks are not additive causal shares.'))
        print('Residual modes',i,flush=True)
    rt.dump('error_modes.json',output)
    rt.finish('error_modes')

if __name__=='__main__':main()
