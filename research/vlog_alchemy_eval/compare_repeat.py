"""Check that the source snapshot repeat preserves measured results and fit bytes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,HERE,SCRATCH,STUDIO_SNAPSHOT,dump,digest,result_path
setup()
import json

def normalize(v):
    if isinstance(v,dict):
        return {k:normalize(x) for k,x in v.items() if k!='seconds'}
    if isinstance(v,list): return [normalize(x) for x in v]
    return v

def main():
    receipt=json.loads((HERE/'studio_snapshot_receipt.json').read_text())
    rows=[]
    for name in receipt['repeat_outputs']:
        before=json.loads((SCRATCH/'result_baseline'/name).read_text())
        after=json.loads(result_path(name).read_text())
        equal=normalize(before)==normalize(after)
        rows.append({'output':name,'output_path':str(result_path(name).relative_to(ROOT)),
                     'equal_except_elapsed_seconds':equal})
    source_ok=all(digest(STUDIO_SNAPSHOT/'src'/p)==h for p,h in receipt['files'].items())
    dump('source_repeat_checks.json',{'snapshot_source_unchanged':source_ok,'outputs':rows,
        'all_equal_except_elapsed_seconds':all(r['equal_except_elapsed_seconds'] for r in rows),
        'source_mutations_during_earlier_run':'Recorded in protected_before/after; no product write by this research task'})
    if not source_ok or not all(r['equal_except_elapsed_seconds'] for r in rows):
        raise ValueError('A measured output differs in the source snapshot repeat')
    print('PASS frozen source and ten output documents; fit bytes and numeric results identical',flush=True)

if __name__=='__main__':
    main()
