import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
PIN='78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8'
groups=[]
for family,unit in [(124,'28mm'),(124,'mount'),(126,'50mm'),(126,'28mm'),(126,'mount')]:
    groups.append({'name':f'group{family}-{unit}-values','job':f'group{family}-{unit}-values-r8','kind':'values'})
for family,unit,kind,suffix in [(124,'28mm','users','-r3'),(124,'mount','users','-r3'),
                              (126,'28mm','users','-r5'),(126,'28mm','other-users',''),
                              (126,'mount','users',''),(126,'mount','other-users','')]:
    name=f'group{family}-{unit}-{kind}'
    groups.append({'name':name,'job':name+suffix,'kind':kind})

def relative(path):return str(path.relative_to(ROOT))
for row in groups:
    receipt=OUT/'evidence'/(row['job']+'.json')
    root=OUT/'local/jobs'/row['job']
    if not receipt.exists():
        row['status']='IN_PROGRESS' if root.exists() else 'NOT_STARTED'
        continue
    value=json.loads(receipt.read_text())
    row.update({key:value[key] for key in ['returncode','seconds']})
    row['receipt']=relative(receipt)
    row['source_results']=[relative(p) for p in root.glob('local/checks/*/result-*.json')]
    row['status']='FAIL'
    if value['status']!='DONE':row['status']=value['status'];continue
    if value['returncode']<0:row['status']='STOPPED';continue
    if value['dat_sha256']!=PIN:row['status']='IDENTITY';continue
    if row['kind']=='values':
        cases=[]
        for path in sorted(root.glob('local/checks/*/local/ui-cases/*.json')):
            case=json.loads(path.read_text())
            cases.append({'file':relative(path),'status':case.get('status'),
                          'dat_sha256':case.get('dat_sha256'),'events':len(case.get('events',[])),
                          'full_committed_settings_checked':case.get('full_committed_settings_checked')})
        row['cases']=cases
        row['case_count']=len(cases)
        if value['returncode']==0 and len(cases)==7 and all(c['status']=='PASS' and c['dat_sha256']==PIN for c in cases):
            row['status']='PASS'
    else:
        display=root/'local/user-display.json'
        if display.exists():
            row['display']=relative(display)
            row['display_data']=json.loads(display.read_text())
        reports=[]
        for path in root.glob('local/checks/*/evidence/*.json'):
            if path.name=='user-tool.json':continue
            data=json.loads(path.read_text())
            reports.append({'file':relative(path),'status':data.get('status'),
                            'full_committed_settings_checked':data.get('full_committed_settings_checked'),
                            'events':len(data.get('events',[]))})
        row['reports']=reports
        if value['returncode']==0 and reports and all(r['status']=='PASS' for r in reports):
            row['status']='PASS'
        elif value['returncode']==1 and row.get('display_data',{}).get('other_assertions_completed') is True:
            if reports and all(r['status']=='PASS' for r in reports):row['status']='CLOSED_KNOWN_P2'

focus=[]
for name in ['empty-28mm-r4','empty-mount-r4','h07-parent-mount-r3','h07-parent-50mm','list-windows','menu-edges-28mm-r5',
             'ownership-host-r4','native-events','code-static']:
    path=OUT/'evidence'/(name+'.json')
    if path.exists():
        result=json.loads(path.read_text());focus.append(dict(result,receipt=relative(path)))
    else:focus.append({'name':name,'status':'IN_PROGRESS' if (OUT/'local/jobs'/name).exists() else 'NOT_STARTED'})

closed=sum(row['status'] in ('PASS','CLOSED_KNOWN_P2') for row in groups)
data={'dat_sha256':PIN,'groups':groups,'closed':closed,'total':len(groups),'focused':focus}
(OUT/'regressions.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
lines=['# 回归表','',f'严格通过或在用户明确认可的已知标题差异下闭合：{closed}/{len(groups)}。',
       '','PASS 要求整组 OS 退出码为 0。CLOSED_KNOWN_P2 保留退出码 1，且要求其余断言全部执行完；已知项只限用户卡片标题。',
       '','| 原组 | 本轮运行 | 原始退出码 | 状态 | 秒 |','| --- | --- | --- | --- | --- |']
for row in groups:
    name=row['name'];job=row['job'];code=row.get('returncode','');seconds=row.get('seconds','')
    lines.append(f'| {name} | {job} | {code} | {row["status"]} | {seconds} |')
lines+=['','原始子项、标题记录和 OS 回执路径见 `regressions.json`。初始读取失败、旧夹紧期望失败和主动停止均保留在 `evidence/runs.jsonl`，不计为本表通过。',
        '','| 独立抽样 | 原始退出码 | 执行状态 | 秒 |','| --- | --- | --- | --- |']
for row in focus:lines.append(f'| {row["name"]} | {row.get("returncode","")} | {row["status"]} | {row.get("seconds","")} |')
(OUT/'REGRESSIONS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'closed':closed,'total':len(groups),'states':{r['name']:r['status'] for r in groups}},ensure_ascii=False))
