"""Format experiment on official instructions, not a product implementation.

The synthetic H05 selector chooses only an experimental detail table. It does
not model or validate resident ownership. Native conversion and row drawing
run unchanged up to the existing glyph submission boundary.
"""
from pathlib import Path
import json
import struct
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT, OUT, file_sha, native_modules, save, sha

ARENA = 0x20680000
FONT_SHA = 'c9271288f8d395296623a3fe5358b2d83dec8730a89ed138a48ff8a2e8f14a5a'


def resources(image):
    path = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch4'
    raw = path.read_bytes()
    assert sha(raw) == FONT_SHA
    u32 = lambda at: int.from_bytes(raw[at:at+4], 'big')
    entries = {}
    for at in range(512+u32(512), len(raw)-31, 32):
        name = raw[at:at+24].split(b'\0')[0]
        if not name:
            break
        entries[name.decode('ascii')] = (512+u32(at+24), u32(at+28))
    start, size = entries['font_ctbl_00.res']
    font = raw[start:start+size]
    assert int.from_bytes(font[:4], 'big') == 1
    metrics = 8+4*int.from_bytes(font[4:8], 'big')+128
    assert metrics == 180 and len(font) == metrics+31*1024
    codes = image.bytes_at(0x2023bc6f, 60)+image.bytes_at(0x2023bcab, 34)
    mappings = {}
    for language in range(10):
        upper = int.from_bytes(image.bytes_at(0x202224e0+4*language, 4), 'big')
        lower = int.from_bytes(image.bytes_at(0x2022250c+4*language, 4), 'big')
        glyphs = struct.unpack('>60H', image.bytes_at(upper, 120))+struct.unpack(
            '>34H', image.bytes_at(lower, 68))
        mappings[language] = dict(zip(codes, glyphs))
    return font, metrics, mappings, dict(path=str(path.relative_to(ROOT)),
        sha256=FONT_SHA, resource='font_ctbl_00.res', file_offset=start, bytes=size,
        font_sha256=sha(font), metrics_offset=metrics)


def expected(text, mapping):
    return b''.join(struct.pack('>H', mapping[c]) for c in text.encode('ascii'))+b'\0'


def encoded_at(h, address, limit=96):
    if not address:
        return b''
    result = bytearray()
    for offset in range(0, limit, 2):
        first = h.b.read(address+offset, 1)
        if first == b'\0':
            return bytes(result)+b'\0'
        result.extend(h.b.read(address+offset, 2))
    raise ValueError('glyph terminator missing')


