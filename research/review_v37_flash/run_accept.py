from pathlib import Path
import hashlib,json,runpy,sys,time
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v37_flash'
ENTRY=ROOT/'research/redisplay_fix/accept.py'
def brief(kind,error,tb):
 print(kind.__name__+': '+str(error),file=sys.stderr)
sys.excepthook=brief
unit=sys.argv[1] if len(sys.argv)>1 else '50mm'
assert unit in ('50mm','28mm','mount')
expected={
 'firmware/package_v37_redisplay/SD_ROOT/ilaunch3':'d00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283',
 'firmware/package_v37_redisplay/SD_ROOT/GXRCE.DAT':'462da6518af29059612ab5628fe13fde75b170cc351d50541da7914e36787574'}
for name,value in expected.items():
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value
sys.path.insert(0,str(ENTRY.parent))
ns=runpy.run_path(str(ENTRY),run_name='review_accept_definitions')
g=ns['main'].__globals__
g['HERE']=OUT
scope=sys.modules['scope']
scope.HERE=OUT
scope.ALLOWED=(OUT,)
for obj in list(g.values()):
 if callable(obj) and getattr(obj,'__module__','')=='scope':
  obj.__globals__['HERE']=OUT
  obj.__globals__['ALLOWED']=(OUT,)
sys.argv=[str(ENTRY),unit]
started=time.monotonic()
ns['main']()
record={'unit':unit,'entry':str(ENTRY.relative_to(ROOT)),'seconds':time.monotonic()-started,'status':'PASS','input_sha256':expected,'output_root':str(OUT.relative_to(ROOT)),'assertions_enabled':__debug__}
(OUT/'local'/('run-'+unit+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print('REVIEW_ACCEPT_PASS',unit,flush=True)
