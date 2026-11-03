#!/usr/bin/env python3
"""Frozen GR III forward predictions. These JPEGs are simulations, not camera evidence."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import subprocess
import numpy as np
from PIL import Image
from common import LOCAL, TMP, MODEL, ROOT, pin, read, dump, output, require, sha, binaries
from tiff_io import Tiff
from chart import camera_half, radial, gain_ev


def decode_card(card):
    p = Path(card['dng_path'])
    require(sha(p) == card['dng_sha256'], 'DNG 与布局清单哈希不符')
    t = Tiff(p.read_bytes())
    g = card['geometry']
    raw = np.zeros((g['height'], g['width']), np.uint16)
    work = output(TMP / ('final-artifact-decode-' + card['dng_sha256'][:16]))
    work.mkdir(parents=True, exist_ok=True)
    _, dec = binaries()
    for seg in t.segments(t.raw):
        src, dst = work / 'packed.ljpg', work / 'unpacked.u16'
        src.write_bytes(t.data[seg['offset']:seg['offset'] + seg['capacity']])
        subprocess.run([str(dec), str(src), str(dst)], check=True, capture_output=True)
        x, y, w, h = seg['box']
        arr = np.fromfile(dst, '<u2').reshape(h, w)
        th, tw = min(h, g['height'] - y), min(w, g['width'] - x)
        raw[y:y + th, x:x + tw] = arr[:th, :tw]
    require(__import__('hashlib').sha256(raw.astype('<u2').tobytes()).hexdigest() == card['raw_u16_sha256'],
            '成品 DNG 解码结果与设计 RAW 不一致')
    return raw


class Renderer:
    def __init__(self):
        self.record = read(pin(MODEL))['shared_neutral_calibration']
        # The round5 target generator and gr_evalsets use the same frozen states.
        r5 = read(pin(ROOT / 'research/color_fit_v2/gr_round5/local/inputs/gr_parameters.json'))['shared_neutral_calibration']
        for mode in ('standard', 'positive', 'negative'):
            for key in ('ColorMatrix_Calc_front_signed12_Q8_hypothesis', 'effective_curve256_u16LE'):
                require(self.record['results'][mode][key] == r5['results'][mode][key], '两个现有 GR III 模型状态不一致')

    def render(self, raw, neutral, mode, exposure_ev=0.):
        saved = self.record['results'][mode]
        matrix = np.asarray(saved['ColorMatrix_Calc_front_signed12_Q8_hypothesis'], float) / 256
        curve = np.asarray(saved['effective_curve256_u16LE']['values'], float)
        value = (np.asarray(raw, float) / np.asarray(neutral)) @ matrix.T
        value = np.clip(value * self.record['parameters']['exposure_scale'] * 2. ** exposure_ev, 0, 1)
        return np.clip(np.interp(value * 4095, np.arange(256) * 16, curve) / 16384, 0, 1)


def predict(manifest, destination, radial_scale=1., exposure_ev=0., toy_bw=False):
    card = read(manifest)
    require('GR III' in card['geometry']['model'], '此预测器只用于 GR III，不能冒充 GR IV 模型')
    folder = output(destination)
    folder.mkdir(parents=True, exist_ok=True)
    raw = camera_half(decode_card(card), card)
    w, h = card['geometry']['crop_wh']
    yy, xx = np.mgrid[0:h:2, 0:w:2]
    raw *= (2. ** (radial_scale * gain_ev(radial(xx + 1, yy + 1, (w, h)))))[..., None]
    model = Renderer()
    files, samples = {}, {}
    modes = ['standard', 'positive', 'negative'] + (['hc_bw'] if toy_bw else [])
    for mode in modes:
        if mode == 'hc_bw':
            rgb = model.render(raw, card['geometry']['neutral'], 'standard', exposure_ev)
            y = np.clip((rgb @ np.array([.2126, .7152, .0722]) - .2) / .6, 0, 1)
            rendered = np.repeat(y[..., None], 3, axis=-1)
        else:
            rendered = model.render(raw, card['geometry']['neutral'], mode, exposure_ev)
        patch_samples = []
        for p in card['patches']:
            x1, y1, x2, y2 = np.asarray(p['roi']) // 2
            patch_samples.append(rendered[y1:y2, x1:x2].mean(axis=(0, 1)))
        samples[mode] = np.asarray(patch_samples)
        image = Image.fromarray(np.rint(rendered * 255).astype(np.uint8)).resize((w, h), Image.Resampling.NEAREST)
        path = folder / f'{mode}.JPG'
        image.save(path, format='JPEG', quality=98, subsampling=0)
        files[mode] = dict(path=str(path), sha256=sha(path))
    np.savez_compressed(folder / 'patch_predictions.npz', labels=np.array([p['id'] for p in card['patches']]), **samples)
    record = dict(schema='gr-incamera-predictions/1', source='GR III frozen partial model + explicit radial hypothesis',
                  card_manifest=str(Path(manifest).resolve()), card_dng_sha256=card['dng_sha256'],
                  model_path=str(MODEL), model_sha256=sha(MODEL),
                  same_states_as_round5=True, exposure_ev=exposure_ev, radial_scale=radial_scale,
                  original_model_has_spatial_correction=False,
                  hc_bw_is_toy=toy_bw, files=files,
                  factory_preset_sliders={mode: model.record['results'][mode]['sliders_inferred_from_original_MakerNote_0247']
                                          for mode in ('standard', 'positive', 'negative')},
                  missing=['MultiAxial', 'local tone', 'real demosaic/sharpen/NR', 'camera acceptance'],
                  camera_acceptance=False, reference_grade='model_prediction')
    dump(folder / 'prediction.json', record)
    return folder / 'prediction.json'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--radial-scale', type=float, default=1.)
    p.add_argument('--exposure-ev', type=float, default=0.)
    p.add_argument('--toy-bw', action='store_true')
    a = p.parse_args()
    print(predict(a.manifest, a.out, a.radial_scale, a.exposure_ev, a.toy_bw))
