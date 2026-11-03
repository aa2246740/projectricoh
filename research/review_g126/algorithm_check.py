"""Audit legacy levels against actual packaged rows, including joint tone settings."""
from pathlib import Path
import ctypes
import itertools
import json
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

OFFSETS = (20,82,115,216,284,346,379,456,518)
SIZES = (62,33,96,56,62,33,66,62,33)

def u16(p, at):
    return struct.unpack_from('>H', p, at)[0]

def u32(p, at):
    return struct.unpack_from('>I', p, at)[0]

def unpack(raw, unit, slot):
    directory = u32(raw,156)+64*unit
    table = u32(raw,directory+20)
    count = raw[directory+30]
    descriptors = [raw[table+16+20*i:][:20] for i in range(count)]
    meta = u32(raw,directory+24)+(slot-1)*28
    desc = descriptors[raw[meta+24]]
    shared = u32(raw,192)
    out = bytearray(552)
    out[0:2] = desc[:2]
    out[4:8] = desc[4:8]
    out[445:447] = desc[2:4]
    for off, kind, index in zip((20,82,115,216,284,346,379,412,456,518), (0,1,2,3,0,1,1,1,0,1), desc[8:18]):
        pool = shared+16+12*kind
        size = u16(raw,pool+2)
        at = shared+u32(raw,pool+4)+index*size
        out[off:off+size] = raw[at:at+size]
    mapping = raw[u32(raw,directory+12):][:152]
    return out, mapping

class Algorithm:
    def __init__(self):
        lib = OUT/'local'/('legacy_algorithm-'+str(os.getpid())+'.dylib')
        source = TREE/'candidate/containers/product/src/research/recipe_tweak/r2/tweak_int.c'
        if not lib.exists():
            run(['/usr/bin/clang','-std=c11','-O2','-fPIC','-dynamiclib',source,'-o',lib], 'legacy-algorithm-compile-'+str(os.getpid()))
        self.lib = ctypes.CDLL(str(lib))
        self.U8 = ctypes.c_uint8
        self.lib.rt_tone.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_void_p]
        self.lib.rt_saturation.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]

    def compute(self, base, stock, levels):
        entry = bytearray(base)
        for i, bit in ((3,1),(4,16),(5,16),(6,2)):
            off,size = OFFSETS[i],SIZES[i]
            if not entry[1]&bit:
                entry[off:off+size] = stock[off:off+size]
        data = (self.U8*552).from_buffer(entry)
        address = ctypes.addressof(data)
        contrast, highlight, shadow, saturation = levels[:4]
        pairs = [(20,82),(456,518)]
        if base[1]&2:
            pairs += [(20,379),(20,412)]
        if base[1]&16:
            pairs += [(284,346)]
        for a,b in pairs:
            if self.lib.rt_tone(address+a,address+b,320,contrast,highlight,shadow,address+b) < 0:
                raise ValueError('tone level rejected')
        gains = (ctypes.c_uint16*3)()
        if self.lib.rt_saturation(address+115,address+216,saturation,base[0]!=3,
                                  address+115,address+216,gains) < 0:
            raise ValueError('saturation level rejected')
        if entry[216:272] != stock[216:272]:
            entry[1] |= 1
        return bytes(entry)

def effect(entry):
    return b''.join(entry[off:off+size] for off,size in zip(OFFSETS,SIZES))+entry[445:447]

def main():
    raw = DAT.read_bytes()
    algorithm = Algorithm()
    all_records = []
    for unit in range(3):
        stock,_ = unpack(raw,unit,4)
        for slot in range(1,9):
            base,_ = unpack(raw,unit,slot)
            candidates = {}
            for c,h,s in itertools.product(range(-5,6),repeat=3):
                levels = (c,h,s,0)
                result = algorithm.compute(base,stock,levels)
                candidates[(c,h,s)] = effect(result)
            dead = []
            for levels, value in candidates.items():
                for param in range(3):
                    if levels[param] == 5:
                        continue
                    other = list(levels);other[param] += 1
                    if value == candidates[tuple(other)]:
                        dead.append(dict(levels=levels,param=param+1))
            valid_radius = 5
            for radius in range(1,6):
                if any(all(-radius<=v<=radius for v in row['levels']) and
                       row['levels'][row['param']-1] < radius for row in dead):
                    valid_radius = radius-1
                    break
            saturation = [effect(algorithm.compute(base,stock,(0,0,0,v))) for v in range(-5,6)]
            satu_dead = [i-5 for i in range(10) if saturation[i]==saturation[i+1]] if slot!=3 else []
            record = dict(unit=unit,base=slot,joint_tone_cases=1331,
                          dead_joint_edges=len(dead),safe_tone_radius=valid_radius,
                          saturation_dead_edges=satu_dead,black_white_saturation_hidden=slot==3)
            all_records.append(record)
            if dead:
                save(f'local/dead-edges-{unit}-{slot}.json',dead)
            print(unit,slot,record,flush=True)
    save('evidence/algorithm-ranges.json',dict(status='PASS' if all(x['safe_tone_radius']>0 and not x['saturation_dead_edges'] for x in all_records) else 'FAIL',
         base_sha256=sha(raw),range_request=9,legacy_exposed_radius=5,records=all_records,
         outside_exposed='Levels ±6..±9 are rejected by the project range boundary. ±9 also exceeds the legacy algorithm contract.'))

if __name__ == '__main__':
    main()
