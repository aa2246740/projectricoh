#!/usr/bin/env python3
"""Repeat the two real-capture diagnostics without touching their sources."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
from common import LOCAL, dump, mount_guard, require
from measure import run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('set', choices=['ring', '2e'])
    args = ap.parse_args()
    mount_guard()
    if args.set == 'ring':
        folder = 'captures/a12-50/2026-10-20/stage2j-v1-calibration/'
        pairs = zip(range(1179, 1183), ('04', '07', '08', '04'))
        baseline, chart, set_id = 'R8051179', 'hue-ring', 'screen-cal'
    else:
        folder = 'captures/a12-50/2026-10-19/stage2e-colorchecker/'
        # Actual image identities from stage2e_verification, including the reversed 01/02 picks.
        pairs = zip(range(1152, 1161), ('04', '03', '02', '01', '05', '06', '07', '08', '04'))
        baseline, chart, set_id = 'R8051160', 'physical', 'stage2e'
    frames = [{'id': f'R805{n}', 'set': set_id, 'slot': slot, 'chart': chart,
               'jpeg': folder+f'R805{n}.JPG', 'baseline': baseline} for n, slot in pairs]
    name = 'dry_ring' if args.set == 'ring' else 'dry_2e'
    manifest = LOCAL / (name+'_frames.json')
    dump(manifest, {'schema': 'closedloop-frames/1', 'diagnostic_only': True, 'frames': frames})
    result = run(manifest, LOCAL / (name+'_measurement.json'))
    require(not result['eligible_for_refit'], '历史诊断不得变成可接受实拍')
    expected_count = 155 if args.set == 'ring' else 24
    require(all(len(f['patches']) == expected_count for f in result['frames']), '提色色块数量不符')
    require(all(v['unchanged'] for v in result['provenance'].values()), '历史输入发生变化')
    require(result['metadata_checks'][set_id]['pass'] == (args.set == 'ring'), '拍摄条件检查结果不符')
    print('历史 dry run 通过；它不构成 v4r2 六槽相机验收。')


if __name__ == '__main__':
    main()
