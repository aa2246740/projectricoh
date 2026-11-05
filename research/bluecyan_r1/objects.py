#!/usr/bin/env python3
"""Read private, visually checked blue-object boxes; publish only statistics."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,np,read,dump,de,stats
import history as h
import physical
from physical_calibration import coefficients,apply
from PIL import Image,ImageDraw


def main():
    h.guard();hm=h.Models();newhm=h.Models()
    rows={r['path']:r for r in read(LOCAL/'history/identities.json')}
    sys.path.insert(0,str(ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src'))
    from gxr_studio.raw.dng import Dng
    results=[]
    for item in read(LOCAL/'objects/regions.json'):
        r=rows[item['path']];meta=r['metadata'];assert r['identity']['accepted']
        rec=r['identity']['record'];entry=(LOCAL/rec['record']).read_bytes()
        model=hm.model('mount-a12',meta['iso'],meta['color_raw13'])
        newmodel=physical.update_model(newhm.model('mount-a12',meta['iso'],meta['color_raw13']),'mount-a12',meta['iso'])
        with Image.open(r['jpeg']) as im:rgb=np.asarray(im.convert('RGB'))
        d=Dng(r['path']);cy,cx,height,width=d.crop_window();centers=[]
        overlay=Image.fromarray(rgb);draw=ImageDraw.Draw(overlay)
        for region in item['boxes_xyxy_fraction']:
            x0,y0,x1,y1=np.array(region)*[width,height,width,height]
            draw.rectangle((x0,y0,x1,y1),outline='cyan',width=5)
            for y in range(int(y0)+4,int(y1)-4,8):
                for x in range(int(x0)+4,int(x1)-4,8):centers.append((x,y))
        centers=np.unique(np.array(centers),axis=0)
        dy,dx=np.meshgrid(np.arange(-3,3),np.arange(-3,3),indexing='ij')
        yy=centers[:,1,None]+dy.ravel();xx=centers[:,0,None]+dx.ravel()
        block=rgb[yy,xx].astype(float);obs=block.mean(1);sd=block.std(1)
        rawp=d.normalised_at(cy+yy,cx+xx-1);cfa=d.cfa_at(cy+yy,cx+xx-1)
        raw=np.column_stack([np.sum(np.where(cfa==c,rawp,0),1)/np.sum(cfa==c,1) for c in range(3)])/d.as_shot_neutral*4095
        xold=hm.input(raw,'mount-a12');xnew=apply(raw,coefficients('mount-a12'))
        old=model.predict(entry,xold);new=newmodel.predict(entry,xnew)
        lab=a.colour_math().rgb_lab(obs/255);C=np.hypot(lab[:,1],lab[:,2]);H=np.angle(lab[:,1]+1j*lab[:,2],deg=True)%360
        valid=(rawp.max(1)<.985)&(obs.min(1)>3)&(obs.max(1)<252)&(sd.max(1)<=18)&(lab[:,0]>15)&(lab[:,0]<90)&(C>=10)&(H>=185)&(H<=280)
        assert valid.sum()>=10
        e0=de(old,obs);e1=de(new,obs)
        results.append(dict(day=r['day'],path=r['path'],iso=meta['iso'],setting=next(s for s in ('04','05','06') if s in rec['labels']),
            points=int(valid.sum()),old=stats(e0[valid]),physical=stats(e1[valid]),
            observed_ycc_error_old=np.median(h.np.array(obs-old)[valid]@np.array([[.299,-.168736,.5],[.587,-.331264,-.418688],[.114,.5,-.081312]]),axis=0),
            observed_ycc_error_physical=np.median(h.np.array(obs-new)[valid]@np.array([[.299,-.168736,.5],[.587,-.331264,-.418688],[.114,.5,-.081312]]),axis=0),
            selection='visually confirmed physical object boxes, fixed blue hue/chroma filter, no model fitting'))
        for x,y in centers[valid][::max(1,int(valid.sum()/300))]:draw.ellipse((x-3,y-3,x+3,y+3),fill='red')
        overlay.thumbnail((1000,750));overlay.save(LOCAL/'objects/private-blue-object-overlay.png');d.release()
    dump('objects/scores.json',results)
    print([{k:v for k,v in r.items() if k!='path'} for r in results],flush=True)


if __name__=='__main__':main()
