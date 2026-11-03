#!/usr/bin/env python3
"""Replay byte-checked official instructions with explicit storage boundaries."""
from pathlib import Path
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect
import host_native as native

COUNT = 0x204c8668
CACHE = 0x204c86ec
FILES = 0x204c8c78
VOLUME = 0x204c8a18
BUFFER = 0x204cbab0
SOURCE = 0x20640000


class CPU(native.CPU):
    def __init__(self, program):
        super().__init__(program)
        self.visits = set()
        self.steps = 0
        self.accesses = []

    def check(self, address, size, kind):
        assert 0x20000000 <= address < address + size <= 0x20800000
        assert not any(address < b and address + size > a for a, b in self.forbidden)

    def read(self, address, size=4):
        self.check(address, size, 'read')
        return int.from_bytes(bytes(self.mem[a] if a in self.mem else self.p.byte(a)
                                    for a in range(address, address + size)), 'big')

    def op(self, name, args, pc):
        self.steps += 1
        if name == 'srai':
            self.visits.add(pc)
            d = native.p.reg(args[0])
            self.r[d] = (native.signed(self.r[d]) >> int(args[1].lstrip('#'), 0)) & 0xffffffff
            return
        if name in ('ld', 'ldh', 'lduh', 'ldb', 'ldub') and re.fullmatch(r'@r\d+\+', args[1]):
            self.visits.add(pc)
            d, base = native.p.reg(args[0]), native.p.reg(args[1][1:-1])
            size = 4 if name == 'ld' else 2 if name in ('ldh', 'lduh') else 1
            address = self.r[base]
            value = self.read(address, size)
            if name in ('ldh', 'ldb') and value & (1 << (size * 8 - 1)):
                value -= 1 << (size * 8)
            self.r[base] = (address + size) & 0xffffffff
            self.r[d] = value & 0xffffffff
            return
        # native.CPU retains an append-based visit sink; use an adapter below.
        return super().op(name, args, pc)

    def call(self, address, args=(), bound=1500000):
        return super().call(address, args, bound)


class Visits(set):
    def append(self, pc):
        self.add(pc)


def cpu(program):
    c = CPU(program)
    c.visits = Visits()
    return c


def data(c, ptr, value):
    c.mem.update({ptr + i: b for i, b in enumerate(value)})


def blob(c, ptr, size):
    return bytes(c.read(ptr + i, 1) for i in range(size))


def setup(program, sectors=64, native_fd=0x81, buffer=None):
    c = cpu(program)
    index = native_fd - 0x81
    if buffer is None:
        buffer = BUFFER + 0x10000 * index
    f = FILES + 708 * index
    c.seed(VOLUME + 174, sectors, 1)
    c.seed(f + 300, buffer)
    c.seed(f + 4, 0, 1)
    c.seed(f + 6, index, 1)
    c.seed(0x204c9206, 0, 1)
    c.seed(0x204c9207, index, 1)
    for address, name in ((0x0500d4e4, 'lock'), (0x0500d4fc, 'unlock'),
                          (0x200a531c, 'normalize')):
        native.stub(c, address, name)
    native.stub(c, 0x200a65f8, 'existing_lookup', native_fd)

    def select(x):
        fd = x.r[4]
        assert fd in (0x81, 0x82)
        x.seed(0x204c9207, fd - 0x81, 1)
        return 0
    native.stub(c, 0x200af828, 'fd_select', hook=select)
    native.stub(c, 0x200a6750, 'lower_close')
    assert c.call(0x200a40b4, (0x20620000, 0)) == native_fd
    cache = CACHE + 16 * (native_fd & 15)
    assert c.read(cache + 2, 2) == sectors
    assert c.read(cache + 4) == buffer
    return c, cache


