"""Inspect fitted curve/matrix/colour data as well as complete entry blobs."""
import json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *

def main():
    fitted=json.loads((ROOT/'artifacts/downloads/g154-looks-r1/local/effects.json').read_text())[10:]
    supplied={x['name']:bytes.fromhex(x['entry_hex']) for x in fitted}
    findings=[];checked=[]
    for relative in ['research/vlog_alchemy_eval/all_fit_parameters.json','research/vlog_alchemy_eval/lumix_fit_parameters.json','research/vlog_alchemy_eval/look_fits.json']:
        p=ROOT/relative
        if not p.exists():checked.append(dict(path=relative,exists=False));continue
        text=p.read_text();obj=json.loads(text);matches=[]
        checked.append(dict(path=relative,exists=True,sha256=sha(p.read_bytes())))
        if 'parameters' in obj:
            for record in obj['parameters']:
                if record['name'] not in supplied or not any(k in record for k in ('curve_hex','matrix_hex','colour_hex')):continue
                raw=supplied[record['name']]
                pieces={'curve_hex':raw[82:115],'matrix_hex':raw[216:272],'colour_hex':raw[115:211]}
                equal=all(bytes.fromhex(record[k])==v for k,v in pieces.items() if k in record)
                assert equal
                matches.append(dict(name=record['name'],exact_fitted_rows=True,fields=[k for k in pieces if k in record]))
        else:
            aliases={'千禧回声 A':'QianXi A','千禧回声 B':'QianXi B','ARRI Classic709':'ARRI 709'}
            for record in obj.get('fits',[]):
                name=aliases.get(record['name'],record['name'])
                if name not in supplied:continue
                fields=record.get('fit',{});present=[k for k in ('curve_values','theta') if k in fields]
                if not present:continue
                if 'curve_values' in fields:assert bytes(fields['curve_values'])==supplied[name][82:115]
                matches.append(dict(name=name,exact_quantized_curve='curve_values' in fields,fields=['fit.'+k for k in present]))
        if not matches:continue
        check=subprocess.run(['git','check-ignore','-v','--',relative],cwd=ROOT,capture_output=True,text=True,timeout=120,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        assert check.returncode in (0,1)
        tracked=subprocess.run(['git','ls-files','--',relative],cwd=ROOT,capture_output=True,text=True,check=True,timeout=120,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        others=subprocess.run(['git','ls-files','--others','--exclude-standard','--',relative],cwd=ROOT,capture_output=True,text=True,check=True,timeout=120,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        findings.append(dict(path=relative,sha256=sha(p.read_bytes()),matches=matches,ignored=check.returncode==0,tracked=bool(tracked.stdout.strip()),
                             untracked_public_path=bool(others.stdout.strip()),first_data_line=next(i for i,s in enumerate(text.splitlines(),1) if any(k in s for k in ('curve_hex','matrix_hex','colour_hex','curve_values','"theta"'))),
                             relation='Upstream evaluation output referenced by the implementation; no claim about prior publication'))
    # Public Studio paths are scanned separately from ignored local stores.
    studio_hits=[]
    for p in (ROOT/'studio').rglob('*'):
        if not p.is_file() or p.is_symlink() or any(x in p.parts for x in ('.venv','node_modules','__pycache__','.git','local','dist')):continue
        if p.stat().st_size>16*1024*1024:continue
        content=p.read_bytes().lower()
        for name,raw in supplied.items():
            if raw[115:211].hex().encode() in content and raw[216:272].hex().encode() in content:
                studio_hits.append(dict(path=str(p.relative_to(ROOT)),name=name))
    result=dict(status='FAIL' if findings or studio_hits else 'PASS',criterion='Fitted third-party LUT data must only reside under artifacts/downloads or package local directories',
                findings=findings,checked_paths=checked,studio_fitted_row_hits=studio_hits,
                narrower_package_result='PASS: new package fitted data is under package local, and build input under artifacts/downloads',
                publication_scope='Read-only Git index/ignore checks only; no remote or publication history inspection')
    save('evidence/license-check.json',result)
    print(json.dumps(dict(status=result['status'],public_fitted_files=[x['path'] for x in findings],studio_hits=studio_hits)))
    raise SystemExit(1 if findings or studio_hits else 0)

if __name__=='__main__':main()
