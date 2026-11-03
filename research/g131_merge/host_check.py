"""Check the host build of the integrated source against complete r2 records."""
from pathlib import Path
import ctypes as ct
import hashlib
import json
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,ENGINE,enable,check_inputs

LOCAL=WORK/'local/host'
P=ENGINE/'candidate/containers/product'

class Levels(ct.Structure):_fields_=[('v',ct.c_int16*10)]
class Request(ct.Structure):_fields_=[('amount',ct.c_int32),('dose',ct.c_int32*10),('wb',ct.c_int32),('tone',ct.c_int32)]
class Stats(ct.Structure):_fields_=[('v',ct.c_int32*7)]

def build(reference=False):
    product=(ROOT/'firmware/engine_v48_own/candidate/containers/product') if reference else P
    core=product/'src/firmware/engine/core';container=product/'src/firmware/card_container_v2'
    source=[WORK/'host_engine.c',product/'memory.c',product/'ui_v2_data.c',product.parents[1]/'engine_services/crc.c']
    source += [core/n for n in ('eng_data.c','eng_semantic.c','eng_crc_compat.c','eng_pin_stub.c')]
    source += [container/n for n in ('common.c','gate.c','api.c')]
    if reference:source += [product/'src/research/recipe_tweak/r2/tweak_int.c']
    else:source += [product/'kv2'/n for n in ('kv_data.c','kv_ui.c','kv_math.c','kv_i64.c')]
    output=LOCAL/('reference.dylib' if reference else 'engine.dylib')
    args=['clang','-std=c11','-O2','-shared','-fPIC','-DENG_HOST','-ffreestanding','-fno-builtin',
          '-I',str(core),'-I',str(product),'-I',str(container)]
    if reference:args+=['-DG131_REFERENCE']
    run=subprocess.run(args+[str(p) for p in source]+['-o',str(output)],capture_output=True,text=True,timeout=1200)
    (LOCAL/('reference-build.log' if reference else 'build.log')).write_text(run.stdout+run.stderr)
    if run.returncode:raise RuntimeError('host compilation: '+run.stderr[-5000:])
    lib=ct.CDLL(str(output));lib.g131_open.argtypes=[ct.c_void_p,ct.c_uint,ct.c_uint]
    lib.g131_compute.argtypes=[ct.c_uint,ct.POINTER(Levels),ct.c_void_p]
    if not reference:
        lib.g131_request.argtypes=[ct.c_uint,ct.POINTER(Levels),ct.POINTER(Request)]
        lib.g131_golden.argtypes=[ct.c_void_p,ct.c_void_p,ct.POINTER(Request),ct.c_void_p,ct.POINTER(Stats)]
        lib.g131_plan.argtypes=[ct.c_uint,ct.POINTER(Levels),ct.c_uint32,ct.c_void_p]
    else:lib.g127_default.argtypes=[ct.c_uint,ct.c_uint32,ct.c_void_p,ct.c_void_p]
    return lib

def raw_buffer(raw):return (ct.c_uint8*len(raw)).from_buffer_copy(raw)
def levels(values=None):return Levels((ct.c_int16*10)(*([100]+[0]*9 if values is None else values)))
def request(values):return Request(values[0],(ct.c_int32*10)(*values[1:11]),values[11],values[12])

def compute(lib,slot,value):
    out=(ct.c_uint8*552)(*([165]*552));status=lib.g131_compute(slot,ct.byref(value),out)
    assert status==0,('integrated_compute_status',slot,status,list(value.v))
    return bytes(out)

