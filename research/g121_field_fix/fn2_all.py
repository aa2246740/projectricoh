"""Check four Fn2 parameters at every communication and preview boundary."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save, sha
from ui_trace_scope import touches_ui, scope_records

n, ux, m, fr = nc.n, nc.ux, nc.m, nc.fr
PARAMETERS = ('contrast', 'saturation', 'highlight', 'shadow')

def unit_state(h, p):
    directory = m.u32(p.dat, 156) + 64 * m.INDEX[p.unit]
    mapping = p.dat[m.u32(p.dat, directory + 12):][:152]
    rows = []
    for i in range(9):
        row = mapping[32+12*i:44+12*i]
        address, size = m.u32(row, 0), m.u16(row, 4)
        data = bytes((p.rpc.half(at & ~1) >> (0 if at & 1 else 8)) & 255
                     for at in range(address, address+size))
        rows.append(dict(address=hex(address), bytes=size, data_hex=data.hex(), sha256=sha(data)))
    base = fr.u32(h, 0x200c0dac)
    return dict(rows=rows, T=p.rpc.t, mode=h.u(base+0x36e, 1),
                wb=list(h.b.read(base+0x6dd, 2)))

def run(unit):
    n.configure(unit, 'fn2-four-parameters')
    h, p, w = m.boot(unit)
    m.published(h, p, w)
    nc.move_to(h, p, 5)
    ux.need(fr.native(h, 0x202be220))
    layout = json.loads((n.OUT/'local/layout/current-adapter-layout.json').read_text())
    base = p.symbol_pc('n')
    all_rows = []
    for parameter, name in enumerate(PARAMETERS):
        assert h.u(base+layout['panel.parameter'], 1) == parameter
        assert list(h.b.read(base+layout['panel.draft'], 4)) == [0, 0, 0, 0]
        old = unit_state(h, p)
        context = nc.stamp(h, p)
        def reference(record):
            at = len(p.rpc.log)
            preview = h.stub_hits.get('preview', 0)
            ux.need(fr.move_key(h, 0x20))
            calls = p.rpc.log[at:]
            values = list(h.b.read(base+layout['panel.draft'], 4))
            assert values == [int(i == parameter) for i in range(4)]
            record.update(parameter=name, old=old, new=unit_state(h, p), values=values,
                          RPC=len(calls), W=sum(c['cmd'] == 22 for c in calls),
                          preview=h.stub_hits.get('preview', 0)-preview,
                          rpc_log=calls, file_mutations=m.no_writes(p))
            assert record['old'] != record['new'] and record['preview'] == 1
        reference_row = nc.case('fn2-reference-'+unit+'-'+name, reference, context)
        points = list(range(1, reference_row['RPC']+1)) + ['preview']
        cases = []
        for point in points:
            def check(record, point=point):
                original = p.rpc.call
                count = 0
                switched = False
                writes = []
                other = None
                at = len(p.rpc.log)
                def switch():
                    nonlocal switched, other
                    other = nc.other_list(h)
                    assert other['activity'] == 7 and other['overlay'] == 21
                    switched = True
                def rpc(command, value):
                    nonlocal count
                    count += 1
                    if count == point:
                        switch()
                    return original(command, value)
                def preview(b):
                    if point == 'preview' and not switched:
                        switch()
                    return False
                def watch(event):
                    if switched and touches_ui(event):
                        writes.append(dict(address=hex(event.address), pc=hex(event.pc),
                                           data_hex=event.data.hex()))
                h.b.add_write_trace(0, 2**32, watch)
                h.b.breakpoints[0x202d6f38].insert(0, preview)
                p.rpc.call = rpc
                result = ux.need(fr.move_key(h, 0x20))
                p.rpc.call = original
                assert switched, ('Boundary not reached', point, count)
                actual = unit_state(h, p)
                complete = [label for label in ('old', 'new') if actual == reference_row[label]]
                after = ux.snap(h, p)
                record.update(unit=unit, parameter=name, point=point, seen=count,
                    result=result, other_menu=other, after=after, complete=complete,
                    actual=actual, writes_after_switch=writes, scope=scope_records(),
                    rpc_log=p.rpc.log[at:], file_mutations=m.no_writes(p))
                assert not writes and len(complete) == 1
                assert after['native_activity'] == 7 and after['native_overlay'] == 21
                assert after['cursor'] == other['cursor'] and after['dot_row'] == other['dot']
            record = nc.case('fn2-switch-'+unit+'-'+name+'-'+str(point), check, context)
            cases.append(dict(point=point, complete=record['complete'],
                              late_writes=len(record['writes_after_switch'])))
        all_rows.append(dict(parameter=name, reference=reference_row, points=cases))
        ux.need(fr.native(h, 0x202be220))
    save('native/fn2-four-parameters-'+unit+'.json',
         dict(status='PASS', unit=unit, dat_sha256=sha(m.DAT.read_bytes()),
              parameters=all_rows, final_recipe_checked=True))
    print('PASS four parameters', unit, sum(len(x['points']) for x in all_rows), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('unit', choices=('50mm', '28mm', 'mount'))
    run(parser.parse_args().unit)
