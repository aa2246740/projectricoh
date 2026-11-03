"""Yield ownership around the new ERR update and redraw IRQ boundaries."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *
from run_cases import prepare
from safety_cases import shadow
from static_audit import symbols

CUTS = ('before_update_irq', 'after_update_restore', 'before_redraw_irq', 'after_redraw_restore')


def run(fixture, panel, cut, switch_kind, record, irq_enabled=False):
    ux, m, fr, pe, v, h, p, w, prepared = fixture
    record.update(prepared)
    if panel:
        ux.need(fr.native(h, 0x202be220))
        ux.need(fr.native(h, 0x202be220))
        ux.need(fr.native(h, 0x202be220))
    layout = json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    n = p.symbol_pc('n')
    scope = load(MATERIALS/'ui_trace_scope.py', 'cut_ui_scope')
    ui = ux.snap(h, p)['root']['ui_block']
    low = p.image_base + 256
    high = low + len((TREE/'candidate/local/full-r13/engine.bin').read_bytes())
    ui_fn = p.symbol_pc('ui_list')
    ui_name,ui_symbol=next((name,value) for name,value in symbols(ELF).items() if value['address']+p.image_base==ui_fn)
    ui_size=ui_symbol['size']
    # LTO removes the constant root argument. The linked entry saves r0 as
    # op and moves r1 into r9 as the request pointer (retained disassembly).
    op_register=0 if '.constprop.' in ui_name else 1
    operation=[0]
    h.b.add_breakpoint(ui_fn,lambda b:operation.__setitem__(0,b.core.r[op_register]) or False)
    switched = [False]
    pending = [False]
    late = []
    draws = []
    native_writes = []
    painted_rows = []
    cut_trace = []

    def switch(b):
        if switched[0]:
            return False
        before = ux.snap(h, p)
        other = shadow(h, v)
        if switch_kind == 'activity':
            other.run_slice(0x202ba380, 0x202ba3c8)
            other.leave_other_list()
        else:
            ux.need(fr.native(other, 0x202b0a74, (55,)))
        switched[0] = True
        record['switch'] = dict(pc=hex(b.pc), psw=b.core.psw, before=before,
                                 after=ux.snap(h, p), native_state=h.u(0x205d9c00))
        return False

    def boundary(b, restoring):
        if not h.u(n+layout['failed'], 1) or switched[0] or pending[0]:
            return False
        caller = b.core.r[14]
        if not ui_fn <= caller < ui_fn + ui_size:
            return False
        op = operation[0]
        if op not in (2, 3):
            return False
        cut_trace.append(dict(operation=op, restoring=restoring, caller=hex(caller), psw=b.core.psw))
        wanted_op = 2 if 'update' in cut else 3
        wanted_restore = 'restore' in cut
        if op != wanted_op or restoring != wanted_restore:
            return False
        if restoring:
            # This callback runs at the continuation only after PSW restore.
            pending[0] = True
            h.b.add_breakpoint(caller, switch)
        else:
            switch(b)
        return False

    h.b.add_breakpoint(p.symbol_pc('rv_irq_save'), lambda b: boundary(b, False))
    h.b.add_breakpoint(p.symbol_pc('rv_irq_restore'), lambda b: boundary(b, True))

    def watch(e):
        if switched[0] and e.origin == 'cpu' and (
                scope.touches_ui(e) or ui <= e.address < ui+1980):
            (late if low <= e.pc < high else native_writes).append(
                dict(pc=hex(e.pc), address=hex(e.address), data=e.data.hex()))

    h.b.add_write_trace(0, 2**32, watch)
    h.b.add_breakpoint(p.symbol_pc('rv_native_draw'), lambda b: (
        draws.append(dict(after_switch=switched[0], state=hex(b.core.r[1]),
                          activity=h.u(0x205d9bf8), native_state=h.u(0x205d9c00))) or False))
    def paint(b):
        if switched[0]:
            state = b.core.r[13]
            painted_rows.append(dict(state=hex(state), marker=h.u(state+9,1),
                                     cursor=h.u(state+10,1), activity=h.u(0x205d9bf8),
                                     native_state=h.u(0x205d9c00)))
        return False
    h.b.add_breakpoint(0x201ffb2c, paint)
    original = p.rpc.call
    fired = [False]

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
    if irq_enabled:
        h.b.core.psw |= 0x40
    record['event'] = ux.need(fr.move_key(h, 0x20, steps=30000000))
    p.rpc.call = original
    record.update(unit=p.unit, panel=panel, cut=cut, switch_kind=switch_kind,
                  switched=switched[0], cut_trace=cut_trace, op_register=op_register, late_DAT_UI=late,
                  draws=draws, painted_rows_after_switch=painted_rows,
                  late_native_UI=native_writes, irq_enabled=irq_enabled,
                  after=ux.snap(h, p), native_state=h.u(0x205d9c00),
                  rpc_log=p.rpc.log, dat_sha256=sha(p.dat), native_UI=ui_audit(h),
                  file_mutations=m.no_writes(p))
    assert switched[0], (cut, cut_trace)
    assert not late, late
    assert not record['native_UI']['host_ui_writes']
    if irq_enabled:
        assert record['switch']['psw'] & 0x40, 'The preemption must occur with IRQ enabled'
        assert not [x for x in draws if x['after_switch']], 'Stale native redraw after ownership loss'
    record['status'] = 'PASS_NO_LATE_DAT_UI_STORE'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unit', choices=('50mm', '28mm', 'mount'), default='50mm')
    parser.add_argument('--cuts', nargs='+', choices=CUTS, default=CUTS)
    parser.add_argument('--irq-enabled', action='store_true')
    args = parser.parse_args()
    fixture = prepare(argparse.Namespace(generation=126, unit=args.unit, case='lock-cutpoints'))
    results = []
    for panel in (False, True):
        for cut in args.cuts:
            for switch_kind in ('activity', 'state'):
                if 'update' in cut:
                    results.append(dict(case=f'{args.unit}-{panel}-{cut}-{switch_kind}',wait_status=0,status='REMOVED_UPDATE_PATH',reason='No list_bind(2) caller remains in gen 126.'))
                    continue
                name = f'{args.unit}-{"panel" if panel else "list"}-{cut}-{switch_kind}'
                sys.stdout.flush()
                pid = os.fork()
                if pid == 0:
                    record = dict(case=name, unit=args.unit)
                    code = 0
                    try:
                        run(fixture, panel, cut, switch_kind, record, args.irq_enabled)
                    except BaseException:
                        record.update(status='FAIL', error=traceback.format_exc())
                        code = 1
                    save('local/cutpoints'+('-irq-enabled' if args.irq_enabled else '')+'/'+name+'.json', record)
                    print(name, record['status'], record.get('error', '')[-700:], flush=True)
                    os._exit(code)
                _, status = os.waitpid(pid, 0)
                results.append(dict(case=name, wait_status=status))
    save('evidence/lock-cutpoints-'+args.unit+('-irq-enabled' if args.irq_enabled else '')+'.json', dict(
        status='PASS' if all(x['wait_status'] == 0 for x in results) else 'FAIL',
        dat_sha256=file_sha(DAT),unit=args.unit, cases=results))
    assert all(x['wait_status'] == 0 for x in results), results


if __name__ == '__main__':
    main()
