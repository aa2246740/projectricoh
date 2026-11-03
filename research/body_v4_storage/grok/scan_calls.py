#!/usr/bin/env python3
"""Bounded call scan of the existing linear disassembly. Writes only this directory."""
from pathlib import Path
import hashlib
import json
import plistlib
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'local'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3'
ASM_DIR = ROOT / 'research/irom_storage/local'
EXPECTED = {
    OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    BODY: '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008',
}
INS = re.compile(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$')
FILE_API = {
    0x200a40b4: 'high_open', 0x200a41ac: 'high_create', 0x200a437c: 'high_close',
    0x200a3e64: 'high_format', 0x200a449c: 'write_sets_status_2',
    0x200a45e8: 'write_sets_status_1', 0x200a46f0: 'write_sets_status_2b',
    0x200a479c: 'photo_commit_a', 0x200a48c8: 'photo_commit_b',
    0x200a4880: 'high_read_candidate', 0x200b92f4: 'slot_alloc',
    0x200a6750: 'lower_close',
}
SEND_API = {
    0x2010ac50: 'storage_send_wrapper', 0x2005e034: 'rtos_send',
    0x2005e078: 'rtos_receive', 0x20109b28: 'storage_receive_wrapper',
}
INTEREST_LO, INTEREST_HI = 0x20109800, 0x2010b200
HANDLER = {
    0x2010e3f8: 'event0_state1', 0x2010e5c8: 'photo_1f03', 0x2010eb0c: 'photo_file',
    0x2010f010: 'event2_1f04_type7', 0x2010ad0c: 'event4_1f08',
    0x201106d4: 'return_zero', 0x201106d8: 'event5_1f09_type7',
    0x20111810: 'format_1f0b', 0x20111b40: 'event7_1f0a',
    0x201136a8: 'event6_1f09_other', 0x20113e68: 'event3_1f04_other',
    0x2010e064: 'event10_1f12',
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def preflight():
    p = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert p['MountPoint'] == '/Volumes/Workspace'
    assert p['FilesystemType'] == 'apfs'
    assert p['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    OUT.mkdir(exist_ok=True)
    for path, expected in EXPECTED.items():
        assert sha(path) == expected, str(path)


class Image:
    def __init__(self):
        self.data = OFFICIAL.read_bytes()
        self.sections = []
        for i in range(16):
            src, va, n, bss, bn = struct.unpack_from('>IIIII', self.data, 32 + i * 20)
            self.sections.append(dict(index=i, file=src + 512, vma=va, size=n))

    def raw(self, va, n):
        hits = [s['file'] + va - s['vma'] for s in self.sections
                if s['vma'] <= va and va + n <= s['vma'] + s['size']]
        assert len(hits) == 1, hex(va)
        off = hits[0]
        return self.data[off:off + n]


def imm(text):
    return int(text.lstrip('#'), 0)


def track(regs, memsrc, name, args):
    """Same-block constant tracking. Returns True when the block must end."""
    d = args[0] if args else ''
    try:
        if name == 'seth':
            regs[d] = imm(args[1]) << 16
            memsrc.pop(d, None)
        elif name == 'ld24':
            regs[d] = int(args[1], 16)
            memsrc.pop(d, None)
        elif name == 'ldi':
            regs[d] = imm(args[1]) & 0xffffffff
            memsrc.pop(d, None)
        elif name == 'mv' and args[1] in regs:
            regs[d] = regs[args[1]]
            if args[1] in memsrc:
                memsrc[d] = memsrc[args[1]]
            else:
                memsrc.pop(d, None)
        elif name in ('or3', 'add3', 'and3') and args[1] in regs:
            x, y = regs[args[1]], imm(args[2])
            if name == 'add3' and 0x8000 <= y <= 0xffff:
                y -= 0x10000
            regs[d] = (x | y if name == 'or3' else x + y if name == 'add3' else x & y) & 0xffffffff
            memsrc.pop(d, None)
        elif name in ('addi', 'slli', 'srli') and d in regs:
            x, y = regs[d], imm(args[1])
            regs[d] = (x + y if name == 'addi' else x << y if name == 'slli' else x >> y) & 0xffffffff
            memsrc.pop(d, None)
        elif name in ('ld', 'ldh', 'lduh', 'ldb', 'ldub') and len(args) > 1:
            address = args[1]
            m = re.fullmatch(r'@\((-?\d+),(\w+)\)', address)
            base = m[2] if m else address.removeprefix('@')
            offset = int(m[1]) if m else 0
            if base in regs:
                memsrc[d] = (regs[base] + offset) & 0xffffffff
            else:
                memsrc.pop(d, None)
            regs.pop(d, None)
        elif name in ('jl', 'bl'):
            for r in range(8):
                regs.pop('r' + str(r), None)
                memsrc.pop('r' + str(r), None)
        elif name.startswith('b') or name in ('jmp', 'rte'):
            regs.clear()
            memsrc.clear()
            return True
        elif name not in ('nop', 'cmp', 'cmpu', 'cmpi', 'cmpui', 'cmpeq', 'st', 'sth', 'stb', 'push', 'pop'):
            regs.pop(d, None)
            memsrc.pop(d, None)
    except (ValueError, IndexError):
        regs.clear()
        memsrc.clear()
    return False


def args_of(text):
    name, _, tail = text.partition(' ')
    found = re.findall(r'@\([^)]*\)|[^,\s]+', tail)
    return name, found


def main():
    preflight()
    im = Image()
    calls = []
    opcodes = []
    verified = 0
    sources = {}
    code = {}
    regs, memsrc = {}, {}
    for path in sorted(ASM_DIR.glob('section*.asm.txt')):
        sources[str(path.relative_to(ROOT))] = sha(path)
        regs.clear()
        memsrc.clear()
        for line in path.read_text(errors='replace').splitlines():
            m = INS.match(line)
            if not m:
                continue
            pc = int(m[1], 16)
            raw = bytes.fromhex(m[2])
            assert im.raw(pc, len(raw)) == raw, hex(pc)
            verified += len(raw)
            parts = re.split(r' -> | \|\| ', m[3])
            if 0x20109000 <= pc < 0x20145000:
                code[pc] = (len(raw), parts)
            for index, text in enumerate(parts):
                name, found = args_of(text)
                site = pc + 2 * index
                if name in ('sth', 'st') and found and found[0] in regs:
                    value = regs[found[0]]
                    if 0x1f00 <= value <= 0x1f40 or 0x1000 <= value <= 0x1010:
                        opcodes.append({'vma': hex(site), 'op': name, 'value': hex(value),
                                        'text': text})
                if name in ('jl', 'bl'):
                    target = None
                    if name == 'bl':
                        target = int(found[0], 16) if found else None
                    elif found and found[0] in regs:
                        target = regs[found[0]]
                    keep = target in FILE_API or target in SEND_API or (
                        target is not None and INTEREST_LO <= target < INTEREST_HI) or (
                        INTEREST_LO <= site < 0x20145000)
                    if keep and target is not None:
                        known = {}
                        for reg in ('r4', 'r5', 'r6', 'r7'):
                            if reg in regs:
                                known[reg] = hex(regs[reg])
                            elif reg in memsrc:
                                known[reg] = 'mem:' + hex(memsrc[reg])
                        calls.append({
                            'vma': hex(site), 'target': hex(target),
                            'name': FILE_API.get(target) or SEND_API.get(target) or HANDLER.get(target) or '',
                            'args': known, 'text': text,
                        })
                if track(regs, memsrc, name, found):
                    break
    # Handler CFG with same-block constants copied along direct edges.
    def walk(entry):
        seen = set()
        outgoing = []
        returns = []
        stops = []
        work = [(entry, {}, {})]
        steps = 0
        while work and steps < 4000:
            pc, rs, ms = work.pop()
            key = (pc, tuple(sorted(rs.items())))
            if key in seen:
                continue
            seen.add(key)
            steps += 1
            if pc not in code or pc < entry or pc >= entry + 0x2000:
                stops.append(hex(pc))
                continue
            length, parts = code[pc]
            rs, ms = dict(rs), dict(ms)
            branched = False
            for index, text in enumerate(parts):
                name, found = args_of(text)
                site = pc + 2 * index
                if name in ('jl', 'bl'):
                    target = int(found[0], 16) if name == 'bl' and found else rs.get(found[0] if found else '')
                    outgoing.append({'vma': hex(site), 'target': hex(target) if target is not None else None,
                                     'name': FILE_API.get(target, '') or SEND_API.get(target, '') or HANDLER.get(target, ''),
                                     'text': text})
                if name in ('bra', 'jmp') or name in ('beq', 'bne', 'beqz', 'bnez', 'bc', 'bnc', 'bgez', 'bltz'):
                    branched = True
                    if name == 'jmp' and found and found[0] in ('lr', 'r14'):
                        returns.append(hex(site))
                    elif name == 'jmp' and found and found[0] in rs:
                        work.append((rs[found[0]] & ~3, dict(rs), dict(ms)))
                    elif name != 'jmp':
                        dest = int(found[-1], 16)
                        work.append((dest, dict(rs), dict(ms)))
                        if name != 'bra':
                            work.append((pc + length, dict(rs), dict(ms)))
                ended = track(rs, ms, name, found)
                if ended and not branched:
                    break
            else:
                if not branched:
                    work.append((pc + length, rs, ms))
        compact = []
        seen_call = set()
        for row in outgoing:
            mark = (row['vma'], row['target'])
            if mark not in seen_call:
                seen_call.add(mark)
                compact.append(row)
        return {'entry': hex(entry), 'name': HANDLER[entry], 'calls': compact,
                'returns': returns[:8], 'stops': stops[:8], 'states': len(seen)}

    handlers = [walk(entry) for entry in HANDLER]
    # Group send sites.
    def bucket(pred):
        rows = [c for c in calls if pred(c)]
        return rows

    summary = {
        'verified_bytes': verified,
        'call_rows': len(calls),
        'opcode_immediates': opcodes,
        'storage_send_wrapper': bucket(lambda c: c['target'] == '0x2010ac50'),
        'rtos_send': bucket(lambda c: c['target'] == '0x2005e034'),
        'rtos_receive': bucket(lambda c: c['target'] == '0x2005e078'),
        'storage_receive_wrapper': bucket(lambda c: c['target'] == '0x20109b28'),
        'constructor_calls': bucket(lambda c: INTEREST_LO <= int(c['target'], 16) < INTEREST_HI
                                    and not (INTEREST_LO <= int(c['vma'], 16) < INTEREST_HI)),
        'file_api_calls': bucket(lambda c: int(c['target'], 16) in FILE_API),
        'handlers': handlers,
        'limitations': [
            'Linear disassembly includes data. Constants are tracked only inside a basic block.',
            'A resolved jl is a syntactic candidate, not a dynamic execution trace.',
            'Handler CFG follows direct branches and stops at unknown indirect jumps.',
            'No camera, card, RTOS scheduling, or product modification.',
        ],
        'sources': sources,
    }
    (OUT / 'call-scan.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print('verified', verified)
    print('send wrapper', len(summary['storage_send_wrapper']))
    print('rtos send', len(summary['rtos_send']))
    print('constructor external', len(summary['constructor_calls']))
    print('file api', len(summary['file_api_calls']))
    print('opcodes', len(opcodes))
    for name, rows in (
        ('wrapper', summary['storage_send_wrapper']),
        ('rtos', summary['rtos_send']),
        ('ctor', summary['constructor_calls']),
    ):
        for row in rows:
            print(name, row['vma'], row['target'], row['name'], row['args'])


if __name__ == '__main__':
    main()
