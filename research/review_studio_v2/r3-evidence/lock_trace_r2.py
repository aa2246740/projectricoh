"""Observer-only lock trace of a real concurrent save and preview; separate from timings."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event,Lock
from unittest.mock import patch
import cProfile,io,json,pstats,sys,time
ROOT=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3');E=ROOT/'evidence'
sys.path.insert(0,'/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src')
from PIL import Image
from fastapi.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
from gxr_studio.render import edits
audit.forbid_volumes();audit.forbid_network()
for p in (Path.home()/'Pictures/GXR Studio',Path.home()/'Pictures/GXR 导出',Path.home()/'Library/Application Support/GXR Studio'):
 audit.protect(p);audit.forbid_reads(p)
s=Settings(library_dir=ROOT/'library',home_dir=ROOT/'app-home',export_dir=ROOT/'exports',volumes_roots=(),min_free_bytes=0,web_dir=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/web'),port=18769,token='trace')
with TestClient(create_app(s),base_url='http://127.0.0.1:18769',headers={'X-GXR-Token':s.token}) as c:
 photos={p['name']:p for p in c.get('/api/photos').json()};sid=photos['R8051219']['id'];jpg=photos['REVIEW']['id']
 c.delete(f'/api/photos/{jpg}/edit');c.delete(f'/api/photos/{jpg}/crop')
 c.put('/api/defaults/finish',json={'frame':{'style':'none'},'stamp':{'enabled':False}})
 before=next(p for p in c.get('/api/photos').json() if p['id']==jpg);a=c.get(before['thumb_url'])
 c.put('/api/defaults/finish',json={'frame':{'style':'gallery'},'stamp':{'enabled':True,'content':'text','text':'GXR','font':'sans'}})
 after=next(p for p in c.get('/api/photos').json() if p['id']==jpg);b=c.get(after['thumb_url'])
 cache={'before_url':before['thumb_url'],'after_url':after['thumb_url'],'url_changed':before['thumb_url']!=after['thumb_url'],'bytes_changed':a.content!=b.content,'cache_control':b.headers.get('cache-control')}
 c.put('/api/defaults/finish',json={'frame':{'style':'none'},'stamp':{'enabled':False}})
 c.delete(f'/api/photos/{sid}/edit');c.delete(f'/api/photos/{sid}/crop')
 entered=Event();events=[];guard=Lock();start=time.perf_counter()
 def event(name,**kw):
  with guard:events.append({'event':name,'seconds':round(time.perf_counter()-start,5),**kw})
 orig=edits.fitted_crop;lib=c.app.state.ctx.lib;origget=lib.get_shot
 def observed_fit(*args,**kw):
  event('fitted_crop_enter');entered.set()
  with cProfile.Profile() as profile:result=orig(*args,**kw)
  event('fitted_crop_exit')
  with (E/'geometry-save-profile.txt').open('w') as stream:pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumtime').print_stats(14)
  return result
 def observed_get(*args,**kw):
  event('get_shot_enter');t=time.perf_counter();result=origget(*args,**kw);event('get_shot_exit',wait_seconds=round(time.perf_counter()-t,5));return result
 def save():
  r=c.put(f'/api/photos/{sid}/edit',json={'geometry':{'vertical':40,'straighten':3}});event('save_response',status=r.status_code);return r.status_code
 with patch('gxr_studio.render.edits.fitted_crop',observed_fit),patch.object(lib,'get_shot',observed_get):
  with ThreadPoolExecutor(max_workers=1) as pool:
   future=pool.submit(save);assert entered.wait(30),'fit was not entered'
   event('preview_request');t=time.perf_counter()
   r=c.post(f'/api/photos/{sid}/render?stage=uncropped&size=preview',json={'geometry':{'vertical':40,'straighten':3}})
   im=Image.open(io.BytesIO(r.content));im.load();event('preview_decoded',status=r.status_code,wh=list(im.size),elapsed=round(time.perf_counter()-t,5));assert future.result(timeout=60)==200
 from gxr_studio.finish import serve
 original_render = serve.render_stage
 profile_rows = []
 def profile_render(*args, **kwargs):
  t = time.perf_counter()
  with cProfile.Profile() as profile:
   result = original_render(*args, **kwargs)
  with (E/'preview-profile-r3.txt').open('w') as stream:
   pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumtime').print_stats(25)
  profile_rows.append({'stage':kwargs.get('stage'),'elapsed_with_profile':time.perf_counter()-t})
  return result
 with patch.object(serve,'render_stage',profile_render):
  diagnostic = c.post(f'/api/photos/{sid}/render?stage=uncropped&size=preview',json={'geometry':{'vertical':13,'straighten':0}})
  assert diagnostic.status_code == 200, diagnostic.text
 result={'cache':cache,'events':events,'diagnostic_profile':profile_rows}
 (E/'lock-trace-r2.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
