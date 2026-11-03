"""Independent CFG edge-cut check of the packaged ELF's open-count gate."""
from collections import deque
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()

text = (HERE / 'engine-disassembly.txt').read_text()
instructions, functions = {}, {}
for line in text.splitlines():
    label = re.fullmatch(r'([0-9a-f]{8}) <([^>]+)>:', line)
    if label and not label[2].startswith('.'):
        functions[label[2]] = int(label[1], 16)
    row = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+){4})\s*(.+)$', line)
    if not row:
        continue
    pc = int(row[1], 16)
    for offset, item in enumerate(re.split(r' -> | \|\| ', row[3])):
        item = re.sub(r' <[^>]*>', '', item).strip()
        instructions[pc + 2 * offset] = item

entry = functions['ig_event']
end = min(a for a in functions.values() if a > entry)
nodes = {pc: op for pc, op in instructions.items() if entry <= pc < end}
gate = 0x3858
assert [nodes[pc] for pc in (0x384c, 0x3850, 0x3854, gate)] == [
    'seth r5,#0x204c', 'or3 r5,r5,#0x8668', 'ld r11,@r5', 'beqz r11,38b4']
targets = {functions[name]: name for name in ('dg_fs_parse', 'dg_fs_lookup', 'dg_fs_attach')}
sites = {pc: targets[int(op.split()[1], 16)] for pc, op in nodes.items()
         if op.startswith('bl ') and int(op.split()[1], 16) in targets}
assert set(sites.values()) == set(targets.values()) and len(sites) == 3


def edges(pc, forced_gate=None):
    op = nodes[pc]
    mnemonic, _, rest = op.partition(' ')
    follow = pc + 2 if pc + 2 in nodes else (pc & ~3) + 4
    if pc == gate and forced_gate is not None:
        return [0x38b4 if forced_gate == 'zero' else follow]
    if mnemonic == 'bra':
        return [int(rest, 16)]
    if mnemonic in ('beqz', 'bnez', 'bltz', 'bgez', 'bgtz', 'blez', 'beq', 'bne', 'bc', 'bnc'):
        return [int(rest.split(',')[-1], 16), follow]
    if mnemonic == 'jmp':
        assert rest == 'lr', (hex(pc), op)
        return []
    assert mnemonic != 'jl', ('unresolved indirect call', hex(pc), op)
    return [follow]


def reach(start, forced_gate=None):
    seen, queue = set(), deque([start])
    while queue:
        pc = queue.popleft()
        if pc in seen:
            continue
        assert pc in nodes, ('left function', hex(pc))
        seen.add(pc)
        queue.extend(edges(pc, forced_gate))
    return seen


all_paths = reach(entry)
nonzero_paths = reach(entry, 'nonzero')
zero_paths = reach(entry, 'zero')
assert all_paths.issuperset(sites)
assert not set(sites) & nonzero_paths
assert zero_paths.issuperset(sites)
busy_tail = reach(0x385c, 'nonzero')
release_sites = [pc for pc in busy_tail if nodes[pc] == 'bl %x' % functions['dg_lock_release']]
assert release_sites == [0x3884], release_sites
assert not [pc for pc in busy_tail if nodes[pc].startswith('bl ') and int(nodes[pc].split()[1],16)
            in {a for name, a in functions.items() if name.startswith('dg_fs_')}]

result = {'status': 'PASS', 'method': 'intraprocedural conservative CFG reachability with the gate edge forced',
          'entry': hex(entry), 'end': hex(end), 'gate': hex(gate),
          'gate_load': [nodes[p] for p in (0x384c,0x3850,0x3854,gate)],
          'sites': {hex(pc): name for pc,name in sites.items()},
          'unconstrained_reachable': len(all_paths), 'nonzero_reachable': len(nonzero_paths),
          'nonzero_file_calls': [], 'busy_release_sites': [hex(p) for p in release_sites],
          'zero_reaches_all_three': True,
          'limits': ['All other branch conditions are conservative; direct callees return to the next instruction.',
                     'This proves the nonzero guard, not the filesystem invariant that zero count means clean FAT.',
                     'Artifact review separately binds this ELF section to the packaged DAT bytes.']}
scope.save(HERE / 'gate-review.json', result)
print(json.dumps(result,indent=1))
