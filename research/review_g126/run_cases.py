"""Independent counterexamples using the packaged DAT and native constructors."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *

def prepare(args):
    ux, m, fr, pe, v = setup(args.generation, args.unit, args.case)
    h, p, w = m.boot(args.unit)
    r = dict(cold=m.published(h, p, w))
    ux.need(fr.move_key(h, 0x20))
    ux.matches(h, p, 5)
    ux.need(fr.press(h, 0x2b))
    r['selected'] = ux.snap(h, p)
    m.reopen(h, p, w)
    r['verified_reopen'] = ux.snap(h, p)
    r['verified_reopen_rpc'] = p.rpc.log[-20:]
    r['artifact'] = dict(dat_sha256=sha(p.dat), generation=args.generation,
                         body_sha256=h.image.sha256, elf_sha256=file_sha(pe.ENGINE_ELF))
    print('PREPARED', args.generation, args.unit, flush=True)
    return ux, m, fr, pe, v, h, p, w, r

def run(args, r, fixture=None):
    ux, m, fr, pe, v, h, p, w, prepared = fixture or prepare(args)
    r.update(prepared)
    core_layout = json.loads((MATERIALS / 'local/layout/layout.json').read_text())
    adapter_layout = json.loads((MATERIALS / 'local/layout/current-adapter-layout.json').read_text())
    def state():
        result = ux.snap(h, p)
        if args.generation == 126:
            base = p.symbol_pc('n')
            result['adapter'] = {name: h.u(base + adapter_layout[name], 1)
                                 for name in ('retry', 'failed', 'watch_view', 'view_lost', 'ui_failed')}
        return result
    def actual_match(slot):
        try:
            return dict(matches=True, result=ux.matches(h, p, slot))
        except AssertionError as error:
            return dict(matches=False, error=str(error))
    at = len(p.rpc.log)
    if args.case == 'partial_reset':
        current, mapping = m.unpack(p.dat, m.INDEX[args.unit], 5)
        stock, _ = m.unpack(p.dat, m.INDEX[args.unit], 4)
        candidates = []
        for row in range(9):
            desc = mapping[32 + 12 * row:44 + 12 * row]
            base = int.from_bytes(desc[:4], 'big')
            size = int.from_bytes(desc[4:6], 'big')
            off = int.from_bytes(desc[6:8], 'big')
            points = [i for i in range(base & 1, size - 1, 2)
                      if current[off+i:off+i+2] != stock[off+i:off+i+2]]
            if len(points) > 1:
                candidates.append((row, base, size, off, points))
        row, base, size, off, points = candidates[0]
        sentinel, corrupt = points[0], points[-1]
        address = base + corrupt
        r['fault'] = dict(kind='explicit unit partial row reset, no body/engine/UI assignment',
                          row=row, address=hex(address), bytes=2,
                          sentinel_address=hex(base + sentinel), epochs_changed=False)
        p.rpc.overlay[address] = int.from_bytes(stock[off+corrupt:off+corrupt+2], 'big')
        r['fault_before_reopen'] = actual_match(5)
        assert not r['fault_before_reopen']['matches']
        r['reopen_result'] = m.reopen(h, p, w)
        r['after'] = state()
        r['after_recipe5'] = actual_match(5)
        assert r['after_recipe5']['matches'], r['after_recipe5']
        assert r['after']['rows']==8 and r['after']['cursor']==r['after']['dot_row']==5
    elif args.case.startswith('deferred_'):
        ux.need(fr.press(h, 0x2b))
        p.rpc.overlay.clear()
        p.rpc.t = 2
        original = p.rpc.call
        def busy(command, value):
            p.rpc.log.append(dict(cmd=command, value=value, page=p.rpc.page,
                                 result=-1, t=p.rpc.t, simulated=True))
            return -1
        p.rpc.call = busy
        h.parent()
        opened, _, error = fr.publish(h, p, w)
        ux.need(opened)
        assert error is None, error
        r['pending'] = state()
        r['pending_recipe5'] = actual_match(5)
        r['pending_stock'] = actual_match(4)
        assert r['pending']['rows']==7 and not r['pending']['root']['ui_restore0'], r['pending']
        assert r['pending']['adapter']['failed']==0 and r['pending']['adapter']['retry']==0
        r['H01'] = opened
        events = []
        def entry(b):
            q = b.core.r[2]
            events.append(dict(entry=hex(b.pc), code=h.u(q+40), keep=h.u(q+44), caller=hex(h.u(q+56))))
            return False
        for name in ('ig_event', 'ig_apply', 'ig_panel_open', 'ig_stop'):
            h.b.add_breakpoint(p.symbol_pc(name), entry)
        start = len(p.rpc.log)
        if args.case == 'deferred_confirm_busy':
            r['event'] = fr.press(h, 0x23, steps=30000000)
        elif args.case in ('deferred_half_busy', 'deferred_half_recovered'):
            if args.case.endswith('recovered'):
                p.rpc.call = original
            h.select_item_8()
            r['first_column'] = fr.native(h, 0x2029fdc4, (0x29, 0), steps=30000000)
            r['event'] = fr.native(h, 0x202bd724, (0x29, 0), steps=30000000)
        elif args.case == 'deferred_adj_busy':
            r['event'] = fr.press(h, 0x2b, steps=30000000)
        elif args.case == 'deferred_raw_half_busy':
            sequence = load(MATERIALS / 'native_sequence.py', 'review_native_sequence')
            sequence.device_edges(h, p)
            r['input_start'] = sequence.prepare_input(h)
            r['event'] = sequence.key(h, fr, 0xd)
        elif args.case in ('deferred_direction', 'deferred_disp', 'deferred_confirm_recovered'):
            p.rpc.call = original
            r['event'] = (fr.move_key(h, 0x20, steps=30000000) if args.case.endswith('direction')
                          else fr.native(h, 0x202be220, steps=30000000) if args.case.endswith('disp')
                          else fr.press(h, 0x23, steps=30000000))
        else:
            raise ValueError(args.case)
        r['events'] = events
        r['event_RPC'] = len(p.rpc.log) - start
        r['after'] = state()
        r['after_recipe5'] = actual_match(5)
        r['after_recipe6'] = actual_match(6)
        r['after_stock'] = actual_match(4)
        p.rpc.call = original
        assert r['after']['rows']!=8 and not r['after']['root']['ui_restore0'], r['after']
        assert not r['after_recipe5']['matches']
        assert not events, events
        r['fallback_native_list']=True
        r['next_H01']=m.reopen(h,p,w)
        r['next_H01_recipe5']=actual_match(5)
        assert r['next_H01_recipe5']['matches']
        assert h.u(0x2022f5ac,1)==8 and h.u(0x2022f726,1)==5
    else:
        raise ValueError(args.case)
    calls = p.rpc.log[at:]
    r['rpc_log'] = calls
    r['RPC'] = len(calls)
    r['W'] = sum(x['cmd'] == 22 for x in calls)
    r['file_mutations'] = m.no_writes(p)
    r['native_UI'] = ui_audit(h)
    assert not r['native_UI']['host_ui_writes'] and not r['native_UI']['getter_callback_present']
    r['status'] = 'PASS'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    parser.add_argument('--generation', type=int, choices=(121, 126), default=126)
    parser.add_argument('--unit', choices=('50mm', '28mm', 'mount'), default='50mm')
    args = parser.parse_args()
    if args.case == 'suite':
        fixture = prepare(args)
        results = []
        names = ['partial_reset','deferred_confirm_busy','deferred_half_busy','deferred_adj_busy',
                 'deferred_half_recovered','deferred_direction','deferred_disp','deferred_confirm_recovered',
                 'deferred_raw_half_busy']
        for name in names:
            sys.stdout.flush()
            pid = os.fork()
            if pid == 0:
                args.case = name
                record = dict(case=name, generation=args.generation, unit=args.unit)
                code = 0
                try:
                    run(args, record, fixture)
                except BaseException:
                    record.update(status='EXECUTION_ERROR', error=traceback.format_exc())
                    code = 1
                save(f'local/cases/{args.generation}-{args.unit}-{name}.json', record)
                print(json.dumps({k:record.get(k) for k in ('case','generation','unit','status','RPC','W','event_RPC')},ensure_ascii=False),flush=True)
                os._exit(code)
            _, status = os.waitpid(pid, 0)
            results.append(dict(case=name, wait_status=status))
        save(f'evidence/suite-{args.generation}-{args.unit}.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',dat_sha256=file_sha(DAT),results=results))
        assert all(x['wait_status']==0 for x in results), results
        return
    record = dict(case=args.case, generation=args.generation, unit=args.unit)
    try:
        run(args, record)
    except BaseException:
        record['status'] = 'EXECUTION_ERROR'
        record['error'] = traceback.format_exc()
        raise
    finally:
        name = f'{args.generation}-{args.unit}-{args.case}'
        save('local/cases/' + name + '.json', record)
        print(json.dumps({k: record.get(k) for k in ('case','generation','unit','status','RPC','W','event_RPC')}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
