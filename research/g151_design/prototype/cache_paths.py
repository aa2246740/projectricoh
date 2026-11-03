"""Read-only host observation for the g151 cursor-cache design (g150 test DAT, 50mm).

For each exit path: open the menu, optionally move, then exit; record which DAT entries ran, the H07 key
(args[13]), the cursor pair 0x2022F725/726, the cache 0x205A2944 and the active state before and after.
Also records, for UP/DOWN, the cache before the key, the cursor the stock handler wrote, and H08 args[8].
Writes only under the Scratch directory."""
import json, sys, os
from pathlib import Path
ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = Path(os.environ['TMPDIR']) / 'probe'
sys.path.insert(0, str(ROOT / 'research/g150/tests'))
import g139_host as H
H.LOCAL = OUT / 'host'
sys.path.insert(0, str(ROOT / 'research/review_g124'))
import native_sequence as NS
CACHE, A, B, STATE = 0x205A2944, 0x2022F725, 0x2022F726, 0x205A293C

def nat(cam):
    return dict(a=cam.h.u(A, 1), b=cam.h.u(B, 1), cache=cam.h.u(CACHE, 1), state=hex(cam.h.u(STATE)),
                rows=cam.h.u(0x2022F5AC, 1), dat_cur=cam.ui('cur') if cam.p.image_base else None,
                dat_phys=cam.ui('physical') if cam.p.image_base else None)

def instrument(cam, log):
    for name in ('ig_event', 'ig_apply', 'ig_panel_open', 'ig_panel_abort', 'ig_stop', 'ig_menu'):
        def entered(b, name=name):
            q = b.core.r[2]
            log.append(dict(entry=name, a8=cam.h.u(q + 40), a9=cam.h.u(q + 44), a13=cam.h.u(q + 60),
                            cursor=cam.h.u(B, 1), cache=cam.h.u(CACHE, 1)))
            return False
        cam.h.b.add_breakpoint(cam.symbol(name), entered)

def run(label, start, moves, exit_kind):
    cam = H.Camera('50mm')
    cam.h.b.write(A, bytes([start])); cam.h.b.write(B, bytes([start])); cam.h.b.write(CACHE, bytes([start]))
    before = nat(cam)
    cam.open_menu(); opened = nat(cam)
    log = []; instrument(cam, log)
    steps = []
    for k in moves:
        pre = nat(cam); cam.press(k); steps.append(dict(key=k, pre=pre, post=nat(cam), entries=list(log))); log.clear()
    pre_exit = nat(cam)
    if exit_kind == 'raw_half':
        NS.prepare_input(cam.h); NS.device_edges(cam.h, cam.p)
        r = NS.key(cam.h, cam.m.fr, 0x0d); detail = dict(logical=r['logical'])
    elif exit_kind == 'direct_half':
        for pc in (0x2029fdc4, 0x202bd724):
            assert cam.m.fr.native(cam.h, pc, (0x29, 0), steps=30000000)['ok']
        detail = {}
    else:
        key = dict(ok=0x23, adj=0x2b, menu=0x29, half0d=0x0d, half63=0x63)[exit_kind]
        assert cam.m.fr.press(cam.h, key, steps=30000000)['ok']; detail = dict(key=hex(key))
    after = nat(cam)
    row = dict(label=label, start=start, moves=moves, exit=exit_kind, before=before, opened=opened, steps=steps,
               pre_exit=pre_exit, exit_entries=list(log), after=after, detail=detail)
    print(json.dumps(row), flush=True)
    return row

def main():
    H.setup()
    rows = []
    rows.append(run('open-ok', 7, [], 'ok'))
    rows.append(run('nav-ok', 2, ['DOWN', 'DOWN'], 'ok'))
    rows.append(run('nav-menu', 6, ['DOWN', 'UP', 'UP'], 'menu'))
    rows.append(run('nav-raw-half', 3, ['DOWN'], 'raw_half'))
    rows.append(run('open-raw-half', 5, [], 'raw_half'))
    rows.append(run('nav-direct-half', 3, ['DOWN'], 'direct_half'))
    rows.append(run('nav-half0d', 4, ['UP'], 'half0d'))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'cache-paths.json').write_text(json.dumps(rows, indent=1) + '\n')

if __name__ == '__main__':
    main()
