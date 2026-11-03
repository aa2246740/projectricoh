"""Static call graph of native routines in the body MAIN image (recursive descent over the repo's
M32R objdump listing).  Used for the gen 146 lock proof: which routines a given root reaches, and
whether any of them reaches the file semaphore 47 wait/signal (0x0500D4E4 / 0x0500D4FC), the raw
semaphore wrappers 0x2005E360 / 0x2005E31C, or the kernel trap stubs, or makes an indirect call
that a static walk cannot resolve.

usage: callgraph.py IMAGE ROOT [ROOT ...]        (hex VMAs; prints JSON)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m32r_listing import dis  # noqa: E402

RANGES = ((0x2004B000, 0x20054F24), (0x20055000, 0x200D88C4), (0x200D9000, 0x20108E0C),
          (0x20109000, 0x20142C9C), (0x20143000, 0x20154EC8), (0x20155000, 0x201BD535),
          (0x201BDC00, 0x2025D6BC), (0x2025D800, 0x20380372), (0x20380800, 0x203ACFA6),
          (0x203AD000, 0x203C7624), (0x203C7C00, 0x2040AF84), (0x05000C00, 0x0500F8FC))
SEM47 = {0x0500D4E4: 'wait47', 0x0500D4FC: 'signal47', 0x0500D4CC: 'create47'}
RAW_SEM = {0x2005E360: 'twai-wrapper', 0x2005E31C: 'signal-wrapper'}
BRANCH = re.compile(r'^(bra|bc|bnc|beq|bne|beqz|bnez|bltz|bgez|bgtz|blez|bl)$')
CALLEE_SAVED = {'r8', 'r9', 'r10', 'r11', 'r12', 'fp'}
LINE = re.compile(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} ){4}\s*(.*)$')


def parse(text):
    out = {}
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        address = int(m.group(1), 16)
        parts = [p.strip() for p in re.split(r'\s*(?:->|\|\|)\s*', m.group(2))]
        # a 32-bit word holds one long insn or two 16-bit insns (second at address+2)
        out[address] = parts[0]
        if len(parts) > 1:
            out[address + 2] = parts[1]
    return out


class Graph:
    def __init__(self, image):
        raw = Path(image).read_bytes()
        self.insn = {}
        for start, end in RANGES:
            self.insn.update(parse(dis(raw, start, end)))

    def function(self, root):
        """Instructions reachable inside one function; returns (calls, indirect, traps)."""
        seen, todo = set(), [root]
        calls, indirect, traps = set(), [], []
        while todo:
            pc = todo.pop()
            regs = {}
            while pc not in seen and pc in self.insn:
                seen.add(pc)
                text = self.insn[pc]
                op, _, args = text.partition(' ')
                args = [a.strip() for a in args.split(',')] if args else []
                nxt = pc + 2 if pc % 4 == 0 and pc + 2 in self.insn else (pc & ~3) + 4
                if op == 'seth':
                    regs[args[0]] = int(args[1].lstrip('#'), 16) << 16
                elif op == 'or3' and args[0] == args[1] and args[0] in regs:
                    regs[args[0]] |= int(args[2].lstrip('#'), 16)
                elif op == 'ld24':
                    regs[args[0]] = int(args[1], 16)
                elif op == 'trap':
                    traps.append(hex(pc))
                elif op in ('jl', 'jmp'):
                    if args[0] == 'lr':
                        break
                    target = regs.get(args[0])
                    if target is None:
                        indirect.append(hex(pc))
                    elif op == 'jl':
                        calls.add(target)
                    else:
                        calls.add(target)  # tail jump: treat as a call
                    if op == 'jmp':
                        break
                    regs = {k: v for k, v in regs.items() if k in CALLEE_SAVED}
                elif BRANCH.match(op):
                    target = int(args[-1], 16)
                    if op == 'bl':
                        calls.add(target)
                        regs = {k: v for k, v in regs.items() if k in CALLEE_SAVED}
                    elif op == 'bra':
                        pc = target
                        continue
                    else:
                        todo.append(target)
                elif op in ('rte',):
                    break
                elif args and args[0] in regs and op not in ('st', 'stb', 'sth', 'cmp', 'cmpu', 'cmpi',
                                                             'cmpui', 'push', 'jl', 'jmp'):
                    regs.pop(args[0], None)
                pc = nxt
        return calls, indirect, traps

    def walk(self, roots, stop=()):
        report, todo, done = {}, list(roots), set()
        while todo:
            fn = todo.pop()
            if fn in done:
                continue
            done.add(fn)
            if fn in SEM47 or fn in RAW_SEM or fn in stop or fn not in self.insn:
                report[hex(fn)] = {'leaf': SEM47.get(fn) or RAW_SEM.get(fn) or
                                   ('stop' if fn in stop else 'outside-listing')}
                continue
            calls, indirect, traps = self.function(fn)
            report[hex(fn)] = {'calls': sorted(hex(c) for c in calls), 'indirect': indirect, 'traps': traps}
            todo.extend(calls)
        return report


def main():
    graph = Graph(sys.argv[1])
    roots = [int(a, 16) for a in sys.argv[2:]]
    report = graph.walk(roots)
    touched = sorted(k for k, v in report.items() if v.get('leaf') in ('wait47', 'signal47', 'create47',
                                                                       'twai-wrapper', 'signal-wrapper'))
    print(json.dumps({'roots': [hex(r) for r in roots], 'functions': len(report), 'semaphore_leaves': touched,
                      'indirect': {k: v['indirect'] for k, v in report.items() if v.get('indirect')},
                      'traps': {k: v['traps'] for k, v in report.items() if v.get('traps')},
                      'outside': sorted(k for k, v in report.items() if v.get('leaf') == 'outside-listing'),
                      'graph': report}, indent=1))


if __name__ == '__main__':
    main()