def main():
    enable();check_inputs();LOCAL.mkdir(parents=True,exist_ok=True)
    lib=build();reference=build(True)
    expected={};counts={};digest=hashlib.sha256()
    for label,file in [('golden','parity_cases.bin'),('domain','extended_cases.bin')]:
        count=0
        with (ROOT/'research/kv2_math/local'/file).open('rb') as stream:
            while raw:=stream.read(1740):
                assert len(raw)==1740
                stock,base=raw[:552],raw[552:1104];values=struct.unpack('>13i',raw[1104:1156])
                wanted=struct.unpack('>8i',raw[1156:1188]);out=(ct.c_uint8*552)(*([165]*552));stats=Stats((ct.c_int32*7)(*([-777]*7)))
                req=request(values)
                status=lib.g131_golden(raw_buffer(stock),raw_buffer(base),ct.byref(req),out,ct.byref(stats))
                assert (status,*stats.v)==wanted,('golden_status_stats',label,count)
                assert bytes(out)==raw[1188:],('golden_bytes',label,count)
                if wanted[0]==0:expected[(stock,base,raw[1104:1156])]=raw[1188:]
                digest.update(bytes(out));count+=1
        counts[label]=count
    assert counts=={'golden':13330,'domain':2504}
    dat=(ENGINE/'candidate/local/full-r13/GXRCE.DAT').read_bytes();dat_mem=raw_buffer(dat)
    old=(ROOT/'firmware/package_v36_g127/SD_ROOT/GXRCE.DAT').read_bytes();old_mem=raw_buffer(old)
    block=(ROOT/'firmware/kv2_modules/data_ui/local/gxkv2r2.bin').read_bytes()
    integrated=defaults=plans=resets=amounts=0;by_unit=[];coverage=[]
    for unit,name in enumerate(('jlaunch','qlaunch','l08firm')):
        assert lib.g131_open(dat_mem,len(dat),unit)==0,('host_open',unit)
        assert reference.g131_open(old_mem,len(old),unit)==0,('reference_open',unit)
        for invalid in (0,9,255,256,257,65535):assert lib.g131_invalid_preview(invalid)==1,('invalid_preview_slot',invalid)
        stock=(ENGINE/'candidate/local/full-r13/expanded'/name/'04.entry').read_bytes()
        unit_count=0;cases=bytearray()
        for slot in range(1,9):
            base=(ENGINE/'candidate/local/full-r13/expanded'/name/f'{slot:02}.entry').read_bytes()
            default=levels();new=compute(lib,slot,default)
            plan=(ct.c_uint8*80)();old_plan=(ct.c_uint8*80)();old_out=(ct.c_uint8*552)()
            assert reference.g127_default(slot,0x1234,old_plan,old_out)==0
            assert new==bytes(old_out)==base,('default_full_bytes',unit,slot)
            defaults+=1
            recipe=block[64+16*(unit*8+slot-1):80+16*(unit*8+slot-1)]
            first=struct.unpack_from('>H',recipe,4)[0]
            for item_index in range(first,first+recipe[2]):
                item=block[448+16*item_index:464+16*item_index];control,n=item[:2]
                offset=struct.unpack_from('>I',item,12)[0]
                for point in range(n):
                    value,dose=struct.unpack_from('>hh',block,offset+4*point)
                    state=levels();state.v[control]=value;req=Request()
                    assert lib.g131_request(slot,ct.byref(state),ct.byref(req))==0
                    values=[req.amount,*req.dose,req.wb,req.tone]
                    key=(stock,base,struct.pack('>13i',*values));assert key in expected,('golden_case_missing',unit,slot,control,value)
                    actual=compute(lib,slot,state);assert actual==expected[key],('integrated_point_bytes',unit,slot,control,value)
                    assert lib.g131_plan(slot,ct.byref(state),0x1234,plan)==0
                    assert bytes(plan)==bytes(old_plan),('settings_plan',unit,slot,control,value)
                    cases+=struct.pack('>II10h',unit,slot,*state.v)+actual
                    plans+=1;integrated+=1;unit_count+=1
                coverage.append({'unit':unit,'slot':slot,'control':control,'points':n})
            if slot not in (3,4):
                state=levels([0]+[0]*9);assert compute(lib,slot,state)==stock;amounts+=1
            for a,b in ((1,2),(6,7),(8,1)):
                state=levels();state.v[a]=1
                req=Request()
                if lib.g131_request(slot,ct.byref(state),ct.byref(req)):continue
                compute(lib,slot,state);state.v[b]=1
                if lib.g131_request(slot,ct.byref(state),ct.byref(req)):continue
                compute(lib,slot,state);state.v[a]=0;actual=compute(lib,slot,state)
                separate=levels();separate.v[b]=1;assert actual==compute(lib,slot,separate)
                resets+=1
        assert unit_count>=1000
        (WORK/'local'/f'target-cases-{unit}.bin').write_bytes(cases)
        by_unit.append(unit_count)
    result={'status':'PASS','dat_sha256':hashlib.sha256(dat).hexdigest(),**counts,'golden_output_sha256':digest.hexdigest(),
            'integrated_points':integrated,'points_per_unit':by_unit,'defaults':defaults,'plans':plans,
            'amount_zero':amounts,'reset_sequences':resets,'coverage':coverage}
    (WORK/'host-results.json').write_text(json.dumps(result,indent=2)+'\n')
    check_inputs();print(json.dumps({k:v for k,v in result.items() if k!='coverage'}))

if __name__=='__main__':main()
