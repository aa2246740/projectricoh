#!/usr/bin/python3 -I -B
"""Rerun prior cases against semantic checks and the public CLI."""
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fixtures import gate,encode,reviewed_cases,load_module
from public_runner import call
from run_mutations import rebound,assert_incomplete

BASE=HERE.parent
ROOT=BASE.parents[1]
SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-r5')


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and SCRATCH.is_dir()
    source=BASE/'r4/record_check.py'
    text=source.read_text()
    replacements=[('    if write:\n        source=profile_data()',
                   '    if False:\n        source=profile_data()'),
                  ("HERE/'record-sensitivity.json'",repr(str(HERE/'legacy-sensitivity.json'))),
                  ("HERE/'record-results.json'",repr(str(HERE/'legacy-results.json')))]
    # Preserve pathlib receivers at the two output sites.
    replacements[1]=(replacements[1][0],'Path('+replacements[1][1]+')')
    replacements[2]=(replacements[2][0],'Path('+replacements[2][1]+')')
    for old,new in replacements:
        assert old in text,old
        text=text.replace(old,new)
    module=types.ModuleType('r5_legacy_checks');module.__file__=str(source)
    exec(compile(text,str(source),'exec'),module.__dict__)
    (HERE/'history-adapter.json').write_text(json.dumps(dict(source=str(source.relative_to(ROOT)),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),replacements=replacements,
        classifier='current public semantic entry with a fixture-only updated record digest; raw observations retained'),indent=2)+'\n')
    raw_capture=gate.read_json(HERE/'positive/00-capture.json')
    capture=gate.load_capture(raw_capture,hashlib.sha256(encode(raw_capture)).hexdigest())
    default_raw=gate.read_json(HERE/'positive/00-profile.json')
    default=gate.load_profile(default_raw,hashlib.sha256(encode(default_raw)).hexdigest())
    rows=[];counts={};negative_calls=0;positive_calls=0
    profile_path=SCRATCH/'history-profile.json';capture_path=SCRATCH/'history-capture.json'
    trace=gzip.open(HERE/'history-inputs.jsonl.gz','wb',compresslevel=1)

    def check(doc,profile=default,name='legacy',fresh=False):
        nonlocal negative_calls,positive_calls
        content=encode(doc);current=rebound(capture,hashlib.sha256(content).hexdigest())
        actual=gate.classify(doc,profile,current)
        reference=profile if profile is not None else default
        profile_path.write_bytes(reference.serialized);capture_path.write_bytes(current.serialized)
        argv=['-','--profile',str(profile_path),'--profile-sha256',reference.digest if profile is not None else '0'*64,
              '--capture',str(capture_path),'--capture-sha256',current.digest]
        # Warm the same verified immutable input cache inherited by the child.
        gate.profile_text(reference.serialized.decode(),reference.digest)
        gate.capture_text(current.serialized.decode(),current.digest)
        if fresh:
            ran=subprocess.run(['/usr/bin/python3','-I','-B',str(BASE/'r3/diag_gate.py')]+argv,
                               input=content.decode(),capture_output=True,text=True,timeout=60)
            code,out=ran.returncode,dict(stdout=ran.stdout,stderr=ran.stderr)
        else:code,out=call(argv,content.decode())
        expected=0 if actual['records_complete'] else 2
        assert code==expected and out['stderr']=='',(name,code,out)
        cli=json.loads(out['stdout'])
        assert cli['records_complete']==actual['records_complete'],(name,actual,cli)
        if expected:
            assert_incomplete(actual);assert_incomplete(cli)
            assert actual['reasons']['record'][0]['code']!='frozen_record_changed'
            negative_calls+=1
        else:positive_calls+=1
        row=dict(name=name,input_sha256=hashlib.sha256(content).hexdigest(),complete=actual['records_complete'],
                 cli_exit=code,fresh_interpreter=fresh,issue=None if not expected else actual['reasons']['record'][0])
        rows.append(row)
        trace.write(json.dumps(dict(row=row,input=doc),separators=(',',':')).encode()+b'\n')
        if len(rows)%1000==0:print(json.dumps(dict(history_progress=len(rows),negative=negative_calls,positive=positive_calls)),flush=True)
        return actual

    module.classify=check
    try:
        legacy=module.run_checks(write=True)
        assert legacy['record_cases_rejected']==8509
        # One old reference-hash case fails before classify and is therefore
        # checked through the JSON boundary explicitly below.
        for row,doc in reviewed_cases():
            if row['expected_complete']:continue
            fresh=row['name'] in ('JPEG_L_valid_2','RAW_L_valid_2','RAW_169_valid_2')
            actual=check(doc,name=row['name'],fresh=fresh)
            assert actual['records_complete'] is False,row['name']
            counts[row['group']]=counts.get(row['group'],0)+1
    finally:trace.close()
    assert sum(counts.values())==381 and counts['success_count_mismatch']==110
    report=dict(classification='host_record_contract_only',legacy_negative_cases=8509,
                review_negative_cases=381,review_count_cases=110,prior_bad_count_cases=30,
                counts=counts,public_positive_calls=positive_calls,public_negative_calls=negative_calls,
                fresh_public_count_examples=sum(row['fresh_interpreter'] for row in rows),cases=rows,
                checker_sha256=hashlib.sha256((BASE/'r3/diag_gate.py').read_bytes()).hexdigest(),
                contract_sha256=hashlib.sha256((HERE/'derived_contract.py').read_bytes()).hexdigest(),
                public_runner_sha256=hashlib.sha256((HERE/'public_runner.py').read_bytes()).hexdigest(),
                runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                trace_sha256=hashlib.sha256((HERE/'history-inputs.jsonl.gz').read_bytes()).hexdigest())
    (HERE/'history-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
