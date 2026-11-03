"""Bind the complete retained matrix to final input tracing and the frozen Python oracle."""
import json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit
def main():
    enable();jobs=json.loads((HERE/'queue.json').read_text())['jobs'];results=[]
    for job in jobs:
        env=dict(os.environ,GXR_SPEEDLAB_STRICT_JOB=job['name'],GXR_SPEEDLAB_STRICT_LABEL='c-strict-release')
        command=['/usr/bin/python3','-I','-B',str(HERE/'strict_group.py')]
        subprocess.run(command,cwd=ROOT,env=env,check=True,timeout=10800)
        proof=json.loads((HERE/'local/comparisons-strict'/(job['name']+'.json')).read_text());assert proof['equal'];results.append(proof)
        emit(HERE/'local/comparisons-strict/progress.json',{'groups_completed':len(results),'job':job['name']})
    keys=('job','equal','packets','wall_seconds','cpu_seconds','speedup_wall','speedup_cpu')
    emit(HERE/'local/comparisons-strict/summary.json',{'passed':True,'jobs':len(results),'json_files':sum(r['json_files'] for r in results),
        'compared_values':sum(r['compared_values'] for r in results),'results':[{k:r[k] for k in keys} for r in results]})
    print(json.dumps({'final_strict_groups':len(results)-1,'passed':True}),flush=True)
if __name__=='__main__':main()
