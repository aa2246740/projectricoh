"""Re-run the independent review's SD, menu and corrected recovery paths."""
import argparse,json,os,signal,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUNS=HERE/'runs'


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15;signal.alarm(6200)
    result=dict(status='RUNNING',comparisons=[])
    target=RUNS/(a.name+'.json');assert not target.exists()
    def invoke(script,name,backend,*args):
        with (RUNS/(name+'.log')).open('x') as log:
            child=subprocess.run([sys.executable,'-I','-B',str(HERE/script),
                    '--backend',backend,'--name',name,*map(str,args)],cwd=ROOT,
                    stdout=log,stderr=subprocess.STDOUT,timeout=1750)
        assert child.returncode==0,(name,child.returncode)
        return json.loads((RUNS/(name+'.json')).read_text())
    def compare(label,pair):
        assert pair['native']['points']==pair['reference']['points'],label
        if 'final' in pair['native']:assert pair['native']['final']==pair['reference']['final'],label
        result['comparisons'].append(dict(label=label,passed=True,points=len(pair['native']['points']),
                                         steps=list(pair['native']['points'].values())[-1]['steps']))
        target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result['comparisons'][-1]),flush=True)
    compare('keys-and-SD',{b:invoke('sd_sequence.py',a.name+'-sd-'+b,b) for b in ('native','reference')})
    previous={}
    for index in range(1,5):
        pair={}
        for backend in ('native','reference'):
            name=a.name+'-menu-'+str(index)+'-'+backend
            extra=['--resume',previous[backend]] if backend in previous else []
            pair[backend]=invoke('segmented_scenarios.py',name,backend,'--kind','menu','--span',100000000,*extra)
            previous[backend]=HERE/(name+'.snap.z')
        compare('menu-segment-'+str(index),pair)
    pair={b:invoke('menu_published.py',a.name+'-published-'+b,b,'--snapshot',previous[b]) for b in ('native','reference')}
    assert all(row['status']=='COMPLETE' and row['menu_open'] for row in pair.values())
    compare('g154-first-eight-row-menu',pair)
    pair={b:invoke('segmented_scenarios.py',a.name+'-recovery-'+b,b,'--kind','recovery','--span',100000000)
          for b in ('native','reference')}
    assert all(row['status']=='COMPLETE' and row['complete'] for row in pair.values())
    compare('four-correction-recovery',pair)
    result['status']='PASS';target.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
