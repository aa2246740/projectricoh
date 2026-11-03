"""Five completed full-resolution HTTP exports per process; no baseline speedup claim."""
from pathlib import Path
import io,json,os,resource,statistics,subprocess,sys,time
ROOT=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r2')
STUDIO=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
sys.path.insert(0,str(STUDIO/'src'))
from PIL import Image
from fastapi.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
audit.forbid_volumes();audit.forbid_network()
for p in (Path.home()/'Pictures/GXR Studio',Path.home()/'Pictures/GXR 导出',Path.home()/'Library/Application Support/GXR Studio'):
 audit.protect(p);audit.forbid_reads(p)
case=sys.argv[1];name='R8051219' if case=='paired' else 'RAW_ONLY'
settings=Settings(library_dir=ROOT/'library',home_dir=ROOT/'app-home',export_dir=ROOT/'perf-exports',volumes_roots=(),min_free_bytes=0,web_dir=STUDIO/'web',port=18769,token='perf-r2')
with TestClient(create_app(settings),base_url='http://127.0.0.1:18769',headers={'X-GXR-Token':settings.token},raise_server_exceptions=False) as c:
 sid=next(p['id'] for p in c.get('/api/photos').json() if p['name']==name)
 assert c.delete(f'/api/photos/{sid}/edit').status_code==200
 assert c.delete(f'/api/photos/{sid}/crop').status_code==200
 body={} if case in ('paired','raw_standard') else {'recipe':{'unit':'jlaunch','slot':8}}
 if case=='raw_geometry':body.update(geometry={'vertical':40,'straighten':3},frame={'style':'gallery'})
 if body:
  start=time.perf_counter();r=c.put(f'/api/photos/{sid}/edit',json=body);save_time=time.perf_counter()-start
  assert r.status_code==200,r.text
 else:save_time=0
 records=[]
 for n in range(5):
  start=time.perf_counter();r=c.post(f'/api/photos/{sid}/export',json={'quality':95});elapsed=time.perf_counter()-start
  assert r.status_code==200,(r.status_code,r.text)
  data=r.json();p=Path(data['path'])
  with Image.open(p) as im:
   im.load();wh=im.size;assert wh==(data['width'],data['height']);assert p.stat().st_size==data['bytes']
  records.append({'seconds':round(elapsed,4),'decoded_wh':wh,'bytes':data['bytes'],'render_label':data['render_label']})
 result={'case':case,'count':5,'failures':0,'save_seconds':round(save_time,4),'median_seconds':statistics.median(x['seconds'] for x in records),'range_seconds':[min(x['seconds'] for x in records),max(x['seconds'] for x in records)],'process_peak_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,2),'records':records,'load':os.getloadavg(),'logical_cores':os.cpu_count()}
 (ROOT/'evidence'/f'export-perf-{case}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False),flush=True)
 if case=='raw_geometry':
  import cProfile,pstats
  from gxr_studio.finish.serve import export_finish
  from gxr_studio.render.params import parse_edit
  ctx=c.app.state.ctx;shot=ctx.lib.get_shot(sid);side,_=ctx.lib.read_sidecar_or_default(shot)
  with cProfile.Profile() as profile:
   probe=export_finish(ctx.render,ctx.lib,shot,parse_edit(side),side,settings.export_dir,[],quality=95,long_edge=None,fmt='jpeg')
   assert probe.path.is_file()
  with (ROOT/'evidence/export-full-profile.txt').open('w') as stream:
   pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumtime').print_stats(18)
