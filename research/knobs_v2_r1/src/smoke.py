import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
s.guard();s.dependencies()
import knobs as k
from bridge import C,compare
from model_adapter import Model,synthetic
import numpy as np

def main():
    s.freeze_inputs();modules=s.parse();c=C();count=0
    for m in modules:
        stock=m['entries'][4]
        for slot,base in m['entries'].items():
            for method in (0,1):
                assert compare(c,stock,base,k.Request(wb_method=method))[0]==base
                assert compare(c,stock,base,k.Request(amount=0,wb_method=method))[0]==stock
                for i in range(10):
                    for dose in (-4096,-2048,-1,0,1,2048,4096):
                        ds=[0]*10;ds[i]=dose
                        compare(c,stock,base,k.Request(100,tuple(ds),method,method));count+=1
            for amount in range(0,151,10):compare(c,stock,base,k.Request(amount));count+=1
    model=Model();x=synthetic();rgb=model.predict(modules[0]['entries'][4],x,quantize=True)
    print('C/Python cases',count,'model shape',rgb.shape,'range',int(rgb.min()),int(rgb.max()),flush=True)
    data=[]
    for scene in __import__('model_adapter').SCENES:
        raw,size,info=model.raw(scene)
        np.savez_compressed(s.LOCAL/(scene[0]+'_input.npz'),x=raw,size=np.array(size))
        data.append(info)
        print('loaded',scene[0],size,info['iso'],flush=True)
    s.dump(s.LOCAL/'scenes.json',data);s.dump(s.LOCAL/'model_inputs.json',model.provenance())
    s.verify_inputs()

if __name__=='__main__':main()
