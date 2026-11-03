#!/usr/bin/env python3
"""Compare portable integer C functions against every Python combination."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ctypes as ct
import itertools
import json
import subprocess
import runtime as r
import tweak as t


def main():
    r.setup()
    _, _, _, entries = r.baseline()
    folder = r.LOCAL / "native"
    folder.mkdir(exist_ok=True)
    library = folder / "librecipe_tweak.dylib"
    argv = ["clang", "-std=c11", "-Os", "-Wall", "-Wextra", "-Werror", "-dynamiclib",
            str(r.HERE / "tweak_int.c"), "-o", str(library)]
    cp = subprocess.run(argv, capture_output=True, text=True, timeout=55)
    r.dump(folder / "compile_port.json", {"argv": argv, "exit_code": cp.returncode,
                                         "stdout": cp.stdout, "stderr": cp.stderr})
    if cp.returncode:
        raise RuntimeError("portable C build failed")
    lib = ct.CDLL(str(library))
    pointer = ct.POINTER(ct.c_uint8)
    lib.rt_tone.argtypes = [pointer, pointer, ct.c_int, ct.c_int, ct.c_int, ct.c_int, pointer]
    lib.rt_tone.restype = ct.c_int
    lib.rt_colour.argtypes = [pointer, ct.c_int, pointer]
    lib.rt_colour.restype = ct.c_int
    array = lambda blob: (ct.c_uint8 * len(blob)).from_buffer_copy(blob)
    out33, out96 = (ct.c_uint8 * 33)(), (ct.c_uint8 * 96)()
    stock = entries["04"]["rows"]
    pivot = t.midgray_input(stock[0], stock[1])
    tones, colours = 0, 0
    for slot in r.SLOTS:
        entry = entries[slot]
        for values in itertools.product(range(-2, 3), repeat=4):
            levels = t.Levels(*values)
            pairs = [(entry["rows"][0], entry["rows"][1])]
            if entry["mask"] & 2:
                pairs += [(entry["rows"][0], entry["rows"][6][i:i + 33]) for i in (0, 33)]
            for a, b in pairs:
                expected = t.tweak_curve(a, b, levels, pivot)
                assert lib.rt_tone(array(a), array(b), pivot, levels.contrast,
                                   levels.highlight, levels.shadow, out33) == 0
                assert bytes(out33) == expected
                tones += 1
            colour = entry["rows"][2]
            expected, clamped = t.tweak_colour(colour, levels.saturation)
            assert lib.rt_colour(array(colour), levels.saturation, out96) == len(clamped)
            assert bytes(out96) == expected
            colours += 1
    # Synthetic endpoints, sign-zero bytes and a full-scale A20 sentinel.
    sat = bytes([127, 255, 0, 128] * 24)
    assert lib.rt_colour(array(sat), 2, out96) == 48 and bytes(out96) == sat
    a20, b20 = stock[4], stock[5]
    for c, h, s in itertools.product(range(-2, 3), repeat=3):
        levels = t.Levels(contrast=c, highlight=h, shadow=s)
        expected = t.tweak_curve(a20, b20, levels, pivot)
        assert lib.rt_tone(array(a20), array(b20), pivot, c, h, s, out33) == 0
        assert bytes(out33) == expected
        tones += 1
    assert lib.rt_tone(array(stock[0]), array(stock[1]), pivot, 3, 0, 0, out33) == -1
    report = {"tone_comparisons": tones, "colour_comparisons": colours, "byte_exact": True,
              "synthetic_clamp_count": 48, "invalid_level_rejected": True,
              "C_source_lines": len((r.HERE / "tweak_int.c").read_text().splitlines()),
              "header_lines": len((r.HERE / "tweak_int.h").read_text().splitlines()),
              "C_source_sha256": r.sha(r.HERE / "tweak_int.c"),
              "scope": "host clang/ctypes only; no M32R build or camera execution"}
    r.dump(folder / "port_result.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
