#!/usr/bin/env python3
"""Fit every Fujifilm film simulation cube once (camera-table approximation, estimate only).

Adapted from research/lut_convert/batch_official.py. Inputs are the read-only copies
extracted into local/luts/fuji/; outputs stay in local/. No card files are produced.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import traceback
from guard import HERE, DOWNLOADS, mount_guard, install_write_fence, dump

GFX = 'fuji/gfx-eterna-55-3d-lut-v110/gfx-eterna-55-3d-lut-v110/33Grid/F-Log2'
XT5 = 'fuji/x-t5-3d-lut-v100/x-t5-3d-lut-v100'
JOBS = [(f'{GFX}/FLog2_to_{n}_33grid_V.1.00.cube', 'flog2') for n in (
    'PROVIA', 'Velvia', 'ASTIA', 'CLASSIC-CHROME', 'REALA-ACE', 'PRO-Neg.Std',
    'CLASSIC-Neg.', 'ETERNA', 'ETERNA-BB', 'ACROS')]
# The four body packs share byte-identical cubes; X-T5 stands for all four.
JOBS += [(f'{XT5}/F-Log2/XT5_FLog2_FGamut_to_{n}_BT.709_33grid_V.1.00.cube', 'flog2')
         for n in ('ETERNA', 'ETERNA-BB')]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='local/fuji-batch')
    p.add_argument('--max-nfev', type=int, default=100)
    p.add_argument('--variants', default='safe,t1')
    args = p.parse_args()
    mount_guard(); install_write_fence()
    from camera import Camera
    from convert import parser, run, prepare, DEFAULT_SCENES
    camera = Camera()
    scenes = prepare(camera, DEFAULT_SCENES, 280)
    results = []
    for i, (rel, space) in enumerate(JOBS, 1):
        cube = DOWNLOADS/rel
        if not cube.exists():
            raise ValueError('缺少 cube：' + str(cube))
        tag = 'xt5-' if rel.startswith(XT5) else 'gfx-'
        label = f'{i:02d}-{tag}' + cube.stem.split('_to_')[1].split('_')[0]
        out = HERE/args.out/label
        argv = [str(cube), '--input-space', space, '--output-space', 'srgb', '--out', str(out),
                '--variants', args.variants, '--max-nfev', str(args.max_nfev)]
        print('LUT', i, '/', len(JOBS), label, flush=True)
        try:
            r = run(parser().parse_args(argv), camera, scenes)
            results.append({'label': label, 'cube': rel, 'path': str(out.relative_to(HERE)),
                            'bw_native03': r['bw_native03'], 'scores': r['scores'],
                            'seconds': r['total_seconds'], 'success': True})
        except Exception as exc:
            row = {'label': label, 'cube': rel, 'success': False, 'error': str(exc),
                   'traceback': traceback.format_exc()}
            results.append(row); dump(out/'FAILED.json', row)
            print('FAILED', exc, flush=True)
        dump(HERE/args.out/'batch.json', results)
    return 0 if all(r['success'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
