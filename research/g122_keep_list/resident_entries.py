"""Observe native H01 when a fixed-resident entry gate prevents DAT calls."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_cases as nc
from common import ROOT, save, sha

def run_unit(unit):
    n, ux, m, fr, pe = nc.n, nc.ux, nc.m, nc.fr, nc.pe
    n.configure(unit, 'resident-entry-gates')
    h, p, w = m.boot(unit)
    m.published(h, p, w)
    nc.move_to(h, p, 5)
    ux.need(fr.press(h, 0x2b))
    checkpoint = nc.stamp(h, p)
    fields = json.loads((ROOT / 'firmware/resident_v36/local/resident/target-layout.json').read_text())['RvRoot']['fields']
    base = pe.ROOT_ADDR
    records = []
    for condition in ('inflight', 'RF_BUSY', 'rv_check_code'):
        def execute(record, condition=condition):
            entries = [0]
            def entered(b):
                entries[0] += 1
                return False
            h.b.add_breakpoint(p.symbol_pc('ig_menu'), entered)
            flags = base + fields['flags']['offset']
            if condition == 'inflight':
                h.put(base + fields['inflight']['offset'], 1, 1)
            elif condition == 'RF_BUSY':
                h.put(flags, h.u(flags) | 8)
            else:
                address = base + fields['code_crc']['offset']
                h.put(address, h.u(address) ^ 1)
            h.parent()
            opened, _, error = fr.publish(h, p, w)
            ux.need(opened)
            assert error is None, error
            first = ux.snap(h, p)
            assert entries[0] == 0 and first['rows'] == 7
            if condition == 'rv_check_code':
                assert first['root']['state'] == 6 and first['root']['block'] == 0
                assert first['root']['check_failure'] == 5
            else:
                if condition == 'inflight':
                    h.put(base + fields['inflight']['offset'], 0, 1)
                else:
                    h.put(flags, h.u(flags) & ~8)
            h.parent()
            second, _, error = fr.publish(h, p, w)
            ux.need(second)
            assert error is None, error
            after = ux.snap(h, p)
            assert after['rows'] == (7 if condition == 'rv_check_code' else 8)
            assert entries[0] == (0 if condition == 'rv_check_code' else 1)
            record.update(unit=unit, condition=condition, dat_sha256=sha(p.dat), first=first,
                after_condition=after, DAT_H01_calls=entries[0], file_mutations=m.no_writes(p),
                fixture='Only private resident gate fields are varied. Native UI is built by official constructors.',
                scope='This proves the fixed resident boundary. It does not identify the camera first-open cause.')
        result = nc.case('resident-entry-' + unit + '-' + condition, execute, checkpoint)
        records.append(dict(condition=condition, first_rows=result['first']['rows'],
                            after_rows=result['after_condition']['rows'], DAT_H01_calls=result['DAT_H01_calls']))
    save('native/resident-entries-' + unit + '.json', dict(status='PASS', unit=unit,
        dat_sha256=sha(p.dat), cases=records, resident_modified=False))

if __name__ == '__main__':
    for name in ('50mm', '28mm', 'mount'):
        run_unit(name)
