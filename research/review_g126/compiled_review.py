"""Combine linked-code checks with the independently observed native failure."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

def main():
    read=lambda name:json.loads((OUT/'evidence'/name).read_text())
    static=read('static-audit.json');code=read('codegen-safety.json');tables=read('compiled-tables.json')
    rebuild=read('rebuild-126.json');findings=read('findings-verified.json')
    assert static['dat_sha256']==code['dat_sha256']==tables['dat_sha256']==rebuild['dat_sha256']==PIN
    assert tables['unclassified_executable_anomalies']==0 and code['PIC_translation_verified']
    assert rebuild['status']=='PASS' and all(rebuild['equal'].values())
    assert findings['status']=='P1_NEW_LATE_SETTINGS_WRITES_CONFIRMED'
    safety=[]
    for unit in ('50mm','28mm','mount'):
        path=OUT/'local/safety'/(unit+'-storage.json')
        r=json.loads(path.read_text())
        assert r['status'].startswith('PASS') and r.get('dat_sha256',r.get('artifact',{}).get('dat_sha256'))==PIN
        assert not any(r['file_mutations'].values())
        safety.append(dict(unit=unit,file=str(path.relative_to(ROOT)),sha256=file_sha(path)))
    rows=[]
    for row in code['changed_C_functions']:
        pure_generation=row['function'] in ('uv_validate','eng_data_accept','gxr2_tweak_layout')
        rows.append(dict(function=row['function'],source=row['file'],line=row['line'],compiled=row['compiled'],
            address_length='PASS',file_operations='PASS',loops_memory='PASS',
            native_UI='PASS_GENERATION_LITERAL_ONLY' if pure_generation else 'NOT_CLOSED_P1_NEW_SETTINGS_RESTORE',
            native_evidence='evidence/findings-verified.json'))
    save('evidence/compiled-review.json',dict(status='FAIL_NATIVE_OWNERSHIP_P1',dat_sha256=PIN,
        per_function=rows,storage_service_evidence=safety,maximum_static_frame=code['maximum_static_frame'],
        engine_bytes=code['engine_bytes'],bss_bytes=code['bss_bytes'],file_bytes=code['file_bytes'],
        scope='Static automatic category checks do not override the observed final-DAT native ordering failure. No RTOS stack or physical camera acceptance.'))
    print('FAIL_NATIVE_OWNERSHIP_P1;',len(rows),'changed C functions reviewed')

if __name__=='__main__':main()
