"""Final-DAT lifecycle, key-action and diagnostic ambiguity probes. Host injection is explicit."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
source = scope.ROOT / 'research/unit28_stock'
a = scope.load(source / 'accept_diag143.py', 'review143_probes')
a.DAT = a.base.DAT = scope.ROOT / 'firmware/package_v38_diag143/SD_ROOT/GXRCE.DAT'
a.HERE = a.base.HERE = scope.SCRATCH / 'experiments'
a.HERE.mkdir(parents=True, exist_ok=True)
off = a.offsets()
layout = json.loads((a.ENGINE.parent / 'layout.json').read_text())
R, NAMES, ROWS = a.R, a.NAMES, a.ROWS
result = dict(dat_sha256=scope.sha(a.DAT), injection_boundary='host model, not camera events')


def boot(name):
    m, h, p, w, syms = a.base.boot('28mm', ready=1)
    setting = h.u(0x200c0dac)
    writes, frees, reads = [], [], set()
    state = dict(name=name)
    h.b.add_write_trace(setting, setting + 4096,
                        lambda e: writes.append(dict(pc=hex(e.pc) if e.pc is not None else None,
                                                     offset=e.address - setting, bytes=len(e.data),
                                                     value=int.from_bytes(e.data, 'big'))))

    def entered(b):
        block = h.u(R + 56)
        if block:
            p.image_base = h.u(block + 312)
            state.update(block=block, alloc_bytes=h.u(R + 108), block_bytes=h.u(R + 104))
        return False

    def freeing(b):
        frees.append(hex(b.get_reg('r4')))
        return False

    h.b.add_breakpoint(h.symbols['rv_invoke'], entered)
    h.b.add_breakpoint(0x2005c038, freeing)
    state.update(m=m, h=h, p=p, w=w, syms=syms, setting=setting, writes=writes, frees=frees)
    return state


def nb(s):
    return s['p'].image_base + s['p'].elf.symbols['n']


def field(s, name, size=1):
    return s['h'].u(nb(s) + off[name], size)


def overlay(s):
    h, at = s['h'], nb(s) + off['ov_rows']
    return [h.b.read(at + 9 * i, 9).split(b'\0', 1)[0].decode('ascii') for i in range(8)]


def snapshot(s):
    h = s['h']
    return dict(root_state=h.u(R + 5, 1), flags=hex(h.u(R + 212)),
                block=hex(h.u(R + 56)), check_failure=h.u(R + 152),
                names=hex(h.u(NAMES)), rows=h.u(ROWS, 1), cursor=h.u(0x2022f726, 1),
                image_mode=h.u(s['setting'] + 0x36e, 1), opens=field(s, 'opens', 4),
                refused=field(s, 'refused'), body_mask=field(s, 'body_mask'),
                dat_mask=field(s, 'dat_mask'), overlay_on=field(s, 'ov_on'), text=overlay(s))


def open_menu(s):
    s['h'].parent()
    value = s['m'].fr.native(s['h'], 0x20287080, steps=40000000)
    assert value.get('ok'), value
    return snapshot(s)


# Native S writes under a valid seven-row refusal overlay. A host hook forces
# part=0 only at the resident H01 entry; native constructor then pushes part 2.
s = boot('native-key-actions')
open_menu(s)
assert s['m'].fr.press(s['h'], 0x23, steps=40000000).get('ok')
armed = dict(on=False)


def part0(b):
    if armed['on'] and b.get_reg('r1') == 1:
        b.write(0x205a280f, bytes(1))
    return False


s['h'].b.add_breakpoint(s['syms']['rv_hook_observe'], part0)
armed['on'] = True
before = open_menu(s)
assert before['rows'] == 7 and before['overlay_on'] == 1 and before['body_mask'] == 4, before
armed['on'] = False
start = len(s['writes'])
move = s['m'].fr.move_key(s['h'], 0x20, steps=40000000)
after_move = snapshot(s)
key_writes = s['writes'][start:]
assert move.get('ok') and key_writes, (move, key_writes)
assert any(e['offset'] == 0x36e and e['pc'] == '0x20268774' for e in key_writes), key_writes
assert after_move['image_mode'] != before['image_mode'], (before, after_move)
start = len(s['writes'])
ok_result = s['m'].fr.press(s['h'], 0x23, steps=40000000)
after_ok = snapshot(s)
assert ok_result.get('ok')
result['native_keys'] = dict(injection='part=0 at H01; actual seven-row stock constructor continues',
                             before=before, move=move, after_move=after_move, s_writes=key_writes,
                             ok_s_writes=s['writes'][start:], after_ok=after_ok,
                             rpc_w=sum(e['cmd'] == 22 for e in s['p'].rpc.log),
                             files=s['m'].no_writes(s['p']))
print('KEY_ACTIONS', json.dumps(result['native_keys']), flush=True)

# Retire after init. The actual resident drops root.block but does not free it.
s = boot('init-retirement')
changed = dict(done=False)


def change_unit(b):
    if not changed['done'] and s['h'].u(R + 5, 1) == 3:
        b.write(0x2040f84a, bytes.fromhex('0001'))
        changed['done'] = True
    return False


s['h'].b.add_breakpoint(s['syms']['rv_check'], change_unit)
retired = open_menu(s)
assert retired['root_state'] == 6 and retired['block'] == '0x0' and retired['check_failure'] == 6, retired
assert retired['text'][1].endswith('C00') and retired['overlay_on'] == 1, retired
block, h = s['block'], s['h']
header = dict(address=hex(block), allocated=h.u(block - 8, 1), span=h.u(block - 4))
assert header['allocated'] == 1 and not s['frees'], (header, s['frees'])
orig_read = h.b.read
hits = set()
labels, glyphs = nb(s) + off['ov_labels'], nb(s) + off['ov_glyphs']


def traced_read(address, size):
    value = orig_read(address, size)
    if h.b.running and (labels <= address < labels + 32 or glyphs <= address < glyphs + 560 or address == NAMES):
        hits.add((h.b.pc, address, size))
    return value


h.b.read = traced_read
draw = s['m'].fr.native(h, 0x201fd360, (2, 0x2022f71c, 0), steps=40000000)
assert draw.get('ok'), draw
image_reads = sorted({hex(pc) for pc, address, size in hits if labels <= address < labels + 32})
start = len(s['writes'])
closed = s['m'].fr.press(h, 0x29, steps=40000000)
assert closed.get('ok'), closed
after_close = snapshot(s)
again = open_menu(s)
hits.clear()
h.leave_other_list()
other = dict(kind=h.u(0x2022f71c, 1), names=hex(h.u(NAMES)),
             overlay_label_reads=sorted({hex(pc) for pc, address, size in hits if labels <= address < labels + 32}))
assert other['kind'] == 2 and not other['overlay_label_reads'], other
h.b.read = orig_read
result['retirement'] = dict(retired=retired, allocation_after_retire=header, native_frees=s['frees'],
                            label_reader_pcs=image_reads, after_menu_close=after_close,
                            again=again, other_menu=other, menu_close_s_writes=s['writes'][start:],
                            files=s['m'].no_writes(s['p']))
print('RETIREMENT', json.dumps(result['retirement']), flush=True)

# A missing overlay is not proof that the DAT did not execute: UI_TEXT can
# reject its task-context guard after direct init conversion has succeeded.
s = boot('no-marker-despite-menu')
h = s['h']
h.b.breakpoints[0x2005f228] = []
h.stub(0x2005f228, 'nonzero_task_context', value=1)
plain = open_menu(s)
assert plain['opens'] == 1 and plain['root_state'] == 3 and plain['names'] == hex(a.STOCK) and plain['overlay_on'] == 0, plain
assert plain['dat_mask'] == 0x30, plain
result['plain_stock_counterexample'] = dict(injection='task_context=1 at native service boundary',
                                           observation=plain, s_writes=s['writes'],
                                           files=s['m'].no_writes(s['p']))
print('PLAIN_STOCK_COUNTEREXAMPLE', json.dumps(result['plain_stock_counterexample']), flush=True)
result['inputs_unchanged'] = scope.freeze_check()
scope.save(scope.HERE / 'experiments.json', result)
print('EXPERIMENTS_DONE', flush=True)
