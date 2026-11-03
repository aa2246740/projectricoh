#!/usr/bin/python3
"""Summarize group results and independently check retained printable labels."""
from pathlib import Path
import collections
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_g127'
WORK=ROOT/'research/g127_fix'
PIN='9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'
NAMES={'safety':'safety-{u}.json','locked':'locked-{u}.json',
       'nested':'lock-nested-127-{u}-record_failure_return-after_update_restore-before_redraw-row_draw.json',
       'cutpoints':'lock-cutpoints-{u}-irq-enabled.json','exits':'lock-exits-127-{u}.json',
       'transitions':'transitions-{u}.json','values':'values-{u}.json',
       'view-reentry':'view-reentry-{u}.json','reentry-six':'reentry-all-keys-{u}.json',
       'users':'users-{u}.json','other-users':'other-users-{u}.json',
       'project':'project-boundary-{u}.json','labels':'labels-{u}.json',
       'half':'../local/official-half-{u}-with-hooks.json'}

def read(path):
    return json.loads(path.read_text())

def counts(data):
    rows=data.get('cases',data.get('results',[]))
    result=dict(PASS=0,FAIL=0,OBSERVED=0,NA=0)
    if rows:
        for row in rows:
            if row.get('status')=='REMOVED_UPDATE_PATH':
                result['NA']+=1
            elif 'wait_status' in row:
                result['PASS' if row['wait_status']==0 else 'FAIL']+=1
            elif row.get('status','').startswith('PASS'):
                result['PASS']+=1
            elif row.get('status')=='OBSERVED':
                result['OBSERVED']+=1
            elif row.get('status') in ('FAIL','EXECUTION_ERROR'):
                result['FAIL']+=1
    elif data.get('status','').startswith('PASS'):
        result['PASS']=1
    elif data.get('status')=='OBSERVED':
        result['OBSERVED']=1
    elif data.get('status') in ('FAIL','EXECUTION_ERROR'):
        result['FAIL']=1
    return result

def journal():
    records={}
    entries=[]
    for path in (WORK/'evidence/groups-commands.jsonl',OUT/'runs.jsonl',OUT/'priority-batch-runs.jsonl'):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            row=json.loads(line)
            if row.get('dat_sha256')==PIN or path.parent==OUT and row.get('status')=='NOT_STARTED':
                row['record_origin']='review' if path.parent==OUT else 'original'
                entries.append(row)
    entries.sort(key=lambda row:(row['record_origin']=='review',row.get('started_utc','9999')))
    for row in entries:
        previous=records.get(row['name'],{})
        if previous.get('returncode')==0 and row.get('returncode') in (None,124):
            continue
        records[row['name']]=row
    return records

def labels():
    result=dict(files=0,strings=0,bad=[],root_groups=[])
    def walk(value,path,where=''):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('labels','ascii_labels') and isinstance(item,list):
                    for text in item:
                        if not isinstance(text,str):
                            continue
                        result['strings']+=1
                        if not 0<len(text)<=8 or not all(32<=ord(char)<=126 for char in text):
                            result['bad'].append(dict(file=str(path.relative_to(ROOT)),field=where+'.'+key,
                                                      codepoints=[ord(char) for char in text]))
                else:
                    walk(item,path,where+'.'+key)
        elif isinstance(value,list):
            for item in value:
                if isinstance(item,(list,dict)):
                    walk(item,path,where)
    for family in (124,126):
        folder=WORK/f'local/release127/review_g{family}'
        for sub in ('evidence','local/ui-cases','local/view-reentry','local/reentry-all-keys',
                    'local/lock-cases','local/nested','local/lock-exits','local/settings-cases'):
            for path in (folder/sub).glob('*.json'):
                result['files']+=1
                walk(read(path),path)
    return result

