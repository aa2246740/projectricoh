"""Native-CFA patch statistics and explicit scene geometry; no demosaiced samples."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
from raw_io import dng_module
from PIL import Image,ImageDraw
import csv
import json

GXR='artifacts/downloads/dpreview-gxr-a12-studio/studio_iso200.DNG'
PREVIEW='artifacts/downloads/dpreview-gxr-a12-studio-preview/studio_iso200_preview.jpg'
NAMES=['dark skin','light skin','blue sky','foliage','blue flower','bluish green',
       'orange','purplish blue','moderate red','purple','yellow green','orange yellow',
       'blue','green','red','yellow','magenta','cyan','white','neutral 8','neutral 6.5',
       'neutral 5','neutral 3.5','black']


def geometry():
    rows=[]
    # Coordinates refer to the original 1600 x 1062 embedded preview, before scaling to CFA.
    # Classic is rotated clockwise: left to right = neutral / saturated / second / first row.
    for original_row in range(4):
        for original_col in range(6):
            index=original_row*6+original_col
            x=800+35*(3-original_row);y=720+35.7*original_col
            r=dict(chart='ColorChecker',id=str(index+1),name=NAMES[index],index=index,
                   nominal_preview_xy=[x,y],roi_preview=None,status='occluded',reason='bottle')
            if original_row==3 and original_col<4:
                r.update(roi_preview=[793,y-8,807,y+8],status='primary',reason='clear centre')
            if original_row==2 and original_col<4:
                r.update(roi_preview=[827,y-8,843,y+8],status='primary',reason='clear centre')
            if original_row in (2,3) and original_col==4:
                r.update(roi_preview=[x-6,853,x+6,860],status='partial',reason='paper covers lower part')
            if original_row in (2,3) and original_col==5: r['reason']='paper'
            if original_row==1:
                bounds=[(861,864),(861,865),(862,867),(863,868),(863,870),(864,872)][original_col]
                r.update(roi_preview=[bounds[0],y-7,bounds[1],y+7],status='partial',reason='narrow visible strip beside bottle')
            rows.append(r)
    # Q-60 upper grid: A-L x 1-22. Portrait A-H/20-22 is not a uniform reference patch.
    for row in range(12):
        for col in range(22):
            x=1086+(col+.5)*(1543-1086)/22
            y=214+(row+.5)*(464-214)/12
            portrait=row<8 and col>=19
            rows.append(dict(chart='Q60',id=f'{chr(65+row)}{col+1}',name='',index=row*22+col,
                nominal_preview_xy=[x,y],roi_preview=None if portrait else [x-5,y-5,x+5,y+5],
                status='portrait' if portrait else 'primary',reason='nonuniform portrait' if portrait else 'clear centre'))
    for col in range(24):
        x=1066+(col+.5)*(1563-1066)/24;y=505
        feather=1220<x<1306 or 1336<x<1370
        rows.append(dict(chart='Q60-gray',id=f'GS{col:02d}',name='',index=col,
              nominal_preview_xy=[x,y],roi_preview=None if feather else [x-4,y-7,x+4,y+7],
              status='occluded' if feather else 'primary',reason='feather' if feather else 'clear centre'))
    return rows


def sample(d,roi,preview_size):
    y0,x0,h,w=d.crop_window();sx=w/preview_size[0];sy=h/preview_size[1]
    xa,ya,xb,yb=roi
    xs=np.arange(int(np.ceil(xa*sx))+x0,int(np.floor(xb*sx))+x0)
    ys=np.arange(int(np.ceil(ya*sy))+y0,int(np.floor(yb*sy))+y0)
    yy,xx=np.meshgrid(ys,xs,indexing='ij')
    v=d.normalised_at(yy,xx);phase=d.cfa_at(yy,xx)
    result={k:[] for k in ('raw_mean','raw_median','raw_trimmed','raw_sd','raw_se','saturation_fraction',
                         'sample_count','quadrant_relative_range','plane_relative_range')}
    for k in range(3):
        use=phase==k; a=v[use];n=len(a);ordered=np.sort(a);trim=max(1,int(.1*n))
        mean=float(np.mean(a));result['raw_mean'].append(mean)
        result['raw_median'].append(float(np.median(a)))
        result['raw_trimmed'].append(float(np.mean(ordered[trim:-trim])))
        result['raw_sd'].append(float(a.std(ddof=1)))
        result['raw_se'].append(float(a.std(ddof=1)/np.sqrt(n)))
        result['saturation_fraction'].append(float(np.mean(a>=.98)))
        result['sample_count'].append(n)
        q=[]
        for ix in range(2):
            for iy in range(2):
                m=use & ((xx>=np.median(xs))==bool(ix)) & ((yy>=np.median(ys))==bool(iy))
                if m.any():q.append(float(np.mean(v[m])))
        result['quadrant_relative_range'].append((max(q)-min(q))/max(mean,1e-8))
        u=(xx[use]-xx.mean())/max(1,np.ptp(xs));z=(yy[use]-yy.mean())/max(1,np.ptp(ys))
        coef=np.linalg.lstsq(np.c_[np.ones(n),u,z],a,rcond=None)[0]
        result['plane_relative_range'].append(float((abs(coef[1])+abs(coef[2]))/max(mean,1e-8)))
    result['roi_raw_xyxy']=[int(xs[0]),int(ys[0]),int(xs[-1])+1,int(ys[-1])+1]
    return result


def main():
    m=dng_module();d=m.Dng(c.inp(GXR));image=Image.open(c.inp(PREVIEW)).convert('RGB')
    overlay=image.copy();draw=ImageDraw.Draw(overlay)
    rows=geometry()
    for row in rows:
        if row['roi_preview']:
            row.update(sample(d,row['roi_preview'],image.size))
            flags=[]
            if max(row['saturation_fraction'])>0: flags.append('raw-saturation')
            if min(row['raw_mean'])<.0003: flags.append('very-low-signal')
            if max(row['quadrant_relative_range'])>.12: flags.append('spatial-gradient-or-contamination')
            row['quality_flags']=flags
            row['usable']=not flags
            row['glare_status']='no obvious clipping; specular veil cannot be excluded from one view'
            color='#44dd55' if row['usable'] and row['status']=='primary' else '#ffcc33'
            if flags:color='#ff5533'
            draw.rectangle(row['roi_preview'],outline=color,width=1)
        else:
            row['usable']=False;x,y=row['nominal_preview_xy']
            draw.line((x-3,y-3,x+3,y+3),fill='#ff3333',width=1)
            draw.line((x-3,y+3,x+3,y-3),fill='#ff3333',width=1)
    overlay.save(c.LOCAL/'patch_map.png')
    c.dump('patches.json',rows)
    with (c.LOCAL/'patches.csv').open('w',newline='') as f:
        keys=['chart','id','name','status','usable','reason','roi_preview','roi_raw_xyxy',
              'raw_mean','raw_trimmed','raw_sd','raw_se','sample_count','saturation_fraction',
              'quadrant_relative_range','plane_relative_range','quality_flags']
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(row[k]) if isinstance(row.get(k),list) else row.get(k,'') for k in keys})
    cc=[r for r in rows if r['chart']=='ColorChecker' and r['usable']]
    neutrals=[r for r in cc if r['index']>=18]
    ratios=np.array([np.array(r['raw_trimmed'])/r['raw_trimmed'][1] for r in neutrals])
    neutral=np.median(ratios,axis=0)
    colour=m.DngColour(d);xy,n_iter,converged=colour.neutral_to_xy(neutral)
    white=colour.white_info(xy,neutral,n_iter,converged)
    summary=dict(metadata=d.summary(),usable={chart:sum(r['usable'] for r in rows if r['chart']==chart)
          for chart in ('ColorChecker','Q60','Q60-gray')},neutral_patch_ids=[r['id'] for r in neutrals],
          neutral_camera_rgb_green1=neutral,neutral_ratio_spread=np.std(ratios,axis=0),
          matrix_conditioned_white=white,flat_field=dict(measured=False,
          action='no inferred full-frame correction; local multiplicative slope is a nuisance in the estimator',
          reason='one exposure has no repeated identical neutral across field; gray level and position are correlated'),
          black_level='subtract DNG tag, which is zero; pre-DNG processing and residual black are not independently measured',
          geometry='explicit inner ROIs; partial strips retained separately; all 24 Classic and 288 Q60 positions accounted for')
    c.dump('extraction.json',summary)
    print('usable patches',summary['usable'],'neutrals',summary['neutral_patch_ids'])
    print('neutral',neutral.tolist(),'matrix-conditioned illuminant',white)


if __name__=='__main__': main()
