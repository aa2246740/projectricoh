"""Attach conditional MOUNT refinements while retaining the validated main rows."""
import collections
import datetime
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from publication import atomic_bytes

HERE=Path(__file__).resolve().parent
OUT=HERE/'local/probe2_local_response'


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def f(value):return '—' if value is None else f'{value:.4f}'


def main():
    profiles=[];verified={}
    for p in (OUT/'verification_batches').glob('*.json'):
        for row in read(p)['profiles']:verified[row['index']]=row
    assert set(verified)==set(range(35))
    validation=read(OUT/'calibration_validation.json')
    phase=read(OUT/'06_output_phase_sensitivity.json')
    calibration_globally_accepted=False
    for index in range(35):
        root=OUT/'fits'/f'{index:02d}';doc=read(root/'exact.json');proof=verified[index]
        record=root/'exact.record552';assert sha(record)==doc['record_sha256']==proof['record_sha256']
        skipped=doc.get('no_independent_curve_increment',False)
        local=root/'verification.json'
        checks=read(local) if local.exists() else proof
        row=dict(label='电脑预测，条件局部导数模型，完整色彩与量化相位仍有误差',unit='mount-a12',index=index,name=doc['name'],
            record_file=str(record.relative_to(HERE)),record_sha256=doc['record_sha256'],flags=doc['flags'],
            anchor_file=doc['anchor_file'],anchor_sha256=doc['anchor_sha256'],
            fit_receipt=str((root/'exact.json').relative_to(HERE)),fit_sha256=sha(root/'exact.json'),
            retained_shared_or_native=skipped,confirmation_kind='unchanged record, no independent-curve fit' if skipped else 'full-start exact in the declared signed local domain',
            full_exact_confirmation_status=checks['exact_gate_status'],
            calibration_sha256=sha(OUT/'calibration.json'),policy_sha256=sha(OUT/'policy.json'),
            full_colour_quantitative_acceptance=False,model_error_not_removed=True,
            source_template='frozen previously selected L1 recipe; only signed nodes8/16/19 may change',
            accepted_into_main_DAT_list=False,
            non_adoption_reason='Heldout colour Cb and extra negative colours regress under the transferred local derivative model; retain main records and expose this conditional branch')
        if not skipped:
            scores=doc['scores'];before=read(root/'iterate.json')
            ranges={}
            for group,value in scores.items():
                if not value:continue
                allvalues=[value]+[u['scores'][group] for u in doc['uncertainty'].values() if u['scores'].get(group)]
                finite=[v['candidate']['similarity_percent'] for v in allvalues if v['candidate']['similarity_percent'] is not None]
                ranges[group]=dict(candidate_min_percent=min(finite) if finite else None,candidate_max_percent=max(finite) if finite else None,
                    scope='ROI35/50/65 and nearest-A derivative calibration; not a confidence interval or quantisation bound')
            row.update(objective=doc['objective'],anchor_objective=doc['anchor_objective'],scores=scores,
                iteration_scores=before['scores'],scene_regression_review=doc['scene_regression_review'],
                exact_gate_status=checks['exact_gate_status'],uncertainty_ranges=ranges,
                quality=doc['quality'],record_changed=doc['record_sha256']!=doc['anchor_sha256'],
                start_manifest=doc['start_manifest'],start_manifest_sha256=doc['start_manifest_sha256'],
                solver_attempts=len(doc['solver_attempts']),all_552_bytes_rebuilt=True,
                all_scores_and_fixtures_rebuilt=True,
                verification_receipt=str(local.relative_to(HERE)),verification_sha256=sha(local))
        profiles.append(row)
    summary=dict(label='电脑预测，MOUNT条件局部响应重拟合',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        profiles=profiles,total_profiles=35,refinement_flows=sum(not p['retained_shared_or_native'] for p in profiles),
        retained_shared_or_native=sum(p['retained_shared_or_native'] for p in profiles),
        changed_records=sum(p.get('record_changed',False) for p in profiles),
        exact_review_profiles=[p['index'] for p in profiles if p['full_exact_confirmation_status']=='REVIEW'],
        calibration_validation=validation,calibration_sha256=sha(OUT/'calibration.json'),
        output_phase_06={g:{k:v for k,v in values.items() if k!='branches'} for g,values in phase['groups'].items()},
        output_phase_06_receipt='local/probe2_local_response/06_output_phase_sensitivity.json',
        output_phase_06_sha256=sha(OUT/'06_output_phase_sensitivity.json'),
        source_manifest_sha256=sha(OUT/'source_manifest.json'),model_policy_sha256=sha(OUT/'policy.json'),
        signed_local_model_is_not_full_curve_calibration=True,
        complete_hardware_response_model_accepted=False,main_record_selection_unchanged=True,
        source_field_report='research/probe_pack_r2/FIELD_PROBE2.md',
        no_global_channel_gain=True,no_fixed_chroma_matrix=True,no_DAT_built=True)
    dump(HERE/'probe2_refit_registry.json',summary)
    registry=read(HERE/'candidate_registry.json')
    before={f'{r["unit"]}/{r["index"]}':r['record_sha256'] for r in registry['profiles']}
    registry.update(probe2_response_incorporated=True,probe2_applied_to_main_admission_model=False,
        probe2_status='35 MOUNT profiles covered in the conditional local derivative branch; colour holdout failures retained; main record choices unchanged',
        probe2_refit_registry_sha256=sha(HERE/'probe2_refit_registry.json'),
        MOUNT_L1_model_scope='Node8/19 +2 and node16 -2 controls repeat; local signed Y/Cb/Cr derivative transfer remains conditional, no continuous full-colour range accepted')
    lookup={p['index']:p for p in profiles}
    for row in registry['profiles']:
        if row['unit']=='mount-a12':
            p=lookup[row['index']]
            row['probe2_conditional_refit']={k:p.get(k) for k in ('record_file','record_sha256','fit_receipt','fit_sha256',
                'confirmation_kind','full_exact_confirmation_status','model_error_not_removed','accepted_into_main_DAT_list','non_adoption_reason')}
    assert before=={f'{r["unit"]}/{r["index"]}':r['record_sha256'] for r in registry['profiles']}
    dump(HERE/'candidate_registry.json',registry)
    lists=read(HERE/'dat_candidate_lists.json');lists.update(candidate_registry_sha256=sha(HERE/'candidate_registry.json'),
        probe2_conditional_registry_sha256=sha(HERE/'probe2_refit_registry.json'),probe2_conditional_records_in_accepted_list=False)
    dump(HERE/'dat_candidate_lists.json',lists)
    report=HERE/'REPORT.md';text=report.read_text()
    text=text.replace('MOUNT多节点/负向探针的现场分析、更多整场景原厂04','MOUNT同场节点16正负定标、更多整场景原厂04')
    text=text.replace('probe2现场分析尚未交接，未虚构负向或节点8/19的响应系数。',
        'probe2现场分析已冻结并用于下述条件局部导数重拟合；仍未把局部导数当成完整色彩响应。')
    marker='\n## probe2局部导数重拟合与剩余模型误差\n'
    if marker in text:text=text.split(marker)[0]
    lines=[marker,'',
        f'节点8/19的+2及节点16的−2都有局部响应。35个MOUNT档案中，{summary["refinement_flows"]}项按测得方向做最多2码的局部重拟合，并由完整原声明/父候选投影起点重新跑exact；{summary["retained_shared_or_native"]}项原生或共享控制记录逐字节保留。{summary["changed_records"]}条局部分支记录改变，主registry中原有105条记录SHA均未因此改变。',
        '校准按输入亮度、色相、节点与符号分别估计Y/Cb/Cr导数，固定分段线性工作模型；节点8/19只允许正增量，16只允许负增量，不借用非同场资料强设正负对称。其它节点、完整矩阵、扇区与横轴冻结。原曲线距离探针A的差异、未采色相、节点间空档和量化相位仍是模型误差。没有一个连续全颜色范围得到定量验收。',
        '主灰阶/彩块校准使用1935/1936/1937及1947/1948/1949，第二次P2扰动1951/1952/1953整帧留出；1940/1941/1942不同页面负向只作诊断。1944–1946继续unknown，不作04或拟合输入。21组照片42个原文件SHA已核对，镜头为机主给出的35mm f/2七片式Mandler复刻，实际f/5.6，EXIF光圈0保留为未报告。',
        '', '| probe2验证，输出码RMSE | 原Y/Cb/Cr | 局部校准Y/Cb/Cr |','| --- | --- | --- |']
    for v in validation['evaluations']:
        lines.append('| '+v['role']+' '+v['colour']+' | '+' / '.join(f(x) for x in v['original_component_RMSE'])+' | '+' / '.join(f(x) for x in v['calibrated_component_RMSE'])+' |')
    lines += ['', '灰阶重复组改善，但彩块留出Cb与不同页面负向彩块仍有回退，因此此分支不替换主DAT准入模型和现有主候选。肤色Cb缺口、蓝块Cr反号保留原始观测与旧预测；没有通过一个RGB倍率或固定色度矩阵把反例隐藏。分支中的完整记录、条件预测、原L1分数、三种ROI/最近A包络、exact起点与SHA见probe2_refit_registry.json及local/probe2_local_response。',
        '06的局部候选ISO200照片名义提升约0.0091百分点；16个输出量化假设下，增益从−0.0099至+0.0092百分点，方向不稳。该敏感性不模拟JPEG DCT/IDCT，也不命名真实ISP舍入算法。其余记录继续保留原128分支量化证据与probe2形状/输入分布诊断，均不等于量化相位已定。',
        '', '实测范围只包括下列离散灰点，端点间空档和其他色相仍不算定量验收。',
        '', '| 通道/节点 | RAW_WB受激灰点端点 | 首帧峰两侧灰点数 |','| --- | --- | --- |']
    for sample in read(OUT/'evidence/recipe_redo_handoff.json')['sampled_gray_ranges']:
        bounds=sample['active_raw_wb_range']
        lines.append('| '+sample['channel']+'/'+str(sample['node'])+' | '+(' 至 '.join(f(x) for x in bounds) if bounds else '—')+' | '+str(sample['left_points'])+' / '+str(sample['right_points'])+' |')
    lines += [
        '', '| MOUNT配方，电脑预测 | 原L1照片% | 局部迭代照片% | 完整exact照片% | ROI/A包络% | 0.1/None门 | 场景门 |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for row in profiles:
        if row['retained_shared_or_native']:
            lines.append('| '+row['name']+' | 共享或原生保留 | — | — | — | 不改记录 | — |');continue
        group='photo_iso200';s=row['scores'][group];r=row['uncertainty_ranges'][group]
        lines.append('| '+' | '.join([row['name'],f(s['anchor']['similarity_percent']),
            f(row['iteration_scores'][group]['candidate']['similarity_percent']),f(s['candidate']['similarity_percent']),
            f(r['candidate_min_percent'])+' 至 '+f(r['candidate_max_percent']),row['full_exact_confirmation_status'],
            '通过' if not row['scene_regression_review'] else '回退'])+' |')
    lines += ['', 'Agfa LeBox与千禧回声A的附加门仍对第一次通过候选的固定参考，未把先前失败的训练最小值当成新的门基准。两项仍不新增，且本来不在g155c的10个Looks内。',
        '', '本轮可交DAT构建验证的主清单仍为dat_candidate_lists.json的accepted；probe2条件分支没有自动混入。需要机主素材：同场A→R+16→R−16→G+16→G−16→B+16→B−16→A最少8张，及更多04整场景；28mm原厂04 RAW+JPG。未构建DAT，最终清理状态见cleanup.json。']
    atomic_bytes(report,(text+'\n'.join(lines)+'\n').encode())
    print('PROBE2 PUBLISHED35',summary['refinement_flows'],'local exact flows;',summary['changed_records'],'changed conditional records; main records unchanged',flush=True)


if __name__=='__main__':main()
