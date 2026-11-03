"""Summarize completed groups without treating missing records as a pass."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
PIN='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'

def read(path,default=None):
    if not path.is_file():return default
    try:return json.loads(path.read_text())
    except (ValueError,OSError):return default

def partial_records(folder):
    counts=Counter();seen=set()
    for path in folder.glob('*/local/*/*.json'):
        item=read(path,{})
        if not isinstance(item,dict) or 'case' not in item or 'status' not in item:continue
        key=str(item['case'])
        if key in seen:continue
        seen.add(key);counts[str(item['status'])]+=1
    return dict(counts)

def summarize(job,finished,active):
    name=job['name'];run=finished.get(name)
    folder=WORK/'local'/name
    result_files=list(folder.glob('*/result.json')) if folder.is_dir() else []
    runtime=next((read(p) for p in result_files if read(p,{}).get('name')==name),{})
    value={'name':name,'returncode':run.get('returncode') if run else None,
           'execution':run.get('state') if run else 'RUNNING' if name in active else 'NOT_STARTED',
           'seconds':run.get('seconds',0) if run else 0,'case_counts':{},'evidence':[]}
    value['partial_record_counts']=partial_records(folder) if folder.is_dir() else {}
    if not run:
        value['status']='RUNNING' if name in active else 'INCOMPLETE';return value
    value['error_type']=runtime.get('error_type')
    if run.get('state')!='FINISHED':value['status']='INCOMPLETE';return value
    if runtime and runtime.get('dat_sha256')!=PIN:value['status']='IDENTITY_ERROR';return value
    aggregates=[]
    for path in folder.glob('*/evidence/*.json'):
        document=read(path,{})
        cases=document.get('cases') if isinstance(document,dict) else None
        if not isinstance(cases,list) or not cases or not all(isinstance(c,dict) and 'wait_status' in c for c in cases):continue
        identity=document.get('dat_sha256')
        if identity is not None and identity!=PIN:value['status']='IDENTITY_ERROR';return value
        aggregates.append((path,cases))
    counts=Counter();seen=set();ids={case.get('case') for _,cases in aggregates for case in cases}
    children={}
    if ids:
        for path in folder.rglob('*.json'):
            if path.stem not in ids:continue
            document=read(path,{})
            if isinstance(document,dict):children[path.stem]=document
    for path,cases in aggregates:
        value['evidence'].append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        for case in cases:
            key=case.get('case');identity=(key,case['wait_status'])
            if identity in seen:continue
            seen.add(identity);status=case.get('status',children.get(key,{}).get('status'))
            if status in ('REMOVED_UPDATE_PATH','NA','NOT_APPLICABLE'):counts['NA']+=1
            elif case['wait_status'] or status in ('FAIL','HARNESS_ERROR'):counts['FAIL']+=1
            elif job['kind']=='history122':counts['OBSERVED']+=1
            else:counts['PASS']+=1
    if not aggregates and run.get('returncode')==0:
        if job['kind'] in ('history122','history123'):
            observations={}
            for path in folder.glob('**/*.json'):
                item=read(path,{})
                if not isinstance(item,dict) or 'case' not in item or 'status' not in item:continue
                if item.get('artifact',{}).get('dat_sha256')!=PIN:continue
                observations[str(item['case'])]=item['status']
            if len(observations)==9:
                counts['OBSERVED' if job['kind']=='history122' else 'PASS']=9
                value['count_scope']='nine_case_records'
            else:
                counts['PASS']=1;value['count_scope']='whole_suite'
        else:counts['PASS']=1;value['count_scope']='whole_suite'
    value['case_counts']=dict(counts)
    if run.get('returncode')!=0 or counts['FAIL']:
        tools=('FileNotFoundError','PermissionError','KeyError','TypeError','UnicodeDecodeError')
        reference_error=any('review_g129/r2_oracle.py:' in name for name in runtime.get('failure_names',[]))
        value['status']='TOOL_ERROR' if runtime.get('error_type') in tools or reference_error else 'FAIL_UNCLASSIFIED'
    else:value['status']='OBSERVED' if job['kind']=='history122' else 'PASS'
    return value

def main():
    plan=read(WORK/'plan.json');runs=read(WORK/'schedule-results.json',[])
    manual=read(WORK/'manual-results.json',[])
    finished={item['name']:item for item in [*runs,*manual]};state=read(WORK/'schedule-state.json',{})
    active=set(state.get('active',[]));jobs={job['name']:job for job in plan['jobs']}
    groups=[]
    for row in plan['matrix']:
        value=summarize(jobs[row['name']],finished,active);value.update(row);groups.append(value)
    aliases=read(WORK/'retry-map.json',{})
    extras=[]
    for job in plan['jobs']:
        if job['kind'] not in ('history123','settings_cases','history122'):continue
        value=summarize(job,finished,active);retry=aliases.get(job['name'])
        if retry in finished:
            prior=value;value=summarize({**job,'name':retry},finished,active)
            value['accepted_run_name']=retry;value['name']=job['name'];value['prior_attempt']=prior
        extras.append(value)
    totals=Counter(item['status'] for item in groups)
    result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'dat_sha256':PIN,
            'required_groups':81,'group_states':dict(totals),'groups':groups,'extra':extras,
            'finished_commands':len(runs),'active_commands':sorted(active)}
    (WORK/'regressions.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['81 组完整回归表。下表只使用本轮 gen 129 的执行结果。','',
           'NA 表示最终代码没有相应旧调用点，不计为实际执行 PASS。缺少记录、时间盒停止和工具适配失败均不记通过。没有逐例汇总的完整套件只计一组通过。已有记录列仅表示已落盘的逐例记录数，不表示整组通过；分类见 JSON 的 partial_record_counts。','',
           '| 家族 | 单元 | 组 | 执行 | 返回码 | 秒 | PASS | FAIL | NA | 已有记录 | 结果 |',
           '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for item in groups:
        counts=item['case_counts'];lines.append('| '+' | '.join(str(v) for v in (item['family'],item['unit'],item['group'],item['execution'],item['returncode'],item['seconds'],counts.get('PASS',0),counts.get('FAIL',0),counts.get('NA',0),sum(item.get('partial_record_counts',{}).values()),item['status']))+' |')
    lines+=['','| 附加套件 | 采用记录 | 执行 | 返回码 | 秒 | PASS | FAIL | OBSERVED | 结果 |','| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for item in extras:
        counts=item['case_counts'];lines.append('| '+' | '.join(str(v) for v in (item['name'],item.get('accepted_run_name',item['name']),item['execution'],item['returncode'],item['seconds'],counts.get('PASS',0),counts.get('FAIL',0),counts.get('OBSERVED',0),item['status']))+' |')
    lines+=['','复跑前的首次结果保留在 regressions.json 的 prior_attempt、对应 local 目录和 manual-results.json 中。没有用独立的窄范围检查替代完整旧套件。']
    lines+=['', '汇总时间：'+result['utc']+'。']
    (WORK/'REGRESSIONS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'name':'regression_summary','returncode':0,'required':81,**dict(totals)}))

if __name__=='__main__':main()
