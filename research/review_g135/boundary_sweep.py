"""Independent boundary sweep on the integrated compute path (replaces the retired uv_levels/uv_window range test of project_boundary.py).

Builds its own host library from the g135 product sources (same file list as the implementation host check), opens the gen 135 DAT for each unit
and checks, for every recipe slot and every control id 0..9: every table point is accepted, every other value in a wide range is rejected
with the output buffer untouched, controls that the recipe does not list reject any non-default value, invalid slot numbers are rejected.
"""
from pathlib import Path
import ctypes as ct
import hashlib
import json
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
IMPL = ROOT / 'research/g135_v37'
ENGINE = ROOT / 'firmware/engine_v53_g135'
P = ENGINE / 'candidate/containers/product'
LOCAL = WORK / 'local/host'

class Levels(ct.Structure):
    _fields_ = [('v', ct.c_int16 * 10)]

def build():
    core = P / 'src/firmware/engine/core'
    container = P / 'src/firmware/card_container_v2'
    source = [IMPL / 'host_engine.c', P / 'memory.c', P / 'ui_v2_data.c', P.parents[1] / 'engine_services/crc.c']
    source += [core / n for n in ('eng_data.c', 'eng_semantic.c', 'eng_crc_compat.c', 'eng_pin_stub.c')]
    source += [container / n for n in ('common.c', 'gate.c', 'api.c')]
    source += [P / 'kv2' / n for n in ('kv_data.c', 'kv_ui.c', 'kv_math.c', 'kv_i64.c')]
    LOCAL.mkdir(parents=True, exist_ok=True)
    output = LOCAL / 'sweep-engine.dylib'
    args = ['clang', '-std=c11', '-O2', '-shared', '-fPIC', '-DENG_HOST', '-ffreestanding', '-fno-builtin',
            '-I', str(core), '-I', str(P), '-I', str(container)]
    run = subprocess.run(args + [str(p) for p in source] + ['-o', str(output)], capture_output=True, text=True, timeout=1200)
    (LOCAL / 'sweep-build.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stderr[-3000:]
    lib = ct.CDLL(str(output))
    lib.g135_open.argtypes = [ct.c_void_p, ct.c_uint, ct.c_uint]
    lib.g135_compute.argtypes = [ct.c_uint, ct.POINTER(Levels), ct.c_void_p]
    lib.g135_invalid_preview.argtypes = [ct.c_uint]
    return lib, hashlib.sha256(output.read_bytes()).hexdigest()

def main():
    lib, library_sha = build()
    dat = (ROOT / 'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT').read_bytes()
    block = (ROOT / 'firmware/kv2_modules/data_ui/local/gxkv2r2.bin').read_bytes()
    # the seventh section of the DAT carries the same block as the frozen module file
    start, length = struct.unpack_from('>II', dat, 132 + 12 * 6)
    section = dat[256 + start:256 + start + length]
    assert block in section, 'frozen gxkv2r2.bin is not inside the gen 135 seventh section'
    mem = (ct.c_uint8 * len(dat)).from_buffer_copy(dat)
    totals = dict(accepted_points=0, rejected_values=0, unlisted_control_rejects=0, invalid_slots=0, output_untouched=0)
    failures = []
    values_off = [v for v in range(-40, 41)] + [100, 127, -127, -128, 255, 256, 32767, -32768, 1000, -1000]
    for unit in range(3):
        assert lib.g135_open(mem, len(dat), unit) == 0
        for invalid in (0, 9, 10, 255, 256, 65535):
            assert lib.g135_invalid_preview(invalid) == 1, ('invalid_slot', unit, invalid)
            totals['invalid_slots'] += 1
        for slot in range(1, 9):
            recipe = block[64 + 16 * (unit * 8 + slot - 1):80 + 16 * (unit * 8 + slot - 1)]
            first = struct.unpack_from('>H', recipe, 4)[0]
            listed = {}
            for index in range(first, first + recipe[2]):
                item = block[448 + 16 * index:464 + 16 * index]
                offset = struct.unpack_from('>I', item, 12)[0]
                listed[item[0]] = {struct.unpack_from('>h', block, offset + 4 * i)[0] for i in range(item[1])}
            for control in range(10):
                for value in sorted(set(values_off) | listed.get(control, set())):
                    state = Levels((ct.c_int16 * 10)(*([100] + [0] * 9)))
                    state.v[control] = value
                    out = (ct.c_uint8 * 552)(*([165] * 552))
                    status = lib.g135_compute(slot, ct.byref(state), out)
                    # the default of every control is also valid, so the listed default and the Amount default 100 are accepted points
                    default = 100 if control == 0 else 0
                    allowed = (control in listed and value in listed[control]) or value == default
                    if allowed != (status == 0):
                        failures.append(dict(unit=unit, slot=slot, control=control, value=value, status=status, allowed=allowed))
                    if allowed:
                        totals['accepted_points'] += 1
                    else:
                        totals['rejected_values'] += 1
                        if control not in listed:
                            totals['unlisted_control_rejects'] += 1
                        if bytes(out) == bytes([165] * 552):
                            totals['output_untouched'] += 1
                        else:
                            failures.append(dict(unit=unit, slot=slot, control=control, value=value, output_modified=True))
    result = dict(status='PASS' if not failures else 'FAIL', dat_sha256=hashlib.sha256(dat).hexdigest(), library_sha256=library_sha,
                  failures=failures[:50], failure_count=len(failures), **totals)
    (WORK / 'boundary-sweep.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'failures'}))

if __name__ == '__main__':
    main()
