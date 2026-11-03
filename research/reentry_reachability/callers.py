"""List fixed callers and candidate containing functions; keep context gaps explicit."""
from pathlib import Path
import bisect
import json
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit
import flow


def main():
    audit.preflight()
    index=json.loads((audit.LOCAL/'v36-index.json').read_text())
    packets=flow.listing()
    tables=flow.relative_tables(packets,index)
    raw,sections=audit.image('v36')
    transfers={r['source']:r for r in index['calls']}
    fixed=index['calls']+index['branches']
    seeds={r['target'] for r in fixed}
    seeds.update(r['value'] for r in index['constants'] if r['value'] in packets)
    seeds.update((0x202871d8,0x20287080,0x2027c3b0))
    pointer_map={}
    for section in sections:
        for offset in range(section['file'],section['file']+section['size']-3,4):
            value=int.from_bytes(raw[offset:offset+4],'big')
            if value in packets:
                seeds.add(value)
                pointer_map.setdefault(value,[]).append(section['va']+offset-section['file'])
    entries=sorted(pc for pc in seeds if pc in packets and (pc in (0x202871d8,0x20287080) or
        any(re.match(r'(?:push |addi sp,#-|add3 sp,sp,#)',op)
            for p in (pc,pc+4,pc+8) for op in packets.get(p,[]))))
    cache={}
    def owner(site):
        candidates=[]
        end=bisect.bisect_right(entries,site)
        for start in reversed(entries[max(0,end-220):end]):
            if site-start>0x8000:break
            if start not in cache:cache[start]=flow.inspect(start,packets,transfers,tables)
            if site&~3 in cache[start]['visited']:
                candidates.append(start)
                break
        return candidates[0] if candidates else None
    targets=([int(value,16) for value in sys.argv[1:]] if len(sys.argv)>1 else
        [0x20268768,0x202bb4bc,0x202c25b8,0x202c2880,0x20287080,0x202871d8,0x202be220,0x202b1100])
    results=[]
    for target in targets:
        rows=[]
        for ref in fixed:
            if ref['target']!=target:continue
            start=owner(ref['source'])
            row={**ref,'owner_candidate':start,'owner_context_proven':False}
            if start is not None:
                row['owner_fixed_callers']=[r['source'] for r in fixed if r['target']==start]
                row['owner_pointer_slots']=pointer_map.get(start,[])
                row['owner_unresolved']=cache[start]['unresolved']
            rows.append(row)
        result=dict(target=target,fixed_callers=rows,pointer_slots=pointer_map.get(target,[]),
            limitation='Containing functions are control-flow candidates; task context needs separate table and registration analysis.')
        results.append(result)
        print(hex(target),'fixed',len(rows),'pointers',len(result['pointer_slots']))
        for row in rows:
            print(' ',hex(row['source']),hex(row['owner_candidate']) if row['owner_candidate'] else None,
                'parents',[hex(v) for v in row.get('owner_fixed_callers',[])],
                'slots',[hex(v) for v in row.get('owner_pointer_slots',[])])
    stem='callers'+('-'+'-'.join(sys.argv[1:]) if len(sys.argv)>1 else '')
    audit.save('local/'+stem+'.json',results)
    audit.save('local/'+stem+'-functions.json',list(cache.values()))


if __name__=='__main__':main()
