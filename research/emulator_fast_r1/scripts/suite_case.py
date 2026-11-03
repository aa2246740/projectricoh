"""One unchanged cumulative check plus a deterministic semantic receipt."""
import argparse,hashlib,json,os,pickle,runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,FAST
enable()

VOLATILE={'elapsed_sec','seconds','started','sources','source_hashes','current_sources','resume_sha256','git_status_protected'}

def normalize(value,output):
    if isinstance(value,dict):return {k:normalize(v,output) for k,v in value.items() if k not in VOLATILE}
    if isinstance(value,list):return [normalize(v,output) for v in value]
    if isinstance(value,str):return value.replace(str(output),'<private-output>')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();output=a.output.resolve();series='suite-r1'
    os.environ.update(GXR_FAST_SERIES=series,GXR_FAST_OUTPUT=str(output),GXR_EMULATOR_BATCH='1',GXR_FAST_BACKEND='native')
    arguments={
        'cold':['boot'],'card':['boot','--profile','card'],'regression':['regression'],'model':['model'],
        'files':['files','--case','files'],'full':['files','--case','full'],
        'read-error':['files','--case','read-error'],'write-error':['files','--case','write-error'],
        'no-card':['files','--case','no-card'],'restart':['restart'],'readback':['files','--case','readback'],
        'guard':['guard'],'m2b':['acceptance','--milestone','m2b'],'m2c':['acceptance','--milestone','m2c']}
    prefixes={
        'cold':['cold-'+series,'stable-'+series],'card':['cold-card-'+series],
        'regression':['existing-checks-'+series],'model':['storage-checks-r1'],
        'restart':['reboot-'+series],'guard':['final-input-guard'],'m2b':['m2b-'+series],'m2c':['m2c-'+series]}
    sys.argv=[str(HERE/'cumulative.py'),*arguments[a.case]]
    runpy.run_path(str(HERE/'cumulative.py'),run_name='__main__')
    sys.path.insert(0,str(FAST));from speed_snapshot import value_hash
    result={}
    for prefix in prefixes.get(a.case,[a.case+'-'+series]):
        path=output/(prefix+'.json');data=json.loads(path.read_text())
        result[prefix]=normalize(data,output)
        state=output/(prefix+'-stop.pkl')
        if state.exists():
            snapshot=pickle.loads(state.read_bytes())
            for name,device in zip(snapshot['device_types'],snapshot['devices']):
                if name=='SdHost' and device.get('medium_record'):device['medium_record']['path']='<private-medium>'
            result[prefix+'-whole-cpu-state']=value_hash(snapshot)
    semantic=output/(a.case+'-semantic.json')
    semantic.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':main()
