"""Read-only probe2 field measurements; derivatives stay in a fresh local tree."""
import os
import sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAP=ROOT/'captures/probe2-field-20261103'
OUT=HERE/'local/field_probe2_20261103'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe2-field-20261103')
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key]='1'
os.environ.update(TMPDIR=str(TMP),MPLCONFIGDIR=str(TMP/'mpl'))
import argparse
import ast
import csv
import datetime
import fcntl
import hashlib
import importlib.util
import json
import math
import plistlib
import signal
import subprocess
import time
volume=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
assert volume['VolumeUUID'].upper()=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert volume['FilesystemType']=='apfs' and volume['WritableVolume']
OUT.mkdir(parents=True,exist_ok=True);TMP.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(HERE.parent/'probe_pack_r1'))
import field_20261103 as f
f.OUT,f.TMP=OUT,TMP
os.environ.update(TMPDIR=str(TMP),MPLCONFIGDIR=str(TMP/'mpl'))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy import ndimage,optimize,interpolate,stats


def finite(value):
    value=f.plain(value)
    if isinstance(value,dict):return {k:finite(v) for k,v in value.items()}
    if isinstance(value,list):return [finite(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def dump(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(finite(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def read(name):return json.loads((OUT/name).read_text())


def audit(event,args):
    if event in ('subprocess.Popen','socket.connect','socket.bind','socket.getaddrinfo'):
        raise PermissionError('No network or subprocess during field analysis')
    if event=='open' and isinstance(args[0],(str,bytes,Path)):
        p=Path(os.fsdecode(args[0])).resolve()
        if str(p).startswith('/Volumes/') and not (p.is_relative_to(ROOT) or p.is_relative_to(TMP)):
            raise PermissionError('Unrelated volume: '+str(p))
        mode,flags=args[1:3]
        write=isinstance(mode,str) and any(k in mode for k in 'wax+')
        write|=isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if write and not (p.is_relative_to(OUT) or p.is_relative_to(TMP)):
            raise PermissionError('Write outside field local/Scratch: '+str(p))
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.utime','os.chmod'):
        for value in args[:2] if event in ('os.rename','os.link','os.symlink') else args[:1]:
            if isinstance(value,(str,bytes,Path)):
                p=Path(os.fsdecode(value)).resolve()
                if not (p.is_relative_to(OUT) or p.is_relative_to(TMP)):
                    raise PermissionError('Mutation outside field local/Scratch: '+str(p))


def layout(phase):return json.loads((HERE/'local/page'/('layout-'+phase+'.json')).read_text())


def inventory():
    rows=[];inputs=[]
    names={f'R805{n}.{suffix}' for n in range(1934,1955) for suffix in ('DNG','JPG')}
    for line in (CAP/'SHA256SUMS').read_text().splitlines():
        wanted,name=line.split(None,1);name=name.lstrip('*')
        assert name in names and f.sha(CAP/name)==wanted,name
        inputs.append(dict(file=str((CAP/name).relative_to(ROOT)),sha256=wanted,bytes=(CAP/name).stat().st_size))
    assert len(inputs)==42 and {Path(r['file']).name for r in inputs}==names
    dump('inputs.json',dict(files=inputs,manifest_sha256=f.sha(CAP/'SHA256SUMS')))
    for n in range(1934,1955):
        stem=f'R805{n}'
        d=f.metadata(f.Tiff((CAP/(stem+'.DNG')).read_bytes()));j=f.metadata(f.jpeg_tiff(CAP/(stem+'.JPG')))
        for key in ('time','iso','exposure_s','selector','sliders_raw','wb_shotinfo'):
            assert d[key]==j[key],(stem,key)
        with Image.open(CAP/(stem+'.JPG')) as im:
            rows.append(dict(frame=stem,dng=d,jpeg=j,jpeg_wh=list(im.size),quantization=im.quantization))
        print(stem,d['time'],d['exposure_s'],d['iso'],d['selector_name'],d['sliders_display'],flush=True)
    dump('metadata.json',rows)
    protected=[HERE/'REPORT_PROBE2.md',HERE/'ramp2.html',HERE/'OWNER_STEPS_PROBE2.md',HERE/'local/page/layout-p1.json',HERE/'local/page/layout-p2.json',
        HERE.parent/'probe_pack_r1/FIELD_20261103_RAMP.md',HERE.parent/'probe_pack_r1/ramp_field_20261103.py',
        HERE.parent/'probe_pack_r1/field_20261103.py',ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT']
    dump('protected.json',{str(p.relative_to(ROOT)):f.sha(p) for p in protected})
    dump('environment.json',dict(python=sys.executable,numpy=np.__version__,nice=os.getpriority(os.PRIO_PROCESS,0),
        numerical_threads=1,max_compute_processes=2,network=False,card_or_camera_access=False))


def project(H,xy):
    xy=np.asarray(xy,float);a=np.c_[xy.reshape(-1,2),np.ones(xy.size//2)]@H.T
    return (a[:,:2]/a[:,2:]).reshape(xy.shape)


def homography(source,target):
    A=[];b=[]
    for (x,y),(u,v) in zip(source,target):
        A.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]]);b.extend([u,v])
    return np.r_[np.linalg.lstsq(A,b,rcond=None)[0],1].reshape(3,3)


def dock_boundary(small):
    h,w=small.shape[:2];sat=np.max(small,axis=2)-np.min(small,axis=2)
    edge=np.r_[np.arange(int(w*.075)),np.arange(int(w*.925),w)]
    score=np.mean((sat[:,edge]>40)&(small[:,edge].mean(2)>55),axis=1)
    score=ndimage.uniform_filter1d(score,size=7)
    ys=np.where((np.arange(h)>h*.55)&(score>.16))[0]
    return int(ys[0]-5) if len(ys) else h


def marker_pattern(marker,blur=.45):
    pattern=np.zeros((90,90),float);pattern[:10]=pattern[-10:]=1;pattern[:,:10]=pattern[:,-10:]=1
    for iy,row in enumerate(marker['bits']):
        for ix,bit in enumerate(row):pattern[(iy+2)*10:(iy+3)*10,(ix+2)*10:(ix+3)*10]=int(bit)
    return ndimage.gaussian_filter(pattern,blur*10)


def edge_points(gray,H,patches,dock,parity=None,span=9):
    hh,ww=gray.shape;found=[]
    for p,patch in enumerate(patches[:49]):
        if parity is not None and p%2!=parity:continue
        r=patch['swatch'];x,y,w,h=(r[k] for k in ('x','y','w','h'))
        for side in range(4):
            for q in (.25,.5,.75):
                point=np.array(([x+w*q,y],[x+w*q,y+h],[x,y+h*q],[x+w,y+h*q])[side])
                normal=np.array(([0,1],[0,-1],[1,0],[-1,0])[side],float)
                uv=project(H,[point])[0]*[ww,hh]
                if not (span+2<uv[0]<ww-span-2 and span+2<uv[1]<min(dock-5,hh-span-2)):continue
                dv=project(H,[point+normal*.001])[0]*[ww,hh]-uv;dv/=np.linalg.norm(dv)
                tt=np.linspace(-span,span,span*16+1);pp=uv+tt[:,None]*dv
                values=ndimage.map_coordinates(gray,[pp[:,1],pp[:,0]],order=1)
                gradient=np.gradient(ndimage.gaussian_filter1d(values,3),tt);k=int(np.argmax(gradient))
                found.append(dict(patch=p,side=side,source=point,target=pp[k]/[ww,hh],offset=float(tt[k]),gradient=float(gradient[k])))
    return found


def locate(rgb,stem):
    lay=layout('p1');ww=1000;hh=round(rgb.shape[0]*ww/rgb.shape[1])
    small=np.asarray(Image.fromarray(rgb).resize((ww,hh),Image.Resampling.BOX),float);gray=small.mean(2)
    dock=dock_boundary(small)
    lab,_=ndimage.label(gray>125);candidates=[]
    patterns={m['corner']:marker_pattern(m) for m in lay['markers']}
    aa=np.linspace(.3,8.7,31);gx,gy=np.meshgrid(aa,aa)
    for sl in ndimage.find_objects(lab):
        yy,xx=sl;w,h=xx.stop-xx.start,yy.stop-yy.start
        if not (15<w<75 and 13<h<75 and .55<h/w<1.5 and yy.stop<dock-2):continue
        if not (xx.start<ww*.35 or xx.start>ww*.65):continue
        actual=ndimage.map_coordinates(gray,[yy.start+gy.ravel()/9*h-.5,xx.start+gx.ravel()/9*w-.5],order=1)
        scores={corner:float(np.corrcoef(actual,ndimage.map_coordinates(pattern,[gy.ravel()*10-.5,gx.ravel()*10-.5],order=1))[0,1]) for corner,pattern in patterns.items()}
        if yy.start<hh*.4:vertical='T'
        elif yy.start>hh*.6:vertical='B'
        else:continue
        corner=vertical+('L' if xx.start<ww/2 else 'R')
        candidates.append(dict(corner=corner,box=[xx.start,yy.start,w,h],correlation=scores[corner],scores=scores))
    chosen=[]
    for m in lay['markers']:
        values=[c for c in candidates if c['corner']==m['corner']]
        if values:chosen.append((m,max(values,key=lambda c:c['box'][2]*c['box'][3])))
    assert len(chosen)>=2,(stem,'fewer than two coded markers',candidates,dock)
    source=np.array([[m['rect']['x']+m['rect']['w']/2,m['rect']['y']+m['rect']['h']/2] for m,_ in chosen])
    target=np.array([[(c['box'][0]+c['box'][2]/2)/ww,(c['box'][1]+c['box'][3]/2)/hh] for _,c in chosen])
    if len(chosen)>=4:H0=homography(source,target)
    elif len(chosen)==3:
        affine=np.linalg.lstsq(np.c_[source,np.ones(3)],target,rcond=None)[0].T;H0=np.r_[affine,[[0,0,1]]]
    else:
        src=[];dst=[]
        for m,c in chosen:
            r=m['rect'];x,y,w,h=c['box']
            src.extend([[r['x'],r['y']],[r['x']+r['w'],r['y']],[r['x']+r['w'],r['y']+r['h']],[r['x'],r['y']+r['h']]])
            dst.extend([[x/ww,y/hh],[(x+w)/ww,y/hh],[(x+w)/ww,(y+h)/hh],[x/ww,(y+h)/hh]])
        H0=homography(src,dst)
    models=[]
    for m,c in chosen:
        r=m['rect'];points=np.column_stack([r['x']+gx.ravel()/9*r['w'],r['y']+gy.ravel()/9*r['h']])
        expected=ndimage.map_coordinates(patterns[m['corner']],[gy.ravel()*10-.5,gx.ravel()*10-.5],order=1)
        models.append((points,expected))
    p0=H0.ravel()[:8]
    def residual(p):
        H=np.r_[p,1].reshape(3,3);values=[]
        for points,expected in models:
            uv=project(H,points)*[ww,hh]
            actual=ndimage.map_coordinates(gray,[uv[:,1]-.5,uv[:,0]-.5],order=1,mode='nearest')
            X=np.c_[np.ones(len(expected)),expected];coef=np.linalg.lstsq(X,actual,rcond=None)[0]
            values.extend((actual-X@coef)/max(coef[1],30))
        values.extend((p-p0)*.2)
        return np.asarray(values)
    span=np.array([.08,.08,.05,.08,.12,.05,.12,.12])
    fit=optimize.least_squares(residual,p0,bounds=(p0-span,p0+span),loss='soft_l1',f_scale=.15,max_nfev=180)
    H=np.r_[fit.x,1].reshape(3,3)
    # Even cells refine geometry; odd cells are held out from this refinement.
    edge_refinements=[]
    for iteration in range(2):
        edges=[v for v in edge_points(gray,H,lay['patches'],dock,parity=0) if v['gradient']>1.4 and abs(v['offset'])<8.5]
        if len(edges)<30:break
        src=np.array([v['source'] for v in edges]);dst=np.array([v['target'] for v in edges])
        initial=H.ravel()[:8]
        def er(p):
            pp=np.r_[p,1].reshape(3,3)
            return np.r_[((project(pp,src)-dst)*[ww,hh]).ravel(),((project(pp,source)-target)*[ww,hh]).ravel()*5]
        ef=optimize.least_squares(er,initial,loss='soft_l1',f_scale=1.2,max_nfev=60)
        H=np.r_[ef.x,1].reshape(3,3);edge_refinements.append(dict(points=len(edges),cost=ef.cost))
    held=[v for v in edge_points(gray,H,lay['patches'],dock,parity=1) if v['gradient']>1.4]
    markers=[]
    for m in lay['markers']:
        r=m['rect'];tx,ty=np.meshgrid(np.linspace(0,1,25),np.linspace(0,1,25))
        points=np.c_[r['x']+tx.ravel()*r['w'],r['y']+ty.ravel()*r['h']];uv=project(H,points)*[ww,hh]
        visible=(uv[:,0]>=0)&(uv[:,0]<ww)&(uv[:,1]>=0)&(uv[:,1]<min(hh,dock))
        picked=next((c for mm,c in chosen if mm['corner']==m['corner']),None)
        a=np.linspace(.3,8.7,31);xx,yy=np.meshgrid(a,a)
        points=np.c_[r['x']+xx.ravel()/9*r['w'],r['y']+yy.ravel()/9*r['h']];uv=project(H,points)*[ww,hh]
        ok=(uv[:,0]>0)&(uv[:,0]<ww)&(uv[:,1]>0)&(uv[:,1]<min(hh,dock))
        correlation=None
        if np.sum(ok)>100:
            actual=ndimage.map_coordinates(gray,[uv[ok,1],uv[ok,0]],order=1)
            expect=ndimage.map_coordinates(patterns[m['corner']],[yy.ravel()[ok]*10-.5,xx.ravel()[ok]*10-.5],order=1)
            correlation=float(np.corrcoef(actual,expect)[0,1])
        markers.append(dict(corner=m['corner'],used_for_marker_fit=picked is not None,seed=picked,
            visible_fraction=float(np.mean(visible)),correlation=correlation,
            state='full' if picked else ('partial' if np.mean(visible)>.02 else 'missing_or_occluded')))
    errors=np.array([abs(v['offset']) for v in held])
    return H,dict(markers=markers,marker_count_used=len(chosen),refined_H=H,seed_H=H0,dock_y_fraction=dock/hh,
        template_fit_nfev=fit.nfev,edge_refinements=edge_refinements,heldout_edge_count=len(held),
        heldout_edge_abs_median=float(np.median(errors)),heldout_edge_abs_95=float(np.percentile(errors,95)),
        heldout_edges=held,candidates=candidates)


def geometry():
    sheet=Image.new('RGB',(1800,7*335),'#eeeeee');draw=ImageDraw.Draw(sheet)
    lay=layout('p1')
    for i,n in enumerate(range(1934,1955)):
        stem=f'R805{n}';rgb=np.asarray(Image.open(CAP/(stem+'.JPG')).convert('RGB'))
        H,loc=locate(rgb,stem);dump('geometry/'+stem+'.json',loc)
        view=Image.fromarray(rgb);view.thumbnail((600,300));d=ImageDraw.Draw(view)
        for patch in lay['patches']:
            r=patch['swatch'];poly=project(H,[[r['x'],r['y']],[r['x']+r['w'],r['y']],[r['x']+r['w'],r['y']+r['h']],[r['x'],r['y']+r['h']]])*view.size
            bad=np.max(poly[:,1])>=loc['dock_y_fraction']*view.height or np.min(poly)<0
            d.line([tuple(v) for v in np.vstack([poly,poly[:1]])],fill='#ff4444' if bad else '#ffff00',width=1)
        for m in lay['markers']:
            r=m['rect'];poly=project(H,[[r['x'],r['y']],[r['x']+r['w'],r['y']],[r['x']+r['w'],r['y']+r['h']],[r['x'],r['y']+r['h']]])*view.size
            d.line([tuple(v) for v in np.vstack([poly,poly[:1]])],fill='#ff00ff',width=1)
        yy=loc['dock_y_fraction']*view.height;d.line([(0,yy),(view.width,yy)],fill='#ff0000',width=1)
        view.save(OUT/(stem+'-roi.jpg'),quality=94)
        x,y=(i%3)*600,(i//3)*335;sheet.paste(view,(x,y+25));draw.text((x+6,y+5),stem,fill='black')
        print(stem,'markers',loc['marker_count_used'],'edge median/95',round(loc['heldout_edge_abs_median'],2),round(loc['heldout_edge_abs_95'],2),'dock',round(loc['dock_y_fraction'],3),flush=True)
    sheet.save(OUT/'roi-contact.jpg',quality=94)


_tree=ast.parse((HERE.parent/'probe_pack_r1/ramp_field_20261103.py').read_text())
_node=next(n for n in _tree.body if isinstance(n,ast.FunctionDef) and n.name=='sample_patch')
exec(compile(ast.Module(body=[_node],type_ignores=[]),'sealed-raw-roi-sampler','exec'),globals())


def choose_phase(patches):
    ii=[i for i,v in enumerate(patches[:49]) if v['valid']]
    rr=np.array([patches[i]['raw_wb'] for i in ii]);scores={}
    for phase in ('p1','p2'):
        lp=layout(phase)['patches'];codes=np.array([lp[i]['rgb'][0] for i in ii],float)/255
        light=np.where(codes<=.04045,codes/12.92,((codes+.055)/1.055)**2.4)
        xy=np.array([[lp[i]['swatch']['x'],lp[i]['swatch']['y']] for i in ii])
        x,y=xy.T;z=np.c_[np.ones(len(ii)),x,y,x*x,y*y,x*y]
        loggain=np.log(rr.mean(1))-np.log(light);coef=np.linalg.lstsq(z,loggain,rcond=None)[0]
        scores[phase]=dict(log_light_rmse=float(np.sqrt(np.mean((loggain-z@coef)**2))),
            spearman=float(stats.spearmanr(codes,rr.mean(1)).statistic))
    return min(scores,key=lambda k:scores[k]['log_light_rmse']),scores


def extract():
    for meta in read('metadata.json'):
        stem=meta['frame'];loc=read('geometry/'+stem+'.json');H=np.array(loc['refined_H'])
        raw,info=f.decode_raw(f.Tiff((CAP/(stem+'.DNG')).read_bytes()))
        rgb=np.asarray(Image.open(CAP/(stem+'.JPG')).convert('RGB'))
        with Image.open(CAP/(stem+'.JPG')) as im:
            im.draft('YCbCr',im.size);assert im.mode=='YCbCr';ycc=np.asarray(im)
        assert raw.shape==rgb.shape[:2]==ycc.shape[:2]
        lay=layout('p1');sets={};visible=[]
        for fraction in (.35,.5,.65):
            patches=[]
            for p,patch in enumerate(lay['patches']):
                r=patch['swatch'];x=r['x']+r['w']*(1-fraction)/2;y=r['y']+r['h']*(1-fraction)/2
                points=project(H,[[x,y],[x+r['w']*fraction,y],[x+r['w']*fraction,y+r['h']*fraction],[x,y+r['h']*fraction]])
                valid=bool(np.all(points>=.001) and np.all(points<.999) and np.max(points[:,1])<loc['dock_y_fraction']-.008)
                if not valid:patches.append(dict(id=patch['id'],valid=False,reason='outside photograph or below visible chart/Dock boundary'));continue
                item=sample_patch(rgb,ycc,raw,info,H,patch,fraction,meta['dng']['as_shot_neutral']);item['valid']=True
                patches.append(item)
            sets[str(fraction)]=patches
        # Phase is inferred by the relation between known screen codes and RAW.
        phase,phase_scores=choose_phase(sets['0.5']);lay=layout(phase)
        for patches in sets.values():
            for p,patch in enumerate(patches):patch['screen_rgb']=lay['patches'][p]['rgb']
        dump('frames/'+stem+'.json',dict(frame=stem,raw=info,location=loc,phase=phase,phase_scores=phase_scores,patches=sets))
        values=np.array([p['raw_wb'] for p in sets['0.5'][:49] if p['valid']])
        print(stem,phase,'phase scores',phase_scores,'valid',sum(p['valid'] for p in sets['0.5']),
            'RAW',np.round(values.min(0),1),np.round(values.max(0),1),flush=True)


def phase():
    for n in range(1934,1955):
        name=f'frames/R805{n}.json';frame=read(name)
        selected,scores=choose_phase(frame['patches']['0.5']);lp=layout(selected)['patches']
        frame['phase']=selected;frame['phase_scores']=scores
        for rows in frame['patches'].values():
            for i,row in enumerate(rows):row['screen_rgb']=lp[i]['rgb']
        dump(name,frame);print(frame['frame'],selected,scores,flush=True)


def extract_verify():
    before={p.name:f.sha(p) for p in (OUT/'frames').glob('*.json')};assert len(before)==21
    extract()
    changed=[name for name,wanted in before.items() if f.sha(OUT/'frames'/name)!=wanted]
    dump('extraction-rerun.json',dict(frames=21,changed=changed,all_bytes_equal=not changed,final_phase_method=True))
    assert not changed,changed


class ProbeModel(f.FieldModel):
    def __init__(self):
        super().__init__()
        fmt=f.load_module('probe2_field_dat_format','research/v39_g153/dat_format.py')
        path=ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT'
        self.inputs[str(path.relative_to(ROOT))]=f.sha(path)
        raw=path.read_bytes();self.entries2={key:fmt.expand_effect(raw,8+i) for i,key in enumerate(('A','RN','GN','BN','RD','GD','BD'))}
        assert self.entries2['A']==self.entries['A']
        for key,e in self.entries2.items():
            self.curves[key]=np.asarray([list(e[379:412]),list(e[82:115]),list(e[412:445])],float)
    def single(self,x,c,node,delta=2):
        curve=self.curves['A'][c].copy();curve[node]+=delta
        return np.interp(x,self.xs,curve)-np.interp(x,self.xs,self.curves['A'][c])


def arrays(fraction):
    meta=read('metadata.json');frames=[read('frames/'+m['frame']+'.json') for m in meta]
    shape=(len(frames),52,3);j=np.full(shape,np.nan);r=j.copy();yc=j.copy();wb=j.copy();valid=np.zeros(shape[:2],bool);clip=np.ones(shape[:2],bool)
    for i,frame in enumerate(frames):
        for p,item in enumerate(frame['patches'][fraction]):
            if not item['valid']:continue
            j[i,p]=item['jpeg_mean'];r[i,p]=item['raw_dn_mean'];yc[i,p]=item['native_ycc_mean'];wb[i,p]=item['raw_wb'];valid[i,p]=True
            clip[i,p]=max(item['raw_clip_fraction'])>0 or max(item['jpeg_clip_fraction'])>.001
    clock=np.array([datetime.datetime.strptime(m['dng']['time'],'%Y:%m:%d %H:%M:%S').timestamp() for m in meta]);clock-=clock[0]
    return meta,frames,j,r,yc,wb,valid,clip,clock


def centered_fit(v,b,x,mask,affine=True):
    rr=[];bb=[];background=[]
    for c in range(3):
        z=np.c_[np.ones(np.sum(mask)),x[mask,c]/1000] if affine else np.ones((np.sum(mask),1))
        vc=v[mask,c];bc=b[mask,c]
        cv=np.linalg.lstsq(z,vc,rcond=None)[0];cb=np.linalg.lstsq(z,bc,rcond=None)[0]
        rr.append(vc-z@cv);bb.append(bc-z@cb);background.append(cv)
    obs=np.array(rr).T;basis=np.array(bb).T
    norm=float(np.sum(basis*basis));alpha=float(np.sum(obs*basis)/norm) if norm>1e-6 else 0
    bounded=float(np.clip(alpha,0,3));res=obs-bounded*basis
    rmse=float(np.sqrt(np.mean(res*res)));null=float(np.sqrt(np.mean(obs*obs)))
    perpoint=np.sum(basis*basis,axis=1)
    return dict(amplitude=alpha,amplitude_used=bounded,rmse=rmse,null_rmse=null,
        improvement=float(np.sum(obs*obs)-np.sum(res*res)),basis_norm=norm,gray_points=int(np.sum(mask)),
        active_points=int(np.sum(perpoint>.05)),background=background)


def identify():
    model=ProbeModel();meta=read('metadata.json')
    dump('model.json',dict(inputs=model.inputs,xs=model.xs,curves=model.curves,row=model.row.describe(),
        Y_coeff=model.row.coef[0]/1024,scope='Existing transferred model; conditional A inverse axis, not direct ISP state'))
    for fraction in ('0.35','0.5','0.65'):
        meta,frames,j,r,yc,wb,valid,clip,clock=arrays(fraction);results=[]
        for phase in ('p1','p2'):
            inds=np.array([i for i,v in enumerate(frames) if v['phase']==phase]);jj=j[inds].copy();rr=r[inds].copy()
            for a in (jj,rr):
                med=np.nanmedian(a,axis=0);missing=~np.isfinite(a);a[missing]=np.broadcast_to(med,a.shape)[missing]
            inverses=[model.inverse(v) for v in jj];xx=np.array([v[0] for v in inverses]);pre=np.array([v[1] for v in inverses])
            gain=np.nanmedian(np.where(valid[inds,:,None],xx/rr,np.nan),axis=0)
            baseline=np.array([model.pre(gain*v) for v in rr]);feature=pre-baseline
            common=np.nanmedian(np.where(valid[inds,:,None],feature,np.nan),axis=0);feature-=common
            for ii,index in enumerate(inds):
                x=gain*rr[ii];mask=valid[index].copy();mask[49:]=False
                fits={}
                for key in ('RN','GN','BN','RD','GD','BD'):
                    b=model.pre(x,key)-model.pre(x)
                    fits[key]=centered_fit(feature[ii],b,x,mask)
                    fits[key]['constant_background']=centered_fit(feature[ii],b,x,mask,False)
                order=sorted(fits,key=lambda k:fits[k]['improvement'],reverse=True);best=order[0];a=fits[best]['amplitude']
                provisional=best if a>.35 and fits[best]['improvement']>2 else ('A' if max(v['amplitude_used'] for v in fits.values())<.35 else 'unknown')
                results.append(dict(frame=meta[index]['frame'],index=int(index),phase=phase,provisional=provisional,
                    best_template=best,second_template=order[1],fits=fits,feature=feature[ii],input=x,
                    common_feature=common,median_A_input_gain=gain,plan_not_used=True))
        results.sort(key=lambda v:v['index']);dump('identity-'+fraction+'.json',dict(frames=results,
            method='Median-centered per-patch inverse-JPG minus RAW-predicted baseline; affine brightness nuisance per channel; six signed templates, no order/count constraint.'))
        print('ROI',fraction,flush=True)
        for row in results:
            print(row['frame'],row['phase'],row['provisional'],{k:round(v['amplitude'],2) for k,v in row['fits'].items()},
                'rmse',round(row['fits'][row['best_template']]['rmse'],3),'gain',round(row['fits'][row['best_template']]['improvement'],2),flush=True)


def classify():
    variants={fraction:read('identity-'+fraction+'.json')['frames'] for fraction in ('0.35','0.5','0.65')};rows=[]
    for i in range(21):
        primary=variants['0.5'][i];samples=[v[i] for v in variants.values()]
        proposed={r['provisional'] for r in samples}
        quality_bad=any(r['fits'][r['best_template']]['rmse']>.6 or r['fits'][r['best_template']]['amplitude']>3 for r in samples)
        label=next(iter(proposed)) if len(proposed)==1 and not quality_bad else 'unknown'
        loc=read('geometry/'+primary['frame']+'.json')
        confidence='unknown' if label=='unknown' else ('medium' if loc['heldout_edge_abs_95']>6 else 'high')
        rows.append(dict(frame=primary['frame'],index=i,phase=primary['phase'],label=label,confidence=confidence,
            all_ROI_labels=sorted(proposed),ROI_amplitudes={fraction:{key:v[i]['fits'][key]['amplitude'] for key in ('RN','GN','BN','RD','GD','BD')} for fraction,v in variants.items()},
            best_template=primary['best_template'],best_amplitude=primary['fits'][primary['best_template']]['amplitude'],
            feature_rmse=primary['fits'][primary['best_template']]['rmse'],fits=primary['fits'],
            marker_count=loc['marker_count_used'],marker_states={r['corner']:r['state'] for r in loc['markers']},
            heldout_edge_median=loc['heldout_edge_abs_median'],heldout_edge_95=loc['heldout_edge_abs_95'],
            reason='ROI/template residual exceeds known probe range; no order used' if label=='unknown' else 'Signed local curve response agrees in all three ROIs; all six templates tested'))
    dump('assignments.json',dict(frames=rows,no_order_or_count_prior=True,known_candidates=['A','RN','GN','BN','RD','GD','BD'],
        confidence_scope='Within these candidates; baseline-compatible A is not proof of a literal menu name or DAT hash.'))
    for row in rows:print(row['frame'],row['phase'],row['label'],row['confidence'],round(row['best_amplitude'],3),flush=True)


def ycc_codes(model,rgb):
    y,c=model.mm.ycbcr(np.asarray(rgb));return np.stack([y,c.real+128,c.imag+128],axis=-1)


def reference_for(i,p,anchors,clock,valid,nearest=False):
    usable=[k for k in anchors if valid[k,p]]
    assert usable,(i,p,'no valid A reference')
    if nearest:
        k=min(usable,key=lambda k:abs(clock[k]-clock[i]));return k,k,0.
    before=[k for k in usable if clock[k]<=clock[i]];after=[k for k in usable if clock[k]>=clock[i]]
    a=max(before,key=lambda k:clock[k]) if before else min(usable,key=lambda k:clock[k])
    b=min(after,key=lambda k:clock[k]) if after else max(usable,key=lambda k:clock[k])
    alpha=0. if a==b else float((clock[i]-clock[a])/(clock[b]-clock[a]))
    return a,b,alpha


def measure():
    assignment=read('assignments.json')['frames'];labels=[r['label'] for r in assignment];model=ProbeModel()
    for fraction in ('0.35','0.5','0.65'):
        meta,frames,j,r,yc,wb,valid,clip,clock=arrays(fraction)
        jj=j.copy()
        for phase_name in ('p1','p2'):
            inds=np.array([i for i,v in enumerate(frames) if v['phase']==phase_name]);sub=jj[inds]
            median=np.nanmedian(sub,axis=0);bad=~np.isfinite(sub);sub[bad]=np.broadcast_to(median,sub.shape)[bad];jj[inds]=sub
        inv=[model.inverse(v) for v in jj];xx=np.array([v[0] for v in inv]);pre=np.array([v[1] for v in inv])
        points=[];controls=[]
        for i,row in enumerate(meta):
            key=labels[i]
            if key in ('unknown','A'):continue
            c='RGB'.index(key[0]);phase_name=frames[i]['phase'];anchors=[k for k in range(21) if frames[k]['phase']==phase_name and labels[k]=='A']
            for p in range(52):
                if not valid[i,p]:continue
                a,b,alpha=reference_for(i,p,anchors,clock,valid)
                gain=(1-alpha)*xx[a,p]/r[a,p]+alpha*xx[b,p]/r[b,p]
                xB=gain*r[i,p];preB=model.pre(xB[None])[0];base=model.predict(xB[None])[0]
                offset=(1-alpha)*(yc[a,p]-ycc_codes(model,j[a,p]))+alpha*(yc[b,p]-ycc_codes(model,j[b,p]))
                expected_ycc=ycc_codes(model,base)+offset
                expected_ycc[0]=(1-alpha)*yc[a,p,0]+alpha*yc[b,p,0]+(preB-(1-alpha)*pre[a,p]-alpha*pre[b,p])@(model.row.coef[0]/1024)
                obs=j[i,p]-base;dycc=yc[i,p]-expected_ycc
                predicted=model.predict(xB[None],key)[0]-base
                predicted_ycc=ycc_codes(model,base+predicted)-ycc_codes(model,base)
                dp=np.zeros(3);dp[c]=.05
                jac=(model.forward_pre((preB+dp)[None])[0]-model.forward_pre((preB-dp)[None])[0])/.1
                q=float(jac@obs/(jac@jac))
                for iteration in range(2):
                    pp=preB.copy();pp[c]+=q;dq=np.zeros(3);dq[c]=.02
                    local_jac=(model.forward_pre((pp+dq)[None])[0]-model.forward_pre((pp-dq)[None])[0])/.04
                    residue=obs-(model.forward_pre(pp[None])[0]-base)
                    q+=float(local_jac@residue/(local_jac@local_jac))
                fitted=preB.copy();fitted[c]+=q;qres=obs-(model.forward_pre(fitted[None])[0]-base)
                na,nb,nalpha=reference_for(i,p,anchors,clock,valid,True)
                nx=xx[na,p]*r[i,p]/r[na,p];npre=model.pre(nx[None])[0];nbase=model.predict(nx[None])[0]
                nearest_ycc=ycc_codes(model,nbase)+yc[na,p]-ycc_codes(model,j[na,p])
                nearest_ycc[0]=yc[na,p,0]+(npre-pre[na,p])@(model.row.coef[0]/1024)
                nodes=[16] if key.endswith('N') else [8,19];delta=-2 if key.endswith('N') else 2
                nominal=float(model.pre(xB[None],key)[0,c]-preB[c]);item=frames[i]['patches'][fraction][p]
                points.append(dict(frame=row['frame'],index=i,label=key,phase=phase_name,channel=key[0],patch=item['id'],patch_index=p,gray=p<49,
                    fraction=fraction,valid=True,excluded=bool(clip[i,p]),screen_rgb=item['screen_rgb'],raw_wb=wb[i,p],
                    conditioned_input=float(xB[c]),x_B=xB,pre_B=preB,raw_target_mean=float(r[i,p,c]),raw_black=frames[i]['raw']['black'],
                    raw_sigma=item['raw_sd'][c],raw_histogram=item['raw_histograms'][c],
                    tile_raw_means=[t['raw_dn'][c] for t in item['tiles']],tile_weights=[t['pixels'] for t in item['tiles']],
                    q_y=float(dycc[0]/(model.row.coef[0,c]/1024)),q_rgb=q,q_nominal=nominal,
                    observed_rgb=obs,observed_ycc=dycc,predicted_rgb=predicted,predicted_ycc=predicted_ycc,q_projection_residual_rgb=qres,
                    nearest_observed_ycc=yc[i,p]-nearest_ycc,reference_frames=[meta[a]['frame'],meta[b]['frame']],reference_alpha=alpha,
                    input_nodes=nodes,delta=delta,node_contributions={str(node):float(model.single(np.array([xB[c]]),c,node,delta)[0]) for node in nodes},
                    raw_relative_to_A=100*(r[i,p]/((1-alpha)*r[a,p]+alpha*r[b,p])-1)))
        drifts=[]
        for phase_name in ('p1','p2'):
            anchors=[k for k in range(21) if frames[k]['phase']==phase_name and labels[k]=='A']
            for a,b in zip(anchors,anchors[1:]):
                mask=valid[a]&valid[b];xb=xx[a,mask]*r[b,mask]/r[a,mask]
                predicted=model.predict(xb);pb=model.pre(xb)
                expected=ycc_codes(model,predicted)+yc[a,mask]-ycc_codes(model,j[a,mask])
                expected[:,0]=yc[a,mask,0]+(pb-pre[a,mask])@(model.row.coef[0]/1024)
                drifts.append(dict(first=meta[a]['frame'],last=meta[b]['frame'],phase=phase_name,elapsed_s=clock[b]-clock[a],
                    patch_indices=np.where(mask)[0],raw_percent=100*(r[b,mask]/r[a,mask]-1),direct_rgb=j[b,mask]-j[a,mask],
                    corrected_rgb=j[b,mask]-predicted,direct_ycc=yc[b,mask]-yc[a,mask],corrected_ycc=yc[b,mask]-expected))
        dump('measure-'+fraction+'.json',dict(points=points,drifts=drifts,
            axes='RAW_WB is independent sensor proxy. Conditioned input inverts response-identified A through the existing model.',
            references='Nearest bracketing identified A per page; unknown frames never serve as references. Nearest-A sensitivity saved.'))
        print('measured',fraction,'points',len(points),'excluded',sum(v['excluded'] for v in points),flush=True)


SHAPES=('linear_tent','raised_cosine','pchip_difference','nearest_node','previous_node','linear_floor','linear_round')


def kernel_bases(rows,model,node,branch):
    result={shape:[] for shape in SHAPES};left,peak,right=model.xs[node-1:node+2]
    for row in rows:
        c='RGB'.index(row['channel']);delta=row['delta']
        if branch=='mean':x=np.array([row['conditioned_input']]);weights=np.ones(1)
        elif branch=='tile_means':
            weights=np.array(row['tile_weights'],float);weights/=weights.sum()
            x=np.array(row['tile_raw_means'])*row['conditioned_input']/row['raw_target_mean']
        else:
            hist=row['raw_histogram'];weights=np.array(hist['counts'],float);weights/=weights.sum()
            x=(np.array(hist['dn'])-row['raw_black'])*row['conditioned_input']/row['raw_target_mean']
        tent=np.maximum(0,np.minimum((x-left)/(peak-left),(right-x)/(right-peak)))
        base=np.interp(x,model.xs,model.curves['A'][c]);bump=delta*tent
        values=dict(linear_tent=bump,raised_cosine=delta*.5*(1-np.cos(np.pi*tent)),
            nearest_node=delta*((x>=(left+peak)/2)&(x<(peak+right)/2)),previous_node=delta*((x>=peak)&(x<right)),
            linear_floor=np.floor(base+bump)-np.floor(base),linear_round=np.floor(base+bump+.5)-np.floor(base+.5),
            pchip_difference=interpolate.PchipInterpolator(model.xs,model.curves[row['label']][c])(x)-interpolate.PchipInterpolator(model.xs,model.curves['A'][c])(x))
        for name,value in values.items():result[name].append(float(value@weights))
    return {k:np.array(v) for k,v in result.items()}


def regression(b,y,mask=None):
    if mask is None:mask=np.ones(len(y),bool)
    x=np.c_[b,np.ones(len(b))];coef=np.linalg.lstsq(x[mask],y[mask],rcond=None)[0];pred=x@coef
    return dict(gain=float(coef[0]),offset=float(coef[1]),rmse=float(np.sqrt(np.mean((pred[mask]-y[mask])**2))),prediction=pred)


def free_kernel(x,y,model,node,kind='linear'):
    left,peak,right=model.xs[node-1:node+2];width=right-left
    lower=np.array([max(0,left-width),peak-(peak-left)*.9,peak+(right-peak)*.2,.05,-.75])
    upper=np.array([peak-(peak-left)*.2,peak+(right-peak)*.9,right+width,4.5,.75])
    def value(par):
        l,p,r,a,o=par;z=np.maximum(0,np.minimum((x-l)/max(p-l,.1),(r-x)/max(r-p,.1)))
        if kind=='cosine':z=(1-np.cos(np.pi*z))/2
        return a*z+o
    def residual(par):
        return np.r_[value(par)-y,max(par[0]+width*.02-par[1],0),max(par[1]+width*.02-par[2],0)]
    solutions=[]
    for seed in (peak-width*.1,peak,peak+width*.1):
        initial=np.clip([left,seed,right,2,0],lower+1e-5,upper-1e-5)
        solutions.append(optimize.least_squares(residual,initial,bounds=(lower,upper),max_nfev=180))
    sol=min(solutions,key=lambda s:np.sum(residual(s.x)**2));l,p,r,a,o=sol.x
    return dict(kind=kind,left=l,peak=p,right=r,amplitude=a,offset=o,FWHM=(r-l)/2,half_left=(l+p)/2,half_right=(p+r)/2,
        rmse=float(np.sqrt(np.mean((value(sol.x)-y)**2))),parameters=sol.x,
        near_parameter_bound=bool(np.any(np.minimum(sol.x-lower,upper-sol.x)/(upper-lower)<.01)))


def fit(primary=False):
    model=ProbeModel();allfits=[];free=[];coverage=[];components=[];repeatability=[];confirmation=[];color_rows=[]
    for fraction in ('0.35','0.5','0.65'):
        data=read('measure-'+fraction+'.json');points=data['points']
        if primary:points=[r for r in points if not (r['label'].endswith('N') and r['phase']!='p1')]
        for key in ('RN','GN','BN','RD','GD','BD'):
            ch=key[0];c='RGB'.index(ch);nodes=[16] if key.endswith('N') else [8,19]
            rows=[r for r in points if r['label']==key and r['gray'] and not r['excluded']]
            frames=sorted({r['frame'] for r in rows})
            for node in nodes:
                l,p,r=model.xs[node-1:node+2];window={8:(65,180),16:(450,900),19:(780,1280)}[node]
                near=np.array([window[0]<v['conditioned_input']<window[1] for v in rows])
                x=np.array([v['conditioned_input'] for v in rows]);active=np.array([abs(v['node_contributions'][str(node)])>.2 for v in rows])
                for branch in ('mean','tile_means','raw_histogram'):
                    bb=kernel_bases(rows,model,node,branch)
                    for response in ('q_y','q_rgb'):
                        y=np.array([v[response] for v in rows]);fits=[]
                        for shape,basis in bb.items():
                            fitted=regression(basis,y,near);cv=[]
                            for held in frames:
                                hold=np.array([v['frame']==held for v in rows]);train=near&~hold;test=near&hold
                                if train.sum()<3 or test.sum()<2:continue
                                trained=regression(basis,y,train)
                                cv.append(dict(frame=held,rmse=float(np.sqrt(np.mean((trained['prediction'][test]-y[test])**2)))))
                            fits.append(dict(shape=shape,gain=fitted['gain'],offset=fitted['offset'],rmse=fitted['rmse'],frame_holdouts=cv))
                        fits.sort(key=lambda v:v['rmse']);allfits.append(dict(fraction=fraction,label=key,channel=ch,node=node,branch=branch,response=response,
                            n=int(near.sum()),frames=frames,window=window,fits=fits))
                if near.sum()>=6:
                    sign=-1 if key.endswith('N') else 1
                    for response in ('q_y','q_rgb'):
                        for kind in (('linear','cosine') if fraction=='0.5' else ('linear',)):
                            ff=free_kernel(x[near],sign*np.array([v[response] for v in rows])[near],model,node,kind)
                            free.append(dict(fraction=fraction,label=key,channel=ch,node=node,response=response,**ff))
                if fraction!='0.5':continue
                first=[v for v in rows if v['frame']==frames[0]];xx=np.array([v['conditioned_input'] for v in first]);ss=np.sort(xx[(xx>l)&(xx<r)])
                ar=[v for v in rows if abs(v['node_contributions'][str(node)])>.2]
                coverage.append(dict(label=key,channel=ch,node=node,frames=frames,first_frame=frames[0],left_points=int(np.sum((xx>l)&(xx<p))),
                    right_points=int(np.sum((xx>p)&(xx<r))),nearest_peak=float(min(abs(xx-p))),max_gap=float(max(np.diff(np.r_[l,ss,r]))),
                    conditioned_range=[float(x.min()),float(x.max())],raw_wb_range=[min(v['raw_wb'][c] for v in rows),max(v['raw_wb'][c] for v in rows)],
                    active_raw_wb_range=[min(v['raw_wb'][c] for v in ar),max(v['raw_wb'][c] for v in ar)] if ar else None,
                    active_conditioned_range=[min(v['conditioned_input'] for v in ar),max(v['conditioned_input'] for v in ar)] if ar else None))
                for frame in frames+['pooled']:
                    rr=[v for v in rows if (frame=='pooled' or v['frame']==frame) and abs(v['node_contributions'][str(node)])>.2]
                    pred=np.array([v['predicted_ycc'] for v in rr]);obs=np.array([v['observed_ycc'] for v in rr]);gains=[];rms=[];nn=[]
                    for comp in range(3):
                        mask=abs(pred[:,comp])>.08;nn.append(int(mask.sum()))
                        gains.append(float(pred[mask,comp]@obs[mask,comp]/(pred[mask,comp]@pred[mask,comp])) if mask.any() else None)
                        rms.append(float(np.sqrt(np.mean((obs[mask,comp]-pred[mask,comp])**2))) if mask.any() else None)
                    components.append(dict(label=key,node=node,frame=frame,n=len(rr),component_n=nn,gain_Y_Cb_Cr=gains,original_rmse_Y_Cb_Cr=rms))
            if fraction!='0.5':continue
            if key.endswith('D') and len(frames)>=2:
                a={v['patch']:v for v in rows if v['frame']==frames[0]};b={v['patch']:v for v in rows if v['frame']==frames[1]}
                for node in ('all',*nodes):
                    pairs=[(a[k],b[k]) for k in sorted(set(a)&set(b)) if max(abs(a[k]['q_nominal']),abs(b[k]['q_nominal']))>.2 and
                        (node=='all' or max(abs(a[k]['node_contributions'][str(node)]),abs(b[k]['node_contributions'][str(node)]))>.2)]
                    aa,bb=zip(*pairs);rgb=np.array([v['observed_rgb'] for v in bb])-np.array([v['observed_rgb'] for v in aa]);ycc=np.array([v['observed_ycc'] for v in bb])-np.array([v['observed_ycc'] for v in aa])
                    predchange=np.array([v['predicted_ycc'] for v in bb])-np.array([v['predicted_ycc'] for v in aa])
                    repeatability.append(dict(label=key,node=node,frames=frames,n=len(pairs),rgb_rms=np.sqrt(np.mean(rgb**2,axis=0)),
                        ycc_rms=np.sqrt(np.mean(ycc**2,axis=0)),input_adjusted_ycc_rms=np.sqrt(np.mean((ycc-predchange)**2,axis=0)),
                        ycc_abs_max=np.max(abs(ycc),axis=0)))
        if fraction=='0.5':
            for frame in sorted({v['frame'] for v in points}):
                rows=[v for v in points if v['frame']==frame and v['gray'] and not v['excluded']];xx=np.array([v['x_B'] for v in rows]);obs=np.array([v['observed_rgb'] for v in rows]);base=model.predict(xx)
                fits={key:centered_fit(obs,model.predict(xx,key)-base,xx,np.ones(len(rows),bool)) for key in ('RN','GN','BN','RD','GD','BD')}
                best=max(fits,key=lambda k:fits[k]['improvement']);confirmation.append(dict(frame=frame,assigned=rows[0]['label'],best_RGB_template=best,fits=fits))
            color_rows=[v for v in points if not v['gray']]
    prefix='primary-' if primary else ''
    dump(prefix+'shape_fits.json',allfits);dump(prefix+'free_kernels.json',free);dump(prefix+'coverage.json',coverage)
    dump(prefix+'components.json',components);dump(prefix+'repeatability.json',repeatability);dump(prefix+'confirmation.json',confirmation);dump(prefix+'colors.json',color_rows)
    for row in components:
        print('COMP',row['label'],row['node'],row['frame'],np.round(row['gain_Y_Cb_Cr'],3).tolist(),flush=True)
    for row in confirmation:print('CONFIRM',row['frame'],row['assigned'],row['best_RGB_template'],flush=True)
    for row in allfits:
        if row['fraction']=='0.5' and row['branch']=='mean' and row['response']=='q_y':
            print('FIT',row['label'],row['node'],[(v['shape'],round(v['rmse'],3),round(v['gain'],3)) for v in row['fits']],flush=True)


def diagnostics():
    model=ProbeModel();data=read('measure-0.5.json');points=data['points'];summaries=[]
    for row in data['drifts']:
        ii=np.array(row['patch_indices'])<49;raw=np.array(row['raw_percent'])[ii];rgb=np.array(row['corrected_rgb'])[ii];yc=np.array(row['corrected_ycc'])[ii]
        summaries.append(dict(first=row['first'],last=row['last'],phase=row['phase'],elapsed_s=row['elapsed_s'],gray_n=int(ii.sum()),
            raw_percent_median=np.median(raw,axis=0),raw_percent_min=raw.min(0),raw_percent_max=raw.max(0),
            corrected_rgb_rms=np.sqrt(np.mean(rgb**2,axis=0)),corrected_rgb_abs_max=np.max(abs(rgb),axis=0),
            corrected_ycc_rms=np.sqrt(np.mean(yc**2,axis=0)),corrected_ycc_abs_max=np.max(abs(yc),axis=0),
            direct_ycc_rms=np.sqrt(np.mean(np.array(row['direct_ycc'])[ii]**2,axis=0))))
    dump('drift.json',summaries)
    colors=[]
    variants={fraction:read('measure-'+fraction+'.json')['points'] for fraction in ('0.35','0.5','0.65')}
    for row in [v for v in points if not v['gray']]:
        matching=[next(v for v in pp if v['frame']==row['frame'] and v['patch']==row['patch']) for pp in variants.values()]
        observed=np.array([v['observed_ycc'] for v in matching]);predicted=np.array([v['predicted_ycc'] for v in matching])
        colors.append(dict(frame=row['frame'],label=row['label'],patch=row['patch'],conditioned_input=row['conditioned_input'],
            q_nominal=row['q_nominal'],observed_ycc=row['observed_ycc'],predicted_ycc=row['predicted_ycc'],
            ROI_observed_min=observed.min(0),ROI_observed_max=observed.max(0),ROI_predicted_min=predicted.min(0),ROI_predicted_max=predicted.max(0),
            nearest_A_observed_ycc=row['nearest_observed_ycc'],reference_frames=row['reference_frames']))
    dump('color_sensitivity.json',colors)
    uniformity=[]
    for meta in read('metadata.json'):
        frame=read('frames/'+meta['frame']+'.json');vv=[p for p in frame['patches']['0.5'][:49] if p['valid']]
        s=np.array([p['jpeg_sd'] for p in vv])
        uniformity.append(dict(frame=meta['frame'],valid_gray=len(vv),valid_colors=sum(p['valid'] for p in frame['patches']['0.5'][49:]),
            jpeg_sd_median=np.median(s,axis=0),jpeg_sd_95=np.percentile(s,95,axis=0),jpeg_sd_max=np.max(s,axis=0)))
    dump('uniformity.json',uniformity)
    oldpath=HERE.parent/'probe_pack_r1/local/ramp_field_20261103/measure-0.5.json';old=json.loads(oldpath.read_text())['points'];symmetry=[]
    for ch in 'RGB':
        rr_old=[r for r in old if r['channel']==ch and r['gray'] and not r['excluded']]
        rr_new=[r for r in points if r['label']==ch+'N' and r['gray'] and not r['excluded']]
        entry=dict(channel=ch,old_positive_frames=sorted({r['frame'] for r in rr_old}),new_negative_frames=sorted({r['frame'] for r in rr_new}))
        for name,rr in [('positive',rr_old),('negative',rr_new)]:
            b=np.array([r['q_nominal'] for r in rr]);y=np.array([r['q_y'] for r in rr]);active=abs(b)>.2;near=np.array([450<r['conditioned_input']<900 for r in rr])
            fitted=regression(b,y,near)
            entry[name]=dict(active_n=int(active.sum()),gain_active_no_intercept=float(b[active]@y[active]/(b[active]@b[active])),
                gain_with_intercept=fitted['gain'],offset=fitted['offset'],rmse=fitted['rmse'])
        entry['negative_positive_gain_ratio']=entry['negative']['gain_active_no_intercept']/entry['positive']['gain_active_no_intercept']
        matched=[]
        for left in np.arange(450,900,25):
            pos=[r['q_y'] for r in rr_old if left<=r['conditioned_input']<left+25]
            neg=[-r['q_y'] for r in rr_new if left<=r['conditioned_input']<left+25]
            if pos and neg:matched.append(dict(input_bin=[int(left),int(left+25)],positive_mean=float(np.mean(pos)),negative_magnitude_mean=float(np.mean(neg)),
                difference=float(np.mean(neg)-np.mean(pos)),positive_n=len(pos),negative_n=len(neg)))
        entry['matched_conditional_bins']=matched;symmetry.append(entry)
    dump('symmetry.json',dict(rows=symmetry,old_positive_measurement=str(oldpath.relative_to(ROOT)),old_sha256=f.sha(oldpath),
        limitation='Different times and chart inputs; not same-scene plus/minus pairs, and not a uniquely identified rounding phase.'))
    bands=[]
    meta,frames,j,r,yc,wb,valid,clip,clock=arrays('0.5');ref=20;xr,pr=model.inverse(j[ref])
    for i in range(13,21):
        mask=valid[i]&valid[ref];mask[49:]=False;xb=xr[mask]*r[i,mask]/r[ref,mask];expected=model.predict(xb)
        direct=j[i,mask]-j[ref,mask];corrected=j[i,mask]-expected;lum=yc[ref,mask,0]
        for low,high in [(30,80),(80,150),(150,220)]:
            selected=(lum>=low)&(lum<high)
            dc=direct-direct.mean(1,keepdims=True);cc=corrected-corrected.mean(1,keepdims=True)
            bands.append(dict(frame=meta[i]['frame'],reference=meta[ref]['frame'],Y_band=[low,high],n=int(selected.sum()),
                direct_channel_minus_mean=np.mean(dc[selected],axis=0),RAW_corrected_channel_minus_mean=np.mean(cc[selected],axis=0),
                direct_channel_mean=np.mean(direct[selected],axis=0)))
    dump('rough_band_check.json',bands)
    for v in summaries:print('DRIFT',v['first'],v['last'],'raw',np.round(v['raw_percent_median'],3),'ycc',np.round(v['corrected_ycc_rms'],3),flush=True)
    for v in symmetry:print('SYMMETRY',v['channel'],v['positive'],v['negative'],v['negative_positive_gain_ratio'],flush=True)
    for v in colors:
        if abs(v['q_nominal'])>.3:print('COLOR_ROI',v['frame'],v['label'],v['patch'],'obs',np.round(v['observed_ycc'],3),'nearest',np.round(v['nearest_A_observed_ycc'],3),flush=True)


def salvage():
    """Try cropped frames using only flat interiors; do not force a new label."""
    model=ProbeModel();assignment=read('assignments.json')['frames'];results=[]
    for fraction in ('0.35','0.5','0.65'):
        meta,frames,j,r,yc,wb,valid,clip,clock=arrays(fraction)
        anchors=[i for i,row in enumerate(assignment) if row['phase']=='p2' and row['label']=='A']
        inv={i:model.inverse(j[i]) for i in anchors}
        for i in (10,11,12):
            frame=frames[i];mask=np.array([p['valid'] and max(p.get('jpeg_sd',[999]))<4 for p in frame['patches'][fraction]])
            mask[49:]=False;ii=np.where(mask)[0];xx=[];obs=[]
            for p in ii:
                a,b,alpha=reference_for(i,p,anchors,clock,valid)
                gain=(1-alpha)*inv[a][0][p]/r[a,p]+alpha*inv[b][0][p]/r[b,p]
                x=gain*r[i,p];xx.append(x);obs.append(model.inverse(j[i,p][None])[1][0]-model.pre(x[None])[0])
            xx=np.array(xx);obs=np.array(obs);fits={}
            for key in ('RN','GN','BN','RD','GD','BD'):
                basis=model.pre(xx,key)-model.pre(xx)
                fits[key]=centered_fit(obs,basis,xx,np.ones(len(ii),bool))
                fits[key]['max_abs_nominal']=float(np.max(abs(basis)))
            best=max(fits,key=lambda k:fits[k]['improvement'])
            results.append(dict(frame=meta[i]['frame'],fraction=fraction,flat_patches=ii,flat_n=len(ii),best=best,fits=fits,
                reason='Only sample standard deviation selects ROIs. No time-order labels. Zero excitation cannot establish A versus an unexcited probe.'))
            print('SALVAGE',meta[i]['frame'],fraction,len(ii),best,{k:round(v['amplitude'],2) for k,v in fits.items()},'rmse',round(fits[best]['rmse'],3),
                'active',{k:v['active_points'] for k,v in fits.items()},flush=True)
    dump('salvage.json',results)


def fit_primary():fit(primary=True)


def refine():
    model=ProbeModel();variants={fraction:read('measure-'+fraction+'.json')['points'] for fraction in ('0.35','0.5','0.65')}
    sensitivities=[];raw_axes=[]
    for key in ('RN','GN','BN','RD','GD','BD'):
        for node in ([16] if key.endswith('N') else [8,19]):
            estimates=[]
            for fraction,points in variants.items():
                rows=[r for r in points if r['label']==key and r['gray'] and not r['excluded'] and
                    (not key.endswith('N') or r['phase']=='p1') and abs(r['node_contributions'][str(node)])>.2]
                pred=np.array([r['predicted_ycc'] for r in rows]);obs=np.array([r['observed_ycc'] for r in rows]);nearest=np.array([r['nearest_observed_ycc'] for r in rows])
                g=[];gn=[]
                for c in range(3):
                    mask=abs(pred[:,c])>.08
                    g.append(float(pred[mask,c]@obs[mask,c]/(pred[mask,c]@pred[mask,c])) if mask.any() else None)
                    gn.append(float(pred[mask,c]@nearest[mask,c]/(pred[mask,c]@pred[mask,c])) if mask.any() else None)
                estimates.append(dict(fraction=fraction,gain=g,nearest_A_gain=gn))
            sensitivities.append(dict(label=key,node=node,estimates=estimates))
            rows=[r for r in variants['0.5'] if r['label']==key and r['gray'] and not r['excluded'] and (not key.endswith('N') or r['phase']=='p1')]
            low,high={8:(65,180),16:(450,900),19:(780,1280)}[node];c='RGB'.index(key[0])
            near=[r for r in rows if low<r['raw_wb'][c]<high]
            for response in ('q_y','q_rgb'):
                sign=-1 if key.endswith('N') else 1
                ff=free_kernel(np.array([r['raw_wb'][c] for r in near]),sign*np.array([r[response] for r in near]),model,node)
                raw_axes.append(dict(label=key,node=node,response=response,axis='independent RAW_WB',**ff))
    dump('component_sensitivity.json',sensitivities);dump('raw_axis_free_kernels.json',raw_axes)
    symmetry=read('symmetry.json');points=variants['0.5']
    for row in symmetry['rows']:
        rr=[r for r in points if r['label']==row['channel']+'N' and r['phase']=='p1' and r['gray'] and not r['excluded']]
        b=np.array([r['q_nominal'] for r in rr]);y=np.array([r['q_y'] for r in rr]);mask=abs(b)>.2
        row['negative_primary']=dict(frame=rr[0]['frame'],active_n=int(mask.sum()),gain_active_no_intercept=float(b[mask]@y[mask]/(b[mask]@b[mask])))
        row['primary_negative_positive_ratio']=row['negative_primary']['gain_active_no_intercept']/row['positive']['gain_active_no_intercept']
    dump('symmetry.json',symmetry)
    meta,frames,j,r,yc,wb,valid,clip,clock=arrays('0.5');direct=[]
    labels=read('assignments.json')['frames']
    for point in [r for r in points if not r['gray'] and abs(r['q_nominal'])>.3]:
        i=point['index'];p=point['patch_index'];anchors=[k for k,row in enumerate(labels) if row['phase']==point['phase'] and row['label']=='A']
        a,b,alpha=reference_for(i,p,anchors,clock,valid)
        direct.append(dict(frame=point['frame'],label=point['label'],patch=point['patch'],
            uncorrected_ycc=yc[i,p]-(1-alpha)*yc[a,p]-alpha*yc[b,p],corrected_ycc=point['observed_ycc'],predicted_ycc=point['predicted_ycc']))
    dump('color_no_RAW_correction.json',direct)
    allshapes=read('primary-shape_fits.json');rank=[]
    for key in ('RN','GN','BN','RD','GD','BD'):
        for node in ([16] if key.endswith('N') else [8,19]):
            for response in ('q_y','q_rgb'):
                rr=[r for r in allshapes if r['label']==key and r['node']==node and r['response']==response]
                winners={};dif=[]
                for item in rr:
                    winner=item['fits'][0]['shape'];winners[winner]=winners.get(winner,0)+1
                    by={r['shape']:r['rmse'] for r in item['fits']};dif.append(by['linear_floor']-by['linear_round'])
                rank.append(dict(label=key,node=node,response=response,winner_counts=winners,
                    floor_minus_round_RMSE_range=[min(dif),max(dif)],branches=len(rr)))
    dump('shape_sensitivity_summary.json',rank)
    for row in symmetry['rows']:print('PRIMARY_SYMMETRY',row['channel'],row['negative_primary'],row['primary_negative_positive_ratio'],flush=True)
    for row in direct:print('DIRECT_COLOR',row['frame'],row['label'],row['patch'],np.round(row['uncorrected_ycc'],3),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['inventory','geometry','extract','extract_verify','phase','identify','classify','measure','fit','fit_primary','diagnostics','salvage','refine']);args=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    lock=os.open(OUT/(args.stage+'.lock'),os.O_CREAT|os.O_RDWR,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.alarm(1800);sys.addaudithook(audit);start=time.monotonic()
    globals()[args.stage]()
    dump('timing-'+args.stage+'.json',dict(status='PASS',seconds=time.monotonic()-start,nice=os.getpriority(os.PRIO_PROCESS,0)))


if __name__=='__main__':main()
