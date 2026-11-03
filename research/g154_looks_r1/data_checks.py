"""直接调用 g154 C 查询、数学和结构校验，核对最终 DAT 的完整条目。"""
from pathlib import Path
import ctypes as C
import struct
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from reference import Reference, user_record


class Section(C.Structure):
    _fields_ = [('offset', C.c_uint32), ('length', C.c_uint32)]


class GateView(C.Structure):
    _fields_ = [('bytes', C.c_void_p), ('length', C.c_uint32), ('build_number', C.c_uint32),
                ('entry_offset', C.c_uint32), ('bss_bytes', C.c_uint32), ('sections', Section * 7),
                ('param_slots', C.c_uint16), ('record_bytes', C.c_uint16),
                ('selected_module', C.c_uint8), ('executable', C.c_uint8), ('semantic', C.c_uint8)]


def view(lib, raw, trust, unit):
    memory = C.create_string_buffer(raw)
    pin = C.create_string_buffer(trust)
    gate, parsed = GateView(), GateView()
    lib.gxr2_gate_validate.argtypes = [C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p,
                                     C.c_uint, C.POINTER(GateView)]
    lib.gxr2_semantic_validate.argtypes = [C.POINTER(GateView), C.c_void_p, C.POINTER(GateView)]
    assert lib.gxr2_gate_validate(memory, len(raw), pin, C.byref(pin, 80 + 48 * unit), 0, C.byref(gate)) == 0
    assert lib.gxr2_semantic_validate(C.byref(gate), pin, C.byref(parsed)) == 0
    assert parsed.selected_module == unit and parsed.semantic == 1
    return parsed, memory, pin


def full_entries(ref, raw, baseline, support):
    lib = ref.lib
    lib.gxr2_expand.argtypes = [C.POINTER(GateView), C.c_uint, C.c_uint, C.c_void_p]
    lib.fx_expand.argtypes = [C.POINTER(GateView), C.c_uint, C.c_void_p]
    effects = selected()
    folder = PACKAGE / 'local/evidence/full-552'
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    for unit in range(3):
        parsed, memory, pin = view(lib, raw, support.trust(raw), unit)
        old_view, old_memory, old_pin = view(lib, baseline, support.trust(baseline), unit)
        for kind, number in [('builtin', i) for i in range(1, 9)] + [('look', i) for i in range(1, 19)]:
            out = C.create_string_buffer(b'\xa5' * 552, 552)
            if kind == 'builtin':
                status = lib.gxr2_expand(C.byref(parsed), unit, number, out)
                expected = expand(raw, unit, number)
            else:
                status = lib.fx_expand(C.byref(parsed), number - 1, out)
                expected = expand_effect(raw, number - 1)
                supplied = bytearray(bytes.fromhex(effects[number - 1]['entry_hex']))
                # GXFX content identity replaces the base recipe identity; every other byte stays intact.
                struct.pack_into('>I', supplied, 4, content_crc(supplied, effects[number - 1]['mask']))
                assert expected == bytes(supplied), (unit, number, 'fitted input differs')
            assert status == 0 and out.raw == expected, (unit, kind, number)
            math_status, computed = ref.compute(raw, unit, expected, [100] + [0] * 9)
            assert math_status == 0 and computed == expected, (unit, kind, number, 'default C math differs')
            old_equal = None
            if kind == 'builtin' or number <= 10:
                previous = C.create_string_buffer(b'\xa5' * 552, 552)
                old_status = (lib.gxr2_expand(C.byref(old_view), unit, number, previous) if kind == 'builtin'
                              else lib.fx_expand(C.byref(old_view), number - 1, previous))
                assert old_status == 0 and previous.raw == out.raw
                old_equal = True
            name = f'{unit}-{kind}-{number}.bin'
            (folder / name).write_bytes(out.raw)
            records.append(dict(unit=unit, kind=kind, number=number, bytes=552,
                sha256=sha(out.raw), original_g154_equal=old_equal, C_default_math_equal=True,
                file=str((folder / name).relative_to(ROOT))))
        for number in range(1, 4):
            slot, levels, name = user_record(raw, number)
            old_slot, old_levels, old_name = user_record(baseline, number)
            assert (slot, levels, name) == (old_slot, old_levels, old_name)
            status, computed = ref.compute(raw, unit, expand(raw, unit, slot), levels)
            old_status, previous = ref.compute(baseline, unit, expand(baseline, unit, slot), levels)
            assert status == old_status == 0 and computed == previous
            path = folder / f'{unit}-user-{number}.bin'
            path.write_bytes(computed)
            records.append(dict(unit=unit, kind='user', number=number, name=name,
                bytes=552, sha256=sha(computed), original_g154_equal=True, file=str(path.relative_to(ROOT))))
    assert len(records) == 87
    return records


