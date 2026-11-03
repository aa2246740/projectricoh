#!/usr/bin/env python3
"""Bind the frozen round-five GR renderer to measured DNGs and observed 04s."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import numpy as np
from common import ROOT, LOCAL, Provenance, dump, read, load, sha, require, mount_guard, output_path
from model import Engine
from targets import Targets


class FirmwareTargets:
    def __init__(self, provenance):
        self.p = provenance
        folder = ROOT / 'research/color_fit_v2/gr_round5'
        sources = read(self.p.add(folder / 'local/inputs.json'))
        require(all(sha(self.p.add(ROOT / rel)) == digest for rel, digest in sources.items()),
                'GR round-five 的冻结源发生变化')
        for path in folder.rglob('*.py'):
            if '__pycache__' not in path.parts:
                self.p.add(path)
        gr = load('gr5_targets_r1', self.p.add(folder / 'gr_targets.py'))
        inputs = folder / 'local/inputs'
        reference = read(self.p.add(inputs / 'reference.json'))
        raw_path = ROOT / 'artifacts/downloads/bastibe-gr3/downloads/bastibe_gr3_dng/Target.DNG'
        require(sha(self.p.add(raw_path)) == reference['source_dng']['sha256'], 'GR 参考 DNG 哈希不符')
        params = read(self.p.add(inputs / 'gr_parameters.json'))['shared_neutral_calibration']
        tables = {q['id']: q for q in read(self.p.add(inputs / 'gr_tables.json'))['tables']}
        metadata = {q['mode']: q for q in read(self.p.add(inputs / 'gr_metadata.json'))['records']}
        validation = read(self.p.add(folder / 'local/generator.json'))
        # Reuse the original numerical methods without constructing Nominal04 or Data.
        self.g = gr.GRGenerator.__new__(gr.GRGenerator)
        self.g.e = params['parameters']['exposure_scale']
        self.g.matrix = np.array(reference['dng_matrices']['camera_to_xyz_d50'])
        self.g.scene_scale = validation['scene_exposure_scale']
        self.g.states = {}
        for mode, name in [('standard', 'Standard'), ('positive', 'Positive_Film'), ('negative', 'Negative_Film')]:
            saved = params['results'][mode]
            md = metadata[mode]
            sat = md['first_seven_fields_inferred']['saturation']
            saturation = np.array(tables[name+f'-saturation-{sat:+d}']['values']).reshape(3, 3)
            look = np.array(tables[name+'-look-matrix']['values']).reshape(3, 3)
            sensor = np.array(tables[name+'-sensor-ccm']['values']).reshape(3, 3)
            front = gr.pm.front_q8(gr.pm.compose_q13_i32(gr.pm.compose_q13(saturation, look), sensor))
            require(np.array_equal(front, saved['ColorMatrix_Calc_front_signed12_Q8_hypothesis']),
                    'GR 矩阵组合与冻结模型不符')
            curve_record = saved['effective_curve256_u16LE']
            curve = np.array(curve_record['values'])
            import hashlib
            require(hashlib.sha256(curve.astype('<u2').tobytes()).hexdigest() == curve_record['sha256'],
                    'GR 曲线哈希不符')
            self.g.states[mode] = {'front': front, 'curve': curve,
                                   'wb': np.array(md['wb_rggb_u16'])[[0, 1, 3]]/8192}
        self.validation = {slot: q['validation'] for slot, q in validation['modes'].items()}

    def render(self, engine, frame, baseline, slot):
        bx, _ = engine.invert04(np.asarray(baseline['rgb']), np.asarray(baseline['raw_wb']))
        x = bx*np.asarray(frame['raw_wb'])/np.maximum(np.asarray(baseline['raw_wb']), 1e-9)
        # This is a declared GXR scene anchor, not a measured GR exposure match.
        scale, anchor = Targets(engine, self.p).scene_scale(baseline, '05')
        scene_xyz = np.asarray(frame['xyz_camera'])*scale
        scene_rgb = scene_xyz @ np.linalg.inv(engine.fs.M709).T
        raw = self.g.camera_rgb(scene_rgb)
        mode = 'positive' if slot == '01' else 'negative'
        grey = np.array([q['gray'] for q in frame['patches']])
        rows, invalid = {}, np.zeros(len(raw), bool)
        for ev in (-.3, 0., .3):
            factor = 2**ev
            gr_raw = raw*factor
            invalid |= np.any((gr_raw < 0) | (gr_raw > 1), axis=1)
            rows[f'{ev:+.1f}'] = self.g.relative_target(engine.predict('04', x*factor),
                                                       gr_raw, mode, grey)
        return rows, invalid, {'gxr_scene_anchor': anchor,
            'gr_reference_scene_scale': self.g.scene_scale, 'nominal04_used': False,
            'metering_anchor_determined': False,
            'zero_EV_definition': 'frozen GXR u_m scene scale and bastibe GR reference scale; GR exposure match unknown',
            'calibration_model_iso': engine.description()['calibration_model_iso']}


def generate(request_path, measurement_path, output, physical_model_iso=None):
    mount_guard()
    output = output_path(output)
    p = Provenance()
    requests = read(p.add(request_path))
    measurement = read(p.add(measurement_path))
    require(requests.get('schema') == 'closedloop-target-requests/1', '请求 schema 不符')
    frames = {f['id']: f for f in measurement['frames']}
    generator, engines, out = FirmwareTargets(p), {}, {}
    for q in requests['frames']:
        slot = q['slot']
        if slot not in ('01', '02'):
            continue
        frame, baseline = frames[q['id']], frames[q['baseline_id']]
        require(q['dng_sha256'] == frame['hashes']['DNG'] and
                q['labels'] == [v['label'] for v in frame['patches']], '请求没有绑定实际 DNG 色块')
        require(np.array_equal(q['raw_wb'], frame['raw_wb']) and
                np.array_equal(q['xyz_camera'], frame['xyz_camera']) and
                np.array_equal(q['input_x'], frame['input_x']), '请求 DNG 输入与测量不一致')
        iso = physical_model_iso if frame['meta']['iso'] == 800 and physical_model_iso else frame['meta']['iso']
        key = frame['model']['table'], iso
        if key not in engines:
            engines[key] = Engine(*key, provenance=p)
        rows, invalid, info = generator.render(engines[key], frame, baseline, slot)
        out[q['key']] = {'slot': slot, 'dng_sha256': q['dng_sha256'], 'labels': q['labels'],
            'lab': rows['+0.0'], 'anchor_lab': {ev: rows[ev] for ev in ('-0.3', '+0.3')},
            'source': 'GR III frozen firmware forward renderer, round5; own DNG scene XYZ and measured 04 bridge',
            'reference_grade': 'surrogate', 'unsupported_patches': np.flatnonzero(invalid).tolist(), **info}
    dump(output, {'schema': 'closedloop-targets/1', 'frames': out,
                  'physical_model_iso': physical_model_iso,
                  'validation_from_frozen_round5': generator.validation, 'provenance': p.finish()})
    print(f'GR 目标写入 {output}；{len(out)} 项，包含基准及三行 EV。', flush=True)
    return output


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--requests', required=True)
    ap.add_argument('--measurement', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--physical-model-iso', type=int, choices=(200, 1600))
    args = ap.parse_args()
    generate(args.requests, args.measurement, args.out, args.physical_model_iso)
