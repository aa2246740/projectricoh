"""Continuous execution versus portable whole-machine snapshot continuation."""
import argparse,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,TEMP
enable()
import bootstrap


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',required=True);args=parser.parse_args()
    result=dict(name=args.name,checks=[],load_before=os.getloadavg(),nice=os.getpriority(os.PRIO_PROCESS,0))
    started=time.perf_counter()
    from importlib import import_module
    bootstrap.load('fast','boot')
    S=import_module('snapshots')
    for kind,points in [('boot',[(35537208,'state5'),(202997601,'BOOT_RUN')]),('recovery',[(65975242,'recovery-confirm')])]:
        direct=bootstrap.construct('fast',kind,args.name+'-'+kind+'-direct');c=direct.machine.cpu
        try:
            for point,label in points:
                stop=c.run(point-c.steps);assert stop.reason=='max_steps'
                c.materialize_native()
                if label=='state5':assert int.from_bytes(c.read(0x205d9c00,4),'big')==5
                if label=='BOOT_RUN':assert c.get_reg('pc')==0x2070d490
                if label=='recovery-confirm':assert c.get_reg('pc')==0x2036c9e4
                path=HERE/'local'/(args.name+'-'+label+'.snap.z')
                saved=S.save(direct,path)
                n=1000000 if label=='state5' else 100000
                stop=c.run(n);assert stop.reason=='max_steps'
                expected=S.fingerprint(direct.machine,direct.controls)
                restored=bootstrap.construct('fast',kind,args.name+'-'+label+'-restored')
                try:
                    began=time.perf_counter();S.restore(restored,path)
                    load_seconds=time.perf_counter()-began
                    stop=restored.machine.cpu.run(n);assert stop.reason=='max_steps'
                    actual=S.fingerprint(restored.machine,restored.controls)
                    assert expected==actual,(label,expected,actual)
                    invalid=[]
                    original=restored.inputs.values['unit']
                    restored.inputs.values['unit']='different-unit'
                    try:S.identity(restored)
                    except ValueError:invalid.append('unit-input')
                    else:raise AssertionError('stale unit snapshot accepted')
                    restored.inputs.values['unit']=original
                    original=restored.inputs.values['model_corrections']
                    restored.inputs.values['model_corrections']=['changed-model-revision']
                    try:S.identity(restored)
                    except ValueError:invalid.append('model-version')
                    else:raise AssertionError('stale model snapshot accepted')
                    restored.inputs.values['model_corrections']=original
                    if kind=='boot':
                        changed=TEMP/(args.name+'-'+label+'-changed.dat')
                        data=bytearray(restored.inputs.values['dat'].read_bytes());data[-1]^=1;changed.write_bytes(data)
                        original=restored.inputs.values['dat'];restored.inputs.values['dat']=changed
                        try:S.identity(restored)
                        except ValueError:invalid.append('DAT-bytes')
                        else:raise AssertionError('stale DAT snapshot accepted')
                        restored.inputs.values['dat']=original
                    row=dict(point=label,steps=point,continued_steps=n,snapshot=saved,load_seconds=load_seconds,
                             equivalent=True,fingerprint=actual,invalidations=invalid)
                    result['checks'].append(row)
                    print(json.dumps(dict(point=label,equivalent=True,load_seconds=load_seconds)),flush=True)
                finally:restored.machine.close()
        finally:direct.machine.close()
    result.update(status='passed',seconds=time.perf_counter()-started,load_after=os.getloadavg())
    (HERE/'runs'/(args.name+'.json')).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
