"""Real HTTP output matrix. Includes real GXR samples and asymmetric Orientation=6 fixtures."""
from pathlib import Path
import hashlib,io,json,shutil,sys,time
ROOT=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3'); E=ROOT/'evidence'
STUDIO=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
sys.path[:0]=[str(STUDIO/'src'),str(STUDIO/'tests')]
import httpx,numpy as np
from PIL import Image,ImageOps
from raw_support import build_dng,bayer_scene
from gxr_studio.engine import colour
ready=json.loads((ROOT/'server-ready.json').read_text()); assert ready['port']!=49667
c=httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}",headers={'X-GXR-Token':'independent-review-browser'},timeout=240)
R={'rows':[],'failures':[]}
def save(): (E/'matrix-r3.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n')
def req(method,url,**kw):
    r=c.request(method,url,**kw); assert r.status_code==200,(url,r.status_code,r.text[:500]);return r
def image(data):
    im=Image.open(io.BytesIO(data));im.load();return ImageOps.exif_transpose(im).convert('RGB')
def metric(a,b):
    shape=(240,round(240*b.height/b.width))
    x=np.asarray(a.resize(shape,Image.Resampling.LANCZOS)); y=np.asarray(b.resize(shape,Image.Resampling.LANCZOS))
    return {'mae':round(float(np.abs(x.astype(float)-y.astype(float)).mean()),4),
            'de00':round(float(colour.delta_e00(colour.lab_from_codes(x),colour.lab_from_codes(y)).mean()),4),
            'aspect_error':round(abs(a.width/a.height-b.width/b.height),5)}
def reset(sid):
    req('DELETE',f'/api/photos/{sid}/edit');req('DELETE',f'/api/photos/{sid}/crop')
def pv(sid,size):return image(req('GET',f'/api/photos/{sid}/render?stage=final&size={size}&quality=95').content)
folder=ROOT/'library/2026/2026-10-31'; folder.mkdir(parents=True,exist_ok=True)
baseline=json.loads((E/'baseline-fixture.json').read_text());sample=ROOT/'library'/baseline['photos']['R8051148']['media']['dng']['relpath']
shutil.copyfile(sample,folder/'RAW_ONLY.DNG')
# Red, green, blue corners and distinct gradients make a lost rotation observable.
h,w=480,640; yy,xx=np.mgrid[0:h,0:w]
rgb=np.stack([35+xx*130/w,40+yy*140/h,60+35*np.sin(xx/33)],axis=-1).astype(np.uint8)
rgb[:90,:100]=(240,30,20);rgb[-90:,:100]=(20,220,45);rgb[:90,-100:]=(30,40,230)
for name in ('PORTRAIT_JPG','PORTRAIT_PAIR'):
    exif=Image.Exif();exif[274]=6;exif[271]='RICOH';exif[272]='GXR A12'
    Image.fromarray(rgb).save(folder/f'{name}.JPG',quality=97,exif=exif)
