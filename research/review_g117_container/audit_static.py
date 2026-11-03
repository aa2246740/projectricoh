"""Check the shipped relocated DAT, every native call, and test-edit ledger."""
from pathlib import Path
import difflib
import hashlib
import importlib.util
import json
import re
import struct
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
BUILDER = ROOT / 'firmware/engine_v38_ro'
U32 = lambda b, p: struct.unpack_from('>I', b, p)[0]


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    spec = importlib.util.spec_from_file_location('independent_elf', ROOT / 'firmware/stage2l_switch/tools/build.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    raw = (ROOT / 'firmware/package_v35_g117/SD_ROOT/GXRCE.DAT').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a'
    e = reader.Elf(BUILDER / 'candidate/local/full-r13/engine.elf')
    moved = reader.Elf(BUILDER / 'candidate/local/product-r13/m32r-lto/translated.elf')
    sec = lambda elf: next(s for s in elf.sections if s['name'] == '.engine')
    code, size = U32(raw, 132), U32(raw, 136)
    assert e.content(sec(e)) == raw[code:code + size]
    relocated = bytearray(raw)
    for pos in range(U32(raw, 144), U32(raw, 144) + U32(raw, 148), 8):
        patch, target = struct.unpack_from('>II', raw, pos)
        assert U32(raw, patch) == target
        struct.pack_into('>I', relocated, patch, 0x21004000 + target)
    assert moved.content(sec(moved)) == relocated[code:code + size]
    lines = (OUT / 'relocated-117.dis').read_text().splitlines()
    functions = {}
    calls, ins = [], []
    owner = None
    for index, line in enumerate(lines):
        m = re.fullmatch(r'([0-9a-f]+) <([^>]+)>:', line)
        if m:
            owner = m[2]
            functions[owner] = []
        m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.+)', line)
        if not m:
            continue
        pc, data, asm = int(m[1], 16), bytes.fromhex(m[2]), m[3]
        # Verify disassembly instruction bytes directly against relocated DAT.
        assert data == relocated[pc - 0x21004000:pc - 0x21004000 + len(data)]
        functions.setdefault(owner, []).append((pc, asm))
        ins.append(dict(pc=hex(pc), owner=owner, asm=asm))
        target = re.search(r'\b(?:bl|bra)\s+([0-9a-f]+) <(rv_native_(open|read|close|create|write|rename|delete))>', asm)
        if target:
            calls.append(dict(pc=hex(pc), caller=owner, operation=target[3], target=target[2],
                              context='\n'.join(lines[max(0, index - 28):index + 8])))
    save('native-file-calls.json', calls)
    counts = {op: sum(row['operation'] == op for row in calls) for op in ('open', 'read', 'close', 'create', 'write', 'rename', 'delete')}
    assert counts == dict(open=4, read=6, close=6, create=1, write=1, rename=2, delete=1)
    bridges = []
    for name, body in functions.items():
        if not name.startswith('rv_native_'):
            continue
        for k, (pc, asm) in enumerate(body[:-1]):
            hi = re.fullmatch(r'seth r6,#0x([0-9a-f]+)', asm)
            lo = re.fullmatch(r'or3 r6,r6,#0x([0-9a-f]+)', body[k + 1][1])
            if hi and lo:
                bridges.append(dict(wrapper=name, pc=hex(pc), native=hex(int(hi[1], 16) << 16 | int(lo[1], 16))))
    save('all-native-bridges.json', bridges)
    external_direct = [row for row in ins if re.search(r'\b(?:bl|bra|jmp)\s+20[0-9a-f]{6}\b', row['asm'])]
    assert not external_direct
    indirect = [row for row in ins if re.search(r'\b(?:jl|jmp)\s+r\d+\b', row['asm'])]
    save('indirect-transfers.json', indirect)
    absolute_high = [row for row in ins if re.search(r'\bseth r\d+,#0x20[0-2][0-9a-f]\b', row['asm'])]
    save('all-official-address-materializations.json', absolute_high)
    # Native filesystem high words occur only in the bridge. This includes
    # 0x200B FAT helpers, not merely the seven known wrapper addresses.
    for row in absolute_high:
        m = re.search(r'#0x(20[0-2][0-9a-f])\b', row['asm'])
        if int(m[1], 16) in (0x200a, 0x200b):
            assert row['owner'].startswith('rv_native_'), row
    cap_loads = [hex(pc) for pc, asm in functions['ig_init'] if re.search(r'ld24 r\d+,e0000\b', asm)]
    assert cap_loads == ['0x2100b3a4', '0x2100bb6c']
    # Concrete machine-code cut points, independently read in the final listing.
    critical = {
        '0x2100cf1c': 'ld r5,@(340,r8)', '0x2100cf20': 'ld24 r6,10000',
        '0x2100cf24': 'and r5,r6', '0x2100cf28': 'beqz r5,2100cf14',
        '0x2100d078': 'ld r7,@(340,r8)', '0x2100d07c': 'ld24 r3,10000',
        '0x2100d080': 'and r7,r3', '0x2100d084': 'beqz r7,2100cf14',
        '0x2100cb84': 'ld r5,@(12,r9)', '0x2100cb98': 'bne r6,r5,2100cbd0',
        '0x2100d02c': 'st r6,@(292,r5)', '0x2100cf5c': 'ldi r1,#0',
        '0x2100ed70': 'ldi r1,#0',
    }
    bypc = {x['pc']: x['asm'] for x in ins}
    checked = {}
    for pc, expected in critical.items():
        assert bypc[pc].startswith(expected), (pc, expected, bypc.get(pc))
        checked[pc] = bypc[pc]
    save('no-write-machine-cutpoints.json', checked)
    # Replay the full builder assertion-edit ledger against the original file.
    original = (ROOT / 'firmware/engine_v37/candidate/host_v34c.c').read_text()
    ledger = json.loads((BUILDER / 'local/host-expectation-changes.json').read_text())
    text = original
    for index, row in enumerate(ledger):
        assert text.count(row['old']) == row['occurrences'], (index, row['old'][:80])
        text = text.replace(row['old'], row['new'])
    actual = (BUILDER / 'candidate/host_v34c.c').read_text()
    (OUT / 'test-ledger-unexplained.patch').write_text(''.join(difflib.unified_diff(
        text.splitlines(True), actual.splitlines(True), fromfile='ledger_result', tofile='actual_host')))
    assert [s for s in text.splitlines() if s] == [s for s in actual.splitlines() if s]
    save('test-ledger-replay.json', dict(entries=len(ledger), nonblank_lines_identical_to_actual=True,
        unlisted_changes='three blank separator lines only',
        scope_notes=['storage removal and RAM acceptance', 'cold cursor=04', 'stale preferences ignored',
                     'additional native counters', 'negative-control include routing'],
        extra_live_tweak_verification_needed=True))
    save('static-summary.json', dict(shipped_sha256=hashlib.sha256(raw).hexdigest(), file_bytes=len(raw),
        engine_bytes=size, bss_bytes=U32(raw, 116), relocated_engine_equals_final_dat=True,
        cap_loads=cap_loads, native_calls=counts, direct_external_calls=external_direct,
        bridges=len(bridges), decoded_instructions=len(ins), assertion_ledger_entries=len(ledger)))
    print('PASS final DAT relocation and all instruction bytes; native file calls', counts)
    print('PASS capability gates, readonly-token invariant, absolute FAT/DCF bridge inventory')
    print('PASS complete assertion-edit ledger replay:', len(ledger), 'changes')


if __name__ == '__main__':
    main()
