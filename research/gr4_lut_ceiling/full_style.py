"""Use valid unpaired Std/Posi/Nega observations as standalone absolute functions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from style import Function,feature,grouped


def main():
    records={s:[] for s in ('standard','positive','negative')}
    root='research/gr_dense_reference/local/private/gr4/r3'
    for band in range(1,5):
        card=rt.read(root+f'/cards/R000990{band+2}.json')
        receipt=rt.read(root+f'/camera-returns-20261025-nega/dense-band-{band}-analysis.json')
        byid={p['id']:p for p in card['patches']}
        for style,mode in receipt['modes'].items():
            for p in mode['patches']:
                source=byid[p['id']]
                if source['role'] not in ('colour','tone','reference','natural'):continue
                if not p['radial_supported'] or max(p['clipped_fraction'])!=0:continue
                raw=np.array(source['raw'])/np.array(card['geometry']['neutral'])
                records[style].append(dict(band=band,raw=raw,Lab=rt.lab(np.array(p['rgb_center'])*255),role=source['role']))
    results=[]
    for style,rr in records.items():
        x=feature(np.array([r['raw'] for r in rr]));y=np.array([r['Lab'] for r in rr]);bands=np.array([r['band'] for r in rr])
        # The same fixed raw-ratio coordinate gives the hue partition for all
        # modes, including points whose Standard JPEG channel was clipped.
        hue=((np.degrees(np.arctan2(x[:,2],x[:,1]))%360)//15).astype(int)%3
        full=Function(x,y)
        np.savez_compressed(rt.LOCAL/f'style/full_{style}_function.npz',feature=full.x,Lab=full.y,
                            tetrahedra=full.function.tri.simplices)
        for scheme,groups in [('page',bands),('raw_hue',hue)]:
            errors=[];supported=0;unsupported=0
            for group in np.unique(groups):
                held=groups==group;keys={tuple(q) for q in np.round(x[held],9)}
                train=np.array([not h and tuple(q) not in keys for h,q in zip(held,np.round(x,9))])
                f=Function(x[train],y[train]);pred,valid,distance=f(x[held]);e=rt.cm.delta_e00(pred[valid],y[held][valid])
                errors.extend(e);supported+=int(valid.sum());unsupported+=int((~valid).sum())
                np.savez_compressed(rt.LOCAL/f'style/full_{style}_{scheme}{group}.npz',prediction_lab=pred[valid],
                                    target_lab=y[held][valid],error=e,index=np.flatnonzero(held)[valid])
            row=dict(style=style,scheme=scheme,total=len(x),unique=len(full.x),supported=supported,
                     unsupported=unsupported,error=rt.stats(errors),paired_support_not_relaxed=True,
                     standalone_absolute_function_only=True)
            results.append(row);print('full',style,scheme,len(x),row['error'],flush=True)
    rt.dump('style/full_functions.json',results)


if __name__=='__main__':main()
