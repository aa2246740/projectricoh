"""Final-image byte binding and instruction-level control-flow utilities."""
from pathlib import Path
import bisect
import json
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_scope import ROOT, SOURCE, OUT, load, save, sha

audit = load(ROOT / 'research/review_g117_codegen/audit.py', 'review_elf_reader')
COND = {'bc', 'bnc', 'beq', 'bne', 'beqz', 'bnez', 'bgtz', 'blez', 'bltz', 'bgez'}
BRANCH = COND | {'bl', 'bra'}
TREES = {118: 'engine_v39_ux', 119: 'engine_v40_ux', 120: 'engine_v42_ux'}


class Image:
    def __init__(self, generation):
        self.generation = generation
        self.source = SOURCE / 'previous_delta' if generation == 118 else SOURCE
        self.elf = audit.Elf(ROOT / 'firmware' / TREES[generation] /
                             'candidate/local/full-r13/engine.elf')
        self.raw = json.loads((self.source / f'decode{generation}.json').read_text())
        self.asm = (self.source / f'engine{generation}.asm').read_text()
        self.relocations = {int(m[1], 16): (m[2], m[3]) for m in re.finditer(
            r'^\s*([0-9a-f]+): (R_M32R_[A-Z0-9_]+)\s+(.+)$', self.asm, re.M)}
        self.rows = {}
        for text, row in self.raw.items():
            pc = int(text)
            raw = bytes.fromhex(row['raw'])
            assert raw == self.elf.bytes(pc, len(raw)), (generation, hex(pc))
            parts = re.split(r' -> | \|\| ', row['asm'])
            if len(parts) == 2:
                assert bool(raw[2] & 128) == (' || ' in row['asm'])
                if ' || ' in row['asm']:
                    assert sum(part != 'nop' for part in parts) == 1
            for index, asm in enumerate(parts):
                size = 2 if len(parts) == 2 else len(raw)
                address = pc + 2 * index
                self.rows[address] = dict(pc=address, packet=pc, size=size,
                    asm=asm, raw=(raw[2*index:2*index+2] if len(parts) == 2 else raw).hex(),
                    relocation=self.relocations.get(pc))
        self.function_starts = sorted((f['address'], name) for name, f in self.elf.functions.items())
        self.start_addresses = [a for a, _ in self.function_starts]
        self.switches = self.switch_tables()
        self.switch_jumps = {}
        tables = {table['base']:table['targets'] for table in self.switches}
        recent = None
        regs = {}
        for row in self.function_rows('rv_call'):
            m = re.fullmatch(r'seth (\w+),#(.*)',row['asm'])
            if m:
                regs[m[1]]=int(m[2],0)<<16
            m = re.fullmatch(r'add3 (\w+),(\w+),#(-?\w+)',row['asm'])
            if m and m[2] in regs:
                value=int(m[3],0)
                if value>=32768:value-=65536
                regs[m[1]]=(regs[m[2]]+value)&0xffffffff
                if row['relocation'] and row['relocation'][0]=='R_M32R_GOTOFF_LO':
                    target=(regs[m[1]]+256)&0xffffffff
                    if target in tables:recent=target
            if row['asm'].startswith('jmp ') and row['asm']!='jmp lr':
                assert recent in tables
                self.switch_jumps[row['pc']]=tables[recent]
        assert len(self.switch_jumps)==2

    def owner(self, pc):
        index = bisect.bisect_right(self.start_addresses, pc) - 1
        if index < 0:
            return None
        start, name = self.function_starts[index]
        return name if pc < start + self.elf.functions[name]['size'] else None

    def function_rows(self, name):
        f = self.elf.functions[name]
        data = {pc for table in self.switches if name == 'rv_call'
                for pc in range(table['base'], table['base'] + table['bytes'])}
        return [row for pc, row in sorted(self.rows.items())
                if f['address'] <= pc < f['address'] + f['size'] and pc not in data]

    def switch_tables(self):
        f = self.elf.functions['rv_call']
        regs = {}
        targets = []
        for pc, row in sorted(self.rows.items()):
            if not f['address'] <= pc < f['address'] + f['size']:
                continue
            m = re.fullmatch(r'seth (\w+),#(.*)', row['asm'])
            if m:
                regs[m[1]] = int(m[2], 0) << 16
            m = re.fullmatch(r'add3 (\w+),(\w+),#(-?\w+)', row['asm'])
            if m and m[2] in regs:
                value = int(m[3], 0)
                if value >= 32768:
                    value -= 65536
                regs[m[1]] = (regs[m[2]] + value) & 0xffffffff
                if self.relocations.get(pc, ('', ''))[0] == 'R_M32R_GOTOFF_LO':
                    target = (regs[m[1]] + 256) & 0xffffffff
                    if f['address'] <= target < f['address'] + f['size']:
                        targets.append(target)
        assert len(set(targets)) == 2
        tables = []
        for base, size in zip(sorted(set(targets)), (56, 52)):
            values = struct.unpack('>' + str(size // 4) + 'i', self.elf.bytes(base, size))
            tables.append(dict(base=base, bytes=size, targets=[base + v for v in values]))
        return tables

    @staticmethod
    def target(row):
        op = row['asm'].split(' ')[0]
        if op not in BRANCH:
            return None
        return int(re.sub(r' <[^>]+>', '', row['asm']).split(',')[-1].split(' ')[-1], 16)

    def successors(self, pc):
        row = self.rows[pc]
        op = row['asm'].split(' ')[0]
        following = pc + row['size']
        if op in COND:
            return [self.target(row), following]
        if op == 'bra':
            return [self.target(row)]
        if op in ('bl', 'jl'):
            return [(row['packet'] & ~3) + 4]
        if op == 'jmp':
            if row['asm'] == 'jmp lr':
                return []
            if self.owner(pc) == 'rv_call':
                return sorted(set(self.switch_jumps[pc]))
            return []
        return [following]

    def dump(self, name):
        return '\n'.join(f"{row['pc']:08x} {row['raw']:<8} {row['asm']}" for row in self.function_rows(name)) + '\n'


def identities():
    rows = []
    for generation in (118, 119, 120):
        im = Image(generation)
        package = ROOT / f'firmware/package_v36_g{generation}{"b" if generation == 120 else ""}/SD_ROOT/GXRCE.DAT'
        raw = package.read_bytes()
        offset, length = struct.unpack_from('>II', raw, 132)
        assert raw[offset:offset+length] == im.elf.engine['data']
        rows.append(dict(generation=generation, dat_sha256=sha(raw), dat_bytes=len(raw),
                         elf_sha256=sha(im.elf.raw), engine_sha256=sha(im.elf.engine['data']),
                         engine_bytes=length, bss_bytes=int.from_bytes(raw[116:120], 'big'),
                         decoded_packets=len(im.raw), decoded_atoms=len(im.rows)))
    assert rows[-1]['dat_sha256'] == '233e23f7b4c9426a267f02fae409d1d580ef940f2b9cccd0379d7f4a479e1607'
    save('identities.json', rows)
    return rows


if __name__ == '__main__':
    print(json.dumps(identities(), indent=2))
