"""Observe the complete bounded compensation path with a held stock lock."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g138_host as H

OUT = Path(__file__).resolve().parent
H.setup()
cam = H.Camera('50mm')
cam.put_s(0x6dd, bytes([10]))
cam.open_menu()
cam.set_lock(0)
before = cam.s_bytes(0, 4096)
stores = []
attempts = []
cam.h.b.add_write_trace(cam.s, cam.s + 4096,
                       lambda event: stores.append(dict(offset=event.address-cam.s,
                                                         bytes=len(event.data), origin=event.origin)))
def service(backend):
    if backend.get_reg('r0') == 6 and backend.get_reg('r1') == 2:
        attempts.append(cam.lock())
    return False
cam.h.b.add_breakpoint(cam.symbol('rv_call'), service)
writes, calls = cam.writes(), len(cam.p.rpc.log)
started = time.monotonic()
event = cam.m.fr.move_key(cam.h, 0x20, steps=400000000)
seconds = time.monotonic() - started
after = cam.check_frame()
assert event.get('ok'), event
assert not stores and before == cam.s_bytes(0, 4096)
assert cam.lock() == (0, 55) and len(attempts) == 7, (cam.lock(), attempts)
assert after['failed'] == 1 and after['labels'][0].startswith('ERR ')
result = dict(status='OBSERVED_M32R', dat_sha256=H.sha(H.DAT),
              S_store_count=len(stores), op2_attempts=len(attempts), compensations=len(attempts)-1,
              lock_after=cam.lock(), unit_writes=cam.writes()-writes,
              RPC=len(cam.p.rpc.log)-calls, host_wall_seconds=round(seconds, 3),
              physical_camera_seconds='NOT_MEASURED', state=after)
(OUT / 'evidence/held-lock.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
