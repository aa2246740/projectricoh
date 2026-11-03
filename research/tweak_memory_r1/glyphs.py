"""Check eight actual native label buffers with the original text converter."""
import argparse
import json
import os
import re
import struct
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime as R
from runtime import ROOT, TEMP, load_snapshot, symbols, layout, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--name', required=True)
    a = p.parse_args()
    saved = load_snapshot(a.source)
    state = saved['cpu']
    def mem(at, n):
        for base, data, _ in state['regions']:
            if base <= at and at+n <= base+len(data):
                return data[at-base:at-base+n]
        raise ValueError(hex(at))
    def u(at, n=4):
        return int.from_bytes(mem(at, n), 'big')
    dat = R.snapshot_dat(saved) if hasattr(R,'snapshot_dat') else Path(saved['dat_path']).read_bytes()
    assert sha(dat)==saved['dat_sha256']
    base = u(0x20054770)-int.from_bytes(dat[132:136], 'big')
    offsets, syms = layout(a.engine), symbols(a.elf)
    ui = base+syms['n']
    text = mem(ui+offsets['n.ui.text'], 8*14)
    assert u(0x2022f5ac, 1) == 8
    sys.path.insert(0, str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    backend = os.environ['GXR_HARNESS_BACKEND']
    PB.CACHE = TEMP/'glyph-check'/backend/a.name
    Backend = PB.PurePythonBackend if backend == 'python' else PB.PythonBackend
    if backend == 'c':
        assert getattr(Backend, 'native_api', None) == 5
    b = Backend()
    for address, data, writable in state['regions']:
        b.map(address, data, writable)
    regs = state['registers']
    b.set_reg('psw', regs['psw'])
    for i in range(16):
        b.set_reg('r'+str(i), regs['r'+str(i)])
    for key in ('spi', 'spu', 'bpc', 'bbpc', 'evb'):
        b.set_reg(key, regs[key])
    b.map(0x10000000, bytes(8192), True)
    stop = b.call(0x201dc180, [], 0x7ffffff0, 10000)
    assert stop.reason == 'return'
    language = b.get_reg('r0')
    rows = []
    table = u(0x2022f5a8)
    for i in range(8):
        ascii_text = text[14*i:14*(i+1)].split(b'\0', 1)[0]
        b.write(0x10000000, ascii_text+b'\0')
        b.write(0x10001000, bytes(128))
        for j, value in enumerate((0x10000000, len(ascii_text), 0x10001000, language), 4):
            b.set_reg('r'+str(j), value)
        stop = b.call(0x201d73e0, [], 0x7ffffff0, 300000)
        assert stop.reason == 'return', stop
        expected = b.read(0x10001000, 70).split(b'\0', 1)[0]
        glyph = u(u(table+4*i))
        actual = mem(glyph, 70).split(b'\0', 1)[0]
        assert actual == expected, (i, ascii_text, actual.hex(), expected.hex())
        rows.append(dict(row=i+1, text=ascii_text.decode('ascii'), glyphs=actual.hex(), equal=True))
    physical = u(ui+offsets['n.ui.physical'], 1)+1
    assert u(0x2022f726, 1) == u(0x205a2944, 1) == physical
    screen=u(ui+offsets['n.ui.screen'],1)
    displayed=[]
    if screen==2:
        labels=['Amt','Cont','High','Shad','Fade','Satu','Warm','Tint','Splt','Filt']
        values=struct.unpack('>10h',mem(ui+offsets['n.ui.levels'],20))
        for row in rows:
            match=re.fullmatch(r'(Amt|Cont|High|Shad|Fade|Satu|Warm|Tint|Splt|Filt)\s+([+-]?\d+)%?',row['text'].strip(' <>'))
            if match:
                control=labels.index(match[1]);actual=int(match[2]);assert actual==values[control]
                displayed.append(dict(control=control,label=match[1],displayed=actual,record_value=values[control]))
        assert displayed,'no numeric control rows were checked'
        if a.source.name.startswith('p1final-'):
            assert mem(u(0x200c0dac)+0xfd4+8,20)==mem(ui+offsets['n.ui.levels'],20)
    result = dict(status='PASS', backend=backend, layer='模拟器实测快照与原厂转换器指令复核',
        source_sha256=sha(a.source.read_bytes()), rows=rows, physical_selected=physical,
        selected_text=rows[physical-1]['text'], native_cursor_equal=True,
        screen=screen,actual_displayed_levels=displayed,dat_sha256=sha(dat),native_state_presets=[])
    out = HERE/'evidence'/(a.name+'-'+backend+'.json')
    assert not out.exists()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status='PASS', name=a.name, backend=backend, selected=result['selected_text'])))
    if a.source.name.startswith('p1final-') and a.source.name.endswith('-first-menu.pkl.z'):
        controls=a.source.with_name(a.source.name.replace('-first-menu.pkl.z','-final.pkl.z'))
        assert controls.exists()
        old=sys.argv
        try:
            sys.argv=[old[0],'--source',str(controls),'--engine',str(a.engine),'--elf',str(a.elf),
                '--name',a.name+'-controls']
            main()
        finally:sys.argv=old


if __name__ == '__main__':
    main()
