"""Bounded control-flow inventory, with unresolved register transfers retained."""
from pathlib import Path
import argparse
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit


def listing():
    packets = {}
    for path in sorted(audit.LOCAL.glob('v36-s??.asm')):
        for line in path.read_text().splitlines():
            match = audit.LINE.match(line)
            if match:
                pc = int(match[1],16)
                packets[pc] = re.split(r'\s*(?:->|\|\|)\s*',match[3].strip())
    return packets


def inspect(entry, packets, transfers, tables=None, limit=24000):
    pending = [entry]
    seen, calls, unknown = set(), {}, []
    while pending:
        pc = pending.pop()
        if pc in seen: continue
        if pc not in packets or len(seen) >= limit:
            unknown.append(dict(source=pc,kind='outside_decoded_bound'))
            continue
        seen.add(pc)
        fall = True
        for i, op in enumerate(packets[pc]):
            site = pc + 2*i
            if match := re.fullmatch(r'(b\w*)\s+(?:[^ ]*,)?(0x[0-9a-f]+|[0-9a-f]+)',op):
                kind, dest = match[1],int(match[2],16)
                if kind in ('bl','bl.s','bl.l','bcl','bncl'):
                    calls[site] = dict(source=site,target=dest,kind=kind)
                else:
                    pending.append(dest)
                    if kind in ('bra','bra.s','bra.l'): fall=False
            elif match := re.fullmatch(r'(jl|jmp|jc|jnc) (r\d+|lr|fp|sp)',op):
                kind, reg = match.groups()
                if reg == 'lr' and kind == 'jmp':
                    fall=False
                elif kind == 'jmp' and tables and site in tables:
                    pending.extend(tables[site]['targets'])
                    fall=False
                elif site in transfers:
                    calls[site] = transfers[site]
                    if kind == 'jmp': fall=False
                else:
                    unknown.append(dict(source=site,kind=kind,register=reg))
                    if kind == 'jmp': fall=False
            elif op.startswith(('trap ','rte')):
                unknown.append(dict(source=site,kind=op))
                if op=='rte': fall=False
            elif '*unknown*' in op:
                unknown.append(dict(source=site,kind='undecoded_item'))
                fall=False
        if fall: pending.append(pc+4)
    return dict(entry=entry,packets=len(seen),first=min(seen) if seen else None,
        last=max(seen) if seen else None,calls=list(calls.values()),unresolved=unknown,
        visited=sorted(seen))


def relative_tables(packets, index):
    ops=[(pc+2*i,op) for pc,part in sorted(packets.items()) for i,op in enumerate(part)]
    constants={r['source']:r for r in index['constants']}
    raw,sections=audit.image('v36')
    out={}
    for i,(pc,op) in enumerate(ops):
        match=re.fullmatch(r'jmp (r\d+|fp)',op)
        if not match:continue
        reg=match[1]
        adds=[(j,m[1]) for j in range(max(0,i-4),i)
            if (m:=re.fullmatch('add '+re.escape(reg)+r',(r\d+|fp|lr)',ops[j][1]))]
        if not adds:continue
        ai,offset_reg=adds[-1]
        bases=[constants[ops[j][0]] for j in range(max(0,ai-8),ai)
            if ops[j][0] in constants and constants[ops[j][0]]['register']==reg]
        if not bases:continue
        loads=[(j,m[1],m[2]) for j in range(max(0,ai-15),ai)
            if (m:=re.fullmatch(r'(ldh|ldub|ldb|lduh|ld) '+re.escape(offset_reg)+r',@(r\d+|fp|lr)',ops[j][1]))]
        if not loads:continue
        li,kind,table_reg=loads[-1]
        refs=[constants[ops[j][0]] for j in range(max(0,li-24),li)
            if ops[j][0] in constants and constants[ops[j][0]]['register']==table_reg]
        if not refs:continue
        counts=[int(m[1],0) for j in range(max(0,li-24),li)
            if (m:=re.fullmatch(r'cmpui (?:r\d+|fp|lr),#(0x[0-9a-f]+|\d+)',ops[j][1]))]
        width=4 if kind=='ld' else 2 if kind in ('ldh','lduh') else 1
        count=counts[-1] if counts and 0<counts[-1]<2048 else 256
        base,table=bases[-1]['value'],refs[-1]['value']
        try:data=audit.at(raw,sections,table,count*width)
        except ValueError:continue
        targets=[(base+int.from_bytes(data[j*width:(j+1)*width],'big',signed=kind in ('ldh','ldb','ld')))&0xfffffffc for j in range(count)]
        out[pc]=dict(jump=pc,table=table,base=base,width=width,count=count,targets=targets,
            bounds_reviewed=False,context=[dict(pc=p,op=o) for p,o in ops[max(0,li-24):i+1]])
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entries',nargs='+')
    parser.add_argument('--tables',action='store_true')
    args=parser.parse_args()
    audit.preflight()
    index=json.loads((audit.LOCAL/'v36-index.json').read_text())
    transfers={r['source']:r for r in index['calls']}
    packets=listing()
    tables=relative_tables(packets,index) if args.tables else {}
    if args.tables:audit.save('local/relative-tables.json',list(tables.values()))
    rows=[]
    for value in args.entries:
        entry=int(value,16)
        row=inspect(entry,packets,transfers,tables)
        rows.append(row)
        print(json.dumps(dict(entry=hex(entry),packets=row['packets'],last=hex(row['last']) if row['last'] else None,
            call_count=len(row['calls']),calls=[(hex(r['source']),hex(r['target'])) for r in row['calls'][:12]],
            unresolved=[{**r,'source':hex(r['source'])} for r in row['unresolved']]),ensure_ascii=False))
    audit.save('local/flow-'+('tables-' if args.tables else '')+'-'.join(args.entries)+'.json',rows)


if __name__=='__main__':main()
