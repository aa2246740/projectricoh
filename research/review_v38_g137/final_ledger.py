import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
PIN='78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8'
BODY='d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
fixture= json.loads((OUT/'evidence/users-fixture-resume.json').read_text())
FIXTURE=fixture['fixture_sha256']
assert fixture['base_sha256']==PIN and fixture['generation']==137
assert fixture['first_six_sections_equal'] and fixture['header_and_data_crc_checked']
assert fixture['roundtrip_empty_exact'] and fixture['user_entries']==32
EXPECTED={*[f'all-values-{i}' for i in range(4)],'L1-virtual-scroll','default-double-DISP','back-from-second-pair'}

def relative(path):return str(path.relative_to(ROOT))
def receipt(job):
    choices=[OUT/'evidence/receipts'/f'{job}.json',OUT/'evidence'/f'{job}.json']
    return next((path for path in choices if path.exists()),None)
def read(path):return json.loads(path.read_text())
def zero_mutations(data):
    values=data.get('file_mutations',{})
    return set(values)=={'create','write','rename','delete','write_open'} and all(value==0 for value in values.values())
def native_observed(data):
    values=data.get('native_UI',{})
    return values.get('watched',0)>0 and values.get('host_ui_writes')==0 and values.get('bad')==[]
def artifact_binding(root):
    bindings=[read(path) for path in root.glob('local/checks/*/binding-*.json')]
    return bool(bindings) and all(value.get('generation')==137 and value.get('dat_sha256')==PIN and
        any(item.get('body_sha256')==BODY for item in value.get('bindings',[])) for value in bindings)

groups=[]
for family,unit in [(124,'28mm'),(124,'mount'),(126,'50mm'),(126,'28mm'),(126,'mount')]:
    job=f'final-values-{family}-{unit}'
    root=OUT/'local/jobs'/job
    row={'name':f'group{family}-{unit}-values','job':job,'kind':'values','status':'NOT_STARTED','cases':[]}
    path=receipt(job)
    if path:
        event=read(path);row.update(returncode=event['returncode'],seconds=event['seconds'],receipt=relative(path))
        row['status']=event['status'] if event['status']!='DONE' else 'FAIL'
        names=set()
        for case_path in sorted(root.glob('local/checks/*/local/ui-cases/*.json')):
            data=read(case_path);name=case_path.stem.removeprefix(unit+'-');names.add(name)
            valid=data.get('status')=='PASS' and data.get('dat_sha256')==PIN and zero_mutations(data) and native_observed(data)
            if name.startswith('all-values-'):
                valid=valid and data.get('full_committed_settings_checked') is True and data.get('both_limits_clamp') is True and data.get('native_wrap_consumed') is True
            row['cases'].append({'name':name,'file':relative(case_path),'valid':valid,'status':data.get('status'),
                                 'events':len(data.get('events',[]))})
        row['artifact_binding']=artifact_binding(root)
        if event['returncode']==0 and names==EXPECTED and all(item['valid'] for item in row['cases']) and row['artifact_binding']:row['status']='PASS'
    elif root.exists():row['status']='IN_PROGRESS'
    groups.append(row)

users=[(124,'28mm','users','group124-28mm-users-r3'),(124,'mount','users','group124-mount-users-r3'),
       (126,'28mm','users','resume-users126-28mm'),(126,'28mm','other-users','group126-28mm-other-users'),
       (126,'mount','users','group126-mount-users'),(126,'mount','other-users','group126-mount-other-users')]
for family,unit,kind,job in users:
    root=OUT/'local/jobs'/job;path=receipt(job)
    row={'name':f'group{family}-{unit}-{kind}','job':job,'kind':kind,'status':'NOT_STARTED','reports':[]}
    if path:
        event=read(path);row.update(returncode=event['returncode'],seconds=event['seconds'],receipt=relative(path));row['status']='FAIL'
        for report_path in root.glob('local/checks/*/evidence/*users*.json'):
            data=read(report_path)
            row['reports'].append({'file':relative(report_path),'status':data.get('status'),
                                   'full_settings':data.get('full_committed_settings_checked'),
                                   'zero_file_mutations':zero_mutations(data),'dat_sha256':data.get('dat_sha256'),
                                   'native_observed':native_observed(data)})
        row['artifact_binding']=artifact_binding(root)
        complete=row['artifact_binding'] and bool(row['reports']) and all(r['status']=='PASS' and r['full_settings'] is True and r['zero_file_mutations'] and r['dat_sha256']==FIXTURE and r['native_observed'] for r in row['reports'])
        display=root/'local/user-display.json'
        if display.exists():
            value=read(display);row['display_file']=relative(display)
            row['other_assertions_completed']=value.get('other_assertions_completed')
            row['differences']=value.get('differences',[])
            title_only=bool(row['differences']) and all(d.get('line')==44 and d.get('actual')=='<5 F-CC' and d.get('expected')=='<FCC-001' for d in row['differences'])
            if event['status']=='DONE' and event['returncode']==1 and value.get('other_assertions_completed') is True and title_only and complete:row['status']='CLOSED_KNOWN_P2'
        if event['status']=='DONE' and event['returncode']==0 and complete:row['status']='PASS'
    elif root.exists():row['status']='IN_PROGRESS'
    groups.append(row)

