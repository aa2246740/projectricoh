"""Host integer reference used to compare the actual target's written bytes."""
from pathlib import Path
import ctypes as C
import os
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import format_checks as F
from dat_format import expand,u32

class View(C.Structure):_fields_=[('bytes',C.c_void_p),('length',C.c_uint32)]
class Levels(C.Structure):_fields_=[('v',C.c_int16*10)]
class Request(C.Structure):_fields_=[('amount',C.c_int32),('dose',C.c_int32*10),('wb',C.c_int32),('tone',C.c_int32)]
LIB=None

def library():
    global LIB
    if LIB is None:
        F.TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g153/math')/os.environ.get('REVIEW_JOB',str(os.getpid()))
        LIB=F.library();LIB.kv_data_open.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(View)]
        LIB.kv_data_request.argtypes=[C.POINTER(View),C.c_uint,C.c_uint,C.POINTER(Levels),C.POINTER(Request)]
        LIB.kv_apply_work.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(Request),C.c_void_p,C.c_void_p,C.c_void_p]
    return LIB

def compute(raw,unit,base,levels):
    lib=library();at=u32(raw,204)+3392;memory=C.create_string_buffer(raw[at:at+7904]);view=View()
    assert lib.kv_data_open(memory,7904,C.byref(view))==0
    values=Levels((C.c_int16*10)(*levels));request=Request()
    assert lib.kv_data_request(C.byref(view),unit,base[0],C.byref(values),C.byref(request))==0
    output=C.create_string_buffer(b'\xa5'*552,552);stats=C.create_string_buffer(b'\xa5'*28,28)
    work=C.create_string_buffer(2288)
    result=lib.kv_apply_work(C.create_string_buffer(expand(raw,unit,4)),C.create_string_buffer(base),C.byref(request),output,stats,work)
    if result:assert output.raw==b'\xa5'*552 and stats.raw==b'\xa5'*28
    return result,output.raw
