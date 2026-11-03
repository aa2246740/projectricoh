"""Separate supported training RGB volume from the LUT model's completion prior."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from scipy.spatial import Delaunay,cKDTree


def main():
    a=rt.arrays(rt.LOCAL/'lut/body_data.npz');rows=[]
    for k,slot in enumerate(('01','02')):
        x=np.floor(a['base_rgb'][a['supported'][:,k]]+.5)
        hull=Delaunay(x);tree=cKDTree(x)
        for n in (17,33):
            nodes=np.stack(np.meshgrid(*([np.linspace(0,255,n)]*3),indexing='ij'),axis=-1).reshape(-1,3)
            support=hull.find_simplex(nodes)>=0;distance=tree.query(nodes)[0]
            np.savez_compressed(rt.LOCAL/f'lut/host_RGB_support_{slot}_{n}.npz',
                                inside_training_hull=support.reshape(n,n,n),nearest_RGB_distance=distance.reshape(n,n,n))
            rows.append(dict(slot=slot,cube=n,inside_training_hull=int(support.sum()),total_nodes=len(nodes),
                             fraction=float(support.mean())))
    rt.dump('lut/host_LUT_scope.json',dict(support=rows,firmware_artifact=False,camera_accepted=False,
                  target_extrapolated=False,model_completion_outside_training_hull='identity-regularized Gaussian RBF prior, not measured target truth',
                  GXR_model_domain='frozen ISO200; old physical data are ISO500 and keep that confound explicit'))


if __name__=='__main__':main()
