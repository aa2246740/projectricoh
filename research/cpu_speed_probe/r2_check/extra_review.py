"""Copy of research/review_cpuprobe_r2/extra_review.py. cache_cases unchanged. timing_cases and draw_case keep
the review's scenarios (same clocks, same read sequences, same draw delay) but now assert the fixed behaviour:
every key press stays under the instruction caps, whatever the tick does (the review's asserts here confirmed
the counterexamples on DAT aee0fb19). OWN_CAP/TOTAL_CAP come from accept_cpuprobe.py."""
from pathlib import Path
import json
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_review as br
rs = br.rs


class Clock:
    def __init__(self, session, per_tick=5000, base=5000000):
        self.s = session
        self.per_tick = per_tick
        self.base = base
        self.anchor = session.counter.total()
        self.fixed = None

    def value(self):
        return (self.fixed if self.fixed is not None else
                self.base + (self.s.counter.total() - self.anchor) // self.per_tick) & 0xffffffff

    def rate(self, per_tick):
        self.base = self.value()
        self.anchor = self.s.counter.total()
        self.per_tick = per_tick

    def read(self, backend):
        value = self.value()
        self.s.tick_calls.append(value)
        return value

    def attach(self):
        b = self.s.h.b
        b.breakpoints.pop(0x2005f164, None)
        self.s.h.stub(0x2005f164, 'review_clock', self.read)
        self.s.now = self.value


def checkpoint(s):
    return s.h.b.snapshot(), s.h.b.nop_steps


def restore(s, saved):
    s.h.b.restore(saved[0])
    s.h.b.nop_steps = saved[1]
    s.tick_calls.clear()
    s.clock_value = 1


def compare_reader(cp, s, original):
    observed = cp.stock_reader(s)
    assert observed['cursor_after'] == original, observed
    return observed


def trace_irq(s):
    tracking = dict(active=None, windows=[])
    symbols = []
    for table, base in [(s.h.symbols, 0), (s.p.elf.symbols, s.p.image_base)]:
        if base == 0 and table is s.p.elf.symbols:
            continue
        if 'rv_irq_save' in table and 'rv_irq_restore' in table:
            symbols.append((base + table['rv_irq_save'], base + table['rv_irq_restore']))

    def save(backend):
        if backend.get_reg('psw') & 0x40 and tracking['active'] is None:
            tracking['active'] = dict(ops=s.counter.total(), caller=hex(backend.get_reg('lr')))
        return False

    def restore_irq(backend):
        if backend.get_reg('r0') & 0x40 and tracking['active'] is not None:
            active = tracking['active']
            tracking['windows'].append(dict(caller=active['caller'],
                ops=s.counter.total() - active['ops'] + 20))
            tracking['active'] = None
        return False
    for save_pc, restore_pc in symbols:
        s.h.b.add_breakpoint(save_pc, save)
        s.h.b.add_breakpoint(restore_pc, restore_irq)
    return tracking


def cache_cases(cp, s):
    b, h = s.h.b, s.h
    result = {}
    b.set_reg('psw', b.get_reg('psw') | 0x40)
    s.open()
    s.press(0x23)
    closed = checkpoint(s)
    for label, slot in [('panel_abort', 5), ('shutdown', 7), ('abort', 8)]:
        restore(s, closed)
        h.put(cp.CUR_A, 3, 1); h.put(cp.CUR_B, 6, 1); h.put(cp.CACHE, 2, 1)
        assert s.open()['rows'] == 8
        entry = s.entry(slot)
        assert entry['ok'], entry
        done = s.p.call(h.symbols['rv_ui_abort'], (cp.R,), steps=1000000)
        assert done['ok'], done
        after = s.native()
        reader = compare_reader(cp, s, 6)
        assert (after['a'], after['b'], after['cache'], after['rows']) == (3, 6, 6, 7), after
        result[label] = dict(entry=entry, after=after, stock_reader=reader)
    restore(s, closed)
    h.put(cp.CUR_A, 5, 1); h.put(cp.CUR_B, 5, 1); h.put(cp.CACHE, 1, 1)
    s.open()
    after = s.press(0x29)
    result['menu_logical_29'] = dict(after=after, stock_reader=compare_reader(cp, s, 5))
    assert after['cache'] == after['b'] == 5

    restore(s, closed)
    h.put(cp.CUR_A, 4, 1); h.put(cp.CUR_B, 4, 1); h.put(cp.CACHE, 1, 1)
    s.open()
    other = 0x206cfff0
    h.b.write(other, bytes(16)); h.put(other + 10, 3, 1)
    h.put(0x205a293c, other); h.put(cp.CACHE, 3, 1)
    done = s.entry(2, {8: 7, 9: 0})
    assert done['ok'] and h.u(cp.CACHE, 1) == 3
    ended = s.p.call(h.symbols['rv_ui_abort'], (cp.R,), steps=1000000)
    assert ended['ok']
    result['other_view'] = dict(entry=done, image_cursor=h.u(cp.CUR_B, 1),
                               cache=h.u(cp.CACHE, 1), stock_reader=compare_reader(cp, s, 3))
    assert h.u(cp.CUR_B, 1) == 4

    restore(s, closed)
    h.put(cp.CUR_A, 5, 1); h.put(cp.CUR_B, 5, 1); h.put(cp.CACHE, 5, 1)
    s.open()
    h.put(cp.NAMES, cp.STOCK); h.put(cp.ROWS, 7, 1)
    h.put(cp.CUR_A, 2, 1); h.put(cp.CUR_B, 2, 1); h.put(cp.CACHE, 2, 1)
    before = len(s.engine_writes)
    after = s.press(0x29)
    result['ownership_changed_image_state'] = dict(after=after,
        engine_writes=len(s.engine_writes) - before, stock_reader=compare_reader(cp, s, 2))
    assert after['cache'] == after['b'] == 2
    assert len(s.engine_writes) == before

    restore(s, closed)
    h.put(cp.CUR_A, 6, 1); h.put(cp.CUR_B, 6, 1); h.put(cp.CACHE, 3, 1)
    ascii_address = 0x201d73e0
    prior = b.breakpoints.get(ascii_address)
    prior_handlers = b.handlers.get(ascii_address)
    b.breakpoints.pop(ascii_address, None)

    def text_error_output(backend):
        backend.write(backend.get_reg('r6'), b'A' * 70)
        return 0xffffffff
    h.stub(ascii_address, 'text_error_output', text_error_output)
    try:
        opened = s.open()
        failed = s.native()
        reader = compare_reader(cp, s, failed['b'])
        assert opened['rows'] == 7
        after = s.press(0x29)
        result['text_publish_failure'] = dict(opened=opened, after_open=failed,
                                              after_close=after, stock_reader=reader,
                                              close_reader=compare_reader(cp, s, after['b']))
    finally:
        b.breakpoints.pop(ascii_address, None)
        if prior is not None:
            b.breakpoints[ascii_address] = prior
        if prior_handlers is not None:
            b.handlers[ascii_address] = prior_handlers
        else:
            b.handlers.pop(ascii_address, None)

    retired = []
    for home in range(1, 8):
        for key in (0x20, 0x1f):
            restore(s, closed)
            h.put(cp.CUR_A, home, 1); h.put(cp.CUR_B, home, 1); h.put(cp.CACHE, home, 1)
            assert s.open()['rows'] == 8
            h.put(cp.R + 212, h.u(cp.R + 212) | 1)
            moved = s.move(key)
            after = s.native()
            reader = cp.stock_reader(s)
            assert h.u(cp.R + 5, 1) == 6 and after['b'] == home and after['rows'] == 7
            assert reader['cursor_after'] == after['cache']
            event = s.fr.native(h, 0x201ca4a0, (0x32,), steps=20000000)
            assert event['ok'], event
            after_event = s.native()
            marks = s.w.mark()
            after_ok = s.press(0x23)
            events = s.w.since(marks)
            lands = [item for row in events for item in row.get('land', [])]
            retired.append(dict(home=home, key=hex(key), move=moved, after=after, stock_reader=reader,
                                event32=event, after_event32=after_event, after_ok=after_ok,
                                lands=lands, root_state=h.u(cp.R + 5, 1)))
            assert 'native_setter' not in lands and after_ok['mode'] == 1, retired[-1]
    result['retirement_boundaries'] = retired
    restore(s, closed)
    cp.final_audit(s, result)
    return result, closed


def bounded(cp, move, label, delay=0):
    """The press returned and stayed under the caps (ops counts the whole callback: an upper bound of own)."""
    ops = move['ops'] - delay
    assert move['rows'] == 8 and ops <= cp.OWN_CAP and move['ops'] - delay <= cp.TOTAL_CAP, (label, move, delay)
    return dict(ops=ops, at_5m_ms=ops / 5000, at_75m_ms=ops / 75000)


def timing_cases(cp, s, closed, result):
    for per_tick in (5000, 75000):
        restore(s, closed)
        clock = Clock(s, per_tick)
        clock.attach()
        assert s.open()['rows'] == 8
        moves = []
        while s.u('test', 1) == 0:
            move = s.move(0x20)
            moves.append(dict(move=move, test=s.test(0), **bounded(cp, move, 'stable')))
            assert len(moves) <= cp.RUNS
        assert s.test(0)['flags'] == 1 and s.test(0)['runs'] == cp.RUNS, s.test(0)
        result['stable_%d' % per_tick] = moves

    restore(s, closed)
    clock = Clock(s, 75000)
    clock.attach()
    s.open()
    first = s.move(0x20)
    second = s.move(0x20)
    before = s.test(0)
    assert before['runs'] == 2, before
    clock.rate(5000)
    s.clock_value = 2
    moved = s.move(0x20)
    result['rate_change'] = dict(first=first, second=second, before=before, move=moved, after=s.test(0),
                                 **bounded(cp, moved, 'rate_change'))
    assert s.test(0)['runs'] == 3 and abs(moved['ops'] - second['ops']) < 20000, result['rate_change']

    restore(s, closed)
    clock = Clock(s)
    clock.attach()
    s.open()
    clock.fixed = clock.value()
    arithmetic = s.p.symbol_pc('cp_arith')
    prior = s.h.b.breakpoints.get(arithmetic)
    prior_handlers = s.h.b.handlers.get(arithmetic)
    s.h.b.breakpoints.pop(arithmetic, None)
    counts = []

    def stop_at_count(backend):
        count = backend.get_reg('r0')
        counts.append(count)
        return count >= 1 << 22                     # tripwire from the review: must never fire now
    s.h.b.add_breakpoint(arithmetic, stop_at_count)
    try:
        moved = s.move(0x20)
        result['constant_tick'] = dict(move=moved, planned_counts=counts, clock_value=clock.fixed,
                                       test=s.test(0), **bounded(cp, moved, 'constant_tick'))
        assert counts == [1 << 14, 1 << 16], counts
        assert s.test(0)['flags'] & 16 and s.u('test', 1) == 1, s.test(0)
        again = s.move(0x20)
        result['constant_tick']['next_press'] = dict(move=again, test=s.test(1), **bounded(cp, again, 'constant 2'))
        assert s.test(1)['flags'] & 16, s.test(1)
    finally:
        s.h.b.breakpoints.pop(arithmetic, None)
        if prior is not None:
            s.h.b.breakpoints[arithmetic] = prior
        if prior_handlers is not None:
            s.h.b.handlers[arithmetic] = prior_handlers
        else:
            s.h.b.handlers.pop(arithmetic, None)

    for label, base in [('wrap', 0xffffffe1), ('zero', 0), ('reverse', 5000000)]:
        restore(s, closed)
        clock = Clock(s, base=base)
        clock.attach()
        s.open()
        if label == 'wrap':
            clock.base = base
            clock.anchor = s.counter.total()
        if label == 'reverse':
            values = iter([10000, 10000, 9000])

            def reverse_read(backend):
                value = next(values, 9000)
                s.tick_calls.append(value)
                return value
            s.h.b.breakpoints.pop(0x2005f164, None)
            s.h.stub(0x2005f164, 'reverse_clock', reverse_read)
        elif label == 'zero':
            clock.fixed = 0
        moved = s.move(0x20)
        result[label] = dict(move=moved, test=s.test(0), tick_reads=list(s.tick_calls), **bounded(cp, moved, label))
        if label in ('zero', 'reverse'):
            assert s.test(0)['flags'] & 16
        else:
            assert s.test(0)['runs'] == 1 and not s.test(0)['flags'] & 16

    for label, used in [('budget_equal', 268), ('budget_over', 269), ('budget_wrap', 0xfffffff0)]:
        restore(s, closed)
        clock = Clock(s)
        clock.attach()
        s.open()
        start_tick = 1000
        later = (start_tick + used) & 0xffffffff
        sequence = iter([start_tick, start_tick, start_tick + 15, later, later, (later + 32) & 0xffffffff])
        reads = []

        def boundary_read(backend):
            value = next(sequence, (later + 32) & 0xffffffff)
            reads.append(value)
            s.tick_calls.append(value)
            return value
        s.h.b.breakpoints.pop(0x2005f164, None)
        s.h.stub(0x2005f164, 'budget_boundary_clock', boundary_read)
        moved = s.move(0x20)
        after = s.test(0)
        result[label] = dict(move=moved, test=after, reads=reads, used=used, **bounded(cp, moved, label))
        # the same reads now: short slice 1000 -> 1000 (0), long slice 1015 -> later; a reading that goes back
        # (0xfffffff0 = 16 back) is an error (TK) and the press returns
        assert bool(after['flags'] & 16) == (label == 'budget_wrap'), result[label]

    restore(s, closed)
    cp.final_audit(s, result)
    return result


def draw_case(cp, s, closed, result):
    restore(s, closed)
    clock = Clock(s)
    clock.attach()
    s.open()
    s.move(0x20)
    s.move(0x20)
    draw_site = s.p.symbol_pc('rv_native_draw')
    marker = 0x20750000
    s.h.b.map(marker, bytes(4))
    prior = s.h.b.breakpoints.get(draw_site)
    prior_handlers = s.h.b.handlers.get(draw_site)
    s.h.b.breakpoints.pop(draw_site, None)
    delay = {}

    def slow_draw(backend):
        if delay:
            return False
        delay['registers'] = {name: backend.get_reg(name) for name in
                              ('psw', 'acc', *('r%d' % i for i in range(16)))}
        delay['start_ops'] = s.counter.total()
        delay['irq_enabled'] = bool(backend.get_reg('psw') & 0x40)
        backend.set_reg('r0', 1000000)
        backend.set_reg('lr', marker)
        backend.set_reg('pc', s.p.symbol_pc('cp_decrement'))
        return False

    def draw_done(backend):
        delay['ops'] = s.counter.total() - delay['start_ops']
        registers = delay['registers']
        for name, value in registers.items():
            backend.set_reg(name, value)
        backend.set_reg('pc', draw_site)
        return False
    s.h.b.add_breakpoint(draw_site, slow_draw)
    s.h.b.add_breakpoint(marker, draw_done)
    start = s.counter.total()
    try:
        moved = s.move(0x20)
        operations = s.counter.total() - start
        result.update(dict(move=moved, delay=delay, ops=operations,
                           at_5m_ms=operations / 5000, at_75m_ms=operations / 75000,
                           without_delay=bounded(cp, moved, 'slow_draw', delay['ops'])))
        assert delay and not delay['irq_enabled'] and delay['ops'] >= 2000000
        # the whole callback still exceeds 500 ms at 5 M/s because of the added delay (not ours); the press
        # itself minus that delay stays under OWN_CAP
    finally:
        s.h.b.breakpoints.pop(marker, None)
        s.h.b.handlers.pop(marker, None)
        s.h.b.breakpoints.pop(draw_site, None)
        if prior is not None:
            s.h.b.breakpoints[draw_site] = prior
        if prior_handlers is not None:
            s.h.b.handlers[draw_site] = prior_handlers
    restore(s, closed)
    cp.final_audit(s, result)
    return result


def main():
    started = time.monotonic()
    mode = sys.argv[1]
    unit = sys.argv[2]
    cp = br.prepare(mode, unit)
    session = cp.Session(unit)
    report = dict(dat=rs.digest(cp.DAT), unit=unit, mode=mode)
    tracking = None
    try:
        if mode == 'draw':
            session.h.b.set_reg('psw', session.h.b.get_reg('psw') | 0x40)
            session.open()
            session.press(0x23)
            closed = checkpoint(session)
        else:
            report['cache'], closed = cache_cases(cp, session)
            rs.save(cp.HERE / 'result.json', report)
        tracking = trace_irq(session)
        report['timing'] = {}
        if mode != 'draw':
            timing_cases(cp, session, closed, report['timing'])
        report['timing']['slow_draw'] = {}
        draw_case(cp, session, closed, report['timing']['slow_draw'])
        report['status'] = 'PASS'
    finally:
        if tracking is not None:
            report['irq_windows'] = tracking['windows']
        report['seconds'] = round(time.monotonic() - started, 3)
        report['batch_stats'] = dict(session.h.b.batch_stats)
        rs.save(cp.HERE / 'result.json', report)
        print('EXTRA_RESULT', unit, report.get('status', 'FAIL'), report['seconds'], flush=True)


if __name__ == '__main__':
    main()
