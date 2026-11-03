"""Optional-panel, hidden LOCK-register and cache-key snapshot checks."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE
enable();import bootstrap


def make(name):
    context=bootstrap.construct('fast','main',name)
    context.machine.cpu.step_hook=context.machine.cpu.step_hook.previous
    del context.machine.panel
    import snapshots as S
    values=dict(context.inputs.values,configuration='no-panel-lock-fixture')
    context.inputs=S.Inputs(**values)
    del context.identity_bound
    context.identity_bound=S.identity(context)
    return context


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',default='snapshot-edges-final1');args=p.parse_args()
    source=make(args.name+'-source')
    import snapshots as S
    target=None
    try:
        c=source.machine.cpu;assert c.run(1000000).reason=='max_steps';c.materialize_native()
        registers=bytearray(S.arch_state(c));registers[-1]=1;S.arch_state(c,bytes(registers))
        cache=S.Cache(HERE/'local'/(args.name+'-cache'))
        saved=cache.store(source,'lock')
        assert cache.available(source,'lock')
        expected=S.fingerprint(source.machine,source.controls)
        target=make(args.name+'-target')
        assert cache.path(source,'lock')==cache.path(target,'lock')
        cache.restore(target,'lock')
        assert S.arch_state(target.machine.cpu)[-1]==1
        assert S.fingerprint(target.machine,target.controls)==expected
        try:cache.restore(target,'lock')
        except ValueError as error:assert 'freshly constructed' in str(error)
        else:raise AssertionError('restore into an advanced instance was accepted')
        record=dict(status='passed',no_panel=True,hidden_lock_preserved=True,hash_key_reused=True,
                    used_instance_rejected=True,snapshot=saved,fingerprint=expected)
        (HERE/'runs'/(args.name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(dict(status='passed',checks=4)))
    finally:
        if target:target.machine.close()
        source.machine.close()


if __name__=='__main__':main()
