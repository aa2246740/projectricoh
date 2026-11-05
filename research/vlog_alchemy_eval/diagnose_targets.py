"""Separate version, sampling, display interpretation and style-distance effects."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,DATA,HERE,dump
setup()
import json
import numpy as np
from data import (Cube,Target,scenes,camera_model,creator_jobs,alchemy_jobs,synthetic,
                  matrix,encode,decode,xyz_to_encoded,rgb_out,de,stats)
from measure import official_cubes,fg_input

def main():
    ss=scenes()
    xyz=np.vstack([a['xyz'][a['valid']] for a,_ in ss])
    official=official_cubes()
    rows=[]
    node=np.linspace(0,1,33)
    nodes=np.array(np.meshgrid(node,node,node,indexing='ij')).reshape(3,-1).T[:,::-1]
    node_xyz=decode(nodes,'vlog')@matrix('vgamut').T
    lin709=node_xyz@np.linalg.inv(matrix('rec709')).T
    take=np.all((lin709>=0)&(lin709<=4),axis=1)
    nodes=nodes[take];node_xyz=node_xyz[take]
    for name in ('PROVIA','CLASSIC-CHROME','CLASSIC-Neg.','ETERNA','ETERNA-BB','ACROS'):
        token='CLASSIC-Neg' if name=='CLASSIC-Neg.' else name
        cube=Cube.read(DATA/'Luts/Fujifilm'/('FLog2C_to_'+token+'_VLog.cube'))
        c=official['flog2c',name][0]
        f=official['flog2',name][0]
        a=c.apply(fg_input(xyz,'flog2c'));b=f.apply(fg_input(xyz,'flog2'))
        al=cube.apply(nodes);direct=c.apply(fg_input(node_xyz,'flog2c'))
        grayxyz=np.repeat(np.array([.01,.03,.09,.18,.5,1,2])[:,None],3,axis=1)@matrix('rec709').T
        row={'style':name,'official_flog2c_vs_flog2':stats(de(rgb_out(a),rgb_out(b))),
             'exact_vlog_nodes_no_composite_interpolation':stats(de(rgb_out(al),rgb_out(direct))),
             'gray_reflections':[.01,.03,.09,.18,.5,1,2],
             'gray_alchemy_rgb':cube.apply(xyz_to_encoded(grayxyz,'vlog')).tolist(),
             'gray_official_flog2c_rgb':c.apply(fg_input(grayxyz,'flog2c')).tolist()}
        rows.append(row)
    model,dat,_=camera_model()
    bas=[];xs=[]
    for a,m in ss:
        v=a['valid'];ui=0 if m['unit']=='a12-50' else 2
        model, _, _ = camera_model(ui)
        bas.append(model.predict(dat.entry_of(ui,4),a['codes'][v]));xs.append(a['xyz'][v])
    base=np.vstack(bas);xyz=np.vstack(xs)
    outputs={j['name']:Target(Cube.read(j['path']),j['input'],j['output']).render(base,xyz)/255
             for j in alchemy_jobs()+creator_jobs()}
    existing=json.loads((ROOT/'research/looks_g152/local/effects.json').read_text())
    for row in existing:
        if not row['name'].startswith(('HNCS','M9')): continue
        cube=Cube.read(ROOT/'research/looks_g152/local/luts'/row['source'])
        outputs[row['name']]=Target(cube,'srgb','srgb').render(base,xyz)/255
    pairs=[('Phocus Standard','HNCS HiCon'),('Phocus Standard','HNCS LowSat'),
           ('Phocus Nature','HNCS HiCon'),('Phocus Standard','Phocus Nature'),
           ('千禧回声 A','千禧回声 B'),('Leica Classic','M9 STD')]
    pairs=[{'a':a,'b':b,'de00':stats(de(outputs[a],outputs[b]))} for a,b in pairs]
    base_distance=[{'name':n,'de00_to_04':stats(de(v,base/255))} for n,v in outputs.items()]
    dump('target_diagnostics.json',{'fuji':rows,'target_pairs':pairs,'target_vs_04':base_distance,
                                  'context':'20 GXR DNG；共同固定曝光；电脑预测04；输出归一为 sRGB'})
    for r in rows[:2]: print(r['style'],'gray18',r['gray_alchemy_rgb'][3],r['gray_official_flog2c_rgb'][3],flush=True)
    print('Target diagnostics complete',flush=True)

if __name__=='__main__':
    main()
