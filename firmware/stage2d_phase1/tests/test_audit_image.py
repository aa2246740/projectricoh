#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import unittest
import argparse
import sys

path = Path(__file__).resolve().parents[1] / "tools/audit_image.py"
spec = importlib.util.spec_from_file_location("recipe_image_audit", path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ImageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.original_hooks, cls.payload, cls.symbols = audit.read_inputs(cls.output)

    def setUp(self):
        self.hooks = copy.deepcopy(self.original_hooks)

    def check(self, files=None, payload=None):
        return audit.audit(self.files if files is None else files, self.hooks,
                           self.payload if payload is None else payload, self.symbols)

    def test_whole_image_preserves_other_components_and_boundaries(self):
        report = self.check()
        self.assertEqual(report["status"], "IN_MEMORY_IMAGE_AUDIT_PASS")
        self.assertEqual(report["official_components_verified"], 29)
        self.assertEqual(len(report["unchanged_components"]), 28)
        self.assertEqual(report["modified_segments"], [0, 8, 9])
        self.assertEqual(len(report["allowed_changes"]), 10)
        self.assertTrue(report["checksum_independently_verified"])
        self.assertTrue(report["shared_layer_function_unchanged"])
        self.assertTrue(report["probe_reserve_unchanged"])
        self.assertFalse(report["image_written"])

    def test_changed_module_or_official_body_rejected(self):
        for name in ("jlaunch3", "ilaunch3"):
            files = dict(self.files)
            value = bytearray(files[name]); value[-1] ^= 1
            files[name] = bytes(value)
            with self.assertRaisesRegex(ValueError, "Not the official"):
                self.check(files=files)

    def test_missing_or_extra_hook_rejected(self):
        self.hooks["hooks"].pop()
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.check()
        self.hooks = copy.deepcopy(self.original_hooks)
        self.hooks["hooks"].append(self.hooks["hooks"][0])
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.check()

    def test_stale_branch_target_rejected(self):
        next(h for h in self.hooks["hooks"] if h['id'] == 'fn2_no_editor')["new_bytes"] = "ff000000"
        with self.assertRaisesRegex(ValueError, "Branch target"):
            self.check()

    def test_forcing_a_nonimage_adj_function_is_not_an_allowed_patch(self):
        self.hooks['hooks'].append({'id':'force_adj_image'})
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.check()

    def test_wrong_file_mapping_rejected(self):
        self.hooks["hooks"][0]["file_offset"] = "0x175b2c"
        with self.assertRaisesRegex(ValueError, "mapping"):
            self.check()

    def test_payload_corruption_or_probe_overlap_rejected(self):
        changed = bytearray(self.payload); changed[0] ^= 1
        with self.assertRaisesRegex(ValueError, "Payload hash"):
            self.check(payload=bytes(changed))
        with self.assertRaisesRegex(ValueError, "reserved region"):
            self.check(payload=b"x" * 8088)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--build',type=Path,default=path.parents[1]/'build')
    args, remaining = parser.parse_known_args()
    ImageAuditTests.output = args.build
    unittest.main(argv=[sys.argv[0],*remaining])