samples=[]
for job in ['resume-empty-28mm','resume-empty-mount','h07-parent-50mm','resume-ownership','resume-native-events']:
    path=receipt(job)
    item={'name':job,'status':'NOT_STARTED'}
    if path:
        event=read(path);item.update(event);item['receipt']=relative(path)
        if job.startswith('resume-empty-'):
            lines=[]
            for line in (OUT/'local'/f'{job}.log').read_text().splitlines():
                try:lines.append(json.loads(line))
                except ValueError:pass
            item['negative_names']=[d['name'] for d in lines if d.get('phase')=='negative' and d.get('status')=='PASS']
            item['positive']=any(d.get('getter_delta')==0 and d.get('entry',{}).get('count')==0 and d.get('after',{}).get('rows')==8 and d.get('dat_sha256')==PIN for d in lines)
            item['accepted']=event['returncode']==0 and item['positive'] and set(item['negative_names'])=={'part0','part4','activity','native_state','names','rows'}
        elif job=='h07-parent-50mm':
            observations=[]
            for path in (OUT/'local/jobs'/job).glob('local/checks/*/evidence/*native-50mm.json'):
                value=read(path)
                valid=(value.get('status')=='OBSERVED' and value.get('dat_sha256')==PIN and
                       value.get('body_sha256')==BODY and
                       value.get('elf_sha256')==read(OUT/'evidence/artifact-resume.json')['engine_elf_sha256'] and
                       value.get('generation')==137 and value.get('assertions_enabled') is True and
                       value.get('switched') is True and value.get('settings_stores_after_switch')==[] and
                       value.get('preview_entries')==[] and zero_mutations(value))
                phases=[phase for phase in value.get('events',[]) if phase.get('phase') in ('hidden','parent_rebuilt')]
                valid=valid and len(phases)==2 and all(phase.get('strict_owned')==0 and phase.get('constructing_owned')==0 for phase in phases)
                observations.append({'file':relative(path),'status':value.get('status'),'valid':valid})
            item['observations']=observations
            item['accepted']=event['returncode']==0 and len(observations)==2 and all(value['valid'] for value in observations)
            item['evidence_status']='OBSERVED'
        elif job=='resume-ownership':
            value=read(OUT/'evidence/ownership-predicates-resume.json')
            item['accepted']=event['returncode']==0 and value['status']=='PASS_HOST_PREDICATES' and value['strict_equal']==4224 and value['data_negative_fields']==24
            item['evidence_status']=value['status']
        else:
            value=read(OUT/'evidence/native-events-resume.json')
            item['accepted']=event['returncode']==0 and value['status']=='PASS_HOST' and value['dat_sha256']==PIN and value['windows']==144177
            item['evidence_status']=value['status']
    elif (OUT/'local/jobs'/job).exists():item['status']='IN_PROGRESS'
    samples.append(item)

menu=[]
for path in (OUT/'local/jobs/final-menu-28mm').glob('local/checks/*/local/ui-cases/*-menu-edges.json'):
    value=read(path);menu.append({'file':relative(path),'status':value.get('status'),'dat_sha256':value.get('dat_sha256'),
                                 'events':len(value.get('events',[])),'full_settings':value.get('full_committed_settings_checked'),
                                 'zero_file_mutations':zero_mutations(value),'native_observed':native_observed(value)})
menu_receipt=receipt('final-menu-28mm')
menu_event=read(menu_receipt) if menu_receipt else {}
menu_ok=menu_event.get('status')=='DONE' and menu_event.get('returncode')==0 and artifact_binding(OUT/'local/jobs/final-menu-28mm') and bool(menu) and all(row['status']=='PASS' and row['dat_sha256']==PIN and row['full_settings'] is True and row['zero_file_mutations'] and row['native_observed'] for row in menu)
closed=sum(row['status'] in ('PASS','CLOSED_KNOWN_P2') for row in groups)
ready=closed==11 and all(item.get('accepted') for item in samples) and menu_ok
result={'dat_sha256':PIN,'users_fixture_sha256':FIXTURE,'groups':groups,'closed':closed,'total':11,'samples':samples,'menu':menu,'ready':ready}
(OUT/'regressions-final.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
lines=['# 回归表','',f'闭合 {closed}/11。PASS 要求整组退出码 0 且子项全部通过；CLOSED_KNOWN_P2 保留退出码 1，只接受已明确认可的卡片标题差异。',
       '','| 原组 | 实际运行 | 原始退出码 | 状态 | 秒 |','| --- | --- | --- | --- | --- |']
for row in groups:lines.append(f'| {row["name"]} | {row["job"]} | {row.get("returncode","")} | {row["status"]} | {row.get("seconds","")} |')
lines+=['','每个 values 整组要求四个数值子项、L1、Default、返回光标共 7 项。数据文件路径及逐项检查在 regressions-final.json。',
        '','| 抽样 | 原始退出码 | 状态 |','| --- | --- | --- |']
for row in samples:lines.append(f'| {row["name"]} | {row.get("returncode","")} | {row.get("evidence_status","PASS") if row.get("accepted") else row["status"]} |')
lines+=['',f'列表首尾及数值端点的当前 M32R 菜单检查：{"PASS" if menu_ok else "未闭合"}。',
        '', '历史 r6 的前三组为 6/7 子项通过，只有 L1 旧期望失败；最后两组实际为返回 -15、各 2 项通过。历史返回码与新结果分开保留。',
        '','所有 observations=0 的旧结果均按错误文件、子项文件和标题记录重新归类，未将它解释为 0 个用例执行。']
(OUT/'REGRESSIONS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'closed':closed,'ready':ready,'groups':{r['name']:r['status'] for r in groups}},ensure_ascii=False))
