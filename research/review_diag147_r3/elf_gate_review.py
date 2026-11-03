"""Independent ELF-byte, graph-dominance and concrete gate review."""
from collections import deque
from pathlib import Path
import json
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
import host_native as native

ELF = scope.ROOT / 'firmware/engine_diag_v38_g147/candidate/local/full-r1/engine.elf'
DAT = scope.ROOT / 'firmware/package_v38_diag147/SD_ROOT/GXRCE.DAT'
raw = ELF.read_bytes()
assert raw[:6] == b'\x7fELF\x01\x02'
header = struct.unpack_from('>16sHHIIIIIHHHHHH', raw)
section_offset, section_size, section_count = header[6], header[11], header[12]
sections = [struct.unpack_from('>IIIIIIIIII', raw, section_offset + i * section_size)
            for i in range(section_count)]
spans = [(s[3], raw[s[4]:s[4]+s[5]]) for s in sections if s[1] == 1 and s[2] & 2]


def blob(address, size):
    for start, data in spans:
        if start <= address and address + size <= start + len(data):
            return data[address-start:address-start+size]
    raise AssertionError(('ELF address', hex(address), size))


listing = subprocess.check_output([str(scope.ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),
                                   '-d', str(ELF)], text=True, timeout=1800)
(HERE / 'engine-disassembly.txt').write_text(listing)
code, labels, packets, widths = {}, {}, {}, {}
verified = 0
for line in listing.splitlines():
    label = re.match(r'^([0-9a-f]+) <([^>]+)>:$', line)
    if label:
        labels[label[2]] = int(label[1], 16)
    match = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$', line)
    if not match:
        continue
    address, data = int(match[1], 16), bytes.fromhex(match[2])
    assert blob(address, len(data)) == data
    verified += len(data)
    parts = [re.sub(r'\s*<[^>]*>', '', x).strip() for x in re.split(r' -> | \|\| ', match[3])]
    packets[address] = tuple(native.p.Program.parse(x) for x in parts)
    widths[address] = len(data)
    for i, instruction in enumerate(parts):
        code[address + 2 * i] = instruction

start = labels['ig_event']
end = min(a for name, a in labels.items() if not name.startswith('.L') and a > start)
assert start == 0x368c and end == 0x3c2c
positions = sorted(a for a in code if start <= a < end)
following = {a: positions[i+1] for i, a in enumerate(positions[:-1])}
conditions = {'beqz', 'bnez', 'bltz', 'bgez', 'blez', 'bgtz', 'beq', 'bne', 'bc', 'bnc'}
graph = {}
for address in positions:
    text = code[address]
    op, _, rest = text.partition(' ')
    if op == 'jmp':
        assert rest == 'lr'
        successors = []
    elif op == 'bra':
        successors = [int(rest, 16)]
    elif op in conditions:
        successors = [int(rest.split(',')[-1], 16), following[address]]
    else:
        assert op != 'jl', ('indirect call in gate function', hex(address))
        successors = [following[address]] if address in following else []
    assert all(start <= a < end for a in successors)
    graph[address] = successors


def reachable(edges):
    seen, queue = {start}, deque([start])
    while queue:
        address = queue.popleft()
        for target in edges[address]:
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


nodes = reachable(graph)
predecessors = {a: set() for a in nodes}
for address in nodes:
    for target in graph[address]:
        predecessors[target].add(address)
dominators = {a: ({start} if a == start else set(nodes)) for a in nodes}
changed = True
while changed:
    changed = False
    for address in positions:
        if address not in nodes or address == start:
            continue
        value = {address} | set.intersection(*(dominators[p] for p in predecessors[address]))
        if value != dominators[address]:
            dominators[address] = value
            changed = True

bridges = {labels[k]: k for k in ('dg_fs_parse', 'dg_fs_lookup', 'dg_fs_attach')}
sites = {address: bridges[int(text.split()[1], 16)] for address, text in code.items()
         if text.startswith('bl ') and int(text.split()[1], 16) in bridges}
assert len(sites) == 3 and all(start <= address < end for address in sites)
assert [code[a] for a in (0x384c, 0x3850, 0x3854, 0x3858)] == [
    'seth r5,#0x204c', 'or3 r5,r5,#0x8668', 'ld r11,@r5', 'beqz r11,38b4']
assert all({0x3854, 0x3858} <= dominators[address] for address in sites)
nonzero = dict(graph)
nonzero[0x3858] = [0x385c]
assert not set(sites) & reachable(nonzero)
assert set(sites) <= reachable(graph)
flipped = dict(graph)
flipped[0x3858] = [0x38b4]
assert set(sites) <= reachable(flipped)


class Program:
    name = 'reviewed-engine-elf'
    symbols = {'entry': 0x384c}
    code = packets
    width = widths

    def byte(self, address):
        try:
            return blob(address, 1)[0]
        except AssertionError:
            return 0


class GateStop(Exception):
    pass


cases = []
for count in (0, 1, 2, 255, 256, 0xffffffff):
    cpu = native.CPU(Program())
    cpu.seed(0x204c8668, count)
    cpu.r[6], cpu.r[8], cpu.r[12] = 0x20600000, 0, 0x20600000
    events = []

    def note(name, result=0):
        def operation(c):
            events.append(name)
            c.r[0] = result
        return operation

    def stop(c):
        raise GateStop()

    for address, name in bridges.items():
        cpu.stubs[address] = note(name, 0x81 if name == 'dg_fs_lookup' else 0)
    cpu.stubs[labels['dg_lock_release']] = note('dg_lock_release')
    cpu.stubs[0x3888] = stop
    cpu.stubs[0x3914] = stop
    try:
        cpu.run('entry', bound=1000)
    except GateStop:
        pass
    expected = ['dg_fs_parse', 'dg_fs_lookup', 'dg_fs_attach'] if count == 0 else ['dg_lock_release']
    assert events == expected, (count, events)
    cases.append(dict(open_count=count, events=events))

dat = DAT.read_bytes()
offset, size = struct.unpack_from('>II', dat, 132)
engine_start = min(address for address, data in spans)
assert engine_start == 0x100
assert dat[offset:offset+size] == blob(engine_start, size)
result = dict(status='PASS', dat_sha256=scope.sha(DAT), elf_sha256=scope.sha(ELF),
              verified_disassembly_bytes=verified, dat_code_equals_elf=True, elf_image_start=hex(engine_start),
              call_sites={hex(a): name for a, name in sites.items()},
              load='0x3854', branch='0x3858', condition='beqz r11,0x38b4',
              load_and_branch_dominate_all_three_calls=True, nonzero_reaches_open_calls=False,
              reversed_condition_reaches_open_calls=True, concrete_cases=cases,
              limits=['Graph treats ordinary calls as returning and checks direct callers of the three bridges.',
                      'Concrete execution starts at the count load with valid diagnostic and stack RAM.',
                      'File internals and semaphore release are recorded at their engine bridges in this check.'])
scope.save(HERE / 'elf-gate-results.json', result)
print(json.dumps(result, indent=2))
