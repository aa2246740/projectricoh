"""Count the actual reboot stop callback while preserving its return value."""
import argparse,functools,hashlib,importlib.util,json,os,pickle,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ACCEPT=HERE/'acceptance'
FAST=ROOT/'tools/gxr_emulator_fast/fix_r1'


def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);p.add_argument('--name',required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    output=ACCEPT/'local'/a.suite
    os.environ.update(GXR_FAST_OUTPUT=str(output),GXR_FAST_BACKEND='native',GXR_FAST_MODEL_FIXES='',GXR_EMULATOR_BATCH='1',GIT_OPTIONAL_LOCKS='0')
    sys.path[:0]=[str(ACCEPT),str(FAST)]
    spec=importlib.util.spec_from_file_location('reboot_callback_adapter',ACCEPT/'cumulative.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.prepare()
    import backend
    counts={};original=backend.Backend.add_breakpoint
    def add(cpu,address,callback):
        code=getattr(callback,'__code__',None)
        if code is not None and code.co_name=='stop_here' and Path(code.co_filename).resolve()==FAST/'input_run.py':
            name=callback.__qualname__
            @functools.wraps(callback)
            def counted(current,callback=callback):
                before=time.perf_counter()
                row=counts.setdefault(name,dict(calls=0,stops=0,body_seconds=0))
                row['calls']+=1
                try:
                    result=callback(current)
                    row['stops']+=bool(result)
                    return result
                finally:counts[name]['body_seconds']+=time.perf_counter()-before
            callback=counted
        return original(cpu,address,callback)
    backend.Backend.add_breakpoint=add
    runner=module.load(ACCEPT/'m2d_restart_run.py');runner.OUT=output
    module.call(a.name,lambda:module.old_main(runner,['--name',a.name,'--case','files-suite-r1']))
    old=json.loads((output/'reboot-suite-r1.json').read_text())
    new=json.loads((output/(a.name+'.json')).read_text())
    fields=('steps','segments','stop','flow','flow_counts','panel_events','observations','open_calls','panel_down',
            'instructions','mmio','timer_expirations','sd_counts','sd_events','events','medium_sha256')
    assert all(old.get(key)==new.get(key) for key in fields)
    states=[]
    for name in ('reboot-suite-r1',a.name):
        state=pickle.loads((output/(name+'-stop.pkl')).read_bytes())
        for kind,d in zip(state['device_types'],state['devices']):
            if kind=='SdHost' and d.get('medium_record'):d['medium_record']['path']='<private-medium>'
        from speed_snapshot import value_hash
        states.append(value_hash(state))
    assert states[0]==states[1]
    assert sum(row['calls'] for row in counts.values())==sum(row['stops'] for row in counts.values())==1,counts
    result=dict(status='PASS',callbacks=counts,whole_cpu_state=states,compared=list(fields),
                timing=json.loads((output/(a.name+'-timing.json')).read_text()),
                instrumentation='Wrap only input_run.stop_here; call the original once and return its exact result.',
                driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target=ACCEPT/'runs'/(a.name+'.json');assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',callbacks=counts)))


if __name__=='__main__':main()
