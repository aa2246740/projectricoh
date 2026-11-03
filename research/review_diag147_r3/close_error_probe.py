"""Record native close state after a modeled device write error."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
import native_replay147 as basis

rows = []
for dirty in (False, True):
    for error_code in (1, 25):
        stage, calls = ['writer'], []
        c = basis.machine(dirty, stage, calls, volume_index=1)
        directory = 0x204c9228 + 4164 + 1588
        basis.replay.data(c, directory, bytes(512))
        c.seed(basis.F + 140, directory)

        def write_error(cpu):
            calls.append(dict(kind='write', stage=stage[0], args=list(cpu.r[4:8]),
                              count=cpu.read(basis.OPEN_COUNT), dirty=cpu.read(basis.F+700, 1)))
            return error_code

        basis.native.stub(c, 0x200a3358, 'device_write_error', hook=write_error)
        stage[0] = 'close'
        result = c.call(0x200a437c, (0x81,))
        rows.append(dict(initial_dirty=dirty, device_error=error_code, close_result=result,
                         open_count=c.read(basis.OPEN_COUNT), dirty_after_close=c.read(basis.F+700, 1),
                         native_slot_volume=c.read(basis.F+4, 1), native_slot_index=c.read(basis.F+6, 1),
                         device_calls=[row for row in calls if row['stage'] == 'close']))
scope.save(HERE / 'close-error-observations.json', dict(status='OBSERVED', cases=rows,
           limits=['Synthetic volume; errors are return values from the final device callback.',
                   'This probe records resulting RAM and does not claim card consistency or a separate defect.']))
print(json.dumps(rows, indent=2))
