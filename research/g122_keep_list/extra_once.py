"""Retain completed extra model commands for the same DAT and source files."""
from pathlib import Path
import atexit
import hashlib
import json
import os
import sys
from common import OUT,DAT,sha,file_sha,command_lock

def record():
    script=Path(sys.argv[0]).resolve()
    parts=[script.name,*sys.argv[1:]]
    identity=sha(json.dumps(parts).encode())[:24]
    held=command_lock('extra-'+identity)
    dependencies=sorted({script.name,'extra_once.py','common.py','runtime_guard.py','run_native.py',
        'native_ux.py','native_cases.py','native_exits.py','ui_trace_scope.py','key_probe.py','native_sequence.py'})
    def source_key():
        digest=hashlib.sha256()
        for name in dependencies:digest.update(name.encode());digest.update((OUT/name).read_bytes())
        return digest.hexdigest()
    source=source_key();pin=file_sha(DAT)
    folder=OUT/'extra-records';folder.mkdir(exist_ok=True);path=folder/(identity+'.json')
    if path.exists():
        previous=json.loads(path.read_text())
        if previous.get('exit_status')==0 and previous.get('dat_sha256')==pin and previous.get('source_sha256')==source:
            print('REUSE completed model command, fixed DAT and sources',parts,flush=True)
            raise SystemExit(0)
    result={'status':0};original=sys.excepthook
    def failed(kind,value,trace):result['status']=1;return original(kind,value,trace)
    sys.excepthook=failed
    def finished():
        good=source_key()==source and file_sha(DAT)==pin
        if script.name=='field_cases.py':
            unit=parts[1]
            for case in parts[parts.index('--only')+1:]:
                p=OUT/'field'/('122-'+unit+'-'+case+'.json')
                if not p.exists():good=False;continue
                status=json.loads(p.read_text()).get('status')
                if status not in ('PASS','INCOMPLETE_DEVICE_REGISTER','INCOMPLETE_CAPTURE_COMPLETION'):good=False
        value=dict(command=parts,dat_sha256=pin,source_sha256=source,
                   exit_status=result['status'] if good else 'INCOMPLETE_EXECUTION',process=os.getpid())
        body=json.dumps(value,indent=2)+'\n'
        if path.exists() and path.read_text()!=body:
            history=OUT/'history/extra-records';history.mkdir(parents=True,exist_ok=True)
            old=path.read_bytes();(history/(identity+'-'+sha(old)[:16]+'.json')).write_bytes(old)
        path.write_text(body);held.close()
    atexit.register(finished)
