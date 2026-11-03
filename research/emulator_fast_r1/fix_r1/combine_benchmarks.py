"""Combine completed alternating groups with the exact same candidate identity."""
import argparse,json,os,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
ACCEPT=HERE/'acceptance'


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('groups',nargs='+');a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    source=None;raw=[];groups=[];count=0
    for name in a.groups:
        path=ACCEPT/'runs'/(name+'.json');record=json.loads(path.read_text())
        assert record['status']=='complete'
        if source is None:source=record['source_hashes']
        assert record['source_hashes']==source
        raw+=record['raw'];count+=record['repetitions'];groups.append(dict(path=str(path),repetitions=record['repetitions']))
    assert len(set(raw))==len(raw)
    rows=[json.loads(Path(path).read_text()) for path in raw]
    summary={}
    for kind in ('main','boot','recovery'):
        selected=[row for row in rows if row['kind']==kind]
        pairs={}
        for row in selected:
            key=row['name'].rsplit('-',1)[0];pairs.setdefault(key,{})[row['impl']]=row
        assert len(pairs)==count
        for pair in pairs.values():
            assert pair['batch']['points']==pair['fast']['points']
            assert pair['fast']['native_machine']['python_bus_calls']==0 and not pair['fast']['native_machine']['hle_callbacks']
        summary[kind]={}
        for impl in ('batch','fast'):
            values=[sum(segment['seconds'] for segment in pair[impl]['segments']) for pair in pairs.values()]
            summary[kind][impl]=dict(seconds=values,median=statistics.median(values),minimum=min(values),maximum=max(values))
        summary[kind]['speedup']=summary[kind]['batch']['median']/summary[kind]['fast']['median']
        summary[kind]['all_states_equal']=True
    target=ACCEPT/'runs'/(a.name+'.json');assert not target.exists()
    result=dict(status='complete',repetitions=count,groups=groups,raw=raw,summary=summary,source_hashes=source)
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',pairs_per_workload=count,speedups={k:v['speedup'] for k,v in summary.items()})))


if __name__=='__main__':main()
