#!/usr/bin/env python3
"""Track saved PSW tokens through compiled branches, registers and stack slots."""
import re

def verify(text):
    functions={m[2]:m[3] for m in re.finditer(r'^([0-9a-f]+) <([^>]+)>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)',text,re.M|re.S)}
    rows=[]
    for name,body in functions.items():
        if '<rv_irq_save>' not in body:continue
        code=[]
        for match in re.finditer(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*(.*?)\s*$',body,re.M):
            pc=int(match[1],16)
            for i,op in enumerate(re.split(r' -> | \|\| ',match[2])):code.append((pc+2*i,op.strip()))
        addresses={pc:i for i,(pc,_) in enumerate(code)}
        initial=[None]*16;initial[15]=('sp',0)
        starts=[i for i,(_,op) in enumerate(code) if re.fullmatch(r'bl [0-9a-f]+ <rv_irq_save>',op)]
        todo=[(i,tuple(initial),(),()) for i in starts];seen=set();saves=set();restores=set();returns=0
        def reg(x):return 13 if x=='fp' else 14 if x=='lr' else 15 if x=='sp' else int(x[1:])
        def location(x,regs):
            m=re.fullmatch(r'@\((-?\d+),(r\d+|sp|fp)\)',x)
            if m:
                v=regs[reg(m[2])];return v[1]+int(m[1]) if isinstance(v,tuple) and v[0]=='sp' else None
            m=re.fullmatch(r'@(r\d+|sp|fp)',x)
            if m:
                v=regs[reg(m[1])];return v[1] if isinstance(v,tuple) and v[0]=='sp' else None
            return None
        while todo:
            state=todo.pop()
            if state in seen:continue
            seen.add(state);assert len(seen)<50000,(name,'CFG state bound')
            i,regs,mem,active=state
            assert 0<=i<len(code),(name,'fell outside function',active)
            pc,op=code[i];regs=list(regs);mem=dict(mem);stack=list(active);nexts=[i+1]
            call=re.fullmatch(r'(bl|bra) ([0-9a-f]+) <([^>]+)>',op)
            branch=re.match(r'(b\w+)\s+.*?([0-9a-f]+) <([^>]+)>$',op)
            if call and call[3].split('+')[0] in ('rv_irq_save','rv_irq_restore'):
                callee=call[3].split('+')[0]
                if callee=='rv_irq_save':
                    saves.add(pc);stack.append(('psw',pc));regs[:8]=[None]*8;regs[0]=stack[-1]
                else:
                    restores.add(pc);assert stack and regs[0]==stack[-1],(name,hex(pc),'restore is not original PSW',regs[0],stack)
                    stack.pop()
                    if not stack:returns+=1;continue
                if call[1]=='bra':assert not stack;returns+=1;continue
            elif call and call[1]=='bl':
                if int(call[2],16)!=pc+4:regs[:8]=[None]*8
            elif op.startswith('jl '):regs[:8]=[None]*8
            elif op.startswith('jmp ') and op!='jmp lr':
                assert not stack,(name,hex(pc),'unresolved branch under IRQ mask');continue
            elif op=='jmp lr':
                assert not stack,(name,hex(pc),'return with masked IRQ',stack);returns+=1;continue
            elif branch:
                target=int(branch[2],16)
                if target in addresses:
                    nexts=[addresses[target]] if branch[1]=='bra' else [i+1,addresses[target]]
                else:
                    assert not stack,(name,hex(pc),'tail with masked IRQ',stack)
                    if branch[1]=='bra':returns+=1;continue
            elif op.startswith('push '):
                r=reg(op[5:]);sp=regs[15][1]-4;regs[15]=('sp',sp);mem[sp]=regs[r]
            elif op.startswith('pop '):
                r=reg(op[4:]);sp=regs[15][1];regs[r]=mem.get(sp);mem.pop(sp,None);regs[15]=('sp',sp+4)
            else:
                m=re.fullmatch(r'mv (r\d+|sp|fp|lr),(r\d+|sp|fp|lr)',op)
                load=re.fullmatch(r'ld (r\d+|sp|fp|lr),(.+)',op)
                store=re.fullmatch(r'st (r\d+|sp|fp|lr),(.+)',op)
                add=re.fullmatch(r'(?:addi (r\d+|sp|fp),#|add3 (r\d+|sp|fp),(r\d+|sp|fp),#)(-?\d+)',op)
                if m:regs[reg(m[1])]=regs[reg(m[2])]
                elif load:regs[reg(load[1])]=mem.get(location(load[2],regs))
                elif store:
                    loc=location(store[2],regs)
                    if loc is not None:mem[loc]=regs[reg(store[1])]
                elif add:
                    dst=reg(add[1] or add[2]);src=reg(add[1] or add[3]);v=regs[src]
                    regs[dst]=('sp',v[1]+int(add[4])) if isinstance(v,tuple) and v[0]=='sp' else None
                elif re.match(r'(?:seth|ldi|ldub|lduh|ldb|ldh|or3|and3|xor|add |sub |neg |not |sll|srl|sra|mvfc) ',op):
                    dst=re.search(r' (r\d+|fp|lr|sp)',op)
                    if dst:regs[reg(dst[1])]=None
            mem=tuple(sorted((a,v) for a,v in mem.items() if v is not None))
            for j in nexts:todo.append((j,tuple(regs),mem,tuple(stack)))
        assert saves and restores and returns,(name,'no complete path',saves,restores,returns)
        rows.append(dict(function=name,save_calls=len(saves),restore_calls=len(restores),return_paths=returns,cfg_states=len(seen),status='PASS'))
    assert rows
    return rows
