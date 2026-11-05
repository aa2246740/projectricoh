"""Scene-referred film library: data, constrained structure surrogate, and full-start fits."""
import argparse
import ast
import copy
import hashlib
from pathlib import Path
import struct
import sys
import types
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import np,rt,ROOT,LOCAL,UNITS,read,dump,sha,predict,arrays

CATALOG=read(LOCAL/'catalog.json')
ROUTES=CATALOG['routes']
FULL={'scene_rgb','scene_rgb_matrix','scene_structure','scene_weighted'}
MATRIX={'scene_shared_matrix','scene_shared_structure','scene_rgb_matrix','scene_structure','scene_weighted'}


class FilmTarget:
    def __init__(self,film):
        from gxr_studio.lut.cube import Cube
        self.film=film
        self.scene_cube=Cube.read(Path(film['scene']['file']))
        self.jpeg_cube=Cube.read(Path(film['jpeg']['file']))
        self.default_cube=Cube.read(Path(film['jpeg_default']['file'])) if 'jpeg_default' in film else self.jpeg_cube
        for name in ('scene','jpeg','jpeg_default'):
            if name not in film:continue
            assert sha(film[name]['file'])==film[name]['sha256']

    def __call__(self,xyz,base=None,usage='scene'):
        from gxr_studio.lut.spaces import xyz_to_encoded
        if usage=='jpeg':codes=np.asarray(base)/255;cube=self.jpeg_cube
        elif usage=='scene_srgb_control':codes=xyz_to_encoded(xyz,'srgb');cube=self.jpeg_cube
        elif usage=='scene_default_control':codes=xyz_to_encoded(xyz,'srgb');cube=self.default_cube
        else:codes=xyz_to_encoded(xyz,self.film['scene_space']);cube=self.scene_cube
        return np.clip(cube.apply(codes),0,1)*255


def reference(unit):
    p=ROOT/'research/recipe_redo_r1/local/inputs'/unit/'definition.json'
    d=read(p)
    return np.asarray(d['neutral']),np.asarray(d['matrix'])


def raw_from_xyz(camera,xyz,unit):
    neutral,matrix=reference(unit)
    u,f=camera.anchor['u_m'],camera.anchor['f']
    white=neutral@matrix.T
    scale=.18/((u-f)*white[1])
    return 4095*((np.asarray(xyz)@np.linalg.inv(matrix).T)/scale/neutral+f)


def inverse_input(x,unit):
    coef=C.coefficients(unit)
    raw=(np.asarray(x)/4095-coef[0])@np.linalg.inv(np.eye(3)+coef[1:4])
    if len(coef)==10:
        for unused in range(24):
            residual=C.pc.apply(raw*4095,coef)/4095-np.asarray(x)/4095
            if abs(residual).max()<1e-12:break
            r,g,b=raw.T
            derivative=np.zeros((len(raw),10,3));derivative[:,1:4]=np.eye(3)
            derivative[:,4,0],derivative[:,5,1],derivative[:,6,2]=2*r,2*g,2*b
            derivative[:,7,0],derivative[:,7,1]=g,r
            derivative[:,8,0],derivative[:,8,2]=b,r
            derivative[:,9,1],derivative[:,9,2]=b,g
            jac=np.eye(3)[None]+np.einsum('nfi,fo->noi',derivative,coef)
            raw-=np.linalg.solve(jac,residual[...,None])[...,0]
    assert abs(C.pc.apply(raw*4095,coef)-x).max()<1e-5
    return raw*4095


def regions(xyz):
    from gxr_studio.lut.spaces import xyz_to_encoded
    lab=rt.lab_from_codes(np.clip(xyz_to_encoded(xyz,'srgb'),0,1)*255)
    chroma=np.hypot(lab[:,1],lab[:,2]);hue=np.degrees(np.arctan2(lab[:,2],lab[:,1]))%360
    out={}
    for key,rule in CATALOG['rules']['color_region_masks'].items():
        out[key]=((lab[:,0]>=rule['L'][0])&(lab[:,0]<=rule['L'][1])&
            (chroma>=rule['C'][0])&(chroma<=rule['C'][1])&(hue>=rule['h'][0])&(hue<=rule['h'][1]))
    return out


