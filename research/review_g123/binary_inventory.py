"""Inventory all function-body changes after normalizing linked addresses."""
from pathlib import Path
import difflib
import json
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *
from static_audit import symbols


def canonical(name):
    return re.sub(r'\.(?:lto_priv|constprop|isra)\.\d+', '', name)


def object_symbols(path):
    raw = path.read_bytes()
    h = struct.unpack_from('>16sHHIIIIIHHHHHH', raw)
    sections = [struct.unpack_from('>10I', raw, h[6]+i*h[11]) for i in range(h[12])]
    found = []
    literals = []
    for s in sections:
        if s[1] != 2:
            continue
        strings = sections[s[6]]
        names = raw[strings[4]:strings[4]+strings[5]]
        for at in range(s[4], s[4]+s[5], s[9]):
            n, value, size, info, other, index = struct.unpack_from('>IIIBBH', raw, at)
            name = names[n:].split(b'\0',1)[0].decode()
            if info & 15 == 1 and size and index:
                
                label=canonical(name)
                if name.startswith('CSWTCH.'):
                    sec=sections[index]
                    label='CSWTCH:'+sha(raw[sec[4]+value-sec[3]:sec[4]+value-sec[3]+size])
                found.append((value, size, label))
            if name.startswith('.LC') and index:
                literals.append((value,index))
    for value,index in literals:
        sec = sections[index]
        candidates = [a for a,n,s in found if a > value]
        candidates += [a for a,ix in literals if ix == index and a > value]
        end = min(candidates + [sec[3]+sec[5]])
        data = raw[sec[4]+value-sec[3]:sec[4]+end-sec[3]]
        found.append((value,end-value,'literal:'+sha(data)))
    return found


def inventory(path, label):
    tool = ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    text = subprocess.run([str(tool), '-d', '-z', str(path)], capture_output=True,
                          text=True, check=True).stdout
    (OUT/'local'/('engine-'+label+'.disasm')).write_text(text)
    functions = symbols(path)
    objects = object_symbols(path)
    ins = []
    for line in text.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$', line)
        if m:
            ins.append((int(m[1],16), bytes.fromhex(m[2]), m[3]))
    result = {}
    for name, item in functions.items():
        start, size = item['address'], item['size']
        body = [(pc, raw, asm) for pc, raw, asm in ins if start <= pc < start+size]
        spans = set()
        tail_padding = 0
        for pc, raw, asm in body:
            if pc+len(raw) > start+size:
                tail = raw[start+size-pc:]
                assert tail in (b'\xf0\x00', b'\x70\x00'), (name,'unclassified tail',tail.hex())
                tail_padding += len(tail)
            for addr in range(pc,pc+len(raw)):
                if addr >= start+size:
                    continue
                assert addr not in spans, (name,hex(addr))
                spans.add(addr)
        assert spans == set(range(start,start+size)), (name,'undecoded bytes',size,len(spans))
        ops = [(pc, op.strip()) for pc, raw, asm in body
               for op in re.split(r' -> | \|\| ', asm)]
        normalized = []
        i = 0
        while i < len(ops):
            pc, op = ops[i]
            hi = re.fullmatch(r'seth (\w+),#(0x[0-9a-f]+|\d+)', op)
            lo = re.fullmatch(r'(add3|or3) (\w+),(\w+),#(-?(?:0x[0-9a-f]+|\d+))',
                              ops[i+1][1]) if i+1 < len(ops) else None
            if hi and lo and hi[1] == lo[2] == lo[3]:
                value = ((int(hi[2],0)<<16) + int(lo[4],0)) & 0xffffffff
                if hi[1] == 'r12':
                    normalized.append('PIC_DELTA r12')
                    i += 2
                    continue
                funcs = [n for n,s in functions.items() if s['address'] == value+256]
                if funcs:
                    normalized.append(f'FUNCTION {hi[1]},{canonical(funcs[0])}')
                    i += 2
                    continue
                matches = [(a,n,s) for a,n,s in objects if a <= value+256 < a+n]
                if matches:
                    a,n,s = min(matches, key=lambda x:x[1])
                    normalized.append(f'OBJECT {hi[1]},{s}+{value+256-a}')
                    i += 2
                    continue
            control = re.match(r'(b\w*(?:\.l)?|bl(?:\.l)?) (.*?)([0-9a-f]+) <([^>]+)>$',op)
            if control:
                target = int(control[3],16)
                if start <= target < start+size:
                    dest = 'self+'+str(target-start)
                else:
                    targets = [(n,s) for n,s in functions.items() if s['address'] == target]
                    dest = canonical(targets[0][0]) if targets else control[4]
                normalized.append(control[1]+' '+control[2]+dest)
            else:
                normalized.append(re.sub(r' <[^>]*>', '', op))
            i += 1
        result[canonical(name)] = dict(name=name,start=start,bytes=size,
            external_tail_nop_bytes=tail_padding,
            raw_sha256=sha(b''.join(raw for pc,raw,asm in body)), normalized=normalized)
    return result


def main():
    final = inventory(ELF, '123')
    comparisons = []
    for generation, tree in ((121,'engine_v43_fix'),(122,'engine_v44_keep')):
        prior = inventory(ROOT/'firmware'/tree/'candidate/local/full-r13/engine.elf', str(generation))
        exact, changed = [], []
        patches = []
        for name in sorted(set(prior) & set(final)):
            a,b=prior[name],final[name]
            if a['normalized'] == b['normalized']:
                exact.append(name)
            else:
                changed.append(dict(name=name,old_bytes=a['bytes'],new_bytes=b['bytes']))
                patches.extend(difflib.unified_diff([x+'\n' for x in a['normalized']],
                    [x+'\n' for x in b['normalized']], fromfile=f'{generation}/{name}',tofile=f'123/{name}'))
        (OUT/'local'/f'normalized-vs-{generation}.patch').write_text(''.join(patches))
        comparisons.append(dict(generation=generation,normalized_identical=exact,
            changed=changed,removed=sorted(set(prior)-set(final)),added=sorted(set(final)-set(prior))))
    save('evidence/binary-inventory.json',dict(status='INVENTORIED_FOR_MANUAL_REVIEW',
        dat_sha256=file_sha(DAT),comparisons=comparisons,
        normalization='M32R packets split; direct control targets become named functions or function-relative offsets; r12 PIC displacement and symbol-backed data offsets are normalized. This inventory is not a compiler equivalence proof.'))
    print([(c['generation'],len(c['normalized_identical']),len(c['changed']),c['removed'],c['added']) for c in comparisons])


if __name__ == '__main__':
    main()
