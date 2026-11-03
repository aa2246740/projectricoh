"""Check first H01 publication while unit checks are temporarily unavailable."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_cases as nc
from common import OUT, save, sha

def main(unit):
    n, ux, m, fr, pe = nc.n, nc.ux, nc.m, nc.fr, nc.pe
    n.configure(unit, 'first-open')
    h, p, w = m.boot(unit)
    m.published(h, p, w)
    nc.move_to(h, p, 5)
    ux.need(fr.press(h, 0x2b))
    ux.matches(h, p, 5)
    checkpoint = nc.stamp(h, p)
    layout = json.loads((OUT / 'local/layout/current-adapter-layout.json').read_text())
    summaries = []
    for condition in ('communication', 'ready', 'settings_epoch_busy', 'ready_row_reset'):
        for entry in ('direction', 'disp', 'confirm'):
            label = 'first-open-' + unit + '-' + condition + '-' + entry
            def run(record, condition=condition, entry=entry):
                original = p.rpc.call
                before = ux.snap(h, p)
                menu_entries = [0]
                drawn = []
                def menu(b):
                    menu_entries[0] += 1
                    return False
                def draw(b):
                    drawn.append(dict(rows=h.u(0x2022f5ac, 1), cursor=h.u(0x2022f726, 1)))
                    return False
                h.b.add_breakpoint(p.symbol_pc('ig_menu'), menu)
                h.b.add_breakpoint(0x201ffb2c, draw)
                if condition.startswith('ready'):
                    p.ready = 0
                    ux.need(fr.native(h, 0x200935b4, (0,)))
                    if condition == 'ready_row_reset':
                        p.rpc.overlay.clear()
                        p.rpc.t = 2
                else:
                    if condition == 'settings_epoch_busy':
                        address = pe.ROOT_ADDR + 8 + 4 * 7
                        h.b.origin = 'model:explicit_epoch_transition'
                        h.b.write(address, struct.pack('>I', h.u(address) + 1))
                    def busy(command, value):
                        p.rpc.log.append(dict(cmd=command, value=value, page=p.rpc.page,
                                             result=-1, t=p.rpc.t, simulated=True))
                        return -1
                    p.rpc.call = busy
                h.parent()
                opened, _, error = fr.publish(h, p, w)
                ux.need(opened)
                assert error is None, error
                pending = ux.snap(h, p)
                record.update(unit=unit, condition=condition, retry_entry=entry,
                    dat_sha256=sha(p.dat), before=before, pending=pending, opened=opened,
                    first_H01_entries=menu_entries[0], drawn_during_first_open=list(drawn))
                assert menu_entries[0] == 1
                assert pending['rows'] == 8 and pending['cursor'] == pending['dot_row'] == h.u(0x205a2944, 1) == 5
                assert pending['W'] == before['W']
                assert h.u(p.symbol_pc('n') + layout['retry'], 1) == 1
                assert h.u(p.symbol_pc('n') + layout['failed'], 1) == 0
                assert drawn and all(x['rows'] == 8 for x in drawn), drawn
                p.rpc.call = original
                if condition.startswith('ready'):
                    p.ready = 1
                    ux.need(fr.native(h, 0x200935b4, (1,)))
                at = len(p.rpc.log)
                if entry == 'direction':
                    retried = ux.need(fr.move_key(h, 0x20, steps=30000000))
                    actual = ux.matches(h, p, 6)
                    assert h.u(0x2022f5ac, 1) == 8
                elif entry == 'disp':
                    retried = ux.need(fr.native(h, 0x202be220, steps=30000000))
                    actual = ux.matches(h, p, 5)
                    assert h.u(0x2022f5ac, 1) == 11
                else:
                    retried = ux.need(fr.press(h, 0x23, steps=30000000))
                    actual = ux.matches(h, p, 5)
                after = ux.snap(h, p)
                assert len(p.rpc.log) > at
                assert h.u(p.symbol_pc('n') + layout['failed'], 1) == 0
                record.update(retried=retried, after=after, actual=actual,
                    retry_RPC=len(p.rpc.log) - at, rpc_log=p.rpc.log,
                    file_mutations=m.no_writes(p), native_UI_built_by_official_constructors=True)
            result = nc.case(label, run, checkpoint)
            summaries.append(dict(case=label, retry_RPC=result['retry_RPC']))
    save('native/first-open-' + unit + '.json', dict(status='PASS', unit=unit,
        dat_sha256=sha(p.dat), cases=summaries,
        scope='Warm loaded session. Unit busy and row reset are explicit model conditions; no capture-completion message is supplied.'))
    print('PASS first H01 and deferred retry', unit, len(summaries), flush=True)

if __name__ == '__main__':
    main(sys.argv[1])
