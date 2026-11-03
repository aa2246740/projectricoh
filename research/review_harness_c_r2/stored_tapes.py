"""Independently reparse and compare the retained full audit-tape evidence."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, sha
from suite_compare import collect, tapes, compare_tapes

def main():
    enable()
    base=ROOT/'research/speed_hillclimb/local'
    left=base/'r2-api4-audit-00-off'
    right=base/'r2-api4-audit-00-on'
    if not left.is_dir() or not right.is_dir():
        raise ValueError('retained evidence directories differ; inspect before choosing inputs')
    _,_,pa=collect(left,70);_,_,pb=collect(right,70)
    a=tapes(left,pa);b=tapes(right,pb)
    result=compare_tapes(a,b)
    assert result['equal'] and result['files']==71 and result['records']==994
    mutant=base/'r2-api4-mutation-witness-mutant'
    _,_,pm=collect(mutant,70)
    m=tapes(mutant,pm)
    mutation_equal=all(a[name]['records']==m[name]['records'] for name in set(a)&set(m)) and set(a)==set(m)
    result.update(kind='independent replay comparison of retained 70-child tapes; no new full-suite run',
        left=str(left),right=str(right),mutation_rejected=not mutation_equal,
        mutant_files=len(m),mutant_records=sum(len(row['records']) for row in m.values()),
        source_summaries={str(p/'summary.json'):sha(p/'summary.json') for p in (left,right,mutant)})
    assert result['mutation_rejected'] and result['mutant_records']==993
    emit(HERE/'local/stored-audit-comparison.json',result)
    print(json.dumps({k:result[k] for k in ('equal','files','records','bytes','mutation_rejected','mutant_records')}),flush=True)

if __name__=='__main__':main()
