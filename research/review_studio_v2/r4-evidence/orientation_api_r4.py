from pathlib import Path
import hashlib,io,json,shutil
import httpx,numpy as np
from PIL import Image,ImageOps
R=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4');E=R/'evidence'
ready=json.loads((R/'server-ready.json').read_text());assert ready['port']!=49667
c=httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}",headers={'X-GXR-Token':'independent-review-browser'},timeout=720)
def req(method,url,**kw):
 response=c.request(method,url,**kw);assert response.status_code==200,(url,response.status_code,response.text[:400]);return response
photos={p['name']:p for p in req('GET','/api/photos').json()}
def centroid(image):
 a=np.asarray(image.convert('RGB'));red=(a[:,:,0]>180)&(a[:,:,1]<60)&(a[:,:,2]<60);ys,xs=np.nonzero(red);assert xs.size>40
 return (float(xs.mean()),float(ys.mean()))
def verify(path,ref):
 with Image.open(path) as image:
  image.load();assert image.getexif().get(274)==1
  assert image.size==ref.size,(path,image.size,ref.size)
  x,y=centroid(image);rx,ry=centroid(ref)
  assert abs(x-rx)<8 and abs(y-ry)<8
  assert x>image.width*.65 and y<image.height*.35
  return {'width':image.width,'height':image.height,'orientation':image.getexif().get(274),'red_centroid':[x,y],'expected_red_centroid':[rx,ry],'centroid_max_error':max(abs(x-rx),abs(y-ry)),'mean_abs_rgb_error':float(np.abs(np.asarray(image.convert('RGB')).astype(float)-np.asarray(ref).astype(float)).mean()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
req('PUT','/api/defaults/finish',json={'frame':{'style':'none'},'stamp':{'enabled':False}})
rows=[]
for name in ('PORTRAIT_JPG','PORTRAIT_PAIR'):
 sid=photos[name]['id'];req('DELETE',f'/api/photos/{sid}/edit');req('DELETE',f'/api/photos/{sid}/crop')
 source=R/f'library/2026/2026-10-31/{name}.JPG'
 with Image.open(source) as raw:
  assert raw.size==(640,480) and raw.getexif().get(274)==6
  upright=ImageOps.exif_transpose(raw).convert('RGB')
 shutil.copyfile(source,E/f'input-{name}-orientation6-r4.jpg')
 for edge in (None,512,2048,4096):
  meta=req('POST',f'/api/photos/{sid}/export',json={'quality':95,'source':'auto','long_edge':edge}).json()
  ref=upright.copy()
  if edge:ref.thumbnail((edge,edge),Image.Resampling.LANCZOS)
  path=Path(meta['path']);assert path.is_relative_to(R)
  row={'name':name,'has_raw':photos[name]['has_raw'],'has_jpg':photos[name]['has_jpg'],'long_edge':edge,'status':200,'render':meta['render'],'render_label':meta['render_label'],**verify(path,ref)}
  assert meta['render']=='camera-jpg'
  artifact=E/f'api-{name}-{edge or "original"}-r4.jpg';shutil.copyfile(path,artifact);row['artifact']=artifact.name
  rows.append(row)
(E/'orientation-api-r4.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+chr(10))
ui=E/'ui-orientation-r4.json'
if ui.exists():
 u=json.loads(ui.read_text());checks=[]
 for case in u['cases']:
  ref=ImageOps.exif_transpose(Image.open(E/f"input-{case['name']}-orientation6-r4.jpg")).convert('RGB')
  checks.append({'name':case['name'],**verify(E/case['artifact'],ref)})
 assert len(checks)==2
 (E/'orientation-ui-artifacts-r4.json').write_text(json.dumps(checks,indent=2)+chr(10))
c.close();print(json.dumps({'api_cases':len(rows),'all_pass':True,'ui_artifacts_checked':ui.exists()}))
