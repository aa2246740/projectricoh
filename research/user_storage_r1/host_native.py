#!/usr/bin/env python3
"""Bounded replay of official M32R wrappers; disk/locks remain explicit stubs."""
from pathlib import Path
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect

ROOT = collect.ROOT
OUT = collect.OUT
spec = importlib.util.spec_from_file_location(
    'storage_policy_cpu', ROOT / 'firmware/resident_v34c/policy_machine.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class Program:
    def __init__(self):
        self.name = 'official-storage-wrappers'
        self.image = collect.Image()
        self.symbols, self.code, self.width = {}, {}, {}
        for path in sorted(OUT.glob('*.asm.txt')):
            for line in path.read_text().splitlines():
                m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$', line)
                if not m:
                    continue
                pc, raw = int(m[1], 16), bytes.fromhex(m[2])
                assert self.image.raw(pc, len(raw)) == raw
                if len(raw) in (2, 4):
                    self.code[pc] = tuple(p.Program.parse(x) for x in re.split(r' -> | \|\| ', m[3]))
                    self.width[pc] = len(raw)

    def byte(self, address):
        try:
            return self.image.raw(address, 1)[0]
        except AssertionError:
            return 0


def signed(v):
    return v - (1 << 32) if v & (1 << 31) else v


class CPU(p.Cpu):
    def __init__(self, program):
        super().__init__(program)
        self.trace = []
        self.visits = []

    def op(self, name, args, pc):
        self.visits.append(pc)
        if name in ('st', 'sth', 'stb') and re.fullmatch(r'@[+-](?:r\d+|sp|fp|lr)', args[1]):
            size = 4 if name == 'st' else 2 if name == 'sth' else 1
            base = p.reg(args[1][2:])
            self.r[base] = (self.r[base] + (size if args[1][1] == '+' else -size)) & 0xffffffff
            self.write(self.r[base], self.r[p.reg(args[0])], size)
            return
        if name == 'add3':
            n = int(args[2].lstrip('#'), 0)
            if 0x8000 <= n <= 0xffff:
                n -= 0x10000
            self.r[p.reg(args[0])] = (self.r[p.reg(args[1])] + n) & 0xffffffff
            return
        if name in ('sll3', 'srl3', 'sra3'):
            x, n = self.r[p.reg(args[1])], int(args[2].lstrip('#'), 0)
            if name == 'sra3':
                x = signed(x)
            self.r[p.reg(args[0])] = (x << n if name == 'sll3' else x >> n) & 0xffffffff
            return
        if name in ('divu', 'remu', 'div', 'rem'):
            d, s = p.reg(args[0]), p.reg(args[1])
            x, y = self.r[d], self.r[s]
            if name in ('div', 'rem'):
                x, y = signed(x), signed(y)
                q = (abs(x) // abs(y)) * (-1 if (x < 0) != (y < 0) else 1)
            else:
                q = x // y
            self.r[d] = (x - q * y if name in ('rem', 'remu') else q) & 0xffffffff
            return
        if name in ('cmp', 'cmpi'):
            x = signed(self.r[p.reg(args[0])])
            y = int(args[1].lstrip('#'), 0) if name == 'cmpi' else signed(self.r[p.reg(args[1])])
            self.condition(x < y)
            return
        if name == 'not':
            self.r[p.reg(args[0])] = ~self.r[p.reg(args[1])] & 0xffffffff
            return
        return super().op(name, args, pc)

    def call(self, address, native_args=(), bound=250000):
        self.r[4:4+len(native_args)] = native_args
        self.p.symbols['entry'] = address
        return signed(self.run('entry', bound=bound))


def stub(cpu, address, name, value=0, hook=None):
    def f(c):
        c.trace.append(dict(name=name, address=hex(address), args=c.r[4:8]))
        result = hook(c) if hook else value
        c.r[0] = result & 0xffffffff
    cpu.stubs[address] = f


def wrapper(program, sectors=64, open_error=False):
    cpu = CPU(program)
    stub(cpu, 0x0500d4e4, 'lock')
    stub(cpu, 0x0500d4fc, 'unlock')
    stub(cpu, 0x200a531c, 'normalize')
    stub(cpu, 0x200a65f8, 'existing_lookup', -1 if open_error else 0)
    stub(cpu, 0x200a6750, 'lower_close')
    def geometry(c):
        c.seed(c.r[5], 0x20600000)
        c.seed(c.r[6], sectors, 2)
        return 0
    stub(cpu, 0x200ab4f0, 'fd_geometry', hook=geometry)
    result = cpu.call(0x200a40b4, (0x20620000, 2))
    assert result == (-1 if open_error else 0)
    return cpu


def lower_file(program, position=0, length=16384, sector_bytes=512, mode=0x82):
    """Model one pre-existing FAT file; execute real write/close control flow."""
    c = CPU(program)
    f, v = 0x204c8c78, 0x204c8a18
    c.seed(0x204c9206, 0, 1)
    c.seed(0x204c9207, 0, 1)
    c.seed(f+7, mode, 1)
    c.seed(f+124, position)
    c.seed(f+156, length)
    c.seed(f+168, 1)
    c.seed(f+202, 2, 2)
    c.seed(f+204, int.from_bytes(length.to_bytes(4, 'little'), 'big'))
    c.seed(v+172, sector_bytes, 2)
    c.seed(v+174, 1, 1)
    c.seed(v+196, sector_bytes, 2)
    c.seed(v+192, 100)
    c.seed(v+240, 20)
    stub(c, 0x200af828, 'fd_select', 0)
    stub(c, 0x200b10fc, 'media_io', 0)
    stub(c, 0x200b0240, 'chain_transition', 0)
    stub(c, 0x200ba1c8, 'media_buffer', 0x20630000)
    stub(c, 0x200b823c, 'directory_sector_write', 0)
    stub(c, 0x200b0c6c, 'timestamp_update', 0)
    stub(c, 0x200b7b10, 'chain_close_update', 0)
    stub(c, 0x200b71b0, 'directory_dirty', 0)
    stub(c, 0x200b8b40, 'directory_flush', 0)
    stub(c, 0x200b97d0, 'volume_flush', 0)
    stub(c, 0x200b8f88, 'fd_release', 0)
    stub(c, 0x200b9170, 'volume_release', 0)
    stub(c, 0x200b56c0, 'fat_finalize', 0)
    def le32(x):
        if x.r[4] == 1:
            value = int.from_bytes(x.read(x.r[5]).to_bytes(4, 'big'), 'little')
            x.seed(x.r[6], value)
        else:
            value = x.read(x.r[6])
            x.seed(x.r[5], int.from_bytes(value.to_bytes(4, 'little'), 'big'))
        return 0
    stub(c, 0x200b9c28, 'directory_le32', hook=le32)
    return c


def main():
    collect.preflight()
    program = Program()
    results = []
    for sectors in (8, 16, 32, 64, 128):
        c = wrapper(program, sectors)
        stub(c, 0x200a829c, 'lower_write_seek')
        stub(c, 0x200aad38, 'prefetch_buffer', 16384)
        stub(c, 0x200ab02c, 'lower_write', 32)
        pos = c.call(0x200a5080, (0, 8192, 0))
        assert pos == 8192
        for i in range(32):
            c.seed(0x20610000+i, 0xa5, 1)
        w = c.call(0x200a45e8, (0, 0x20610000, 32))
        assert w == 32
        closed = c.call(0x200a437c, (0,))
        assert closed == 0
        writes = [t for t in c.trace if t['name'] == 'lower_write']
        expected = 32 if sectors <= 16 else 8224
        assert len(writes) == 1 and writes[0]['args'][2] == expected
        results.append(dict(case='write_B_at_8192',buffer_bytes=sectors*512,
                            seek=pos,write=w,close=closed,lower_write_bytes=expected,
                            shares_A_buffer=sectors>16,trace=c.trace))
    c = wrapper(program, 64)
    stub(c, 0x200a829c, 'lower_write_seek_ERROR', -1)
    result = c.call(0x200a5080, (0, 32768, 0))
    assert result == 32768
    results.append(dict(case='write_seek_ignores_lower_failure_at_aligned_offset',
                        lower_result=-1,wrapper_result=result,trace=c.trace))
    for entry in (0x200a4f40,0x200a5080):
        c = wrapper(program,64)
        stub(c,0x200af828,'fd_select_ERROR',34)
        stub(c,0x200af4ec,'native_error',-1)
        result = c.call(entry,(0,32768,0))
        assert result == 32768
        assert c.read(0x204c8c78+124) == 0
        results.append(dict(case='seek_reports_target_after_real_lower_fd_error',
                            wrapper=hex(entry),requested=32768,result=result,
                            lower_position=0,trace=c.trace,
                            actual_lower_seek_executed=True))
    for fail in (False, True):
        c = wrapper(program, 64)
        stub(c, 0x200ab02c, 'lower_write', -1 if fail else 32)
        for i in range(32):
            c.seed(0x20610000+i, i, 1)
        assert c.call(0x200a45e8, (0, 0x20610000, 32)) == 32
        assert not any(t['name'] == 'lower_write' for t in c.trace)
        closed = c.call(0x200a437c, (0,))
        assert closed == (-1 if fail else 0)
        assert c.read(0x204c8668) == (1 if fail else 0)
        results.append(dict(case='dirty_close',injected_error=fail,close=closed,
                            remaining_wrapper_handles=c.read(0x204c8668),trace=c.trace))
    c = wrapper(program, open_error=True)
    assert c.read(0x204c8668) == 0
    assert not any(t['name'] == 'lower_write' for t in c.trace)
    results.append(dict(case='existing_open_failure_does_not_create',result=-1,trace=c.trace))
    for mode in (2, 0x82):
      for position in (0, 8192):
        for count in (32, 512):
            c = lower_file(program, position, mode=mode)
            written = c.call(0x200ab02c, (0, 0, count))
            assert written == count
            old_length_field = c.read(0x204c8c78+156)
            closed = c.call(0x200a6750, (0,))
            assert closed == 0
            final_size = int.from_bytes(c.read(0x204c8c78+204).to_bytes(4, 'big'), 'little')
            expected = position + count if count < 512 and mode == 2 else 16384
            assert final_size == expected, (position, count, final_size, expected)
            results.append(dict(case='official_lower_write_then_close',initial_size=16384,
                                mode=mode,position=position,count=count,write=written,close=closed,
                                length_field_after_write=old_length_field,
                                directory_size_after_close=final_size,
                                directory_write_calls=sum(t['name']=='directory_sector_write' for t in c.trace),
                                directory_flush_calls=sum(t['name']=='directory_flush' for t in c.trace),
                                volume_flush_calls=sum(t['name']=='volume_flush' for t in c.trace),
                                media_and_chain_helpers_are_stubs=True,trace=c.trace))
    collect.save('host-native-results.json', dict(
        status='PASS_BOUNDED_OFFICIAL_INSTRUCTIONS',
        instruction_bytes=sum(program.width.values()), cases=results,
        limits=['Disk, path normalization, geometry, locks and lower seek/read/write are explicit stubs.',
                'No FAT, NAND, power-loss, concurrency or camera claim.']))
    print('PASS', len(results), 'bounded official wrapper cases')
    for r in results:
        print(json.dumps({k:v for k,v in r.items() if k!='trace'}))


if __name__ == '__main__':
    main()