def formal(ref, raw, support):
    lib = ref.lib
    pinned = C.create_string_buffer(support.trust(raw))
    for unit in range(3):
        assert lib.check_dat(C.create_string_buffer(raw), len(raw), pinned, unit) == 0
    mutations = support.variants(raw)
    # That old fixture writes entry 11, which is occupied in this variant.
    mutations.pop('fx-unused-entry')
    at, size = effect_area(raw)
    curve_end = at + 32 + 32 * 18 + 18 * 33
    altered = bytearray(raw)
    altered[curve_end] = 1
    mutations['fx-curve-padding'] = support.fix_effects(altered)
    altered = bytearray(raw)
    altered[-1] ^= 1
    mutations['DAT-payload-CRC'] = bytes(altered)
    altered = bytearray(raw)
    altered[80] ^= 1
    mutations['DAT-header-CRC'] = bytes(altered)
    rejected = []
    for name, data in mutations.items():
        result = lib.check_dat(C.create_string_buffer(data), len(data), pinned, 0)
        assert result != 0, name
        rejected.append(dict(name=name, result=result, sha256=sha(data)))
    windows = 0
    for count in range(1, 50):
        for current in range(count):
            for top in range(50):
                out = (C.c_uint8 * 2)(165, 165)
                assert lib.check_window(count, current, top, out) == 0
                assert out[0] + out[1] == current and out[1] < 8 and out[0] <= max(0, count - 8)
                windows += 1
    out = (C.c_uint8 * 2)(165, 165)
    assert lib.check_window(50, 49, 42, out) == -1 and list(out) == [165, 165]
    return dict(valid_units=3, rejected=rejected, window_cases=windows, above49_rejected=True)


def studio(raw):
    path = ROOT / 'studio/src/gxr_studio/camdata/datcodec.py'
    digest = sha(path.read_bytes())
    codec = load(path, 'g154_looks_readonly_studio_datcodec')
    parsed = codec.parse(raw)
    assert parsed.generation == 154 and len(parsed.looks) == 18 and len(parsed.users) == 3
    assert codec.pack(parsed) == raw
    for unit in range(3):
        assert all(parsed.entry_of(unit, slot) == expand(raw, unit, slot) for slot in range(1, 9))
    assert [look.entry for look in parsed.looks] == [expand_effect(raw, i) for i in range(18)]
    assert sha(path.read_bytes()) == digest
    return dict(status='PASS', generation=154, looks=18, users=3, byte_identical_roundtrip=True,
                datcodec_sha256=digest, registration_change_required=False, scope='codec API only')


def main():
    guard()
    started = time.monotonic()
    raw = (PACKAGE / 'local/SD_ROOT/GXRCE.DAT').read_bytes()
    baseline = (BASE_PACKAGE / 'local/SD_ROOT/GXRCE.DAT').read_bytes()
    support = load(ROOT / 'research/v39_g153/format_checks.py', 'g154_looks_formal_support')
    ref = Reference(154)
    result = dict(status='PASS', dat_sha256=sha(raw), backend='original g154 host C',
        effects=strict_effects(raw), format=formal(ref, raw, support),
        full_entries=full_entries(ref, raw, baseline, support), studio=studio(raw))
    result['seconds'] = time.monotonic() - started
    save(HERE / 'evidence/data-checks.json', result)
    print(json.dumps(dict(status='PASS', full552=len(result['full_entries']),
        rejected=len(result['format']['rejected']), window_cases=result['format']['window_cases'],
        studio_roundtrip=True, seconds=result['seconds'])))


if __name__ == '__main__':
    main()
