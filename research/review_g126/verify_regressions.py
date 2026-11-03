"""Verify the completed replay matrix, exact DAT pins and raw result records."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

GROUPS=(
 ('cold','cold-reentry-126-{u}.json',4,0),
 ('cold-H07','cold-exit-{u}.json',2,0),
 ('cold-exit-matrix','cold-exit-matrix-{u}-r2.json',12,0),
 ('gen122','suite-126-{u}.json',9,0),
 ('safety','safety-{u}.json',8,0),
 ('locked','locked-{u}.json',8,0),
 ('nested','lock-nested-126-{u}-record_failure_return-after_update_restore-before_redraw-row_draw.json',40,10),
 ('switches','lock-cutpoints-{u}-irq-enabled.json',16,8),
 ('lock-exits','lock-exits-126-{u}.json',24,0),
 ('transitions','transitions-{u}.json',42,0),
 ('withdrawal','row-transitions-{u}-irq.json',21,0),
 ('values','values-{u}.json',7,0),
 ('view-reentry','view-reentry-{u}.json',70,0),
 ('six-keys','reentry-all-keys-{u}.json',210,0),
 ('settings','settings-cases-{u}.json',36,0),
 ('users','users-{u}.json',None,0),
 ('other-users','other-users-{u}.json',None,0),
 ('project','project-boundary-{u}.json',None,0),
 ('labels','labels-{u}.json',None,0),
)

def main():
    fixture=json.loads((OUT/'evidence/user-tool.json').read_text())['fixture_sha256']
    matrix=[];missing=[];bad=[]
    for group,template,count,removed in GROUPS:
        for unit in ('50mm','28mm','mount'):
            path=OUT/'evidence'/template.format(u=unit)
            row=dict(group=group,unit=unit,file=str(path.relative_to(ROOT)),expected_cases=count,expected_removed=removed)
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)));row['status']='INCOMPLETE';matrix.append(row);continue
            r=json.loads(path.read_text());cases=r.get('cases',r.get('results',[]))
            pin=r.get('dat_sha256')
            expected=fixture if group in ('users','other-users') else PIN
            if group!='cold':assert pin==expected,(group,unit,pin)
            if count is not None:
                assert len(cases)==count and all(x['wait_status']==0 for x in cases),(group,unit)
                actual_removed=sum(x.get('status')=='REMOVED_UPDATE_PATH' for x in cases)
                assert actual_removed==removed,(group,unit,actual_removed)
                row.update(executed_cases=count-removed,removed_cases=removed)
            assert group=='cold' or r['status'].startswith('PASS'),(group,unit,r.get('status'))
            if group=='project':assert r['level_cases']==1693 and r['window_cases']==8686
            if group=='other-users':assert len(r['seven_other_base_users'])==7 and r['readonly_metadata_unchanged']
            if group=='users':assert len(r['entry_names'])==25 and r['readonly_metadata_unchanged']
            row.update(status='PASS',source_sha256=file_sha(path),dat_sha256=expected)
            matrix.append(row)
    folders=('cold-reentry','cold-exit','cold-exit-matrix-r2','cases','safety','lock-cases','nested',
             'cutpoints-irq-enabled','lock-exits','ui-cases','row-transitions-irq','view-reentry',
             'reentry-all-keys','settings-cases')
    raw=[]
    for folder in folders:
        for path in sorted((OUT/'local'/folder).glob('*.json')):
            r=json.loads(path.read_text())
            assert r.get('dat_sha256',r.get('artifact',{}).get('dat_sha256'))==PIN,path
            assert r.get('status','').startswith('PASS'),(path,r.get('status'))
            ui=r.get('native_UI')
            if ui:assert not ui['host_ui_writes'] and not ui['getter_callback_present'],path
            counters=r.get('file_mutations')
            if counters:assert not any(counters.values()),path
            raw.append(dict(file=str(path.relative_to(ROOT)),sha256=file_sha(path),status=r['status']))
    for unit in ('50mm','28mm','mount'):
        path=OUT/'local'/('official-half-'+unit+'-with-hooks.json')
        if path.exists():
            r=json.loads(path.read_text());assert r['status'].startswith('PASS') and r['dat_sha256']==PIN
            matrix.append(dict(group='official-half',unit=unit,status='PASS',file=str(path.relative_to(ROOT)),source_sha256=file_sha(path)))
        else:missing.append(str(path.relative_to(ROOT)))
    save('evidence/regressions-verified.json',dict(status='PASS' if not missing and not bad else 'INCOMPLETE',
        dat_sha256=PIN,matrix=matrix,missing=missing,bad=bad,raw_records=raw,
        model_preparation_errors_excluded='local/cold-exit-matrix and its cancelled first commands; fixed r2 matrix is separately required.'))
    print('matrix',len(matrix),'raw final records',len(raw),'missing',len(missing))
    if missing:print('\n'.join(missing))
    assert not missing and not bad

if __name__=='__main__':main()
