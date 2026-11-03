"""Separate interpolation, node/weight quantization and 8-bit output errors."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from lut import fit,predict,vertices


def main():
    a=rt.arrays(rt.LOCAL/'lut/body_data.npz');rows=[]
    for k,slot in enumerate(('01','02')):
        valid=a['supported'][:,k];x=np.floor(a['base_rgb'][valid]+.5)
        mdl=fit(x,np.clip(rt.rgb(a['targets'][valid,k]),0,255),48.,.03)
        pixels=a['pairs'][valid].reshape(-1,3).astype(float)
        exact=np.empty_like(pixels)
        for start in range(0,len(pixels),2048):exact[start:start+2048]=np.clip(predict(mdl,pixels[start:start+2048]),0,255)
        for n in (17,33):
            vv,w=vertices(pixels,n,False);nodes=vv.reshape(-1,3)*(255/(n-1))
            unique,inv=np.unique(nodes,axis=0,return_inverse=True);values=np.empty_like(unique)
            for start in range(0,len(unique),2048):values[start:start+2048]=np.clip(predict(mdl,unique[start:start+2048]),0,255)
            floatvals=values[inv].reshape(len(pixels),4,3);interp=(floatvals*w[:,:,None]).sum(1)
            vq,wq=vertices(pixels,n,True)
            nodeq=vq.reshape(-1,3)*(255/(n-1));uniqueq,invq=np.unique(nodeq,axis=0,return_inverse=True);valuesq=np.empty_like(uniqueq)
            for start in range(0,len(uniqueq),2048):valuesq[start:start+2048]=np.clip(predict(mdl,uniqueq[start:start+2048]),0,255)
            qvalues=np.floor(valuesq*256+.5).astype(np.int64)[invq].reshape(len(pixels),4,3)
            quant=(qvalues*wq[:,:,None]).sum(1)/65536;out8=np.floor(quant+.5)
            components=dict(interpolation=(interp,exact),nodes_and_weights=(quant,interp),
                            output8=(out8,quant),total=(out8,exact))
            detail={};saved={}
            for name,(left,right) in components.items():
                pixel_error=rt.cm.delta_e00(rt.lab(left),rt.lab(right))
                means_left=left.reshape(-1,48,3).mean(1);means_right=right.reshape(-1,48,3).mean(1)
                patch_error=rt.cm.delta_e00(rt.lab(means_left),rt.lab(means_right))
                detail[name]=dict(pixel=rt.stats(pixel_error),patch=rt.stats(patch_error));saved[name+'_pixel_error']=pixel_error;saved[name+'_patch_error']=patch_error
            np.savez_compressed(rt.LOCAL/f'lut/quantization_{slot}_{n}.npz',**saved)
            rows.append(dict(slot=slot,cube=n,components=detail,against_continuous_software_function=True,
                             camera_implementation_error_measured=False))
            print('quantization',slot,n,detail,flush=True)
    rt.dump('lut/quantization.json',rows)


if __name__=='__main__':main()
