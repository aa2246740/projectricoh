"""Execute existing v3.6 and gen 117 bytes through native menu functions."""
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, ROOT, save, sha, verify_pins

TREE = ROOT / 'firmware/engine_v38_b36'
sys.path.insert(0, str(TREE))
spec = importlib.util.spec_from_file_location('r28_integration', TREE / 'integration_native.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
v, fr, pe = m.v, m.fr, m.pe
R = pe.ROOT_ADDR
EVENTS = {}
PUBLICATIONS = {}


def need(result):
    assert result.get('ok'), result
    return result


class ResearchProduct(m.Product):
    def _install(self):
        h = self.h
        original_put, original_write = h.put, h.b.write
        def put(address, value, n=4):
            if address != 0x2040f804:
                original_put(address, value, n)
        def write(address, data):
            if address not in (0x2040f81c, 0x2040f848):
                original_write(address, data)
        h.put, h.b.write = put, write
        try:
            super()._install()
        finally:
            h.put, h.b.write = original_put, original_write
        packet = bytearray(2048)
        packet[4:12] = self.identity[:8]
        packet[48:52] = self.identity[8:12]
        packet[2044:] = sum(packet[:2044]).to_bytes(4, 'big')
        self.device_packet = bytes(packet)
        h.b.map(0x20690000, self.device_packet + bytes(0x3000))
        self._native(0x20063f64, 'device_packet_buffer', lambda b: 0x20690000)
        def packet_copy(b):
            assert b.get_reg('r4') == 0x2040f818
            assert b.get_reg('r5') == 2048
            b.write(b.get_reg('r4'), self.device_packet)
            return 0
        self._native(0x2006c65c, 'device_packet_copy', packet_copy)
        self._native(0x2005e034, 'device_message_submit', lambda b: 0)


def configure():
    verify_pins()
    v.python_backend.CACHE = OUT / 'decode'
    pe.STAGED, pe.STAGED_SHA, pe.ENGINE_ELF = m.DAT, sha(m.DAT.read_bytes()), v.ENGINE_ELF
    pe.FileEdge, fr.Product = m.Files, ResearchProduct
    v.harness_mod.Harness = v.V35Harness
    syms = v.Elf(v.RESIDENT_ELF).symbols
    fr.OBSERVE = syms['rv_hook_observe']
    fr.LAND = {syms['rv_skip_06']: 'h06_skip', syms['rv_close_07']: 'h07_close',
               syms['rv_skip_08']: 'h08_skip', 0x202871dc: 'native_setter',
               0x202bb96c: 'native_h08'}


def set_ready(h, p, ready):
    need(fr.native(h, 0x200935b4, (ready,)))
    p.ready = ready
    assert h.u(0x200d7fd8) == ready


def set_link(h, p):
    need(fr.native(h, 0x200637e0))
    p.link = 1
    assert h.u(0x2040f804) == 1
    assert h.b.read(0x2040f81c, 8) == p.identity[:8]
    assert h.b.read(0x2040f848, 4) == p.identity[8:12]


def instrument(h):
    events = []
    publications = []
    def publication(event):
        publications.append(dict(address=hex(event.address), bytes=len(event.data), value=event.value,
                                 writer_pc=None if event.pc is None else hex(event.pc),
                                 origin=event.origin, phase=h.phase))
    h.b.add_write_trace(0x200d7fd8, 0x200d7fdc, publication)
    h.b.add_write_trace(0x2040f804, 0x2040f808, publication)
    PUBLICATIONS[id(h)] = publications
    def hook(b):
        events.append(dict(hook=b.get_reg('r1'), rows=h.u(0x2022f5ac, 1),
                           state=h.u(R+5, 1), ready=h.u(0x200d7fd8),
                           link=h.u(0x2040f804), phase=h.phase))
        return False
    h.b.add_breakpoint(h.symbols['rv_hook_observe'], hook)
    return events


def boot(ready=0, link=1):
    m.FS_SETUP = {'/ATA1/GXRCE.DAT': m.DAT.read_bytes()}
    h, p, w = fr.boot('28mm', ready=ready, link=link)
    assert 0x20271fec not in h.b.breakpoints
    assert 0x2009359c not in h.b.breakpoints
    assert h.u(0x200d7fd8) == h.u(0x2040f804) == 0
    events = instrument(h)
    set_ready(h, p, ready)
    if link:
        set_link(h, p)
    EVENTS[id(h)] = events
    return h, p, w


def snapshot(h, p):
    fields = fr.root_fields(h)
    array, count = h.u(0x205a27d8), h.u(0x205a27d4, 1)
    views = []
    if array and count <= 8:
        for i in range(count):
            views.append(dict(tag=h.u(array+8*i, 1), state=hex(h.u(array+8*i+4))))
    return dict(rows=h.u(0x2022f5ac, 1), names=hex(h.u(0x2022f5a8)),
                cursor=h.u(0x2022f726, 1), mode=h.u(h.settings+0x36e, 1),
                native_state=h.u(0x205d9c00), native_item=h.u(0x205d9bf8),
                overlay=h.u(0x2037f3bc), part=h.u(0x205a280f, 1), views=views,
                ready=h.u(0x200d7fd8), link=h.u(0x2040f804), root=fields,
                loads=h.b.visits[h.symbols['rv_load']],
                engine_calls=h.b.visits[h.symbols['rv_engine']],
                getter_visits=h.b.visits[0x20271fec],
                hooks=dict(Counter(str(e['hook']) for e in EVENTS[id(h)])),
                file_calls=len(p.native_log), rpc_calls=len(p.rpc.log))


def action(rec, label, h, p, fn):
    at = len(h.writes)
    publication_at = len(PUBLICATIONS[id(h)])
    before = snapshot(h, p)
    h.phase = label
    result = fn()
    if result is not None and isinstance(result, dict) and 'ok' in result:
        need(result)
    after = snapshot(h, p)
    writes = [e for e in h.writes[at:] if int(e['address'], 16) in
              (0x200d7fd8, 0x2040f804, 0x2022f5a8, 0x2022f5ac, h.settings+0x36e)]
    rec['steps'].append(dict(label=label, result=result, before=before, after=after, writes=writes,
                             publications=PUBLICATIONS[id(h)][publication_at:]))
    return after


def seven(state):
    assert state['rows'] == 7, state
    assert state['root']['state'] == 0 and state['root']['block'] == 0, state
    assert not (state['root']['flags'] & 32), state
    assert state['engine_calls'] == state['file_calls'] == state['rpc_calls'] == 0, state


def open_list(rec, h, p, w, expected):
    def opened():
        result, _, error = fr.publish(h, p, w)
        assert error is None, error
        return result
    state = action(rec, 'open Image settings', h, p, opened)
    if expected == 7:
        seven(state)
    else:
        assert state['rows'] == 8 and state['root']['state'] == 3, state
        assert state['engine_calls'] >= 3, state
    return state


def redraw(rec, h, p):
    array, count = h.u(0x205a27d8), h.u(0x205a27d4, 1)
    top = array+8*(count-1)
    assert h.u(top, 1) == 33
    state = h.u(top+4)
    before = sum(e['hook'] == 5 for e in EVENTS[id(h)])
    result = action(rec, 'native list redraw', h, p,
                    lambda: fr.native(h, 0x201fd360, (2, state, 0)))
    after = sum(e['hook'] == 5 for e in EVENTS[id(h)])
    assert after > before
    return result


def leave(rec, h, p):
    from exit_path import event
    return action(rec, 'native ADJ exit through event table', h, p, lambda: event(h, 0x2b))


def finish(rec, h, p):
    rec['hooks'] = EVENTS[id(h)]
    rec['file_observations'] = m.no_writes(p)
    rec['native_log'] = p.native_log
    rec['publication_writers'] = PUBLICATIONS[id(h)]
    assert rec['publication_writers']
    assert not any(e['writer_pc'] is None for e in rec['publication_writers']), rec['publication_writers']
    assert 0x20271fec not in h.b.breakpoints and not h.stub_hits.get('image_mode_getter', 0)
    rec['status'] = 'PASS'


def normal(rec):
    h, p, w = boot(1, 1)
    open_list(rec, h, p, w, 8)
    redraw(rec, h, p)
    finish(rec, h, p)


def late(rec, ready, link):
    h, p, w = boot(ready, link)
    open_list(rec, h, p, w, 7)
    if not ready:
        seven(action(rec, 'native ready publication', h, p, lambda: set_ready(h, p, 1)))
    if not link:
        seven(action(rec, 'native link publication', h, p, lambda: set_link(h, p)))
    seven(redraw(rec, h, p))
    for key in (0x20, 0x1f):
        seven(action(rec, 'native arrow '+hex(key), h, p, lambda key=key: fr.move_key(h, key)))
    seven(action(rec, 'native packet formatter H09', h, p,
                 lambda: fr.native(h, 0x2017098c, (0, 0x20691000))))
    leave(rec, h, p)
    action(rec, 'native parent page', h, p, h.parent)
    open_list(rec, h, p, w, 8)
    finish(rec, h, p)


def never(rec):
    h, p, w = boot(0, 0)
    open_list(rec, h, p, w, 7)
    seven(redraw(rec, h, p))
    for key in (0x20, 0x1f):
        seven(action(rec, 'native arrow '+hex(key), h, p, lambda key=key: fr.move_key(h, key)))
    leave(rec, h, p)
    action(rec, 'native parent page', h, p, h.parent)
    open_list(rec, h, p, w, 7)
    leave(rec, h, p)
    action(rec, 'native parent page', h, p, h.parent)
    action(rec, 'native ready publication away from Image', h, p, lambda: set_ready(h, p, 1))
    action(rec, 'native link publication away from Image', h, p, lambda: set_link(h, p))
    seven(action(rec, 'other native list constructor', h, p, h.leave_other_list))
    action(rec, 'native parent page', h, p, h.parent)
    open_list(rec, h, p, w, 8)
    finish(rec, h, p)


def panel(rec):
    h, p, w = boot(0, 1)
    open_list(rec, h, p, w, 7)
    action(rec, 'native ready publication', h, p, lambda: set_ready(h, p, 1))
    state = action(rec, 'native Fn2 entry H06', h, p, lambda: fr.native(h, 0x202be220))
    seven(state)
    finish(rec, h, p)


def scheduled(rec, address, expected):
    h, p, w = boot(0, 1)
    active = [True]
    schedule = []
    def callback(b):
        if not active[0]:
            return False
        active[0] = False
        core = b.core
        context = {k: copy.deepcopy(getattr(core, k)) for k in ('r', 'psw', 'bpsw', 'bbpsw', 'cr', 'acc', 'current_pc')}
        pc, running = b.pc, b.running
        before = snapshot(h, p)
        try:
            b.running = False
            set_ready(h, p, 1)
            schedule.append(dict(at=hex(address), before=before, after=snapshot(h, p)))
        finally:
            for key, value in context.items():
                setattr(core, key, value)
            b.pc, b.running = pc, running
        return False
    h.b.add_breakpoint(address, callback)
    open_list(rec, h, p, w, expected)
    assert not active[0]
    rec['schedule'] = schedule
    finish(rec, h, p)


CASES = {
    'ready-at-entry': normal,
    'ready-after-open': lambda r: late(r, 0, 1),
    'link-after-open': lambda r: late(r, 1, 0),
    'both-after-open': lambda r: late(r, 0, 0),
    'not-ready-before-exit': never,
    'late-ready-Fn2': panel,
    'ready-before-H01': lambda r: scheduled(r, 0x20287098, 8),
    'ready-after-H01': lambda r: scheduled(r, 0x202870a4, 7),
}


def run_case(name):
    record = dict(name=name, status='RUNNING', steps=[],
                  body_sha256=v.BODY_SHA, dat_sha256=pe.STAGED_SHA,
                  engine_elf_sha256=sha(pe.ENGINE_ELF.read_bytes()),
                  native_getter_fixed_result_removed=True,
                  ui_fields_assigned_by_research_script=False,
                  readiness_writers='native 0x200935b4 and native 0x200637e0')
    try:
        CASES[name](record)
    except Exception:
        record['status'] = 'FAIL'
        record['error'] = traceback.format_exc()
        save('native/'+name+'.json', record)
        print(json.dumps(dict(name=name, status='FAIL', error=record['error'])))
        raise
    save('native/'+name+'.json', record)
    print(json.dumps(dict(name=name, status=record['status'],
                          steps=[dict(label=s['label'], rows=s['after']['rows'],
                                      loads=s['after']['loads'], engine=s['after']['engine_calls']) for s in record['steps']])))


def main():
    configure()
    for name in sys.argv[1:]:
        run_case(name)


if __name__ == '__main__':
    main()
