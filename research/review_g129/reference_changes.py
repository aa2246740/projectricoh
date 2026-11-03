"""Record old and new mathematical expectations for shared menu values."""
from pathlib import Path
import ctypes as ct
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent

class OldLevels(ct.Structure):_fields_=[('v',ct.c_int8*11)]
class NewLevels(ct.Structure):_fields_=[('v',ct.c_int16*10)]
class Request(ct.Structure):_fields_=[('amount',ct.c_int32),('dose',ct.c_int32*10),('wb',ct.c_int32),('tone',ct.c_int32)]

def memory(raw):return (ct.c_uint8*len(raw)).from_buffer_copy(raw)
def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
    folder=WORK/'local/integrated-host/host'
    old=ct.CDLL(str(folder/'reference.dylib'));new=ct.CDLL(str(folder/'engine.dylib'))
    old.g129_open.argtypes=new.g129_open.argtypes=[ct.c_void_p,ct.c_uint,ct.c_uint]
    old.g129_compute.argtypes=[ct.c_uint,ct.POINTER(OldLevels),ct.c_void_p]
    new.g129_compute.argtypes=[ct.c_uint,ct.POINTER(NewLevels),ct.c_void_p]
    new.g129_request.argtypes=[ct.c_uint,ct.POINTER(NewLevels),ct.POINTER(Request)]
    before=(ROOT/'firmware/package_v36_g127/SD_ROOT/GXRCE.DAT').read_bytes()
    after=(ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes()
    assert sha(after)=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
    old_dat=memory(before);new_dat=memory(after);rows=[];outputs=bytearray();defaults=0
    for unit,label in enumerate(('50mm','28mm','mount')):
        assert old.g129_open(old_dat,len(before),unit)==0 and new.g129_open(new_dat,len(after),unit)==0
        for slot in range(1,9):
            cases=[(None,0)]+[(control,value) for control in range(4) if not (slot==3 and control==3) for value in (-1,1)]
            for control,value in cases:
                old_vector=[0]*11;new_vector=[100]+[0]*9
                if control is not None:
                    old_vector[control]=value;new_vector[(1,2,3,5)[control]]=value
                old_levels=OldLevels((ct.c_int8*11)(*old_vector));new_levels=NewLevels((ct.c_int16*10)(*new_vector))
                old_out=(ct.c_uint8*552)();new_out=(ct.c_uint8*552)();request=Request()
                assert old.g129_compute(slot,ct.byref(old_levels),old_out)==0
                assert new.g129_compute(slot,ct.byref(new_levels),new_out)==0
                assert new.g129_request(slot,ct.byref(new_levels),ct.byref(request))==0
                if control is None:assert bytes(old_out)==bytes(new_out);defaults+=1
                rows.append({'unit':label,'slot':slot,'old_control':control,
                             'new_control':None if control is None else (1,2,3,5)[control],'level':value,
                             'before_vector':old_vector,'after_vector':new_vector,
                             'after_request':[request.amount,*request.dose,request.wb,request.tone],
                             'before_output_sha256':sha(bytes(old_out)),'after_output_sha256':sha(bytes(new_out)),
                             'different_byte_count':sum(a!=b for a,b in zip(old_out,new_out))})
                outputs.extend(bytes(old_out)+bytes(new_out))
    assert len(rows)==210 and defaults==24
    destination=WORK/'local/reference-changes';destination.mkdir(parents=True,exist_ok=True)
    binary=destination/'expected-entries.bin';binary.write_bytes(outputs)
    result={'status':'DOCUMENTED','before_dat_sha256':sha(before),'after_dat_sha256':sha(after),
            'records':len(rows),'identical_defaults':defaults,
            'changed_records':sum(bool(row['different_byte_count']) for row in rows),
            'before_library_sha256':sha((folder/'reference.dylib').read_bytes()),
            'after_library_sha256':sha((folder/'engine.dylib').read_bytes()),
            'binary_sha256':sha(outputs),'cases':rows}
    (WORK/'reference-changes.json').write_text(json.dumps(result,indent=2)+'\n')
    text='''旧参考与新参考的具体值见 reference-changes.json：三个单元、八个配方的默认值，以及旧四项的 −1/+1，共210条。03没有旧Satu条目。每条列出旧11字节向量、新20字节向量、实际r2请求、旧/新552B输出SHA和改变的字节数；完整字节只在已忽略的local/reference-changes/expected-entries.bin。

旧库与新库均来自本轮重新编译。24个默认完整输出相同。新参考使用冻结r2点表和整数数学，旧四项0/1/2/3对应新控制1/2/3/5，Amount默认100；依据为设计和用户修正。这里不改写旧脚本，也不据参考结果给失败的旧套件补记PASS。旧WB非零尾部期望没有迁移，相关用例若未闭合仍须保留。
'''
    (WORK/'REFERENCE_CHANGES.md').write_text(text)
    print(json.dumps({'name':'reference_expectation_values','returncode':0,'records':len(rows),'defaults':defaults,'changed':result['changed_records']}))

if __name__=='__main__':main()
