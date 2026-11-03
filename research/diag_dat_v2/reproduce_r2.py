"""Record menu events and executed diagnostic entries without source output."""
from pathlib import Path
import contextlib
import hashlib
import io
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_call as legacy
import scope


def main():
    sys.addaudithook(legacy.fence)
    scope.freeze_check()
    support = legacy.load_path(scope.ROOT / 'research/diag_dat_v1/native_support.py')
    events = []
    calls = []
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        h, p, *_ = support['setup']('50mm')
        for name in ('ig_menu', 'ig_panel_open', 'ig_apply', 'ig_event', 'capture'):
            if name not in p.elf.symbols:
                continue
            pc = p.symbol_pc(name)
            def entered(b, name=name):
                calls.append(dict(entry=name, steps=b.total_steps))
                return False
            h.b.add_breakpoint(pc, entered)
        original = h.invoke
        def invoked(address, args=(), native=True, max_steps=100000):
            calls.append(dict(address=hex(address), args=list(args), native=native,
                              steps=h.b.total_steps))
            return original(address, args, native, max_steps)
        h.invoke = invoked
        for index, (event, expected) in enumerate([('open', 'A')]+[('disp', x) for x in 'BCDFHA']):
            at = len(calls)
            before = h.b.total_steps
            result = support['open_menu'](h, p) if event == 'open' else support['action'](h, p, event)
            rows = support['text_rows'](h, p)
            events.append(dict(index=index, event=event, expected_page=expected,
                               actual_page=rows[0][0], rows=rows,
                               steps=h.b.total_steps-before, path=calls[at:],
                               result=result))
    output = scope.HERE / 'reproduction-r2.json'
    if output.exists():
        output = scope.HERE / 'reproduction-check-r2.json'
    scope.save(output, dict(
        status='REPRODUCED' if any(e['actual_page'] != e['expected_page'] for e in events) else 'PASS',
        unit='50mm', dat_sha256=hashlib.sha256(p.dat).hexdigest(), events=events))
    print('REPRODUCTION_R2 RETURN 0 COUNT', len(events))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('REPRODUCTION_R2 RETURN 1 COUNT 0 TYPE', type(error).__name__)
        raise SystemExit(1)