def structural_seed(camera,target,unit):
    white=np.array([.3127/.3290,1.,(1-.3127-.3290)/.3290])
    ev=np.linspace(-12,8,2001)
    xyz=.18*2**ev[:,None]*white
    raw=raw_from_xyz(camera,xyz,unit);x=C.input_codes(raw,unit)
    desired=target(xyz)
    q=np.array([np.interp(camera.curve.xs,x[:,j],desired[:,j]) for j in range(3)])
    rawq=q.copy();q=np.maximum.accumulate(np.clip(q,0,255),axis=1)
    middle_xyz=np.array([.18*white]);middle_raw=raw_from_xyz(camera,middle_xyz,unit)
    middle=C.input_codes(middle_raw,unit)
    neutral,matrix=reference(unit)
    J=np.empty((3,3));slopes=[]
    for j in range(3):
        eps=max(1.,float(abs(middle[0,j])*.01));delta=np.zeros((1,3));delta[0,j]=eps
        plus=camera.xyz(inverse_input(middle+delta,unit),neutral,matrix)
        minus=camera.xyz(inverse_input(middle-delta,unit),neutral,matrix)
        J[:,j]=((target(plus)-target(minus))/(2*eps))[0]
        ix=np.clip(np.searchsorted(camera.curve.xs,middle[0,j])-1,0,31)
        slopes.append((q[j,ix+1]-q[j,ix])/(camera.curve.xs[ix+1]-camera.curve.xs[ix]))
    rgb=J@np.diag(1/np.maximum(np.asarray(slopes),1e-5))
    rgb=np.clip(rgb,-2,2)
    ycc=np.array([[.299,.587,.114],[-.168736,-.331264,.5],[.5,-.418688,-.081312]])
    mat=ycc@rgb*1024
    # The initializer respects exactly the same C100 coefficient search box as the solver.
    base=camera.row.coef.astype(float)
    pY=(mat[0,[0,2]]-base[0,[0,2]])/1024
    pY=np.clip(pY,-.8,.8)
    mat[0]=base[0]+1024*np.array([pY[0],-pY.sum(),pY[1]])
    mat[1:]=np.clip(mat[1:],np.maximum(base[1:]-.8*1024,-1279),np.minimum(base[1:]+.8*1024,1279))
    return dict(curve_y_u8=np.rint(q).astype(int),matrix_q10=np.rint(mat).astype(int),
        total_response_not_layer_density=True,print_folded_into_input_curves=True,
        neutral_monotonic_projection_max_codes=float(abs(q-rawq).max()),
        midpoint_xyz=middle_xyz,midpoint_conditioned_input=middle,local_RGB_Jacobian=J,
        stage_order_mismatch='Real spectral mixing precedes layer nonlinearities and print follows mixing; GXR exposes curves -> matrix -> sectors, no proven separate print curve.')


