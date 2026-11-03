"""Actual 04 photograph: 4:2:2, quantization, slopes and histogram holes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT, LOCAL, guard, inp, read, dump
from prepare import modules, rgb_to_ycc, ycc_to_rgb, SLOTS
from simulate import table_apply, apply422
import numpy as np
from PIL import Image


def hole_stats(y):
    hist=np.bincount(np.asarray(y).astype(np.uint8).ravel(),minlength=256)
    active=np.flatnonzero(hist)
    lo,hi=int(active[0]),int(active[-1])
    return {'range':[lo,hi],'interior_holes':int(np.sum(hist[lo:hi+1]==0)),
            'holes_5_to_250':int(np.sum(hist[5:251]==0)), 'histogram':hist}


def dstat(fs,a,b):
    e=fs.delta_e00(fs.lab_from_codes(np.clip(ycc_to_rgb(a),0,255).reshape(-1,3)),
                     fs.lab_from_codes(np.clip(ycc_to_rgb(b),0,255).reshape(-1,3)))
    return {'median':float(np.median(e)),'p90':float(np.percentile(e,90)),'max':float(e.max())}


def main():
    guard()
    cm,_,_=modules();fs=cm.helper('fs')
    ds=read('research/body_lut/local/dataset.json')
    frame=next(f for f in ds['frames'] if f['id']=='R8051160')
    with Image.open(inp(frame['jpeg'])) as im:
        rgb=np.asarray(im.convert('RGB'))
    h,w=rgb.shape[:2];assert w%2==0
    base=np.clip(np.floor(rgb_to_ycc(rgb)+.5),0,255).astype(np.uint8)
    rng=np.random.default_rng(20261021)
    points=base.reshape(-1,3)[rng.choice(h*w,12000,replace=False)].astype(float)
    pairs=np.asarray([r['pairs_rgb'] for r in ds['rows']]).reshape(-1,2,3)
    report={'photograph':frame,'shape':[h,w], 'is_actual_capture':True,
        'scene':'physical 24-patch ColorChecker photograph; no verified native-04 natural-scene frame available',
        'baseline_histogram':hole_stats(base[...,0]),'results':{},'precision_components':{},
        'limitation':'JPEG-decode proxy for unknown pre-compression RAM; histograms do not prove absence of visible banding'}
    Image.fromarray(rgb).resize((1072,712)).save(LOCAL/'photo_original_preview.png')
    for n in (9,17,33):
        table=np.load(LOCAL/f'deploy_lut{n}_float.npy')
        report['results'][str(n)]={}
        report['precision_components'][str(n)]={}
        for j,s in enumerate(SLOTS):
            tt=table[:,:,:,j]
            raw=rgb_to_ycc(pairs)
            raw8=np.clip(np.floor(raw+.5),0,255)
            shared=raw8.copy();shared[:,:,1:]=np.floor(shared[:,:,1:].mean(axis=1,keepdims=True)+.5)
            ideal=table_apply(tt,raw,False,False)
            quantin=table_apply(tt,raw8,False,False)
            in422=table_apply(tt,shared,False,False)
            fixed=table_apply(tt,shared,True,False)
            out422=apply422(tt,pairs)
            report['precision_components'][str(n)][s]={
                'input8_vs_continuous444':dstat(fs,quantin,ideal),
                'shared_input_chroma_vs_444':dstat(fs,in422,quantin),
                'Q8_fraction_and_Q8_8_nodes':dstat(fs,fixed,in422),
                'output422_and_output8':dstat(fs,out422,fixed),
                'combined_vs_continuous444':dstat(fs,out422,ideal)}
            if n==9:
                continue
            out=np.empty_like(base)
            for y in range(0,h,64):
                pp=rgb[y:y+64].reshape(-1,2,3)
                out[y:y+64]=apply422(tt,pp).reshape(-1,w,3).astype(np.uint8)
            np.save(LOCAL/f'photo_n{n}_{s}_ycc.npy',out)
            preview=np.clip(np.floor(ycc_to_rgb(out[::2,::2])+.5),0,255).astype(np.uint8)
            Image.fromarray(preview).save(LOCAL/f'photo_n{n}_{s}_preview.png')
            hist=hole_stats(out[...,0])
            slopes=[]
            for axis in range(3):
                lo=points.copy();hi=points.copy()
                lo[:,axis]=np.maximum(lo[:,axis]-.5,0)
                hi[:,axis]=np.minimum(hi[:,axis]+.5,255)
                dd=(table_apply(tt,hi,False,False)-table_apply(tt,lo,False,False))/(
                    hi[:,axis]-lo[:,axis])[:,None]
                slopes.append({'max_abs':float(np.max(np.abs(dd))),
                    'p99_abs':float(np.percentile(np.abs(dd),99))})
            gray_ramp=np.stack([np.linspace(0,255,4096),np.full(4096,128.),np.full(4096,128.)],axis=-1)
            ramp=table_apply(tt,gray_ramp,False,False)
            ramp8=table_apply(tt,gray_ramp,True,True)
            np.savez(LOCAL/f'ramp_n{n}_{s}.npz',input=gray_ramp,continuous=ramp,quantized=ramp8)
            report['results'][str(n)][s]={'histogram':hist,'observed_photo_max_local_slopes':slopes,
                'global_node_edge_max_slope':float(max(np.abs(np.diff(tt,axis=a)).max()*(n-1)/255 for a in range(3))),
                'gray_ramp_max_Y_slope':float(np.max(np.abs(np.diff(ramp[:,0])))/(255/4095)),
                'gray_ramp_Y_descending_steps':int(np.sum(np.diff(ramp[:,0]) < -1e-8)),
                'gray_ramp_output_Y_codes':int(len(np.unique(ramp8[:,0]))),
                'gray_ramp_max_identical_run_samples':int(np.max(np.diff(np.r_[0,
                    np.flatnonzero(np.diff(ramp8[:,0])!=0)+1,len(ramp8)])))}
            print('photo',n,s,flush=True)
    dump('photo_results.json',report)


if __name__=='__main__':
    main()
