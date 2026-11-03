"""Official Fuji LUTs, frozen GR transfers and a DNG-bound target interchange."""
import sys
sys.dont_write_bytecode = True
from types import SimpleNamespace
import numpy as np
from scipy.spatial import cKDTree
from common import ROOT, LOCAL, helper, load, sha, read, dump, require


class Targets:
    def __init__(self, engine, provenance, overrides=None):
        self.engine, self.p = engine, provenance
        self.fs = engine.fs
        self.relative = {}
        self.lut = None
        self.overrides = read(self.p.add(overrides)) if overrides else None
        if self.overrides:
            require(self.overrides.get('schema') == 'closedloop-targets/1', '目标 hook schema 不符')
        self.overridden_slots = {q.get('slot') for q in self.overrides.get('frames', {}).values()} if self.overrides else set()
        self.bw_tree = None

    def gr(self, slot):
        if slot not in self.relative:
            if slot == '01':
                path = ROOT / 'research/color_fit_v2/01_gr_positive/local/neutralised_fit_state.json'
                state = read(self.p.add(path))
                samples = state['models']['200']['samples']
                rgb04 = {s['label']: np.asarray(s['rgb04']) for s in samples}
            else:
                path = ROOT / 'research/color_fit_v2/02_gr_negative/round4/local/baseline/neutralised_prepared.json'
                state = read(self.p.add(path))
                d = state['datasets']['iso200']
                rgb04 = {s['label']: np.asarray(s['rgb04']) for s in d['samples']}
            self.p.add(ROOT / 'research/stage2d_verification/measurements.json')
            ctx = SimpleNamespace(rgb04=rgb04)
            self.relative[slot] = self.fs.RelativeTarget('gr3:' + ('positive' if slot == '01' else 'negative'), ctx)
        return self.relative[slot]

    def fuji(self):
        if self.lut is None:
            folder = ROOT / 'artifacts/downloads/fuji-luts'
            path = self.p.add(folder / 'gfx-eterna-55-3d-lut-v110.zip')
            sums = self.p.add(folder / 'SHA256SUMS').read_text().splitlines()
            expected = next(line.split()[0] for line in sums if line.split()[-1] == path.name)
            require(sha(path) == expected, 'Fuji LUT zip SHA-256 不符')
            self.lut = self.fs.FujiLUT(path)
            require(self.lut.ok, 'Fuji LUT 不可用')
        return self.lut

    def scene_scale(self, baseline, slot):
        folder = '05_classic_chrome' if slot == '05' else '06_classic_neg'
        path = ROOT / f'research/color_fit_v2/{folder}/round4/local/fit_v4_noT1.json'
        fit = read(self.p.add(path))
        anchor = fit['anchor']
        greys = [i for i, p in enumerate(baseline['patches']) if p['label'] == 'D4' or p['name'] == 'G_L50']
        require(len(greys) == 1, '需要基准 D4 或 G_L50')
        i = greys[0]
        u = float(np.asarray(baseline['raw_wb'])[i] @ np.array([.25, .5, .25]))
        rho = .18 * (u - anchor['f']) / (anchor['u_m'] - anchor['f'])
        yy = float(np.asarray(baseline['xyz_camera'])[i, 1])
        require(rho > 0 and yy > 0, '中灰的 DNG 亮度无效')
        return rho / yy, {'anchor': anchor, 'baseline_grey_u': u, 'baseline_grey_rho': rho,
                          'scene_scale': rho / yy, 'scope': 'same scale for every frame in this set'}

    def bw_reference(self):
        """Reuse round-2 flat-block observations; never fit targets from GXR JPEGs."""
        cache = LOCAL / 'bw_reference.npz'
        inputs = [ROOT / 'research/gr4_modes/local' / n for n in
                  ('hdf_hc.npz', 'hc_bw.npz', 'candidates.json', 'hcbw.json', 'tone_curves.json')]
        hashes = {str(self.p.add(p)): sha(p) for p in inputs}
        meta = cache.with_suffix('.json')
        valid = cache.exists() and meta.exists() and read(meta).get('inputs_sha256') == hashes
        if not valid:
            from types import SimpleNamespace
            h = load('bw_helpers', LOCAL / 'vendor/bw_helpers.py')
            cm = load('bw_colour_math', LOCAL / 'vendor/research/color_references/colour_math.py')
            h.cm, h.gr4io, h.core = cm, SimpleNamespace(dng_tags_for_colour=h.dng_tags_for_colour), h
            h.LUMA709 = np.array([.2126, .7152, .0722], np.float32)
            h.GR4, h.GXR_MID = ROOT / 'research/gr4_modes', 320.
            c, hc, tone = [read(p) for p in inputs[2:]]
            points, values, frames = [], [], []
            for i, (name, key) in enumerate((('hdf_hc', 'B_hdf'), ('hc_bw', 'pooled_gruser_dr_off'))):
                b = h.gr4_blocks(name, c['gr4_standard_118_u_c'][key],
                                np.asarray(hc['gxr_mix']['gxr_to_c_from_linsrgb']),
                                np.asarray(tone['radial']['gr4_coef_natural_log']))
                points.append(b['x']); values.append(b['j']); frames.append(np.full(len(b['j']), i))
            xx, yy, ff = np.concatenate(points), np.concatenate(values), np.concatenate(frames)
            # Deterministic thinning limits tree size without changing the reference convention.
            select = np.arange(0, len(yy), 4)
            np.savez(cache, x=xx[select], j=yy[select], frame=ff[select])
            dump(meta, {'inputs_sha256': hashes, 'source_blocks': len(yy), 'retained_blocks': len(select),
                       'method': '32-neighbour empirical GR IV HC JPEG mean in log GXR camera RGB; round-2 mapping',
                       'target_is_empirical_interpolation': True})
        self.p.add(cache); self.p.add(meta)
        with np.load(cache, allow_pickle=False) as z:
            x, self.bw_j, self.bw_frame = z['x'], z['j'], z['frame']
        self.bw_tree = cKDTree(np.log2(np.maximum(x, 1.)))

    def render(self, frame, baseline, x, stock_rgb, anchor_ev=0.):
        slot = frame['slot']
        labels = [p['label'] for p in frame['patches']]
        override_key = frame['id'] + ':' + slot
        if self.overrides and override_key not in self.overrides.get('frames', {}):
            q = self.overrides.get('frames', {}).get(frame['id'])
            if q is not None and q.get('slot') == slot:
                override_key = frame['id']
        if self.overrides and override_key in self.overrides.get('frames', {}):
            q = self.overrides['frames'][override_key]
            require(q.get('slot') == slot and q.get('dng_sha256') == frame['hashes']['DNG'],
                    'hook 目标与槽位或 DNG 哈希不匹配')
            require(q.get('labels') == labels and bool(q.get('source')), 'hook 目标的色块或来源缺失')
            if anchor_ev:
                key = f'{anchor_ev:+.1f}'
                require(key in q.get('anchor_lab', {}),
                        f'hook 缺少 {override_key} 的 {key} EV 目标；不能改用旧目标补齐')
                lab = np.asarray(q['anchor_lab'][key], float)
            else:
                lab = np.asarray(q['lab'], float)
            require(lab.shape == (len(labels), 3) and np.isfinite(lab).all(), 'hook Lab 数组无效')
            unsupported = q.get('unsupported_patches', [])
            require(isinstance(unsupported, list) and all(isinstance(i, int) and 0 <= i < len(labels)
                    for i in unsupported), 'hook 的不支持色块索引无效')
            return lab, {'kind': 'external_hook', 'source': q['source'],
                         'reference_grade': q.get('reference_grade', 'surrogate'),
                         'unsupported_patches': unsupported,
                         'metering_anchor_determined': q.get('metering_anchor_determined', False)}
        require(slot not in self.overridden_slots,
                f'hook 缺少 {frame["id"]}:{slot}，同槽实拍及其 04 基准都必须有新目标')
        if slot in ('04', '07', '08'):
            return self.fs.lab_from_codes(stock_rgb), {'kind': 'stock_control' if slot == '04' else 'probe_control',
                'reference_grade': 'control', 'note': '探针不设原创色彩目标，只诊断相对 stock 的偏差'}
        if slot in ('01', '02'):
            target = self.gr(slot)
            labs = self.fs.lab_from_codes(stock_rgb)
            out = np.array([target.apply(lab, target.change[label]) if frame['chart'] == 'physical'
                            else target.relative_target(lab)[0] for label, lab in zip(labels, labs)])
            return out, {'kind': 'GR_III_photo_relative', 'source': target.source,
                         'chart': 'per-patch transfer' if frame['chart'] == 'physical' else 'hue-interpolated transfer',
                         'input_pipeline': 'own DNG WB RGB / matched 04 DNG WB RGB; observed 04 inverse; stock forward; frozen real-patch GR relative transfer',
                         'anchor_delta_EV': anchor_ev, 'uses_Nominal04': False,
                         'reference_grade': 'surrogate', 'absolute_original_camera_similarity': False}
        if slot in ('05', '06'):
            scale, info = self.scene_scale(baseline, slot)
            xyz = np.asarray(frame['xyz_camera']) * scale
            sim = 'classic_chrome' if slot == '05' else 'classic_neg'
            rgb = self.fuji().render_xyz(sim, xyz)
            return self.fs.lab_from_codes(rgb), {'kind': 'official_FLog2_LUT_passthrough', 'simulation': sim,
                'zip_sha256': self.lut.sha, 'interpolation': 'tetrahedral', 'reference_grade': 'official_LUT',
                'input_pipeline': 'own DNG CFA RGB; DNG dual-illuminant matrix and Bradford D65; frozen metering anchor; F-Log2; official LUT passthrough',
                'uses_Nominal04': False,
                'absolute_original_camera_similarity': False, **info}
        require(slot == '03', '未知目标槽位')
        if self.bw_tree is None:
            self.bw_reference()
        dist, idx = self.bw_tree.query(np.log2(np.maximum(x, 1.)), k=32, workers=1)
        w = 1 / np.maximum(dist, .02)**2
        y = np.sum(w*self.bw_j[idx], axis=1)/w.sum(axis=1)
        lab = self.fs.lab_from_codes(np.repeat(y[:, None], 3, axis=1))
        return lab, {'kind': 'GR_IV_HC_empirical_round2', 'reference_grade': 'surrogate',
            'nearest_distance_log2_rgb': dist[:, 0].tolist(), 'unsupported_patches': np.flatnonzero(dist[:, 0] > .5).tolist(),
            'note': '实拍 GR IV 平坦块的局部插值；超出参考色域的色块不得解释为原机相似度',
            'absolute_original_camera_similarity': False}
