"""Run unchanged g158 C parsers and knob APIs against the proposed Acros rebase.

The test uses in-memory negative parser fixtures, never a generation159 DAT.
The accepted input is the owner's g158 DAT, verified by SHA in preflight.json.
"""
from pathlib import Path
import argparse
import ctypes as T
import json
import struct
import subprocess
import sys
import types
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def build_host(tag):
    module = C.load(C.ROOT / "research/v39_g153/format_checks.py", "g159_host_parsers")
    module.ROOT = C.ROOT
    module.PRODUCT = C.PRODUCT
    module.TMP = C.LOCAL / "checks" / tag / "host"
    module.HERE = C.LOCAL / "checks" / tag
    module.subprocess = types.SimpleNamespace(run=lambda argv, **kw: subprocess.run([*argv, "-DRV_HOST"], **kw))
    (module.HERE / "evidence").mkdir(parents=True, exist_ok=True)
    library = module.library()
    library.kv_data_open.argtypes = (T.c_void_p, T.c_size_t, T.c_void_p)
    library.kv_data_open.restype = T.c_int
    library.kv_data_request.argtypes = (T.c_void_p, T.c_uint, T.c_uint, T.c_void_p, T.c_void_p)
    library.kv_data_request.restype = T.c_int
    library.kv_data_find.argtypes = (T.c_void_p, T.c_uint, T.c_uint, T.c_uint, T.c_void_p)
    library.kv_data_find.restype = T.c_int
    library.kv_apply_work.argtypes = (T.c_void_p, T.c_void_p, T.c_void_p, T.c_void_p, T.c_void_p, T.c_void_p)
    library.kv_apply_work.restype = T.c_int
    sources = ("src/firmware/card_container_v2/gate.c", "src/firmware/card_container_v2/semantic.c",
               "src/firmware/card_container_v2/common.c", "kv2/kv_data.c", "kv2/kv_ui.c", "kv2/kv_math.c",
               "fx_pool.c", "ui_v2_data.c", "memory.c", "src/firmware/engine/core/eng_core.c", "adapter.c")
    return module, library, {name: C.sha((C.PRODUCT / name).read_bytes()) for name in sources}


class View(T.Structure):
    _fields_ = [("bytes", T.c_void_p), ("length", T.c_uint32)]


class Item(T.Structure):
    _fields_ = [("control", T.c_uint8), ("points", T.c_uint8), ("cap", T.c_uint8), ("step", T.c_uint8),
                ("minimum", T.c_int16), ("maximum", T.c_int16), ("default", T.c_int16), ("offset", T.c_uint32)]


def controls(lib, view, unit, slot):
    result = []
    for control in range(10):
        item = Item()
        if lib.kv_data_find(T.byref(view), unit, slot, control, T.byref(item)) == 0:
            result.append(dict(control=control, minimum=item.minimum, maximum=item.maximum,
                               default=item.default, points=item.points, step=item.step))
    return result


def request(lib, view, unit, slot, levels):
    data = (T.c_int16 * 10)(*levels)
    out = T.create_string_buffer(bytes([0xA5]) * 52, 52)
    result = lib.kv_data_request(T.byref(view), unit, slot, data, out)
    assert result == 0 or out.raw == bytes([0xA5]) * 52
    return result, out.raw


