"""Follow a real W-started permanent lock through native exit handlers."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *
from run_cases import prepare


def run(fixture, panel, action, keep, record):
    ux, m, fr, pe, v, h, p, w, prepared = fixture
    record.update(prepared)
    sequence = load(MATERIALS / 'native_sequence.py', 'lock_exit_sequence')
    sequence.device_edges(h, p)
    sequence.prepare_input(h)
    # The native task prologue changes the active view. Re-enter with the
    # official constructor before attempting the W-started fault.
    m.reopen(h, p, w)
    if panel:
        for _ in range(3):ux.need(fr.native(h, 0x202be220))
    before = ux.snap(h, p)
    original = p.rpc.call
    fired = [False]
    at = len(p.rpc.log)

    def fault(cmd, value):
        if not fired[0] and cmd == 22:
            result = original(cmd, value)
            p.rpc.log[-1].update(device_result=result, result=-1, simulated=True)
            fired[0] = True
            return -1
        if fired[0]:
            p.rpc.log.append(dict(cmd=cmd, value=value, page=p.rpc.page,
                                 result=-1, t=p.rpc.t, simulated=True))
            return -1
        return original(cmd, value)

    p.rpc.call = fault
    record['lock_event'] = ux.need(fr.move_key(h, 0x20, steps=30000000))
    p.rpc.call = original
    assert fired[0]
    record['locked'] = ux.snap(h, p)
    assert record['locked']['list']['uncertain'] == 1
    if record['artifact']['generation'] == 126:
        assert record['locked']['rows'] == 8 and record['locked']['cursor'] == record['locked']['dot_row'] == 1
        layout = json.loads((OUT / 'local/layout/current-adapter-layout.json').read_text())
        n = p.symbol_pc('n')
        assert h.u(n + layout['failed'], 1) == 1
        assert h.u(n + layout['panel.open'], 1) == h.u(n + layout['panel.input_enabled'], 1) == 0
    ux.need(fr.native(h, 0x20265818, (keep,)))
    assert h.u(0x2037f2fe, 1) == keep
    settings = h.u(0x200c0dac)
    settings_before = h.b.read(settings, 0xc9e)
    image_before = h.b.read(settings + 0x36e, 1)
    writes = []
    entries = []
    setters = []
    hooks = w.mark()
    rpc_at = len(p.rpc.log)

    def changed(e):
        writes.append(dict(address=hex(e.address), offset=e.address-settings,
                           pc=hex(e.pc), origin=e.origin, data=e.data.hex()))

    h.b.add_write_trace(settings, settings + 0xc9e, changed)
    for name in ('ig_event', 'ig_apply', 'ig_panel_open', 'ig_panel_event', 'ig_stop'):
        def entered(b, name=name):
            q = b.core.r[2]
            entries.append(dict(name=name, code=h.u(q+40), keep=h.u(q+44)))
            return False
        h.b.add_breakpoint(p.symbol_pc(name), entered)
    for pc in (0x202871dc, 0x20268768, 0x20268774):
        def setter(b, pc=pc):
            setters.append(dict(pc=hex(pc), args=list(b.core.r[4:8])))
            return False
        h.b.add_breakpoint(pc, setter)
    if action in ('confirm', 'adj'):
        result = fr.press(h, 0x23 if action == 'confirm' else 0x2b, steps=30000000)
    elif action in ('half', 'release'):
        key = 0x29 if action == 'half' else 0x63
        h.select_item_8()
        record['first_column'] = ux.need(fr.native(h, 0x2029fdc4, (key, 0), steps=30000000))
        result = fr.native(h, 0x202bd724, (key, 0), steps=30000000)
    elif action == 'raw_half':
        result = sequence.key(h, fr, 0xd)
    elif action == 'disp_confirm':
        record['disp'] = ux.need(fr.native(h, 0x202be220, steps=30000000))
        record['after_disp'] = ux.snap(h, p)
        result = fr.press(h, 0x23, steps=30000000)
    else:
        raise ValueError(action)
    if action == 'raw_half':
        assert result['logical'] == 0x29 and all(x['ok'] for x in result['dispatch']), result
    else:
        ux.need(result)
    after = ux.snap(h, p)
    settings_after = h.b.read(settings, 0xc9e)
    changes = [dict(offset=i, before=a, after=b) for i, (a, b) in
               enumerate(zip(settings_before, settings_after)) if a != b]
    record.update(panel=panel, action=action, keep=keep, before=before, result=result,
                  after=after, native_setters=setters, DAT_entries=entries,
                  resident_hooks=w.since(hooks), S_writes=writes, S_changes=changes,
                  S_sha_before=sha(settings_before), S_sha_after=sha(settings_after),
                  exit_RPC=len(p.rpc.log)-rpc_at, rpc_log=p.rpc.log,
                  fault_RPC=p.rpc.log[at:rpc_at], cursor_cache=h.u(0x205a2944, 1),
                  native_UI=ui_audit(h), file_mutations=m.no_writes(p))
    assert not record['native_UI']['host_ui_writes'] and not record['native_UI']['getter_callback_present']
    assert h.b.read(settings + 0x36e, 1) == image_before, record
    assert not setters, setters
    if action != 'raw_half':
        assert not writes and not changes, (writes, changes)
    else:
        record['S_comparison_policy'] = 'Compare the complete S transition with gen 121; the native shooting task also updates S outside the Image setter.'
    assert len(p.rpc.log) == rpc_at, 'No engine RPC may resume after permanent lock'
    record['status'] = 'PASS_NO_NATIVE_OPTION_APPLIED'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generation', type=int, choices=(126,), default=126)
    parser.add_argument('--unit', choices=('50mm', '28mm', 'mount'), default='50mm')
    parser.add_argument('--actions', nargs='+', choices=('confirm','adj','half','release','raw_half','disp_confirm'),
                        default=('confirm','adj','half','release','raw_half','disp_confirm'))
    parser.add_argument('--record-tag', default='')
    args = parser.parse_args()
    raw_recheck = args.actions == ['raw_half']
    fixture = prepare(argparse.Namespace(generation=args.generation, unit=args.unit,
                                        case=('lock-exits-raw-recheck' if raw_recheck else 'lock-exits')+args.record_tag))
    results = []
    for panel in (False, True):
        for keep in (0, 1):
            for action in args.actions:
                name = f'{args.generation}-{args.unit}-{"panel" if panel else "list"}-k{keep}-{action}'
                if raw_recheck:
                    name += '-recheck'
                if args.record_tag:
                    name += '-'+args.record_tag
                sys.stdout.flush()
                pid = os.fork()
                if pid == 0:
                    record = dict(case=name, generation=args.generation, unit=args.unit)
                    code = 0
                    try:
                        run(fixture, panel, action, keep, record)
                    except BaseException:
                        record.update(status='FAIL', error=traceback.format_exc())
                        code = 1
                    save('local/lock-exits/' + name + '.json', record)
                    print(name, record['status'], record.get('error', '')[-900:], flush=True)
                    os._exit(code)
                _, status = os.waitpid(pid, 0)
                results.append(dict(case=name, wait_status=status))
    suffix = '-raw-half-recheck' if args.actions == ['raw_half'] else ''
    if args.record_tag:
        suffix += '-'+args.record_tag
    save(f'evidence/lock-exits-{args.generation}-{args.unit}{suffix}.json', dict(
        status='PASS' if all(x['wait_status'] == 0 for x in results) else 'FAIL',
        generation=args.generation, unit=args.unit, dat_sha256=file_sha(DAT), cases=results))
    assert all(x['wait_status'] == 0 for x in results), results


if __name__ == '__main__':
    from completed import reuse
    if not reuse(Path(__file__).stem,sys.argv[1:]):
        main()
