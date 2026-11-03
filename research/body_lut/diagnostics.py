"""Coverage, near collisions and neutral-ramp reversals; all observations stay local."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import guard,read,dump,LOCAL
from prepare import modules,SLOTS
import numpy as np
from scipy.spatial.distance import cdist


def main():
    guard();cm,_,_=modules();fs=cm.helper('fs')
    ds=read('research/body_lut/local/dataset.json');rr=ds['rows']
    x=np.array([r['ycc'] for r in rr]);g=np.array([r['group'] for r in rr])
    target=np.array([[r['targets'][s] for s in SLOTS] for r in rr])
    dd=cdist(x,x);dd[g[:,None]==g[None,:]]=np.inf
    ii,jj=np.where(np.triu(dd<=2,1))
    near=[]
    for a,b in zip(ii,jj):
        near.append({'a':int(a),'b':int(b),'distance_codes':float(dd[a,b]),
            'target_de00':{s:float(fs.delta_e00(target[a,j],target[b,j])) for j,s in enumerate(SLOTS)}})
    coverage={}
    for n in (9,17,33):
        cells=np.minimum((x*(n-1)/255).astype(int),n-2)
        coverage[str(n)]={'occupied_cells':len(np.unique(cells,axis=0)),
            'all_cube_cells':(n-1)**3,
            'fraction_full_cube':len(np.unique(cells,axis=0))/(n-1)**3}
    ramps={}
    for n in (17,33):
        ramps[str(n)]={}
        for s in SLOTS:
            with np.load(LOCAL/f'ramp_n{n}_{s}.npz') as z:
                y=z['continuous'][:,0]
                drawdown=np.maximum.accumulate(y)-y
                ramps[str(n)][s]={'max_neutral_Y_drawdown_codes':float(drawdown.max()),
                    'min_Y_derivative':float(np.diff(y).min()/(255/4095))}
    dump('diagnostics.json',{'coverage':coverage,'near_distinct_patch_pairs_within_2_codes':near,
        'neutral_ramps':ramps,
        'frame_caveats':{'physical':'ISO500 AWB differs between the two frames; no same-ISO locked-WB domain pair',
            'notables':'not in supplied frozen slot manifest; not silently assigned 04',
            'natural_scene':'R8051129 selector=4 ISO3200; excluded from the native04 gradient check'}})
    print('coverage',coverage,'near pairs',len(near),'ramps',ramps)


if __name__=='__main__':
    main()
