"""Knob behaviour on MOUNT after the table change (computer, host C build of the g139m engine sources).

The knob data block (GXKV2R2, unchanged in g139m) holds per-unit dose curves and
caps; MOUNT's were derived from MOUNT's old rows, and the engine's kv_data.c
hard-codes MOUNT's caps and Amount steps. This script measures what that means
on the new rows, per slot / control / level:

  - dead steps: two adjacent levels give byte-identical 552-byte entries;
  - clamps: KvStats.clamps > 0 at that level (byte saturation inside kv_math);
  - step size: median dE00 between adjacent levels on the 1533 street grid
    (MOUNT UnitModel of research/recipe_iso_unit_drift); the knob tables were
    built so every adjacent pair is >= 1.0 on their own chart region;
  - MOUNT vs 50mm: whether the same knob level gives the same entry on both units.

Configurations: g139 MOUNT (old rows + MOUNT knobs), g139m MOUNT (50mm rows + MOUNT
knobs), g139m 50mm (50mm rows + 50mm knobs, the reference).
Writes research/g139m/knob_check.json. Homebrew python3 -I -B (numpy).
"""
from pathlib import Path
import ctypes as ct
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g139m/knobs')
TMP.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(TMP)
sys.path.insert(0, str(HERE))
import decode as D  # noqa: E402
sys.path.insert(0, str(ROOT / 'research/recipe_iso_unit_drift'))
import drift_common as dc  # noqa: E402
dc.LOCAL, dc.TMP = HERE / 'local/preview', TMP
os.environ['TMPDIR'] = str(TMP)          # drift_common sets its own TMPDIR on import
import mount_model as mm  # noqa: E402
mm.s.HERE, mm.s.LOCAL = HERE, HERE / 'local/preview'
import numpy as np  # noqa: E402

PRODUCT = ROOT / 'firmware/engine_v57_g139m/candidate/containers/product'
PRODUCT_G139 = ROOT / 'firmware/engine_v56_g139/candidate/containers/product'   # read-only: its sources accept build 139
G139 = ROOT / 'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT'
G139M = ROOT / 'firmware/package_v38_g139m/local/SD_ROOT/GXRCE.DAT'
CONTROLS = ('Amt', 'Cont', 'High', 'Shad', 'Fade', 'Satu', 'Warm', 'Tint', 'Splt', 'Filt')


class Levels(ct.Structure):
    _fields_ = [('v', ct.c_int16 * 10)]


class Stats(ct.Structure):
    _fields_ = [('v', ct.c_int32 * 7)]


def library(PRODUCT, tag):
    core, container = PRODUCT / 'src/firmware/engine/core', PRODUCT / 'src/firmware/card_container_v2'
    sources = [ROOT / 'research/emptystack_v38/host_engine.c', PRODUCT / 'memory.c', PRODUCT / 'ui_v2_data.c',
               PRODUCT.parents[1] / 'engine_services/crc.c']
    sources += [core / n for n in ('eng_data.c', 'eng_semantic.c', 'eng_crc_compat.c', 'eng_pin_stub.c')]
    sources += [container / n for n in ('common.c', 'gate.c', 'api.c')]
    sources += [PRODUCT / 'kv2' / n for n in ('kv_data.c', 'kv_ui.c', 'kv_math.c', 'kv_i64.c')]
    out = TMP / f'knob-host-{tag}.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-shared', '-fPIC', '-DENG_HOST', '-ffreestanding', '-fno-builtin',
                    '-I', str(core), '-I', str(PRODUCT), '-I', str(container), *map(str, sources), '-o', str(out)],
                   check=True, capture_output=True)
    return ct.CDLL(str(out))


LIBS = {G139: library(PRODUCT_G139, 'g139'), G139M: library(PRODUCT, 'g139m')}
SAMPLE = np.load(ROOT / 'research/recipe_iso_unit_drift/local/samples/R8051533.npz')['x']
M = mm.UnitModel('mount', iso=200)


def entry448(e552, stock552):
    import struct
    S = mm.SRC
    p, s = e552[:448], stock552[:448]
    rows = tuple(p[o:o + n] for o, n in zip(S.ROW_OFFSETS, S.ROW_BYTES))
    srows = tuple(s[o:o + n] for o, n in zip(S.ROW_OFFSETS, S.ROW_BYTES))
    mask = p[1]
    written = tuple(rows[r] if not bit or mask & bit else srows[r] for r, bit in enumerate(S.ROW_BITS))
    return dict(slot=p[0], mask=mask, rows=rows, control=struct.unpack_from('>H', p, S.CONTROL_OFFSET)[0], written=written)


def render(slot, e552, stock552):
    entries = {'04': entry448(stock552, stock552), f'{slot:02d}': entry448(e552, stock552)}
    M.base.entries = entries
    if slot == 3:
        r = M.mm.MatrixRow.from_bytes(entries['03']['written'][3][:28])
        y = r.apply(M.pre('03', SAMPLE))[0]
        return np.clip(np.repeat(y[:, None], 3, axis=1), 0, 255)
    return M.predict(f'{slot:02d}', SAMPLE)


