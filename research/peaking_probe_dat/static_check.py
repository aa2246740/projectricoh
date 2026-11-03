"""Compiled-code check for the peaking probe P1 engine: the machine code can write the unit at one
address only.

Usage: /usr/bin/python3 -I -B static_check.py

Reads firmware/engine_probe_p1/candidate/local/full-r1/engine.elf (the exact code packed into
GXRCE.DAT) through m32r-elf-objdump and checks:
  1. every call to the RPC dispatcher rv_rpc8_native has literal arguments, and the set of
     (command, operand) pairs is exactly the P1 whitelist;
  2. the only W (command 22) sites are W 7FFF and W FFFF; each sits after X 2012 and V EBE0 with no
     other call in between, i.e. the cursor is EBE0 on the D page;
  3. the dispatcher address 0x2009005c is loaded only inside rv_rpc8_native;
  4. the register-indirect calls are the six native bridge targets plus the services table call;
  5. no byte of the image holds the address of a file, S, allocator, preview or unit-query native,
     or the S pointer.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
from scope import ROOT, sha, save
scope.enable_fence()

ELF = ROOT / 'firmware/engine_probe_p1/candidate/local/full-r1/engine.elf'
BIN = ROOT / 'firmware/engine_probe_p1/candidate/local/full-r1/engine.bin'
if len(sys.argv) == 3:      # negative control: another engine image, e.g. the product engine of g137
    ELF, BIN = Path(sys.argv[1]), Path(sys.argv[2])
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
SCRATCH = scope.SCRATCH

WHITELIST = {(23, 0x12c0), (23, 0x2012),
             (21, 0x3b06), (21, 0x3b10), (21, 0x3b00), (21, 0xebe2), (21, 0xebe0),
             (22, 0x7fff), (22, 0xffff)}
BRIDGE_TARGETS = {0x201d73e0: 'ascii', 0x201dc180: 'language', 0x201fd360: 'draw',
                  0x2005f228: 'native_context', 0x2009359c: 'rpc_ready', 0x20094e2c: 'rpc_limit'}
DISPATCHER = 0x2009005c
# Natives and words that must not appear anywhere in the image.
FORBIDDEN = {0x200a544c: 'file create', 0x200a45e8: 'file write', 0x200a49d8: 'file rename',
             0x200a4910: 'file delete', 0x200a40b4: 'file open', 0x200a449c: 'file read',
             0x200a437c: 'file close', 0x200a3240: 'sd id', 0x202d6f38: 'preview',
             0x201c092c: 'layer', 0x2005bf5c: 'alloc', 0x2005c038: 'free', 0x20063f64: 'unit query',
             0x200c0dac: 'S pointer', 0x200c0db0: 'S length'}
DEST_FIRST = {'add', 'addi', 'addv', 'addx', 'add3', 'sub', 'subv', 'subx', 'and', 'and3', 'or', 'or3',
              'xor', 'xor3', 'neg', 'not', 'sll', 'sll3', 'slli', 'sra', 'sra3', 'srai', 'srl', 'srl3',
              'srli', 'mul', 'div', 'divu', 'rem', 'remu', 'mv', 'ld', 'ldb', 'ldh', 'ldub', 'lduh',
              'ld24', 'ldi', 'seth', 'mvfc', 'mvfachi', 'mvfaclo', 'mvfacmi', 'pop'}
CALLS = {'bl', 'jl'}


def disassemble():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    out = SCRATCH / 'engine-static.dis'
    text = subprocess.run([str(OBJDUMP), '-d', str(ELF)], capture_output=True, text=True, check=True).stdout
    out.write_text(text)
    return text


def parse(text):
    """-> list of (address, function, label_start, ops[]) with ops = [(mnemonic, operands)]."""
    rows, function, label = [], None, True
    for line in text.splitlines():
        head = re.match(r'^([0-9a-f]{8}) <([^>]+)>:$', line)
        if head:
            name = head.group(2)
            if name.startswith('.L'):
                label = True
            else:
                function, label = name, True
            continue
        m = re.match(r'^\s+([0-9a-f]+):\t(?:[0-9a-f]{2} ?)+\t(.+)$', line)
        if not m or function is None:
            continue
        ops = []
        for part in re.split(r' \|\| | -> ', m.group(2).strip()):
            part = re.sub(r'\s*<[^>]*>', '', part).strip()
            if not part or part == 'nop':
                continue
            mnemonic, _, operands = part.partition(' ')
            ops.append((mnemonic, operands.strip()))
        rows.append((int(m.group(1), 16), function, label, ops, m.group(2)))
        label = False
    return rows


def number(token):
    token = token.strip().lstrip('#')
    return int(token, 0) if re.match(r'^-?(0x)?[0-9a-fA-F]+$', token) and (token.startswith(('0x', '-')) or token.isdigit()) else None


def hexnumber(token):
    return int(token.strip(), 16)


def simulate(rows):
    """Forward constants over straight-line regions (a label starts a fresh region)."""
    sites, indirect, loads = [], [], []
    regs = {}
    for address, function, label, ops, raw in rows:
        if label:
            regs = {}
        for mnemonic, operands in ops:
            args = [a.strip() for a in operands.split(',')] if operands else []
            if mnemonic == 'ldi':
                regs[args[0]] = number(args[1])
            elif mnemonic == 'ld24':
                regs[args[0]] = hexnumber(args[1].split()[0])
            elif mnemonic == 'seth':
                regs[args[0]] = (number(args[1]) << 16) & 0xffffffff
            elif mnemonic == 'or3' and args[0] == args[1] and regs.get(args[1]) is not None and number(args[2]) is not None:
                regs[args[0]] = regs[args[1]] | number(args[2])
            elif mnemonic == 'mv':
                regs[args[0]] = regs.get(args[1])
            elif mnemonic in CALLS:
                if mnemonic == 'bl' and 'rv_rpc8_native' in raw:
                    sites.append(dict(address=address, function=function, r0=regs.get('r0'), r1=regs.get('r1')))
                if mnemonic == 'jl':
                    indirect.append(dict(address=address, function=function, register=args[0], value=regs.get(args[0])))
                for r in ('r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7'):
                    regs[r] = None
            elif mnemonic in DEST_FIRST and args:
                regs[args[0]] = None
            if mnemonic in ('seth',) or (mnemonic == 'or3' and args and regs.get(args[0]) is not None):
                value = regs.get(args[0])
                if value is not None:
                    loads.append((address, function, value))
        if any(m in ('bra', 'jmp') for m, _ in ops):
            regs = {}
    return sites, indirect, loads


def main():
    scope.freeze_check()
    text = disassemble()
    rows = parse(text)
    sites, indirect, loads = simulate(rows)
    report = {'engine_elf': sha(ELF), 'engine_bin': sha(BIN), 'instructions': len(rows),
              'dispatcher_call_sites': len(sites)}
    # 1. every dispatcher call is literal and on the whitelist
    pairs = {}
    for site in sites:
        assert site['r0'] in (21, 22, 23) and site['r1'] is not None, ('non-literal dispatcher call', site)
        pair = (site['r0'], site['r1'])
        assert pair in WHITELIST, ('outside whitelist', hex(site['address']), pair)
        pairs.setdefault(pair, []).append(site['address'])
    assert set(pairs) == WHITELIST, ('whitelist not fully used', set(pairs) ^ WHITELIST)
    report['pairs'] = {'%s %04X' % ({21: 'V', 22: 'W', 23: 'X'}[c], v): [hex(a) for a in addrs]
                       for (c, v), addrs in sorted(pairs.items())}
    # 2. W sites: after X 2012 and V EBE0, nothing else called in between
    wsites = [s for s in sites if s['r0'] == 22]
    assert sorted(s['r1'] for s in wsites) == [0x7fff, 0xffff], wsites
    calls_by_function = {}
    for address, function, label, ops, raw in rows:
        if any(m in CALLS for m, _ in ops):
            calls_by_function.setdefault(function, []).append(address)
    for w in wsites:
        function_calls = [a for a in calls_by_function[w['function']] if a < w['address']]
        by_address = {s['address']: s for s in sites}
        previous = function_calls[-1]
        assert previous in by_address and (by_address[previous]['r0'], by_address[previous]['r1']) == (21, 0xebe0), \
            ('W not directly after V EBE0', hex(w['address']), hex(previous))
        x_before = [a for a in function_calls if a in by_address and by_address[a]['r0'] == 23]
        assert (by_address[x_before[-1]]['r1']) == 0x2012, ('W page is not D', hex(w['address']))
        between = [a for a in function_calls if x_before[-1] < a < previous and not (a in by_address and by_address[a]['r0'] == 21)]
        assert not between, ('call between X 2012 and V EBE0', [hex(a) for a in between])
    report['write_sites'] = [{'address': hex(w['address']), 'value': '%04X' % w['r1'], 'function': w['function']} for w in wsites]
    # 3. the dispatcher address is built only inside rv_rpc8_native
    where = sorted({f for _, f, v in loads if v == DISPATCHER})
    assert where == ['rv_rpc8_native'], where
    report['dispatcher_loaded_in'] = where
    # 4. register-indirect calls
    bridge_functions = {'rv_rpc8_native'}
    native = sorted({v for _, f, v in loads if v in BRIDGE_TARGETS or v == DISPATCHER})
    assert set(native) == set(BRIDGE_TARGETS) | {DISPATCHER}, [hex(v) for v in native]
    report['native_targets'] = {hex(v): BRIDGE_TARGETS.get(v, 'rpc dispatcher') for v in native}
    # .Lnative (the shared tail of the six NATIVE stubs) sits after rv_native_rpc_limit in the listing
    outside = [i for i in indirect if i['function'] not in bridge_functions and not i['function'].startswith('rv_native_')]
    report['indirect_calls'] = [dict(address=hex(i['address']), function=i['function'], register=i['register'],
                                     target=hex(i['value']) if i['value'] is not None else 'dynamic') for i in indirect]
    # the native bridges call through r0/r6 loaded from their own constants; everything else is the services table
    for i in outside:
        assert i['value'] is None and i['function'] in ('rpc', 'call'), ('unexpected indirect call', i)
    # 5. forbidden natives and words, in code constants and anywhere in the packed bytes
    blob = BIN.read_bytes()
    found = {}
    for address, function, value in loads:
        if value in FORBIDDEN:
            found.setdefault(FORBIDDEN[value], []).append((hex(address), function))
    for value, name in FORBIDDEN.items():
        needle = value.to_bytes(4, 'big')
        at = blob.find(needle)
        while at >= 0:
            found.setdefault(name, []).append(('bin+%d' % at, 'raw'))
            at = blob.find(needle, at + 1)
    assert not found, found
    report['forbidden_absent'] = {'%08X' % v: n for v, n in FORBIDDEN.items()}
    # symbols: no storage, settings, preview, lease, or generic transport entry in the image
    symbols = subprocess.run([str(OBJDUMP), '-t', str(ELF)], capture_output=True, text=True, check=True).stdout
    names = set(re.findall(r'\s(\S+)$', symbols, re.M))
    for banned in ('rv_native_create', 'rv_native_write', 'rv_native_rename', 'rv_native_delete', 'rv_native_open',
                   'rv_native_read', 'rv_native_close', 'rv_native_sd_id', 'rv_native_preview', 'rv_native_alloc',
                   'rv_native_free', 'rv_native_layer', 'rv_native_unit', 'es_storage_mark', 'storage', 'settings', 'ui_view'):
        assert banned not in names, banned
    report['symbols_checked_absent'] = True
    report['status'] = 'PASS'
    if len(sys.argv) == 1:
        save(HERE / 'local/static-check.json', report)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
