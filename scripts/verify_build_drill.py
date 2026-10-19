#!/usr/bin/env python3
"""Check build_drill against upstream's pinned language builds and against bad patches; writes no firmware outside a temp dir."""

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_drill as bd


OUT = bd.ROOT / "artifacts/phase0-drill/builder-verification.json"
# Pinned results of sources/gxr-language-patch/gxr_firmware_modifier.py; the patch bytes below are transcribed from it, not imported.
UPSTREAM_ENGLISH_SHA256 = "e543f5866bbc99ad4697c6dddb931c5a0fa0526fed34c421541ae32fb7f0c785"
UPSTREAM_UNLOCK_SHA256 = "1a383ab94db6bcc4b00583ca3d61339b7f39917aeaf8ec3be9c8809b222c9439"


def bl(pc, target):
    delta = target - (pc & ~3)
    assert delta % 4 == 0 and -(1 << 25) <= delta < (1 << 25)
    return "fe " + ((delta // 4) & 0xFFFFFF).to_bytes(3, "big").hex(" ")


def patch(name, offset, expected, replacement):
    return {"name": name, "file": "ilaunch3", "offset": offset, "expected": expected, "replacement": replacement}


ENGLISH = {"name": "upstream-english", "patches": [
    patch("boot language map", "0x1C348",
          "d0 c0 20 0c 80 e0 0d 9c 20 c0 f0 00 a0 90 00 17",
          "61 01 f0 00 b0 11 00 03 60 06 f0 00 80 e0 00 00"),
    patch("sync branch", "0x1C774", "7f 02", "7f 04"),
    patch("runtime sync", "0x1C778",
          "a2 91 00 17 d0 c0 20 0c 80 e0 0d ac 21 c0 f0 00 a2 01 03 97",
          "12 80 61 01 b2 11 00 02 62 06 f0 00 a2 03 03 97 80 e0 00 00"),
    patch("language init", "0x176150",
          "28 7f 2e 7f 18 84 f0 00 d0 c0 20 1d 80 e0 1e fc 14 88 1e c0 "
          "d0 c0 20 1d 80 e0 4f 24 14 88 1e c0 d0 c0 20 1d 80 e0 83 ec 14 88 1e c0",
          "28 7f 2e 7f 18 84 60 01 b8 10 00 02 68 06 14 88 " + bl(0x201C0F60, 0x201D1EFC) + " 14 88 f0 00 "
          + bl(0x201C0F68, 0x201D4F24) + " 80 e0 00 00 14 88 f0 00 " + bl(0x201C0F74, 0x201D83EC) + " 80 e0 00 00"),
]}
UNLOCK = {"name": "upstream-unlock", "patches": [
    patch("region persistence wrapper", "0x2D1C8",
          "4f ec 28 7f 29 7f 2e 7f d0 c0 20 0c 85 e0 a4 d3 d0 c0 20 0b 84 af 00 0c 80 e0 bd 04 66 12 1e c0 "
          "d0 c0 20 0c 80 e0 0d 9c 24 c0 f0 00",
          "28 7f 2e 7f 18 84 f0 00 d1 c0 20 0c 81 e1 0d 9c 21 c1 60 06 a0 01 00 17 " + bl(0x20077FE0, 0x2007785C)
          + " 14 88 f0 00 " + bl(0x20077FE8, 0x201C0F50) + " 2e ef 28 ef 1f ce f0 00"),
    patch("language confirm", "0x30FDC8", "d0 c0 20 1c 80 e0 0f 50", "d0 c0 20 07 80 e0 7f c8"),
    patch("spare language confirm", "0x327140", "d0 c0 20 1c 80 e0 0f 50", "d0 c0 20 07 80 e0 7f c8"),
]}


def refused(files, segments, spec):
    try:
        bd.build(files, {"name": "bad", **spec}, segments)
    except ValueError as error:
        return str(error)
    raise AssertionError(f"accepted a bad spec: {spec}")


def main():
    files = bd.load_official(bd.ROOT / "artifacts/firmware/gxr-1.51")
    segments = bd.load_segments(bd.ROOT / "research/firmware/ilaunch3-sections.csv")
    checks = {}

    outputs, report = bd.build(files, ENGLISH, segments)
    assert bd.digest(outputs["ilaunch3"]) == UPSTREAM_ENGLISH_SHA256
    assert report[0]["patches"][3]["vma"] == "0x201C0F50"
    checks["reproduces_upstream_english"] = bd.digest(outputs["ilaunch3"])
    outputs, report = bd.build(files, UNLOCK, segments)
    assert bd.digest(outputs["ilaunch3"]) == UPSTREAM_UNLOCK_SHA256
    assert report[0]["patches"][0]["vma"] == "0x20077FC8"
    checks["reproduces_upstream_unlock"] = bd.digest(outputs["ilaunch3"])

    seg0_end, seg1_start = segments[0]["end"], segments[1]["start"]
    good = ENGLISH["patches"][1]
    checks["refusals"] = {
        "wrong_expected_bytes": refused(files, segments, {"patches": [{**good, "expected": "0000"}]}),
        "length_change": refused(files, segments, {"patches": [{**good, "replacement": "7f0400"}]}),
        "empty_patch": refused(files, segments, {"patches": [{**good, "expected": "", "replacement": ""}]}),
        "inside_header": refused(files, segments, {"patches": [patch("hdr", "0x16C", files["ilaunch3"][0x16C:0x170].hex(), "00000000")]}),
        "inter_segment_padding": refused(files, segments, {"patches": [patch("pad", f"0x{seg0_end + 4:X}", "ff", "00")]}),
        "straddles_segment_end": refused(files, segments, {"patches": [
            patch("edge", f"0x{seg0_end - 2:X}", files["ilaunch3"][seg0_end - 2:seg0_end + 2].hex(), "00000000")]}),
        "overlapping": refused(files, segments, {"patches": [good, {**good, "name": "again"}]}),
        "module_file": refused(files, segments, {"patches": [{**good, "file": "jlaunch3"}]}),
    }
    tampered = dict(files, ilaunch4=files["ilaunch4"][:-1] + bytes([files["ilaunch4"][-1] ^ 1]))
    try:
        bd.check_official(tampered)
        raise AssertionError("accepted a tampered official file")
    except ValueError as error:
        checks["refusals"]["tampered_input"] = str(error)
    stray = bytearray(outputs["ilaunch3"])
    stray[0x300] ^= 1
    try:
        bd.checksum_phase(stray)
        raise AssertionError("checksum missed a one-byte change")
    except ValueError as error:
        checks["refusals"]["checksum_detects_one_byte"] = str(error)

    with tempfile.TemporaryDirectory() as temp:
        outputs, report = bd.build(files, ENGLISH, segments)
        drill, recovery = Path(temp, "drill/SD_ROOT"), Path(temp, "recovery/SD_ROOT")
        bd.write_tree(drill, outputs)
        bd.write_tree(recovery, files)
        bd.check_written(drill, recovery, files, report)
        caught = {}
        for label, path in (("recovery_file_changed", recovery / "jlaunch3"), ("unpatched_drill_file_changed", drill / "ilaunch4")):
            original = path.read_bytes()
            path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            try:
                bd.check_written(drill, recovery, files, report)
                raise AssertionError(f"write check missed {label}")
            except (AssertionError, ValueError) as error:
                if str(error).startswith("write check missed"):
                    raise
                caught[label] = str(error)
            path.write_bytes(original)
        (drill / "EXTRA.TXT").write_text("x")
        try:
            bd.check_written(drill, recovery, files, report)
            raise AssertionError("write check missed an extra file")
        except AssertionError as error:
            if str(error).startswith("write check missed"):
                raise
            caught["extra_file_on_card"] = str(error).replace(temp, "<tmp>")
        checks["write_check"] = {"clean_tree": "passed", **caught}

    evidence = {"status": "passed", "camera_tested": False, "firmware_inputs": "official 1.51, 29 SHA-256 matched", **checks}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "refusals": len(checks["refusals"]), "write_checks": len(checks["write_check"])}))


if __name__ == "__main__":
    main()
