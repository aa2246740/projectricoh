"""Search entry and interior references, including encoded relative branches."""
from pathlib import Path
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit

RANGES={
    'setter':(0x20268768,0x2026877c),
    'h01_parent':(0x20287080,0x202871d8),
    'h07_parent':(0x202871d8,0x202872e0),
    'h08_region':(0x202bb968,0x202bba30),
    'h06_parent':(0x202be220,0x202be6b8),
    'down':(0x202c25b8,0x202c27f4),
    'up':(0x202c2880,0x202c2abc),
}


def main():
    audit.preflight()
    raw,sections=audit.image('v36')
    index=json.loads((audit.LOCAL/'v36-index.json').read_text())
    table_file=audit.LOCAL/'relative-tables.json'
    tables=json.loads(table_file.read_text()) if table_file.exists() else []
    pointers={key:[] for key in RANGES}
    for offset in range(len(raw)-3):
        value=int.from_bytes(raw[offset:offset+4],'big')&~3
        if not 0x20268000<=value<0x202c2b00:continue
        for key,(lo,hi) in RANGES.items():
            if lo<=value<hi:
                pointers[key].append(dict(file_offset=offset,address=audit.address_of(sections,offset),target=value,aligned=offset%4==0))
    encoded=[]
    def signed(value,bits):return value-(1<<bits) if value&(1<<(bits-1)) else value
    def retain(source,target,kind):
        for key,(lo,hi) in RANGES.items():
            if lo<=target<hi and not lo<=source<hi:
                encoded.append(dict(range=key,source=source,target=target,kind=kind))
    for section in sections:
        data=raw[section['file']:section['file']+section['size']]
        for offset in range(0,len(data)-1,2):
            pc=section['va']+offset
            half=int.from_bytes(data[offset:offset+2],'big')
            half=half&0x7fff if pc%4==2 else half
            if half>>8 in (0x78,0x79,0x7c,0x7d,0x7e,0x7f):
                retain(pc,(pc&~3)+signed(half&255,8)*4,'branch8_candidate')
            if pc%4 or offset+4>len(data):continue
            word=int.from_bytes(data[offset:offset+4],'big')
            if word>>24 in (0xf8,0xf9,0xfc,0xfd,0xfe,0xff):
                retain(pc,pc+signed(word&0xffffff,24)*4,'branch32_candidate')
            elif word>>28==0xb and (word>>20)&15 in (0,1,8,9,10,11,12,13):
                retain(pc,pc+signed(word&65535,16)*4,'conditional32_candidate')
    results=[]
    for key,(lo,hi) in RANGES.items():
        row=dict(name=key,first=lo,end=hi,pointers=pointers[key],
            external_constants=[r for r in index['constants'] if lo<=r['value']&~3<hi and not lo<=r['source']<hi],
            external_calls=[r for r in index['calls']+index['branches'] if lo<=r['target']<hi and not lo<=r['source']<hi],
            relative_candidates=[dict(jump=t['jump'],table=t['table'],target=value) for t in tables for value in t['targets']
                if lo<=value<hi and not lo<=t['jump']<hi],
            encoded_candidates=[r for r in encoded if r['range']==key])
        results.append(row)
        print(key,{name:len(row[name]) for name in ('pointers','external_constants','external_calls','relative_candidates','encoded_candidates')})
    audit.save('local/range-references.json',dict(ranges=results,
        limitation='Byte patterns and linear decoded data can create false candidates. Runtime RAM pointers and general arithmetic remain unresolved.'))


if __name__=='__main__':main()
