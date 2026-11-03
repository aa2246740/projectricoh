"""Compare feasible continuous colour rings for the four fits and stock control."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,HERE,BUILD_DATA,dump
setup()
import json
import numpy as np
from data import camera_model

def main():
    model,dat,provenance=camera_model()
    mm=model.mm;fs=model.fs
    reference=mm.MatrixRow.from_bytes(dat.entry_of(0,4)[216:244])
    candidates=[('stock04',dat.entry_of(0,4))]
    candidates += [(r['name'],bytes.fromhex(r['entry_hex']))
                   for r in json.loads((BUILD_DATA/'local/effects.json').read_text())]
    angle=np.deg2rad(np.arange(0,360,.25))
    out=[]
    for name,entry in candidates:
        q=np.array(list(entry[82:115]))
        row=mm.MatrixRow.from_bytes(entry[216:244])
        ab=np.array([fs.decode_word(entry[i:i+4]) for i in range(115,211,4)])
        z=fs.Z_of_words(ab[:,0],ab[:,1],model.engine.ctx)
        count=0;reversals=0;clipped_pairs=0;clipped_reversals=0;minimum=1e9
        for level in (12,24,48,72,96,128,160,192,224,244):
            for radius in (.5,2,5,10,20,40,80):
                circle=radius*np.exp(1j*angle)
                pre=reference.invert(np.full(len(circle),level),circle)
                physical=np.all((pre>q[0]+1e-8)&(pre<q[-1]-1e-8),axis=1)
                y,ci=row.apply(pre)
                co=model.engine.table.forward(ci,z)[0]
                rgb=mm.rgb_from_ycc(y,co)
                clipped=np.any((rgb<0)|(rgb>255),axis=1)
                pairs=physical&np.roll(physical,-1)
                good=pairs&~clipped&~np.roll(clipped,-1)&(abs(co)>1e-8)&(abs(np.roll(co,-1))>1e-8)
                derivative=np.angle(np.roll(co,-1)[good]/co[good],deg=True)/.25
                count+=int(good.sum());reversals+=int((derivative<=0).sum())
                if len(derivative): minimum=min(minimum,float(derivative.min()))
                jpegco=mm.ycbcr(np.clip(rgb,0,255))[1]
                cp=pairs&~good&(abs(jpegco)>1e-8)&(abs(np.roll(jpegco,-1))>1e-8)
                cd=np.angle(np.roll(jpegco,-1)[cp]/jpegco[cp],deg=True)/.25
                clipped_pairs+=int(cp.sum());clipped_reversals+=int((cd<-.000001).sum())
        out.append({'name':name,'unclipped_pairs':count,'unclipped_hue_reversals':reversals,
                    'minimum_unclipped_hue_derivative':None if minimum==1e9 else minimum,
                    'clipped_pairs':clipped_pairs,'clipped_hue_reversals':clipped_reversals})
    dump('physical_ring_checks.json',{'method':'连续可达共同曲线范围；0.25度色环；不含8位量化与相机实拍',
        'model_scope':'50mm ISO200 模型；三单元物理表现未定','provenance':provenance,'results':out})
    print(out,flush=True)

if __name__=='__main__':
    main()
