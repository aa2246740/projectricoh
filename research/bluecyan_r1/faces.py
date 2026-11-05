#!/usr/bin/env python3
"""Private real-face skin regions, independent of noon model fitting."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,np,read,dump,de,stats
import history as h
import physical
from physical_calibration import apply,coefficients
from PIL import Image,ImageDraw
import argparse


def prepare():
    rows=read(LOCAL/'history/identities.json')
    selected=[r for r in rows if r.get('identity',{}).get('accepted') and r['metadata']['unit']=='mount-a12'
        and any(s in r['identity']['record']['labels'] for s in ('04','05','06'))]
    dump('faces/input.json',[dict(path=r['path'],jpeg=r['jpeg']) for r in selected])
    print('private photos for on-device rectangle detection',len(selected),flush=True)


def raw_point(x,y,w,h,orientation):
    if orientation==1:return x,y
    if orientation==3:return w-x,h-y
    if orientation==6:return y,h-x
    if orientation==8:return w-y,x
    if orientation==2:return w-x,y
    if orientation==4:return x,h-y
    if orientation==5:return y,x
    if orientation==7:return w-y,h-x
    raise ValueError('EXIF orientation')


def score():
    h.guard();rows={r['path']:r for r in read(LOCAL/'history/identities.json')}
    hm=h.Models();new_hm=h.Models();out=[];points=[];views=[]
    sys.path.insert(0,str(ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src'))
    from gxr_studio.raw.dng import Dng
    for detected in read(LOCAL/'faces/detected.json'):
        if not detected.get('faces'):continue
        r=rows[detected['path']];meta=r['metadata'];rec=r['identity']['record'];entry=(LOCAL/rec['record']).read_bytes()
        model=hm.model('mount-a12',meta['iso'],meta['color_raw13'])
        newmodel=new_hm.model('mount-a12',meta['iso'],meta['color_raw13'])
        if not getattr(newmodel,'physical_geometry_applied',False):
            physical.update_model(newmodel,'mount-a12',meta['iso']);newmodel.physical_geometry_applied=True
        with Image.open(r['jpeg']) as im:rgb=np.asarray(im.convert('RGB'))
        d=Dng(r['path']);cy,cx,hh,ww=d.crop_window();assert rgb.shape[:2]==(hh,ww)
        orientation=detected['orientation'];ow,oh=(hh,ww) if orientation>=5 else (ww,hh)
        centers=[];rectangles=[]
        for face in detected['faces']:
            fx,fy=face['x']*ow,(1-face['y']-face['h'])*oh;fw,fh=face['w']*ow,face['h']*oh
            if min(fw,fh)<24:continue
            # Cheeks only. Visual QA rejected the forehead area near headwear.
            for ax,ay,bx,by in ((.18,.45,.40,.72),(.60,.45,.82,.72)):
                x0,y0=raw_point(fx+fw*ax,fy+fh*ay,ww,hh,orientation)
                x1,y1=raw_point(fx+fw*bx,fy+fh*by,ww,hh,orientation)
                left,right=sorted((x0,x1));top,bottom=sorted((y0,y1))
                rectangles.append([left,top,right,bottom])
                for y in range(int(top)+3,int(bottom)-3,4):
                    for x in range(int(left)+3,int(right)-3,4):centers.append((x,y))
        if not centers:d.release();continue
        centers=np.unique(np.array(centers),axis=0)
        dy,dx=np.meshgrid(np.arange(-3,3),np.arange(-3,3),indexing='ij')
        xx=centers[:,0,None]+dx.ravel();yy=centers[:,1,None]+dy.ravel()
        block=rgb[yy,xx].astype(float);obs=block.mean(1);sd=block.std(1)
        mosaic=d.normalised_at(cy+yy,cx+xx-1);cfa=d.cfa_at(cy+yy,cx+xx-1)
        raw=np.column_stack([np.sum(np.where(cfa==c,mosaic,0),1)/np.sum(cfa==c,1) for c in range(3)])/d.as_shot_neutral*4095
        xold=hm.input(raw,'mount-a12');xnew=apply(raw,coefficients('mount-a12'))
        old=model.predict(entry,xold);new=newmodel.predict(entry,xnew)
        nodes_only=newmodel.predict(entry,xold);input_map_only=model.predict(entry,xnew)
        lab=a.colour_math().rgb_lab(obs/255);L=lab[:,0];C=np.hypot(lab[:,1],lab[:,2]);H=np.angle(lab[:,1]+1j*lab[:,2],deg=True)%360
        valid=(mosaic.max(1)<.985)&(obs.min(1)>3)&(obs.max(1)<252)&(sd.max(1)<=18)&(L>15)&(L<95)&(C>5)&(C<65)&(H>=15)&(H<=85)
        label=next(s for s in ('04','05','06') if s in rec['labels'])
        e0=de(old,obs);e1=de(new,obs)
        if valid.any():
            out.append(dict(day=r['day'],path=r['path'],jpeg=r['jpeg'],iso=meta['iso'],setting=label,
                faces=len(detected['faces']),sample_points=int(valid.sum()),old=stats(e0[valid]),physical=stats(e1[valid]),
                nodes_only=stats(de(nodes_only,obs)[valid]),input_map_only=stats(de(input_map_only,obs)[valid]),
                signed_error_old=np.median((obs-old)[valid],axis=0),signed_error_physical=np.median((obs-new)[valid],axis=0),
                face_regions=rectangles,face_detector='Apple Vision VNDetectFaceRectanglesRequest; no identity recognition',
                pixel_regions_private_only=True))
            for old_e,new_e in zip(e0[valid],e1[valid]):points.append(dict(day=r['day'],iso=meta['iso'],setting=label,path=r['path'],old=old_e,physical=new_e))
            im=Image.fromarray(rgb);draw=ImageDraw.Draw(im)
            for box in rectangles:draw.rectangle(box,outline='yellow',width=4)
            im.thumbnail((400,300));views.append(im)
        d.release()
    dump('faces/photo-scores.json',out);dump('faces/point-errors.json',points)
    summary={}
    for day in ('2026-10-31','2026-11-01','2026-11-02'):
      for label in ('04','05','06'):
        p=[v for v in points if v['day']==day and v['setting']==label]
        if not p:continue
        summary[day+' '+label]=dict(photos=len(set(r['path'] for r in p)),points=len(p),
            old=stats([r['old'] for r in p]),physical=stats([r['physical'] for r in p]),
            iso200_points=sum(r['iso']==200 for r in p))
    dump('faces/scores.json',summary);print(summary,flush=True)
    if views:
        cols=4;sheet=Image.new('RGB',(cols*400,((len(views)+cols-1)//cols)*300),'#eeeeee')
        for i,im in enumerate(views):sheet.paste(im,((i%cols)*400,(i//cols)*300))
        sheet.save(LOCAL/'faces/private-region-contact.png')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('prepare','score'));args=ap.parse_args();globals()[args.phase]()
