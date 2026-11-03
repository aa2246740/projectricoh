"""Independent r2 matrix. Real HTTP, disposable library only, serial requests."""
from pathlib import Path
import hashlib,io,json,os,shutil,statistics,subprocess,sys,time
ROOT=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4')
HERE=ROOT/'evidence'
STUDIO=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
sys.path.insert(0,str(STUDIO/'src'))
import httpx
import numpy as np
from PIL import Image,ImageOps
from gxr_studio.engine import colour
ready=json.loads((ROOT/'server-ready.json').read_text());assert ready['port']!=49667
c=httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}",headers={'X-GXR-Token':'independent-review-browser'},timeout=240)
R={}
def save(): (HERE/'regression-r2.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n')
def req(method,url,**kw):
 r=c.request(method,url,**kw);assert r.status_code==200,(url,r.status_code,r.text[:500]);return r
def image(r):
 im=Image.open(io.BytesIO(r.content));im.load();return ImageOps.exif_transpose(im).convert('RGB')
def small(im,wh=(240,160)):return np.asarray(im.resize(wh,Image.Resampling.LANCZOS))
def metric(a,b):
 x,y=small(a),small(b);d=np.abs(x.astype(float)-y.astype(float))
 return {'mae':round(float(d.mean()),4),'de00':round(float(colour.delta_e00(colour.lab_from_codes(x),colour.lab_from_codes(y)).mean()),4)}
def reset(sid):
 req('DELETE',f'/api/photos/{sid}/edit');req('DELETE',f'/api/photos/{sid}/crop')
def put(sid,body):return req('PUT',f'/api/photos/{sid}/edit',json=body).json()
def exp(sid,**kw):
 r=req('POST',f'/api/photos/{sid}/export',json={'quality':95,**kw}).json()
 im=Image.open(r['path']);im.load();return im.convert('RGB'),r
def pv(sid,size='preview',stage='final'):
 return image(req('GET',f'/api/photos/{sid}/render?stage={stage}&size={size}&quality=95'))
# Add a genuine RAW-only grouping without modifying the original sample or paired shot.
baseline=json.loads((HERE/'baseline-fixture.json').read_text())
src=ROOT/'library'/baseline['photos']['R8051148']['media']['dng']['relpath']
folder=ROOT/'library/2026/2026-10-31';folder.mkdir(exist_ok=True,parents=True)
shutil.copyfile(src,folder/'RAW_ONLY.DNG')
Image.new('RGB',(1600,1200),(150,100,60)).save(folder/'LARGE.JPG',quality=95)
oriented=Image.Exif();oriented[274]=6
Image.new('RGB',(640,480),(140,90,50)).save(folder/'ORIENTED.JPG',quality=95,exif=oriented)
req('POST','/api/library/rebuild',json={})
photos={p['name']:p for p in req('GET','/api/photos').json()}
req('PUT','/api/defaults/finish',json={'frame':{'style':'none'},'stamp':{'enabled':False}})
R['matrix']=[];save()
for kind,name in [('raw_only','RAW_ONLY'),('jpg_only','REVIEW'),('raw_jpg','R8051219')]:
 sid=photos[name]['id']
 for mode,body in [('zero',{}),('adjust',{'adjust':{'exposure_ev':1,'contrast':30}}),('recipe',{'recipe':{'unit':'jlaunch','slot':8}}),('decor',{'frame':{'style':'gallery'},'stamp':{'enabled':True,'content':'text','text':'上海','font':'sans'}})]:
  reset(sid)
  if kind=='jpg_only' and mode=='recipe':
   R['matrix'].append({'kind':kind,'mode':mode,'capabilities':req('GET',f'/api/photos/{sid}/capabilities').json()});save();continue
  if body:put(sid,body)
  preview=pv(sid);full=pv(sid,'full');thumb=image(req('GET',f'/api/photos/{sid}/thumb'))
  output,meta=exp(sid)
  row={'kind':kind,'mode':mode,'preview_wh':preview.size,'full_wh':full.size,'thumb_wh':thumb.size,'export_wh':output.size,'preview_export':metric(preview,output),'thumb_export':metric(thumb,output),'full_export':metric(full,output),'render_label':meta['render_label']}
  R['matrix'].append(row);save();print(json.dumps(row,ensure_ascii=False),flush=True)
# Exercise the UI's current source override versus the contract's auto source.
sid=photos['R8051219']['id'];reset(sid)
a,auto=exp(sid,source='auto');b,forced=exp(sid,source='recipe')
R['forced_recipe']={'edit':req('GET',f'/api/photos/{sid}/edit').json(),'auto':{k:auto[k] for k in ('render','render_label','width','height')},'forced':{k:forced[k] for k in ('render','render_label','width','height')},'difference':metric(a,b)};save()
# Larger-than-1200 canvas and EXIF orientation regressions, using real API values.
R['orientation']=[]
sid=photos['ORIENTED']['id']
for mode,body in [('zero',{}),('adjust',{'adjust':{'exposure_ev':1}}),('decor',{'frame':{'style':'gallery'}})]:
 reset(sid)
 if body:put(sid,body)
 preview=pv(sid);full=pv(sid,'full');output,meta=exp(sid)
 R['orientation'].append({'mode':mode,'preview_wh':preview.size,'full_wh':full.size,'export_wh':output.size,'difference':metric(preview,output),'export_orientation':Image.open(meta['path']).getexif().get(274)})
 save()
R['canvas']=[]
for name in ('LARGE','ORIENTED'):
 sid=photos[name]['id']
 for geom in ({},{'rotate90':1},{'vertical':80},{'distortion':70}):
  reset(sid)
  if geom:put(sid,{'geometry':geom})
  uncrop=pv(sid,'full','uncropped');crop=req('GET',f'/api/photos/{sid}/crop').json();full=pv(sid,'full')
  before=dict(crop)
  req('PUT',f'/api/photos/{sid}/crop',json={'preset':'1:1'})
  square=pv(sid,'full')
  row={'name':name,'geometry':geom,'frame':crop['frame'],'uncropped_wh':uncrop.size,'crop':before,'final_wh':full.size,'square_wh':square.size}
  R['canvas'].append(row);save();print('canvas',json.dumps(row),flush=True)
reset(photos['REVIEW']['id']);reset(photos['R8051219']['id']);c.close()
