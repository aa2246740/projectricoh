#!/usr/bin/env python3
"""Convert a declared .cube target to local GXR recipe candidates."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import csv
import hashlib
import json
import time
from guard import HERE, ROOT, LOCAL, input_path, output_path, mount_guard, install_write_fence, dump, sha

DEFAULT_SCENES = ['captures/a12-50/2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051131.DNG',
                  *[f'captures/a12-50/2026-10-19/stage2c-first-run/R80511{n}.DNG' for n in ('44','45','47')]]


def samples(camera, n, seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    pre = rng.uniform(8, 247, (n*2, 3))
    x = camera.curve.inverse(pre)
    base = camera.stock(x)
    ok = np.all((base > 3) & (base < 252), axis=1)
    x = x[ok][:n]
    gray = np.repeat(camera.curve.inverse(np.linspace(4, 251, 77))[:, None], 3, axis=1)
    return np.vstack([x, gray]), np.r_[np.ones(len(x)), np.full(77, 4.)]


def prepare(camera, paths, width, stock04_json=None):
    import numpy as np
    from PIL import Image, ImageOps
    declared = {}
    if stock04_json:
        manifest = input_path(stock04_json)
        camera.E.provenance.add(manifest)
        doc = json.loads(manifest.read_text())
        if doc.get('schema') != 'gxr-confirmed-stock04/1':
            raise ValueError('stock04-json schema 应为 gxr-confirmed-stock04/1')
        declared = doc['pairs']
    scenes = []
    for path in paths:
        p = Path(path)
        if not p.is_absolute():
            p = ROOT/p
        scene = camera.scene(p, width)
        if declared:
            key = str(p.relative_to(ROOT))
            if key not in declared:
                raise ValueError('stock04-json 缺少场景：' + key)
            jp = input_path(ROOT/declared[key])
            camera.E.provenance.add(jp)
            im = ImageOps.exif_transpose(Image.open(jp)).convert('RGB')
            im = im.resize((scene['x'].shape[1], scene['x'].shape[0]), Image.Resampling.BOX)
            rgb = np.asarray(im, float)
            x, valid, err = camera.inverse(rgb)
            scene['x'] = x.reshape(scene['x'].shape)
            scene['clipped'] = scene['clipped'] | ~valid.reshape(scene['clipped'].shape)
            scene['meta'] = {**scene['meta'], 'baseline': 'user-declared observed stock04 JPEG, inverse checked',
                             'stock04_jpeg': str(jp.relative_to(ROOT)), 'stock04_sha256': sha(jp),
                             'stock04_inverse_valid_share': float(valid.mean()),
                             'stock04_inverse_max_code_residual': float(err.max())}
        scene['stock'] = camera.stock(scene['x']).reshape(scene['x'].shape)
        scenes.append(scene)
    return scenes


def sector_rows(camera, x, base, pred, target):
    import numpy as np
    from fit import score, stats
    hue = camera.mm.hue_deg(camera.row.apply(camera.curve(x))[1])
    nodes = camera.E.table.nodes
    dist = abs((hue[:, None]-nodes[None, :]+180)%360-180)
    labels = np.argmin(dist, axis=1)
    plab, tlab = camera.fs.lab_from_codes(pred), camera.fs.lab_from_codes(target)
    rows = []
    for i in range(24):
        take = labels == i
        s, _ = score(camera, base[take], pred[take], target[take])
        delta = np.median(plab[take]-tlab[take], axis=0) if take.any() else [None]*3
        rows.append({'sector': i, 'node_angle_deg': float(nodes[i]), 'n': int(take.sum()),
                     'de00_median': s['de00']['median'], 'de00_p90': s['de00']['p90'],
                     'similarity': s['similarity'], 'signed_dL': delta[0], 'signed_da': delta[1], 'signed_db': delta[2]})
    return rows


def limitations(camera, target, reference, bw, scores):
    import numpy as np
    gray = np.repeat(np.linspace(8, 247, 80)[:, None], 3, axis=1)
    gx, valid, _ = camera.inverse(gray)
    xyz = camera.xyz(gx, reference['neutral'], reference['matrix'])
    out = target.render(gray, xyz)
    lab = camera.fs.lab_from_codes(out)
    axis_spread = float(np.max(np.linalg.norm(lab[:, 1:]-np.median(lab[:, 1:], axis=0), axis=1)))
    notes = ['这是 50mm、ISO 200 前向模型的局部近似；不能据此承诺其他单元、ISO 或相机实拍的还原率。',
             '有限的固定色相扇区和共同曲线不能表达完整三维 LUT；同一颜色在不同明暗、饱和度下的变化会留下误差。',
             'LUT 无法补回 GXR 传感器已经裁掉的高光，也不包含颗粒、锐化、光晕、局部蒙版等空间效果。']
    if axis_spread > 1.2:
        notes.append('LUT 把灰色的暗部和亮部染成不同颜色；日常共同曲线与中性矩阵不能分别保留这些偏色。T1 可能改善。')
    if target.input_space not in ('srgb', 'rec709', 'gamma24'):
        notes.append('Log 目标依赖 GXR 的 DNG 矩阵、中灰锚与白平衡；这是把色彩处理迁移到 GXR，不能复制徕卡传感器的光谱响应。')
    if bw:
        notes.append('黑白使用原生 03 路径、共同曲线与通道混合；任意“先混色再套非线性曲线”的 LUT 仍不能保证精确重现。')
        notes.append('03 不保留棕调、蓝调等彩色黑白；带色黑白需走彩色路径。03 与 T1 组合仍须单独验证生命周期。')
    if 't2-hypothesis' in scores:
        notes.append('T2 对比仅假设按亮度调节饱和度；它不能分别给暗部和亮部转色相，且硬件语义尚未标定。')
    safe = scores['safe']['synthetic_holdout']
    if safe['similarity'] is not None and safe['similarity'] < 0:
        notes.append('这个 LUT 在本次留出样本上的候选甚至比 04 更远；不得把它当作已接受的配方。')
    return {'neutral_axis_tint_spread_lab': axis_spread, 'neutral_inverse_valid_share': float(valid.mean()),
            'split_toning_limited': axis_spread > 1.2, 'plain_language': notes}


def preview(camera, target, scenes, solutions, path, title):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 15)
    variants = ['safe']+(['t1'] if 't1' in solutions else [])
    columns = ['04 HOST MODEL', 'LUT IDEAL sRGB']+[v.upper()+' MODEL' for v in variants]
    tilew = scenes[0]['stock'].shape[1]
    heights = [s['stock'].shape[0]+49 for s in scenes]
    image = Image.new('RGB', (tilew*len(columns), sum(heights)+55), '#181a1b')
    draw = ImageDraw.Draw(image)
    draw.text((10, 7), title[:110], font=font, fill='white')
    draw.text((10, 28), 'SIMULATION ONLY | 04 / LUT / recipe | last row held out | no camera acceptance', font=font, fill='#c4c8cb')
    y = 55
    for no, scene in enumerate(scenes):
        flatx = scene['x'].reshape(-1, 3)
        outputs = [scene['stock'], target.render(scene['stock'], scene['xyz'])]
        for v in variants:
            p, q = solutions[v]
            outputs.append(p.predict(q['theta'], flatx).reshape(scene['x'].shape))
        for col, arr in enumerate(outputs):
            im = Image.fromarray(np.uint8(np.clip(np.rint(arr), 0, 255)))
            image.paste(im, (col*tilew, y+45))
            draw.text((col*tilew+6, y+2), columns[col], font=font, fill='white')
            label = Path(scene['meta']['path']).stem+f' ISO{scene["meta"]["iso"]}'
            draw.text((col*tilew+6, y+23), label+(' HOLDOUT' if no == len(scenes)-1 else ''), font=font, fill='#b6bec4')
        y += heights[no]
    image.save(output_path(path))


def run(args, camera=None, prepared=None):
    import numpy as np
    from camera import Camera
    from cube import Cube
    from spaces import Target
    from fit import Problem, score
    start = time.perf_counter()
    cube = Cube.read(args.cube)
    out = output_path(HERE/args.out if not Path(args.out).is_absolute() else args.out)
    if out.exists() and any(out.iterdir()) and not args.overwrite:
        raise ValueError('输出目录已有文件；换一个 --out 或显式 --overwrite')
    out.mkdir(parents=True, exist_ok=True)
    camera = camera or Camera(args.module, args.iso)
    camera.E.provenance.add(args.cube)
    for name in ('guard.py','cube.py','spaces.py','camera.py','fit.py','convert.py'):
        camera.E.provenance.add(HERE/name)
    target = Target(cube, args.input_space, args.output_space, args.input_gamut, args.output_gamut,
                    args.input_range, args.output_range)
    scenes = prepared or prepare(camera, args.scene or DEFAULT_SCENES, args.width, args.stock04_json)
    if len(scenes) < 3 or len(scenes) > 4:
        raise ValueError('需要 3–4 张 DNG；最后一整张留出，不参与拟合')
    ref = scenes[0]
    x, sw = samples(camera, args.samples, 151)
    stock = camera.stock(x)
    desired = target.render(stock, camera.xyz(x, ref['neutral'], ref['matrix']))
    for scene in scenes[:-1]:
        xx = scene['x'].reshape(-1, 3)
        valid = np.flatnonzero(~scene['clipped'].ravel())
        if not len(valid):
            raise ValueError('场景没有未裁切样本')
        take = valid[np.linspace(0, len(valid)-1, 140).astype(int)]
        yy = target.render(scene['stock'], scene['xyz']).reshape(-1, 3)[take]
        x = np.vstack([x, xx[take]])
        desired = np.vstack([desired, yy])
        sw = np.r_[sw, np.ones(len(take))]
    probe = target.render(camera.stock(x), camera.xyz(x, ref['neutral'], ref['matrix']))
    monochrome = bool(np.max(np.ptp(probe, axis=1)) < .5)
    bw = monochrome if args.bw == 'auto' else args.bw == 'on'
    if bw and not monochrome:
        raise ValueError('此 LUT 输出带色；原生 03 会丢掉偏色，不能强制黑白')
    testx, _ = samples(camera, args.samples*2, 20261023)
    testbase = camera.stock(testx)
    testtarget, lut_stats = target.render(testbase, camera.xyz(testx, ref['neutral'], ref['matrix']), info=True)
    last = scenes[-1]
    valid = np.flatnonzero(~last['clipped'].ravel())
    if not len(valid):
        raise ValueError('留出场景没有未裁切样本')
    take = valid[np.linspace(0, len(valid)-1, min(2500, len(valid))).astype(int)]
    hx, hb = last['x'].reshape(-1, 3)[take], last['stock'].reshape(-1, 3)[take]
    ht = target.render(last['stock'], last['xyz']).reshape(-1, 3)[take]
    scores, solutions, exports = {}, {}, {}
    for variant in args.variants.split(','):
        if variant not in ('safe', 't1', 't2-hypothesis'):
            raise ValueError('未知 variant：' + variant)
        if bw and variant == 't2-hypothesis':
            continue
        P = Problem(camera, x, desired, variant=variant, bw=bw, sample_weights=sw)
        initial = P.theta0.copy()
        rampx = np.repeat(camera.curve.xs[:, None], 3, axis=1)
        ramp = target.render(camera.stock(rampx), camera.xyz(rampx, ref['neutral'], ref['matrix']))
        # A declared LUT's neutral ramp is a deterministic initial curve, not
        # a fitted exposure or a target-dependent change to the DNG anchor.
        ramp_y = np.maximum.accumulate(ramp@np.array([.299,.587,.114]))
        initial[P.qstart:P.t2start] = np.tile(ramp_y-camera.curve.ys, 3 if P.t1 else 1)
        if variant != 'safe' and 'safe' in solutions:
            previous, q0 = solutions['safe']
            initial = P.promote(q0['theta'], previous)
        fit, solver = P.solve(initial, args.max_nfev)
        q = P.quantize(fit.x)
        solutions[variant] = (P,q)
        train, _ = score(camera, camera.stock(x), P.predict(q['theta'], x), desired)
        testpred = P.predict(q['theta'], testx)
        test, _ = score(camera, testbase, testpred, testtarget)
        heldout, _ = score(camera, hb, P.predict(q['theta'], hx), ht)
        scores[variant] = {'training': train, 'synthetic_holdout': test, 'scene_holdout': heldout,
                           'solver': solver, 'sector_safety': q['safety'],
                           'evidence_kind': 'host_forward_model',
                           'hardware_semantics': 'hypothesis' if variant == 't2-hypothesis' else 'existing 50mm model',
                           'quantized_before_scoring': True}
        rows = sector_rows(camera, testx, testbase, testpred, testtarget)
        dest = out/variant
        exports[variant] = P.export(q, dest)
        with (dest/'sector_residuals.csv').open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
        dump(dest/'metrics.json', scores[variant])
        print(variant, 'holdout DE00', round(test['de00']['median'], 4), round(test['de00']['p90'], 4),
              'similarity', None if test['similarity'] is None else round(100*test['similarity'], 2), flush=True)
    if 'safe' not in solutions:
        raise ValueError('variants 必须包含 safe，并将 safe 放在第一项')
    limits = limitations(camera, target, ref, bw, scores)
    if not args.skip_previews:
        preview(camera, target, scenes, solutions, out/'preview.png', Path(args.cube).name)
    for variant in scores:
        notes = list(limits['plain_language'])
        if not scores[variant]['solver']['success']:
            notes.append('本轮达到优化求值上限，候选只是预算内的近似，未确认收敛。')
        if any(not s['meta']['model_calibrated_for_scene_iso'] for s in scenes):
            notes.append('部分实景 ISO 没有对应标定，只能用当前 ISO 模型作代理诊断。')
        (out/variant/'LIMITATIONS.txt').write_text('\n'.join('- '+s for s in notes)+'\n')
    results = {'schema': 'gxr-lut-conversion/1', 'lut': cube.description(), 'pipeline': target.description(),
               'module': camera.description(), 'bw_native03': bw, 'scores': scores, 'exports': exports,
               'limitations': limits, 'lut_application': lut_stats, 'scenes': [s['meta'] for s in scenes],
               'configuration': {'samples_requested': args.samples, 'training_n': len(x),
                                 'synthetic_holdout_n': len(testx), 'max_nfev': args.max_nfev,
                                 'width': args.width, 'variants': args.variants,
                                 'scene_holdout_model_calibrated': last['meta']['model_calibrated_for_scene_iso']},
               'split': {'training_scenes': [s['meta']['path'] for s in scenes[:-1]],
                         'scene_holdout': scenes[-1]['meta']['path'],
                         'synthetic_train_seed': 151, 'synthetic_holdout_seed': 20261023,
                         'scene_holdout_is_new_camera_capture': False},
               'total_seconds': time.perf_counter()-start, 'camera_acceptance': False,
               'inputs': camera.E.provenance.finish()}
    dump(out/'results.json', results)
    sums = []
    for f in sorted(out.rglob('*')):
        if f.is_file() and f.name != 'SHA256SUMS':
            sums.append(sha(f)+'  '+str(f.relative_to(out)))
    (out/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    return results


def parser():
    from spaces import SPACES, PRIMARIES
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cube')
    p.add_argument('--input-space', required=True, choices=SPACES)
    p.add_argument('--output-space', default='srgb', choices=('srgb','rec709','gamma24','linear'))
    p.add_argument('--input-gamut', choices=PRIMARIES)
    p.add_argument('--output-gamut', choices=PRIMARIES)
    p.add_argument('--input-range', choices=('full','legal'), default='full')
    p.add_argument('--output-range', choices=('full','legal'), default='full')
    p.add_argument('--module', choices=('a12-50','a12-28','mount-a12'), default='a12-50')
    p.add_argument('--iso', type=int, choices=(200,1600), default=200)
    p.add_argument('--out', required=True, help='路径必须位于本任务 local/')
    p.add_argument('--scene', action='append', help='3–4 张 DNG，最后一张整图留出')
    p.add_argument('--stock04-json', help='明确确认原厂04的 JPEG/DNG 配对清单；否则 04 是模型模拟')
    p.add_argument('--bw', choices=('auto','on','off'), default='auto')
    p.add_argument('--variants', default='safe', help='safe,t1,t2-hypothesis；后两项受限')
    p.add_argument('--samples', type=int, default=700)
    p.add_argument('--width', type=int, default=280)
    p.add_argument('--max-nfev', type=int, default=60)
    p.add_argument('--skip-previews', action='store_true')
    p.add_argument('--overwrite', action='store_true')
    return p


def main():
    mount_guard(); install_write_fence()
    args = parser().parse_args()
    if not 100 <= args.samples <= 20000 or not 100 <= args.width <= 1000 or not 1 <= args.max_nfev <= 200:
        raise ValueError('samples/width/max-nfev 超出边界')
    r = run(args)
    print('saved', args.out, 'seconds', round(r['total_seconds'], 2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        print(type(exc).__name__+': '+str(exc), file=sys.stderr)
        raise SystemExit(2)