def promoted_acros(raw, unit):
    area, _ = C.D.effect_area(raw)
    choices = []
    for i in range(C.D.u16(raw, area + 10)):
        at = area + 32 + 32 * i
        descriptor = raw[at:at + 32]
        if descriptor[18] >> unit & 1 and descriptor[20:].split(b"\0")[0] == b"Acros":
            choices.append((at, descriptor))
    assert len(choices) == 1
    at, descriptor = choices[0]
    original = C.D.expand_effect(raw, (at - area - 32) // 32)
    assert original[0] == 3 and original[1] == 1 and original[114] >= 128
    entry = bytearray(original)
    entry[1] = 7
    entry[445:447] = bytes(2)
    entry[379:412] = entry[82:115]
    entry[412:445] = entry[82:115]
    entry = bytearray(C.D.refresh_entry(entry))
    return at, descriptor, original, entry


def fixture(raw, unit, base):
    at, descriptor, original, entry = promoted_acros(raw, unit)
    entry[0] = base
    entry[4:8] = struct.pack(">I", C.D.content_crc(entry, descriptor[18]))
    out = bytearray(raw)
    out[at] = base
    out[at + 1] = 7
    out[at + 2:at + 4] = bytes(2)
    out[at + 4:at + 8] = entry[4:8]
    # Both extra curves alias the existing shared curve, without new pool rows.
    out[at + 14] = descriptor[9]
    out[at + 15] = descriptor[9]
    area, length = C.D.effect_area(out)
    struct.pack_into(">I", out, area + 24, C.D.crc(out[area + 32:area + length]))
    struct.pack_into(">I", out, area + 28, C.D.crc(out[area:area + 28]))
    out = C.D.seal(out)
    actual = C.D.expand_effect(out, (at - area - 32) // 32)
    assert actual == entry
    assert actual[115:272] == original[115:272], "C080 and both C100 halves unchanged"
    assert actual[82:115] == original[82:115]
    assert actual[379:412] == actual[412:445] == actual[82:115]
    return out, original, bytes(entry)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    assert args.tag and all(c.isascii() and (c.isalnum() or c in "-_") for c in args.tag)
    C.setup()
    result_dir = C.LOCAL / "checks" / args.tag
    assert not result_dir.exists(), "Use a new tag; preserve prior receipts."
    C.gate("Acros-actual-C-equivalence-witness")
    module, lib, source_hashes = build_host(args.tag)
    (result_dir / "driver.py").write_bytes(Path(__file__).read_bytes())
    expected_DAT = dict(test="6a40262c3fc5b94e7152012c655f5c7d2dc98bf6186cf3e80d2429b76f45fcee",
                        release="756d5840da9d0393f29411a4f8f61c7e2bb88fb546c814b316982ca8c7cb24f6")
    rows = []
    for profile in ("test", "release"):
        raw = C.baseline_dat(profile).read_bytes()
        assert C.sha(raw) == expected_DAT[profile]
        knob = raw[C.D.u32(raw, 204) + 3392:C.D.u32(raw, 204) + 11296]
        assert len(knob) == 7904
        pinned = T.create_string_buffer(knob)
        view = View()
        assert lib.kv_data_open(pinned, len(knob), T.byref(view)) == 0
        for unit in range(3):
            assert lib.check_dat(raw, len(raw), module.trust(raw), unit) == 0
            old_controls = controls(lib, view, unit, 3)
            assert {x["control"] for x in old_controls} == {1, 2, 3, 4, 9}
            levels = [100] + [0] * 9
            levels[9] = 1
            old_result, old_request = request(lib, view, unit, 3, levels)
            assert old_result == 0
            old_slot = C.D.expand(raw, unit, 3)
            old_at, _, acros, _ = promoted_acros(raw, unit)
            area, _ = C.D.effect_area(raw)
            tri = []
            for index in range(C.D.u16(raw, area + 10)):
                descriptor = raw[area + 32 + 32 * index:area + 64 + 32 * index]
                if descriptor[18] >> unit & 1 and descriptor[20:].split(b"\0")[0] == b"Tri-X 400":
                    tri.append(C.D.expand_effect(raw, index))
            assert len(tri) == 1 and tri[0][0] == 3 and tri[0][1] == old_slot[1] == acros[1] == 1
            candidates = []
            for base in (1, 2, 3, 5, 6, 7, 8):
                base_record = C.D.expand(raw, unit, base)
                # The requested layout changes slots05-08 to flags7. Slots01-04
                # remain byte-identical to g158, including slot03 flags1.
                planned_flags = base_record[1] if base < 5 else 7
                found = controls(lib, view, unit, base)
                new_result, _ = request(lib, view, unit, base, levels)
                amount_levels = [0] * 10
                old_amount, _ = request(lib, view, unit, 3, amount_levels)
                new_amount, _ = request(lib, view, unit, base, amount_levels)
                assert old_amount == -1
                candidates.append(dict(base=base, requested_base_flags=planned_flags,
                    flags_compatible=planned_flags == 7,
                    controls=found, old_filter_plus1_result=old_result, rebased_filter_plus1_result=new_result,
                    old_amount0_result=old_amount, rebased_amount0_result=new_amount,
                    controls_equal=found == old_controls,
                    equivalent=planned_flags == 7 and found == old_controls and new_result == 0))
            assert not any(x["equivalent"] for x in candidates)
            invalid, _, _ = fixture(raw, unit, 3)
            rejected = lib.check_dat(invalid, len(invalid), module.trust(invalid), unit)
            assert rejected != 0, "Actual C parser must reject flags7 Acros on fixed flags1 slot03"
            valid, _, promoted = fixture(raw, unit, 6)
            accepted = lib.check_dat(valid, len(valid), module.trust(valid), unit)
            assert accepted == 0, "Control fixture: flags7 Acros on existing flags7 slot06 parses"
            output = T.create_string_buffer(552)
            stats = T.create_string_buffer(28)
            work = T.create_string_buffer(2288)
            stock = C.D.expand(raw, unit, 4)
            assert lib.kv_apply_work(stock, acros, old_request, output, stats, work) == 0
            assert output.raw[216:222] != acros[216:222], "Filt+1 must change the actual Y matrix"
            witness_path = result_dir / "witness" / profile / C.UNITS[unit]
            witness_path.mkdir(parents=True, exist_ok=True)
            (witness_path / "old-Acros.record552").write_bytes(acros)
            (witness_path / "old-Acros-Filt-plus1.record552").write_bytes(output.raw)
            (witness_path / "proposed-flags7-base06.record552").write_bytes(promoted)
            row = dict(profile=profile, unit=C.UNITS[unit], status="FAIL_BEHAVIOR_EQUIVALENCE",
                       DAT_sha256=C.sha(raw), old_base=3, old_flags=1, old_controls=old_controls,
                       retained_03_sha256=C.sha(old_slot), old_Acros_sha256=C.sha(acros),
                       HC_BW_TriX_Acros_group=dict(all_flags=1, actual_base=3,
                           TriX_sha256=C.sha(tri[0]), TriX_still_present_in_counterexample=True,
                           original03_and_TriX_and_Acros_left_unmodified=True),
                       original_Acros_descriptor_offset_is_private=True,
                       filter_plus1=dict(levels=levels, old_result=0, old_request_hex=old_request.hex(),
                                         changes_Y_matrix=True, result_sha256=C.sha(output.raw)),
                       actual_C_parser=dict(flags7_on_fixed03=rejected, flags7_on_existing06=accepted),
                       all_permitted_bases=candidates,
                       default_effective_rows=dict(curve_equal=True, matrix_equal=True, C080_equal=True),
                       proposed_pipeline_RGB_and_DE00=None,
                       metric_reason="Behavior fails before rendering: a previously legal Filt request is rejected. This is not an output quantization difference.",
                       Acros_cannot_keep_existing_range_on_any_allowed_flags7_base=True)
            rows.append(row)
    result = dict(status="FAIL_BEHAVIOR_EQUIVALENCE", profile_unit_cases=len(rows), rows=rows,
                  actual_unmodified_C_sources=source_hashes,
                  parser_host_sha256=C.sha((result_dir / "host/parsers.dylib").read_bytes()),
                  driver_sha256=C.sha((result_dir / "driver.py").read_bytes()),
                  generation159_DAT_created=False, generation159_packages_created=False,
                  no_engine_or_g158_modification=True,
                  decision="Do not package under the owner's explicit failure rule.")
    C.save(result_dir / "equivalence.json", result)
    print(json.dumps(dict(status=result["status"], actual_C_cases=len(rows),
                          failure="Acros Filt+1 is valid on03 and rejected on every allowed flags7 base",
                          generation159_DAT_created=False), ensure_ascii=False))


if __name__ == "__main__":
    main()
