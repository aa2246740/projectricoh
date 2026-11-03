"""Compile and call the C mirror. Compiler scratch and binaries stay local."""
import ctypes as ct
import os
import subprocess
from pathlib import Path
import support as s
import knobs as k


class CRequest(ct.Structure):
    _fields_=[('amount',ct.c_int32),('dose',ct.c_int32*10),('wb_method',ct.c_int32),('tone_method',ct.c_int32)]


class CStats(ct.Structure):
    _fields_=[(n,ct.c_int32) for n in ('clamps','node_repairs','monotone_repairs','slope_repairs','colour_cap','matrix_cap','rowsum_cap')]


class C:
    def __init__(self,build=True):
        self.path=s.LOCAL/'knobs.dylib'
        if build:
            command=['/usr/bin/clang','-std=c99','-O2','-Wall','-Wextra','-Werror','-pedantic',
                     '-fno-modules','-fno-implicit-modules','-dynamiclib',str(s.HERE/'src/knobs.c'),'-o',str(self.path)]
            cp=subprocess.run(command,text=True,capture_output=True)
            (s.LOCAL/'compile.log').write_text(' '.join(command)+'\n'+cp.stdout+cp.stderr)
            cp.check_returncode()
        self.lib=ct.CDLL(str(self.path))
        self.lib.kv_apply.argtypes=[ct.c_void_p,ct.c_void_p,ct.POINTER(CRequest),ct.c_void_p,ct.POINTER(CStats)]
        self.lib.kv_apply.restype=ct.c_int

    def apply(self,stock,base,request):
        request.validate()
        rq=CRequest(request.amount,(ct.c_int32*10)(*request.doses),request.wb_method,request.tone_method)
        out=(ct.c_uint8*552)();stats=CStats()
        rc=self.lib.kv_apply(stock,base,ct.byref(rq),out,ct.byref(stats))
        if rc:raise ValueError('C apply returned '+str(rc))
        return bytes(out),{n:getattr(stats,n) for n,_ in stats._fields_}


def compare(c,stock,base,request):
    py,ps=k.apply(stock,base,request);cc,cs=c.apply(stock,base,request)
    if py!=cc or ps!=cs:
        raise AssertionError(dict(request=request,byte_diff=[i for i,(a,b) in enumerate(zip(py,cc)) if a!=b],python=ps,c=cs))
    return py,ps