def main():
    records=journal()
    acceptance=read(WORK/'evidence/acceptance.json')
    results=[]
    for group in acceptance['groups']:
        family,unit,name=group['family'],group['unit'],group['group']
        label=f'group{family}-{unit}-{name}'
        row=records.get(label,{})
        path=WORK/f'local/release127/review_g{family}/evidence'/NAMES[name].format(u=unit)
        path=path.resolve()
        data=read(path) if path.exists() else {}
        values=counts(data)
        valid_sha=data.get('dat_sha256')==PIN
        if name in ('users','other-users'):
            tool=read(WORK/f'local/release127/review_g{family}/evidence/user-tool.json')
            valid_sha=data.get('dat_sha256')==tool['fixture_sha256'] and tool['base_dat_sha256']==PIN
        complete=row.get('returncode')==0 and values['FAIL']==0 and values['PASS']>0 and valid_sha
        current_failure=(row.get('record_origin')=='review' and row.get('returncode') not in (None,124) and
                         (row.get('returncode') not in (None,0,124) or values['FAIL']))
        status='PASS' if complete else 'FAIL' if current_failure else 'INCOMPLETE'
        counts_known=bool(data) or row.get('status')=='NOT_STARTED'
        results.append(dict(name=label,family=family,unit=unit,group=name,status=status,
            returncode=row.get('returncode'),seconds=row.get('seconds'),case_counts=values,
            case_counts_known=counts_known,
            execution_status=row.get('status','ORIGINAL_RESULT' if row.get('record_origin')=='original' else 'NOT_STARTED'),
            original_complete=group['complete'],source=row.get('record_origin','none'),
            reused=row.get('reused',False),artifact_sha_valid=valid_sha,
            evidence=str(path.relative_to(ROOT)) if path.exists() else None,
            evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None))
    assert len(results)==81
    extra=[]
    for kind,family,filename in (('history123',123,'suite-127-{u}.json'),
                                 ('settings_cases',126,'settings-cases-{u}.json')):
        for unit in ('50mm','28mm','mount'):
            label=kind+'-'+unit
            row=records.get(label,{})
            path=WORK/f'local/release127/review_g{family}/evidence'/filename.format(u=unit)
            data=read(path) if path.exists() else {}
            values=counts(data)
            valid_sha=data.get('dat_sha256')==PIN
            if kind=='history123' and row.get('returncode')==0:
                valid_sha=True
                for case in data.get('results',[]):
                    raw=WORK/f'local/release127/review_g123/local/cases/127-{unit}-{case["case"]}.json'
                    actual=read(raw) if raw.exists() else {}
                    valid_sha=valid_sha and actual.get('artifact',{}).get('dat_sha256')==PIN
                    valid_sha=valid_sha and actual.get('artifact',{}).get('elf_sha256')=='13ecc74e2a23089fda0fbe6e694a3ce8cf74bc6233e357902e95b5c3cae12bae'
            done=row.get('returncode')==0 and values['FAIL']==0 and values['PASS'] and valid_sha
            failed=row.get('returncode') not in (None,0,124) or row.get('returncode')==0 and values['FAIL']
            extra.append(dict(name=label,returncode=row.get('returncode'),seconds=row.get('seconds'),
                case_counts=values,status='PASS' if done else 'FAIL' if failed else 'INCOMPLETE',
                artifact_sha_valid=valid_sha,
                evidence=str(path.relative_to(ROOT)) if path.exists() else None))
    ascii_check=labels()
    value=dict(groups_required=81,groups_complete=sum(r['status']=='PASS' for r in results),
               groups_failed=sum(r['status']=='FAIL' for r in results),groups=results,extra=extra,
               label_check=ascii_check)
    (OUT/'regressions.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    lines=['81 组回归表。NA 表示旧套件保留的已移除调用点，不计入实际执行 PASS。',
           '未生成结构化组汇总时，已执行部分的 PASS/FAIL 数记为未知；NOT_STARTED 的本轮执行数为零。',
           '', '| 家族 | 单元 | 组 | 来源 | 执行状态 | 返回码 | 秒 | PASS | FAIL | NA | 结果 |',
           '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in results:
        c=row['case_counts']
        display={key:str(value) if row['case_counts_known'] else '未知' for key,value in c.items()}
        lines.append(f"| {row['family']} | {row['unit']} | {row['group']} | {row['source']} | {row['execution_status']} | {row['returncode'] if row['returncode'] is not None else '无'} | {row['seconds'] if row['seconds'] is not None else '无'} | {display['PASS']} | {display['FAIL']} | {display['NA']} | {row['status']} |")
    lines+=['', '| 附加套件 | 返回码 | 秒 | PASS | FAIL | 结果 |','| --- | --- | --- | --- | --- | --- |']
    for row in extra:
        c=row['case_counts']
        lines.append(f"| {row['name']} | {row['returncode'] if row['returncode'] is not None else '无'} | {row['seconds'] if row['seconds'] is not None else '无'} | {c['PASS']} | {c['FAIL']} | {row['status']} |")
    (OUT/'REGRESSIONS.md').write_text('\n'.join(lines)+'\n')
    print('groups',value['groups_complete'],'/',81,'FAIL',value['groups_failed'],
          'extra_complete',sum(row['status']=='PASS' for row in extra),
          'labels_checked',ascii_check['strings'],'bad',len(ascii_check['bad']))

if __name__=='__main__':
    main()
