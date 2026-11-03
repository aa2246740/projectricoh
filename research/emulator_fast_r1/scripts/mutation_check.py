"""Compile one device mutation and prove the complete-state check rejects it."""
import argparse,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,FAST,TEMP
enable()
import bootstrap


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',default='mutation-check');args=p.parse_args()
    source=TEMP/(args.name+'-source');assert not source.exists();source.mkdir()
    for path in FAST.iterdir():
        if path.suffix in ('.c','.h','.inc'):shutil.copyfile(path,source/path.name)
    path=source/'machine_scheduler.inc';text=path.read_text();needle='++m->clock.expirations;'
    assert text.count(needle)==1;text=text.replace(needle,'m->clock.expirations+=2;');path.write_text(text)
    (HERE/'runs'/(args.name+'-machine-scheduler.inc')).write_text(text)
    spec=importlib.util.spec_from_file_location('native_build',FAST/'build.py')
    build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
    target=FAST/'build'/(args.name+'.dylib')
    command=build.library_command(source,target)
    result=subprocess.run(command,capture_output=True,text=True,timeout=120)
    (HERE/'runs'/(args.name+'-build.log')).write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr
    control=bootstrap.construct('fast','main',args.name+'-control')
    from snapshots import fingerprint,sha
    import backend
    original=backend.Backend.__init__
    def mutated(cpu,**kwargs):return original(cpu,**{**kwargs,'library':target})
    backend.Backend.__init__=mutated
    candidate=bootstrap.construct('fast','main',args.name+'-candidate')
    try:
        for context in (control,candidate):
            stop=context.machine.cpu.run(50000000);assert stop.reason=='max_steps'
        a=fingerprint(control.machine,control.controls);b=fingerprint(candidate.machine,candidate.controls)
        assert a['registers']==b['registers'] and a['memory']==b['memory']
        assert a['devices']!=b['devices'] and a['all']!=b['all']
        counters=[context.machine.devices['timer'].expirations for context in (control,candidate)]
        assert counters[1]==2*counters[0] and counters[0]>0
        record=dict(status='detected',mutation='timer expiration observation increments by two instead of one',
                    control=a,mutant=b,expirations=counters,mutant_library_sha256=sha(target),
                    changed_source_sha256=sha(path),load=os.getloadavg(),
                    native=[context.machine.cpu._native_driver.stats() for context in (control,candidate)])
        assert all(x['instructions']==50000000 and x['python_bus_calls']==0 and not x['hle_callbacks'] for x in record['native'])
        (HERE/'runs'/(args.name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(dict(status=record['status'],expirations=counters)))
    finally:
        candidate.machine.close();control.machine.close()


if __name__=='__main__':main()
