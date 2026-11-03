"""Serial, read-only analysis of the MOUNT dense-ramp captures."""
import os
import sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local/ramp_field_20261103'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe-ramp-field')
CAP = ROOT / 'captures/mount-probe-ramp-20261103'
REF = ROOT / 'captures/mount-probe-ramp-20261103-take1-no-preset'
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key] = '1'
os.environ.update(TMPDIR=str(TMP), MPLCONFIGDIR=str(TMP/'mpl'))
import argparse
import datetime
import fcntl
import hashlib
import json
import math
import shutil
import time
import csv
import importlib.util
import subprocess
import plistlib
volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
assert volume['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert volume['FilesystemType']=='apfs' and volume['WritableVolume']
OUT.mkdir(exist_ok=True)
TMP.mkdir(parents=True,exist_ok=True)
lock = os.open(OUT/'serial.lock',os.O_CREAT|os.O_RDWR,0o600)
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sys.path.insert(0,str(HERE))
import field_20261103 as f
f.OUT,f.TMP = OUT,TMP
os.environ.update(TMPDIR=str(TMP), MPLCONFIGDIR=str(TMP/'mpl'))
import numpy as np
from scipy import ndimage, optimize, interpolate, stats
from PIL import Image, ImageDraw, ImageFont


def finite(value):
    value=f.plain(value)
    if isinstance(value,dict): return {k:finite(v) for k,v in value.items()}
    if isinstance(value,list): return [finite(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    return value


def dump(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(finite(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def read(name): return json.loads((OUT/name).read_text())


def audit(event,args):
    if event in ('subprocess.Popen','socket.connect','socket.bind','socket.getaddrinfo'):
        raise PermissionError('Network and subprocesses disabled during analysis')
    if event=='open' and isinstance(args[0],(str,bytes,Path)):
        p=Path(os.fsdecode(args[0])).resolve()
        if str(p).startswith('/Volumes/') and not (p.is_relative_to(ROOT) or p.is_relative_to(TMP)):
            raise PermissionError('Unrelated volume: '+str(p))
        mode,flags=args[1:3]
        write=isinstance(mode,str) and any(c in mode for c in 'wax+')
        write|=isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if write and not (p.is_relative_to(OUT) or p.is_relative_to(TMP)):
            raise PermissionError('Write outside new local output: '+str(p))
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.utime','os.chmod'):
        for value in args[:2] if event in ('os.rename','os.link','os.symlink') else args[:1]:
            if isinstance(value,(str,bytes,Path)):
                p=Path(os.fsdecode(value)).resolve()
                if not (p.is_relative_to(OUT) or p.is_relative_to(TMP)):
                    raise PermissionError('Mutation outside new local output: '+str(p))


def inventory():
    rows=[]
    before=OUT/'before.json'
    if not before.exists():
        dump('before.json',{str(p.relative_to(ROOT)):f.sha(p) for p in HERE.rglob('*')
            if p.is_file() and not p.is_relative_to(OUT) and p.name!='ramp_field_20261103.py'})
    for folder,tag in [(CAP,'formal'),(REF,'reference_only')]:
        hashes=[]
        for line in (folder/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split(None,1);name=name.lstrip('*')
            p=folder/name
            assert p.resolve().parent==folder.resolve() and f.sha(p)==expected,name
            hashes.append(dict(file=str(p.relative_to(ROOT)),sha256=expected,bytes=p.stat().st_size))
        assert len(hashes)==16
        dump(tag+'-inputs.json',dict(files=hashes,manifest_sha256=f.sha(folder/'SHA256SUMS')))
        sheet=Image.new('RGB',(1800,670),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for i,jpg in enumerate(sorted(folder.glob('*.JPG'))):
            stem=jpg.stem
            d=f.metadata(f.Tiff(jpg.with_suffix('.DNG').read_bytes()))
            j=f.metadata(f.jpeg_tiff(jpg))
            for key in ('time','iso','exposure_s','selector','sliders_raw','wb_shotinfo'):
                assert d[key]==j[key],(stem,key)
            with Image.open(jpg) as im:
                row=dict(frame=stem,group=tag,dng=d,jpeg=j,jpeg_wh=list(im.size),quantization=im.quantization)
                rows.append(row)
                im.thumbnail((450,300));x,y=(i%4)*450,(i//4)*335
                sheet.paste(im,(x,y+25));draw.text((x+6,y+5),stem,fill='black')
                if stem in ('R8051926','R8051932','R8051918'):
                    view=Image.open(jpg);view.thumbnail((1600,1100));view.save(OUT/(stem+'-view.jpg'),quality=94)
            print(stem,tag,d['time'],d['exposure_s'],d['iso'],d['sliders_display'],flush=True)
        sheet.save(OUT/(tag+'-contact.jpg'),quality=92)
    dump('all_metadata.json',rows)
    dump('metadata.json',[r for r in rows if r['group']=='formal'])
    dump('environment.json',dict(python=sys.executable,numpy=np.__version__,nice=os.getpriority(os.PRIO_PROCESS,0),
        threads={k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS')},
        compute_processes=1,network=False,camera_or_card=False))


def project(H, xy):
    xy=np.asarray(xy,float);v=np.c_[xy.reshape(-1,2),np.ones(xy.size//2)]@H.T
    return (v[:,:2]/v[:,2:]).reshape(xy.shape)


def homography(source,target):
    A=[];b=[]
    for (x,y),(u,v) in zip(source,target):
        A.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]])
        b.extend([u,v])
    return np.r_[np.linalg.lstsq(A,b,rcond=None)[0],1].reshape(3,3)


def locate(rgb,stem):
    layout=json.loads((HERE/'local/ramp/browser/layout.json').read_text())
    small=np.asarray(Image.fromarray(rgb).resize((1000,664),Image.Resampling.BOX),float).mean(2)
    lab,_=ndimage.label(small>130);candidates=[]
    for sl in ndimage.find_objects(lab):
        yy,xx=sl;w,h=xx.stop-xx.start,yy.stop-yy.start
        if 20<w<65 and 10<h<65 and yy.start<550:
            candidates.append([xx.start,yy.start,w,h])
    centers=[];seeds=[];models=[]
    for m in layout['markers']:
        corner=m['corner'];right=corner.endswith('R');bottom=corner.startswith('B')
        valid=[b for b in candidates if ((b[0]>730) if right else (b[0]<180)) and
            ((b[1]>360) if bottom else (b[1]<150))]
        assert valid,(stem,corner,candidates)
        x,y,w,h=max(valid,key=lambda b:b[2]*b[3]);clipped=y==0
        effective_h=w if clipped else h
        cx=x+w/2;cy=y+h-effective_h/2 if clipped else y+h/2
        r=m['rect'];centers.append([r['x']+r['w']/2,r['y']+r['h']/2])
        seeds.append([cx/1000,cy/664])
        rows=m['bits'];pattern=np.zeros((90,90),float)
        pattern[:10]=1;pattern[-10:]=1;pattern[:,:10]=1;pattern[:,-10:]=1
        for iy,row in enumerate(rows):
            for ix,bit in enumerate(row):
                pattern[(iy+2)*10:(iy+3)*10,(ix+2)*10:(ix+3)*10]=int(bit)
        pattern=ndimage.gaussian_filter(pattern,4.5)
        a=np.linspace(.3,8.7,35);xx,yy=np.meshgrid(a,a)
        points=np.column_stack([r['x']+xx.ravel()/9*r['w'],r['y']+yy.ravel()/9*r['h']])
        expect=ndimage.map_coordinates(pattern,[yy.ravel()*10-.5,xx.ravel()*10-.5],order=1)
        models.append((points,expect,corner,clipped,[x,y,w,h]))
    H0=homography(centers,seeds);p0=H0.ravel()[:8]
    # The partially clipped top markers still contribute every visible coded cell.
    visible=[]
    for points,expect,corner,clipped,box in models:
        uv=project(H0,points)
        mask=(uv[:,0]>.003)&(uv[:,0]<.997)&(uv[:,1]>.012)&(uv[:,1]<.988)
        visible.append((points[mask],expect[mask]))
    def residual(p):
        H=np.r_[p,1].reshape(3,3);values=[]
        for points,expected in visible:
            if len(points)<600: continue
            uv=project(H,points)
            actual=ndimage.map_coordinates(small,[uv[:,1]*664-.5,uv[:,0]*1000-.5],order=1,mode='nearest')
            X=np.column_stack([np.ones(len(expected)),expected]);coef=np.linalg.lstsq(X,actual,rcond=None)[0]
            values.extend((actual-X@coef)/max(coef[1],50))
        values.extend((p-p0)*.25)
        return np.array(values)
    span=np.array([.06,.04,.03,.04,.06,.03,.08,.08])
    fit=optimize.least_squares(residual,p0,bounds=(p0-span,p0+span),max_nfev=150,loss='soft_l1',f_scale=.15,
        ftol=1e-9,xtol=1e-9,gtol=1e-9)
    H=np.r_[fit.x,1].reshape(3,3)
    marker_rows=[]
    for m,(_,_,corner,clipped,box),(points,expected) in zip(layout['markers'],models,visible):
        uv=project(H,points);actual=ndimage.map_coordinates(small,[uv[:,1]*664-.5,uv[:,0]*1000-.5],order=1)
        marker_rows.append(dict(corner=corner,seed_bbox_1000=box,partially_clipped=clipped,
            visible_template_samples=len(points),used_for_fit=len(points)>=600,
            correlation=float(np.corrcoef(actual,expected)[0,1])))
    assert sum(m['used_for_fit'] for m in marker_rows)>=3,(stem,marker_rows)
    assert min(m['correlation'] for m in marker_rows if m['used_for_fit'])>.65,(stem,marker_rows)
    return H,dict(markers=marker_rows,fit_nfev=fit.nfev,fit_rmse=float(np.sqrt(np.mean(residual(fit.x)**2))),
                  seed_H=H0,refined_H=H,template_blur_cells=.45,fit_success=fit.success)


def sample_patch(rgb,ycc,raw,info,H,patch,fraction,neutral):
    r=patch['swatch'];x=r['x']+r['w']*(1-fraction)/2;y=r['y']+r['h']*(1-fraction)/2
    w=r['w']*fraction;h=r['h']*fraction
    poly=project(H,[[x,y],[x+w,y],[x+w,y+h],[x,y+h]])*np.array(rgb.shape[1::-1])
    x0,y0=np.floor(poly.min(0)).astype(int);x1,y1=np.ceil(poly.max(0)).astype(int)+1
    assert x0>=0 and y0>=0 and x1<=rgb.shape[1] and y1<=rgb.shape[0],(patch['id'],poly)
    yy,xx=np.mgrid[y0:y1,x0:x1]
    uv=project(np.linalg.inv(H),np.stack([(xx+.5)/rgb.shape[1],(yy+.5)/rgb.shape[0]],axis=-1))
    mask=(uv[:,:,0]>=x)&(uv[:,:,0]<=x+w)&(uv[:,:,1]>=y)&(uv[:,:,1]<=y+h)
    assert mask.sum()>300,patch['id']
    ox,oy=info['crop_origin_xy'];cfa=np.array([[0,1],[1,2]])[(yy+oy)%2,(xx+ox)%2]
    channels=[raw[y0:y1,x0:x1][mask&(cfa==c)] for c in range(3)]
    jr=rgb[y0:y1,x0:x1];yc=ycc[y0:y1,x0:x1]
    hist=[]
    for values in channels:
        counts=np.bincount(values,minlength=4096);bins=np.where(counts>0)[0]
        hist.append(dict(dn=bins,counts=counts[bins]))
    tiles=[]
    for ty in range(4):
        for tx in range(4):
            tile=mask&(uv[:,:,0]>=x+tx*w/4)&(uv[:,:,0]<x+(tx+1)*w/4)&(uv[:,:,1]>=y+ty*h/4)&(uv[:,:,1]<y+(ty+1)*h/4)
            tiles.append(dict(rgb=jr[tile].mean(0),ycc=yc[tile].mean(0),
                raw_dn=[raw[y0:y1,x0:x1][tile&(cfa==c)].mean()-info['black'] for c in range(3)],pixels=int(tile.sum())))
    return dict(id=patch['id'],screen_rgb=patch['rgb'],polygon=poly,roi_bbox=[x0,y0,x1,y1],pixels=int(mask.sum()),
        jpeg_mean=jr[mask].mean(0),native_ycc_mean=yc[mask].mean(0),
        jpeg_sd=jr[mask].std(0),ycc_sd=yc[mask].std(0),
        raw_dn_mean=[a.mean()-info['black'] for a in channels],raw_sd=[a.std() for a in channels],
        raw_wb=[(a.mean()-info['black'])/neutral[c] for c,a in enumerate(channels)],raw_histograms=hist,
        raw_clip_fraction=[float(np.mean(a>=info['white']-16)) for a in channels],
        jpeg_clip_fraction=np.mean((jr[mask]<=2)|(jr[mask]>=253),axis=0),tiles=tiles)


def extract():
    layout=json.loads((HERE/'local/ramp/browser/layout.json').read_text())
    sheet=Image.new('RGB',(1800,700),'#eeeeee');sd=ImageDraw.Draw(sheet)
    previous={p.name:f.sha(p) for p in (OUT/'frames').glob('*.json')} if (OUT/'frames').exists() else {}
    for i,meta in enumerate(read('metadata.json')):
        stem=meta['frame'];t=f.Tiff((CAP/(stem+'.DNG')).read_bytes())
        raw,info=f.decode_raw(t);rgb=np.asarray(Image.open(CAP/(stem+'.JPG')).convert('RGB'))
        with Image.open(CAP/(stem+'.JPG')) as im:
            im.draft('YCbCr',im.size);assert im.mode=='YCbCr';ycc=np.asarray(im)
        assert raw.shape==rgb.shape[:2]==ycc.shape[:2]
        H,location=locate(rgb,stem)
        sets={str(fraction):[sample_patch(rgb,ycc,raw,info,H,p,fraction,meta['dng']['as_shot_neutral'])
               for p in layout['patches']] for fraction in (.35,.5,.65)}
        dump('frames/'+stem+'.json',dict(frame=stem,raw=info,location=location,patches=sets))
        view=Image.fromarray(rgb);view.thumbnail((450,310));d=ImageDraw.Draw(view);scale=np.array(view.size)/np.array(rgb.shape[1::-1])
        for p in sets['0.5']:
            poly=np.array(p['polygon'])*scale;d.line([tuple(v) for v in np.vstack([poly,poly[:1]])],fill='#ffff00',width=1)
        for m in layout['markers']:
            r=m['rect'];poly=project(H,[[r['x'],r['y']],[r['x']+r['w'],r['y']],[r['x']+r['w'],r['y']+r['h']],[r['x'],r['y']+r['h']]])*np.array(view.size)
            d.line([tuple(v) for v in np.vstack([poly,poly[:1]])],fill='#ff00ff',width=1)
        xx,yy=i%4*450,i//4*350;sheet.paste(view,(xx,yy+25));sd.text((xx+6,yy+5),stem,fill='black')
        view.save(OUT/(stem+'-roi.jpg'),quality=94)
        raws=np.array([p['raw_wb'] for p in sets['0.5'][:49]])
        print(stem,'RAW range',np.round(raws.min(0),1),np.round(raws.max(0),1),
              'marker r',np.round([v['correlation'] for v in location['markers']],3),flush=True)
    sheet.save(OUT/'roi-contact.jpg',quality=94)
    if previous:
        changed=[name for name,sha in previous.items() if f.sha(OUT/'frames'/name)!=sha]
        dump('extraction-rerun.json',dict(frames_compared=len(previous),changed=changed,all_bytes_equal=not changed))
        assert not changed,changed


def ycc_codes(model,rgb):
    y,c=model.mm.ycbcr(np.asarray(rgb));return np.stack([y,c.real+128,c.imag+128],axis=-1)


def geometry():
    layout=json.loads((HERE/'local/ramp/browser/layout.json').read_text());rows=[]
    for meta in read('metadata.json'):
        stem=meta['frame'];saved=read('frames/'+stem+'.json');H=np.array(saved['location']['refined_H'])
        rgb=np.asarray(Image.open(CAP/(stem+'.JPG')).resize((1000,664),Image.Resampling.BOX),float).mean(2)
        errors=[]
        for patch in layout['patches'][:49]:
            if patch['id']=='g48':continue
            r=patch['swatch'];x,y,w,h=(r[k] for k in ('x','y','w','h'))
            for side in range(4):
                for q in (.25,.5,.75):
                    point=([x+w*q,y],[x+w*q,y+h],[x,y+h*q],[x+w,y+h*q])[side]
                    normal=np.array(([0,1],[0,-1],[1,0],[-1,0])[side],float)
                    uv=project(H,[point])[0]*[1000,664]
                    dv=project(H,[np.array(point)+normal*.001])[0]*[1000,664]-uv;dv/=np.linalg.norm(dv)
                    tt=np.linspace(-8,8,129);pp=uv+tt[:,None]*dv
                    line=ndimage.map_coordinates(rgb,[pp[:,1],pp[:,0]],order=1)
                    gradient=np.gradient(ndimage.gaussian_filter1d(line,3),tt)
                    k=int(np.argmax(gradient));errors.append(dict(patch=patch['id'],side=side,
                        offset_pixels_1000=float(tt[k]),gradient=float(gradient[k])))
        offsets=np.array([v['offset_pixels_1000'] for v in errors])
        rows.append(dict(frame=stem,edge_points=len(errors),offset_median=float(np.median(offsets)),
            offset_abs_median=float(np.median(abs(offsets))),offset_abs_95=float(np.percentile(abs(offsets),95)),
            boundary_hits=int(np.sum(abs(offsets)>=7.875)),details=errors))
        print('edge check',stem,'median/95',rows[-1]['offset_abs_median'],rows[-1]['offset_abs_95'],flush=True)
    dump('geometry-check.json',dict(rows=rows,scope='Independent grey-edge checks after marker fit; no coordinates refitted.'))


def measure():
    meta=read('metadata.json');frames=[read('frames/'+r['frame']+'.json') for r in meta]
    model=f.FieldModel()
    dump('model.json',dict(inputs=model.inputs,xs=model.xs,curves=model.curves,
        row=model.row.describe(),Y_coeff=model.row.coef[0]/1024,
        scope='Original transferred model, not refitted; conditional inverse axis'))
    clock=np.array([datetime.datetime.strptime(r['dng']['time'],'%Y:%m:%d %H:%M:%S').timestamp() for r in meta]);clock-=clock[0]
    for fraction in ('0.35','0.5','0.65'):
        ps=[r['patches'][fraction] for r in frames]
        j=np.array([[p['jpeg_mean'] for p in row] for row in ps]);r=np.array([[p['raw_dn_mean'] for p in row] for row in ps])
        yc=np.array([[p['native_ycc_mean'] for p in row] for row in ps]);wb=np.array([[p['raw_wb'] for p in row] for row in ps])
        inverses=[model.inverse(v) for v in j];xx=np.array([v[0] for v in inverses]);pre=np.array([v[1] for v in inverses])
        gain=np.median(xx/r,axis=0)
        predicted_pre=np.array([model.pre(gain*rr) for rr in r])
        feature=pre-predicted_pre;feature-=np.median(feature,axis=0)
        identity=[]
        for i,row in enumerate(meta):
            amps=[];rms=[]
            for c,ch in enumerate('RGB'):
                x=gain*r[i];nominal=model.pre(x,ch)[:,c]-model.pre(x)[:,c]
                v=feature[i,:,c];b=nominal
                amps.append(float(b@v/(b@b)));rms.append(float(np.sqrt(np.mean((v-amps[-1]*b)**2))))
            best=int(np.argmax(amps));label='RGB'[best] if amps[best]>.3 else 'A'
            identity.append(dict(frame=row['frame'],response_label=label,feature_amplitudes=dict(zip('RGB',amps)),
                feature_rmse=dict(zip('RGB',rms)),feature=feature[i],independent_of_plan=True))
        labels=[v['response_label'] for v in identity];anchors=np.where(np.array(labels)=='A')[0]
        assert len(anchors)>=2,(fraction,labels,identity)
        a0,a1=int(anchors[0]),int(anchors[-1]);assert a0==0 and a1==7,(fraction,anchors)
        anchor_offset=yc[[a0,a1]]-ycc_codes(model,j[[a0,a1]])
        points=[];checks=[]
        for i,row in enumerate(meta):
            if labels[i]=='A':continue
            c='RGB'.index(labels[i]);ch=labels[i]
            alpha=float((clock[i]-clock[a0])/(clock[a1]-clock[a0]))
            input_gain=(1-alpha)*xx[a0]/r[a0]+alpha*xx[a1]/r[a1]
            xB=input_gain*r[i];preB=model.pre(xB);baseline=model.predict(xB)
            expected_ycc=ycc_codes(model,baseline)+(1-alpha)*anchor_offset[0]+alpha*anchor_offset[1]
            # Direct Y correction uses only C100's luminance row.
            expected_ycc[:,0]=(1-alpha)*yc[a0,:,0]+alpha*yc[a1,:,0]+(
                preB-(1-alpha)*pre[a0]-alpha*pre[a1])@(model.row.coef[0]/1024)
            obs=j[i]-baseline;dycc=yc[i]-expected_ycc
            allpred={k:model.predict(xB,k)-baseline for k in 'RGB'}
            jac=[]
            for cc in range(3):
                dp=np.zeros_like(preB);dp[:,cc]=.05
                jac.append((model.forward_pre(preB+dp)-model.forward_pre(preB-dp))/.1)
            jac=np.array(jac)
            q=np.sum(jac[c]*obs,axis=1)/np.sum(jac[c]**2,axis=1)
            for iteration in range(2):
                pp=preB.copy();pp[:,c]+=q
                dq=np.zeros_like(pp);dq[:,c]=.02
                local_jac=(model.forward_pre(pp+dq)-model.forward_pre(pp-dq))/.04
                residue=obs-(model.forward_pre(pp)-baseline)
                q+=np.sum(local_jac*residue,axis=1)/np.sum(local_jac**2,axis=1)
            fitted=preB.copy();fitted[:,c]+=q
            qres=obs-(model.forward_pre(fitted)-baseline)
            nominal=model.pre(xB,ch)[:,c]-preB[:,c]
            fit_scores={}
            for k in 'RGB':
                b=allpred[k][:49];o=obs[:49];amp=float(np.clip(np.sum(b*o)/np.sum(b*b),0,3))
                fit_scores[k]=dict(amplitude=amp,rmse=float(np.sqrt(np.mean((o-amp*b)**2))))
            fit_scores['A']=dict(amplitude=0,rmse=float(np.sqrt(np.mean(obs[:49]**2))))
            checks.append(dict(frame=row['frame'],response_label=ch,best_template=min(fit_scores,key=lambda k:fit_scores[k]['rmse']),
                template_fits=fit_scores,reference_alpha=alpha))
            for p in range(52):
                patch=ps[i][p];pred_ycc=ycc_codes(model,allpred[ch][p])-np.array([0,128,128])
                points.append(dict(frame=row['frame'],index=i,channel=ch,patch=patch['id'],patch_index=p,gray=p<49,
                    screen_rgb=patch['screen_rgb'],fraction=fraction,raw_wb=wb[i,p],raw_input=wb[i,p,c],
                    conditioned_input=xB[p,c],x_B=xB[p],pre_B=preB[p],baseline_rgb=baseline[p],
                    reference_alpha=alpha,raw_relative_to_time_A=100*(r[i,p]/((1-alpha)*r[a0,p]+alpha*r[a1,p])-1),
                    direct_rgb=j[i,p]-((1-alpha)*j[a0,p]+alpha*j[a1,p]),
                    observed_rgb=obs[p],observed_ycc=dycc[p],predicted_rgb=allpred[ch][p],predicted_ycc=pred_ycc,
                    q_estimate=q[p],q_y=dycc[p,0]/(model.row.coef[0,c]/1024),q_nominal=nominal[p],
                    q_projection_residual_rgb=qres[p],raw_histogram=patch['raw_histograms'][c],
                    raw_target_mean=r[i,p,c],raw_black=frames[i]['raw']['black'],raw_sigma=patch['raw_sd'][c],
                    excluded=any(np.array(patch['raw_clip_fraction'])>0) or max(patch['jpeg_clip_fraction'])>.001))
        drift_expected=model.predict(xx[a0]*r[a1]/r[a0]);drift_pre=model.pre(xx[a0]*r[a1]/r[a0])
        drift_ycc=ycc_codes(model,drift_expected)+anchor_offset[0]
        drift_ycc[:,0]=yc[a0,:,0]+(drift_pre-pre[a0])@(model.row.coef[0]/1024)
        dump('measure-'+fraction+'.json',dict(points=points,identity=identity,template_checks=checks,
            drift=dict(first=meta[a0]['frame'],last=meta[a1]['frame'],elapsed_s=clock[a1]-clock[a0],
                raw_percent=100*(r[a1]/r[a0]-1),direct_rgb=j[a1]-j[a0],corrected_rgb=j[a1]-drift_expected,
                direct_ycc=yc[a1]-yc[a0],corrected_ycc=yc[a1]-drift_ycc,
                first_raw_wb=wb[a0],last_raw_wb=wb[a1],first_conditioned_input=xx[a0],last_conditioned_input=xx[a1]),
            axes='RAW_WB is independent sensor proxy; conditioned_input inverts A through the existing model.'))
        print('fraction',fraction,'identities',labels,flush=True)
        if fraction=='0.5':
            print('identity amplitudes',[(v['frame'],{k:round(a,3) for k,a in v['feature_amplitudes'].items()}) for v in identity],flush=True)
            for check in checks:print('template',check['frame'],{k:round(v['rmse'],3) for k,v in check['template_fits'].items()},flush=True)
            dp=100*(r[a1,:49]/r[a0,:49]-1)
            print('drift raw median',np.median(dp,axis=0),'range',dp.min(0),dp.max(0),flush=True)


SHAPES=('linear_tent','raised_cosine','pchip_difference','nearest_node','previous_node','linear_floor','linear_round')


def bases(rows,model,branch):
    result={shape:[] for shape in SHAPES};left,peak,right=model.xs[15:18]
    for row in rows:
        c='RGB'.index(row['channel'])
        if branch=='mean': x=np.array([row['conditioned_input']]);weights=np.ones(1)
        elif branch=='tile_means':
            weights=np.array(row['tile_weights'],float);weights/=weights.sum()
            x=np.array(row['tile_raw_means'])*row['conditioned_input']/row['raw_target_mean']
        else:
            hist=row['raw_histogram'];weights=np.array(hist['counts'],float);weights/=weights.sum()
            x=(np.array(hist['dn'])-row['raw_black'])*row['conditioned_input']/row['raw_target_mean']
        tent=np.maximum(0,np.minimum((x-left)/(peak-left),(right-x)/(right-peak)))
        base=np.interp(x,model.xs,model.curves['A'][c]);bump=2*tent
        values=dict(linear_tent=bump,raised_cosine=1-np.cos(np.pi*tent),
            nearest_node=2*((x>=(left+peak)/2)&(x<(peak+right)/2)),previous_node=2*((x>=peak)&(x<right)),
            linear_floor=np.floor(base+bump)-np.floor(base),linear_round=np.floor(base+bump+.5)-np.floor(base+.5),
            pchip_difference=interpolate.PchipInterpolator(model.xs,model.curves[row['channel']][c])(x)-
                interpolate.PchipInterpolator(model.xs,model.curves['A'][c])(x))
        for shape,v in values.items(): result[shape].append(float(v@weights))
    return {k:np.array(v) for k,v in result.items()}


def regression(b,y,mask=None):
    if mask is None:mask=np.ones(len(y),bool)
    X=np.column_stack([b,np.ones(len(b))]);coef=np.linalg.lstsq(X[mask],y[mask],rcond=None)[0]
    pred=X@coef
    return dict(gain=float(coef[0]),offset=float(coef[1]),rmse=float(np.sqrt(np.mean((pred[mask]-y[mask])**2))),prediction=pred)


def free_kernel(x,y,kind='linear'):
    # Four shape parameters, shared by both repeats. No claim that sample means
    # are the ISP input distribution.
    def value(par,xx=x):
        left,peak,right,amp,offset=par
        z=np.maximum(0,np.minimum((xx-left)/max(peak-left,1),(right-xx)/max(right-peak,1)))
        if kind=='cosine':z=(1-np.cos(np.pi*z))/2
        return amp*z+offset
    def residual(par):
        penalty=np.array([max(par[0]+20-par[1],0),max(par[1]+20-par[2],0)])*.1
        return np.r_[value(par)-y,penalty]
    solutions=[]
    for center in (630,660,690):
        sol=optimize.least_squares(residual,[550,center,800,2,0],
            bounds=([420,570,700,.2,-.4],[650,760,1000,4,.4]),max_nfev=150)
        solutions.append(sol)
    sol=min(solutions,key=lambda v:np.sum(residual(v.x)**2))
    left,peak,right,amp,offset=sol.x
    return dict(kind=kind,left=left,peak=peak,right=right,amplitude=amp,offset=offset,
        FWHM=(right-left)/2,half_left=(left+peak)/2,half_right=(right+peak)/2,
        rmse=float(np.sqrt(np.mean((value(sol.x)-y)**2))),parameters=sol.x)


def fit():
    model=f.FieldModel();allfits=[];components=[];repeat_rows=[];ranges=[];sensitivity=[]
    frame_cache={m['frame']:read('frames/'+m['frame']+'.json') for m in read('metadata.json')}
    for fraction in ('0.35','0.5','0.65'):
        data=read('measure-'+fraction+'.json')
        for ch in 'RGB':
            rows=[r for r in data['points'] if r['channel']==ch and r['gray'] and not r['excluded']]
            for r in rows:
                tiles=frame_cache[r['frame']]['patches'][fraction][r['patch_index']]['tiles'];c='RGB'.index(ch)
                r['tile_raw_means']=[t['raw_dn'][c] for t in tiles];r['tile_weights']=[t['pixels'] for t in tiles]
            near=np.array([450<r['conditioned_input']<900 for r in rows])
            active=np.array([r['q_nominal']>.2 for r in rows])
            frames=sorted({r['frame'] for r in rows});frame_mask=np.array([r['frame']==frames[0] for r in rows])
            for branch in ('mean','tile_means','raw_histogram'):
                bb=bases(rows,model,branch)
                for response in ('q_estimate','q_y'):
                    y=np.array([r[response] for r in rows]);fits=[]
                    for shape,b in bb.items():
                        fitted=regression(b,y,near)
                        cv=[]
                        for train in (frame_mask,~frame_mask):
                            trained=regression(b,y,near&train)
                            cv.append(float(np.sqrt(np.mean((trained['prediction'][near&~train]-y[near&~train])**2))))
                        fits.append(dict(shape=shape,gain=fitted['gain'],offset=fitted['offset'],
                            rmse=fitted['rmse'],active_rmse=float(np.sqrt(np.mean((fitted['prediction'][active]-y[active])**2))),
                            repeat_holdout_rmse=cv))
                    fits.sort(key=lambda v:v['rmse'])
                    allfits.append(dict(fraction=fraction,channel=ch,branch=branch,response=response,
                        n=int(near.sum()),unique_patches=len(set(r['patch'] for r,m in zip(rows,near) if m)),fits=fits))
            x=np.array([r['conditioned_input'] for r in rows])[near]
            for response in ('q_estimate','q_y'):
                y=np.array([r[response] for r in rows])[near]
                for kind in ('linear','cosine'):
                    free=free_kernel(x,y,kind)
                    sensitivity.append(dict(fraction=fraction,channel=ch,response=response,**free))
            if fraction!='0.5':continue
            # Component slopes are local final-JPEG diagnostics, not new DAT coefficients.
            for frame in frames+['pooled']:
                rr=[r for r in rows if (r['frame']==frame or frame=='pooled') and r['q_nominal']>.2]
                pred=np.array([r['predicted_ycc'] for r in rr]);obs=np.array([r['observed_ycc'] for r in rr]);g=[];rm=[];counts=[]
                for c in range(3):
                    valid=abs(pred[:,c])>.08
                    counts.append(int(valid.sum()))
                    gain=float(pred[valid,c]@obs[valid,c]/(pred[valid,c]@pred[valid,c]))
                    g.append(gain);rm.append(float(np.sqrt(np.mean((obs[valid,c]-pred[valid,c])**2))))
                components.append(dict(channel=ch,frame=frame,n=len(rr),component_n=counts,gain_Y_Cb_Cr=g,
                    original_rmse_Y_Cb_Cr=rm,frames=frames))
            by={frame:{r['patch']:r for r in rows if r['frame']==frame} for frame in frames}
            common=sorted(set(by[frames[0]])&set(by[frames[1]]))
            pairs=[(by[frames[0]][p],by[frames[1]][p]) for p in common]
            chosen=[(a,b) for a,b in pairs if max(a['q_nominal'],b['q_nominal'])>.2]
            def pair_stats(pairs):
                a,b=zip(*pairs)
                rgb=np.array([v['observed_rgb'] for v in b])-np.array([v['observed_rgb'] for v in a])
                ycc=np.array([v['observed_ycc'] for v in b])-np.array([v['observed_ycc'] for v in a])
                q=np.array([v['q_estimate'] for v in b])-np.array([v['q_estimate'] for v in a])
                return dict(n=len(pairs),rgb_difference_rms=np.sqrt(np.mean(rgb**2,axis=0)),
                    rgb_difference_abs_max=np.max(abs(rgb),axis=0),ycc_difference_rms=np.sqrt(np.mean(ycc**2,axis=0)),
                    q_difference_rms=np.sqrt(np.mean(q*q)),q_difference_abs_max=max(abs(q)),
                    raw_percent_rms=np.sqrt(np.mean(np.array([100*(np.array(vb['raw_wb'])/va['raw_wb']-1) for va,vb in pairs])**2,axis=0)))
            repeat_rows.append(dict(channel=ch,frames=frames,active=pair_stats(chosen),all=pair_stats(pairs)))
            c='RGB'.index(ch);xs=model.xs[15:18]
            first=[r for r in rows if r['frame']==frames[0]];xp=np.sort([r['conditioned_input'] for r in first])
            low=max(v for v in xp if v<xs[1]);high=min(v for v in xp if v>xs[1])
            active_rows=[r for r in rows if r['q_nominal']>.2]
            peakrow=max(first,key=lambda r:r['q_estimate']);ypeak=max(first,key=lambda r:r['q_y'])
            ranges.append(dict(channel=ch,gray_regions_per_frame=len(first),valid_points=len(rows),
                raw_range=[min(r['raw_input'] for r in rows),max(r['raw_input'] for r in rows)],
                conditioned_range=[min(r['conditioned_input'] for r in rows),max(r['conditioned_input'] for r in rows)],
                primary_input_scale_median=np.median([r['conditioned_input']/r['raw_input'] for r in rows]),
                left_side_points=sum(xs[0]<v<xs[1] for v in xp),right_side_points=sum(xs[1]<v<xs[2] for v in xp),
                gap_bracketing_nominal_peak=[low,high],max_gap_in_support=max(np.diff(np.r_[xs[0],xp[(xp>xs[0])&(xp<xs[2])],xs[2]])),
                active_raw_range=[min(r['raw_input'] for r in active_rows),max(r['raw_input'] for r in active_rows)],
                active_conditioned_range=[min(r['conditioned_input'] for r in active_rows),max(r['conditioned_input'] for r in active_rows)],
                observed_max_projection=dict(patch=peakrow['patch'],raw_input=peakrow['raw_input'],conditioned_input=peakrow['conditioned_input'],
                    q=peakrow['q_estimate'],Yq=peakrow['q_y'],RGB=peakrow['observed_rgb'],YCC=peakrow['observed_ycc']),
                observed_max_Y=dict(patch=ypeak['patch'],input=ypeak['conditioned_input'],q=ypeak['q_y'])))
    dump('shape_fits.json',allfits);dump('free_shape_sensitivity.json',sensitivity)
    dump('components.json',components);dump('repeatability.json',repeat_rows);dump('coverage.json',ranges)
    for v in allfits:
        if v['fraction']=='0.5':print('SHAPE',v['channel'],v['branch'],v['response'],[(k['shape'],round(k['rmse'],3),round(k['gain'],3)) for k in v['fits']],flush=True)
    print('FREE',[{k:v for k,v in r.items() if k not in ('parameters',)} for r in sensitivity if r['fraction']=='0.5'],flush=True)
    print('COMPONENTS',[(r['channel'],r['frame'],np.round(r['gain_Y_Cb_Cr'],3).tolist()) for r in components],flush=True)
    print('REPEAT',[(r['channel'],r['active']) for r in repeat_rows],flush=True)


def diagnostics():
    model=f.FieldModel();data=read('measure-0.5.json');points=data['points']
    grey=[r for r in points if r['gray'] and not r['excluded'] and r['q_nominal']>.2]
    first={ch:min(r['index'] for r in grey if r['channel']==ch) for ch in 'RGB'}
    y_gains={r['channel']:r['gain_Y_Cb_Cr'][0] for r in read('components.json') if r['frame']=='pooled'}
    def learn(rows):
        gains={}
        for ch in 'RGB':
            rr=[r for r in rows if r['channel']==ch]
            p=np.array([r['predicted_ycc'][0] for r in rr]);o=np.array([r['observed_ycc'][0] for r in rr])
            mask=abs(p)>.08
            gains[ch]=float(p[mask]@o[mask]/(p[mask]@p[mask])) if mask.any() else 1.
        pp=np.array([np.array(r['predicted_ycc'][1:])*gains[r['channel']] for r in rows])
        oo=np.array([r['observed_ycc'][1:] for r in rows])
        H=np.linalg.lstsq(pp,oo,rcond=None)[0].T
        return gains,H
    def assess(rows,gains,H):
        pp=np.array([np.array(r['predicted_ycc'])*gains[r['channel']] for r in rows]);pp[:,1:]=pp[:,1:]@H.T
        oo=np.array([r['observed_ycc'] for r in rows]);original=np.array([r['predicted_ycc'] for r in rows])
        return dict(n=len(rows),original_ycc_rmse=np.sqrt(np.mean((oo-original)**2,axis=0)),
            fitted_ycc_rmse=np.sqrt(np.mean((oo-pp)**2,axis=0)),original_RGB_rmse=np.sqrt(np.mean((np.array([r['observed_rgb'] for r in rows])-
            np.array([r['predicted_rgb'] for r in rows]))**2)),
            rows=[dict(frame=r['frame'],patch=r['patch'],channel=r['channel'],observed_ycc=r['observed_ycc'],
                       predicted_ycc=r['predicted_ycc'],candidate_ycc=p) for r,p in zip(rows,pp)])
    gains,H=learn(grey);chromatic=[r for r in points if not r['gray'] and not r['excluded'] and r['q_nominal']>.2]
    validation=[]
    for which in (0,1):
        train=[r for r in grey if (r['index']==first[r['channel']])==(which==0)]
        test=[r for r in grey if r not in train]
        gg,hh=learn(train)
        validation.append(dict(train_repeat=which+1,gains=gg,chroma_matrix=hh,**assess(test,gg,hh)))
    color_assessment=assess(chromatic,gains,H) if chromatic else None
    dump('local_output_candidate.json',dict(scope='Node16 +2, current grey ramp only; experimental diagnostic, not accepted globally',
        luma_channel_gains=gains,chroma_matrix=H,grey_training=assess(grey,gains,H),repeat_holdout=validation,
        chromatic_holdout=color_assessment))
    # Compare to frozen earlier results without reinterpreting their identities.
    prior=json.loads((HERE/'local/bracket_20261103/native_Y_checks.json').read_text())
    cross=dict(earlier_component_fits=prior['component_fits'],ramp_component_fits=read('components.json'),
        warning='Different sampled brightness/hue and quantization phases. Do not average the coefficients into a global correction.')
    dump('cross_session.json',cross)
    # Component means alone cannot identify unknown quantization phase in ISP.
    quant=[]
    for m in read('metadata.json'):
        quant.append(dict(frame=m['frame'],Y_DC=m['quantization']['0'][0],CbCr_DC=m['quantization']['1'][0],
            DC_mean_step=m['quantization']['0'][0]/8))
    dump('quantization.json',dict(tables=quant,
        hypothetical_curve_floor_difference_error_bound_precurve=1,
        hypothetical_curve_floor_error_bound_Y=model.row.coef[0]/1024,
        note='A diagnostic bound, not evidence that the ISP floors at this stage. JPEG IDCT rounding and component quantization remain.'))
    summary=[]
    for ch in 'RGB':
        rr=[r for r in read('free_shape_sensitivity.json') if r['channel']==ch]
        summary.append(dict(channel=ch,scope='Envelope across ROI 35/50/65%, RGB projection/Y, linear/cosine mean fits; not a confidence interval',
            peak_range=[min(r['peak'] for r in rr),max(r['peak'] for r in rr)],
            FWHM_range=[min(r['FWHM'] for r in rr),max(r['FWHM'] for r in rr)],
            amplitude_range=[min(r['amplitude'] for r in rr),max(r['amplitude'] for r in rr)],
            ascending_half_range=[min(r['half_left'] for r in rr),max(r['half_left'] for r in rr)],
            descending_half_range=[min(r['half_right'] for r in rr),max(r['half_right'] for r in rr)]))
    dump('kernel_envelopes.json',summary)
    independent_axis=[]
    for ch in 'RGB':
        rr=[dict(r,conditioned_input=r['raw_input']) for r in points if r['channel']==ch and r['gray'] and not r['excluded']]
        near=np.array([450<r['raw_input']<900 for r in rr])
        for response in ('q_estimate','q_y'):
            yy=np.array([r[response] for r in rr]);bb=bases(rr,model,'mean');fits=[]
            for shape,b in bb.items():
                fitted=regression(b,yy,near);fits.append({k:fitted[k] for k in ('gain','offset','rmse')}|dict(shape=shape))
            independent_axis.append(dict(channel=ch,response=response,axis='RAW_WB proxy',fits=sorted(fits,key=lambda r:r['rmse'])))
    dump('raw_axis_shape_fits.json',independent_axis)
    drift=data['drift'];actual=np.array(drift['direct_ycc'])[:49]
    corrected=np.array(drift['corrected_ycc'])[:49];pred=actual-corrected
    dump('A_correction_check.json',dict(component_order=['Y','Cb','Cr'],regions=49,photo_pairs=1,
        observed_over_predicted_slope=np.sum(actual*pred,axis=0)/np.sum(pred*pred,axis=0),
        residual_rmse=np.sqrt(np.mean(corrected**2,axis=0)),
        note='One A pair across spatial regions. This validates local baseline correction, not 49 independent repetitions.'))
    adjusted_repeats=[]
    for ch in 'RGB':
        rr=[r for r in points if r['channel']==ch and r['gray'] and not r['excluded']]
        frames=sorted({r['frame'] for r in rr})
        first={r['patch']:r for r in rr if r['frame']==frames[0]};second={r['patch']:r for r in rr if r['frame']==frames[1]}
        pairs=[(a,second[patch]) for patch,a in first.items() if max(a['q_nominal'],second[patch]['q_nominal'])>.2]
        def delta(a,b,key):return np.array(b[key])-a[key]
        RGB=np.array([delta(a,b,'observed_rgb')-delta(a,b,'predicted_rgb') for a,b in pairs])
        YCC=np.array([delta(a,b,'observed_ycc')-delta(a,b,'predicted_ycc') for a,b in pairs])
        adjusted_repeats.append(dict(channel=ch,frames=frames,n_regions=len(pairs),
            original_model_input_adjusted_RGB_rms=np.sqrt(np.mean(RGB**2,axis=0)),
            original_model_input_adjusted_YCC_rms=np.sqrt(np.mean(YCC**2,axis=0)),
            main_channel_absolute_max=float(np.max(abs(RGB[:,'RGB'.index(ch)])))))
    dump('repeat_input_adjusted.json',dict(rows=adjusted_repeats,
        note='Subtracts the original model prediction for the small between-repeat change in curve input. Conditional on that model, not direct hardware repeatability.'))
    # CSV contains all 312 primary points, including colours and excluded rows.
    fields=['frame','channel','patch','gray','raw_input','conditioned_input','q_nominal','q_estimate','q_y','excluded']
    fields += [f'{prefix}_{c}' for prefix,channels in [('observed','RGB'),('predicted','RGB'),('observed',['Y','Cb','Cr']),('predicted',['Y','Cb','Cr'])] for c in channels]
    with (OUT/'main-points.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for r in points:
            row={k:r[k] for k in fields if k in r}
            for prefix in ('observed','predicted'):
                row.update({f'{prefix}_{c}':r[prefix+'_rgb'][i] for i,c in enumerate('RGB')})
                row.update({f'{prefix}_{c}':r[prefix+'_ycc'][i] for i,c in enumerate(['Y','Cb','Cr'])})
            writer.writerow(row)
    print('LOCAL OUTPUT',gains,np.round(H,4).tolist(),flush=True)
    print('HOLDOUT',[(v['train_repeat'],v['original_ycc_rmse'],v['fitted_ycc_rmse']) for v in validation],flush=True)
    print('COLORS',color_assessment,flush=True)
    print('ENVELOPES',summary,flush=True)


def validate():
    checks=[];inputs={}
    before=read('before.json')
    changed=[name for name,sha in before.items() if f.sha(ROOT/name)!=sha]
    assert not changed,changed
    checks.append(dict(check='preexisting_artifacts_unchanged',files=len(before),changed=changed))
    for tag in ('formal','reference_only'):
        rows=read(tag+'-inputs.json')['files']
        for row in rows:
            assert f.sha(ROOT/row['file'])==row['sha256'];inputs[row['file']]=row['sha256']
        checks.append(dict(check=tag+'_capture_hashes',files=len(rows)))
    model=read('model.json')
    for name,sha in model['inputs'].items():assert f.sha(ROOT/name)==sha;inputs[name]=sha
    for name in ('field_20261103.py','ramp.html','local/ramp/browser/layout.json',
                 'FIELD_20261103.md','FIELD_20261103_BRACKET.md',
                 'FIELD_20261103.SHA256SUMS','FIELD_20261103_BRACKET.SHA256SUMS',
                 'local/bracket_20261103/native_Y_checks.json','local/bracket_20261103/kernel_points.json'):
        p=HERE/name;inputs[str(p.relative_to(ROOT))]=f.sha(p)
    meta=read('metadata.json');payloads=[]
    for r in meta:
        for kind in ('dng','jpeg'):
            d=r[kind];assert d['iso']==200 and abs(d['exposure_s']-1/15)<1e-12
            assert d['exposure_program']==1 and d['exposure_mode']==1 and d['wb_shotinfo']==1 and d['light_source']==1
            assert d['orientation']==1 and d['f_number']==0
        assert r['dng']['as_shot_neutral']==meta[0]['dng']['as_shot_neutral']
        frame=read('frames/'+r['frame']+'.json');payloads.append(frame['raw']['sensor_payload_sha256'])
        for fraction in ('0.35','0.5','0.65'):
            ps=frame['patches'][fraction];assert len(ps)==52 and len(set(p['id'] for p in ps))==52
            for p in ps:assert p['pixels']>300 and sum(t['pixels'] for t in p['tiles'])==p['pixels']
    assert len(set(payloads))==8
    checks.append(dict(check='metadata_raw_roundtrip_and_roi_inventory',frames=8,unique_sensor_payloads=8,patches_per_frame=52,ROI_variants=3))
    for fraction in ('0.35','0.5','0.65'):
        data=read('measure-'+fraction+'.json');labels=[r['response_label'] for r in data['identity']]
        assert labels==list('ARGBRGBA'),(fraction,labels)
        assert len(data['points'])==312 and sum(r['gray'] for r in data['points'])==294
        assert not any(r['excluded'] for r in data['points'])
        assert all(r['response_label']==r['best_template'] for r in data['template_checks'])
        for r in data['points']:
            if r['channel']=='R' and r['patch']=='skin':
                assert r['observed_ycc'][1]>0 and r['predicted_ycc'][1]<0
        checks.append(dict(check='identity_and_chromatic_counterexample',fraction=fraction,labels=labels,primary_points=312,excluded=0))
    assert len(read('shape_fits.json'))==54
    assert len(read('free_shape_sensitivity.json'))==36
    for r in read('geometry-check.json')['rows']:assert r['edge_points']==576 and r['offset_abs_95']<=5.25
    rerun=read('extraction-rerun.json');assert rerun['frames_compared']==8 and rerun['all_bytes_equal']
    checks.append(dict(check='extraction_rerun_exact_bytes',**rerun))
    with (OUT/'INPUT_SHA256SUMS').open('w') as handle:
        for name,sha in sorted(inputs.items()):handle.write(sha+'  '+name+'\n')
    dump('validation.json',dict(status='PASS',checks=checks,source_files_checked=len(inputs),
        caveats=['Partially clipped markers handled explicitly','Input axis and q remain conditional',
                 'Only two photos per perturbation','Reference take excluded from main analysis']))
    print('VALIDATION PASS',len(checks),'checks;',len(inputs),'frozen sources',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['inventory','extract','geometry','measure','fit','diagnostics','validate'])
    args=parser.parse_args();sys.addaudithook(audit)
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    globals()[args.stage]()


if __name__=='__main__': main()
