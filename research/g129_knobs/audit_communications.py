"""Call the original record audit by path on complete target RPC streams."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,enable,check_inputs

def main():
    enable();check_inputs()
    dat=ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT'
    records=sorted((WORK/'local/release129/review_g126').glob('product-rpc-*.json'))
    assert records,'complete target RPC records are required'
    output=WORK/'local/communication-audit.json'
    script=ROOT/'research/g122_keep_list/audit_records.py'
    sys.argv=[str(script),'--dat',str(dat),'--records',*[str(path) for path in records],
              '--output',str(output),'--base-dir',str(ROOT)]
    stream=io.StringIO();status=0
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:runpy.run_path(str(script),run_name='__main__')
        except SystemExit as error:status=error.code or 0
        except BaseException as error:
            status=1
            (WORK/'communication-diagnostic.json').write_text(json.dumps({'type':type(error).__name__,'message':str(error)},indent=2)+'\n')
    total=sum(len(json.loads(path.read_text())['records']) for path in records)
    audit=json.loads(output.read_text()) if output.exists() else {}
    if audit.get('status') not in (None,'PASS'):status=status or 1
    result={'name':'audit_records.py','returncode':status,'dat_sha256':hashlib.sha256(dat.read_bytes()).hexdigest(),
            'records':total,'files':len(records),'captured_lines':len(stream.getvalue().splitlines()),
            'status':'PASS' if status==0 else 'INCOMPLETE','scope':[path.name for path in records],
            'unit_results':audit.get('units',{}),'failures':len(audit.get('failures',[])),
            'raw_status':audit.get('status'),'raw_report':str(output.relative_to(ROOT))}
    (WORK/'communications.json').write_text(json.dumps(result,indent=2)+'\n')
    check_inputs();print(json.dumps(result));raise SystemExit(status)

if __name__=='__main__':main()
