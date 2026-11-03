"""Check all sixteen correction selections through guest device operations."""
import argparse,itertools,json,os,signal,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ACCEPT=HERE/'acceptance'
NAMES=('nand-word','preview-link','sd-long-response','nand-read-tail')


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15;signal.alarm(1800)
    target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    rows=[]
    for mask in range(16):
        fixes=','.join(name for bit,name in enumerate(NAMES) if mask&(1<<bit))
        pair={}
        for backend in ('native','reference'):
            name=a.name+'-'+str(mask)+'-'+backend
            with (HERE/'runs'/(name+'.log')).open('x') as log:
                child=subprocess.run([sys.executable,'-I','-B',str(ACCEPT/'scripts/native_corrections.py'),
                    '--backend',backend,'--fixes',fixes,'--name',name],cwd=ROOT,
                    stdout=log,stderr=subprocess.STDOUT,timeout=180)
            assert child.returncode==0,(name,child.returncode)
            pair[backend]=json.loads((ACCEPT/'runs'/(name+'.json')).read_text())
        fields=('sd_rows','nand_rows','nand_state','text_rows','text_final','preview','model_revision','full_states')
        assert all(pair['native'][key]==pair['reference'][key] for key in fields),fixes
        rows.append(dict(mask=mask,fixes=fixes,passed=True,full_state_count=len(pair['native']['full_states'])))
        target.write_text(json.dumps(dict(status='RUNNING',rows=rows),indent=2)+'\n')
        print(json.dumps(rows[-1]),flush=True)
    target.write_text(json.dumps(dict(status='PASS',rows=rows,load=os.getloadavg()),indent=2)+'\n')


if __name__=='__main__':main()
