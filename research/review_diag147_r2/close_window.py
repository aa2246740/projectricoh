"""Replay the native close count-decrement window using byte-checked instructions."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
import native_replay147 as base


class PauseClose(Exception):
    pass


class CPU(base.CPU):
    def op(self, name, args, pc):
        if getattr(self, 'pause_close', False) and pc == 0x200a4460:
            self.pause_close = False
            raise PauseClose()
        return super().op(name, args, pc)


base.CPU = CPU
rows = []
for initial_dirty in (False, True):
    stage, calls = ['writer'], []
    writer = base.machine(initial_dirty, stage, calls)
    lock = {'held': False}
    events = []

    def wait(cpu):
        assert not lock['held']
        lock['held'] = True
        events.append({'operation': 'wait47', 'count': cpu.read(base.OPEN_COUNT),
                       'dirty': cpu.read(base.F + 700, 1)})
        return 0

    def signal(cpu):
        assert lock['held']
        lock['held'] = False
        events.append({'operation': 'signal47', 'count': cpu.read(base.OPEN_COUNT),
                       'dirty': cpu.read(base.F + 700, 1)})
        return 0

    base.native.stub(writer, 0x0500d4e4, 'wait47', hook=wait)
    base.native.stub(writer, 0x0500d4fc, 'signal47', hook=signal)
    stage[0] = 'writer-close'
    writer.pause_close = True
    try:
        writer.call(0x200a437c, (0x81,))
        raise AssertionError('close returned without pause')
    except PauseClose:
        pass
    state = {'pause_before': '0x200a4460', 'count': writer.read(base.OPEN_COUNT),
             'dirty': writer.read(base.F + 700, 1), 'lock_held': lock['held'],
             'slot0_volume': writer.read(base.F + 4, 1),
             'slot0_index': writer.read(base.F + 6, 1),
             'slot1_volume': writer.read(base.F + 708 + 4, 1)}
    assert state['count'] == 0 and state['dirty'] == 1 and not state['lock_held'], state
    # A separate task has a separate register/stack state, sharing filesystem RAM.
    reader = CPU(base.program)
    reader.visits = base.replay.Visits()
    reader.mem = writer.mem.copy()
    reader.stubs = writer.stubs.copy()
    reader.r[15] = 0x206dfffc
    # The diagnostic's try47 can succeed because the native writer released 47.
    lock['held'] = True
    gate = reader.read(base.OPEN_COUNT)
    assert gate == 0
    result = base.lookup(reader, stage, calls)
    assert result['first_request'] == 'write', result
    rows.append({'initial_dirty': initial_dirty, 'status': 'REPRODUCED',
                 'state_at_preemption': state, 'close_lock_events': events,
                 'writer_close_visits': [hex(pc) for pc in sorted(writer.visits)
                                         if 0x200a437c <= pc < 0x200a449c],
                 'gate_count': gate, 'gate_result': 'continue', **result})
    print(json.dumps({k: v for k, v in rows[-1].items() if not k.endswith('trace')}, indent=1))

scope.save(HERE / 'close-window.json', {
    'status': 'REPRODUCED', 'cases': rows,
    'body_sha256': scope.sha(base.collect.BODY),
    'dat_sha256': scope.sha(scope.ROOT / 'firmware/package_v38_diag147/SD_ROOT/GXRCE.DAT'),
    'limits': [
        'Synthetic FAT32 state retained from the previous review and implementer replay.',
        'Native buffered write/flush and native close run through the actual decrement store.',
        'Semaphore services, slot allocation, memcpy, writer media IO and device callbacks are explicit models.',
        'Task preemption is inserted before 0x200a4460; no RTOS scheduler or physical medium runs.',
        'The diagnostic gate is evaluated on RAM; independent ELF analysis binds its condition to the packaged DAT.',
        'Lookup stops at its first device request, whose read/write selection runs native dispatch.'
    ]})
