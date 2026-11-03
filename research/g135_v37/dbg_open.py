"""Diagnostic postcheck: UI/native state after the optional H01 restore, then the slot-4 DISP open."""
from pathlib import Path
import json
import os
import runpy
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def run(context, arguments, out, sessions):
    unit = arguments[arguments.index('--unit') + 1]
    products = [item for session in sessions for item in (session if isinstance(session, tuple) else (session,))
                if hasattr(item, 'image_base') and hasattr(item, 'rpc')]
    p = next(item for item in products if item.image_base)
    h = p.h
    if os.environ.get('DBG_RESTORE', '1') == '1':
        runpy.run_path(str(HERE / 'capture_state.py'))['h01_restore'](p, unit, out)
    adapter = json.loads((HERE / 'adapter-layout.json').read_text())
    n = p.image_base + next(v for k, v in p.elf.symbols.items() if k == 'n' or k.startswith('n.lto_priv.'))
    ui = n + adapter['ui']
    def get(name):
        return h.u(ui + adapter['ui.' + name], 1)
    log = []
    def state(tag):
        names = ('screen', 'cur', 'top', 'physical', 'count')
        log.append(dict(tag=tag, ui={x: get(x) for x in names},
            part=h.u(0x205a280f, 1), views=h.u(0x205a27d4, 1), rows=h.u(0x205d9bf8), overlay=h.u(0x2037f3bc),
            cursor_native=h.u(0x2022f726, 1)))
    state('after-restore')
    def call(slot, values=()):
        r = p.engine(slot, list(values))
        log.append(dict(call=slot, result={k: v for k, v in r.items() if isinstance(v, (int, str, bool))}))
    if os.environ.get('DBG_SKIPMENU') != '1':
        call(1)
    state('after-menu')
    for _ in range(6):
        cur = get('cur')
        if cur == 3:
            break
        physical = (get('physical') + (1 if cur < 3 else -1)) % 8
        h.put(0x2022f726, physical + 1, 1)
        call(6, [physical])
        state('after-arrow')
    call(3)
    state('after-disp')
    (out / ('dbg-' + os.environ.get('DBG_TAG', 'x') + '.json')).write_text(json.dumps(log, indent=1) + '\n')
