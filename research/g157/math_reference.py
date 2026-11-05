"""Host C record mathematics, independent of the running simulated unit."""
import ctypes as T
import common as C
D=C.D
class View(T.Structure):_fields_=[('bytes',T.c_void_p),('length',T.c_uint32)]
class Levels(T.Structure):_fields_=[('v',T.c_int16*10)]
class Request(T.Structure):_fields_=[('amount',T.c_int32),('dose',T.c_int32*10),('wb',T.c_int32),('tone',T.c_int32)]
class Reference:
    def __init__(self):
        self.lib=T.CDLL(str(C.LOCAL/'parser/parsers.dylib'))
        self.lib.kv_data_open.argtypes=[T.c_void_p,T.c_size_t,T.POINTER(View)]
        self.lib.kv_data_request.argtypes=[T.POINTER(View),T.c_uint,T.c_uint,T.POINTER(Levels),T.POINTER(Request)]
        self.lib.kv_apply_work.argtypes=[T.c_void_p,T.c_void_p,T.POINTER(Request),T.c_void_p,T.c_void_p,T.c_void_p]
        assert T.sizeof(Request)==52
    def compute(self,raw,unit,base,levels):
        at=D.u32(raw,204)+3392;memory=T.create_string_buffer(raw[at:at+7904]);view=View()
        assert self.lib.kv_data_open(memory,7904,T.byref(view))==0
        values=Levels((T.c_int16*10)(*levels));request=Request()
        assert self.lib.kv_data_request(T.byref(view),unit,base[0],T.byref(values),T.byref(request))==0
        out=T.create_string_buffer(552);stats=T.create_string_buffer(28);work=T.create_string_buffer(2288)
        assert self.lib.kv_apply_work(T.create_string_buffer(D.expand(raw,unit,4)),T.create_string_buffer(base),T.byref(request),out,stats,work)==0
        return out.raw
def user_record(raw,index):
    at=D.u32(raw,204)+1408;record=raw[at+D.u32(raw,at+36)+24*index:at+D.u32(raw,at+36)+24*(index+1)]
    assert len(record)==24;values=[100]+[0]*9
    for old,control in enumerate((1,2,3,5)):
        value=record[10+old];values[control]=value if value<128 else value-256
    return record[0],values
