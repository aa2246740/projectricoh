"""Describe support gaps, yellow/green residuals and the fixed integer tables."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import ROOT, HERE, LOCAL, guard, read, dump, sha
from score import runtime
import argparse
import json
import numpy as np


def lch(lab):
    return lab[:, 0], np.hypot(lab[:, 1], lab[:, 2]), np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360


def main():
    guard()
    r = runtime()
    package = ROOT / 'artifacts/stage2j-packages/tables-v5-fuji-test/DEEPTBL0.DAT'
    blob = package.read_bytes()
    assert blob == package.with_name('DEEPTBL1.DAT').read_bytes()
    assert len(blob) == 3600
    rows = {}
    for slot in ('01', '02'):
        D = r.P.data_of(slot, 200)
        row, A, B = r.P.E.f.unpack_solution(D.current)
        row2 = r.P.MM.row2_from_row1(row, D.rows)[0]
        p = blob[16 + int(slot) * 448:16 + (int(slot) + 1) * 448]
        assert p[115:211] == bytes.fromhex(D.current['colour_words']['row_hex'])
        assert p[216:272] == row.to_bytes() + row2.to_bytes()
        cx, cy = r.P.E.src.unpack_tone(p[20:82], p[82:115])
        assert np.array_equal([0, *cx, 4095], D.a['curve_x']) and np.array_equal(cy, D.a['curve_y'])
        rows[slot] = dict(curve_matches=True, matrix_matches=True, chroma_matches=True)
    dump(HERE / 'round5_identity.json', dict(package_sha256=sha(package), DAT0_equals_DAT1=True,
                                           entries=rows, generated_tables=0))
    out = {}
    for f in read(LOCAL / 'inventory.json'):
        q = read(HERE / ('scores_' + f['id'] + '.json'))
        with np.load(LOCAL / ('scores_' + f['id'] + '.npz'), allow_pickle=False) as z:
            d = dict(z)
        L, C, h = lch(d['base'])
        SL, SC, SH = lch(d['source_scene_lab'])
        stdL, stdC, stdH = lch(d['standard'])
        modeL, modeC, modeH = lch(d['style_observed'])
        masks = dict(scene_yellow_D50_60_120_C25=(SC >= 25) & (SH >= 60) & (SH < 120),
                     GXR04_yellow_D65_90_120_C8=(C >= 8) & (h >= 90) & (h < 120),
                     GXR04_green_D65_150_180_C8=(C >= 8) & (h >= 150) & (h < 180),
                     Standard_yellow_D50_60_120_C25=(stdC >= 25) & (stdH >= 60) & (stdH < 120))
        rec = {}
        for name, mask in masks.items():
            valid = mask & d['valid']
            one = dict(feature_thinned=int(mask.sum()), physically_eligible=int((mask & d['eligible']).sum()),
                       scored=int(valid.sum()))
            if valid.any():
                one['score200'] = r.score(d['target'][valid], d['pred200'][valid], d['base'][valid])
                one['median_observed_vs_standard_delta_L'] = float(np.median((modeL - stdL)[valid]))
                one['median_observed_vs_standard_chroma_ratio'] = float(np.median((modeC / np.maximum(stdC, 1e-9))[valid]))
                dh = (modeH - stdH + 180) % 360 - 180
                one['median_observed_vs_standard_hue_shift_deg'] = float(np.median(dh[valid]))
                pc = np.hypot(d['pred200'][:, 1], d['pred200'][:, 2])
                tc = np.hypot(d['target'][:, 1], d['target'][:, 2])
                one['median_prediction_minus_target_chroma'] = float(np.median((pc - tc)[valid]))
            rec[name] = one
        out[f['id']] = rec
        ss = q['models']['200']['strata']
        lights = [x for x in ss if x['kind'] == 'lightness' and x['n']]
        print(json.dumps(dict(id=f['id'], residual=q['models']['200']['residual']['exact_squared_DE00_energy_fraction'],
            lightness=[dict(start=x['start'], n=x['n'], median=x['median'], p90=x['p90'],
                            squared_error_share=x['squared_error_share']) for x in lights],
            embedded={iso: dict(similarity=sc['similarity'], median=sc['median'], p90=sc['p90'])
                for iso, sc in (q.get('embedded_same_coordinates_sensitivity') or {}).items()}), ensure_ascii=False))
    dump(HERE / 'colour_diagnostics.json', out)


if __name__ == '__main__':
    main()
