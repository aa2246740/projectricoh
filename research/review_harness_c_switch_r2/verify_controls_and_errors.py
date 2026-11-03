"""Check worker errors and compare the complete formal error products."""
from pathlib import Path
import hashlib,json,sys

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from audit_evidence import read,compare,metadata_normalize,sha

def main():
    controls=read(OUT/'entry-controls/summary.json')
    rows=[]
    for record in controls['records']:
        row=dict(record);error=row['expected_error']
        if error:
            files=[OUT/'entry-controls'/(row['case']+'.log'),Path(row['run'])/'local/logs/entry-control.log']
            text='\n'.join(p.read_text() for p in files if p.is_file())
            row['error_found_in_saved_logs']=error in text
            row['checked_logs']=[str(p) for p in files if p.is_file()]
            row['passed']=row['returncode']!=0 and error in text and row['product_sha256'] is None
        rows.append(row)
    controls.update(records=rows,passed=all(r['passed'] for r in rows) and controls['acceptance_identical'],
                    correction='The first checker inspected only scheduler output. API errors are in the recorded worker log; the original result and logs are retained.')
    (OUT/'entry-controls/verified-summary.json').write_text(json.dumps(controls,indent=2)+'\n')
    errors=[]
    for name in ('event-entry','event-entry-variant'):
        summary=OUT/name/'summary.json'
        if not summary.is_file():continue
        value=read(summary);raw={};normalized={};paths={}
        for record in value['records']:
            s=record['side'];run_name=('event-' if name=='event-entry' else 'event-variant-')+s
            run=OUT/'entry/local/runs'/run_name
            matches=list(run.rglob('error-case-.json'));assert len(matches)==1
            path=matches[0];paths[s]=str(path);raw[s]=read(path)
            normalized[s]=metadata_normalize(raw[s],[(str(run),'<run>')])
        n,d=compare(normalized['python'],normalized['c'])
        # A second view maps the two base-backend source paths to one label,
        # while preserving every frame, function and line.
        logical={s:metadata_normalize(v,[('tools/native_harness/python_backend.py','<base-backend>'),('tools/speedlab/harness_release_r4/python_backend.py','<base-backend>')]) for s,v in normalized.items()}
        _,logical_diff=compare(logical['python'],logical['c'])
        errors.append({'case':name,'entry_returncodes':{r['side']:r['entry_returncode'] for r in value['records']},
                       'error_type_and_message_equal':all(raw['python'][k]==raw['c'][k] for k in ('error','message')),
                       'complete_error_product_equal':not d,'differences':d,'logical_backend_paths_still_differ':bool(logical_diff),'logical_differences':logical_diff,
                       'frame_counts':{s:len(v['location']) for s,v in raw.items()},'error_files':paths,'raw_sha256':{s:sha(Path(p)) for s,p in paths.items()}})
    proof={'controls_passed':controls['passed'],'errors':errors}
    (OUT/'evidence/error-product-comparison.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,indent=2))
    return 0 if controls['passed'] and all(r['error_type_and_message_equal'] and not r['complete_error_product_equal'] and r['logical_backend_paths_still_differ'] for r in errors) else 1

if __name__=='__main__':raise SystemExit(main())
