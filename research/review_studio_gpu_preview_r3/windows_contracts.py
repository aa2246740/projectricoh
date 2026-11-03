"""Host checks of Windows declarations and production function control flow.

This does not call Windows APIs and does not establish Windows runtime acceptance.
"""
import ast
import ctypes
import errno
import json
import os
from pathlib import Path
import stat
import struct
from types import SimpleNamespace

OUT = Path(os.environ.get('REVIEW_OUT', Path(__file__).resolve().parent))
SOURCE = Path(os.environ['REVIEW_SOURCE']) / 'src/gxr_studio/osplat.py'
tree = ast.parse(SOURCE.read_text())
branch = next(n for n in tree.body if isinstance(n, ast.If) and any(isinstance(x, ast.FunctionDef) and x.name == '_nt_open' for x in n.body))
nodes = {n.name:n for n in branch.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
wintypes = SimpleNamespace(USHORT=ctypes.c_uint16, ULONG=ctypes.c_uint32, DWORD=ctypes.c_uint32,
                          HANDLE=ctypes.c_void_p, LPVOID=ctypes.c_void_p, LPWSTR=ctypes.c_void_p, WCHAR=ctypes.c_uint16)
g = {'ctypes':ctypes,'wintypes':wintypes,'Any':object,'errno':errno,'os':os,'struct':struct}


def load(name):
    exec(compile(ast.fix_missing_locations(ast.Module(body=[nodes[name]], type_ignores=[])),str(SOURCE),'exec'),g)
    return g[name]


def declarations():
    for name in ('_UnicodeString','_ObjectAttributes','_IoStatusBlock'):
        load(name)
    n = 7
    rename_class = next(node for node in ast.walk(nodes['rename_at']) if isinstance(node, ast.ClassDef))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[rename_class],type_ignores=[])),str(SOURCE),'exec'),{**g,'n':n},local := {})
    rename = local['_Rename']
    layouts = {
        'UNICODE_STRING':{'size':ctypes.sizeof(g['_UnicodeString']),'Buffer':g['_UnicodeString'].Buffer.offset},
        'OBJECT_ATTRIBUTES':{'size':ctypes.sizeof(g['_ObjectAttributes']),'RootDirectory':g['_ObjectAttributes'].RootDirectory.offset,'ObjectName':g['_ObjectAttributes'].ObjectName.offset,'Attributes':g['_ObjectAttributes'].Attributes.offset},
        'IO_STATUS_BLOCK':{'size':ctypes.sizeof(g['_IoStatusBlock']),'Information':g['_IoStatusBlock'].Information.offset},
        'FILE_RENAME_INFORMATION':{'RootDirectory':rename.RootDirectory.offset,'FileNameLength':rename.FileNameLength.offset,'FileName':rename.FileName.offset,'allocated':ctypes.sizeof(rename),'minimum_used':20+2*n},
    }
    assert layouts['UNICODE_STRING'] == {'size':16,'Buffer':8}
    assert layouts['OBJECT_ATTRIBUTES'] == {'size':48,'RootDirectory':8,'ObjectName':16,'Attributes':24}
    assert layouts['IO_STATUS_BLOCK'] == {'size':16,'Information':8}
    assert layouts['FILE_RENAME_INFORMATION']['FileName'] == 20
    assert layouts['FILE_RENAME_INFORMATION']['allocated'] >= layouts['FILE_RENAME_INFORMATION']['minimum_used']
    return layouts


def deletion():
    load('_delete_open')
    g.update(_DELETE=0x10000,_FILE_READ_ATTRIBUTES=0x80,_FILE_OPEN=1,
             _FileDispositionInformationEx=64,_FileDispositionInformation=13,
             _where=lambda *_:'review/name',_nt_error=lambda status,name:OSError('status '+str(status)))
    rows=[]
    for responses in ([0],[-1,0],[-1,-2]):
        pending=list(responses);calls=[];closed=[]
        g.update(_nt_open=lambda *_:123,_is_surrogate=lambda _:(False,False),_close_handle=closed.append)
        def set_info(h,cls,data):
            calls.append({'handle':h,'class':cls,'size':ctypes.sizeof(data),'value':data.value})
            return pending.pop(0)
        g['_set_info']=set_info
        error=None
        try:g['_delete_open'](9,'f',want_dir=False)
        except OSError as exc:error=str(exc)
        assert closed == [123] and not pending
        assert [c['class'] for c in calls] == ([64] if len(responses)==1 else [64,13])
        assert calls[0]['size']==4 and calls[0]['value']==0x13
        if len(calls)==2:assert calls[1]['size']==1 and calls[1]['value']==1
        assert bool(error)==(responses[-1]<0)
        rows.append({'statuses':responses,'calls':calls,'closed':closed,'error':error})
    return rows


def open_failures():
    load('_open_checked');load('_to_fd')
    rows=[]
    for link,is_dir,want in [(True,False,False),(False,True,False),(False,False,True),(False,False,False)]:
        closed=[]
        g.update(_nt_open=lambda *_:222,_is_surrogate=lambda _:(link,is_dir),_close_handle=closed.append)
        failed=False
        try:answer=g['_open_checked'](9,'f',1,1,1,want_dir=want)
        except OSError:failed=True
        assert failed == (link or is_dir!=want)
        assert closed==([222] if failed else [])
        rows.append({'link':link,'is_dir':is_dir,'want_dir':want,'failed':failed,'raw_closed':closed})
    closed=[]
    def failed_wrap(*_):raise OSError('review CRT refusal')
    g.update(msvcrt=SimpleNamespace(open_osfhandle=failed_wrap),_close_handle=closed.append)
    try:g['_to_fd'](333,True)
    except OSError:pass
    else:raise AssertionError('Expected refusal')
    assert closed==[333]
    rows.append({'CRT_failure_raw_closed':closed})
    return rows


def directory_records():
    load('listdir_fd')
    names=['simple.JPG','\u76ee\u5f55-\U0001f4f7.DNG']
    records=[]
    for index,name in enumerate(names):
        raw=name.encode('utf-16-le')
        size=(68+len(raw)+7)//8*8
        record=bytearray(size)
        struct.pack_into('<I',record,0,size if index+1<len(names) else 0)
        struct.pack_into('<I',record,60,len(raw))
        record[68:68+len(raw)]=raw
        records.append(record)
    data=b''.join(records);classes=[]
    def get_info(h,cls,buf,size):
        classes.append(cls)
        if len(classes)>1:return False
        ctypes.memmove(buf,data,len(data))
        return True
    class CtypesView:
        def __getattr__(self,name):return getattr(ctypes,name)
        def get_last_error(self):return 18
    g.update(ctypes=CtypesView(),sys=SimpleNamespace(audit=lambda *_:None),fd_path=lambda _:'review',
             _handle=lambda _:100,_GetInfoEx=get_info,_FileFullDirectoryRestartInfo=15,
             _FileFullDirectoryInfo=14,_ERROR_NO_MORE_FILES=18)
    result=g['listdir_fd'](9)
    assert result==names and classes==[15,14]
    return {'names':result,'classes':classes,'length_offset':60,'name_offset':68}


result={'scope':'Windows x64 ABI layout and host model of production control flow; no Windows API execution',
        'layouts':declarations(),'delete':deletion(),'open_failures':open_failures(),'directory_records':directory_records()}
(OUT/'windows-contracts.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False))
