"""Screen-trained LUT on the unseen ISO200 native physical-chart photograph."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from isp import model
from style import Dense,feature
from lut import fit,apply
from PIL import Image


def main():
    m=model();d=rt.arrays(rt.LOCAL/'bridge/R8051477.npz')
    md=next(x for x in rt.read(rt.LOCAL/'bridge/native.json') if x['id']=='R8051477')
    assert md['matches_calibrated_menu_state'] and md['iso']==200
    eligible=d['valid']&(d['jpeg_sd'].max(1)<3.5)
    indices=np.flatnonzero(eligible)
    key=np.floor(feature(np.maximum(d['raw_wb'][indices],1e-7))/[.12,.04,.04]).astype(int)
    _,first=np.unique(key,axis=0,return_index=True);take=indices[first]
    x,bad=m.inverse04(d['observed'][take],d['raw_wb'][take])
    base=rt.lab(d['observed'][take])
    folder=rt.ROOT/'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root/DCIM/100RICOH'
    with Image.open(rt.inp(folder/'R8051477.JPG')) as im:image=np.asarray(im.convert('RGB'))
    xx,yy=np.meshgrid(np.arange(-6,6),np.arange(-6,6));offset=np.c_[xx.ravel(),yy.ravel()]
    chosen=offset[np.linspace(0,len(offset)-1,48,dtype=int)]
    center=d['centers'][take];pixels=image[center[:,1,None]+chosen[None,:,1],center[:,0,None]+chosen[None,:,0]]
    training=rt.arrays(rt.LOCAL/'lut/body_data.npz');results=[]
    for k,(slot,style) in enumerate((('01','positive'),('02','negative'))):
        target,supported,_=Dense(style).target(x,base);valid=supported&~bad
        train=(training['domain']=='screen')&training['supported'][:,k]
        mdl=fit(np.floor(training['base_rgb'][train]+.5),np.clip(rt.rgb(training['targets'][train,k]),0,255),48.,.03)
        baseline=rt.cm.delta_e00(base[valid],target[valid])
        for n in (17,33):
            pred=apply(mdl,pixels[valid].reshape(-1,3),n).reshape(int(valid.sum()),48,3).mean(1)
            error=rt.cm.delta_e00(rt.lab(pred),target[valid])
            row=dict(slot=slot,cube=n,source='R8051477',points=int(valid.sum()),**rt.score(error,baseline),
                     ISO200=True,menu_matches_calibration=True,physical_image_never_trained=True,
                     target_is_relative_proxy_not_GRIV_same_physical_scene=True)
            results.append(row);print('native physical',slot,n,row['similarity_median'],row['error'],flush=True)
            np.savez_compressed(rt.LOCAL/f'lut/native1477_{slot}_{n}.npz',prediction=pred,target=target[valid],
                                error=error,baseline=baseline,index=take[valid])
    rt.dump('lut/native_physical_summary.json',results)


if __name__=='__main__':main()
