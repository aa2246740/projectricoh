#!/usr/bin/env python3
"""Round-one regressions against read-only camera inputs; fixtures stay in local/."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy
import unittest
import numpy as np
import measure
from common import LOCAL, ROOT, Provenance, helper, read, load, sha
from model import Engine
from targets import Targets


class OrientationTests(unittest.TestCase):
    def test_physical06_accepts_styled_jpeg(self):
        manifest = read(LOCAL / 'frames_20261021.json')
        frame = next(f for f in manifest['frames'] if f['id'] == 'physical06')
        result = measure.extract(frame, Provenance())
        self.assertEqual(len(result['patches']), 24)
        self.assertTrue(result['raw_jpeg_registration']['ok'])
        checks = result['geometry']['orientation_checks']
        self.assertTrue(checks['raw_grey_u_descending'])
        self.assertFalse(checks['third_row_b_min_is_C1_blue'])
        self.assertTrue(checks['warnings'])

    def test_rotated_and_mirrored_raw_are_rejected(self):
        physical = helper('physical')
        previous = physical.CAP
        try:
            physical.CAP = ROOT / 'captures/a12-50/2026-10-21/chart-closedloop'
            sampled, _, _ = physical.sample('R8051212')
        finally:
            physical.CAP = previous
        labels = [q['label'] for q in sampled]
        grid = np.arange(24).reshape(4, 6)
        permutations = [np.rot90(grid, k).ravel() for k in (1, 2, 3)]
        permutations += [grid[:, ::-1].ravel(), grid[::-1].ravel()]
        for indices in permutations:
            rotated = [dict(copy.deepcopy(sampled[i]), label=label)
                       for i, label in zip(indices, labels)]
            for slot in ('04', '03', '06'):
                with self.subTest(slot=slot, indices=indices.tolist()):
                    with self.assertRaisesRegex(ValueError, 'RAW|raw'):
                        measure.physical_orientation_checks(rotated, slot)

    def test_iso800_is_reported_but_cannot_enter_refit(self):
        result = read(LOCAL / 'm20261021_r1.json')
        self.assertEqual(result['eligible_refit_sets'], ['screen'])
        self.assertFalse(result['eligible_for_refit'])
        self.assertEqual(len(result['frames']), 14)
        for f in result['frames']:
            if f['set'] == 'physical':
                self.assertFalse(f['measurement_valid'])
                self.assertFalse(f['eligible_for_refit'])
                self.assertTrue(f['target_measurement_valid'])
                self.assertEqual(f['iso_status'], 'ISO 800 未标定')
            else:
                self.assertTrue(f['eligible_for_refit'])

    def test_fuji_targets_do_not_call_isp(self):
        result = read(LOCAL / 'm20261021_r1.json')
        frames = {f['id']: f for f in result['frames']}
        real = Engine()
        class NoISP:
            fs = real.fs
            def __getattr__(self, name):
                raise AssertionError('Fuji target called ISP: ' + name)
        target = Targets(NoISP(), Provenance())
        for slot in ('05', '06'):
            f, b = frames['physical'+slot], frames['physical04']
            first, _ = target.render(f, b, np.zeros((24, 3)), np.zeros((24, 3)))
            second, _ = target.render(f, b, np.full((24, 3), 9999.), np.full((24, 3), 255.))
            np.testing.assert_array_equal(first, second)
            np.testing.assert_allclose(first, f['target_lab'], atol=0)

    def test_firmware_hook_has_no_nominal04_and_contains_ev_and_controls(self):
        from firmware_targets import generate
        gr = load('gr5_targets_r1', ROOT / 'research/color_fit_v2/gr_round5/gr_targets.py')
        original = gr.fs.Nominal04
        def forbidden(*args, **kwargs):
            raise AssertionError('Nominal04 called by measured target generator')
        gr.fs.Nominal04 = forbidden
        try:
            generated = generate(LOCAL / 'm20261021_r1_target_requests.json',
                                 LOCAL / 'm20261021_r1.json', LOCAL / 'tmp/test_gr_targets.json')
        finally:
            gr.fs.Nominal04 = original
        self.assertEqual(sha(generated), sha(LOCAL / 'gr_targets_20261021_r1.json'))
        result = read(LOCAL / 'gr_targets_20261021_r1.json')
        self.assertEqual(len(result['frames']), 8)
        for set_name in ('screen', 'physical'):
            for slot in ('01', '02'):
                for fid in (set_name+slot, set_name+'04'):
                    q = result['frames'][fid+':'+slot]
                    self.assertFalse(q['nominal04_used'])
                    self.assertFalse(q['metering_anchor_determined'])
                    self.assertEqual(set(q['anchor_lab']), {'-0.3', '+0.3'})
                    self.assertEqual(len(q['lab']), len(q['labels']))

    def test_public_payload_48_byte_boundary(self):
        from verify_delivery import check_public_payload
        fixture = LOCAL / 'tmp/test_public_payload.py'
        try:
            for size in (32, 47):
                fixture.write_text('payload = ' + repr('ab'*size) + '\n')
                check_public_payload(fixture)
            for content in ('payload = ' + repr('ab'*48), 'payload = ' + repr(b'x'*48)):
                fixture.write_text(content + '\n')
                with self.assertRaisesRegex(ValueError, '48'):
                    check_public_payload(fixture)
        finally:
            fixture.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
