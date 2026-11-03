"""Bind changed source functions to linked code and explicit review obligations."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from static_audit import symbols
from codegen_safety import INLINE

def main():
    read=lambda name:json.loads((OUT/name).read_text())
    static=read('evidence/static-audit.json');tables=read('evidence/compiled-tables.json');rebuilt=read('evidence/rebuild-exact.json')
    assert static['dat_sha256']==tables['dat_sha256']==rebuilt['DAT_sha256']==PIN
    assert rebuilt['status']=='PASS' and tables['unclassified_executable_anomalies']==0
    available=symbols(ELF);changed=[]
    for row in static['changed_functions']:
        name=row['function'];carriers=INLINE.get(name,[name]);spans=[]
        for carrier in carriers:
            found=[dict(symbol=k,**v) for k,v in available.items() if re.sub(r'\.(?:constprop|isra|lto_priv)\.\d+','',k)==carrier]
            assert found,carrier
            spans+=found
        if not carriers:assert name=='eng_project_compute' and name not in available
        changed.append(dict(**row,compiled_spans=spans,eliminated=not carriers,
            address_length='Validated GXUI, 552-byte entry, 8x9 text slots and leased 8-row publication; see native/compiled obligations.',
            file_operations='No mutation capability or new storage caller; all three direct service boundaries executed.',
            native_UI='Private state or the guarded 8-row publisher. The last ownership-check-to-draw window is P2-01, not atomic.',
            loops_memory='Fixed bounds: 8 rows, 11 levels, 24 configs, 32 users, 16 navigation rounds; 4+2 recovery attempts.'))
    stack=[]
    for path in (OUT/'local/rebuild/product-r13/m32r-lto').glob('engine.elf.ltrans*.su'):
        for line in path.read_text().splitlines():
            p=line.split('\t')
            if len(p)==3:stack.append(dict(function=p[0],bytes=int(p[1]),kind=p[2]))
    assert stack and all(x['kind']=='static' for x in stack)
    obligations=[]
    names=['evidence/input-identity.json','evidence/critical-12-exact.json','evidence/reentry-verified-50mm.json',
           'evidence/compiled-tables.json','evidence/rebuild-exact.json','evidence/row-transitions-50mm-irq.json',
           'evidence/project-boundary-50mm.json','evidence/users-50mm.json','evidence/memory-budget.json']
    names += ['evidence/other-users-'+u+'.json' for u in ('50mm','28mm','mount')]
    for name in names:
        path=OUT/name
        value=json.loads(path.read_text()) if path.exists() else {}
        good=isinstance(value,list) and all(x.get('byte_exact') for x in value)
        if isinstance(value,dict):good=str(value.get('status','')).startswith('PASS')
        obligations.append(dict(file=name,exists=path.exists(),passed=good,sha256=file_sha(path) if path.exists() else None))
    for unit in ('50mm','28mm','mount'):
        path=OUT/'local/safety'/(unit+'-storage.json');value=json.loads(path.read_text())
        assert value['status']=='PASS' and not any(value['file_mutations'].values())
        obligations.append(dict(file=str(path.relative_to(OUT)),passed=True,sha256=file_sha(path)))
    cold=OUT/'evidence/cold-publication-verified.json'
    publication_failure=cold.exists() and json.loads(cold.read_text()).get('status')=='P1_REPRODUCED'
    result=dict(status='FAIL_NATIVE_PUBLICATION' if publication_failure else 'PASS_SCOPED_WITH_P2' if all(x['passed'] for x in obligations) else 'PENDING_REPLAY',
        dat_sha256=PIN,changed_functions=len(changed),per_function=changed,obligations=obligations,
        maximum_static_frame=max(x['bytes'] for x in stack),all_frames_static=True,
        compiled_jump_tables=tables['switch_words'],unclassified_executable_anomalies=0,
        actual_rebuild=True,categories=['地址与长度','文件操作','原生界面写入','循环与内存'],
        native_UI_status='FAIL_P1_FIRST_PUBLICATION' if publication_failure else 'PASS_SCOPED_WITH_P2',
        first_publication_counterexample=str(cold.relative_to(ROOT)) if publication_failure else None,
        limitation='The native drawing window is observed and remains P2-01 in both gen121 and gen124. No RTOS high-water or physical camera proof.')
    save('evidence/compiled-review.json',result)
    print(result['status'],len(changed),'changed functions; maximum rebuilt frame',result['maximum_static_frame'])

if __name__=='__main__':main()
