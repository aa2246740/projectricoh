"""Invoke the orchestrator's standard-library RPC auditor without changes."""
from pathlib import Path
import argparse,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,file_sha,save
UNITS=('50mm','28mm','mount')

def run(group):
    if group=='all':paths=[OUT/'local/lock-cases'];output=OUT/'record-safety.json'
    elif group=='matrix':paths=[OUT/'local/native'/('matrix-'+u+'.json') for u in UNITS];output=OUT/'evidence/matrix-record-safety.json'
    elif group=='counterexamples':paths=[OUT/'local/cases'];output=OUT/'evidence/counterexample-record-safety.json'
    elif group=='h01':paths=sorted((OUT/'local/native/cases').glob('first-open-*.json'));output=OUT/'evidence/h01-record-safety.json'
    else:raise ValueError(group)
    assert paths and all(p.exists() for p in paths),(group,paths)
    dat=DAT if group=='all' else OUT/'local/p1-verified/artifact/GXRCE.DAT'
    tool=ROOT/'research/g122_keep_list/audit_records.py'
    argv=['/usr/bin/python3','-I','-B',str(tool),'--dat',str(dat),'--records',*[str(p) for p in paths],'--output',str(output)]
    result=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True)
    log=OUT/'local'/('rpc-review-'+group+'.log');log.write_text(result.stdout+result.stderr)
    assert result.returncode==0,(result.stdout,result.stderr)
    report=json.loads(output.read_text())
    assert report['dat_sha256']==file_sha(dat) and report['status']=='PASS'
    assert all(report['coverage'][u]['raw_streams_present'] for u in UNITS),report['coverage']
    evidence=dict(group=group,status='PASS',argv=argv,returncode=result.returncode,
        auditor_sha256=file_sha(tool),dat_sha256=file_sha(dat),output=str(output.relative_to(OUT)),coverage=report['coverage'])
    save('evidence/rpc-review-'+group+'-command.json',evidence)
    print('PASS authoritative RPC review',group,report['coverage'],flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('group',choices=('all','matrix','counterexamples','h01'));a=p.parse_args();run(a.group)
