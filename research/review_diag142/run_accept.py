"""Run the original assertions with outputs confined to this independent review."""
from pathlib import Path
import hashlib
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
unit, mode = sys.argv[1:3]
case = scope.HERE / 'cases' / (unit + '-' + mode)
case.mkdir(parents=True, exist_ok=True)
source = scope.ROOT / 'research/unit28_stock'
(case / 'rows-g137.json').write_text((source / 'rows-g137.json').read_text())
accept = scope.load(source / 'accept_diag38.py', 'review142_accept')
accept.HERE = case
accept.DAT = scope.ROOT / 'firmware/package_v38_diag/SD_ROOT/GXRCE.DAT'
base_boot = accept.boot
observations = []


def boot(unit, ready):
    m, h, p, w, syms = base_boot(unit, ready)
    settings = h.u(0x200c0dac)
    writes = []
    before = hashlib.sha256(h.b.read(settings,4096)).hexdigest()
    h.b.add_write_trace(settings, settings+4096,
                        lambda event: writes.append({'pc':hex(event.pc) if event.pc is not None else None,
                                                     'offset':event.address-settings,'bytes':len(event.data)}))
    observations.append((h,p,settings,before,writes))
    return m,h,p,w,syms


accept.boot = boot
sys.argv = [str(source/'accept_diag38.py'),unit,mode]
started = time.monotonic()
accept.main()
result = []
for h,p,settings,before,writes in observations:
    after = hashlib.sha256(h.b.read(settings,4096)).hexdigest()
    assert before == after and not writes, writes
    assert not any(e['cmd'] == 22 for e in p.rpc.log)
    result.append({'settings_before_sha256':before,'settings_after_sha256':after,
                   'settings_write_events':writes,'rpc_commands':sorted({e['cmd'] for e in p.rpc.log}),
                   'rpc_w':0})
scope.save(case/'review-observation.json',{'unit':unit,'mode':mode,'seconds':time.monotonic()-started,
                                        'dat_sha256':scope.sha(accept.DAT),'observations':result,
                                        'inputs_unchanged':scope.freeze_check()})
print('INDEPENDENT_REVIEW_DONE',unit,mode,'settings_write_events=0',flush=True)
