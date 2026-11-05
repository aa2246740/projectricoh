"""Write a bounded report from receipts. No firmware execution or fitting occurs."""
from pathlib import Path
import argparse
import datetime
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args();C.setup()
def read(path):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None
utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
state=read(C.LOCAL/'r1-work.progress.json') or {}
disposition=[]
if a.final:
    settled=read(C.LOCAL/'r1-work.result.json') or {}
    finished=settled.get('finished',state.get('finished',{}))
    live={}
    for key,pid in state.get('running',{}).items():
        process=subprocess.run(['ps','-p',str(pid),'-o','command='],text=True,capture_output=True)
        active=process.returncode==0 and str(C.HERE/'run.py') in process.stdout
        if active:live[key]=pid
        disposition.append(dict(task=key,pid=pid,status='STILL_RUNNING_OPEN' if active else 'STOPPED_OR_SETTLED',result=(read(C.LOCAL/'runs'/key/'result.json') or {}).get('status')))
    for key in state.get('pending',[]):
        if key not in finished:disposition.append(dict(task=key,status='NOT_STARTED_OPEN'))
    state=dict(state,finished=finished,running=live)
    C.save(C.LOCAL/'deadline-disposition.json',dict(utc=utc,deadline=settled.get('deadline'),running=live,rows=disposition,boundary='Stopped or incomplete runs remain OPEN. Their original result files are preserved.'))
allruns=[(f.parent.name,read(f)) for f in (C.LOCAL/'runs').glob('*/result.json')]
summary={}
for dataset in ('model','control'):
    manifests={profile:read(C.artifact(profile,dataset)['manifest']) for profile in ('test','release')}
    valid=[(name,r) for name,r in allruns if r and r.get('dataset')==dataset and r.get('dat_sha256')==manifests.get(r.get('version'),{}).get('dat_sha256') and r.get('cold_start') and not r.get('snapshots') and r.get('status')=='OBSERVED']
    full=[];refs=[];cold=[];partial=[];acros=[]
    for profile in ('test','release'):
        for unit in C.UNITS:
            these=[(n,r) for n,r in valid if r['version']==profile and r['unit']==unit]
            native=[n for n,r in these if r.get('actual_backend')=='native' and len(r.get('samples',[]))==18 and len(r.get('builtin_samples',[]))==8 and len(r.get('user_samples',[]))==3 and r.get('DISP_back',{}).get('screen')==0 and r.get('after_close',{}).get('state')==5 and r.get('ADJ_closed',{}).get('state')==5 and r.get('close_record_equal')]
            reference=[n for n,r in these if r.get('actual_backend')=='reference' and r.get('challenge')=='none' and (r.get('BOOT_expected_552_equal') if profile=='test' else r['first_menu']['memory_result']==1 and r.get('unit_W')==0)]
            standby=[n for n,r in these if r.get('cold',{}).get('state')==5 and r.get('first_menu',{}).get('rows')==8 and r['first_menu']['root_state']==3]
            key=profile+'/'+unit
            full.append(dict(case=key,status='PASS' if native else 'OPEN',runs=native))
            refs.append(dict(case=key,status='PASS' if reference else 'OPEN',runs=reference))
            cold.append(dict(case=key,status='PASS' if standby else 'OPEN',runs=standby))
            acros_runs=[n for n,r in these if r.get('actual_backend')=='native' and r.get('DISP_back',{}).get('screen')==0 and r.get('after_close',{}).get('state')==5 and r.get('ADJ_closed',{}).get('state')==5 and r.get('close_record_equal') and any(s.get('name')=='Acros' and s.get('full_40_equal') and s.get('unit_readback',{}).get('complete_552_equal') for s in r.get('samples',[]))]
            acros.append(dict(case=key,status='PASS' if acros_runs else 'OPEN',runs=acros_runs,boundary='Acros readback and navigation only; this does not replace the full 29-row sweep.'))
            candidates=[(n,r) for n,r in allruns if r and r.get('dataset')==dataset and r.get('dat_sha256')==manifests[profile]['dat_sha256'] and r.get('version')==profile and r.get('unit')==unit and r.get('actual_backend')=='native' and len(r.get('samples',[]))==18 and len(r.get('builtin_samples',[]))==8 and len(r.get('user_samples',[]))==3]
            partial.append(dict(case=key,all_29_rows_observed=bool(candidates),whole_flow_verified=bool(native),source_runs=[n for n,r in candidates]))
    tag='r2' if dataset=='model' else 'r1';directory=C.LOCAL/('persistence-'+tag+'-'+dataset)
    inputs=read(directory/'inputs.json') or [];verification=read(directory/'verification.json')
    replay=[]
    for row in inputs:
        r=read(C.LOCAL/'runs'/row['label']/'result.json')
        if r and r.get('status')=='OBSERVED' and r.get('dat_sha256')==manifests[row['target']]['dat_sha256']:replay.append(row['label'])
    receipts=C.LOCAL/'acceptance'/dataset
    host=[]
    for backend in ('c','python'):
        memory=read(receipts/('host-'+backend+'.json')) or {}
        ok=memory.get('status')=='PASS' and memory.get('cases')==108 and len(memory.get('rows',[]))==108 and all(row.get('DAT_sha256')==manifests.get(row.get('profile'),{}).get('dat_sha256') and row.get('owned_record')==1 and row.get('memory_build_literal_equal') for row in memory.get('rows',[]))
        host.append(dict(probe='memory-'+backend,status='PASS' if ok else 'OPEN',cases=memory.get('cases',0)))
        for profile in ('test','release'):
            service=read(receipts/('service-'+profile+'-'+backend+'.json')) or {}
            ok=service.get('status')=='PASS' and service.get('DAT_sha256')==manifests[profile]['dat_sha256'] and len(service.get('rows',[]))==54 and all(row.get('op5')==0 and row.get('full_40_equal') and row.get('S_write_fence') and len(row.get('readbacks',[]))==3 for row in service.get('rows',[]))
            host.append(dict(probe='SETTINGS-op5-'+profile+'-'+backend,status='PASS' if ok else 'OPEN',cases=len(service.get('rows',[]))))
    summary[dataset]=dict(manifests=manifests,host=host,native=full,reference=refs,cold=cold,acros_navigation=acros,observed_rows=partial,S48=dict(status='PASS' if verification and verification.get('status')=='PASS' and verification.get('cases')==48 else 'OPEN',completed=len(replay),required=48,verification=str(directory/'verification.json')))
