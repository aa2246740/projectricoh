"""Same-RAW classification against the frozen GXR04 model and exact gen115 rows."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import boundary as b
import artifacts as a
import importlib.util
import json
from types import MethodType
import numpy as np
from PIL import Image

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,b.add(path));mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

def plain(x):
    if isinstance(x,dict):return {str(k):plain(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [plain(v) for v in x]
    if isinstance(x,np.ndarray):return plain(x.tolist())
    if isinstance(x,np.generic):return plain(x.item())
    if isinstance(x,Path):return str(x)
    return x

def stats(v):
    v=np.asarray(v,float)
    return dict(n=len(v),median=float(np.median(v)),mean=float(v.mean()),p90=float(np.percentile(v,90)),max=float(v.max()))

def setup():
    sys.path.insert(0,str(b.ROOT/'research/module_adapt'))
    support=load('support',b.ROOT/'research/module_adapt/support.py')
    original_source=support.source
    support.source=lambda p:b.add(original_source(p))
    sys.path.insert(0,str(b.ROOT/'research/closed_loop'))
    common=load('common',b.ROOT/'research/closed_loop/common.py')
    original_add=common.Provenance.add
    common.Provenance.add=lambda self,p:b.add(original_add(self,p))
    # The loaders only read code. Redirecting output helpers is unnecessary:
    # boundary.audit rejects any attempted write outside this task.
    um=load('field_unit_model',b.ROOT/'research/module_adapt/unit_model.py')
    cal=load('field_calibrate',b.ROOT/'research/module_adapt/calibrate.py')
    dng=load('field_dng',b.ROOT/'research/color_table_fit/dng_scene.py')
    session=load('field_session',b.ROOT/'research/chart_session_20261024/session_runtime.py')
    ar=load('field_metadata',b.ROOT/'research/hue_ring/analyze_ring.py')
    session.patch_tiff(dng.analyze_capture().Tiff);session.patch_tiff(ar.s2d().Tiff)
    base=support.engine(200);raw,modules=a.parse()
    entries=modules[0]['entries']
    base.entries={f'{slot:02d}':dict(slot=slot,mask=e['descriptor'][1],control=a.u16(e['descriptor'],2),
                 written=e['rows'][:6]+[e['rows'][6]+e['rows'][7]]) for slot,e in entries.items()}
    def parameters(self,slot):
        rows=self.entries[slot]['written'];matrix=self.mm.MatrixRow.from_bytes(rows[3][:28])
        ab=np.array([(0,0) if rows[2][i:i+4]==bytes(4) else self.fs.decode_word(rows[2][i:i+4]) for i in range(0,96,4)])
        return matrix,ab[:,0],ab[:,1]
    base.parameters=MethodType(parameters,base)
    calibration=json.loads(b.add(b.ROOT/'research/refit_50mm_r7/local/folds/full/calibration.json').read_text())
    return um,cal,dng,ar,base,calibration,support

def sample(dp,jp,dng):
    with Image.open(b.add(jp)) as im:
        image=np.asarray(im.convert('RGB'));orientation=im.getexif().get(274,1)
    d=dng.Dng(b.add(dp));h,w=image.shape[:2];mapping=dng.RawMap(d,(w,h),orientation)
    verification=dng.verify_mapping(d,image,mapping)
    if verification.get('ok'):
        offset=verification['suggested_integer_offset_xy'];assert max(abs(v) for v in offset)<=8
        mapping=dng.RawMap(d,(w,h),orientation,offset)
    xx,yy=np.meshgrid(np.linspace(48,w-49,40).astype(int),np.linspace(48,h-49,28).astype(int))
    centers=np.c_[xx.ravel(),yy.ravel()];dx,dy=np.meshgrid(np.arange(-6,6),np.arange(-6,6))
    xs=centers[:,0,None]+dx.ravel()[None,:];ys=centers[:,1,None]+dy.ravel()[None,:]
    block=image[ys,xs].astype(float);observed=block.mean(1);jsd=block.std(1)
    cy,cx=mapping.pixels(ys,xs);y0,x0,_,_=d.crop_window()
    pixels=d.normalised_at(cy+y0,cx+x0);cfa=d.cfa_at(cy+y0,cx+x0)
    raw=np.column_stack([np.sum(np.where(cfa==k,pixels,0),axis=1)/np.sum(cfa==k,axis=1) for k in range(3)])
    maximum=np.column_stack([np.max(np.where(cfa==k,pixels,-1),axis=1) for k in range(3)])
    sd=np.column_stack([np.sqrt(np.sum(np.where(cfa==k,(pixels-raw[:,k,None])**2,0),axis=1)/np.sum(cfa==k,axis=1)) for k in range(3)])
    valid=(maximum<.98).all(1)&(raw>.0005).all(1)&(observed>3).all(1)&(observed<252).all(1)&(jsd.max(1)<10)&(sd.max(1)<.025)
    return d,dict(raw=raw,raw_wb=raw/d.as_shot_neutral,observed=observed,valid=valid,
                  centers=centers,jpeg_sd=jsd,raw_sd=sd),verification,orientation

def main():
    um,cal,dng,ar,base,calibration,support=setup();results=[]
    for number in (1476,1477,1478,1479,1480,1481):
        stem=f'R805{number:04d}';folder=(a.OLD_CARD if number<1478 else a.CARD)/'root/DCIM/100RICOH'
        dp=folder/(stem+'.DNG');jp=folder/(stem+'.JPG')
        # Retain MakerNote from both carriers; changing a deep row is not an EXIF recipe identity.
        md=ar.read_meta(jp,dp,None);jmd=ar.read_meta(jp,None,None)
        if number>=1480:
            d=dng.Dng(b.add(dp))
            results.append(dict(id=stem,metadata=md,jpeg_metadata=jmd,asn=d.as_shot_neutral.tolist(),
                dng_exif=d.exif,unit='28mm',model_classification='not calibrated; metadata only'))
            continue
        d,data,verification,orientation=sample(dp,jp,dng)
        display=md['display'];assert d.exif['iso']==200, 'ISO200 calibration required'
        # Keep the exact earlier model. The 1476 native 7/7/7 state lies
        # outside its measured vividness=100% contract and is a confound.
        m=um.UnitModel('50mm',iso=200,base=base)
        x=cal.apply_calibration(data['raw_wb'],calibration);data['x']=x
        errors={};prediction={}
        for slot in ('04','01','02'):
            pred=m.predict(slot,x);prediction[slot]=pred
            de=m.de(pred,data['observed']);data['error_'+slot]=de;data['pred_'+slot]=pred
            errors[slot]=stats(de[data['valid']])
        model_separation={slot:stats(m.de(prediction[slot],prediction['04'])[data['valid']]) for slot in ('01','02')}
        discriminating={}
        for slot in ('01','02'):
            sep=m.de(prediction[slot],prediction['04'])
            valid=data['valid']&(sep>=3)
            discriminating[slot]=dict(points=int(valid.sum()),
                error04=stats(data['error_04'][valid]),error_recipe=stats(data['error_'+slot][valid]),
                fraction_closer_to04=float(np.mean(data['error_04'][valid]<data['error_'+slot][valid])))
        np.savez_compressed(b.LOCAL/(stem+'.npz'),**data)
        results.append(dict(id=stem,metadata=md,jpeg_metadata=jmd,unit='50mm',dng_exif=d.exif,
            asn=d.as_shot_neutral.tolist(),orientation=orientation,points=int(data['valid'].sum()),
            grid=1120,roi='12x12 fixed regular grid; no score-selected patches',mapping=verification,
            errors=errors,model_recipe_vs04_separation=model_separation,discriminating=discriminating,
            model_display=m.display,model_display_matches=display==m.display,
            menu_raw13_matches_calibration=md['raw13']==calibration['selector_bytes_04']['raw13']))
        print(stem,'points',int(data['valid'].sum()),'median DE00', {k:round(v['median'],4) for k,v in errors.items()},flush=True)
    # Check exact same-RAW code path against the previously retained 04 control results.
    prior=json.loads((b.ROOT/'research/gr4_lut_ceiling/local/bridge/native.json').read_text())
    controls=[]
    for number in (1476,1477):
        stem=f'R805{number:04d}';now=next(r for r in results if r['id']==stem);old=next(r for r in prior if r['id']==stem)
        controls.append(dict(id=stem,previous_frozen=old['stock_row5_model_error'],
            current_frozen_model=now['errors']['04'],
            warning='1476 contrast/sharpness/vividness 7/7/7 differ from 5/6/5 calibration'))
    b.dump('image_results.json',plain(dict(results=results,controls=controls,
        fixed_model='research/gr4_lut_ceiling/bridge.py native + refit_50mm_r7 full calibration',
        prediction_rows='exact final gen115 jlaunch descriptors; no fit to field JPEG',
        interpretation='conditional host model classification; not proof of every transient RPC event')))
    # Every imported project source is added before final verification. Existing
    # source trees were frozen before any imports; late helper dependencies also
    # carry the frozen model vendor hashes and Provenance checks.
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path and Path(path).resolve().is_relative_to(b.ROOT) and Path(path).is_file():b.add(path)
    for path in support.INPUTS:b.add(b.ROOT/path)
    for path in base.provenance.before:b.add(path)
    b.verify()

if __name__=='__main__':main()
