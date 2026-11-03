"""Compare C and independent Python integer math for every effect control point."""
from pathlib import Path
import importlib.util
import itertools
import json
import struct
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from dat_format import expand,expand_effect,u16,u32,sha
from math_reference import compute

def load():
    source=ROOT/'studio/src/gxr_studio/engine/knobs.py'
    spec=importlib.util.spec_from_file_location('g152_python_math',source)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module,source

def controls(raw,unit,slot):
    at=u32(raw,204)+3392;recipe=at+64+16*(unit*8+slot-1);out={}
    for i in range(raw[recipe+2]):
        item=at+448+16*(u16(raw,recipe+4)+i);control=raw[item];count=raw[item+1];points=u32(raw,item+12)
        lo=struct.unpack_from('>h',raw,item+2)[0]
        out[control]=[(min(j*raw[item+9],150) if control==0 else lo+j,struct.unpack_from('>h',raw,at+points+2*j)[0]) for j in range(count)]
    return out

def main():
    py,source=load();raw=(ROOT/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT').read_bytes()
    started=time.time_ns();t=time.monotonic();point_cases=pair_cases=cases=0;by_effect=[]
    for unit in range(3):
        stock=expand(raw,unit,4)
        for effect in range(10):
            base=expand_effect(raw,effect);table=controls(raw,unit,base[0]);dose_maps={c:dict(p) for c,p in table.items()};local=0
            def compare(levels):
                nonlocal cases,local
                amount=dose_maps[0][levels[0]] if 0 in dose_maps else 100
                doses=tuple(dose_maps[c][levels[c]] if c in dose_maps else 0 for c in range(1,10))+(0,)
                expected,stats=py.apply(stock,base,py.Request(amount,doses))
                result,actual=compute(raw,unit,base,levels)
                assert result==0 and actual==expected,(unit,effect,levels,result)
                cases+=1;local+=1
            compare([100]+[0]*9)
            for control,points in table.items():
                for value,_ in points:
                    levels=[100]+[0]*9;levels[control]=value;compare(levels);point_cases+=1
            for left,right in itertools.combinations(table,2):
                for a,b in itertools.product((table[left][0][0],table[left][-1][0]),(table[right][0][0],table[right][-1][0])):
                    levels=[100]+[0]*9;levels[left]=a;levels[right]=b;compare(levels);pair_cases+=1
            for last in (False,True):
                levels=[100]+[0]*9
                for control,points in table.items():levels[control]=points[-1 if last else 0][0]
                compare(levels)
            by_effect.append(dict(unit=unit,effect=effect+1,cases=local))
            print('PARITY',unit,effect+1,local,flush=True)
    result=dict(status='PASS',dat_sha256=sha(raw),cases=cases,point_cases=point_cases,pair_extrema_cases=pair_cases,
                python_source=str(source.relative_to(ROOT)),python_source_sha256=sha(source.read_bytes()),by_effect=by_effect,
                started_ns=started,ended_ns=time.time_ns(),seconds=time.monotonic()-t,
                scope='Every legal single control point plus pair extrema and all-control extrema on each final effect for all three units. Full 552-byte results agree between C and Python.')
    (HERE/'evidence/control_parity.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
