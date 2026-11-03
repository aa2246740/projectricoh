"""Observe actual S stores at RV_SETTINGS in the final M32R image.

Lock states are model inputs at the normal service boundary. Busy owners
release after that rejected call's IRQ restore so compensation can finish.
"""
import json
import os
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g138_host as H

OUT = Path(__file__).resolve().parent
H.setup()
cam = H.Camera('50mm')
cam.open_menu()
cases = [(op, count, ident) for op in (2, 5) for count, ident in
         [(-1, 55), (0, 55), (1, 55), (-1, 54)]]


def check(op, count, ident):
    cam.h.b.core.psw |= 0x40
    active = [False]
    entered = [False]
    host_write = [False]
    released = [False]
    events = []
    lock_events = []
    result = {}
    def host(function):
        host_write[0] = True
        try:
            function()
        finally:
            host_write[0] = False
    if op == 2:
        host(lambda: cam.put_s(0x6dd, bytes([10])))
    def s_store(event):
        if active[0] and not host_write[0]:
            events.append(dict(offset=event.address-cam.s, bytes=len(event.data),
                               irq_enabled=bool(cam.h.b.get_reg('psw') & 0x40),
                               count=cam.lock()[0]))
    def lock_store(event):
        if active[0] and not host_write[0]:
            lock_events.append(dict(address=event.address, bytes=len(event.data),
                                    value=event.value))
    cam.h.b.add_write_trace(cam.s, cam.s + 4096, s_store)
    cam.h.b.add_write_trace(H.LOCK, H.LOCK + 8, lock_store)
    def completed(backend):
        if not active[0]:
            return False
        active[0] = False
        value = backend.get_reg('r0')
        result['status'] = value - 2**32 if value >= 2**31 else value
        result['lock_after'] = cam.lock()
        return False
    def enter(backend):
        if (not entered[0] and backend.get_reg('r0') == 6 and
                backend.get_reg('r1') == op):
            entered[0] = active[0] = True
            host(lambda: cam.set_lock(count, ident))
            cam.h.b.add_breakpoint(backend.get_reg('r14'), completed)
        return False
    def restore(backend):
        if active[0] and (count, ident) != (-1, 55):
            result['busy_lock_before_owner_release'] = cam.lock()
            def owner_releases(after_irq):
                if released[0]:
                    return False
                assert after_irq.get_reg('psw') & 0x40
                released[0] = True
                host(lambda: cam.set_lock(-1, 55))
                return False
            cam.h.b.add_breakpoint(backend.get_reg('r14'), owner_releases)
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'), enter)
    cam.h.b.add_breakpoint(cam.symbol('rv_irq_restore'), restore)
    # The test is the first service operation, including all same-value
    # stores. Later engine compensation is outside that observation.
    event = cam.m.fr.move_key(cam.h, 0x20, steps=400000000)
    assert event.get('ok'), event
    assert cam.h.b.get_reg('psw') & 0x40, 'IRQ enable state was not restored'
    assert entered[0] and not active[0], (op, result)
    busy = (count, ident) != (-1, 55)
    if busy:
        assert result['status'] == -2 and not events and not lock_events, (result, events, lock_events)
        assert tuple(result['busy_lock_before_owner_release']) == (count, ident)
    else:
        assert result['status'] == 0 and result['lock_after'] == (-1, 55)
        assert all(not e['irq_enabled'] and e['count'] == 0 for e in events), events
        if op == 5:
            assert [e['offset'] for e in events] == list(range(0xfd4, 0xffc, 4)), events
            assert all(e['bytes'] == 4 for e in events)
        else:
            assert [e['offset'] for e in events] == [0x6dd], events
        assert [e['value'] for e in lock_events] == [0, 0xffffffff], lock_events
    return dict(op=op, input_count=count, input_id=ident, result=result,
                S_stores=events, lock_stores=lock_events, status='PASS')


receipts = []
for op, count, ident in cases:
    name = 'op%d-count%d-id%d' % (op, count, ident)
    sys.stdout.flush()
    pid = os.fork()
    if not pid:
        code = 0
        try:
            result = check(op, count, ident)
        except BaseException as error:
            result = dict(status='FAIL', error=type(error).__name__ + ': ' + str(error),
                          frames=[dict(file=f.filename, line=f.lineno, function=f.name)
                                  for f in traceback.extract_tb(error.__traceback__)])
            code = 1
        (OUT / 'local' / ('lock-trace-' + name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        os._exit(code)
    _, status = os.waitpid(pid, 0)
    receipts.append(dict(case=name, wait_status=status))
    print('lock-trace', name, status, flush=True)
result = dict(status='PASS_M32R' if all(r['wait_status'] == 0 for r in receipts) else 'FAIL',
              dat_sha256=H.sha(H.DAT), cases=receipts)
(OUT / 'evidence/lock-trace.json').write_text(json.dumps(result, indent=2) + '\n')
assert result['status'] == 'PASS_M32R', receipts
