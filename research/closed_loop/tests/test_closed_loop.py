#!/usr/bin/env python3
"""Behavior tests, with all generated scene data in ../local/tests/."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy
import json
import unittest
from types import SimpleNamespace
import numpy as np
from common import ROOT, LOCAL, read, dump, sha, output_path, input_path, mount_guard, Provenance
from model import Engine
from measure import stats, similarity, metadata_checks, validate_manifest
from targets import Targets
from refit import Problem, run as refit_run


class ClosedLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mount_guard()
        cls.E = Engine()
        cls.out = LOCAL / 'tests'
        cls.out.mkdir(exist_ok=True)
        cls.results = {}

    @classmethod
    def tearDownClass(cls):
        dump(cls.out / 'results.json', cls.results)

    def test_01_ciede2000_and_statistics(self):
        fs = self.E.fs
        # Sharma et al. reference pair, independent of the camera model.
        a, b = np.array([50., 2.6772, -79.7751]), np.array([50., 0., -82.7485])
        self.assertAlmostEqual(float(fs.delta_e00(a, b)), 2.0425, places=4)
        self.assertEqual(stats([.5, 1., 1.5, 2., 3.])['share_under_1'], .2)
        self.assertEqual(stats([.5, 1., 1.5, 2., 3.])['share_under_2'], .6)
        self.assertAlmostEqual(similarity([1, 1], [4, 4])['value'], .75)
        self.assertIsNone(similarity([1, 1], [0, 0])['value'])
        self.assertLess(similarity([5], [2])['value'], 0)
        self.assertIsNone(stats([])['median'])

    def test_02_reject_inconsistent_metadata_and_missing_baseline(self):
        meta = {'program': 1, 'exposure_mode': 1, 'iso': 200, 't': 1/60, 'f': 4.,
                'wb_exif': 1, 'wb_record_0x26': 5, 'selector': 1, 'asn': [1., 1., 1.]}
        f = {'id': 'A', 'slot': '04', 'meta': meta, 'metadata_errors': []}
        self.assertTrue(metadata_checks([f])['pass'])
        for field, value in [('program', 2), ('iso', 400), ('t', 1/125), ('f', 5.6),
                             ('wb_exif', 0), ('wb_record_0x26', 0), ('asn', [1.1, 1., 1.])]:
            g = copy.deepcopy(f); g['id'] = 'B'; g['meta'][field] = value
            self.assertFalse(metadata_checks([f, g])['pass'], field)
        g = copy.deepcopy(f); g['slot'] = '03'
        self.assertFalse(metadata_checks([g])['pass'])
        manifest = {'schema': 'closedloop-frames/1', 'frames': [
            {'id': 'x', 'set': 's', 'slot': '01', 'chart': 'hue-ring', 'jpeg': 'x.JPG', 'baseline': 'missing'}]}
        with self.assertRaisesRegex(ValueError, 'baseline'):
            validate_manifest(manifest)

    def test_03_write_boundary_and_other_volume_rejected(self):
        with self.assertRaises(ValueError):
            output_path(ROOT / 'research/should_not_write.json')
        with self.assertRaises(ValueError):
            input_path('/Volumes/UnrelatedDrive/frame.JPG')
        with self.assertRaises(ValueError):
            output_path(LOCAL / '../escaped.json')
        link = self.out / 'escape_link'
        if not link.exists():
            link.symlink_to(ROOT, target_is_directory=True)
        try:
            with self.assertRaises(ValueError):
                output_path(link / 'outside.json')
        finally:
            link.unlink()

    def test_04_invalid_real_measurement_cannot_refit(self):
        for name in ['dry_ring_measurement', 'dry_2e_measurement']:
            path = LOCAL / (name+'.json')
            self.assertTrue(path.exists(), '先运行 tests/dry_run.py')
            with self.assertRaisesRegex(ValueError, '禁止回拟'):
                refit_run(path, self.out / 'must_not_exist')
        self.assertFalse((self.out / 'must_not_exist').exists())

    def test_05_target_hooks_bind_dng_slot_and_baseline(self):
        f = {'id': 'frame', 'slot': '01', 'hashes': {'DNG': 'a'*64}, 'chart': 'hue-ring',
             'patches': [{'label': '1'}]}
        q = {'slot': '01', 'labels': ['1'], 'lab': [[45., 2., 3.]], 'dng_sha256': 'a'*64,
             'source': 'invented test target'}
        path = self.out / 'hook.json'
        dump(path, {'schema': 'closedloop-targets/1', 'frames': {'frame:01': q}})
        T = Targets(self.E, Provenance(), path)
        lab, meta = T.render(f, f, np.ones((1, 3)), np.ones((1, 3)))
        np.testing.assert_equal(lab, [[45., 2., 3.]])
        bad = copy.deepcopy(f); bad['hashes']['DNG'] = 'b'*64
        with self.assertRaisesRegex(ValueError, '哈希'):
            T.render(bad, bad, np.ones((1, 3)), np.ones((1, 3)))
        base = copy.deepcopy(f); base['id'] = '04base'
        with self.assertRaisesRegex(ValueError, '缺少'):
            T.render(base, base, np.ones((1, 3)), np.ones((1, 3)))

    def test_06_frozen_gr_targets_and_fuji_zip(self):
        T = Targets(self.E, Provenance())
        for slot in ('01', '02'):
            gr = T.gr(slot)
            self.assertEqual(len(gr.hk), 18)
            path = 'research/color_fit_v2/01_gr_positive/local/neutralised_fit_state.json' if slot == '01' else \
                   'research/color_fit_v2/02_gr_negative/round4/local/baseline/neutralised_prepared.json'
            saved = read(ROOT / path)
            samples = saved['models']['200']['samples'] if slot == '01' else saved['datasets']['iso200']['samples']
            actual = np.array([gr.chart_target(q['label']) for q in samples])
            expected = np.array([q['target'] for q in samples])
            np.testing.assert_allclose(actual, expected, atol=1e-12)
        lut = T.fuji()
        self.assertTrue(lut.ok)
        self.assertEqual(len(lut.sha), 64)
        # Frozen round-4 target arrays use exactly this official LUT renderer.
        fit = read(ROOT / 'research/fuji_phase2/local/fit.json')
        xyz = self.E.fs.chart_xyz_d65(fit)
        values = {}
        for sim in ('classic_chrome', 'classic_neg'):
            recorded = {p['label']: np.array(p['fuji_srgb_code']) for p in fit['chart_patches'][sim]}
            error = max(float(np.max(abs(lut.render_xyz(sim, xyz[label])-v))) for label, v in recorded.items())
            self.assertLess(error, 2e-5)
            values[sim] = error
        self.results['official_lut_frozen_chart_max_RGB_code_error'] = values

    def test_07_v2_jacobian_and_bias_sign(self):
        rng = np.random.default_rng(722)
        x = rng.uniform(150, 1200, (150, 3)); rgb = self.E.predict('05', x)
        P = Problem(self.E, '05', x, rgb+np.array([.3, -.2, .1]), self.E.fs.lab_from_codes(rgb))
        np.testing.assert_allclose(P.corrected_rgb(P.initial), np.clip(rgb+[.3, -.2, .1], 0, 255), atol=2e-5)
        direction = rng.normal(size=P.np); direction /= np.linalg.norm(direction)
        th = P.initial.copy(); eps = 1e-5
        fd = (P.residuals(th+eps*direction)-P.residuals(th-eps*direction))/(2*eps)
        analytic = P.jacobian(th)@direction
        error = np.linalg.norm(fd-analytic)/np.linalg.norm(fd)
        self.assertLess(error, 1e-5)
        self.results['jacobian_relative_error'] = error

    def test_08_injected_error_recovered_after_integer_encoding(self):
        rng = np.random.default_rng(27)
        x = rng.uniform(150, 1200, (420, 3))
        rgb = self.E.predict('05', x)
        x = x[(rgb.min(1)>10) & (rgb.max(1)<245)]
        # Explicit neutral ramp supplies anchors for the actual refit entry point.
        gray_x = np.repeat(np.linspace(160, 1100, 12)[:, None], 3, axis=1)
        x = np.vstack([gray_x, x]); gray = np.arange(len(x)) < len(gray_x)
        rgb = self.E.predict('05', x); target = self.E.fs.lab_from_codes(rgb)
        P0 = Problem(self.E, '05', x, rgb, target, gray=gray, ridge=1e-5, smooth=1e-4)
        injected = P0.initial.copy(); injected[:2] = [.025, -.015]
        hue = np.arange(24)*2*np.pi/24
        injected[2:26] += .025*np.sin(hue); injected[26:] += .02*np.cos(hue)
        observed = P0.corrected_rgb(injected)
        P = Problem(self.E, '05', x, observed, target, gray=gray, ridge=1e-5, smooth=1e-4)
        solution = P.solve(50)
        self.assertTrue(solution.success)
        np.testing.assert_allclose(solution.x[:2], [-.025, .015], atol=.001)
        continuous_rms = float(np.sqrt(np.mean((solution.x-P.initial+injected-P0.initial)**2)))
        self.assertLess(continuous_rms, .002)
        candidate = P.quantize(solution.x)
        row, _, A, B, _, _ = candidate
        qtheta = P.initial.copy()
        qtheta[:2] = (row.coef[0, [0, 2]]-P.row.coef[0, [0, 2]])/1024
        z = self.E.fs.Z_of_words(A, B, self.E.ctx)
        qtheta[2:26], qtheta[26:] = np.log(abs(z)), np.angle(z)
        # A new synthetic camera pass, not merely the corrected model projection.
        actual_next = P0.corrected_rgb(injected + qtheta - P.initial)
        before = self.E.fs.delta_e00(self.E.fs.lab_from_codes(observed), target)
        after = self.E.fs.delta_e00(self.E.fs.lab_from_codes(actual_next), target)
        improvement = 1-np.median(after[~gray])/np.median(before[~gray])
        self.assertGreater(improvement, .65)
        parameter_rms = float(np.sqrt(np.mean((qtheta-P.initial+injected-P0.initial)**2)))
        # A Q5 colour-word step plus safety repair is coarser than the continuous optimum.
        self.assertLess(parameter_rms, .02)
        self.assertTrue(self.E.safety(A, B)['passes'])
        np.savez(self.out / 'synthetic_frames.npz', x=x, deployed_rgb=rgb, target_lab=target,
                 observed_rgb=observed, next_camera_rgb=actual_next, injected_theta=injected,
                 recovered_theta=qtheta)
        self.results['synthetic_integer_recovery'] = {'patches': len(x), 'before': stats(before[~gray]),
            'next_camera_after_integer': stats(after[~gray]), 'improvement': improvement,
            'continuous_parameter_RMS': continuous_rms, 'integer_parameter_RMS': parameter_rms,
            'Y_recovered_Q10_delta': (row.coef[0]-P.row.coef[0]).tolist()}
        frame = {'id': 'synthetic05', 'slot': '05', 'chart': 'hue-ring', 'set': 'invented',
                 'measurement_valid': True, 'meta': {'iso': 200}, 'model': self.E.description(),
                 'input_x': x, 'rgb': observed, 'target_lab': target,
                 'valid': np.ones(len(x), bool), 'hue_deg': np.mod(np.arange(len(x))*137.5, 360),
                 'patches': [{'gray': bool(g)} for g in gray],
                 'target_definition': {'kind': 'synthetic_known_injection'}}
        measure = self.out / 'synthetic_measurement.json'
        dump(measure, {'schema': 'closedloop-measurement/1', 'eligible_for_refit': True,
                       'diagnostic_only': False, 'is_synthetic': True, 'frames': [frame], 'provenance': {}})
        refit_run(measure, self.out / 'synthetic_candidates', ['05'], max_nfev=40)
        result = read(self.out / 'synthetic_candidates/slot05_candidate.json')
        self.assertFalse(result['firmware_ready'])
        self.assertFalse(result['accepted'])
        self.assertFalse(result['deployable'])
        self.assertEqual(result['curve']['output33_u8'], self.E.curve_of('05').ys.astype(int).tolist())
        self.results['refit_cli_review_gate_passed'] = result['review_gate_passed']

    def test_09_bw_y_only_and_chroma_cannot_leak(self):
        rng = np.random.default_rng(93); x = rng.uniform(100, 800, (150, 3))
        rgb = self.E.predict('03', x); target = self.E.fs.lab_from_codes(rgb)
        P = Problem(self.E, '03', x, rgb, target, ridge=1e-5)
        self.assertEqual(P.np, 2)
        th = P.initial.copy(); th[:] = [.035, -.02]
        observed = P.corrected_rgb(th)
        Q = Problem(self.E, '03', x, observed, target, ridge=1e-5)
        sol = Q.solve(30); row, _, A, B, _, _ = Q.quantize(sol.x)
        np.testing.assert_equal(A, P.A); np.testing.assert_equal(B, P.B)
        self.assertEqual(int(row.coef[0].sum()), 1024)
        self.assertLess(np.max(abs(sol.x + th)), .001)
        pred = Q.integer_rgb(Q.quantize(sol.x))
        np.testing.assert_equal(pred[:, 0], pred[:, 1])
        np.testing.assert_equal(pred[:, 1], pred[:, 2])

    def test_10_targets_use_each_dng_without_nominal04(self):
        from measure import score_record
        d = read(LOCAL / 'dry_2e_measurement.json')
        base = next(f for f in d['frames'] if f['id'] == 'R8051160')
        saved = self.E.fs.Nominal04
        def forbidden(*args, **kwargs):
            raise AssertionError('Nominal04 must never be in the measured-target path')
        self.E.fs.Nominal04 = forbidden
        try:
            shifts = {}
            for slot in ('01', '02', '05', '06'):
                f = copy.deepcopy(next(f for f in d['frames'] if f['slot'] == slot))
                T = Targets(self.E, Provenance())
                first = score_record(self.E, T, copy.deepcopy(f), base)
                changed = copy.deepcopy(f)
                changed['raw_wb'] = np.asarray(changed['raw_wb'])*2**.3
                changed['xyz_camera'] = np.asarray(changed['xyz_camera'])*2**.3
                second = score_record(self.E, T, changed, base)
                delta = self.E.fs.delta_e00(first['target_lab'], second['target_lab'])
                self.assertGreater(float(np.median(delta)), 1., slot)
                shifts[slot] = float(np.median(delta))
                if slot in ('01', '02'):
                    self.assertEqual([r['anchor_delta_EV'] for r in first['gr_anchor_sensitivity']], [-.3, 0., .3])
                    # Main target remains exactly the 0 EV target; no best-row selection.
                    np.testing.assert_allclose(first['de00'], first['gr_anchor_sensitivity'][1]['de00'], atol=1e-10)
            self.results['own_DNG_plus_0p3_EV_target_shift_median'] = shifts
        finally:
            self.E.fs.Nominal04 = saved


if __name__ == '__main__':
    unittest.main(verbosity=2)
