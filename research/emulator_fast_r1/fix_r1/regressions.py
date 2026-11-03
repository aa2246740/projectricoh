"""Regression assertions for the independent review's five P1 counterexamples."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUNS=HERE/'runs'


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);a=p.parse_args()
    signal.alarm(900);assert os.getpriority(os.PRIO_PROCESS,0)>=15
    def run(script,name,*args):
        target=RUNS/(name+'.json');assert not target.exists()
        with (RUNS/(name+'.log')).open('w') as log:
            r=subprocess.run([sys.executable,'-I','-B',str(HERE/script),'--name',name,*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=350)
        assert r.returncode==0,(name,(RUNS/(name+'.log')).read_text()[-2500:])
        return json.loads(target.read_text())
    pair={b:run('edge_cases.py',a.phase+'-edges-'+b,'--backend',b) for b in ('native','reference')}
    checks=[]
    for case in pair['native']['cases']:
        x,y=pair['native']['cases'][case],pair['reference']['cases'][case]
        equal=x['detail']==y['detail'] and x['state']==y['state']
        checks.append(dict(test=case,passed=equal))
    overlay={b:run('preinstalled_overlay.py',a.phase+'-overlay-'+b,'--backend',b) for b in ('native','reference')}
    checks.append(dict(test='preinstalled-wrapper',passed=overlay['native']['state']==overlay['reference']['state'] and overlay['native']['r0']==overlay['reference']['r0']==84))
    snap=HERE/(a.phase+'-default.snap.z')
    original=run('snapshot_keys.py',a.phase+'-snapshot-create','--action','create','--snapshot',str(snap))
    for i,fixes in enumerate(('nand-read-tail','nand-word','preview-link','sd-long-response','nand-read-tail,preview-link','nand-word,preview-link,sd-long-response,nand-read-tail')):
        row=run('snapshot_keys.py',a.phase+'-snapshot-'+str(i),'--action','restore','--snapshot',str(snap),'--fixes',fixes)
        checks.append(dict(test='snapshot-key-'+fixes,passed=not row['identity_equal'] and row['key']!=original['key'] and not row['accepted'] and row['restore_target_unchanged'] and row['error']['message']=='snapshot input or emulator identity differs'))
    changed=run('snapshot_keys.py',a.phase+'-snapshot-input-source','--action','input-source')
    checks.append(dict(test='snapshot-input-source',passed=bool(changed['input_change_rejected'] and changed['source_change_rejected'])))
    result=dict(phase=a.phase,status='PASS' if all(row['passed'] for row in checks) else 'FAIL',checks=checks,failed=[r['test'] for r in checks if not r['passed']],load=os.getloadavg())
    (RUNS/(a.phase+'-regressions.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));assert result['status']=='PASS',result['failed']


if __name__=='__main__':main()
