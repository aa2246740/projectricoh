"""Check the two native callbacks assigned to the ADJ exit event."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))


def event(h, key):
    from field_replay import native
    state = h.u(0x205d9c00)
    table = h.u(0x2037f658+4*state)
    for i in range(128):
        at = table+12*i
        value = h.u(at)
        if value == key:
            callbacks = (h.u(at+4), h.u(at+8))
            break
        assert value, (state, key)
    else:
        raise AssertionError('native event table limit')
    rows = []
    for entry in callbacks:
        result = native(h, entry, (key,))
        assert result.get('ok'), result
        rows.append(dict(entry=hex(entry), result=result, state=h.u(0x205d9c00)))
    return dict(ok=True, source_state=state, key=hex(key), callbacks=rows)


def scenario(record):
    import native_cases as n
    h, p, w = n.boot(0, 1)
    n.open_list(record, h, p, w, 7)
    n.action(record, 'native ADJ event callbacks', h, p, lambda: event(h, 0x2b))
    n.finish(record, h, p)


if __name__ == '__main__':
    import native_cases as n
    n.configure()
    n.CASES['ADJ-exit-path'] = scenario
    n.run_case('ADJ-exit-path')
