"""复用现有主机 C 数学参照，按最终 DAT 计算完整 552 B。"""
from pathlib import Path
import ctypes as C
import importlib.util
import os
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1/reference')
sys.path.insert(0,str(ROOT/'research/v39_g153'))
from dat_format import expand,expand_effect,u32


class View(C.Structure):_fields_=[('bytes',C.c_void_p),('length',C.c_uint32)]
class Levels(C.Structure):_fields_=[('v',C.c_int16*10)]
class Request(C.Structure):_fields_=[('amount',C.c_int32),('dose',C.c_int32*10),('wb',C.c_int32),('tone',C.c_int32)]


class Reference:
    def __init__(self,generation):
        tree={153:'engine_v62_g153',154:'engine_v63_g154',155:'engine_v64_g155'}[generation]
        spec=importlib.util.spec_from_file_location('g154_format_'+str(generation),ROOT/'research/v39_g153/format_checks.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.TMP=TMP/str(generation);module.PRODUCT=ROOT/('firmware/'+tree+'/candidate/containers/product');module.HERE=HERE
        self.lib=module.library()
        self.lib.kv_data_open.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(View)]
        self.lib.kv_data_request.argtypes=[C.POINTER(View),C.c_uint,C.c_uint,C.POINTER(Levels),C.POINTER(Request)]
        self.lib.kv_apply_work.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(Request),C.c_void_p,C.c_void_p,C.c_void_p]
        self.lib.check_window.argtypes=[C.c_uint,C.c_uint,C.c_uint,C.c_void_p]
        assert C.sizeof(Request)==52

    def request(self,raw,unit,slot,levels):
        at=u32(raw,204)+3392;memory=C.create_string_buffer(raw[at:at+7904]);view=View()
        assert self.lib.kv_data_open(memory,7904,C.byref(view))==0
        values=Levels((C.c_int16*10)(*levels));request=Request()
        result=self.lib.kv_data_request(C.byref(view),unit,slot,C.byref(values),C.byref(request))
        return result,request

    def apply(self,stock,base,request):
        output=C.create_string_buffer(b'\xa5'*552,552);stats=C.create_string_buffer(b'\xa5'*28,28);work=C.create_string_buffer(2288)
        result=self.lib.kv_apply_work(C.create_string_buffer(stock),C.create_string_buffer(base),C.byref(request),output,stats,work)
        if result:assert output.raw==b'\xa5'*552 and stats.raw==b'\xa5'*28
        return result,output.raw

    def compute(self,raw,unit,base,levels):
        result,request=self.request(raw,unit,base[0],levels)
        if result:return result,None
        return self.apply(expand(raw,unit,4),base,request)


def user_record(raw,number):
    at=u32(raw,204)+1408+1216+24*(number-1)
    record=raw[at:at+24];values=[100]+[0]*9
    for previous,current in enumerate((1,2,3,5)):
        value=record[10+previous];values[current]=value if value<128 else value-256
    return record[0],values,record[2:9].decode('ascii')
