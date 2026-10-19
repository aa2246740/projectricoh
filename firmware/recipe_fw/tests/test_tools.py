#!/usr/bin/env python3
import copy
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import zlib

HERE = Path(__file__).resolve().parents[1]


def module(name,path):
    specification = importlib.util.spec_from_file_location(name,path)
    result = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(result)
    return result


make = module("make",HERE/"tools/make_recipes.py")
build = module("build",HERE/"tools/build.py")


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads((HERE/"tools/example_recipes.json").read_text())

    def test_crc_and_canonical_empty_slots(self):
        blob = make.compile_recipes(self.document)
        self.assertEqual(len(blob),1056)
        self.assertEqual(blob[:16],b"GXRRV101\x00\x01\x00\x20\x00\x40\x00\x10")
        self.assertEqual(struct.unpack_from(">I",blob,28)[0],zlib.crc32(blob[:28]))
        self.assertEqual(struct.unpack_from(">I",blob,24)[0],zlib.crc32(blob[32:]))
        for index in range(16):
            record = blob[32+index*64:96+index*64]
            self.assertEqual(record[0],index+1)
            self.assertEqual(struct.unpack_from(">I",record,60)[0],zlib.crc32(record[:60]))
            if index not in (0,1,2,15): self.assertEqual(record[1:60],bytes(59))

    def test_all_display_values_and_wb(self):
        recipe = self.document["recipes"][0]
        for name in make.PARAMETERS: recipe["parameters"][name] = 1
        for value,raw in enumerate((7,6,1,2,3,4,5,8,9),1):
            recipe["parameters"]["contrast"] = value
            self.assertEqual(make.compile_recipes(self.document)[68],raw)
        self.assertEqual(make.compile_recipes(self.document)[81:83],bytes((2,253)))

    def test_names(self):
        for name in (""," ","中","bad\x00name","bad\nname","a"*33):
            self.document["recipes"][0]["name"] = name
            with self.assertRaises(ValueError): make.compile_recipes(self.document)
        self.document["recipes"][0]["name"] = "a"*32
        self.assertEqual(make.compile_recipes(self.document)[34],32)

    def test_parameter_ranges_and_types(self):
        for value in (0,10,-1,True,1.5,"5"):
            self.document["recipes"][0]["parameters"]["contrast"] = value
            with self.assertRaises(ValueError): make.compile_recipes(self.document)

    def test_wb_ranges_and_shape(self):
        for wb in ([-9,0],[0,9],[True,0],[],[0],[0,0,0]):
            self.document["recipes"][0]["wb"] = wb
            with self.assertRaises(ValueError): make.compile_recipes(self.document)

    def test_duplicate_and_bad_slots(self):
        duplicate = copy.deepcopy(self.document)
        duplicate["recipes"][1]["slot"] = 1
        with self.assertRaises(ValueError): make.compile_recipes(duplicate)
        for slot in (0,17,False,"1"):
            self.document["recipes"][0]["slot"] = slot
            with self.assertRaises(ValueError): make.compile_recipes(self.document)

    def test_generation_range_and_missing_parameters(self):
        for generation in (-1,0x100000000,True):
            self.document["generation"] = generation
            with self.assertRaises(ValueError): make.compile_recipes(self.document)
        self.document["generation"] = 1
        del self.document["recipes"][0]["parameters"]["blue_hue"]
        with self.assertRaises(ValueError): make.compile_recipes(self.document)

    def test_branch_boundaries_reject_silent_wrap(self):
        for bits in (8,16,24):
            limit = (1 << (bits-1))*4
            pc = 0x2028a000
            self.assertTrue(build.distance(pc,pc-limit,bits)["pass"])
            self.assertTrue(build.distance(pc,pc+limit-4,bits)["pass"])
            for delta in (-limit-4,limit,1):
                with self.assertRaises(ValueError): build.distance(pc,pc+delta,bits)

    def test_hooks_match_firmware_and_do_not_touch_probe(self):
        spec = json.loads((HERE/"hooks.json").read_text())
        image = build.IMAGE.read_bytes()
        changes = []
        for hook in spec["hooks"]:
            offset = int(hook["file_offset"],16)
            old,new = bytes.fromhex(hook["original_bytes"]),bytes.fromhex(hook["new_bytes"])
            self.assertEqual(len(old),len(new))
            self.assertEqual(image[offset:offset+len(old)],old)
            changes.append((offset,offset+len(old)))
        self.assertEqual(len(changes),9)
        for i,(begin,end) in enumerate(changes):
            self.assertTrue(all(end <= start or begin >= stop for start,stop in changes[:i]))
        probe = spec["probe_contract"]
        start = int(probe["file_offset"],16)
        self.assertEqual(image[start:start+256],b"\xff"*256)
        payload = spec["payload_patch"]
        self.assertLessEqual(int(payload["file_offset"],16)+payload["length"],start)
        self.assertFalse(probe["integration_writes"])

    def test_proposed_changes_preserve_whole_shared_layer_function(self):
        spec = json.loads((HERE/"hooks.json").read_text())
        original = build.IMAGE.read_bytes()
        candidate = bytearray(original)
        for hook in spec["hooks"]:
            start = int(hook["file_offset"],16)
            candidate[start:start+hook["length"]] = bytes.fromhex(hook["new_bytes"])
        payload = spec["payload_patch"]
        start = int(payload["file_offset"],16)
        candidate[start:start+payload["length"]] = (build.ROOT/payload["new_bytes_asset"]).read_bytes()
        self.assertEqual(candidate[0x175b2c:0x175ef4],original[0x175b2c:0x175ef4])
        self.assertEqual(candidate[0x175b2c:0x175b30],bytes.fromhex("287f297f"))
        self.assertNotIn("layer_close_lifetime",[h["id"] for h in spec["hooks"]])

    def test_shared_layer_guard_rejects_entry_body_and_payload_overlap(self):
        original = build.IMAGE.read_bytes()
        segments = build.image_segments(original)
        for start,length in ((0x175b2c,4),(0x175b2b,2),(0x175c00,4),(0x175ef3,2)):
            hook = {"file_offset":hex(start),"length":length}
            with self.assertRaisesRegex(ValueError,"patch overlaps protected code"):
                build.check_protected_code(original,segments,[hook],0x796c,4)
            with self.assertRaisesRegex(ValueError,"patch overlaps protected code"):
                build.check_protected_code(original,segments,[],start,length)

    def test_native_activity_branches_cannot_be_patched(self):
        original = build.IMAGE.read_bytes()
        segments = build.image_segments(original)
        for begin,end in ((0x202be23c,0x202be24c),(0x202bb960,0x202bb968)):
            for va in range(begin,end,4):
                _,offset = build.map_va(segments,va,4)
                hook = {"file_offset":hex(offset),"length":4}
                with self.assertRaisesRegex(ValueError,"patch overlaps protected code"):
                    build.check_protected_code(original,segments,[hook],0x796c,4)


if __name__ == "__main__":
    unittest.main()
