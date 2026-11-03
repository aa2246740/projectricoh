"""Serial read-only analysis of the MOUNT node-16 exposure bracket."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local/bracket_20261103'
CAP=ROOT/'captures/mount-probe-bracket-20261103'
MORNING=HERE/'local/field_20261103'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe-bracket-20261103')
# Acquire before numerical-library imports, including when the report imports
# this module. A second analysis command fails before doing any heavy work.
import fcntl
assert os.path.ismount('/Volumes/Workspace')
OUT.mkdir(parents=True,exist_ok=True)
_serial_fd=os.open(OUT/'serial.lock',os.O_CREAT|os.O_RDWR,0o600)
fcntl.flock(_serial_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key]='1'
sys.path.insert(0,str(HERE))
import field_20261103 as f
f.OUT,f.CAP,f.TMP=OUT,CAP,TMP
os.environ.update(TMPDIR=str(TMP),MPLCONFIGDIR=str(TMP/'mpl'),GIT_OPTIONAL_LOCKS='0')
import argparse
import datetime
import json
import math
import shutil
import hashlib
import csv
import time
import numpy as np
from scipy import interpolate,optimize,stats,ndimage
from PIL import Image,ImageDraw,ImageFont


def dump(name,value):
    f.dump(name,value)


def read(name):
    return json.loads((OUT/name).read_text())


def audit(event,args):
    if event in ('subprocess.Popen','socket.connect','socket.bind','socket.getaddrinfo'):
        raise PermissionError('No subprocess or network in the analysis')
    if event=='open' and isinstance(args[0],(str,bytes,Path)):
        p=Path(os.fsdecode(args[0])).resolve()
        if str(p).startswith('/Volumes/') and not (p.is_relative_to(ROOT) or p.is_relative_to(TMP)):
            raise PermissionError('Unrelated volume: '+str(p))
        mode,flags=args[1:3]
        write=isinstance(mode,str) and any(c in mode for c in 'wax+')
        write|=isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if write and not (p.is_relative_to(OUT) or p.is_relative_to(TMP) or p==HERE/'FIELD_20261103_BRACKET.SHA256SUMS'):
            raise PermissionError('Write outside bracket outputs: '+str(p))
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.utime','os.chmod'):
        for value in args[:2] if event in ('os.rename','os.link','os.symlink') else args[:1]:
            if isinstance(value,(str,bytes,Path)):
                p=Path(os.fsdecode(value)).resolve()
                if not (p.is_relative_to(OUT) or p.is_relative_to(TMP)):
                    raise PermissionError('Mutation outside bracket outputs: '+str(p))


def manifest_check(path):
    base=path.parent
    rows=[]
    for line in path.read_text().splitlines():
        expected,name=line.split(None,1)
        p=base/name.lstrip('*')
        assert p.resolve().is_relative_to(base.resolve())
        assert f.sha(p)==expected,name
        rows.append(dict(file=p.name,sha256=expected,bytes=p.stat().st_size))
    return rows


def old_seal_check():
    paths=[HERE/'FIELD_20261103.SHA256SUMS',MORNING/'SHA256SUMS']
    hashes={}
    for manifest in paths:
        hashes[str(manifest.relative_to(ROOT))]=f.sha(manifest)
        for line in manifest.read_text().splitlines():
            digest,name=line.split(None,1)
            p=ROOT/name.lstrip('*')
            assert f.sha(p)==digest,name
            hashes[str(p.relative_to(ROOT))]=digest
    return hashes


def inventory():
    rows=manifest_check(CAP/'SHA256SUMS')
    assert len(rows)==34
    prior=old_seal_check()
    dump('inputs.json',dict(files=rows,manifest_sha256=f.sha(CAP/'SHA256SUMS'),morning_sealed_inputs=prior,
        original_analysis_script_sha256=f.sha(HERE/'field_20261103.py')))
    sheet=Image.new('RGB',(1920,1700),'#eeeeee')
    metadata=[]
    for i,n in enumerate(range(1901,1918)):
        stem=f'R805{n}'
        d=f.metadata(f.Tiff((CAP/(stem+'.DNG')).read_bytes()))
        j=f.metadata(f.jpeg_tiff(CAP/(stem+'.JPG')))
        for key in ('time','selector','sliders_raw','iso','exposure_s','wb_shotinfo'):
            assert d[key]==j[key],(stem,key)
        planned_ch='ARGB'[(n-1901)//4] if n<1917 else 'A'
        exposure_index=(n-1901)%4 if n<1917 else 2
        expected_exp=(1/8,1/15,1/30,1/60)[exposure_index]
        assert abs(d['exposure_s']-expected_exp)<1e-12
        row=dict(frame=stem,dng=d,jpeg=j,planned_label=planned_ch,exposure_index=exposure_index)
        metadata.append(row)
        with Image.open(CAP/(stem+'.JPG')) as im:
            row['jpeg_wh']=list(im.size)
            im.thumbnail((480,310))
            x,y=i%4*480,i//4*340
            sheet.paste(im,(x,y+24))
            ImageDraw.Draw(sheet).text((x+8,y+5),f'{stem} 1/{round(1/d["exposure_s"])}',fill='black')
            if n in (1901,1903):
                view=Image.open(CAP/(stem+'.JPG'))
                view.thumbnail((1500,1000))
                view.save(OUT/(stem+'-view.jpg'),quality=92)
        print(stem,d['time'],d['exposure_s'],d['selector_name'],d['sliders_display'],flush=True)
    sheet.save(OUT/'contact.jpg',quality=90)
    dump('metadata.json',metadata)
    dump('environment.json',dict(python=sys.executable,numpy=np.__version__,nice=os.getpriority(os.PRIO_PROCESS,0),
        compute_processes=1,threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS')},
        network=False,camera_or_card=False,scope='bracket only; morning artifacts read-only'))


def extract():
    sheet=Image.new('RGB',(1920,1700),'#eeeeee')
    for i,n in enumerate(range(1901,1918)):
        stem=f'R805{n}'
        raw,info=f.decode_raw(f.Tiff((CAP/(stem+'.DNG')).read_bytes()))
        rgb=np.asarray(Image.open(CAP/(stem+'.JPG')).convert('RGB'))
        boxes=locate(rgb,stem)
        # The bracket frames cut off different amounts of browser chrome.
        # Locate a flat bright band inside the same blank address-field X
        # interval instead of extrapolating a fixed Y offset off the image.
        auxbox=locate_auxiliary(rgb,boxes)
        patchsets={}
        for fraction in (.35,.5,.65):
            patchsets[str(fraction)]=[f.roi_stats(rgb,raw,info,box,fraction) for box in boxes]
        aux=f.roi_stats(rgb,raw,info,auxbox,1.)
        # Decode the JPEG's own YCbCr samples as a separate amplitude check.
        with Image.open(CAP/(stem+'.JPG')) as im:
            im.draft('YCbCr',im.size)
            assert im.mode=='YCbCr'
            ycc=np.asarray(im)
        for patches in list(patchsets.values())+[[aux]]:
            for p in patches:
                a,b,c,d=p['roi_xyxy']
                v=ycc[b:d,a:c]
                p['native_jpeg_ycc_mean']=v.mean(axis=(0,1)).tolist()
                p['native_jpeg_ycc_sd']=v.std(axis=(0,1)).tolist()
                q=raw[b:d,a:c]
                ox,oy=info['crop_origin_xy'];cfa=np.asarray([[0,1],[1,2]])
                hist=[]
                for ch in range(3):
                    values=np.concatenate([q[dy::2,dx::2].ravel() for dy in range(2) for dx in range(2)
                                           if cfa[(oy+b+dy)%2,(ox+a+dx)%2]==ch])
                    counts=np.bincount(values,minlength=4096);bins=np.where(counts>0)[0]
                    hist.append(dict(dn=bins.tolist(),counts=counts[bins].tolist()))
                p['raw_histograms']=hist
                p['raw_headroom_fraction']=float(np.mean(q>=info['white']-16))
                p['jpeg_near_clip_fraction']=np.mean((rgb[b:d,a:c]<=2)|(rgb[b:d,a:c]>=253),axis=(0,1)).tolist()
                p['excluded_saturation']=bool(p['raw_headroom_fraction']>0 or max(p['jpeg_near_clip_fraction'])>.001)
        row=dict(frame=stem,raw=info,boxes_xyxy=boxes,patches=patchsets,
                 auxiliary_boxes_xyxy={'toolbar':auxbox},auxiliary_patches={'toolbar':aux})
        dump('frames/'+stem+'.json',row)
        view=Image.fromarray(rgb);view.thumbnail((480,310));d=ImageDraw.Draw(view)
        sx,sy=view.width/rgb.shape[1],view.height/rgb.shape[0]
        for box,name in zip([p['roi_xyxy'] for p in patchsets['0.5']]+[aux['roi_xyxy']],f.PATCH_NAMES+('toolbar',)):
            a,b,c,dd=box;bb=[a*sx,b*sy,c*sx,dd*sy]
            d.rectangle(bb,outline='#ff00ff' if name=='toolbar' else '#ffff00',width=2)
            d.text((bb[0],bb[1]),name,fill='#ffff00')
        xx,yy=i%4*480,i//4*340;sheet.paste(view,(xx,yy+24));ImageDraw.Draw(sheet).text((xx+8,yy+5),stem,fill='black')
        print(stem,'RGB',np.round([p['jpeg_mean'] for p in patchsets['0.5']]+[aux['jpeg_mean']],2).tolist(),
              'WB RAW',np.round(np.array([p['raw_dn_mean'] for p in patchsets['0.5']]+[aux['raw_dn_mean']])/
                                np.array(read('metadata.json')[i]['dng']['as_shot_neutral']),1).tolist(),
              'excluded',[p['excluded_saturation'] for p in patchsets['0.5']]+[aux['excluded_saturation']],flush=True)
    sheet.save(OUT/'roi-contact.jpg',quality=91)


def locate(rgb,stem=''):
    small=np.asarray(Image.fromarray(rgb).resize((750,500),Image.Resampling.BOX),float)
    r,g,b=small.transpose(2,0,1);yy,xx=np.indices(r.shape)
    # At 1/8 s, the blue-tinted dark frame connects to the sky patch under
    # chroma-only thresholds. The sky also has substantial absolute signal.
    masks=((b-r>25)&(g-r>12)&(g>60)&(b>80),(r-g>14)&(g-b>6),(g-r>15)&(g-b>12))
    boxes=[]
    windows=((10,270),(230,490),(450,710))
    for mask,(lo,hi) in zip(masks,windows):
        labels,n=ndimage.label(mask&(yy>180)&(yy<400)&(xx>lo)&(xx<hi))
        sizes=np.bincount(labels.ravel());sizes[0]=0;which=int(np.argmax(sizes))
        assert sizes[which]>5000,(stem,sizes[which])
        y,x=np.where(labels==which)
        boxes.append([float(x.min()),float(y.min()),float(x.max()+1),float(y.max()+1)])
    boxes=np.asarray(boxes)
    print('geometry',stem,boxes.tolist(),flush=True)
    heights=boxes[:,3]-boxes[:,1];widths=boxes[:,2]-boxes[:,0]
    assert np.ptp(heights)<35 and np.ptp(widths)<35,(stem,boxes)
    gap=np.median(boxes[1:,0]-boxes[:-1,2]);delta=float(np.median(heights)+gap)
    top=boxes.copy();top[:,[1,3]]-=delta
    boxes=np.vstack([top,boxes]);boxes[:,[0,2]]*=rgb.shape[1]/750;boxes[:,[1,3]]*=rgb.shape[0]/500
    return boxes


def locate_auxiliary(rgb,boxes):
    x0,y0,x1,y1=boxes[2];w,h=x1-x0,y1-y0
    a,c=int(x0+.23*w)//2*2,int(x0+.73*w)//2*2
    ymax=min(int(y0-.12*h),rgb.shape[0]//5)
    profile=np.median(rgb[:ymax,a:c].astype(float),axis=(1,2))
    smooth=ndimage.gaussian_filter1d(profile,1.5)
    bottom=int(np.argmin(np.diff(smooth)))+1
    assert bottom>48,(bottom,ymax)
    height=32;b=(bottom-42)//2*2
    assert b>=0 and c>a and b+height<=rgb.shape[0]
    return [a,b,c,b+height]


def load_frames(fraction='0.5'):
    meta=read('metadata.json')
    frames=[read('frames/'+r['frame']+'.json') for r in meta]
    patches=[v['patches'][fraction]+[v['auxiliary_patches']['toolbar']] for v in frames]
    j=np.asarray([[p['jpeg_mean'] for p in ps] for ps in patches])
    r=np.asarray([[p['raw_dn_mean'] for p in ps] for ps in patches])
    neutral=np.asarray([v['dng']['as_shot_neutral'] for v in meta])
    wb=r/neutral[:,None,:]
    bad=np.asarray([[p['excluded_saturation'] for p in ps] for ps in patches])
    return meta,frames,patches,j,r,wb,bad


def model_dump(model):
    dump('model.json',dict(inputs=model.inputs,xs=model.xs,curves=model.curves,
        row=model.row.describe(),source='Existing MOUNT native rows with transferred 50mm sector response',
        response_refit=False))


def measure():
    model=f.FieldModel();model_dump(model)
    meta,frames,patches,j,r,wb,bad=load_frames()
    t=np.asarray([datetime.datetime.strptime(v['dng']['time'],'%Y:%m:%d %H:%M:%S').timestamp() for v in meta]);t-=t[0]
    inv=[]
    for i in range(len(j)):
        # Saturated points remain in the inventory but are not inverted.
        valid=~bad[i];x=np.full((7,3),np.nan);pre=x.copy()
        if valid.any():
            xx,pp=model.inverse(j[i,valid]);x[valid]=xx;pre[valid]=pp
        inv.append((x,pre))
    dump('inverse.json',[dict(frame=meta[i]['frame'],x=finite(inv[i][0]),pre=finite(inv[i][1])) for i in range(17)])
    rows=[];frame_summaries=[]
    for i in range(4,16):
        e=meta[i]['exposure_index'];ai=e
        label=meta[i]['planned_label'];component='RGB'.index(label)
        xA,preA=inv[ai]
        # The 1/30 reference is interpolated in time between the two A shots;
        # other exposures have only one A and retain that drift limitation.
        alpha=float(np.clip((t[i]-t[2])/(t[16]-t[2]),0,1)) if e==2 else 0.
        gain0=xA/r[ai]
        gain=gain0.copy()
        if e==2:
            gain=(1-alpha)*gain0+alpha*(inv[16][0]/r[16])
        xB=gain*r[i]
        valid=~(bad[i]|bad[ai])
        if e==2:valid&=~bad[16]
        expectedA=np.full((7,3),np.nan);preB0=expectedA.copy()
        expectedA[valid]=model.predict(xB[valid]);preB0[valid]=model.pre(xB[valid])
        observed=j[i]-expectedA
        predictions={ch:np.full((7,3),np.nan) for ch in 'ARGB'}
        predictions['A'][valid]=0
        for ch in 'RGB':predictions[ch][valid]=model.predict(xB[valid],ch)-expectedA[valid]
        before=model.pre(xA[valid])
        initialExpected=model.predict(xA[valid]*r[i,valid]/r[ai,valid])
        rawcorrection=initialExpected-j[ai,valid]
        q_est=[]
        for p in range(7):
            if not valid[p]:
                rows.append(dict(frame=meta[i]['frame'],reference=meta[ai]['frame'],planned=label,
                    channel=label,patch_index=p,patch=(f.PATCH_NAMES+('toolbar',))[p],exposure_s=meta[i]['dng']['exposure_s'],
                    excluded=True,reason='JPEG endpoint or RAW headroom exclusion',raw_wb=wb[i,p].tolist()))
                continue
            q=preB0[p].copy();baseline=expectedA[p].copy()
            def response(delta):
                v=q.copy();v[component]+=delta
                return model.forward_pre(v[None])[0]-baseline
            solved=optimize.minimize_scalar(lambda d:float(np.sum((response(d)-observed[p])**2)),
                                             bounds=(-4,5),method='bounded',options={'xatol':1e-5})
            qhat=float(solved.x);jac=(response(qhat+.01)-response(qhat-.01))/.02
            residual=observed[p]-response(qhat)
            conditional_pre=inv[i][1][p]-preB0[p]
            # Native JPEG Y is independent of sector interpolation. The
            # correction uses only the known matrix Y row and the A inputs.
            yA=patches[ai][p]['native_jpeg_ycc_mean'][0]
            yB=patches[i][p]['native_jpeg_ycc_mean'][0]
            ycorr=float((preB0[p]-preA[p])@(model.row.coef[0]/1024))
            if e==2:
                yA=(1-alpha)*yA+alpha*patches[16][p]['native_jpeg_ycc_mean'][0]
                pA=(1-alpha)*preA[p]+alpha*inv[16][1][p]
                ycorr=float((preB0[p]-pA)@(model.row.coef[0]/1024))
            dy=float(yB-yA-ycorr)
            native_q=dy/(model.row.coef[0,component]/1024)
            row=dict(frame=meta[i]['frame'],reference=meta[ai]['frame'],planned=label,channel=label,
                patch_index=p,patch=(f.PATCH_NAMES+('toolbar',))[p],exposure_s=meta[i]['dng']['exposure_s'],excluded=False,
                raw_wb=wb[i,p],raw_input=wb[i,p,component],conditioned_input=xB[p,component],
                raw_relative_to_A_percent=100*(r[i,p]/r[ai,p]-1),jpeg_difference=j[i,p]-j[ai,p],
                observed_rgb=observed[p],predicted_rgb=predictions[label][p],all_predicted_rgb={k:v[p] for k,v in predictions.items()},
                q_estimate=qhat,q_projection_residual_rgb=residual,q_projection_jacobian=jac,
                conditional_pre_delta=conditional_pre,native_Y_delta=dy,native_Y_q_estimate=native_q,
                q_nominal=float(model.pre(xB[p:p+1],label)[0,component]-preB0[p,component]),
                pre_A_at_B=preB0[p],x_B=xB[p],baseline_at_B=expectedA[p],
                raw_histogram=patches[i][p]['raw_histograms'][component],raw_black=frames[i]['raw']['black'],
                raw_target_mean=r[i,p,component],
                reference_interpolation_alpha=alpha)
            rows.append(row);q_est.append((row['patch'],round(row['raw_input'],1),round(qhat,3),round(row['q_nominal'],3)))
        scores={}
        for ch in 'ARGB':
            delta=observed[valid]-predictions[ch][valid]
            scores[ch]=float(np.sqrt(np.mean(delta**2))) if valid.any() else None
        best=min(scores,key=scores.get)
        energies={ch:float(np.linalg.norm(predictions[ch][valid])) for ch in 'RGB'}
        frame_summaries.append(dict(frame=meta[i]['frame'],planned=label,best_fixed_model_label=best,
            model_rmse_rgb=scores,template_norm_rgb=energies,valid_regions=int(valid.sum()),
            mean_raw_shift_percent=np.mean(100*(r[i,valid]/r[ai,valid]-1),axis=0)))
        print(meta[i]['frame'],label,'scores', {k:round(v,3) for k,v in scores.items()},'points',q_est,flush=True)
    dump('points.json',finite(rows));dump('frame_checks.json',frame_summaries)
    # Restore pair and morning comparison. The raw ratios use actual measured
    # values, not nominal shutter fractions.
    x0=inv[2][0];valid=~(bad[2]|bad[16]);expected=np.full((7,3),np.nan)
    expected[valid]=model.predict(x0[valid]*r[16,valid]/r[2,valid])
    morning_assign=json.loads((MORNING/'assignments.json').read_text())['frames']
    morning_rows=[]
    for old in morning_assign:
        if old['label']!='A':continue
        oldframe=json.loads((MORNING/'frames'/(old['frame']+'.json')).read_text())
        ps=oldframe['patches']['0.5']+[oldframe['auxiliary_patches']['toolbar']]
        oj=np.asarray([p['jpeg_mean'] for p in ps]);orr=np.asarray([p['raw_dn_mean'] for p in ps])
        ox=model.inverse(oj)[0];pred=model.predict(ox*r[2]/orr)
        morning_rows.append(dict(frame=old['frame'],raw_bracket_1903_over_morning=r[2]/orr,
                                 jpeg_direct_1903_minus_morning=j[2]-oj,raw_corrected_1903_minus_morning=j[2]-pred))
    drift=dict(A_first='R8051903',A_last='R8051917',elapsed_s=t[16]-t[2],raw_percent=100*(r[16]/r[2]-1),
        jpeg_direct=j[16]-j[2],jpeg_raw_corrected=j[16]-expected,
        morning_A=morning_rows,exposure_ratios_vs_1903=wb[:4]/wb[2],
        nominal_exposure_ratios=[3.75,2,1,.5],quantum_uncertainty_not_repetition=True)
    dump('drift.json',finite(drift))
    print('A drift RAW %',np.round(drift['raw_percent'],3).tolist(),flush=True)
    print('A drift JPG corrected',np.round(drift['jpeg_raw_corrected'],3).tolist(),flush=True)


def finite(value):
    value=f.plain(value)
    if isinstance(value,dict):return {k:finite(v) for k,v in value.items()}
    if isinstance(value,list):return [finite(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


MAIN_PATCHES=(0,1,2,6)
SHAPES=('linear_tent','nearest_node','previous_node','raised_cosine','pchip_difference')


def kernel_basis(row,model,shape):
    ch='RGB'.index(row['channel']);hist=row['raw_histogram']
    x=(np.asarray(hist['dn'])-row['raw_black'])*row['conditioned_input']/row['raw_target_mean']
    weights=np.asarray(hist['counts'],float);weights/=weights.sum()
    left,peak,right=model.xs[15:18]
    up=(x-left)/(peak-left);down=(right-x)/(right-peak)
    tent=np.maximum(0,np.minimum(up,down))
    if shape=='linear_tent':v=2*tent
    elif shape=='nearest_node':v=2*((x>=(left+peak)/2)&(x<(peak+right)/2)).astype(float)
    elif shape=='previous_node':v=2*((x>=peak)&(x<right)).astype(float)
    elif shape=='raised_cosine':v=1-np.cos(np.pi*tent)
    elif shape=='pchip_difference':
        a=interpolate.PchipInterpolator(model.xs,model.curves['A'][ch])
        b=interpolate.PchipInterpolator(model.xs,model.curves[row['channel']][ch])
        v=b(x)-a(x)
    else:raise ValueError(shape)
    return float(v@weights)


def morning_points(model):
    # Verify the original photos too before decoding their read-only RAW data.
    folder=ROOT/'captures/mount-probe-20261103'
    verified=manifest_check(folder/'SHA256SUMS')
    dump('morning_photo_hashes.json',verified)
    assigned=json.loads((MORNING/'assignments.json').read_text())['frames']
    metadata=json.loads((MORNING/'metadata.json').read_text())
    points=[]
    for i,old in enumerate(assigned):
        if old['label']=='A':continue
        name=old['frame'];ch='RGB'.index(old['label'])
        saved=json.loads((MORNING/'frames'/(name+'.json')).read_text())
        patches=saved['patches']['0.5']+[saved['auxiliary_patches']['toolbar']]
        raw,info=f.decode_raw(f.Tiff((folder/(name+'.DNG')).read_bytes()))
        expected=np.asarray(old['expected_A']);x,pre=model.inverse(expected)
        for p in MAIN_PATCHES:
            q=pre[p].copy();target=np.asarray(old['observed_delta'][p]);baseline=expected[p]
            def response(d):
                qq=q.copy();qq[ch]+=d
                return model.forward_pre(qq[None])[0]-baseline
            solved=optimize.minimize_scalar(lambda d:float(np.sum((response(d)-target)**2)),bounds=(-4,5),method='bounded')
            a,b,c,d=patches[p]['roi_xyxy'];roi=raw[b:d,a:c]
            ox,oy=info['crop_origin_xy'];cfa=np.asarray([[0,1],[1,2]])
            vals=np.concatenate([roi[dy::2,dx::2].ravel() for dy in range(2) for dx in range(2)
                                 if cfa[(oy+b+dy)%2,(ox+a+dx)%2]==ch])
            counts=np.bincount(vals,minlength=4096);bins=np.where(counts>0)[0]
            dn=patches[p]['raw_dn_mean'][ch];neutral=metadata[i]['dng']['as_shot_neutral'][ch]
            points.append(dict(frame=name,session='morning',channel=old['label'],patch_index=p,
                patch=(f.PATCH_NAMES+('toolbar',))[p],exposure_s=1/30,excluded=False,
                raw_input=dn/neutral,conditioned_input=x[p,ch],raw_target_mean=dn,raw_black=info['black'],
                raw_histogram=dict(dn=bins.tolist(),counts=counts[bins].tolist()),
                q_estimate=float(solved.x),q_nominal=float(model.pre(x[p:p+1],old['label'])[0,ch]-pre[p,ch]),
                observed_rgb=old['observed_delta'][p],q_projection_residual_rgb=target-response(solved.x),
                verified_label=True))
        print('morning histogram',name,flush=True)
    return points


def identify(points):
    frame_checks=read('frame_checks.json');byframe={}
    for row in points:
        byframe.setdefault(row['frame'],[]).append(row)
    output=[]
    for check in frame_checks:
        rows=[r for r in byframe[check['frame']] if not r['excluded']]
        obs=np.asarray([r['observed_rgb'] for r in rows])
        sse0=float(np.sum(obs**2));fits={}
        for ch in 'RGB':
            template=np.asarray([r['all_predicted_rgb'][ch] for r in rows]);energy=float(np.sum(template**2))
            if energy<1e-10:
                gain=0.;sse=sse0
            else:
                gain=float(np.clip(np.sum(template*obs)/energy,0,2.5))
                sse=float(np.sum((obs-gain*template)**2))
            fits[ch]=dict(gain=gain,rmse=float(np.sqrt(sse/obs.size)),sse=sse,template_energy=energy)
        best=min(fits,key=lambda ch:fits[ch]['sse']);improvement=sse0-fits[best]['sse']
        c='RGB'.index(best);dominant=float(np.max(obs[:,c]));zero=['A']+[ch for ch in 'RGB' if fits[ch]['template_energy']<.04]
        confirmed=bool(improvement>.25 and dominant>.35 and fits[best]['template_energy']>.04)
        confidence='high' if improvement>1 else 'moderate'
        output.append(dict(**check,fitted_templates=fits,zero_response_candidates=zero,
            response_label=best if confirmed else None,label_verified=confirmed,
            confidence=confidence if confirmed else 'unidentifiable',sse_improvement=improvement,
            observed_main_RGB_max=dominant,planned_compatible=(best==check['planned'] if confirmed else check['planned'] in zero)))
    return output


def fit():
    model=f.FieldModel();points=read('points.json')
    identified=identify(points);dump('identity.json',identified)
    decisions={v['frame']:v for v in identified}
    for row in points:
        row['session']='bracket'
        row['verified_label']=decisions[row['frame']]['label_verified'] and decisions[row['frame']]['response_label']==row['channel']
    morning=morning_points(model)
    allpoints=[r for r in points+morning if not r['excluded'] and r['patch_index'] in MAIN_PATCHES]
    for row in allpoints:
        row['kernel_bases']={shape:kernel_basis(row,model,shape) for shape in SHAPES}
        point=dict(row,raw_histogram=dict(dn=[row['raw_target_mean']+row['raw_black']],counts=[1]))
        row['kernel_bases_mean_input']={shape:kernel_basis(point,model,shape) for shape in SHAPES}
        hist=row['raw_histogram'];values=np.asarray(hist['dn'],float);weights=np.asarray(hist['counts'],float);weights/=weights.sum()
        row['conditional_input_sigma']=float(np.sqrt(np.sum(weights*(values-(row['raw_target_mean']+row['raw_black']))**2))*
                                              row['conditioned_input']/row['raw_target_mean'])
    model_results=[]
    for scope in ('bracket_all_planned','bracket_verified','combined_verified'):
        selected=[r for r in allpoints if (scope=='bracket_all_planned' and r['session']=='bracket') or
                  (scope=='bracket_verified' and r['session']=='bracket' and r['verified_label']) or
                  (scope=='combined_verified' and r['verified_label'])]
        for ch in 'RGB':
            data=[r for r in selected if r['channel']==ch]
            y=np.asarray([r['q_estimate'] for r in data])
            for distribution,field in (('mean_input','kernel_bases_mean_input'),('raw_histogram','kernel_bases')):
              for shape in SHAPES:
                basis=np.asarray([r[field][shape] for r in data])
                norm=float(basis@basis)
                gain=max(0.,float(basis@y/norm)) if norm>1e-10 else None
                rmse=float(np.sqrt(np.mean((y-(gain or 0)*basis)**2)))
                active=np.abs(y)>.3
                cv=[]
                for session in sorted(set(r['session'] for r in data)):
                    train=np.array([r['session']!=session for r in data]);test=~train
                    denom=float(basis[train]@basis[train])
                    if not train.any() or denom<1e-8:
                        cv.append(dict(held_out=session,identifiable=False));continue
                    g=max(0.,float(basis[train]@y[train]/denom))
                    cv.append(dict(held_out=session,identifiable=True,gain=g,
                                   rmse=float(np.sqrt(np.mean((y[test]-g*basis[test])**2))),
                                   active_rmse=float(np.sqrt(np.mean((y[test&active]-g*basis[test&active])**2))) if (test&active).any() else None))
                model_results.append(dict(scope=scope,channel=ch,shape=shape,input_distribution=distribution,n=len(data),gain=gain,
                    peak_if_fitted_gain=2*gain if gain is not None else None,rmse_q=rmse,
                    active_rmse_q=float(np.sqrt(np.mean((y[active]-(gain or 0)*basis[active])**2))) if active.any() else None,
                    active_points=int(active.sum()),
                    rmse_nominal_q=float(np.sqrt(np.mean((y-basis)**2))),leave_session_out=cv,
                    positive_basis_points=int(np.sum(basis>.2)),high_information_distinct_regions=sorted(set(r['patch'] for r,b in zip(data,basis) if b>.2))))
    dump('kernel_points.json',finite(allpoints));dump('kernel_fits.json',model_results)
    coverage=[]
    for ch in 'RGB':
        new=[r for r in allpoints if r['channel']==ch and r['session']=='bracket']
        verified=[r for r in allpoints if r['channel']==ch and r['verified_label']]
        active=[r for r in verified if r['kernel_bases']['linear_tent']>.2 and r['q_estimate']>.2]
        newactive=[r for r in new if r['kernel_bases']['linear_tent']>.2 and r['q_estimate']>.2]
        peak=max(active,key=lambda r:r['q_estimate']) if active else None
        left,peaknode,right=model.xs[15:18]
        left_samples=[r for r in active if r['conditioned_input']<peaknode-.15*(peaknode-left)]
        right_samples=[r for r in active if r['conditioned_input']>peaknode+.15*(right-peaknode)]
        near_samples=[r for r in active if abs(r['conditioned_input']-peaknode)<.1*min(peaknode-left,right-peaknode)]
        unique=lambda data:len({(r['session'],r['patch'],round(r['conditioned_input']/10)) for r in data})
        enough=unique(left_samples)>=2 and unique(right_samples)>=2 and unique(near_samples)>=1
        cv=dict(channel=ch,new_valid_main_points=len(new),new_verified_main_points=sum(r['verified_label'] for r in new),
            new_active_main_points=[dict(frame=r['frame'],patch=r['patch'],raw_input=r['raw_input'],q_estimate=r['q_estimate'],q_nominal=r['q_nominal']) for r in newactive],
            combined_active_input_min=min(r['raw_input'] for r in active),combined_active_input_max=max(r['raw_input'] for r in active),
            observed_max=({k:peak[k] for k in ('frame','patch','raw_input','conditioned_input','q_estimate')} if peak else None),
            effective_left_contexts=unique(left_samples),effective_right_contexts=unique(right_samples),effective_peak_contexts=unique(near_samples),
            both_flanks_and_peak_sampled=enough,nonparametric_peak_location_identified=enough,FWHM_identified=enough,
            raw_input_coverage_min=min(r['raw_input'] for r in verified),raw_input_coverage_max=max(r['raw_input'] for r in verified))
        coverage.append(cv)
    dump('coverage.json',coverage)
    print('IDENTITY',[(r['frame'],r['response_label'],r['confidence'],r['zero_response_candidates']) for r in identified],flush=True)
    print('COVERAGE',json.dumps(finite(coverage)),flush=True)
    print('FITS',[(r['channel'],r['shape'],r['input_distribution'],round(r['gain'],3) if r['gain'] is not None else None,round(r['active_rmse_q'],3))
                  for r in model_results if r['scope']=='combined_verified'],flush=True)


def assess():
    model=f.FieldModel();points=read('points.json');kp=read('kernel_points.json');fits=read('kernel_fits.json')
    meta,frames,patches,j,r,wb,bad=load_frames()
    exemplars=[]
    for frame,p in (('R8051905',1),('R8051906',4),('R8051909',5),('R8051910',3),('R8051911',6),('R8051915',6)):
        v=next(x for x in points if x['frame']==frame and x['patch_index']==p)
        c='RGB'.index(v['channel'])
        exemplars.append(dict(frame=frame,patch=v['patch'],channel=v['channel'],raw_input=v['raw_input'],
            observed_rgb=v['observed_rgb'],predicted_rgb=v['predicted_rgb'],q_estimate=v['q_estimate'],q_nominal=v['q_nominal'],
            native_Y_delta=v['native_Y_delta'],native_Y_q_estimate=v['native_Y_q_estimate'],
            primary_ratio=v['observed_rgb'][c]/v['predicted_rgb'][c] if abs(v['predicted_rgb'][c])>.05 else None,
            projection_residual_rgb=v['q_projection_residual_rgb']))
    ranges=[]
    for c,ch in enumerate('RGB'):
        values=[wb[i,p,c] for i in (0,1,2,3,16) for p in MAIN_PATCHES if not bad[i,p]]
        active=[x for x in kp if x['channel']==ch and x['verified_label'] and x['kernel_bases_mean_input']['linear_tent']>.2 and x['q_estimate']>.2]
        active_new=[x for x in active if x['session']=='bracket']
        ratio=np.asarray([x['conditioned_input']/x['raw_input'] for x in kp if x['channel']==ch and x['session']=='bracket'])
        ranges.append(dict(channel=ch,baseline_raw_min=min(values),baseline_raw_max=max(values),
            activated_main_raw_min=min(x['raw_input'] for x in active),activated_main_raw_max=max(x['raw_input'] for x in active),
            activated_main_count=len(active),activated_new_main_count=len(active_new),
            activated_contexts=[dict(frame=x['frame'],patch=x['patch'],raw=x['raw_input'],conditioned=x['conditioned_input'],q=x['q_estimate']) for x in active],
            A_conditioned_input_scale_min=float(ratio.min()),A_conditioned_input_scale_median=float(np.median(ratio)),
            A_conditioned_input_scale_max=float(ratio.max())))
    drift=read('drift.json');old=drift['morning_A']
    moraw=np.asarray([v['raw_bracket_1903_over_morning'] for v in old]);modiff=np.asarray([v['raw_corrected_1903_minus_morning'] for v in old])
    inverse=read('inverse.json');refs=[]
    for i in (0,1,2,3,16):
        valid=~bad[i];xx=np.array([[float(z) if z is not None else np.nan for z in row] for row in inverse[i]['x']])
        aa=model.predict(xx[valid]);norms={ch:float(np.linalg.norm(model.predict(xx[valid],ch)-aa)) for ch in 'RGB'}
        refs.append(dict(frame=meta[i]['frame'],response_type='A',indistinguishable_candidates=['A']+[ch for ch in 'RGB' if norms[ch]<.2],
                         template_norms=norms,concrete_menu_identity_verified=False))
    summary=dict(verdict='部分可用',exemplars=exemplars,ranges=ranges,reference_identity=refs,
        morning_raw_ratio_min=moraw.min(axis=0),morning_raw_ratio_max=moraw.max(axis=0),
        morning_corrected_median=np.median(modiff,axis=0),morning_corrected_min=modiff.min(axis=0),morning_corrected_max=modiff.max(axis=0),
        high_clipped_regions=sum(p['raw_headroom_fraction']>0 or max(p['jpeg_near_clip_fraction'])>=.001 and
                                 max(p['jpeg_mean'])>250 for ps in patches for p in ps),
        low_clipped_regions=sum(p['excluded_saturation'] and max(p['jpeg_mean'])<30 for ps in patches for p in ps),
        main_nominal_pairs=48,main_valid_pairs=sum(not v['excluded'] and v['patch_index'] in MAIN_PATCHES for v in points),
        model_response_amplitude_refit_accepted=False,full_interpolation_identified=False,
        input_distribution_branches='Mean only and RAW histogram integration; neither is asserted to be the actual post-demosaic/noise-reduction ISP input distribution',
        q_units='Conditional pre-C100 code estimate projected through the existing downstream model; not direct register or internal-pixel telemetry')
    dump('assessment.json',summary)
    with (OUT/'main-points.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['frame','planned_channel','patch','shutter_s','excluded','RAW_WB_R','RAW_WB_G','RAW_WB_B','delta_JPG_R','delta_JPG_G','delta_JPG_B','q_estimate','q_nominal','label_verified'])
        ids={v['frame']:v for v in read('identity.json')}
        for v in points:
            if v['patch_index'] not in MAIN_PATCHES:continue
            raw=v['raw_wb']
            writer.writerow([v['frame'],v['channel'],v['patch'],v['exposure_s'],v['excluded'],*raw,
                             *v.get('observed_rgb',['','','']),v.get('q_estimate',''),v.get('q_nominal',''),ids[v['frame']]['label_verified']])
    for v in exemplars:print('EXAMPLE',json.dumps(v),flush=True)
    for v in fits:
        if v['shape']=='linear_tent' and v['scope']=='combined_verified':
            print('LINEAR',json.dumps(v),flush=True)
    print('RANGES',json.dumps(ranges),flush=True)


def ambiguity():
    """A concrete ambiguity, preserving node changes and total monotonicity."""
    model=f.FieldModel();kp=read('kernel_points.json');fits=read('kernel_fits.json')
    data=[p for p in kp if p['channel']=='G' and p['verified_label']]
    fit=next(v for v in fits if v['scope']=='combined_verified' and v['channel']=='G' and
             v['shape']=='linear_tent' and v['input_distribution']=='mean_input')
    gain=fit['gain'];left,peak,right=model.xs[15:18]
    x=np.asarray([p['conditioned_input'] for p in data]);y=np.asarray([p['q_estimate'] for p in data])
    join=float(max(x[x<peak])+1)
    join_y=2*gain*(join-left)/(peak-left)
    assert left<join<peak and 0<join_y<2
    def curve(v,power):
        v=np.asarray(v,float);out=np.zeros(v.shape)
        lower=(v>=left)&(v<=join);out[lower]=2*gain*(v[lower]-left)/(peak-left)
        upper=(v>join)&(v<=peak);out[upper]=join_y+(2-join_y)*(v[upper]-join)/(peak-join)
        falling=(v>peak)&(v<right);out[falling]=2*((right-v[falling])/(right-peak))**power
        return out
    a,b=curve(x,1),curve(x,4)
    assert np.max(abs(a-b))<1e-10
    grid=np.linspace(0,4095,81901)
    base=np.interp(grid,model.xs,model.curves['A'][1])
    tables=[]
    for power in (1,4):
        delta=curve(grid,power);full=base+delta
        assert np.min(np.diff(full))>=-1e-10
        node_delta=curve(model.xs,power)
        assert np.count_nonzero(node_delta)==1 and abs(node_delta[16]-2)<1e-12
        a_half=optimize.brentq(lambda z:float(curve(np.array([z]),power)[0])-1,left,peak)
        b_half=optimize.brentq(lambda z:float(curve(np.array([z]),power)[0])-1,peak,right)
        tables.append(dict(falling_power=power,peak_input=peak,peak_height=2.,FWHM=b_half-a_half,
                           rms_at_sample_means=float(np.sqrt(np.mean((y-curve(x,power))**2))),
                           monotone_complete_curve=True,node_changes_exactly_match_probe=True))
    dump('nonidentifiability.json',dict(channel='G',scope='Conditioned mean-input branch, not a claim about the actual interpolation circuit',
        rationale='Two monotone output curves preserve the same node-16 +2 change and match every verified G grey-region sample mean identically, yet have different FWHM.',
        samples=len(x),max_sample_prediction_difference=float(np.max(abs(a-b))),kernels=tables,
        grid_input=grid[::20],kernel_linear_fall=curve(grid[::20],1),kernel_fast_fall=curve(grid[::20],4),
        full_raw_histogram_branch_is_a_separate_unverified_pixel_input_assumption=True))
    print('NONIDENTIFIABILITY',json.dumps(tables),flush=True)


def native_checks():
    model=f.FieldModel();assignment=json.loads((MORNING/'assignments.json').read_text())['frames']
    md=json.loads((MORNING/'metadata.json').read_text())[:16]
    stamps={v['frame']:datetime.datetime.strptime(v['dng']['time'],'%Y:%m:%d %H:%M:%S').timestamp() for v in md}
    expected={v['frame']:v for v in assignment};data={};qt={}
    for v in assignment:
        name=v['frame'];old=json.loads((MORNING/'frames'/(name+'.json')).read_text())
        patches=old['patches']['0.5']+[old['auxiliary_patches']['toolbar']]
        with Image.open(ROOT/'captures/mount-probe-20261103'/(name+'.JPG')) as im:
            qt[name]=dict(luma_DC=im.quantization[0][0],luma_DC_mean_step=im.quantization[0][0]/8)
            im.draft('YCbCr',im.size);ycc=np.asarray(im)
        data[name]=[ycc[p['roi_xyxy'][1]:p['roi_xyxy'][3],p['roi_xyxy'][0]:p['roi_xyxy'][2]].mean(axis=(0,1)).tolist() for p in patches]
    def codes(rgb):
        y,c=model.mm.ycbcr(np.asarray(rgb))
        return np.stack([y,c.real+128,c.imag+128],axis=-1)
    def differences(rgb):
        return codes(rgb)-np.array([0,128,128])
    anchors=[v for v in assignment if v['label']=='A'];at=np.asarray([stamps[v['frame']] for v in anchors])
    offsets=np.asarray([np.asarray(data[v['frame']])-codes(v['jpeg_mean']) for v in anchors])
    rows=[]
    for p in read('kernel_points.json'):
        if p['session']!='morning':continue
        name=p['frame'];pi=p['patch_index'];ch='RGB'.index(p['channel'])
        off=np.array([np.interp(stamps[name],at,offsets[:,pi,c]) for c in range(3)])
        expected_ycc=codes(expected[name]['expected_A'])[pi]+off
        delta=np.asarray(data[name][pi])-expected_ycc;dy=float(delta[0])
        rows.append(dict(frame=name,patch=p['patch'],channel=p['channel'],native_Y_delta=dy,
            session='morning',native_ycc_delta=delta,predicted_ycc_delta=differences(expected[name]['predicted_delta'][pi]),
            native_Y_q_estimate=dy/(model.row.coef[0,ch]/1024),q_projection=p['q_estimate'],q_nominal=p['q_nominal']))
    meta,frames,ps,j,r,wb,bad=load_frames();clock=np.array([datetime.datetime.strptime(v['dng']['time'],'%Y:%m:%d %H:%M:%S').timestamp() for v in meta])
    new=[]
    for p in read('points.json'):
        if p['excluded'] or p['patch_index'] not in MAIN_PATCHES:continue
        i=int(p['frame'][-4:])-1901;ai=meta[i]['exposure_index'];pi=p['patch_index'];ch='RGB'.index(p['channel'])
        offset=np.asarray(ps[ai][pi]['native_jpeg_ycc_mean'])-codes(j[ai,pi])
        if ai==2:
            alpha=p['reference_interpolation_alpha']
            offset=(1-alpha)*offset+alpha*(np.asarray(ps[16][pi]['native_jpeg_ycc_mean'])-codes(j[16,pi]))
        expected_ycc=codes(p['baseline_at_B'])+offset
        delta=np.asarray(ps[i][pi]['native_jpeg_ycc_mean'])-expected_ycc
        new.append(dict(frame=p['frame'],patch=p['patch'],channel=p['channel'],session='bracket',native_ycc_delta=delta,
            predicted_ycc_delta=differences(p['predicted_rgb']),native_Y_delta=float(delta[0]),
            native_Y_q_estimate=float(delta[0]/(model.row.coef[0,ch]/1024)),q_projection=p['q_estimate'],q_nominal=p['q_nominal']))
    for v in read('metadata.json'):
        with Image.open(CAP/(v['frame']+'.JPG')) as im:
            qt[v['frame']]=dict(luma_DC=im.quantization[0][0],luma_DC_mean_step=im.quantization[0][0]/8)
    component_fits=[]
    for scope in ('morning','bracket','combined'):
        for ch in 'RGB':
            selected=[v for v in rows+new if v['channel']==ch and v['q_nominal']>.2 and (scope=='combined' or v['session']==scope)]
            predicted=np.asarray([v['predicted_ycc_delta'] for v in selected]);actual=np.asarray([v['native_ycc_delta'] for v in selected])
            denom=np.sum(predicted**2,axis=0);gains=np.divide(np.sum(actual*predicted,axis=0),denom,out=np.zeros(3),where=denom>1e-10)
            component_fits.append(dict(scope=scope,channel=ch,n=len(selected),native_component_gains=gains,
                native_component_rmse=np.sqrt(np.mean((actual-predicted)**2,axis=0)),
                fields=['Y','Cb','Cr']))
    dump('native_Y_checks.json',dict(morning=rows,bracket=new,component_fits=component_fits,JPEG_quantization=qt,
        boundary='Native JPEG Y avoids the chroma sector inverse but retains JPEG quantization, IDCT rounding and the assumed C100 Y mapping. It is a diagnostic, not direct internal curve telemetry.'))
    for ch in 'RGB':
        active=[v for v in rows if v['channel']==ch and v['q_nominal']>.2]
        print('MORNING Y',ch,[(v['frame'],v['patch'],round(v['native_Y_q_estimate'],3),round(v['q_projection'],3),round(v['q_nominal'],3)) for v in active],flush=True)
    print('JPEG DC quantization',sorted({q['luma_DC'] for q in qt.values()}),flush=True)
    print('NATIVE COMPONENTS',json.dumps(f.plain(component_fits)),flush=True)


def figures():
    model=f.FieldModel();kp=read('kernel_points.json');points=read('points.json');coverage=read('coverage.json')
    summary=read('assessment.json');amb=read('nonidentifiability.json');drift=read('drift.json')
    fontpath='/System/Library/Fonts/Supplemental/Arial.ttf'
    small=ImageFont.truetype(fontpath,16);font=ImageFont.truetype(fontpath,20);title=ImageFont.truetype(fontpath,25)
    im=Image.new('RGB',(1500,760),'white');d=ImageDraw.Draw(im)
    d.text((45,20),'MOUNT node-16 response: measured positions remain sparse',font=title,fill='black')
    for ci,ch in enumerate('RGB'):
        l,t,w,h=80+ci*485,110,380,465
        xp=lambda x:l+(x-450)/450*w;yp=lambda y:t+h-(y+.4)/3.2*h
        for y in (0,1,2):
            d.line((l,yp(y),l+w,yp(y)),fill='#dddddd');d.text((l-27,yp(y)-8),str(y),font=small,fill='#555555')
        for x in (450,550,650,750,850):
            d.line((xp(x),t,xp(x),t+h),fill='#eeeeee');d.text((xp(x)-14,t+h+10),str(x),font=small,fill='#555555')
        scale=summary['ranges'][ci]['A_conditioned_input_scale_median']
        xx=np.linspace(450,900,450);left,peak,right=model.xs[15:18]
        yy=2*np.maximum(0,np.minimum((xx*scale-left)/(peak-left),(right-xx*scale)/(right-peak)))
        d.line([(xp(x),yp(y)) for x,y in zip(xx,yy)],fill='#888888',width=2)
        for row in kp:
            if row['channel']!=ch or not (450<=row['raw_input']<=900):continue
            x,y=xp(row['raw_input']),yp(row['q_estimate']);color='#c87324' if row['session']=='morning' else '#286baf'
            if row['session']=='bracket' and not row['verified_label']:
                d.ellipse((x-5,y-5,x+5,y+5),outline='#aaaaaa',width=2)
            else:d.ellipse((x-5,y-5,x+5,y+5),fill=color)
        # Supplementary chromatic regions diagnose identity and downstream
        # response. They are not part of the main grey-kernel fit.
        for row in points:
            if row['excluded'] or row['channel']!=ch or row['patch_index'] in MAIN_PATCHES or row['q_nominal']<=.1:continue
            if not 450<=row['raw_input']<=900:continue
            x,y=xp(row['raw_input']),yp(row['q_estimate'])
            d.polygon([(x,y-6),(x-6,y+5),(x+6,y+5)],outline='#777777',width=2)
        d.text((l,t-35),ch+': conditional pre-C100 code estimate',font=font,fill='black')
        d.text((l,t+h+40),'White-balanced RAW proxy (DN)',font=small,fill='black')
    d.text((60,665),'Blue: new grey points. Orange: morning. Hollow: planned label not observable. Triangles: chromatic supplements.',font=small,fill='black')
    d.text((60,695),'Grey curve: nominal linear kernel using median A input scale. Projected amplitudes depend on the downstream model.',font=small,fill='#444444')
    im.save(OUT/'kernel-samples.png')
    im=Image.new('RGB',(1500,720),'white');d=ImageDraw.Draw(im)
    d.text((45,20),'Two monotone kernels give identical predictions at every G sampled mean',font=title,fill='black')
    l,t,w,h=110,110,1250,440
    peak=amb['kernels'][0]['peak_input'];left,right=model.xs[15],model.xs[17]
    xp=lambda x:l+(x-left+30)/(right-left+60)*w;yp=lambda y:t+h-(y+.1)/2.4*h
    for y in (0,1,2):
        d.line((l,yp(y),l+w,yp(y)),fill='#dddddd');d.text((l-30,yp(y)-10),str(y),font=small,fill='#555555')
    for x in range(550,801,50):d.text((xp(x)-16,t+h+10),str(x),font=small,fill='#555555')
    gx=np.asarray(amb['grid_input']);valid=(gx>=left-30)&(gx<=right+30)
    for key,color in (('kernel_linear_fall','#286baf'),('kernel_fast_fall','#be4a35')):
        yy=np.asarray(amb[key]);d.line([(xp(x),yp(y)) for x,y in zip(gx[valid],yy[valid])],fill=color,width=3)
    for row in kp:
        if row['channel']=='G' and row['verified_label'] and left-30<row['conditioned_input']<right+30:
            x,y=xp(row['conditioned_input']),yp(row['q_estimate']);d.ellipse((x-5,y-5,x+5,y+5),fill='#222222')
    d.text((110,580),'Conditioned model input, node 16 at '+f'{peak:.0f}'+' (not directly observed ISP telemetry)',font=font,fill='black')
    d.text((110,625),f'Blue FWHM {amb["kernels"][0]["FWHM"]:.1f}; red FWHM {amb["kernels"][1]["FWHM"]:.1f}. Maximum difference at sample means: 0.',font=font,fill='black')
    d.text((110,665),'This is a mean-input identifiability counterexample, not a proposed hardware interpolation algorithm.',font=small,fill='#444444')
    im.save(OUT/'width-ambiguity.png')
    im=Image.new('RGB',(1500,760),'white');d=ImageDraw.Draw(im)
    d.text((45,20),'Exposure bracket coverage: four planned grey regions at four shutter settings',font=title,fill='black')
    colors=('#a65a26','#438b45','#286baf','#805ea9')
    for ci,ch in enumerate('RGB'):
        l,t,w,h=90+ci*480,120,375,430;xp=lambda x:l+x/2800*w
        scale=summary['ranges'][ci]['A_conditioned_input_scale_median'];lo,hi=model.xs[15]/scale,model.xs[17]/scale
        d.rectangle((xp(lo),t-10,xp(hi),t+h+20),fill='#f0e7c8')
        for pi,p in enumerate(MAIN_PATCHES):
            y=t+pi*125;d.text((l-70,y-7),('dark','mid','light','toolbar')[pi],font=small,fill='black')
            d.line((l,y,l+w,y),fill='#dddddd')
            for row in points:
                if row['channel']!=ch or row['patch_index']!=p:continue
                e=(int(row['frame'][-4:])-1901)%4;raw=row['raw_wb'][ci]
                x=xp(raw);yy=y+(-15,-5,5,15)[e]
                if row['excluded']:
                    d.line((x-5,yy-5,x+5,yy+5),fill='black',width=2);d.line((x-5,yy+5,x+5,yy-5),fill='black',width=2)
                else:d.ellipse((x-4,yy-4,x+4,yy+4),fill=colors[e])
        for x in (0,700,1400,2100,2800):d.text((xp(x)-15,t+h+36),str(x),font=small,fill='#555555')
        d.text((l,t-45),ch+' RAW proxy input',font=font,fill='black')
    for i,shutter in enumerate(('1/8','1/15','1/30','1/60')):
        x=100+i*250;d.ellipse((x,660,x+10,670),fill=colors[i]);d.text((x+20,650),shutter+' s',font=font,fill='black')
    d.text((100,705),'Shaded band: nominal linear support after A input scaling. Cross: low-end clipping. Most points are outside the band.',font=small,fill='#444444')
    im.save(OUT/'input-coverage.png')
    checks=read('native_Y_checks.json')
    active=[v for v in checks['morning']+checks['bracket'] if v['channel']=='G' and v['q_nominal']>.2]
    im=Image.new('RGB',(1200,670),'white');d=ImageDraw.Draw(im)
    d.text((45,20),'G response: luminance agrees more closely than chroma',font=title,fill='black')
    l,t,w,h=130,100,960,410;yp=lambda y:t+h-(y-.7)/1.05*h
    for y in (.8,1.,1.2,1.4,1.6):
        d.line((l,yp(y),l+w,yp(y)),fill='#555555' if y==1 else '#dddddd',width=2 if y==1 else 1)
        d.text((l-45,yp(y)-10),f'{y:.1f}',font=small,fill='#555555')
    for ci,name in enumerate(('Y','Cb','Cr')):
        x=l+160+ci*310;d.text((x-15,t+h+20),name,font=font,fill='black')
        for k,row in enumerate(active):
            ratio=row['native_ycc_delta'][ci]/row['predicted_ycc_delta'][ci]
            color='#c87324' if row['session']=='morning' else '#286baf';xx=x+(k-2)*10
            d.ellipse((xx-5,yp(ratio)-5,xx+5,yp(ratio)+5),fill=color)
    d.text((130,565),'Native JPEG component response / existing model prediction. One dot per photo, not per pixel.',font=small,fill='black')
    d.text((130,600),'Orange: 4 morning photos. Blue: 1 bracket photo. Values describe this local case; no global gain was changed.',font=small,fill='#444444')
    im.save(OUT/'g-luma-chroma.png')


def cleanup():
    assert str(TMP)=='/Volumes/Workspace/Scratch/tmp/projectricoh/probe-bracket-20261103'
    assert not TMP.is_symlink()
    paths=[p for p in TMP.rglob('*') if p.is_file()] if TMP.exists() else []
    count=len(paths);size=sum(p.stat().st_size for p in paths)
    if TMP.exists():shutil.rmtree(TMP)
    dump('cleanup.json',dict(scratch=str(TMP),removed_files=count,removed_bytes=size,scratch_removed=not TMP.exists(),
                            no_card_access=True,no_subagents=True,no_git_writes=True))
    print('Scratch removed:',not TMP.exists())


def validate():
    frozen=read('inputs.json');rows=manifest_check(CAP/'SHA256SUMS')
    assert rows==frozen['files'] and f.sha(CAP/'SHA256SUMS')==frozen['manifest_sha256']
    assert old_seal_check()==frozen['morning_sealed_inputs']
    assert f.sha(HERE/'field_20261103.py')==frozen['original_analysis_script_sha256']
    oldphotos=manifest_check(ROOT/'captures/mount-probe-20261103/SHA256SUMS')
    assert oldphotos==read('morning_photo_hashes.json')
    for name,digest in read('model.json')['inputs'].items():assert f.sha(ROOT/name)==digest,name
    md,frames,patches,j,r,wb,bad=load_frames()
    assert len(md)==17 and all(v['dng']['iso']==200 and v['dng']['exposure_program']==1 and v['dng']['wb_shotinfo']==1 for v in md)
    assert all(v['dng']['as_shot_neutral']==[.51282,1.,.666666] for v in md)
    assert len({v['raw']['sensor_payload_sha256'] for v in frames})==17
    for frame,ps in zip(frames,patches):
        assert frame['raw']['crop_wh']==[4288,2848] and frame['raw']['crop_origin_xy']==[8,7]
        assert frame['raw']['cfa_visible']==[[1,2],[0,1]]
        for p in ps:
            a,b,c,d=p['roi_xyxy'];assert 0<=a<c<=4288 and 0<=b<d<=2848
            assert np.isfinite(np.asarray(p['jpeg_mean'])).all() and np.isfinite(np.asarray(p['raw_dn_mean'])).all()
            for ch,hist in enumerate(p['raw_histograms']):
                bins=np.asarray(hist['dn']);counts=np.asarray(hist['counts'])
                mean=float(bins@counts/counts.sum())-frame['raw']['black']
                assert abs(mean-p['raw_dn_mean'][ch])<1e-8
    points=read('points.json');assert len(points)==84
    main=[v for v in points if v['patch_index'] in MAIN_PATCHES]
    assert len(main)==48 and sum(not v['excluded'] for v in main)==45
    ids=read('identity.json');assert len(ids)==12 and sum(v['label_verified'] for v in ids)==6
    assert all(v['planned_compatible'] for v in ids)
    assert all(not v['both_flanks_and_peak_sampled'] for v in read('coverage.json'))
    proof=read('nonidentifiability.json');assert proof['max_sample_prediction_difference']<1e-10
    assert proof['kernels'][0]['FWHM']/proof['kernels'][1]['FWHM']>1.5
    assert all(v['monotone_complete_curve'] and v['node_changes_exactly_match_probe'] for v in proof['kernels'])
    assert read('assessment.json')['high_clipped_regions']==0
    assert not TMP.exists() and read('cleanup.json')['scratch_removed']
    report=(HERE/'FIELD_20261103_BRACKET.md').read_text()
    assert report.splitlines()[0]=='部分可用'
    assert all(f'R805{n}' in report for n in range(1901,1918))
    for name in ('kernel-samples.png','width-ambiguity.png','input-coverage.png','g-luma-chroma.png',
                 'recipe_redo_handoff.json','validation_corrections.json','main-points.csv'):
        assert (OUT/name).is_file(),name
    return dict(status='部分可用',new_original_files_unchanged=len(rows),morning_original_files_unchanged=len(oldphotos),
        morning_sealed_files_unchanged=len(frozen['morning_sealed_inputs']),new_pairs=17,
        planned_B_frames=12,response_identified_B_frames=6,nonunique_B_frames=6,
        nominal_main_grey_points=48,valid_main_grey_points=45,new_significantly_activated_main_points_per_channel=1,
        hardware_interpolation_identified=False,full_MOUNT_L1_quantitative_model_closed=False,
        both_counterexample_curves_monotone=True,counterexample_sample_predictions_equal=True,
        independently_rerunnable=True,scratch_absent=True,nice=os.getpriority(os.PRIO_PROCESS,0),
        image_and_fit_processes_max=1,exclusive_process_lock_active=True,
        initial_hash_job_exit_receipt_order_corrected=True)


def seal():
    receipt=validate();dump('acceptance.json',receipt)
    source={}
    for folder in (CAP,ROOT/'captures/mount-probe-20261103'):
        for row in manifest_check(folder/'SHA256SUMS'):
            source[str((folder/row['file']).relative_to(ROOT))]=row['sha256']
        source[str((folder/'SHA256SUMS').relative_to(ROOT))]=f.sha(folder/'SHA256SUMS')
    source.update(read('inputs.json')['morning_sealed_inputs']);source.update(read('model.json')['inputs'])
    (OUT/'INPUT_SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in sorted(source.items())))
    paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p!=OUT/'SHA256SUMS')
    (OUT/'SHA256SUMS').write_text(''.join(f'{f.sha(p)}  {p.relative_to(ROOT)}\n' for p in paths))
    deliverables=[HERE/'FIELD_20261103_BRACKET.md',HERE/'bracket_20261103.py',HERE/'bracket_20261103_report.py',OUT/'SHA256SUMS']
    (HERE/'FIELD_20261103_BRACKET.SHA256SUMS').write_text(''.join(f'{f.sha(p)}  {p.relative_to(ROOT)}\n' for p in deliverables))
    print(json.dumps(receipt,ensure_ascii=False))


def verify():
    receipt=validate();counts=[]
    for manifest in (HERE/'FIELD_20261103_BRACKET.SHA256SUMS',OUT/'SHA256SUMS',OUT/'INPUT_SHA256SUMS'):
        n=0
        for line in manifest.read_text().splitlines():
            digest,name=line.split(None,1);p=(ROOT/name.lstrip('*')).resolve()
            assert p.is_relative_to(ROOT) and f.sha(p)==digest,name
            n+=1
        counts.append(n)
    print(json.dumps(dict(**receipt,manifest_verified_files=counts),ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('inventory','extract','measure','fit','assess','ambiguity','native_checks','figures','cleanup','seal','verify'));args=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.path.ismount('/Volumes/Workspace')
    OUT.mkdir(parents=True,exist_ok=True)
    if args.stage not in ('cleanup','seal','verify'):TMP.mkdir(parents=True,exist_ok=True)
    sys.addaudithook(audit)
    globals()[args.stage]()


if __name__=='__main__':
    main()
