"""Replay the native close handoff and a complete close with directory storage."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
import native_replay147 as basis


class CloseHandoff(Exception):
    pass


class CPU(basis.CPU):
    pause_close = False

    def op(self, name, args, pc):
        if self.pause_close and pc == 0x200a4460:
            raise CloseHandoff()
        return super().op(name, args, pc)


basis.CPU = CPU
rows = []
for dirty in (False, True):
    for mode in ('close_handoff', 'close_complete'):
        stage, calls = ['writer'], []
        c = basis.machine(dirty, stage, calls, volume_index=1)
        directory = 0x204c9228 + 4164 + 1588
        basis.replay.data(c, directory, bytes(512))
        c.seed(basis.F + 140, directory)
        c.pause_close = mode == 'close_handoff'
        stage[0] = 'writer_close'
        c.trace = []
        row = dict(initial_dirty=dirty, volume_index=1, mode=mode,
                   directory_buffer=hex(directory), directory_buffer_field=hex(basis.F + 140))
        try:
            result = c.call(0x200a437c, (0x81,))
            row['close_result'] = result
            row['close_returned'] = True
        except CloseHandoff:
            row['close_returned'] = False
            row['paused_pc'] = '0x200a4460'
        except Exception as error:
            row.update(status='INCOMPLETE', error=repr(error),
                       last_instructions=[(hex(a), n, list(x)) for a, n, x in list(c.ring)[-20:]],
                       registers=[hex(v) for v in c.r])
            rows.append(row)
            print(json.dumps(row), flush=True)
            continue
        row.update(open_count=c.read(basis.OPEN_COUNT), dirty_after_close_phase=c.read(basis.F + 700, 1),
                   native_slot_volume=c.read(basis.F + 4, 1), native_slot_index=c.read(basis.F + 6, 1),
                   close_phase_trace=c.trace[:],
                   close_phase_device_calls=[x for x in calls if x['stage'] == 'writer_close'])
        assert row['open_count'] == 0
        if mode == 'close_handoff':
            assert not row['close_returned'] and row['dirty_after_close_phase'] == 1
            assert row['native_slot_volume'] == 1 and row['native_slot_index'] == 0
            locks = [x['name'] for x in c.trace if x['name'] in ('wait47', 'signal47')]
            assert locks == ['wait47', 'signal47'], locks
        else:
            assert row['close_result'] == 0 and row['dirty_after_close_phase'] == 0
        row['diagnostic_gate_result'] = 'continue' if c.read(basis.OPEN_COUNT) == 0 else 'BUSY'
        c.pause_close = False
        row.update(basis.lookup(c, stage, calls, volume_index=1))
        row['status'] = 'PASS' if row['first_request'] == ('write' if mode == 'close_handoff' else 'read') else 'FAIL'
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if not k.endswith('trace')}), flush=True)
counts = {k: sum(row.get('status') == k for row in rows) for k in ('PASS', 'FAIL', 'INCOMPLETE')}
scope.save(HERE / 'close-window-results.json', dict(counts=counts, cases=rows,
           body_sha256=scope.sha(basis.collect.BODY),
           dat_sha256=scope.sha(scope.ROOT / 'firmware/package_v38_diag147/SD_ROOT/GXRCE.DAT'),
           limits=['Local synthetic FAT32 state; no physical medium.',
                   'Native writer, flush, close prefix, lookup and device dispatch execute checked original bytes.',
                   'The native close is paused before taking semaphore 47; a scheduling handoff is modeled.',
                   'Semaphore services, slot allocation, memory copy, writer media I/O and final device callbacks are modeled.',
                   'Lookup stops at the first device request.']))
print('CLOSE_WINDOW', counts, flush=True)
