"""Host models of the new Windows stat and error contracts."""
import ast,ctypes,errno,json,os
from pathlib import Path
from types import SimpleNamespace
p=Path(os.environ['REVIEW_SOURCE'])/'src/gxr_studio/osplat.py'
tree=ast.parse(p.read_text());branch=next(n for n in tree.body if isinstance(n,ast.If) and any(isinstance(x,ast.FunctionDef) and x.name=='_nt_open' for x in n.body))
nodes={n.name:n for n in branch.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
class CtypesView:
 def __getattr__(self,name):return getattr(ctypes,name)
 def WinError(self,code):return OSError(code,'model query failed')
 def get_last_error(self):return 5
 def FormatError(self,code):return 'model error '+str(code)
g={'ctypes':CtypesView(),'wintypes':SimpleNamespace(DWORD=ctypes.c_uint32),'os':os,'errno':errno}
for name in ['_FileBasicInfo','fstat','_nt_error']:exec(compile(ast.Module(body=[nodes[name]],type_ignores=[]),str(p),'exec'),g)
info=g['_FileBasicInfo'];assert ctypes.sizeof(info)==40 and info.ChangeTime.offset==24
fixture=Path(os.environ['REVIEW_TMP'])/'stat-model.bin';fixture.write_bytes(b'fixture');fd=os.open(fixture,os.O_RDONLY)
try:
 actual=os.fstat(fd);expected_ns=1700000000123456700
 def query(handle,kind,ptr,size):
  assert handle==fd and kind==0 and size==40
  ctypes.cast(ptr,ctypes.POINTER(info)).contents.ChangeTime=116444736000000000+expected_ns//100
  return True
 g.update(_GetInfoEx=query,_handle=lambda x:x)
 result=g['fstat'](fd)
 assert result.st_ctime_ns==expected_ns and result.st_ctime==expected_ns/1e9
 for field in ['st_ino','st_dev','st_size','st_mtime_ns','st_atime_ns','st_birthtime']:assert getattr(result,field)==getattr(actual,field)
 g['_GetInfoEx']=lambda *args:False
 try:g['fstat'](fd)
 except OSError as exc:failure=type(exc).__name__
 else:raise AssertionError('Expected query refusal')
finally:os.close(fd)
g['_RtlNtStatusToDosError']=lambda x:5
errors=[]
for status,cls,number in [(-1073741638,IsADirectoryError,errno.EISDIR),(-1073741565,NotADirectoryError,errno.ENOTDIR)]:
 error=g['_nt_error'](status,'entry');assert isinstance(error,cls) and error.errno==number;errors.append({'status':hex(status&0xffffffff),'class':cls.__name__,'errno':number})
report={'scope':'host model only; actual Windows calls are covered by linked CI logs','FILE_BASIC_INFO_size':40,'ChangeTime_offset':24,'ctime_ns':result.st_ctime_ns,'preserved':['dev','ino','size','mtime_ns','atime_ns','birthtime'],'query_failure':failure,'errors':errors}
(Path(os.environ['REVIEW_OUT'])/'windows-new-contracts.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
