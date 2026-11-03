"""One serial validation lane; the other compute slot is the alternating benchmark."""
import argparse,datetime,json,os,signal,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ACCEPT=HERE/'acceptance'


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    os.environ['GIT_OPTIONAL_LOCKS']='0'
    signal.alarm(7500)
    target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    steps=[
        ('p1-regressions',HERE/'regressions.py',['--phase',a.name]),
        ('extended',HERE/'run_extended.py',['--name',a.name+'-extended']),
        ('additional',HERE/'run_additional.py',['--name',a.name+'-additional']),
        ('hold-bindings',HERE/'run_hold.py',['--name',a.name+'-hold-bindings']),
        ('retained-snapshot-native',HERE/'retained_snapshot.py',['--backend','native','--name',a.name+'-retained-snapshot-native']),
        ('retained-snapshot-reference',HERE/'retained_snapshot.py',['--backend','reference','--name',a.name+'-retained-snapshot-reference']),
        ('wide-snapshot-native',HERE/'wide_snapshot.py',['--backend','native','--name',a.name+'-wide-snapshot-native']),
        ('wide-snapshot-reference',HERE/'wide_snapshot.py',['--backend','reference','--name',a.name+'-wide-snapshot-reference']),
        ('switches',HERE/'switch_matrix.py',['--name',a.name+'-switches']),
        ('snapshot-matrix',HERE/'snapshot_matrix.py',['--name',a.name+'-snapshot-matrix']),
        ('suite',ACCEPT/'scripts/suite.py',['--name',a.name+'-suite','--jobs','1']),
        ('current-inputs',HERE/'current_acceptance.py',['--suite',a.name+'-suite','--name',a.name+'-current-inputs']),
        ('snapshots',ACCEPT/'scripts/snapshot_check.py',['--name',a.name+'-snapshots']),
        ('snapshot-edges',ACCEPT/'scripts/snapshot_edges.py',['--name',a.name+'-snapshot-edges']),
        ('g145',ACCEPT/'g145_replay.py',['--impl','batch',a.name+'-g145']),
        ('g145-compare',ACCEPT/'g145_compare.py',[str(ROOT/'research/emulator_batch/local/g145/run-batch'),
             str(ACCEPT/'local/g145'/(a.name+'-g145')),str(ACCEPT/'runs'/(a.name+'-g145-comparison.json'))]),
        ('mutation',ACCEPT/'scripts/mutation_check.py',['--name',a.name+'-mutation']),
        ('codec',ACCEPT/'scripts/codec_check.py',[]),
        ('reviewed-workloads',HERE/'reviewed_workloads.py',['--name',a.name+'-reviewed']),
        ('seal',HERE/'seal.py',['--name',a.name+'-seal-after','--verify',str(HERE/'runs/delivery-candidate.json')]),
    ]
    result=dict(status='RUNNING',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),steps=[])
    for label,script,args in steps:
        began=time.perf_counter()
        with (HERE/'runs'/(a.name+'-lane-'+label+'.log')).open('x') as log:
            child=subprocess.run([sys.executable,'-I','-B',str(script),*args],cwd=ROOT,
                    stdout=log,stderr=subprocess.STDOUT,timeout=6300 if label=='reviewed-workloads' else 1800)
        row=dict(step=label,exit_code=child.returncode,seconds=time.perf_counter()-began,load=os.getloadavg())
        result['steps'].append(row);target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        assert child.returncode==0,(label,child.returncode)
    result['status']='PASS';target.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
