#!/usr/bin/env python3
"""Execute frozen final instruction bytes in bounded, declared subsets."""
import importlib.util
import json
import pathlib
import random
import re
import struct

HERE = pathlib.Path(__file__).resolve().parent
LOCAL = HERE / 'local'
spec = importlib.util.spec_from_file_location('review_collect', HERE / 'review.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def irq():
    results = []
    canonical = None
    for label, rel in [('resident', r.ELF), ('services', 'firmware/resident_v3/local/resident/engine-services/services-linkcheck.elf')]:
        data = (LOCAL / 'frozen' / rel).read_bytes()
        sections, symbols = r.elf_parse(data)
        sec = sections['.payload']
        def read(name, size):
            va = symbols[name]['va']
            off = sec['offset'] + va - sec['va']
            return data[off:off+size], va
        code, va = read('rv_irq_save', 12)
        restore, rva = read('rv_irq_restore', 4)
        if canonical is None:
            canonical = code, restore
        assert (code, restore) == canonical
        results.append(dict(name=label, address=va, save_bytes=code.hex(), restore_address=rva, restore_bytes=restore.hex()))
    for path in sorted((LOCAL / 'frozen/firmware/resident_v3/local').rglob('GXRCE.DAT')):
        data = path.read_bytes()
        start, size = struct.unpack_from('>II', data, 132)
        at = data.find(canonical[0]+canonical[1], start, start+size)
        assert at >= 0 and data.find(canonical[0]+canonical[1], at+1, start+size) < 0
        results.append(dict(name=path.parts[-2], address=at, save_bytes=canonical[0].hex(), restore_bytes=canonical[1].hex()))
    save, restore = canonical
    # Decode both register fields and the logical opcode from the actual word.
    mvfc, rhs = struct.unpack('>HH', save[:4])
    op = int.from_bytes(save[4:8], 'big')
    mvtc, ret = struct.unpack('>HH', save[8:])
    assert mvfc & 0xf0f0 == 0x1090 and (mvfc & 15) == 0 and rhs == 0xf000
    assert op & 0xf0f00000 == 0x80c00000
    assert mvtc & 0xf0f0 == 0x10a0 and ret & 0xfff0 == 0x1fc0 and ret & 15 == 14
    restore_op, restore_ret = struct.unpack('>HH', restore)
    assert restore_op & 0xf0ff == 0x10a0 and restore_ret == ret
    for row in results:
        for psw in range(65536):
            regs = [0]*16
            regs[(mvfc >> 8) & 15] = psw
            regs[(op >> 24) & 15] = regs[(op >> 16) & 15] & (op & 65535)
            masked = regs[mvtc & 15]
            assert regs[0] == psw and masked == (psw & ~0x40)
            restored = regs[restore_op & 15]
            assert restored == psw
        row['raw_psw_vectors'] = 65536
    nested = []
    for psw in (0, 1, 0x40, 0x41, 0x80, 0x81, 0xc0, 0xc1):
        outer, inner = psw, psw & (op & 65535)
        assert not inner & 0x40 and (inner & (op & 65535)) == inner
        nested.append(dict(incoming=psw, after_inner_restore=inner, after_outer_restore=outer))
    r.save('irq-independent.json', dict(artifacts=results, nested=nested, native_cpu=False,
           limitations='Instruction semantics only. No interrupt delivery, PSW banking, pipeline or cache model.'))
    print('IRQ_FINAL_BYTES_PASS artifacts=%d raw_vectors=%d' % (len(results), 65536*len(results)))


def replay():
    source = (LOCAL / 'frozen/research/review_flash_v2/local/m32r_replay.py').read_text()
    definition = source[source.index('def sign('):source.index('\ncases=0')]
    data = (LOCAL / 'frozen' / r.ELF).read_bytes()
    sections, symbols = r.elf_parse(data)
    sec = sections['.payload']
    namespace = dict(struct=struct, random=random, SEC=sec,
                     CODE=data[sec['offset']:sec['offset']+sec['size']], OBSERVE=symbols['rv_hook_observe']['va'])
    exec(definition, namespace)
    Base = namespace['Machine']
    class Machine(Base):
        def __init__(self, *args, edit=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.edit = edit
        def run(self, start, end):
            self.pc = start
            for _ in range(256):
                if self.pc == end:
                    return
                if self.pc == namespace['OBSERVE']:
                    self.ids.append(self.r[1]); ret = self.r[14]; frame = self.r[2]
                    for i in range(14):
                        self.r[i] = self.rng.getrandbits(32)
                    self.psw ^= 1
                    if self.edit:
                        for index, value in self.edit.items():
                            self.mem[frame+4*index] = value
                    self.pc = ret
                    continue
                word = self.read(self.pc); target = self.word(word)
                self.pc = self.pc+4 if target is None else target
            raise AssertionError('instruction bound')
    count = 0; skip_count = 0; rows = []
    for h in json.loads((LOCAL / 'hooks.json').read_text()):
        if not h['changed']:
            continue
        hook = h['number']
        for psw in (0, 1, 0x40, 0x41, 0x80, 0x81, 0xc0, 0xc1):
            for seed in range(16):
                rng = random.Random(seed)
                regs = [rng.getrandbits(32) for _ in range(16)]
                regs[14], regs[15] = 0x20301234, 0x05017ffc
                expected = Machine(regs, psw, {}, seed)
                displaced = bytes.fromhex(h['original'])
                for off in range(0, len(displaced), 4):
                    expected.pc = h['va']+off
                    assert expected.word(struct.unpack_from('>I', displaced, off)[0]) is None
                actual = Machine(regs, psw, {}, seed)
                actual.run(h['target'], h['resume'])
                assert actual.r == expected.r and actual.psw == expected.psw and actual.ids == [hook]
                for address, value in actual.mem.items():
                    if address >= actual.r[15]:
                        assert value == expected.mem.get(address, 0xdeadbeef)
                count += 1
                if hook == 9:
                    continue
                targets = {1:0x202870a8, 2:0x20287118, 5:0x201febec, 6:0x202be6a8, 7:regs[14], 8:0x202bcf58}
                edit = {1:symbols['rv_skip_%02d' % hook]['va']}
                expected_regs = list(regs)
                if hook == 1:
                    edit[15] = 5; expected_regs[0] = 5
                if hook == 2:
                    edit[7] = regs[0]; expected_regs[8] = regs[0]
                if hook == 5:
                    edit[13] = 0x20710000; expected_regs[2] = 0x20710000
                if hook in (6, 8):
                    edit[7] = 0; expected_regs[8] = 0
                if hook == 7:
                    edit[15] = 0; expected_regs[0] = 0
                actual = Machine(regs, psw, {}, seed, edit=edit)
                actual.run(h['target'], targets[hook])
                assert actual.r == expected_regs and actual.psw == psw and actual.ids == [hook]
                skip_count += 1
        rows.append(dict(hook=hook, default_vectors=128, consumed_vectors=128 if hook != 9 else 0))
    r.save('replay-independent.json', dict(default_vectors=count, consumed_vectors=skip_count, hooks=rows,
           interpreter='Frozen v2 review subset, reviewed and extended for consumed branches', native_cpu=False,
           limitations='Observer C is intercepted. No ACC, interrupts, banked stacks, cache, native ABI callees or task concurrency.'))
    print('REPLAY_FINAL_BYTES_PASS default=%d consumed=%d' % (count, skip_count))


if __name__ == '__main__':
    r.preflight()
    irq()
    replay()
