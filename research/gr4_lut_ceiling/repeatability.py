"""Repeated identical injected RAW inputs estimate a narrow measurement repeatability."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from style import Dense,PAIRS,relative


def main():
    rows=[]
    for style in PAIRS:
        a=Dense(style).a
        keys,inverse,count=np.unique(np.round(a['feature'],9),axis=0,return_inverse=True,return_counts=True)
        repeated=np.flatnonzero(count>1);allerrors={s:[] for s in ('standard',style)}
        chromatic_groups=0;relative_errors=[]
        for group in repeated:
            use=inverse==group
            if np.linalg.norm(a['standard'][use,1:].mean(0))>=8:chromatic_groups+=1
            for mode in allerrors:
                mean=a[mode][use].mean(0)
                allerrors[mode].extend(rt.cm.delta_e00(a[mode][use],mean))
            transfer=relative(np.tile([50.,0.,0.],(int(use.sum()),1)),a['standard'][use],a[style][use])
            relative_errors.extend(rt.cm.delta_e00(transfer,transfer.mean(0)))
        rows.append(dict(style=style,repeated_input_groups=len(repeated),observations=int(count[repeated].sum()),
                         chromatic_groups=chromatic_groups,errors_to_group_mean={s:rt.stats(v) for s,v in allerrors.items()},
                         relative_transfer_error=rt.stats(relative_errors),
                         not_a_global_noise_floor=True,reason='repeats are concentrated in neutral references, not all chromatic samples'))
    rt.dump('style/repeatability.json',rows)
    print(rows,flush=True)


if __name__=='__main__':main()
