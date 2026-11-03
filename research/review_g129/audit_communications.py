"""Audit the three complete final-DAT streams with the required auditor."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import sys

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent

def main():
    names={'50mm':'focus-product-50mm','28mm':'focus-product-28mm-r17','mount':'focus-product-mount'}
    records=[];counts={};pin='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
    for unit,job in names.items():
        path=WORK/'local'/job/'review_g126'/f'product-rpc-{unit}.json'
        value=json.loads(path.read_text());assert value['unit']==unit and value['dat_sha256']==pin
        product=json.loads((path.parent/f'product-{unit}.json').read_text());assert product['status']=='PASS'
        records.append(path);counts[unit]=len(value['records'])
    output=WORK/'local/communication-audit.json';script=ROOT/'research/g122_keep_list/audit_records.py'
    sys.argv=[str(script),'--dat',str(ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT'),
              '--records',*[str(path) for path in records],'--output',str(output),'--base-dir',str(ROOT)]
    stream=io.StringIO();status=0;error_name=None
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:runpy.run_path(str(script),run_name='__main__')
        except SystemExit as error:status=error.code or 0
        except BaseException as error:status=1;error_name=type(error).__name__
    raw=json.loads(output.read_text()) if output.exists() else {}
    assert raw.get('dat_sha256')==pin
    result={'name':'audit_records.py','returncode':status,'status':raw.get('status','INCOMPLETE'),
            'dat_sha256':pin,'records_per_unit':counts,'records':sum(counts.values()),
            'units':raw.get('units',{}),'failures':len(raw.get('failures',[])),
            'captured_lines':len(stream.getvalue().splitlines()),'error_type':error_name,
            'inputs':[{'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in records]}
    (WORK/'communications.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))
    assert status==0 and raw.get('status')=='PASS'

if __name__=='__main__':main()
