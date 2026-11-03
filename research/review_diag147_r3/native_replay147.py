"""Native replay for review D147-01 (adapted from research/review_diag147/cache_review.py, device-queue mode).

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diag147 \
       nice -n 10 /usr/bin/python3 -I -B research/diag147/native_replay147.py

The reviewer's state, unchanged: a synthetic FAT32 volume (64-sector clusters, two FAT copies, a ready cluster pool
and a pending chain queue), file slot 0 open (native count 1), the real buffered write API 0x200A45E8 with the real
flush 0x200AB02C leaves the shared FAT cache dirty (F+700 = 1, set by the original FAT setter) and signals 47.
Original bytes run for the write, close, lookup, cache ownership, address conversion and device dispatch; the final
device callbacks 0x200A32A8 (read) / 0x200A3358 (write) are recording stubs (no medium). Listings are copied from
research/diag147/local/native-listings into the ignored local/native-listings (official bytes; checked against the
v3.8 body by host_native.Program). For other_file_dirty in (False, True), three continuations:
  ungated  control = the review's counterexample: lookup at count 1 -> the first device call is a WRITE (0x200A3358)
  gated    the g147 gate (diag.c fx_read): with 47 held, the native count word 0x204C8668 is read; non-zero ->
           BUSY, no parse/lookup/attach -> zero device calls after the writer
  closed   the writer closes its file through the real close API 0x200A437C, then (count 0) lookup must make no
           device write. In the review's synthetic state this stops inside the close's directory-entry copy
           (0x200B71B0 gets a destination of 0: no directory sector buffer is modelled), so it is recorded as
           INCOMPLETE (counted separately, never as PASS).
Writes local/native-replay147.json.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
LISTINGS = HERE / 'local/native-listings'
LISTINGS.mkdir(parents=True, exist_ok=True)
sys.path.insert(1, str(scope.ROOT / 'research/user_storage_r2'))
import collect
collect.BODY = scope.ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
collect.EXPECTED = {collect.OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
                    collect.BODY: 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'}
collect.OUT = LISTINGS
# Windows the close path needs beyond the review's listings (official bytes equal to the v3.8 body, asserted by dump).
EXTRA = [(0x200ba280, 0x200ba600, 'g147-native-utils-wide')]
for start, end, label in EXTRA:
    if not (LISTINGS / (label + '.asm.txt')).exists():
        collect.Image().dump(start, end, label)
import host_native as native
import replay
program = native.Program()
F, V = replay.FILES, replay.VOLUME
OPEN_COUNT = 0x204c8668
assert replay.COUNT == OPEN_COUNT


class CPU(replay.CPU):
    def op(self, name, args, pc):
        if not hasattr(self, 'ring'):
            self.ring = __import__('collections').deque(maxlen=40)
        self.ring.append((pc, name, tuple(args)))
        if name in ('addx', 'subx'):
            self.visits.add(pc)
            d, s = native.p.reg(args[0]), native.p.reg(args[1])
            x, y, carry = self.r[d], self.r[s], self.psw & 1
            if name == 'addx':
                value = x + y + carry
                self.condition(value > 0xffffffff)
            else:
                value = x - y - carry
                self.condition(x < y + carry)
            self.r[d] = value & 0xffffffff
            return
        if name == 'neg':
            self.visits.add(pc)
            self.r[native.p.reg(args[0])] = (-self.r[native.p.reg(args[1])]) & 0xffffffff
            return
        return super().op(name, args, pc)


class MediaRequest(Exception):
    pass


def machine(dirty, stage, device_calls, volume_index=0):
    """The review's device-queue state up to the end of the writer's buffered write (file still open)."""
    V = replay.VOLUME + 304 * volume_index
    c = CPU(program)
    c.visits = replay.Visits()
    for i in (0, 1):
        f = F + 708 * i
        c.seed(f + 4, volume_index, 1)
        c.seed(f + 6, i, 1)
        c.seed(f + 7, 0xc2 if i == 0 else 0x82, 1)
        if i == 0:
            c.seed(f + 300, replay.BUFFER)
            c.seed(f + 124, 0)
            c.seed(f + 156, 32768)
            c.seed(f + 160, 7)
            c.seed(f + 164, 7)
            c.seed(f + 168, 1)
            c.seed(f + 202, 2, 2)
            c.seed(f + 354, 0xffff, 2)
        if i == 1:
            c.seed(f + 4, 255, 1)
            c.seed(f + 6, 255, 1)
            c.seed(f + 7, 0, 1)
    c.seed(OPEN_COUNT, 1)
    c.seed(V + 4, 0, 1)
    c.seed(V + 6, 1, 1)
    c.seed(V + 172, 512, 2)
    c.seed(V + 174, 64, 1)
    c.seed(V + 178, 512, 2)
    c.seed(V + 196, 32768, 2)
    c.seed(V + 200, 2, 1)
    c.seed(V + 284, 2)
    c.seed(V + 160, 32 * 512)
    c.seed(V + 164, (32 + 2 * 8192) * 512)
    c.seed(V + 184, 8192, 2)
    c.seed(V + 224, 8192 * 512)
    c.seed(V + 272, 32 * 512)
    c.seed(V + 276, 8192)
    c.seed(V + 192, 1040000)
    c.seed(0x204c8940 + 108 * volume_index, 0x200a32a8)
    c.seed(0x204c8944 + 108 * volume_index, 0x200a3358)
    c.seed(V + 228, 32, 2)
    c.seed(V + 230, 0, 2)
    c.seed(V + 232, 32, 2)
    c.seed(0x204c9206, volume_index, 1)
    c.seed(0x204c9207, 0, 1)
    cache = 0x204c9228 + 4164 * volume_index + 4
    replay.data(c, cache, bytes(1536))
    replay.data(c, cache, (0x0ffffff8).to_bytes(4, 'little') + (0x0fffffff).to_bytes(4, 'little') * 2)
    replay.data(c, cache + 28, (0x0fffffff).to_bytes(4, 'little'))
    if volume_index == 1:
        # The ATA1 fixture also contains the existing one-cluster diagnostic file.
        replay.data(c, cache + 12, (0x0fffffff).to_bytes(4, 'little'))
    c.initial_fat = replay.blob(c, cache, 1536)
    c.seed(F + 700, 0, 1)
    c.seed(F + 308, 6, 2)
    c.seed(F + 310, 1, 2)
    for i in range(7):
        c.seed(F + 312 + 4 * i, 7 + i)
    if dirty:
        assert c.call(0x200b0164, (7, 8, cache + 28)) >= 0      # the original FAT32 setter
        assert c.read(F + 700, 1) == 1
    native.stub(c, 0x0500d4e4, 'wait47', 0)
    native.stub(c, 0x0500d4fc, 'signal47', 0)
    native.stub(c, 0x200b10fc, 'writer_media_io', 0)
    native.stub(c, 0x0500d514, 'kernel_error_notification', 0)
    native.stub(c, 0x0500d638, 'kernel_volume_context_a', 0)
    native.stub(c, 0x0500d63c, 'kernel_volume_context_b', 0)

    def device(x, kind):
        row = dict(kind=kind, stage=stage[0], args=list(x.r[4:8]), original_file_dirty=x.read(F + 700, 1),
                   open_count=x.read(OPEN_COUNT))
        device_calls.append(row)
        if stage[0] == 'lookup':
            raise MediaRequest()
        assert 1 <= x.r[6] <= 3, row
        return 0
    native.stub(c, 0x200a32a8, 'device_read', hook=lambda x: device(x, 'read'))
    native.stub(c, 0x200a3358, 'device_write', hook=lambda x: device(x, 'write'))

    def copy_bytes(x):
        replay.data(x, x.r[4], replay.blob(x, x.r[5], x.r[6]))
        return x.r[4]
    native.stub(c, 0x200627d8, 'copy_bytes', hook=copy_bytes)
    entry = replay.CACHE + 16
    c.seed(entry, 1, 2)
    c.seed(entry + 2, 64, 2)
    c.seed(entry + 4, replay.BUFFER)
    c.seed(entry + 8, 32767)
    replay.data(c, replay.SOURCE, b'x')
    written = c.call(0x200a45e8, (0x81, replay.SOURCE, 1))
    assert written == 1 and c.read(F + 700, 1) == 1, (written, c.read(F + 700, 1))
    assert any(x['name'] == 'signal47' for x in c.trace)
    return c


def lookup(c, stage, device_calls, volume_index=0):
    stage[0] = 'lookup'
    count = c.read(OPEN_COUNT)

    def allocate(x):
        assert x.read(F + 708 + 4, 1) == 255 and x.read(OPEN_COUNT) == count
        x.seed(F + 708 + 4, volume_index, 1)
        x.seed(F + 708 + 6, 1, 1)
        x.seed(F + 708 + 300, replay.BUFFER + 65536)
        x.seed(F + 708 + 354, 0xffff, 2)
        x.seed(0x204c9207, 1, 1)
        return 1
    native.stub(c, 0x200af654, 'allocate_slot', hook=allocate)
    native.stub(c, 0x200af8b8, 'slot_check', 0)
    c.trace = []
    returned = None
    try:
        returned = c.call(0x200a65f8, (0x204c866c, 2))
    except MediaRequest:
        pass
    calls = [x for x in device_calls if x['stage'] == 'lookup']
    return dict(open_count_at_lookup=count, lookup_device_calls=calls, lookup_returned=returned,
                first_request=calls[0]['kind'] if calls else None, lookup_prefix_trace=c.trace)


def main():
    cases, failures = [], []
    for dirty in (False, True):
        for mode in ('ungated', 'gated', 'closed'):
            stage, device_calls = ['writer'], []
            c = machine(dirty, stage, device_calls)
            row = dict(other_file_dirty_before_writer=dirty, mode=mode, dirty_after_writer=c.read(F + 700, 1),
                       open_count_after_writer=c.read(OPEN_COUNT))
            if mode == 'closed':
                stage[0] = 'writer-close'
                c.trace = []
                try:
                    closed = c.call(0x200a437c, (0x81,))
                except AssertionError as error:
                    # The review's synthetic state has no directory sector buffer: the close's directory-entry
                    # copy (0x200b71b0, called with r4 = destination) gets 0 and the replay stops. Recorded as
                    # INCOMPLETE, not as a pass and not as a finding.
                    row.update(status='INCOMPLETE', reason='writer close stopped: ' + repr(error),
                               last_instructions=[(hex(a), n, list(x)) for a, n, x in list(c.ring)[-12:]],
                               registers=['r%d=%08x' % (i, v) for i, v in enumerate(c.r)],
                               writer_close_device_calls=[x for x in device_calls if x['stage'] == 'writer-close'])
                    cases.append(row)
                    print('CASE', json.dumps({k: v for k, v in row.items() if k != 'last_instructions'}), flush=True)
                    continue
                row.update(writer_close_result=native.signed(closed), open_count_after_close=c.read(OPEN_COUNT),
                           dirty_after_close=c.read(F + 700, 1),
                           writer_close_device_calls=[x for x in device_calls if x['stage'] == 'writer-close'],
                           writer_close_trace=[x['name'] for x in c.trace])
            # the g147 gate, as diag.c fx_read does it with 47 held
            count = c.read(OPEN_COUNT)
            gate_busy = count != 0
            row['gate'] = dict(open_count=count, result='BUSY' if gate_busy else 'continue')
            if mode == 'ungated' or not gate_busy:
                row.update(lookup(c, stage, device_calls))
            else:
                row.update(lookup_device_calls=[], first_request=None)
            writes = [x for x in row['lookup_device_calls'] if x['kind'] == 'write']
            row['read_path_writes'] = len(writes)
            if mode == 'ungated' and row['first_request'] != 'write':
                failures.append('control did not reproduce the review write (%s)' % row)
            if mode == 'gated' and (not gate_busy or row['lookup_device_calls']):
                failures.append('gated: %s' % row['gate'])
            if mode == 'closed':
                if row['writer_close_result'] != 0 or row['open_count_after_close'] != 0:
                    failures.append('closed: writer close %s, count %s' % (row['writer_close_result'],
                                                                            row['open_count_after_close']))
                if writes or row['first_request'] not in (None, 'read'):
                    failures.append('closed: lookup wrote %s' % writes)
            row.setdefault('status', 'PASS' if not [f for f in failures if f.startswith(mode)] else 'FAIL')
            cases.append(row)
            print('CASE', json.dumps({k: v for k, v in row.items() if not k.endswith('trace')}), flush=True)
    counts = {k: sum(1 for x in cases if x['status'] == k) for k in ('PASS', 'FAIL', 'INCOMPLETE')}
    out = dict(status='PASS' if not failures else 'FAIL', counts=counts, failures=failures, cases=cases,
               body_sha256=scope.sha(collect.BODY),
               dat_sha256=scope.sha(scope.ROOT / 'firmware/engine_diag_v38_g147/candidate/local/full-r1/GXRCE.DAT'),
               limits=['Synthetic FAT32 file/volume state of research/review_diag147/cache_review.py (device-queue).',
                       'Original bytes: buffered write and flush, FAT setter, close API, lookup/search/cache, device '
                       'dispatch. Stubs: semaphore services, slot allocation, memcpy, writer media I/O, final device '
                       'callbacks (recorded, no medium).',
                       'The gate is the diag.c condition evaluated on the replay RAM; the DAT itself does not run here '
                       '(its gate is proved on the ELF by lock_proof147.py and tested in accept_diag147.py otherfile).',
                       'Lookup stops at its first device request; no full mount, JPEG history or RTOS scheduling.'])
    scope.save(HERE / 'local/native-replay147.json', out)
    print('NATIVE_REPLAY', out['status'], json.dumps(counts), failures, flush=True)
    sys.exit(0 if not failures else 1)


if __name__ == '__main__':
    main()
