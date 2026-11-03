"""Recompute acceptance equivalence from the actual review products."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, sha

def read(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate JSON key: '+key)
            result[key]=value
        return result
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs)

def compare(left,right):
    differences=[];count=[0]
    def walk(a,b,path):
        if type(a) is not type(b):differences.append(dict(path=path,reason='type'))
        elif isinstance(a,dict):
            if set(a)!=set(b):differences.append(dict(path=path,reason='keys'))
            for key in sorted(set(a)&set(b)):walk(a[key],b[key],path+'/'+str(key))
        elif isinstance(a,list):
            if len(a)!=len(b):differences.append(dict(path=path,reason='length'))
            for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i))
        else:
            count[0]+=1
            if a!=b:differences.append(dict(path=path,left=a,right=b))
    walk(left,right,'')
    return dict(equal=not differences,compared_values=count[0],differences=differences,excluded_paths=[])

def view(folder):
    process=read(folder/'summary.json')
    children=[read(path) for path in sorted(folder.glob('child_*.json'))]
    mappings=[read(folder/'output_map.json')]+[child['output_map'] for child in children]
    products={}
    for mapping in mappings:
        for logical,target in mapping.items():
            path=Path(target)
            if path.suffix!='.json' or not path.is_file():continue
            if '/local/view-reentry/' not in logical and not logical.endswith('/evidence/view-reentry-50mm.json'):continue
            name=logical.replace(str(ROOT)+'/','').replace('tools/native_harness_c/','tools/native_harness/')
            value=read(path)
            if name in products and products[name]!=value:raise ValueError('conflicting logical products')
            products[name]=value
    assert process['returncode']==0 and len(children)==28 and all(child['returncode']==0 for child in children)
    assert len(products)==29 and all(value.get('status')=='PASS' for value in products.values())
    suite=next(value for name,value in products.items() if '/evidence/view-reentry-' in name)
    assert len(suite['cases'])==28
    assert {row['cut'] for row in suite['cases']}=={'entry','row_draw'}
    assert {row['view'] for row in suite['cases']}=={'L1','card','items','value','groups','entries','ERR'}
    assert {row['key'] for row in suite['cases']}=={'UP','DOWN'}
    all_processes=[process]+children
    instructions=sum(item['steps'] or 0 for record in all_processes for item in record['timings'] if item['name']=='interpreter_call')
    native=sum(item.get('native_stats',{}).get('instructions',0) for record in all_processes for item in record['timings'] if item['name']=='interpreter_call')
    stats={}
    for record in all_processes:
        for item in record['timings']:
            for key,value in item.get('native_stats',{}).items():stats[key]=stats.get(key,0)+value
    return products,dict(children=len(children),products=len(products),instructions=instructions,native_instructions=native,native_stats=stats)

def main():
    enable()
    a,b=[HERE/'local'/('fixed-'+side+'-50mm') for side in ('python','c')]
    check=compare(read(a/'result.json'),read(b/'result.json'))
    ma,mb=read(a/'metrics.json'),read(b/'metrics.json')
    check['instruction_count_equal']=ma['instruction_count']==mb['instruction_count']
    check['opcode_count_equal']=ma['opcode_count']==mb['opcode_count']
    check['instruction_count']=ma['instruction_count'];check['opcode_count']=ma['opcode_count']
    check['raw_json_sha256']=[sha(folder/'local/accept-50mm.json') for folder in (a,b)]
    emit(HERE/'local/fixed-comparison.json',check)
    assert check['equal'] and check['instruction_count_equal'] and check['opcode_count_equal']
    print(json.dumps(dict(fixed=check)),flush=True)
    if (HERE/'local/view-c/summary.json').is_file() and (HERE/'local/view-python/summary.json').is_file():
        va,vma=view(HERE/'local/view-python');vb,vmb=view(HERE/'local/view-c')
        result=compare(va,vb)
        result.update(left=vma,right=vmb,instruction_count_equal=vma['instructions']==vmb['instructions'])
        emit(HERE/'local/view-comparison.json',result)
        assert result['equal'] and result['instruction_count_equal'] and vmb['native_instructions']>0
        print(json.dumps(dict(view=result)),flush=True)
    if (HERE/'local/snapshot-cold/result.json').is_file() and (HERE/'local/snapshot-restore/result.json').is_file():
        snap=compare(read(HERE/'local/snapshot-cold/result.json'),read(HERE/'local/snapshot-restore/result.json'))
        emit(HERE/'local/snapshot-comparison.json',snap)
        assert snap['equal']
        print(json.dumps(dict(snapshot=snap)),flush=True)

if __name__=='__main__':main()