def shared_structure(camera,original):
    """Give the shared-curve side the same neutral-response initialization budget."""
    q=np.asarray(original['curve_y_u8'],float)
    one=np.rint(np.array([.299,.587,.114])@q).astype(int)
    middle=np.asarray(original['midpoint_conditioned_input'])[0]
    slopes=[]
    for j in range(3):
        ix=np.clip(np.searchsorted(camera.curve.xs,middle[j])-1,0,31)
        slopes.append((one[ix+1]-one[ix])/(camera.curve.xs[ix+1]-camera.curve.xs[ix]))
    rgb=np.asarray(original['local_RGB_Jacobian'])@np.diag(1/np.maximum(slopes,1e-5))
    rgb=np.clip(rgb,-2,2)
    ycc=np.array([[.299,.587,.114],[-.168736,-.331264,.5],[.5,-.418688,-.081312]])
    mat=ycc@rgb*1024;base=camera.row.coef.astype(float)
    pY=np.clip((mat[0,[0,2]]-base[0,[0,2]])/1024,-.8,.8)
    mat[0]=base[0]+1024*np.array([pY[0],-pY.sum(),pY[1]])
    mat[0]=np.clip(mat[0],-2047,2047)
    mat[1:]=np.clip(mat[1:],np.maximum(base[1:]-.8*1024,-1279),np.minimum(base[1:]+.8*1024,1279))
    return dict(original,shared_curve_y_u8=one[None,:],shared_matrix_q10=np.rint(mat).astype(int),
        fair_shared_curve_initialization=True)


def parameters_of(entry):
    from gxr_studio.engine.knobs import dec
    words=np.array([[dec(v,128) for v in entry[i:i+4]] for i in range(115,211,4)])
    assert np.array_equal(words[:,0],words[:,3]) and np.array_equal(words[:,1],-words[:,2])
    ab=words[:,:2]
    return dict(curve_x_u12=np.r_[0,struct.unpack_from('>31H',entry,20),4095],
        curve_y_u8=np.array([list(entry[379:412]),list(entry[82:115]),list(entry[412:445])]) if entry[1]&4 else np.array([list(entry[82:115])]),
        matrix_q10=rt.mm.MatrixRow.from_bytes(entry[216:244]).coef,sector_a=ab[:,0],sector_b=ab[:,1])


def template(camera,ui,full):
    b=bytearray(camera.entry);b[0]=6 if full else 5
    b[1]|=1  # The fitted C100 must stay enabled through kv_apply_work.
    return C.codec.encode(bytes(b),parameters_of(camera.entry),level=int(full),
        look_unit_mask=None if full else 1<<ui)


def prepare(ordinal):
    film=CATALOG['films'][ordinal];target=FilmTarget(film)
    for ui,unit in enumerate(UNITS):
        camera=rt.Camera(ui);root=LOCAL/'films'/f'{ordinal:02d}'/unit
        root.mkdir(parents=True,exist_ok=True)
        meta=read(LOCAL/'targets'/unit/'14/profile.json')
        groups={}
        for key,path in meta['groups'].items():
            v=arrays(path)
            v={k:value for k,value in v.items() if k not in ('alchemy_want','want')}
            v['want']=target(v['xyz'])
            v['want_jpeg']=target(v['xyz'],v['base_new'],'jpeg')
            v['want_scene_srgb_control']=target(v['xyz'],usage='scene_srgb_control')
            p=root/(key+'.npz');np.savez_compressed(p,**v);groups[key]=str(p)
            if key=='train':
                j=dict(v,want=v['want_jpeg']);np.savez_compressed(root/'train_jpeg.npz',**j)
                masks=regions(v['xyz']);weight=np.ones(len(v['x']))
                for m in masks.values():weight[m]=2.5
                w=dict(v,sw=v['sw']*weight);np.savez_compressed(root/'train_weighted.npz',**w)
        seed=structural_seed(camera,target,unit);dump(root/'structure.json',seed)
        for route in ROUTES:
            index=film['indices'][route];folder=LOCAL/'targets'/unit/f'{index:02d}'
            folder.mkdir(parents=True,exist_ok=True)
            full=route in FULL;b=template(camera,ui,full)
            p=folder/'current.record552';p.write_bytes(b)
            photo=folder/'photos.json';photo.write_bytes((LOCAL/'inputs'/unit/'photos.json').read_bytes())
            seeds=[str(p)]
            if route in ('scene_shared_structure','scene_structure','scene_weighted'):
                packed=parameters_of(b);packed.update({k:seed[k] for k in ('curve_y_u8','matrix_q10')})
                if not full:
                    shared=shared_structure(camera,seed)
                    packed.update(curve_y_u8=shared['shared_curve_y_u8'],matrix_q10=shared['shared_matrix_q10'])
                    dump(root/'look-structure.json',shared)
                shaped=C.codec.encode(b,packed,level=int(full),gray=film['family']=='bw',look_unit_mask=None if full else 1<<ui)
                sp=folder/'seed-structure.record552';sp.write_bytes(shaped);seeds.append(str(sp))
            parents={
                'scene_rgb':('scene_shared',),
                'scene_shared_matrix':(),
                'scene_rgb_matrix':('scene_shared_matrix',),
                'scene_weighted':('scene_structure',),
            }.get(route,())
            for parent in parents:
                seeds.append(str(LOCAL/'fits'/unit/f'{film["indices"][parent]:02d}/exact.record552'))
            selected_groups=dict(groups)
            if route=='jpeg_control':selected_groups['train']=str(root/'train_jpeg.npz')
            if route=='scene_weighted':selected_groups['train']=str(root/'train_weighted.npz')
            doc=dict(unit=unit,index=index,ui=ui,name=film['name'],kind='builtin' if full else 'look',
                level=int(full),route=route,film_ordinal=ordinal,current_record=str(p),current_sha256=sha(p),
                groups=selected_groups,seeds=seeds,source_groups=meta['source_groups'],
                additional_gate_reference=None,absent_from_g156=True,restore_from_g154=False,
                target_definition_sha256=film['scene']['sha256'],c040_geometry='native',
                target=film,structure_file=str(root/'structure.json'),
                canonical_full_slot=6 if full else None,canonical_Look_base=5 if not full else None,
                source_slot_not_installation_authorization=True)
            dump(folder/'profile.json',doc)
        print('FILM PREPARED',ordinal,film['name'],unit,flush=True)
    dump(LOCAL/'films'/f'{ordinal:02d}/prepared.json',dict(ordinal=ordinal,film=film['name'],routes=ROUTES,complete=True))


