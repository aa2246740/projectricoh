"""Re-run the task's bounded final-artifact verification in the foreground."""
from pathlib import Path
import argparse
import json
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import probe_common as c


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild-compare',action='store_true')
    args=parser.parse_args();c.guard()
    out=c.RESEARCH/'evidence/verification.json'
    report=dict(status='RUNNING',completed=[],scope='CPU/read-only subset; hardware mutation probes omitted')
    c.save(out,report)
    try:
        if args.rebuild_compare:
            before=(c.LOCAL/'package/GXRCE.DAT').read_bytes()
            print('RUN rebuild comparison',flush=True)
            result=c.run(['/usr/bin/python3','-I','-B',c.HERE/'build_probe.py'],'final-rebuild',timeout=180)
            assert before==(c.LOCAL/'package/GXRCE.DAT').read_bytes(),'nonreproducible DAT'
            c.save(c.RESEARCH/'evidence/rebuild-reproducible.json',dict(status='PASS',dat_sha256=c.sha(c.LOCAL/'package/GXRCE.DAT'),byte_identical=True))
            print(result.stdout,flush=True)
        report['dat_sha256']=c.sha(c.LOCAL/'package/GXRCE.DAT')
        for script,label,timeout in (
            ('check_native.py','native-functional-final',1800),('check_contracts.py','native-contracts-final',900),
            ('check_p1.py','native-p1-final',1200),('check_faults.py','native-faults-final',1800),
            ('check_binding.py','native-binding-final',600),
            ('check_analysis.py','analysis-final',120),('audit_probe.py','artifact-audit-final',180)):
            print('RUN',label,flush=True)
            result=c.run(['/usr/bin/python3','-I','-B',c.HERE/script],label,timeout=timeout)
            print(result.stdout,flush=True)
            report['completed'].append(label);c.save(out,report)
        for name in ('native-functional','native-contracts','p1-native','native-faults','native-binding','formula-checks','final-artifact-audit'):
            record=json.loads((c.RESEARCH/('evidence/'+name+'.json')).read_text())
            assert record['status']=='PASS' and record['dat_sha256']==report['dat_sha256'],name
        report['status']='PASS';c.save(out,report);print('PASS all final-artifact checks',flush=True)
    except BaseException:
        report['status']='FAIL';report['error']=traceback.format_exc();c.save(out,report)
        raise


if __name__=='__main__':main()
