"""Full-frame clipping receipts and modest-resolution same-RAW comparisons."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
import numpy as np

REGIONS = {
    'R8051704': {'sky': [.36,.008,.74,.045], 'bottom_dark': [.30,.85,.80,.99]},
    'R8051705': {'sky_cloud': [.25,.02,.98,.87], 'bright_cloud': [.47,.12,.62,.40], 'left_dark': [.01,.58,.12,.68]},
    'R8051706': {'white_towel': [.40,.25,.56,.85], 'yellow_towel': [.72,.16,.90,.85]},
    'R8051702': {'toilet': [.25,.23,.65,.67]},
}


def jpeg_metrics(rgb):
    flat = rgb.reshape(-1,3)
    L = a.lab(flat[::max(1,len(flat)//200000)])
    return dict(pixels=len(flat), any_channel_ge253=float(np.mean((flat>=253).any(1))),
        all_channels_ge253=float(np.mean((flat>=253).all(1))), all_channels_255=float(np.mean((flat==255).all(1))),
        channel_ge253=np.mean(flat>=253,axis=0),
        L_p05_p50_p95=np.percentile(L[:,0],[5,50,95]), rgb_max=flat.max(0))


def full_raw_regions(rgb, d, mapping, rectangles):
    h,w=rgb.shape[:2]
    regions={'full':[0,0,1,1], **rectangles}
    out={k:dict(n=0, saturated=0, max=0., channel_n=np.zeros(3,dtype=np.int64),
                channel_saturated=np.zeros(3,dtype=np.int64),channel_max=np.zeros(3)) for k in regions}
    y0,x0,_,_=d.crop_window()
    for top in range(0,h,96):
        yy,xx=np.meshgrid(np.arange(top,min(top+96,h)),np.arange(w),indexing='ij')
        cy,cx=mapping.pixels(yy,xx)
        cy,cx=cy+y0,cx+x0
        raw=d.normalised_at(cy,cx)
        colors=d.cfa_at(cy,cx)
        for k,(rx0,ry0,rx1,ry1) in regions.items():
            mask=(xx>=rx0*w)&(xx<rx1*w)&(yy>=ry0*h)&(yy<ry1*h)
            if not mask.any(): continue
            v=raw[mask]
            c=colors[mask]
            r=out[k]
            r['n']+=len(v);r['saturated']+=int((v>=.98).sum());r['max']=max(r['max'],float(v.max()))
            for color in range(3):
                vv=v[c==color]
                if len(vv):
                    r['channel_n'][color]+=len(vv)
                    r['channel_saturated'][color]+=int((vv>=.98).sum())
                    r['channel_max'][color]=max(r['channel_max'][color],float(vv.max()))
    for k,r in out.items():
        r['saturated_fraction']=r['saturated']/r['n']
        r['channel_saturated_fraction']=r['channel_saturated']/np.maximum(r['channel_n'],1)
    return out


def dense(rgb,d,mapping,cols=300,rows=200):
    h,w=rgb.shape[:2]
    xs,ys=np.meshgrid(np.linspace(6,w-7,cols).astype(int),np.linspace(6,h-7,rows).astype(int))
    s=a.sample_blocks(rgb,d,mapping,np.column_stack([xs.ravel(),ys.ravel()]),half=3)
    return s,(rows,cols)


def main():
    scores=__import__('json').loads((a.HERE/'frame_scores.json').read_text())
    allr={}
    for n in (1691,1692,1702,1703,1704,1705,1706):
        stem=f'R805{n}'
        rgb,d,mapping,meta=a.open_frame(stem)
        rectangles=REGIONS.get(stem,{})
        h,w=rgb.shape[:2]
        stats=dict(meta=meta,jpeg={'full':jpeg_metrics(rgb)}, raw=full_raw_regions(rgb,d,mapping,rectangles))
        for k,(x0,y0,x1,y1) in rectangles.items():
            stats['jpeg'][k]=jpeg_metrics(rgb[round(y0*h):round(y1*h),round(x0*w):round(x1*w)])
        samples=np.load(a.HERE/'samples'/(stem+'.npz'))
        v=samples['valid']
        p4=a.predict('04',samples['x'])
        slot=scores[stem]['all_best']
        predicted=a.predict('02',samples['x'],'user:GRN*001') if slot=='GRN*001' else a.predict(slot,samples['x'])
        L4=a.lab(p4)
        neutral=v&(a.chroma(L4)<8)&(L4[:,0]>60)&(L4[:,0]<95)
        stats['measured_vs_predicted04']=a.metrics(samples['jpeg'],p4,v)
        stats['neutral_bright_vs_model']=a.metrics(samples['jpeg'],predicted,neutral)
        stats['neutral_bright_a_b_actual']=np.median(a.lab(samples['jpeg'])[neutral,1:],0) if neutral.any() else None
        allr[stem]=stats
        s,shape=dense(rgb,d,mapping)
        key='02' if slot=='GRN*001' else slot
        kind='user:GRN*001' if slot=='GRN*001' else 'mount'
        np.savez_compressed(a.HERE/'samples'/(stem+'-dense.npz'),
            actual=s['jpeg'].reshape(*shape,3),
            stock04=a.predict('04',s['x']).reshape(*shape,3),
            recipe=a.predict(key,s['x'],kind).reshape(*shape,3),
            raw=s['raw'].reshape(*shape,3))
        print(stem,slot,'JPEG clip all/any',round(stats['jpeg']['full']['all_channels_ge253']*100,5),
              round(stats['jpeg']['full']['any_channel_ge253']*100,5),'RAW clip',
              round(stats['raw']['full']['saturated_fraction']*100,5),'RAW peak',round(stats['raw']['full']['max'],4),flush=True)
        a.dump('scene_metrics.json',allr)
    a.finish('scenes')


if __name__=='__main__': main()
