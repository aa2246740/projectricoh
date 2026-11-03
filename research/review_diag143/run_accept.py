"""Run existing g143 assertions against the packaged DAT with independent observations."""
from pathlib import Path
import hashlib
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
unit, mode = sys.argv[1:3]
source = scope.ROOT / 'research/unit28_stock'
case = scope.SCRATCH / (unit + '-' + mode)
case.mkdir(parents=True, exist_ok=True)
accept = scope.load(source / 'accept_diag143.py', 'review143_accept')
accept.HERE = accept.base.HERE = case
accept.DAT = accept.base.DAT = scope.ROOT / 'firmware/package_v38_diag143/SD_ROOT/GXRCE.DAT'
original_boot = accept.base.boot
observations = []


def boot(unit, ready):
    m, h, p, w, syms = original_boot(unit, ready)
    settings = h.u(0x200c0dac)
    writes, close_records, ascii_calls = [], [], []
    before = hashlib.sha256(h.b.read(settings, 4096)).hexdigest()
    h.b.add_write_trace(settings, settings + 4096,
                        lambda e: writes.append(dict(pc=hex(e.pc) if e.pc is not None else None,
                                                     offset=e.address - settings, bytes=len(e.data))))
    original_press = m.fr.press

    def press(hh, key, **kwargs):
        result = original_press(hh, key, **kwargs)
        close_records.append(dict(key=hex(key), names=hex(h.u(accept.NAMES)),
                                  rows=h.u(accept.ROWS, 1), state=h.u(accept.R + 5, 1),
                                  restore0=hex(h.u(accept.R + 156))))
        return result

    m.fr.press = press

    def ascii_enter(b):
        ascii_calls.append(dict(root_state=h.u(accept.R + 5, 1), flags=hex(h.u(accept.R + 212)),
                                source=hex(b.get_reg('r4')), count=b.get_reg('r5'),
                                target=hex(b.get_reg('r6'))))
        return False

    h.b.add_breakpoint(0x201d73e0, ascii_enter)
    observations.append((h, p, settings, before, writes, close_records, ascii_calls))
    return m, h, p, w, syms


accept.base.boot = boot
sys.argv = [str(source / 'accept_diag143.py'), unit, mode]
started = time.monotonic()
accept.main()
result = []
for h, p, settings, before, writes, close_records, ascii_calls in observations:
    after = hashlib.sha256(h.b.read(settings, 4096)).hexdigest()
    assert before == after and not writes, writes
    assert not any(e['cmd'] == 22 for e in p.rpc.log)
    result.append(dict(settings_before_sha256=before, settings_after_sha256=after,
                       settings_write_events=writes, rpc_commands=sorted({e['cmd'] for e in p.rpc.log}),
                       close_records=close_records, ascii_calls=ascii_calls))
out = scope.HERE / 'cases' / (unit + '-' + mode)
out.mkdir(parents=True, exist_ok=True)
report = json.loads((case / ('local/accept143-%s-%s.json' % (unit, mode))).read_text())
scope.save(out / 'accept.json', report)
scope.save(out / 'observation.json', dict(unit=unit, mode=mode, seconds=time.monotonic() - started,
                                        dat_sha256=scope.sha(accept.DAT), observations=result,
                                        inputs_unchanged=scope.freeze_check()))
print('INDEPENDENT_REVIEW_DONE', unit, mode, 'settings_write_events=0', flush=True)