def main():
    image_loader, _, harness = native_modules()
    h = harness.Harness(body=image_loader.OFFICIAL)
    h.quiet_trace = True
    h.b.map(ARENA, bytes(0x10000))
    font, metrics, mappings, resource = resources(h.image)
    converted, draws, tables, native_widths = [], [], [], []
    selection = {'table': 0}
    phase = {'name': 'setup'}
    known = {}

    def select(b):
        if selection['table']:
            b.set_reg('r2', selection['table'])
            b.set_reg('pc', 0x201febec)
        return False

    def submitted(b):
        style = b.get_reg('r5')
        kind = h.u(style+4, 1)
        pointer = h.u(style+8)
        if kind == 8 and pointer:
            record = dict(phase=phase['name'], style=hex(style), pointer=hex(pointer),
                x=h.u(style, 2), y=h.u(style+2, 2), kind=kind,
                caller=hex(b.get_reg('r14')))
            try:
                data = encoded_at(h, pointer)
                record.update(encoded_sha256=sha(data), text=known.get(data))
            except Exception as exc:
                record['read_error'] = str(exc)
            draws.append(record)
        return False

    h.b.add_breakpoint(0x201febe4, select)
    h.b.breakpoints[0x201d7170].insert(0, submitted)
    h.prepare_menu()
    h.leave_other_list()
    h.open_image_settings()

    # Populate only the existing font-resource model from the genuine metrics
    # resource. Keep the native width routine, including its glyph parser.
    h.b.write(0x205cc84c, font[metrics:])
    for group in range(1, 32):
        h.put(0x205c2c88+4*group, 0x205cc84c+1024*(group-1))
    h.b.breakpoints.pop(0x201d74a8)
    for address in (0x201fed98, 0x201fee18, 0x201feed4):
        def measured(b, address=address):
            native_widths.append(dict(phase=phase['name'], return_pc=hex(address),
                                      width=b.get_reg('r0')))
            return False
        h.b.add_breakpoint(address, measured)

    texts = ('DISP: Tweak', 'DISP:Tw', 'DISP', 'C01', 'C02')
    for setting in range(11):
        h.invoke(0x201dc174, (setting,))
        language = h.invoke(0x201dc180)
        assert language == (1 if setting == 10 else setting)
        for index, text in enumerate(texts):
            src, dst = ARENA+0x20, ARENA+0x100+96*index
            h.b.write(src, text.encode('ascii')+b'\0')
            h.b.write(dst, b'\xa5'*96)
            h.invoke(0x201d73e0, (src, len(text), dst, language))
            want = expected(text, mappings[language])
            actual = encoded_at(h, dst)
            assert actual == want, (language, text, actual.hex(), want.hex())
            assert h.b.read(dst+len(want), 1) == b'\xa5'
            known[actual] = text
            glyphs = [mappings[language][c] for c in text.encode('ascii')]
            advances = [int.from_bytes(font[metrics+1024*((g>>8)-1)+4*(g&255)+2:
                metrics+1024*((g>>8)-1)+4*(g&255)+4], 'big') for g in glyphs]
            assert all(a == 12 for a in advances)
            converted.append(dict(language_setting=setting, language_index=language,
                text=text, ascii_bytes=len(text),
                glyph_bytes=len(want), encoded_sha256=sha(want),
                advance_sum=sum(advances), conservative_width=sum(advances)+2))

    # Use language index 1 for record experiments. Converter output remains in
    # host-owned arena; the selector is explicitly a model, not a DAT change.
    language = 1
    for index, text in enumerate(texts):
        src, dst = ARENA+0x20, ARENA+0x100+96*index
        h.b.write(src, text.encode('ascii')+b'\0')
        h.invoke(0x201d73e0, (src, len(text), dst, language))
        h.put(ARENA+0x800+4*index, dst)
    table = ARENA+0x1000
    selection['table'] = table
    for field in (0, 8):
        h.b.write(table, bytes(16*12))
        for row in range(7):
            h.put(table+row*12+field, ARENA+0x800)
        phase['name'] = 'record_field_'+str(field)
        before = len(draws)
        h.invoke(0x201fd360, (2, 0x2022f71c, 0), max_steps=400000)
        found = [x for x in draws[before:] if x.get('text') == texts[0]]
        assert len(found) == 1, found
        tables.append(dict(field=field, submissions=found))

    layouts = []
    for flag in (0, 1):
        h.put(0x205d444c, flag)
        for index in (0, 1):
            text = texts[index]
            h.b.write(table, bytes(16*12))
            for row in range(7):
                h.put(table+row*12, ARENA+0x800+4*index)
            phase['name'] = 'layout_'+str(flag)+'_'+str(index)
            start_draw, start_width = len(draws), len(native_widths)
            h.invoke(0x201fd360, (2, 0x2022f71c, 0), max_steps=400000)
            found = [x for x in draws[start_draw:] if x.get('text') == text]
            widths = native_widths[start_width:]
            assert len(found) == 1 and len(widths) == 1, (found, widths)
            width = widths[0]['width']
            right = 640 if flag else 320
            layouts.append(dict(text=text, display_flag=flag, x=found[0]['x'],
                y=found[0]['y'], native_width=width, edge=found[0]['x']+width,
                right=right, fits=found[0]['x']+width <= right))
    h.put(0x205d444c, 0)

    # Same record is read again on a later render. Replace only its reference
    # slot with another complete glyph string; never overwrite a live string.
    h.b.write(table, bytes(16*12))
    cursor = h.u(0x2022f726, 1)
    row = cursor-1
    ref = ARENA+0x800+4*3
    h.put(table+12*row, ref)
    phase['name'] = 'live_ref_C01'
    before = len(draws)
    h.invoke(0x201fd360, (2, 0x2022f71c, 0), max_steps=400000)
    assert any(x.get('text') == 'C01' for x in draws[before:])
    h.put(ref, ARENA+0x100+96*4)
    phase['name'] = 'live_ref_C02'
    before = len(draws)
    h.invoke(0x201fd360, (2, 0x2022f71c, 0), max_steps=400000)
    assert any(x.get('text') == 'C02' for x in draws[before:])

    raw = dict(conversions=converted, draws=draws, table_experiments=tables,
               native_widths=native_widths, layouts=layouts,
               calls=h.calls, stub_hits=h.stub_hits)
    save('local/text-probe-raw.json', raw)
    save('text-probe.json', dict(status='PASS_NATIVE_SUBMISSION', body=h.image.sha256,
        resource=resource, conversions=converted, table_experiments=tables,
        native_width_measurements=layouts, native_width_function_unmodified=True,
        font_resource_model='Genuine font_ctbl_00 metrics loaded into native font globals.',
        live_reference_observed=True, native_ui_hand_seeded=False,
        experimental_details_hand_constructed=True, h05_selector_is_model=True,
        evidence_scope='Official converter and row renderer up to modeled glyph_draw. '
            'No pixel rasterization, LCD, resident ownership, DAT publication, or lifetime acceptance.'))
    print('PASS', len(converted), 'native conversions;', len(tables), 'record fields;',
          'live reference re-read')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        save('text-probe-failure.json', dict(status='FAIL', traceback=traceback.format_exc()))
        raise
