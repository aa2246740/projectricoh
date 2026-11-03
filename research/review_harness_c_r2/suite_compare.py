"""Compare actual suite products and parse every audit tape record."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, sha
from independent_cases import differences

def read(path):return json.loads(Path(path).read_text())

def collect(folder,count):
    folder=Path(folder)
    summary=read(folder/'summary.json')
    children=[read(p) for p in sorted(folder.glob('child_*.json'))]
    assert summary['returncode']==0 and summary['fork_count']==count
    assert len(children)==count and all(c['returncode']==0 for c in children)
    products={}
    for mapping in [read(folder/'output_map.json')]+[c['output_map'] for c in children]:
        for logical,target in mapping.items():
            target=Path(target)
            if target.suffix!='.json' or not target.is_file():continue
            if '/local/view-reentry/' not in logical and '/evidence/view-reentry-' not in logical:continue
            name=logical.replace(str(ROOT)+'/','').replace('tools/native_harness_c/','tools/native_harness/')
            value=read(target)
            if name in products:assert products[name]==value,name
            products[name]=value
    assert len(products)==count+1 and all(v.get('status')=='PASS' for v in products.values())
    processes=[summary]+children
    timings=[t for p in processes for t in p['timings'] if t['name']=='interpreter_call']
    stats={}
    for t in timings:
        for k,v in t.get('native_stats',{}).items():stats[k]=stats.get(k,0)+v
    return products,dict(children=count,products=len(products),instruction_count=sum(t['steps'] or 0 for t in timings),
        native_stats=stats),processes

def leaves(value):
    if isinstance(value,dict):return sum(leaves(v) for v in value.values())
    if isinstance(value,(list,tuple)):return sum(leaves(v) for v in value)
    return 1

def parse_tape(path):
    raw=Path(path).read_bytes();offset=0;records=[]
    while offset<len(raw):
        assert offset+20<=len(raw)
        address,size,pc,text_size,data_size=struct.unpack_from('>5I',raw,offset)
        offset+=20
        assert size==data_size and offset+text_size+data_size<=len(raw)
        origin=raw[offset:offset+text_size].decode();offset+=text_size
        data=raw[offset:offset+data_size].hex();offset+=data_size
        records.append(dict(address=address,size=size,pc=pc,origin=origin,data=data))
    assert offset==len(raw)
    return records

def tapes(folder,processes):
    result={}
    for p in processes:
        for row in p['audit_tapes']:
            assert row['name'] not in result
            path=Path(folder)/'audit-tapes'/row['name']
            assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
            records=parse_tape(path)
            assert len(records)==row['records']
            result[row['name']]=dict(path=path,records=records,metadata=row)
    return result

def compare_tapes(left,right):
    assert set(left)==set(right),(set(left)-set(right),set(right)-set(left))
    rows=[]
    for name in sorted(left):
        a,b=left[name],right[name]
        diff=differences(a['records'],b['records'])
        byte_equal=a['path'].read_bytes()==b['path'].read_bytes()
        rows.append(dict(name=name,equal=not diff and byte_equal,records=len(a['records']),
                         bytes=a['path'].stat().st_size,left_sha256=sha(a['path']),right_sha256=sha(b['path']),
                         differences=diff[:5]))
    return dict(equal=all(r['equal'] for r in rows),files=len(rows),records=sum(r['records'] for r in rows),
                bytes=sum(r['bytes'] for r in rows),rows=rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('left',type=Path);p.add_argument('right',type=Path)
    p.add_argument('--children',type=int,default=28);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();enable()
    a,ma,pa=collect(args.left,args.children);b,mb,pb=collect(args.right,args.children)
    diff=differences(a,b)
    tape=compare_tapes(tapes(args.left,pa),tapes(args.right,pb))
    assert tape['files']>0 and tape['records']>0
    equal=not diff and ma['instruction_count']==mb['instruction_count'] and tape['equal']
    result=dict(equal=equal,json_files=len(a),compared_values=leaves(a),differences=diff[:20],left=ma,right=mb,audit_tapes=tape)
    emit(args.output,result)
    print(json.dumps({k:result[k] for k in ('equal','json_files','compared_values')}),flush=True)
    print(json.dumps({k:tape[k] for k in ('equal','files','records','bytes')}),flush=True)
    assert equal

if __name__=='__main__':main()
