"""Observe native Fn2 edits, confirmation, and half-shutter exit."""
from pathlib import Path
import argparse
import json
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, sha, load

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('unit', choices=('50mm', '28mm', 'mount'))
    args = parser.parse_args()
    ux = load(OUT / 'native_ux.py', 'fn2_native_ux')
    ux.OUT = OUT / 'native'
    ux.save = lambda name, value: save('native/' + name, value)
    m, fr, v, pe = ux.m, ux.fr, ux.v, ux.pe
    m.OUT = OUT / 'native'
    dat, elf = ux.configure(False, args.unit + '-fn2-contract')
    v.python_backend.CACHE = OUT / 'decode' / args.unit
    assert sha(dat.read_bytes()) == 'd11e88eae677f7ee3aeba4dc602c2085ef92b9c81f5c70286c8eb038211e4bbc'
    assert int.from_bytes(dat.read_bytes()[28:32], 'big') == 119
    cases = []
    started = time.monotonic()
    for name, key in (('ok', 0x23), ('adj', 0x2b), ('half', 0x29)):
        h, p, w = m.boot(args.unit)
        assert 0x20271fec not in h.b.breakpoints
        m.published(h, p, w)
        ins = ux.instrument(h, p)
        for function in ('ig_event', 'ig_apply', 'ig_panel_open'):
            h.b.add_breakpoint(p.symbol_pc(function), ins['entry_callback'])
        # Keep the existing exact CRC-32 computation boundary. Native events,
        # setters, getters and every recipe transaction still run M32R code.
        m.move_to(h, 5)
        baseline = ux.snap(h, p)
        ux.matches(h, p, 5)
        ux.need(fr.native(h, 0x202be220))
        opened = ux.snap(h, p)
        assert opened['rows'] == 11 and opened['cursor'] == 6
        ux.matches(h, p, 5)
        rpc_before = len(p.rpc.log)
        preview_before = h.stub_hits.get('preview', 0)
        ux.need(fr.move_key(h, 0x20))
        edited = ux.snap(h, p)
        unchanged_live = ux.matches(h, p, 5)
        assert len(p.rpc.log) == rpc_before
        assert h.stub_hits.get('preview', 0) == preview_before
        assert edited['deep_sha256'] == opened['deep_sha256']
        assert edited['rows'] == 11 and edited['cursor'] == 7
        try:
            ux.matches(h, p, 5, contrast=1)
        except AssertionError:
            edited_value_already_applied = False
        else:
            edited_value_already_applied = True
        assert not edited_value_already_applied
        trace = []
        for function in ('ig_event', 'eng_apply', 'apply_impl', 'core_call'):
            address = p.symbol_pc(function)
            def observe(b, function=function):
                trace.append(dict(function=function, pc=hex(b.pc), arguments=b.core.r[:4],
                                  rpc_count=len(p.rpc.log), preview_count=h.stub_hits.get('preview', 0)))
                return False
            h.b.add_breakpoint(address, observe)
        event_start = len(ins['events'])
        if name == 'half':
            h.select_item_8()
            result = [ux.need(fr.native(h, 0x2029fdc4, (key, 0), steps=8000000)),
                      ux.need(fr.native(h, 0x202bd724, (key, 0), steps=8000000))]
            expected_contrast = 0
        else:
            result = [ux.need(fr.press(h, key))]
            expected_contrast = 1
        closed = ux.snap(h, p)
        actual = ux.matches(h, p, 5, contrast=expected_contrast)
        rpc_delta = len(p.rpc.log) - rpc_before
        writes = sum(row['cmd'] == 22 for row in p.rpc.log[rpc_before:])
        previews = h.stub_hits.get('preview', 0) - preview_before
        if name == 'half':
            assert rpc_delta == writes == previews == 0
            assert closed['deep_sha256'] == edited['deep_sha256']
        else:
            assert rpc_delta > 0 and writes > 0 and previews > 0
            assert closed['deep_sha256'] != edited['deep_sha256']
            assert any(row['function'] == 'ig_event' for row in trace)
            assert any(row['function'] == 'eng_apply' for row in trace)
        counters = m.no_writes(p)
        cases.append(dict(name=name, baseline=baseline, opened=opened, edited=edited,
            edited_value_already_applied=edited_value_already_applied,
            live_after_arrow=unchanged_live, arrow_extra_rpc=0, arrow_extra_preview=0,
            closed=closed, expected_contrast=expected_contrast, final_actual=actual,
            close_rpc=rpc_delta, close_W=writes, close_preview=previews,
            close_rpc_log=p.rpc.log[rpc_before:], close_events=ins['events'][event_start:],
            call_trace=trace, native_results=result, file_mutations=counters))
        save('native/fn2-contract-' + args.unit + '.json', dict(status='RUNNING', unit=args.unit,
            dat_sha256=sha(dat.read_bytes()), elf_sha256=sha(elf.read_bytes()), cases=cases))
        print('PASS native Fn2 contract', args.unit, name, 'arrow RPC=0; exit RPC', rpc_delta,
              'W', writes, 'preview', previews, 'final contrast', expected_contrast, flush=True)
    save('native/fn2-contract-' + args.unit + '.json', dict(status='PASS', unit=args.unit,
        dat_sha256=sha(dat.read_bytes()), elf_sha256=sha(elf.read_bytes()), body_sha256=v.BODY_SHA,
        native_ui_hand_seeded=False, getter_fixed_return_stub_removed=True, cases=cases,
        seconds=time.monotonic()-started,
        observation='Fn2 arrows retain the committed unit recipe; OK and ADJ apply the draft in H07; half shutter retains the committed recipe.'))

if __name__ == '__main__':
    main()
