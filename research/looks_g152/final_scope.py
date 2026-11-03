"""Record actual final-identity regression coverage and remaining work."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
def read(name):
    p=HERE/name
    return json.loads(p.read_text()) if p.is_file() else {}
def main():
    package=read('package.json');test=package['test']['dat_sha256']
    identities={test,package['release']['dat_sha256']}
    plan=HERE/'REGRESSION_SCOPE_PLAN.json'
    if not plan.exists():plan.write_text((HERE/'REGRESSION_SCOPE.json').read_text())
    rows=json.loads(plan.read_text());result=[]
    for old in rows:
        row=dict(old,planned_units=old['units'],units=[])
        for unit in ('50mm','mount','28mm'):
            name='evidence/reg-'+unit+'-'+old['case']+'.json'
            if old['case']=='t-boot' and unit!='28mm':name='evidence/t0-'+unit+'.json'
            if old['case']=='service-six-matrix' and unit=='mount':name='evidence/review-service-six-matrix-mount.json'
            receipt=read(name)
            if receipt.get('status')=='PASS' and receipt.get('dat_sha256') in identities:row['units'].append(unit)
        if row['units']:
            row.update(status='FINAL_PASS',reason='最终 DAT 实测通过所列单元；未列单元留给发布复审。')
        elif old['units']:
            row.update(status='DEFERRED_RELEASE_REVIEW',reason='留给发布复审：本组不在续轮相关回归选择内，未把旧摘要结果计为最终通过。')
        else:row['status']='DEFERRED_RELEASE_REVIEW'
        result.append(row)
    (HERE/'REGRESSION_SCOPE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    text=['# 相关旧回归的最终范围','','按最终 DAT 回执列实际执行单元。原计划另存 REGRESSION_SCOPE_PLAN.json；旧候选结果不计入本表。','','| 来源 | 用例 | 最终执行单元 | 结论与理由 |','|---|---|---|---|']
    for r in result:text.append('| '+r['group']+' | '+r['case']+' | '+(', '.join(r['units']) or '—')+' | '+r['reason']+' |')
    (HERE/'REGRESSION_SCOPE.md').write_text('\n'.join(text)+'\n')
    planned={j['name']:j for j in read('queue-required.json')}
    gaps=[];passed=0
    for job in planned.values():
        r=read('evidence/jobs/'+job['name']+'.json')
        if r.get('status')=='PASS' and r.get('dat_sha256')==test:passed+=1;continue
        reason='本轮要求项尚未完成，必须补齐后才能交复审。'
        if r:reason='最终候选回执为 '+r.get('status','UNKNOWN')+'；须查明并重新验收。'
        gaps.append(dict(job=job['name'],script=job['script'],args=job.get('args',[]),reason=reason))
    deferred=[]
    for unit in ('50mm','mount'):
        deferred.append(dict(job='full-locks-'+unit,classification='RELEASE_REVIEW',script='lock_checks.py',args=['--unit',unit],
            reason='留给发布复审：完整 4×6×3=72 项。按用户续轮指令，本轮先做该单元 4×3×2=24 项；旧候选完整 144 项均通过，本轮核对最终改动是否改变同类路径。C 后端仍在复审，本轮不用。'))
    deferred += [dict(job='legacy-other-cases',classification='RELEASE_REVIEW',script='REGRESSION_SCOPE.md',args=[],reason='留给发布复审：99 条旧用例中未选部分，逐条理由见该表。'),
        dict(job='core-81-groups',classification='RELEASE_REVIEW',script='CORE_REGRESSION_SCOPE.md',args=[],reason='留给发布复审：81 组全量回归未在本轮扩跑，逐条理由见该表。'),
        dict(job='camera-and-unit-paths',classification='RELEASE_REVIEW',script='REPORT.md',args=[],reason='留给发布复审：真实 LCD、RPC/RTOS 时序、ISO100 单元分支、rpc_ready=0 首开和失归属时 S 待写边界仍须现场验证。'),
        dict(job='image-quality',classification='RELEASE_REVIEW',script='fit_results.json',args=[],reason='留给发布复审：扇区模型限制及 28mm/MOUNT 独立画质标定不能由本轮编码行与主机预测代替。')]
    (HERE/'FINAL_GAPS.json').write_text(json.dumps(dict(dat_sha256=test,required=len(planned),passed=passed,uncompleted_required=gaps,remaining=deferred),ensure_ascii=False,indent=2)+'\n')
    lines=['# 留给发布复审','','本轮必跑项目按最终 DAT 摘要核对。完整 144 项由用户明确留给发布复审；本轮替换为 48 项测试卡缩减版。','','| 项目 | 入口 | 理由 |','|---|---|---|']
    for g in deferred:lines.append('| '+g['job']+' | '+g['script']+' '+ ' '.join(g['args'])+' | '+g['reason']+' |')
    if gaps:
        lines+=['','当前还有本轮未完成项，报告必须保持有缺陷：','']
        for g in gaps:lines.append('- '+g['job']+'：'+g['reason'])
    (HERE/'FINAL_GAPS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(required=len(planned),passed=passed,uncompleted_required=len(gaps),release_review=len(deferred),legacy_groups=len(result))))
if __name__=='__main__':main()