def sweep(dat_path, unit):
    raw = dat_path.read_bytes()
    mods = D.modules(raw)
    m = mods[unit]
    stock = m['entries'][4]
    LIB = LIBS[dat_path]
    buf = (ct.c_uint8 * len(raw)).from_buffer_copy(raw)
    assert LIB.g135_open(buf, len(raw), unit) == 0
    out = {}
    for slot in (1, 2, 3, 5, 6, 7, 8):
        base = m['entries'][m['refs'][slot - 1]]
        for control in range(10):
            levels = range(0, 151, 5) if control == 0 else range(-9, 10)
            rows = []
            for level in levels:
                v = [100] + [0] * 9
                v[control] = level
                request = (ct.c_uint8 * 52)()
                if LIB.g135_request(slot, ct.byref(Levels((ct.c_int16 * 10)(*v))), request) != 0:
                    continue
                e = (ct.c_uint8 * 552)()
                if LIB.g135_compute(slot, ct.byref(Levels((ct.c_int16 * 10)(*v))), e) != 0:
                    continue
                st, golden = Stats(), (ct.c_uint8 * 552)()
                s552 = (ct.c_uint8 * 552)(*stock); b552 = (ct.c_uint8 * 552)(*base)
                rc = LIB.g135_golden(s552, b552, request, golden, ct.byref(st))
                rows.append(dict(level=level, entry=bytes(e), clamps=st.v[0] if rc == 0 else None,
                                 golden_equal=rc == 0 and bytes(golden) == bytes(e)))
            if len(rows) > 1 and not (control == 0 and slot == 4):
                out[(slot, control)] = rows
    return out, stock


def summarise(rows, slot, stock, render_steps=True):
    dead = [(a['level'], b['level']) for a, b in zip(rows, rows[1:]) if a['entry'] == b['entry']]
    clamps = [r['level'] for r in rows if r['clamps']]
    res = dict(levels=[rows[0]['level'], rows[-1]['level']], dead_steps=dead, clamp_levels=clamps,
               golden_mismatch=[r['level'] for r in rows if not r['golden_equal']])
    if render_steps:
        lab = [M.fs.lab_from_codes(np.asarray(render(slot, r['entry'], stock), float)) for r in rows]
        steps = [float(np.median(M.fs.delta_e00(a, b))) for a, b in zip(lab, lab[1:])]
        res['min_step_de'] = min(steps)
        res['steps_below_1'] = [(rows[i]['level'], rows[i + 1]['level'], round(s, 2)) for i, s in enumerate(steps) if s < 1.0]
    return res


def main():
    configs = {'g139_mount': (G139, 2), 'g139m_mount': (G139M, 2), 'g139m_50mm': (G139M, 0)}
    sweeps = {k: sweep(p, u) for k, (p, u) in configs.items()}
    result = {}
    for (slot, control), rows in sorted(sweeps['g139m_mount'][0].items()):
        if slot == 4:
            continue
        key = f'{slot:02d}-{CONTROLS[control]}'
        row = {}
        for name, (data, stock) in sweeps.items():
            if (slot, control) in data:
                row[name] = summarise(data[(slot, control)], slot, stock)
        ref = {r['level']: r['entry'] for r in sweeps['g139m_50mm'][0].get((slot, control), [])}
        mine = {r['level']: r['entry'] for r in rows}
        row['mount_vs_50mm_same_levels'] = sorted(set(mine) & set(ref)) == sorted(mine) == sorted(ref)
        row['mount_levels_equal_50mm_entry'] = sum(1 for l in mine if l in ref and mine[l] == ref[l])
        row['mount_levels'] = len(mine)
        stock_m, stock_f = sweeps['g139m_mount'][1], sweeps['g139m_50mm'][1]
        gaps = {l: float(np.median(M.fs.delta_e00(M.fs.lab_from_codes(np.asarray(render(slot, mine[l], stock_m), float)),
                                                   M.fs.lab_from_codes(np.asarray(render(slot, ref[l], stock_f), float)))))
                for l in sorted(set(mine) & set(ref))}
        row['mount_vs_50mm_de_by_level'] = {str(k): round(v, 3) for k, v in gaps.items()}
        row['mount_vs_50mm_de_max'] = max(gaps.values()) if gaps else None
        result[key] = row
        print(key, {k: (v['levels'], len(v['dead_steps']), len(v['clamp_levels']), round(v.get('min_step_de', 0), 2))
                    for k, v in row.items() if k in configs},
              'equal50', row['mount_levels_equal_50mm_entry'], '/', row['mount_levels'],
              'dE_vs_50mm_max', row['mount_vs_50mm_de_max'] and round(row['mount_vs_50mm_de_max'], 2), flush=True)
    # GRN*001 (test package user entry: base 02, Cont 2 High 5 Shad 5 Satu -5) on MOUNT vs 50mm
    grn = {}
    for name, (path, unit) in configs.items():
        raw = path.read_bytes(); lib = LIBS[path]
        assert lib.g135_open((ct.c_uint8 * len(raw)).from_buffer_copy(raw), len(raw), unit) == 0
        e = (ct.c_uint8 * 552)()
        assert lib.g135_compute(2, ct.byref(Levels((ct.c_int16 * 10)(100, 2, 5, 5, 0, -5, 0, 0, 0, 0))), e) == 0
        grn[name] = (bytes(e), sweeps[name][1])
    lab = {k: M.fs.lab_from_codes(np.asarray(render(2, e, st), float)) for k, (e, st) in grn.items()}
    result['GRN*001'] = dict(mount_g139m_vs_50mm_de=float(np.median(M.fs.delta_e00(lab['g139m_mount'], lab['g139m_50mm']))),
                             mount_g139_vs_50mm_de=float(np.median(M.fs.delta_e00(lab['g139_mount'], lab['g139m_50mm']))),
                             L_mount_g139=float(np.median(lab['g139_mount'][:, 0])), L_mount_g139m=float(np.median(lab['g139m_mount'][:, 0])),
                             L_50mm=float(np.median(lab['g139m_50mm'][:, 0])))
    print('GRN*001', result['GRN*001'])
    (HERE / 'knob_check.json').write_text(json.dumps(result, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
