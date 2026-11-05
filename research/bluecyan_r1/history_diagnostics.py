#!/usr/bin/env python3
"""Evaluate native C040 or the exploratory T-only model on old camera JPEGs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import np,ROOT,LOCAL,read,dump,stats,de
import history as h
from correction import Correction
from PIL import Image,ImageDraw
import collections


def masks(base):
    lab=a.colour_math().rgb_lab(base/255);L=lab[:,0];C=np.hypot(lab[:,1],lab[:,2]);H=np.angle(lab[:,1]+1j*lab[:,2],deg=True)%360
    common=(L>=15)&(L<=90)&(C>=10)
    return dict(all=np.ones(len(base),bool),
        bluecyan=common&(H>=180)&(H<=285),
        skin_hue=common&(H>=25)&(H<=75)&(C<=65),
        foliage_hue=common&(H>=85)&(H<=170))


def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--physical',action='store_true');args=ap.parse_args()
    physical_mode=args.physical
    h.guard();models=h.Models();corr=None if physical_mode else Correction();inputs=read(LOCAL/'history/identities.json')
    if physical_mode:
        import physical
        from physical_calibration import coefficients,apply
        newmodels=h.Models();prefix='physical/history-'
    else:prefix='history/'
    per_photo=[];flat=[];chosen=[]
    for row in inputs:
        identity=row.get('identity',{})
        if not identity.get('accepted'):continue
        rec=identity['record'];labels=rec['labels']
        if not any(s in labels for s in ('04','05','06')):continue
        label=next(s for s in ('04','05','06') if s in labels)
        meta=row['metadata'];unit=meta['unit'];iso=meta['iso']
        model=models.model(unit,iso,meta['color_raw13'])
        with np.load(LOCAL/row['samples_file'],allow_pickle=False) as z:v=dict(z)
        held=v['cells'].sum(1)%2==1
        raw=v['raw_codes'][held];obs=v['observed'][held];x=models.input(raw,unit)
        entry=(LOCAL/rec['record']).read_bytes()
        stock=(LOCAL/next(r['record'] for r in models.bank if r['unit']==rec['unit'] and '04' in r['labels'])).read_bytes()
        old=model.predict(entry,x);direct=model.predict(entry,raw)
        if physical_mode:
            physical_model=newmodels.model(unit,iso,meta['color_raw13'])
            if not getattr(physical_model,'physical_geometry_applied',False):
                physical.update_model(physical_model,unit,iso);physical_model.physical_geometry_applied=True
            C=coefficients(unit)
            newx=apply(raw,C) if C.ndim==2 and C.size else raw
            new=physical_model.predict(entry,newx)
        else:new=corr.predict(model,entry,x) if unit=='mount-a12' else old.copy()
        base=model.predict(stock,x)
        region=masks(base);error_old=de(old,obs);error_new=de(new,obs);error_direct=de(direct,obs)
        lab_obs=a.colour_math().rgb_lab(obs/255);lab_old=a.colour_math().rgb_lab(old/255);lab_new=a.colour_math().rgb_lab(new/255)
        changes={}
        for group,mask in region.items():
            if not mask.any():continue
            def component(pred,lab):
                hue=(np.angle(lab_obs[:,1]+1j*lab_obs[:,2],deg=True)-np.angle(lab[:,1]+1j*lab[:,2],deg=True)+180)%360-180
                rgb_err=obs-pred;ycc_err=rgb_err@h.np.array([[.299,-.168736,.5],[.587,-.331264,-.418688],[.114,.5,-.081312]])
                return dict(hue_median=float(np.median(hue[mask])),delta_L=float(np.median((lab_obs-lab)[mask,0])),
                            Cb=float(np.median(ycc_err[mask,1])),Cr=float(np.median(ycc_err[mask,2])))
            changes[group]=dict(old=stats(error_old[mask]),corrected=stats(error_new[mask]),direct_raw=stats(error_direct[mask]),
                old_components=component(old,lab_old),corrected_components=component(new,lab_new))
        out=dict(day=row['day'],path=row['path'],jpeg=row['jpeg'],unit=unit,iso=iso,setting=label,
            record_sha256=rec['sha256'],catalogs=rec['catalogs'],identity=identity,regions=changes,
            correction_scope='ISO200 MOUNT primary' if unit=='mount-a12' and iso==200 else 'other-ISO or unit diagnostic',
            bluecyan_pixels=region['bluecyan'].sum(),skin_hue_pixels=region['skin_hue'].sum())
        per_photo.append(out)
        for j in range(len(obs)):
            flat.append(dict(day=row['day'],unit=unit,iso=iso,setting=label,path=row['path'],
                groups=[k for k,m in region.items() if m[j]],old_error=error_old[j],corrected_error=error_new[j],direct_error=error_direct[j]))
        if row['day']=='2026-10-31' and unit=='mount-a12' and iso==200:chosen.append(row)
    dump(prefix+'photo_scores.json',per_photo);dump(prefix+'point_errors.json',flat)
    summaries={}
    for day in ('2026-10-31','2026-11-01','2026-11-02'):
      for iso_scope in ('ISO200','allISO'):
       for label in ('04','05','06'):
        pp=[p for p in per_photo if p['day']==day and p['setting']==label and p['unit']=='mount-a12' and (iso_scope=='allISO' or p['iso']==200)]
        pts=[p for p in flat if p['day']==day and p['setting']==label and p['unit']=='mount-a12' and (iso_scope=='allISO' or p['iso']==200)]
        if not pts:continue
        key=' '.join((day,iso_scope,label));result={}
        for group in ('all','bluecyan','skin_hue','foliage_hue'):
            values=[p for p in pts if group in p['groups']]
            photos=[p for p in pp if group in p['regions']]
            if not values:continue
            result[group]=dict(photos=len(photos),points=len(values),
                old=stats([p['old_error'] for p in values]),corrected=stats([p['corrected_error'] for p in values]),
                direct_raw=stats([p['direct_error'] for p in values]),
                old_photo_medians=stats([p['regions'][group]['old']['median'] for p in photos]),
                corrected_photo_medians=stats([p['regions'][group]['corrected']['median'] for p in photos]))
        summaries[key]=result
        print(key,[(g,q['photos'],round(q['old']['median'],3),round(q['old']['p95'],3),round(q['corrected']['median'],3),round(q['corrected']['p95'],3)) for g,q in result.items()],flush=True)
    dump(prefix+'scores.json',summaries)
    # Private contact sheet only; never embedded or named in the public report.
    if chosen:
        sheet=Image.new('RGB',(400*len(chosen),335),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(chosen):
            with Image.open(row['jpeg']) as im:
                im=im.convert('RGB');im.thumbnail((395,300));sheet.paste(im,(i*400,30))
            draw.text((i*400+5,7),Path(row['jpeg']).stem,fill='black')
        sheet.save(LOCAL/'history/private-primary-contact.png')


if __name__=='__main__':main()