scene=(rgb.astype(float)/255)*0.7+0.05
raw=build_dng(bayer_scene(h,w,scene,white=4095),white=4095,active=(0,0,h,w),orientation=6,neutral=(0.645161,1.0,0.574712))
for name in ('PORTRAIT_RAW','PORTRAIT_PAIR'): (folder/f'{name}.DNG').write_bytes(raw)
req('POST','/api/library/rebuild',json={});photos={p['name']:p for p in req('GET','/api/photos').json()}
req('PUT','/api/defaults/finish',json={'frame':{'style':'none'},'stamp':{'enabled':False}})
cases=[('zero',{}),('adjust',{'adjust':{'exposure_ev':1,'contrast':30}}),('recipe',{'recipe':{'unit':'jlaunch','slot':8}}),('decor',{'frame':{'style':'gallery'},'stamp':{'enabled':True,'content':'text','text':'上海','font':'sans'}}),('rotate',{'geometry':{'rotate90':1}}),('combined',{'adjust':{'exposure_ev':0.5,'saturation':25},'curve':{'master':[[0,0],[128,105],[255,255]]},'geometry':{'rotate90':1,'vertical':15},'frame':{'style':'gallery'},'stamp':{'enabled':True,'content':'text','text':'GXR','font':'sans'}})]
for kind,name in [('raw_only','RAW_ONLY'),('jpg_only','REVIEW'),('raw_jpg','R8051219'),('portrait_raw','PORTRAIT_RAW'),('portrait_jpg','PORTRAIT_JPG'),('portrait_pair','PORTRAIT_PAIR')]:
    sid=photos[name]['id']
    for mode,body in cases:
        reset(sid)
        if kind in ('jpg_only','portrait_jpg') and mode=='recipe':
            caps=req('GET',f'/api/photos/{sid}/capabilities').json();r=c.post(f'/api/photos/{sid}/render?stage=final&size=preview',json=body)
            R['rows'].append({'kind':kind,'mode':mode,'capabilities':caps,'render_status':r.status_code,'render_error':r.json()});save();continue
        if body:req('PUT',f'/api/photos/{sid}/edit',json=body)
        preview=pv(sid,'preview');full=pv(sid,'full');thumb=image(req('GET',f'/api/photos/{sid}/thumb').content)
        exported=req('POST',f'/api/photos/{sid}/export',json={'quality':95,'source':'auto'}).json()
        with Image.open(exported['path']) as im:
            im.load();out=im.convert('RGB'); orientation=im.getexif().get(274)
        row={'kind':kind,'mode':mode,'preview_wh':preview.size,'full_wh':full.size,'thumb_wh':thumb.size,'export_wh':out.size,'orientation':orientation,'render_label':exported['render_label'],'preview_export':metric(preview,out),'thumb_export':metric(thumb,out),'full_export':metric(full,out)}
        if mode=='zero' and 'jpg' in photos[name].get('files',{}):pass
        if name in ('PORTRAIT_JPG','PORTRAIT_PAIR') and mode=='zero':
            ref=ImageOps.exif_transpose(Image.open(folder/f'{name}.JPG')).convert('RGB');row['source_jpg_export']=metric(ref,out)
            row['corners_export']=[out.getpixel((20,20)),out.getpixel((out.width-20,20)),out.getpixel((20,out.height-20))]
        if mode in ('zero','adjust','rotate') and kind.startswith('portrait'):
            expected=(640,480) if mode=='rotate' else (480,640)
            row['expected_wh']=expected;row['orientation_pass']=out.size==expected and orientation==1
        if full.size!=out.size:R['failures'].append({'kind':kind,'mode':mode,'reason':'full/export dimensions'})
        if row.get('orientation_pass') is False:R['failures'].append({'kind':kind,'mode':mode,'reason':'orientation'})
        R['rows'].append(row);save();print(json.dumps(row,ensure_ascii=False),flush=True)
R['sized_orientation']=[]
for name in ('PORTRAIT_JPG','PORTRAIT_PAIR'):
    sid=photos[name]['id'];reset(sid)
    for edge in (None,512,2048,4096):
        meta=req('POST',f'/api/photos/{sid}/export',json={'quality':95,'source':'auto','long_edge':edge}).json()
        with Image.open(meta['path']) as im:
            im.load();out=im.convert('RGB');orientation=im.getexif().get(274)
        ref=ImageOps.exif_transpose(Image.open(folder/f'{name}.JPG')).convert('RGB')
        if edge:ref.thumbnail((edge,edge),Image.Resampling.LANCZOS)
        row={'name':name,'long_edge':edge,'export_wh':out.size,'expected_wh':ref.size,'orientation':orientation,'match':out.size==ref.size,'difference':metric(ref,out)}
        R['sized_orientation'].append(row);save();print('sized_orientation',json.dumps(row),flush=True)
for name in ('REVIEW','R8051219'):reset(photos[name]['id'])
c.close();save()
