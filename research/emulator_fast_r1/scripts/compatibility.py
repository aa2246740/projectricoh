"""Replay the batch review counterexamples with only paths rebound."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,ROOT,FAST
enable()


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',default='compatibility-final1');args=p.parse_args()
    names=['hook_cases.py','r2_extended_hooks.py','r2_forwarding_hooks.py','r2_machine_forwarding.py']
    folder=HERE/args.name;assert not folder.exists();folder.mkdir();(folder/'local').mkdir()
    (folder/'scope_guard.py').write_text('import sys\nsys.path.insert(0,'+repr(str(HERE/'scripts'))+')\nfrom safety import enable\n')
    records=[]
    for name in names:
        source=ROOT/'research/emulator_batch'/name;target=folder/name
        assert not target.exists()
        text=source.read_text().replace('tools/gxr_emulator_batch','tools/gxr_emulator_fast')
        text=text.replace('research/emulator_batch','research/emulator_fast_r1')
        text=text.replace('ROOT = HERE.parents[1]','ROOT = Path('+repr(str(ROOT))+')')
        text=text.replace('from scope_guard import enable',"sys.path.insert(0, "+repr(str(FAST))+")\nfrom scope_guard import enable")
        target.write_text(text)
    for name in names:
        target=folder/name;source=ROOT/'research/emulator_batch'/name
        argv=[sys.executable,'-I','-B',str(HERE/'scripts/limit.py'),'600',str(target)]
        with (HERE/'runs'/(args.name+'-'+name+'.log')).open('w') as log:
            child=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=650)
        records.append(dict(script=name,exit_code=child.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),adapter_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        print(json.dumps(records[-1]),flush=True)
        if child.returncode:break
    (HERE/'runs'/(args.name+'.json')).write_text(json.dumps(dict(cases=records,passed=len(records)==len(names) and all(r['exit_code']==0 for r in records)),indent=2)+'\n')
    assert len(records)==len(names) and all(r['exit_code']==0 for r in records)


if __name__=='__main__':main()
