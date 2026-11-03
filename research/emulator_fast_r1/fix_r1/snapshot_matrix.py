"""Every single-bit model change rejects a snapshot before changing its target."""
import argparse,json,os,signal,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
NAMES=('nand-word','preview-link','sd-long-response','nand-read-tail')


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15;signal.alarm(900)
    target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    def invoke(name,action,mask,snapshot):
        fixes=','.join(name for bit,name in enumerate(NAMES) if mask&(1<<bit))
        with (HERE/'runs'/(name+'.log')).open('x') as log:
            child=subprocess.run([sys.executable,'-I','-B',str(HERE/'snapshot_keys.py'),'--action',action,
                    '--fixes',fixes,'--name',name,'--snapshot',str(snapshot)],cwd=ROOT,
                    stdout=log,stderr=subprocess.STDOUT,timeout=90)
        assert child.returncode==0,(name,child.returncode)
        return json.loads((HERE/'runs'/(name+'.json')).read_text())
    rows=[];keys={}
    for mask in range(16):
        snapshot=HERE/'acceptance/local'/(a.name+'-'+str(mask)+'.snap.z')
        created=invoke(a.name+'-create-'+str(mask),'create',mask,snapshot);keys[mask]=created['key']
        for bit in range(4):
            changed=mask^(1<<bit)
            row=invoke(a.name+'-restore-'+str(mask)+'-'+str(changed),'restore',changed,snapshot)
            assert not row['accepted'] and not row['identity_equal'] and row['key']!=created['key']
            assert row['restore_target_unchanged'] and row['error']['message']=='snapshot input or emulator identity differs'
            rows.append(dict(source=mask,target=changed,passed=True))
        print(json.dumps(dict(source=mask,passed=True,changes=4)),flush=True)
    assert len(set(keys.values()))==16
    target.write_text(json.dumps(dict(status='PASS',keys=keys,checks=rows),indent=2)+'\n')


if __name__=='__main__':main()
