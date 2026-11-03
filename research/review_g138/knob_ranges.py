"""Which knob levels are selectable, and do they all take effect?

Host build of the gen 138 engine path (research/emptystack_v38/host_engine.c,
read-only, plus this tree's sources). For every unit/recipe/control the
selectable levels are the knob table's points. Each level is computed with the
real compute path (other controls at default); a level whose 552-byte result
equals its inner neighbour's is "selectable but no further effect".
Output: research/review_g138/knob-ranges.json. /usr/bin/python3 -I -B.
"""
from pathlib import Path
import ctypes as ct
import hashlib
import json
import os
import subprocess
import struct

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g138')
PRODUCT = ROOT / 'firmware/engine_v55_g138/candidate/containers/product'
DAT = ROOT / 'firmware/package_v38_g138/local/SD_ROOT/GXRCE.DAT'
LABELS = ('Amt', 'Cont', 'High', 'Shad', 'Fade', 'Satu', 'Warm', 'Tint', 'Splt', 'Filt')
NAMES = ('50mm', '28mm', 'mount')


class Levels(ct.Structure):
    _fields_ = [('v', ct.c_int16 * 10)]


def build():
    TMP.mkdir(parents=True, exist_ok=True)
    core = PRODUCT / 'src/firmware/engine/core'
    container = PRODUCT / 'src/firmware/card_container_v2'
    sources = [ROOT / 'research/emptystack_v38/host_engine.c', PRODUCT / 'memory.c', PRODUCT / 'ui_v2_data.c',
               PRODUCT.parents[1] / 'engine_services/crc.c']
    sources += [core / n for n in ('eng_data.c', 'eng_semantic.c', 'eng_crc_compat.c', 'eng_pin_stub.c')]
    sources += [container / n for n in ('common.c', 'gate.c', 'api.c')]
    sources += [PRODUCT / 'kv2' / n for n in ('kv_data.c', 'kv_ui.c', 'kv_math.c', 'kv_i64.c')]
    out = TMP / 'knob-engine.dylib'
    args = ['clang', '-std=c11', '-O2', '-shared', '-fPIC', '-DENG_HOST', '-ffreestanding', '-fno-builtin',
            '-I', str(core), '-I', str(PRODUCT), '-I', str(container), *map(str, sources), '-o', str(out)]
    run = subprocess.run(args, capture_output=True, text=True, env=dict(os.environ, TMPDIR=str(TMP)))
    assert run.returncode == 0, run.stderr[-4000:]
    lib = ct.CDLL(str(out))
    lib.g135_open.argtypes = [ct.c_void_p, ct.c_uint, ct.c_uint]
    lib.g135_compute.argtypes = [ct.c_uint, ct.POINTER(Levels), ct.c_void_p]
    lib.g135_default.argtypes = [ct.c_uint, ct.POINTER(Levels)]
    return lib


def items(dat, unit, slot):
    section = struct.unpack_from('>I', dat, 204)[0]
    kv = dat[section + 3392:section + 3392 + 17384]
    r = 64 + (unit * 8 + slot - 1) * 16
    count, first = kv[r + 2], struct.unpack_from('>H', kv, r + 4)[0]
    result = []
    for i in range(count):
        p = 448 + (first + i) * 16
        control, points = kv[p], kv[p + 1]
        lo, hi = struct.unpack_from('>hh', kv, p + 2)
        offset = struct.unpack_from('>I', kv, p + 12)[0]
        levels = [struct.unpack_from('>h', kv, offset + 4 * j)[0] for j in range(points)]
        result.append(dict(control=control, label=LABELS[control], lo=lo, hi=hi, levels=levels))
    return result


def main():
    dat = DAT.read_bytes()
    lib = build()
    memory = (ct.c_uint8 * len(dat)).from_buffer_copy(dat)
    report = dict(dat_sha256=hashlib.sha256(dat).hexdigest(), units={})
    flat = total = 0
    for unit, name in enumerate(NAMES):
        assert lib.g135_open(memory, len(dat), unit) == 0, name
        recipes = {}
        for slot in range(1, 9):
            default = Levels()
            assert lib.g135_default(slot, ct.byref(default)) == 0
            rows = []
            for item in items(dat, unit, slot):
                outputs = {}
                for level in item['levels']:
                    value = Levels((ct.c_int16 * 10)(*default.v))
                    value.v[item['control']] = level
                    out = (ct.c_uint8 * 552)()
                    assert lib.g135_compute(slot, ct.byref(value), out) == 0, (name, slot, item['label'], level)
                    outputs[level] = bytes(out)
                    total += 1
                neutral = default.v[item['control']]
                same = [lv for lv in item['levels'] if lv != neutral and
                        outputs[lv] == outputs[lv - (1 if lv > neutral else -1) if item['control'] else
                                               item['levels'][item['levels'].index(lv) + (-1 if lv > neutral else 1)]]]
                flat += len(same)
                rows.append(dict(label=item['label'], lo=item['lo'], hi=item['hi'], points=len(item['levels']),
                                 no_further_effect=same))
            recipes[slot] = rows
        report['units'][name] = recipes
    report.update(points=total, no_further_effect_points=flat)
    (HERE / 'knob-ranges.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(dict(points=total, no_further_effect_points=flat)))
    for name, recipes in report['units'].items():
        for slot, rows in recipes.items():
            for row in rows:
                if row['no_further_effect'] or row['hi'] != (150 if row['label'] == 'Amt' else 9) or row['lo'] not in (-9, 0):
                    print(name, slot, row['label'], row['lo'], row['hi'], 'flat:', row['no_further_effect'])


if __name__ == '__main__':
    main()