result=dict(verdict='有缺陷',utc=utc,final=a.final,datasets=summary,LCD=dict(status='OPEN',screenshot=None),queue_running=state.get('running',{}),queue_pending=state.get('pending',[]),deadline_disposition=disposition,persistent_Vivid_MAIN='OPEN',boundary='Only completed receipts with the final DAT SHA count. Partial/failed/stopped runs never become whole-flow PASS.')
C.save(C.LOCAL/('FINAL.json' if a.final else 'STAGE.json'),result)
def count(rows):return sum(r['status']=='PASS' for r in rows)
lines=['## '+('最终封存' if a.final else '最新阶段快照')+'（'+utc+'）','',
    '有缺陷。以下计数只来自最终 DAT SHA 匹配且正常收尾的回执。LCD 像素截图仍缺失，完整矩阵未完成的单元继续 OPEN。','',
    '| 验收 | 新记录最终包 | 早期数据对照 |','| --- | --- | --- |',
    '| 主机 C/Python 与真实 op5 | '+('PASS' if all(r['status']=='PASS' for r in summary['model']['host']) else 'OPEN')+' | '+('PASS' if all(r['status']=='PASS' for r in summary['control']['host']) else 'OPEN')+' |',
    f"| 新 MAIN 待机与八行发布 | {count(summary['model']['cold'])}/6 | {count(summary['control']['cold'])}/6 |",
    f"| 29 条配方、游标、DISP、OK/ADJ 完整流程 | {count(summary['model']['native'])}/6 | {count(summary['control']['native'])}/6 |",
    f"| Acros 读回与 DISP/OK/ADJ 单项路径 | {count(summary['model']['acros_navigation'])}/6 | {count(summary['control']['acros_navigation'])}/6 |",
    f"| 参考模拟器关键路径 | {count(summary['model']['reference'])}/6 | {count(summary['control']['reference'])}/6 |",
    f"| 完整 S 交叉重放 | {summary['model']['S48']['completed']}/48，{summary['model']['S48']['status']} | {summary['control']['S48']['completed']}/48，{summary['control']['S48']['status']} |",
    '| 字节审计、数据接入引擎等价 | PASS，未解释 0 B | PASS，未解释 0 B |',
    '| LCD 像素与诊断截图 | OPEN，无截图 | OPEN |','',
    '逐单元结果、部分观察与未完成队列保存在 '+('local/FINAL.json' if a.final else 'local/STAGE.json')+'。50mm/28mm 的完整流程若未正常收尾，不因已核对部分颜色记录而改计 PASS。','',
    'OPEN：表中尚未完成的原生/参考/S 重放组合；实际 LCD 截图；首次 ADJ 前持续 Vivid 的完整 MAIN 路径；物理 M 与 H51 原值绑定；真实关机/NAND、单元持久状态、首拍/JPEG。DAT 缺席/retired 的 resident 页面按本轮合同只写设计，未实现。','']
lines+=['| 包 / 单元 | 最终包完整原生流程 | 最终包参考关键路径 | 对照完整原生流程 | 对照参考关键路径 |','| --- | --- | --- | --- | --- |']
for i,row in enumerate(summary['model']['native']):
    lines.append('| '+row['case']+' | '+row['status']+' | '+summary['model']['reference'][i]['status']+' | '+summary['control']['native'][i]['status']+' | '+summary['control']['reference'][i]['status']+' |')
lines.append('')
report=C.HERE/'REPORT.md';text=report.read_text();start='<!-- G157 LIVE RECEIPTS BEGIN -->';end='<!-- G157 LIVE RECEIPTS END -->';block=start+'\n'+'\n'.join(lines)+'\n'+end
if start in text:text=text[:text.index(start)]+block+text[text.index(end)+len(end):]
else:
    at=text.index('\n\n');text=text[:at+2]+block+'\n\n'+text[at+2:]
if a.final:
    text=text.replace('本报告会在封存时按最终回执更新。','本报告已按截止时最终回执封存。')
    text=text.replace('模拟器完整矩阵正在运行。','模拟器已按截止时回执封存，未完成组合保持 OPEN。')
report.write_text(text)
for profile,root in C.PACKAGES.items():
    manifest=read(root/'MANIFEST');manifest['status']='PARTIAL_ACCEPTANCE_OPEN' if a.final else 'LOCAL_ACCEPTANCE_IN_PROGRESS'
    manifest['acceptance_utc']=utc;manifest['native_complete']=count(summary['model']['native']);manifest['reference_complete']=count(summary['model']['reference']);manifest['S_replay']=summary['model']['S48'];manifest['LCD_screenshot']='OPEN';manifest['verdict']='有缺陷';C.save(root/'MANIFEST',manifest)
print(json.dumps(dict(verdict='有缺陷',utc=utc,final=a.final,model_native=count(summary['model']['native']),model_reference=count(summary['model']['reference']),model_S48=summary['model']['S48'],control_native=count(summary['control']['native']),control_S48=summary['control']['S48'])))
