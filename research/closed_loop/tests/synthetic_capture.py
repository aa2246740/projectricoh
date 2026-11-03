#!/usr/bin/env python3
"""Generate model-rendered DNG/JPEG files and drive the real measurement CLI path."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import struct
import numpy as np
from PIL import Image
from common import ROOT, LOCAL, helper, read, dump, sha, mount_guard, require, Provenance
from model import Engine
from refit import Problem, run as refit
from measure import run as measure, stats


def manual_metadata(data, ac):
    tiff = ac.Tiff(data)
    root = tiff.ifd(tiff.root)
    exif = tiff.ifd(root[34665]['value'][0])
    result = bytearray(data)
    for tag, value in ((0x8827, 200), (0xA403, 1), (0x8822, 1), (0xA402, 1)):
        e = exif[tag]
        require(e['type'] == 3 and e['count'] == 1, '合成元数据模板类型不符')
        struct.pack_into(tiff.endian+'H', result, e['offset'], value)
    record = ac.shot_info(tiff)['maker_shot_record_offset_in_tiff']
    result[record+0x26] = 5
    return bytes(result)


def main():
    mount_guard()
    E = Engine()
    p = Provenance()
    previous = read(LOCAL / 'dry_2e_measurement.json')
    base = next(f for f in previous['frames'] if f['id'] == 'R8051160')
    ac = helper('ar').s2d()
    dng_path = p.add(base['dng']); jpg_path = p.add(base['jpeg'])
    original = dng_path.read_bytes()
    crop, black, white, neutral, raw_info = ac.decode_raw(ac.Tiff(original))
    # Scene inputs are the old chart's effective inputs. Every output pixel is newly rendered.
    x = np.asarray(base['input_x'])
    deployed = E.predict('05', x)
    target = E.fs.lab_from_codes(deployed)
    P = Problem(E, '05', x, deployed, target)
    injected = P.initial.copy(); injected[:2] = [.035, -.025]
    h = np.arange(24)*2*np.pi/24
    injected[2:26] += .025*np.sin(h); injected[26:] += .02*np.cos(h)
    observed = P.corrected_rgb(injected)
    stock = E.predict('04', x)
    W, H = raw_info['crop_wh']
    ox, oy = raw_info['crop_origin_xy']
    raw_h, raw_w = raw_info['shape']
    signal = np.repeat(np.full((raw_h, raw_w, 1), .004, np.float32), 3, axis=2)
    frames_rgb = [np.full((H, W, 3), 15, np.uint8) for _ in range(2)]
    centers = np.array([[(q['roi'][0]+q['roi'][2])/2, (q['roi'][1]+q['roi'][3])/2] for q in base['patches']])
    half = int(.39*base['geometry']['pitch_px'])
    for i, (cx, cy) in enumerate(centers):
        x0, x1 = int(round(cx-half)), int(round(cx+half))
        y0, y1 = int(round(cy-half)), int(round(cy+half))
        require(0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H, '合成色块在画外')
        signal[oy+y0:oy+y1, ox+x0:ox+x1] = (x[i]/4095)*neutral
        for image, values in zip(frames_rgb, (stock, observed)):
            image[y0:y1, x0:x1] = np.rint(values[i]).astype(np.uint8)
    yy, xx = np.indices((raw_h, raw_w))
    cfa = np.where((yy % 2 == 0) & (xx % 2 == 0), 0,
                   np.where((yy % 2 == 1) & (xx % 2 == 1), 2, 1))
    cam = np.take_along_axis(signal, cfa[:, :, None], axis=2)[:, :, 0]
    raw = np.rint(black+cam*(white-black)).clip(0, 4095).astype(np.uint16)
    packed = helper('dng').pack12(raw)
    require(len(packed) == raw_info['raw_strip_bytes'], '合成 RAW 字节数错误')
    dng_bytes = bytearray(manual_metadata(original, ac))
    offset = raw_info['raw_strip_offset']
    dng_bytes[offset:offset+len(packed)] = packed
    exif_bytes = manual_metadata(ac.jpeg_tiff(jpg_path).data, ac)
    out = LOCAL / 'tests/synthetic_capture'
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for name, slot, image in zip(('synthetic04', 'synthetic05'), ('04', '05'), frames_rgb):
        (out/(name+'.DNG')).write_bytes(dng_bytes)
        Image.fromarray(image).save(out/(name+'.JPG'), quality=100, subsampling=0, exif=b'Exif\0\0'+exif_bytes)
        frames.append({'id': name, 'slot': slot, 'chart': 'physical', 'set': 'synthetic',
                       'jpeg': str(out/(name+'.JPG')), 'baseline': 'synthetic04'})
    manifest = out / 'frames.json'
    dump(manifest, {'schema': 'closedloop-frames/1', 'diagnostic_only': False, 'evidence_kind': 'synthetic', 'frames': frames})
    hook = out / 'targets.json'
    dump(hook, {'schema': 'closedloop-targets/1', 'frames': {
        name+':05': {'slot': '05', 'dng_sha256': sha(out/(name+'.DNG')),
                     'labels': [q['label'] for q in base['patches']], 'lab': target,
                     'source': 'synthetic known target rendered by v2 before injected error', 'reference_grade': 'synthetic'}
        for name in ('synthetic04', 'synthetic05')}})
    result = measure(manifest, out / 'measurement.json', hook)
    require(result['eligible_for_refit'], '合成文件未通过真实测量入口')
    f = next(f for f in result['frames'] if f['slot'] == '05')
    with Image.open(out / 'synthetic05.JPG') as im:
        raster = np.asarray(im.convert('RGB'))
    centers_int = np.rint(centers).astype(int)
    known_pixels = raster[centers_int[:, 1], centers_int[:, 0]]
    require(np.max(abs(known_pixels-np.asarray(f['rgb']))) < .01, '提色与 JPEG 内的已知平坦像素不一致')
    require(np.max(abs(np.rint(observed)-np.asarray(f['rgb']))) <= 1.01, 'JPEG 编码误差超出合成样本的预期')
    error = E.fs.delta_e00(E.fs.lab_from_codes(known_pixels), E.fs.lab_from_codes(f['rgb']))
    require(result['slots']['05']['model_vs_measured']['median'] > .1, '注入误差未被测到')
    refit(out / 'measurement.json', out / 'candidates', ['05'], max_nfev=50)
    candidate = read(out / 'candidates/slot05_candidate.json')
    require(not candidate['deployable'] and not candidate['firmware_ready'], '合成候选不应可部署')
    dump(out / 'verification.json', {'synthetic_only': True, 'metadata_pass': True,
         'frames': len(frames), 'patches_each': len(x), 'raster_extraction_de00': stats(error),
         'measured_model_error': result['slots']['05']['model_vs_measured'],
         'review_gate_passed': candidate['review_gate_passed'], 'inputs': p.finish()})
    print('合成 DNG/JPEG → 提色 → 模型残差 → 回拟 JSON 的完整路径通过。')


if __name__ == '__main__':
    main()
