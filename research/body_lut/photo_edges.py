"""Do not estimate 4:2:2 edge error from flat chart interiors alone."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import LOCAL,guard,read,inp,dump
from prepare import modules,rgb_to_ycc,SLOTS
from simulate import table_apply,apply422
from photo import dstat
import numpy as np
from PIL import Image


def main():
    guard();cm,_,_=modules();fs=cm.helper('fs')
    f=next(f for f in read('research/body_lut/local/dataset.json')['frames'] if f['id']=='R8051160')
    with Image.open(inp(f['jpeg'])) as im:
        rgb=np.asarray(im.convert('RGB'))
    pairs=rgb.reshape(-1,2,3)
    rng=np.random.default_rng(20261021)
    pairs=pairs[rng.choice(len(pairs),12000,replace=False)]
    rows={}
    for n in (9,17,33):
        rows[str(n)]={}
        table=np.load(LOCAL/f'deploy_lut{n}_float.npy')
        raw=rgb_to_ycc(pairs);r8=np.clip(np.floor(raw+.5),0,255)
        shared=r8.copy();shared[:,:,1:]=np.floor(shared[:,:,1:].mean(axis=1,keepdims=True)+.5)
        for j,s in enumerate(SLOTS):
            tt=table[:,:,:,j]
            ideal=table_apply(tt,raw,False,False)
            in8=table_apply(tt,r8,False,False)
            in422=table_apply(tt,shared,False,False)
            fixed=table_apply(tt,shared,True,False)
            final=apply422(tt,pairs)
            rows[str(n)][s]={'input8':dstat(fs,in8,ideal),
                'input422':dstat(fs,in422,in8),'fixed':dstat(fs,fixed,in422),
                'output422_and_8bit':dstat(fs,final,fixed),'combined':dstat(fs,final,ideal)}
    dump('photo_edge_results.json',{'pairs':12000,'selection':'uniformly sampled from entire actual photograph, includes boundaries',
        'scores':rows,'not_camera_RAM_error_measurement':True})
    print('full-photo pair error calculated')


if __name__=='__main__':
    main()
