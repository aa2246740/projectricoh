from pathlib import Path
import hashlib,io,json
import httpx,numpy as np
from PIL import Image,ImageOps
ROOT=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3');E=ROOT/'evidence'
ready=json.loads((ROOT/'server-ready.json').read_text());assert ready['port']!=49667
c=httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}",headers={'X-GXR-Token':'independent-review-browser'},timeout=240)
def req(method,url,**kw):
 r=c.request(method,url,**kw);assert r.status_code==200,(url,r.status_code,r.text[:400]);return r
photos={p['name']:p for p in req('GET','/api/photos').json()};sid=photos['PORTRAIT_JPG']['id']
req('PUT','/api/defaults/finish',json={'frame':{'style':'none'},'stamp':{'enabled':False}})
req('DELETE',f'/api/photos/{sid}/edit');req('DELETE',f'/api/photos/{sid}/crop')
texts=['上海北京'*6,('上海北京'*6)[:-2]+'上海'];images=[];rows=[]
for n,text in enumerate(texts):
 req('PUT',f'/api/photos/{sid}/edit',json={'stamp':{'enabled':True,'content':'date+text','date_format':'yyyy.mm.dd','show_time':True,'text':text,'font':'sans','glow':False}})
 row={'text':text};ims={}
 for size,url in [('gallery_thumb',f'/api/photos/{sid}/thumb'),('style_thumb',f'/api/photos/{sid}/render?stage=final&size=thumb'),('preview',f'/api/photos/{sid}/render?stage=final&size=preview')]:
  data=req('GET',url).content;im=ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB');ims[size]=np.asarray(im);row[size]={'wh':im.size,'sha256':hashlib.sha256(data).hexdigest()}
  if n==0:im.save(E/f'stamp-http-{size}-r3.png')
 meta=req('POST',f'/api/photos/{sid}/export',json={'quality':95}).json()
 with Image.open(meta['path']) as im:ims['export']=np.asarray(im.convert('RGB'));row['export']={'wh':im.size}
 images.append(ims);rows.append(row)
R={'cases':rows,'distinct_suffix_has_identical_pixels':{k:bool(np.array_equal(images[0][k],images[1][k])) for k in images[0]}}
(E/'stamp-http-r3.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n');print(json.dumps(R,ensure_ascii=False));c.close()
