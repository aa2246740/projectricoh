"""Serial native cases with bounded runs and Python replay of any unexpected C failure."""
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_review import ROOT,REVIEW,LOCAL,SOURCE,sha,save,setup

records=[]

def run(mode,name,args=(),backend='c',script=None,timeout=900):
    command=['/usr/bin/python3','-I','-B',str(script or REVIEW/'run_review.py')]
    if script is None:command.append(mode)
    command+=list(args)
    started=time.monotonic()
    with (LOCAL/(name+'.log')).open('w') as output:
        try:
            proc=subprocess.run(command,cwd=ROOT,env=dict(os.environ,GXR_HARNESS_BACKEND=backend),
                stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
            code=proc.returncode
        except subprocess.TimeoutExpired:
            code=124
    records.append(dict(name=name,backend=backend,returncode=code,seconds=time.monotonic()-started,command=command))
    save(LOCAL/'suite-jobs.json',records)
    print(json.dumps(records[-1]),flush=True)
    if code:
        if backend=='c':
            replay=[value+'-python-replay' if value==name else value for value in args]
            run(mode,name+'-python-replay',replay,'python',script,timeout)
        raise RuntimeError('Case failed; any C failure replayed on Python: '+name)

def prepare_restart():
    cases=[]
    for unit,name,prefix in [('mount','mount-owner-c','m'),('50mm','j-owner-c','j'),('28mm','q-owner-c','q')]:
        folder=LOCAL/'native'/name
        result=json.loads((folder/'result.json').read_text())
        assert result['status']=='PASS' and result['backend']=='c'
        inputs=[]
        for path in sorted(folder.glob('*-S.bin')):
            if '-A-' in path.name:continue
            data=path.read_bytes()
            assert len(data)==4096 and data[0xfd4:0xffc]==bytes(40)
            serialized=data[:4092]+(sum(struct.unpack('>2046H',data[:4092]))&0xffffffff).to_bytes(4,'big')
            inputs.append(dict(file=str(path.relative_to(ROOT)),original_sha256=sha(data),serialized_sha256=sha(serialized)))
        assert len(inputs)==(6 if unit=='mount' else 3)
        assert len({row['serialized_sha256'] for row in inputs})==1
        old=(SOURCE/'local/restart-inputs'/(unit+'.bin')).read_bytes()
        assert serialized==old,'Independent saved state differs from cold-boot source'
        cold=SOURCE/'local/cold'/(prefix+'-restart-final')
        snapshot=json.loads((cold/'snapshot.json').read_text())
        assert (cold/'cold-S.bin').read_bytes()==serialized
        assert snapshot['settings_source_sha256']==sha(serialized)
        assert snapshot['settings_source_reads'] and all(r['source_sha256']==sha(serialized) for r in snapshot['settings_source_reads'])
        assert sha((cold/'standby.snap.z').read_bytes())==snapshot['sha256']
        output=LOCAL/'restart-inputs'/(unit+'.bin');output.parent.mkdir(exist_ok=True);output.write_bytes(serialized)
        cases.append(dict(unit=unit,independent_post_B_inputs=inputs,serialized_sha256=sha(serialized),
            matches_frozen_MAIN_restart_input=True,snapshot_sha256=snapshot['sha256'],
            scope='Review reruns native consumer from a frozen producer MAIN result. Full MAIN boot is not rerun.'))
    save(LOCAL/'restart-source-review.json',dict(status='PASS',cases=cases))

def main():
    setup()
    run('native','q-owner-c',['--unit','28mm','--name','q-owner-c','--snapshot',str(SOURCE/'local/cold/q-final-cold/standby.snap.z')])
    prepare_restart()
    for unit,prefix in [('mount','m'),('50mm','j'),('28mm','q')]:
        original=SOURCE/'local/cold'/(prefix+'-final-cold')/'standby.snap.z'
        restarted=SOURCE/'local/cold'/(prefix+'-restart-final')/'standby.snap.z'
        name=prefix+'-restart-open-c'
        run('native',name,['--unit',unit,'--name',name,'--snapshot',str(restarted),'--initial-only'])
        for kind in ('header-crc','payload-crc','effect-crc'):
            name=prefix+'-'+kind+'-c'
            run('native',name,['--unit',unit,'--name',name,'--snapshot',str(original),
                '--dat',str(LOCAL/'host'/(kind+'.DAT')),'--reject'])
    name='mount-G154L-open-c'
    run('restore-native',name,['--unit','mount','--name',name,'--snapshot',str(SOURCE/'local/cold/m-restart-final/standby.snap.z'),'--initial-only'])
    for backend in ('c','python'):
        name='unit-review-'+backend
        run('unit',name,['--name',name],backend)
    run('codec','codec-review')
    for backend in ('c','python'):
        run('','boundary-'+backend,backend=backend,script=REVIEW/'boundary_replay.py')
    save(LOCAL/'suite-result.json',dict(status='PASS',jobs=len(records),serial_compute_jobs=1,nice=os.getpriority(os.PRIO_PROCESS,0)))

if __name__=='__main__':main()
