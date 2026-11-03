"""Run the studio's route-1 knob fit on real cubes (huzi Panasonic-Standard LUTs, Leica official LUTs) and write
research/studio_lut_s8a/results/real_luts.json + real_luts.md. Every number is a computer prediction (电脑预测).

    studio/.venv/bin/python research/studio_lut_s8a/tools/measure_real_luts.py [--profile normal] [--only name,...]

Ricoh bytes: the camera data (DAT) is copied from the local firmware package into a temp dir for the run and the
temp dir is deleted at the end; nothing Ricoh-derived is written to results/. One process, no network, no card access.
"""
import argparse
import json
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'studio/src'))
sys.path.insert(0, str(ROOT / 'studio/tests'))
OUT = ROOT / 'research/studio_lut_s8a/results'

SCENES = ['captures/a12-50/2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051131.DNG',
          'captures/a12-50/2026-10-19/stage2c-first-run/R8051144.DNG',
          'captures/a12-50/2026-10-19/stage2c-first-run/R8051145.DNG',
          'captures/a12-50/2026-10-19/stage2c-first-run/R8051147.DNG']          # the last one is holdout-only
HUZI = ROOT / 'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'
LEICA = ROOT / 'artifacts/downloads/leica-luts/20261023-official'


def jobs():
    out = []
    for p in sorted(HUZI.glob('*.cube')):
        out.append({'group': 'huzi (Panasonic Standard in, sRGB out)', 'path': p, 'space': 'srgb', 'output': 'srgb', 'output_gamut': None})
    for p in sorted(LEICA.rglob('*.cube')):
        out.append({'group': 'Leica official (L-Log in)', 'path': p, 'space': 'llog', 'output': 'gamma24',
                    'output_gamut': 'rec2020' if 'Rec2020' in p.stem and 'to_Rec709' not in p.stem else None})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', default='normal')
    ap.add_argument('--only', default='')
    args = ap.parse_args()
    import numpy as np
    import e0_support as t
    from gxr_studio.camdata import calib, store
    from gxr_studio.lut import scene, spaces
    from gxr_studio.lut.cube import Cube
    from gxr_studio.lut.fit import Fitter
    from gxr_studio.lut.worker import load_photos
    from gxr_studio.render.recipes import CameraData

    home = Path(tempfile.mkdtemp(prefix='s8a-measure-'))
    try:
        store.import_from_dat(t.fixture_dat(127), home)
        calib.import_calibration(home, calib.dev_sources(t.REPO))
        cam = CameraData(home)
        model = calib.model_for(home, 200)[0]
        photos, skipped = load_photos([{'dng': str(ROOT / s), 'label': Path(s).stem} for s in SCENES], 4)
        assert not skipped and len(photos) == 4, skipped
        rows = []
        only = [x for x in args.only.split(',') if x]
        for job in jobs():
            if only and job['path'].stem not in only:
                continue
            cube = Cube.read(job['path'])
            t0 = time.perf_counter()
            samples = scene.build_samples(model, cam.stock[0], job['space'], photos)
            target = spaces.Target(cube, job['space'], job['output'], None, job['output_gamut'])
            stock, ideal = scene.target_rgb(model, cam.stock[0], samples, target)
            fit = Fitter(cam, model, samples, stock, ideal, profile=args.profile)
            res = fit.run()
            row = {'file': job['path'].name, 'group': job['group'], 'input_space': job['space'], 'output_space': job['output'],
                   'output_gamut': job['output_gamut'], 'cube_sha256': cube.source_sha256, 'cube_kind': cube.description()['size_3d'],
                   'seconds': res['seconds'], 'evaluations': res['evaluations'], 'samples': res['samples']['groups'],
                   'candidates': [{k: c[k] for k in ('slot', 'number', 'short', 'levels', 'similarity', 'label', 'holdout', 'train',
                                                      'baseline04_holdout', 'per_group', 'differences')} for c in res['candidates']]}
            rows.append(row)
            b = res['candidates'][0]
            print(f"{job['path'].name:60s} best {b['number']} {b['similarity'] if b['similarity'] is None else round(b['similarity'], 1)}% "
                  f"{b['label']} {res['seconds']:.0f}s", flush=True)
            OUT.mkdir(parents=True, exist_ok=True)
            doc = {'schema': 'gxr-studio/lut-real-measure/1', 'profile': args.profile, 'prediction': True,
                   'scenes': SCENES, 'machine': platform.platform(), 'python': platform.python_version(),
                   'numpy': np.__version__, 'rows': rows}
            (OUT / 'real_luts.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=float) + '\n')
    finally:
        shutil.rmtree(home, ignore_errors=True)
    write_md(rows, args.profile)


def write_md(rows, profile):
    lines = [f'# 真实 LUT 的路线 1 拟合结果（电脑预测，profile={profile}）', '',
             '相似度 = 1 − median(候选→目标 ΔE00) / median(04→目标 ΔE00)，留出样本；全部是电脑预测，没有相机实测。', '',
             '| 文件 | 最近的底子 | 相似度 | 标签 | 留出 ΔE00 中位 / p90 | 04→目标 中位 | 前 3 名（底子 相似度） | 秒 |', '|---|---|---:|---|---|---:|---|---:|']
    for r in rows:
        b = r['candidates'][0]
        sim = 'N/A' if b['similarity'] is None else f"{b['similarity']:.1f}%"
        top = '；'.join(f"{c['number']} {'N/A' if c['similarity'] is None else format(c['similarity'], '.1f') + '%'}" for c in r['candidates'])
        lines.append(f"| {r['file']} | {b['number']} {b['short']} | {sim} | {b['label']} | {b['holdout']['median']:.2f} / {b['holdout']['p90']:.2f} "
                     f"| {b['baseline04_holdout']['median']:.2f} | {top} | {r['seconds']:.0f} |")
    (OUT / 'real_luts.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