def sequential(program, bank_size, sectors, chunk, fd=0x81):
    c, cache = setup(program, sectors, fd)
    native_buffer = c.read(cache + 4)
    expected = bytes((i * 37 + (i >> 8) * 11 + 73) % 256 for i in range(bank_size))
    other_fd = 0x82 if fd == 0x81 else 0x81
    disks = {fd: bytearray([0xcc]) * bank_size,
             other_fd: bytearray([0x6d]) * bank_size}
    writes = []
    position = 0

    def write(x):
        nonlocal position
        target, ignored_pointer, n, _ = x.r[4:8]
        assert target == fd
        assert 0 <= position <= position + n <= bank_size
        # Official lower_write ignores r5 and obtains its buffer via file+300.
        # This boundary models only that private buffer and per-file cursor.
        payload = blob(x, native_buffer, n)
        disks[target][position:position + n] = payload
        writes.append(dict(fd=target, offset=position, size=n,
                           native_buffer=hex(native_buffer), caller_r5=hex(ignored_pointer),
                           sha256=hashlib.sha256(payload).hexdigest()))
        position += n
        return n

    native.stub(c, 0x200ab02c, 'lower_write', hook=write)
    for off in range(0, bank_size, chunk):
        payload = expected[off:off + chunk]
        data(c, SOURCE, payload)
        assert c.call(0x200a45e8, (fd, SOURCE, len(payload))) == len(payload)
    logical = c.read(cache + 8)
    assert c.call(0x200a437c, (fd,)) == 0
    assert logical == position == bank_size
    assert bytes(disks[fd]) == expected
    assert bytes(disks[other_fd]) == bytes([0x6d]) * bank_size
    assert c.read(COUNT) == 0
    assert not any(0x200a4f40 <= v < 0x200a51d0 for v in c.visits)
    assert sum(w['size'] for w in writes) == bank_size
    return dict(case='sequential_two_file_boundary', bank_bytes=bank_size,
                Q=sectors * 512, chunk_bytes=chunk, fd=fd,
                result='PASS', exact_content=True, other_file_unchanged_in_model=True,
                seek_instruction_visits=0, writes=writes,
                official_steps=c.steps, real_geometry_executed=True,
                boundary='lookup, fd-select, locks, lower-close and disk are stubs')


def handle_cases(program):
    rows = []
    c, cache = setup(program, 1)
    data(c, SOURCE, bytes([0xa5]) * 32)
    native.stub(c, 0x200ab02c, 'lower_write_ERROR', -1)
    assert c.call(0x200a45e8, (0x81, SOURCE, 32)) == 32
    assert c.call(0x200a437c, (0x81,)) == -1
    assert c.read(COUNT) == 1
    rows.append(dict(case='dirty_close_error', wrapper_count=1, trace=c.trace))
    # Native lower-close is called on the failure branch, but the wrapper count is not decremented.
    native.stub(c, 0x200a65f8, 'existing_lookup_second', 0x82)
    c.seed(FILES + 708 + 300, BUFFER + 65536)
    assert c.call(0x200a40b4, (0x20620000, 0)) == 0x82
    assert c.call(0x200a45e8, (0x82, SOURCE, 32)) == 32
    assert c.call(0x200a437c, (0x82,)) == -1
    assert c.read(COUNT) == 2
    old = len(c.trace)
    assert c.call(0x200a40b4, (0x20620000, 0)) == -1
    assert c.call(0x200a544c, (0x20620000, 2)) == -1
    assert len(c.trace) == old
    rows.append(dict(case='two_leaks_block_open_and_create', wrapper_count=2,
                     lower_calls_after_exhaustion=0, trace=c.trace))
    c, cache = setup(program, 1)
    c.stubs.pop(0x200a6750)
    native.stub(c, 0x200af828, 'fd_select_ERROR', 34)
    assert c.call(0x200a437c, (0x81,)) == -1
    assert c.read(COUNT) == 0
    rows.append(dict(case='wrapper_count_zero_after_lower_close_error',
                     wrapper_count=0, actual_lower_close_error_branch=True,
                     native_slot_volume=c.read(FILES + 4, 1),
                     native_slot_index=c.read(FILES + 6, 1), trace=c.trace))
    c, cache = setup(program, 1)
    data(c, SOURCE, bytes([0xa5]) * 512)
    native.stub(c, 0x200ab02c, 'lower_write_SHORT', 511)
    assert c.call(0x200a45e8, (0x81, SOURCE, 512)) == 512
    assert c.call(0x200a437c, (0x81,)) == 0
    rows.append(dict(case='positive_lower_short_write_is_not_detected_by_wrapper',
                     requested=512, actual_boundary_return=511, wrapper_return=512,
                     close=0, trace=c.trace))
    return rows


def main():
    collect.preflight()
    program = native.Program()
    rows = []
    for bank in (8192, 16384):
        for sectors in (1, 2, 3, 5, 8, 16, 32, 64, 128, 255):
            rows.append(sequential(program, bank, sectors, 512))
        for sectors in (1, 16, 64):
            rows.append(sequential(program, bank, sectors, bank, 0x82))
    for bank, sectors in ((32768, 64), (65536, 128)):
        rows.append(sequential(program, bank, sectors, 512))
    rows.extend(handle_cases(program))
    collect.save('replay-results.json', dict(
        status='PASS_BOUNDED_OFFICIAL_INSTRUCTIONS', cases=rows,
        count=len(rows), instruction_bytes=sum(program.width.values()),
        limits=['Per-file lower-write model assumes a valid existing chain and correct native media driver.',
                'No physical FAT, SD controller, concurrent task, RTOS timing, camera or power-loss proof.']))
    print('PASS', len(rows), 'bounded official instruction cases')
    for r in rows:
        print(json.dumps({k: v for k, v in r.items() if k not in ('trace', 'writes')}))


if __name__ == '__main__':
    main()
