"""Verify retained list and panel state through each pre-W retry entry."""
from pathlib import Path
import copy
import json
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_cases as nc
from common import OUT, save, sha

def main(unit):
    n, ux, m, fr, pe, v = nc.n, nc.ux, nc.m, nc.fr, nc.pe, nc.v
    n.configure(unit, 'keep-cases')
    h, p, w = m.boot(unit)
    m.published(h, p, w)
    layout = json.loads((OUT / 'local/layout/current-adapter-layout.json').read_text())
    checkpoint = nc.stamp(h, p)
    summaries = []
    quick='--quick' in sys.argv[2:]
    for panel in (False, True):
        for condition in ('settings_epoch', 'mode_epoch', 'communication', 'communication_three', 'ready', 'row_reset'):
            for entry in ('direction', 'disp', 'confirm'):
                if quick and not (condition=='communication' or
                    entry=='direction' and condition in ('communication_three','ready','settings_epoch')):
                    continue
                label = 'keep-' + unit + '-' + ('panel' if panel else 'list') + '-' + condition + '-' + entry
                prior = OUT / 'native/cases' / (label + '.json')
                if prior.exists() and '--rerun' not in sys.argv[2:]:
                    prior_record = json.loads(prior.read_text())
                    if prior_record.get('status') == 'PASS' and prior_record.get('dat_sha256') == sha(p.dat):
                        summaries.append(dict(case=label, retry_rpc=prior_record['retry_rpc'], retained_final_result=True))
                        print('PASS existing', label, 'final DAT', flush=True)
                        continue
                def run(record, panel=panel, condition=condition, entry=entry):
                    if condition == 'row_reset':
                        nc.move_to(h, p, 5)
                        ux.need(fr.press(h, 0x2b))
                        m.reopen(h, p, w)
                    if panel:
                        nc.move_to(h, p, 5)
                        ux.need(fr.native(h, 0x202be220))
                    before = ux.snap(h, p)
                    original = p.rpc.call
                    row_counts = []
                    entry_counts = dict(h08=0, h06=0, h07=0)
                    for name, key in (('ig_apply', 'h08'), ('ig_panel_open', 'h06'), ('ig_event', 'h07')):
                        def entered(b, key=key):
                            entry_counts[key] += 1
                            return False
                        h.b.add_breakpoint(p.symbol_pc(name), entered)
                    def rows_changed(event):
                        row_counts.append(dict(value=event.data.hex(), pc=hex(event.pc), origin=event.origin))
                    h.b.add_write_trace(0x2022f5ac, 0x2022f5ad, rows_changed)
                    fired = [False]
                    if condition in ('communication', 'communication_three', 'row_reset'):
                        if condition == 'row_reset':
                            p.rpc.overlay.clear()
                            p.rpc.t = 2
                        def busy(command, value):
                            fired[0] = True
                            p.rpc.log.append(dict(cmd=command, value=value, page=p.rpc.page,
                                                 result=-1, t=p.rpc.t, simulated=True))
                            return -1
                        p.rpc.call = busy
                    else:
                        h.b.map(0x206a0000, bytes(0x10000))
                        def boundary(b):
                            if fired[0]:
                                return False
                            fired[0] = True
                            if condition.endswith('_epoch'):
                                index = 7 if condition == 'settings_epoch' else 8
                                address = pe.ROOT_ADDR + 8 + 4 * index
                                value = h.u(address) + 1
                                h.b.origin = 'model:explicit_epoch_transition'
                                h.b.write(address, struct.pack('>I', value))
                            else:
                                p.ready = 0
                                backend = v.PythonBackend()
                                backend.regions, backend.mmio, backend.traces = h.b.regions, h.b.mmio, h.b.traces
                                backend.breakpoints = {k:list(x) for k, x in h.b.breakpoints.items()}
                                backend.core.r, backend.core.psw = list(h.b.core.r), h.b.core.psw
                                backend.core.cr = dict(h.b.core.cr)
                                backend.core.bpsw, backend.core.bbpsw, backend.core.acc = h.b.core.bpsw, h.b.core.bbpsw, h.b.core.acc
                                backend.set_reg('r15', 0x206afff0)
                                shadow = copy.copy(h)
                                shadow.b = backend
                                ux.need(fr.native(shadow, 0x200935b4, (0,)))
                            return False
                        h.b.add_breakpoint(p.symbol_pc('write_word'), boundary)
                    at = len(p.rpc.log)
                    failures = []
                    for _ in range(3 if condition == 'communication_three' else 1):
                        fail_result = ux.need(fr.move_key(h, 0x20))
                        failure_state=ux.snap(h,p)
                        failure_state['cursor_cache']=h.u(0x205a2944,1)
                        assert failure_state['cursor']==failure_state['dot_row']==failure_state['cursor_cache']==before['cursor']
                        assert failure_state['rows']==(11 if panel else 8) and failure_state['W']==before['W']
                        failures.append(failure_state)
                    p.rpc.call = original
                    failed = ux.snap(h, p)
                    adapter = p.symbol_pc('n')
                    record.update(unit=unit, panel=panel, condition=condition, retry_entry=entry,
                        dat_sha256=sha(p.dat), before=before, failed=failed, fail_result=fail_result,
                        fired=fired[0], failures=failures, rows_during_failure=row_counts, entries=entry_counts)
                    assert fired[0] and failed['W'] == before['W']
                    assert failed['rows'] == (11 if panel else 8), failed
                    assert h.u(adapter + layout['failed'], 1) == 0
                    assert failed['cursor'] == failed['dot_row'] == h.u(0x205a2944, 1)
                    assert failed['cursor'] == before['cursor']
                    assert all(x['value'] != '07' for x in row_counts)
                    if condition == 'ready':
                        p.ready = 1
                        ux.need(fr.native(h, 0x200935b4, (1,)))
                    retry_at = len(p.rpc.log)
                    counts_before = dict(entry_counts)
                    budget = 30000000 if condition == 'row_reset' else 8000000
                    if entry == 'direction':
                        retried = ux.need(fr.move_key(h, 0x20, steps=budget))
                        assert entry_counts['h08'] == counts_before['h08'] + 1
                        if panel:
                            ux.matches(h, p, 5, contrast=1)
                        else:
                            ux.matches(h, p, 6 if condition == 'row_reset' else 5)
                    elif entry == 'disp':
                        retried = ux.need(fr.native(h, 0x202be220, steps=budget))
                        assert entry_counts['h06'] == counts_before['h06'] + 1
                        assert h.u(0x2022f5ac, 1) == 11
                        assert h.u(adapter + layout['panel.parameter'], 1) == (1 if panel else 0)
                    else:
                        retried = ux.need(fr.press(h, 0x23, steps=budget))
                        assert entry_counts['h07'] == counts_before['h07'] + 1
                    after = ux.snap(h, p)
                    assert len(p.rpc.log) > retry_at
                    assert h.u(adapter + layout['failed'], 1) == 0
                    if entry != 'confirm':
                        assert after['cursor'] == after['dot_row'] == h.u(0x205a2944, 1)
                        assert all(x['value'] != '07' for x in row_counts)
                    record.update(after=after, retried=retried, retry_rpc=len(p.rpc.log) - retry_at,
                        rpc_log=p.rpc.log[at:], rows_all=row_counts,
                        file_mutations=m.no_writes(p), epoch_model=condition.endswith('_epoch'))
                result = nc.case(label, run, checkpoint)
                summaries.append(dict(case=label, retry_rpc=result['retry_rpc']))
    save('native/keep-cases-' + unit + '.json', dict(status='PASS', unit=unit,
        dat_sha256=sha(p.dat), cases=summaries,
        selected_mode='core_failure_entries' if quick else 'full_permutations',
        epoch_scope='Settings and mode epoch changes are explicit device-model conditions, separate from shooting sequences.'))
    print('PASS retained view and retry entries', unit, len(summaries), flush=True)

if __name__ == '__main__':
    main(sys.argv[1])