def matrix_classes(fast,reference,structured):
    """Keep only C100 extra coefficients, with no C120, offsets, C004 or RLUT."""
    source=Path(reference.__file__)
    tree=ast.parse(source.read_text())
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Problem')
    init=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    class Shared(ast.NodeTransformer):
        def visit_Compare(self,n):
            n=self.generic_visit(n)
            if ast.unparse(n)=='self.level == 0':
                return ast.parse("self.level == 0 or config.get('shared_curves', False)",mode='eval').body
            return n
    init=Shared().visit(copy.deepcopy(init))
    def patched(base):
        ns=dict(base.__globals__)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[init],type_ignores=[])),str(source),'exec'),ns)
        return ns['__init__']
    fast._initialize=patched(fast._initialize)
    ref_init=patched(reference.Problem.__init__)
    def add(self,key,*args):
        if key not in ('gains','offsets','tint'):reference.Problem.add(self,key,*args)
    def finish(self):
        sl=self.blocks['matrix']
        if not self.bw:
            for j,base in enumerate(self.c.row.coef[1:].ravel()):
                self.lower[sl.start+1+j]=max(-.8,(-1279-float(base))/1024)
                self.upper[sl.start+1+j]=min(.8,(1279-float(base))/1024)
        if structured:
            q=np.asarray(structured['curve_y_u8'],float)
            if self.nc==1:q=np.asarray(structured.get('shared_curve_y_u8',q[1:2]),float)
            center=self.theta0.copy();center[self.qstart:self.qend]=(q-self.c.curve.ys).ravel()
            mat=np.asarray(structured.get('shared_matrix_q10',structured['matrix_q10']) if self.nc==1 else structured['matrix_q10'],float)
            center[:2]=(mat[0,[0,2]]-self.c.row.coef[0,[0,2]])/1024
            ex=[float((mat[0].sum()-self.c.row.coef[0].sum())/1024)]
            if not self.bw:ex.extend(((mat[1:]-self.c.row.coef[1:])/1024).ravel())
            center[sl]=ex
            self.theta0=np.clip(center,np.asarray(self.lower)+1e-9,np.asarray(self.upper)-1e-9)
            # A weak, explicit neutral-response prior; no photo or holdout enters it.
            anchor=np.zeros((self.qend-self.qstart,self.np))
            anchor[:,self.qstart:self.qend]=np.eye(self.qend-self.qstart)*.04
            self.R=np.vstack([self.R,anchor])
    def config(cfg):
        return dict(cfg,shared_curves=cfg.get('shared_curves',cfg['level']==0),level=3,
            only_extra_C100=True,structured_surrogate=structured is not None,
            frozen_current_C100_chroma_and_centers=False)
    def ri(self,camera,x,target,sw,cfg):ref_init(self,camera,x,target,sw,config(cfg));finish(self)
    def fi(self,camera,x,target,sw,cfg):fast.Problem.__init__(self,camera,x,target,sw,config(cfg));finish(self)
    return (type('FilmMatrixFast',(fast.Problem,),dict(__init__=fi,add=add)),
            type('FilmMatrixReference',(reference.Problem,),dict(__init__=ri,add=add)))


def fit(ordinal,unit,route,phase,nfev):
    film=CATALOG['films'][ordinal];index=film['indices'][route]
    F=C.load_fit();old_helpers=F.helpers
    profile_path=LOCAL/'targets'/unit/f'{index:02d}/profile.json'
    original_read=F.read
    def resolve_read(path):
        value=original_read(path)
        if Path(path)==profile_path:
            if phase=='exact':
                value=dict(value,seeds=original_read(LOCAL/'fits'/unit/f'{index:02d}/iterate.json')['meta']['seeds'])
            else:
                seeds=[]
                for seed in value['seeds']:
                    p=Path(seed)
                    if not p.exists() and p.name=='exact.record552':p=p.with_name('iterate.record552')
                    assert p.exists(),str(p)
                    seeds.append(str(p))
                value=dict(value,seeds=seeds)
        return value
    F.read=resolve_read
    seed_name='look-structure.json' if route=='scene_shared_structure' else 'structure.json'
    struct_seed=read(LOCAL/'films'/f'{ordinal:02d}'/unit/seed_name) if route in ('scene_shared_structure','scene_structure','scene_weighted') else None
    def helpers(camera):
        fast,reference,guard,quality,H,G=old_helpers(camera)
        if route in MATRIX:
            PF,PR=matrix_classes(fast,reference,struct_seed)
            fast=types.SimpleNamespace(Problem=PF);reference=types.SimpleNamespace(Problem=PR)
            oldseed=H['seed']
            def seed(P,b):
                p=oldseed(P,b);row=rt.mm.MatrixRow.from_bytes(b[216:244]);sl=P.blocks['matrix']
                ex=[float((row.coef[0].sum()-P.c.row.coef[0].sum())/1024)]
                if not P.bw:ex.extend(((row.coef[1:]-P.c.row.coef[1:])/1024).ravel())
                p[sl]=ex;return p
            H['seed']=seed
        return fast,reference,guard,quality,H,G
    F.helpers=helpers
    F.encode=lambda entry,P,theta,ui,kind:C.codec.encode(entry,rt.plain(P.packed(theta)),
        level=int(P.nc==3),gray=P.bw,look_unit_mask=1<<ui if kind=='look' else None)
    F.run(unit,index,phase,nfev)


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','iterate','exact'))
    p.add_argument('--film',type=int,required=True);p.add_argument('--unit',choices=UNITS)
    p.add_argument('--route',choices=ROUTES);p.add_argument('--nfev',type=int,default=240)
    args=p.parse_args()
    if args.stage=='prepare':return prepare(args.film)
    assert args.unit and args.route
    fit(args.film,args.unit,args.route,args.stage,args.nfev)


if __name__=='__main__':main()
