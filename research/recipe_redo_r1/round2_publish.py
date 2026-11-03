"""Publish g155c comparisons atomically and preserve previously consumed records."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import io
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from publication import atomic_bytes,save_record
import g155c_baseline as base

HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'
UNITS=('mount-a12','a12-50','a12-28')
PRIORITY={'a12-50':(20,21,22,24,26),'mount-a12':(20,22,23,24,26)}


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def rel(path):return str(Path(path).relative_to(HERE))
def f(value):return '—' if value is None else f'{value:.3f}'


def row_cost(record,unit,name):
    D=base.decoder();pools=[set() for _ in D.LENGTHS]
    for items in base.records().values():
        for item in items:
            content=(HERE/item['record_file']).read_bytes()
            for kind,offset in zip(D.KINDS,D.OFFSETS):pools[kind].add(content[offset:offset+D.LENGTHS[kind]])
    added=[set() for _ in D.LENGTHS];content=Path(record).read_bytes()
    for kind,offset in zip(D.KINDS,D.OFFSETS):
        value=content[offset:offset+D.LENGTHS[kind]]
        if value not in pools[kind]:added[kind].add(value)
    before=base.table_cost({})
    existing=next(r for r in base.records()[unit] if r['name']==name)
    after=before if content==(HERE/existing['record_file']).read_bytes() else base.table_cost({(unit,name):Path(record)})
    return dict(row_sizes=list(D.LENGTHS),new_unique_rows_by_size=list(map(len,added)),
        new_unique_rows=sum(map(len,added)),new_unique_payload_bytes=sum(len(a)*n for a,n in zip(added,D.LENGTHS)),
        descriptor_delta=after['look_descriptors']-before['look_descriptors'],
        net_repacked_table_delta_bytes=after['data_table_bytes']-before['data_table_bytes'],
        comparison='New rows versus all g155c rows; net delta also removes unused rows and includes descriptor splits')


def reason(row):
    if row['index']==30:return 'Native04 retained byte for byte'
    failures=[]
    if not row['flags_compatible']:failures.append('flags differ from the actual referenced base slot; needs a compatible refit')
    if row['full_exact_confirmation_status']!='PASS':failures.append('full-start exact '+row['full_exact_confirmation_status'])
    if not row['quality']['passes']:failures.append('g155c-relative fixture guard fails')
    if row['scene_regression_review']:failures.append('whole-scene median/P95 regresses')
    if not row['basic_quality_recommendation']:failures.append('primary median/P95 gain gate fails')
    if not row['published']:failures.append('no g155c slot; research target is not a published replacement')
    return '; '.join(failures) or 'All computer-model, exact, scene and flags gates pass'


def table(headers,rows):
    return ['', '| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+[
        '| '+' | '.join(str(x).replace('|','／') for x in r)+' |' for r in rows]


def write_csv(name,rows):
    if not rows:return
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows)
    atomic_bytes(HERE/name,stream.getvalue().encode())


def score_tables(rows):
    scores=[];scenes=[];photos=[]
    photo_info={u:read(LOCAL/'inputs'/u/'photos.json') for u in UNITS}
    new7=HERE/read(HERE/'new7_raw_holdout_summary_L1.json')['artifact_root']/'photos.json'
    new7_info=read(new7)
    for row in rows:
        data=read(HERE/row['scores_receipt'])
        common=dict(label='电脑预测，28mm仅合成',unit=row['unit'],index=row['index'],name=row['name'],
            comparison_baseline=data['comparison_baseline_kind'],record_sha256=row['record_sha256'])
        for group,value in data['scores'].items():
            if value is None:continue
            scores.append(dict(**common,group=group,current_percent=value['current']['similarity_percent'],
                candidate_percent=value['candidate']['similarity_percent'],gain_pp=data['gain_over_current_pp'][group],
                current_median_de00=value['current']['de00']['median'],candidate_median_de00=value['candidate']['de00']['median'],
                current_p95_de00=value['current']['de00']['p95'],candidate_p95_de00=value['candidate']['de00']['p95'],
                candidate_training_objective=row['objective'],full_exact_gate=row['full_exact_confirmation_status']))
        for group,items in data['per_scene'].items():
            for scene,value in items.items():
                scenes.append(dict(**common,group=group,scene=scene,current_percent=value['current']['similarity_percent'],
                    candidate_percent=value['candidate']['similarity_percent'],
                    current_median_de00=value['current']['de00']['median'],candidate_median_de00=value['candidate']['de00']['median'],
                    current_p95_de00=value['current']['de00']['p95'],candidate_p95_de00=value['candidate']['de00']['p95']))
        for group,items in data['per_photo'].items():
            for value in items:
                info=(new7_info if group=='photo_new7_RAW_diagnostic' else photo_info[row['unit']])[value['photo_id']]
                photos.append(dict(**common,group=group,photo_id=value['photo_id'],current_percent=value['current']['similarity_percent'],
                    candidate_percent=value['candidate']['similarity_percent'],
                    RAW_file=info['path'],RAW_sha256=info['sha256'],ISO=info['iso'],scene=info['scene_group'],
                    current_median_de00=value['current']['de00']['median'],candidate_median_de00=value['candidate']['de00']['median'],
                    current_p95_de00=value['current']['de00']['p95'],candidate_p95_de00=value['candidate']['de00']['p95']))
    write_csv('scores.csv',scores);write_csv('scene_scores.csv',scenes);write_csv('photo_scores.csv',photos)


def main():
    state=read(LOCAL/'round2_state.json');prior=read(HERE/state['checkpoint']/'candidate_registry.json')
    prior_rows={(r['unit'],r['index']):r for r in prior['profiles']}
    rows=[];variant_rows=[];changed=[];replacements={};pending=[]
    for unit in UNITS:
        receipt=read(LOCAL/'round2_replay'/unit/'receipt.json');assert receipt['status']=='PASS' and receipt['count']==35
        for index in range(35):
            source=LOCAL/'round2_replay'/unit/f'{index:02d}.json';data=read(source)
            old=prior_rows[unit,index]
            record=HERE/data['record_file'];content=record.read_bytes();assert sha(record)==data['record_sha256']
            target=save_record(LOCAL/'final_candidates'/unit/f'{index:02d}.record552',content)
            row={k:v for k,v in data.items() if k not in ('per_scene','per_photo','compatible_variants','scores')}
            row.update(record_file=rel(target),selected_fit_record=data['record_file'],
                status='refitted' if read(HERE/data['fit_receipt'])['origin']=='refit' else 'retained_current',
                main_level=0 if index in PRIORITY.get(unit,()) else old['main_level'],
                record_encoding_level=read(HERE/data['fit_receipt']).get('record_encoding_level',read(HERE/data['fit_receipt'])['level']),
                objective=data['training_objective'],training_only_selection=True,
                comparison_baseline_kind=data['comparison_baseline_kind'],
                current_record_sha256=data['baseline']['record_sha256'],
                current_record_file=data['baseline']['record_file'],
                published_baseline='g155c',scores_receipt=rel(source),scores_receipt_sha256=sha(source),
                S_mode='04 Standard',all_552_bytes_rebuilt=True,all_scores_recomputed=True,
                photo_holdout_available=unit!='a12-28',holdout_kind='synthetic_only' if unit=='a12-28' else 'whole_scene_RAW_computer_render',
                no_camera_acceptance=True,no_DAT_built=True,backend='exact_TRF_SVD',
                accepted_for_research=data['accepted'],accepted_for_existing_g155c_slot=data['accepted'] and data['published'])
            if index==30:row['recommendation']='keep_native04'
            elif row['accepted_for_existing_g155c_slot']:row['recommendation']='replace_candidate'
            elif not data['published']:row['recommendation']='do_not_add'
            elif data['full_exact_confirmation_status']=='PENDING' and data['basic_quality_recommendation']:
                row['recommendation']='pending_full_start_exact'
            elif data['full_exact_confirmation_status']=='REVIEW':row['recommendation']='review_exact_holdout'
            elif not data['flags_compatible']:row['recommendation']='needs_shared_compatible_refit'
            else:row['recommendation']='keep_current_after_review'
            row['build_block_reason']=reason(data)
            if unit=='mount-a12' and index in (0,1):
                row['mount_reexamination']=next(r for r in read(LOCAL/'mount_reexamination/decisions.json')['profiles'] if r['index']==index)
                row['deployment_action']='do_not_add_no_g155c_slot'
            if row['accepted_for_existing_g155c_slot']:
                replacements[unit,row['name']]=target
                row['unique_row_cost']=row_cost(target,unit,row['name'])
            for variant in data.get('compatible_variants',[]):
                variant={k:v for k,v in variant.items() if k not in ('per_scene','per_photo','scores')}
                variant['unique_row_cost']=row_cost(HERE/variant['record_file'],unit,row['name'])
                variant_rows.append(variant)
            before=state['baseline_record_shas'][f'{unit}/{index:02d}']
            if before['record_sha256']!=row['record_sha256']:
                allowed=unit=='a12-28' or (unit=='mount-a12' and index in (0,1)) or index in PRIORITY.get(unit,())
                assert allowed,('Unexpected record mutation',unit,index)
                changed.append(dict(unit=unit,index=index,name=row['name'],before_record_file=before['record_file'],
                    before_sha256=before['record_sha256'],after_record_file=row['record_file'],after_sha256=row['record_sha256']))
            if row['recommendation'] in ('pending_full_start_exact','review_exact_holdout'):
                pending.append({k:row[k] for k in ('unit','index','name','recommendation','record_file','record_sha256','fit_receipt','build_block_reason')})
            dump(target.with_name(target.stem+'.round2.json'),dict(**row,record_content_hex=content.hex(),
                parameters=read(HERE/row['fit_receipt']).get('parameters')))
            rows.append(row)
    for key,value in state['frozen_build38'].items():
        assert sha(HERE/value['record_file'])==value['record_sha256'],('Old build input changed',key)
    assert len(rows)==105
    stability=dict(label='记录一致性',changed_records=changed,changed_count=len(changed),unchanged_count=105-len(changed),
        frozen_build38_old_paths_and_bytes_preserved=True,baseline_registry_sha256=state['baseline_candidate_registry_sha256'])
    dump(HERE/'record_sha_changes.json',stability)
    dump(HERE/'pending_exact_confirmations.json',dict(label='电脑预测，28mm仅合成',profiles=pending,pending_profiles=len(pending),not_in_DAT_build_list=True))
    dump(HERE/'compatible_look_candidates.json',dict(label='电脑预测',profiles=variant_rows,
        default_policy=read(LOCAL/'compat_g155c/deployment_policy.json'),
        each_family_selected_by_integer_training_objective_only=True,
        other_family_or_older_candidate_not_substituted_after_holdout_failure=True))
    capacity=base.table_cost(replacements)
    mount50={key:path for key,path in replacements.items() if key[0]!='a12-28'}
    per_unit={unit:base.table_cost({key:path for key,path in replacements.items() if key[0]==unit}) for unit in UNITS}
    dump(HERE/'g155c_row_budget.json',dict(label='静态行数和容量预测',baseline_minimal_repacked=base.table_cost({}),
        selected_existing_slot_replacements=capacity,predicted_not_built=True,
        MOUNT_50mm_only=base.table_cost(mount50),each_unit_alone=per_unit,
        per_candidate=[dict(unit=r['unit'],index=r['index'],name=r['name'],**r['unique_row_cost']) for r in rows if r.get('unique_row_cost')]))
    registry=dict(label='电脑预测，28mm仅合成',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        profiles=rows,completed_main_profiles=105,expected_main_profiles=105,full_main_matrix_complete=True,
        published_baseline='firmware/package_v310_g155c',published_looks_per_unit=10,
        full_start_28_confirmations_completed=32,shared_compatible_fits_full_confirmed=30,
        baseline_manifest_sha256=sha(LOCAL/'g155c_baseline/manifest.json'),
        prior_registry_sha256=state['baseline_candidate_registry_sha256'],
        record_sha_changes_sha256=sha(HERE/'record_sha_changes.json'),frozen_build38_old_paths_and_bytes_preserved=True,
        compatible_look_candidates_sha256=sha(HERE/'compatible_look_candidates.json'),
        row_budget_sha256=sha(HERE/'g155c_row_budget.json'),
        pending_exact_confirmations_sha256=sha(HERE/'pending_exact_confirmations.json'),
        all_build_candidates_exact_confirmed=True,no_DAT_built=True,
        probe2_response_incorporated=False,probe2_status='No field-analysis handoff received; no measured-response update invented',
        MOUNT_L1_model_scope='Discrete node16 +2 grey response only; other nodes, gaps and hues remain model extrapolation',
        by_unit={u:dict(completed=35,accepted_existing_slots=sum(r['accepted_for_existing_g155c_slot'] for r in rows if r['unit']==u)) for u in UNITS})
    dump(HERE/'candidate_registry.json',registry)
    lists=dict(label='电脑预测，28mm仅合成',created_utc=registry['created_utc'],candidate_registry_sha256=sha(HERE/'candidate_registry.json'),
        published_baseline='g155c actual ten Looks per unit',units={},
        capacity_prediction=capacity,not_a_DAT_or_host_acceptance=True,
        package_generation_gate_not_resolved_by_recipe_fitting=True)
    for unit in UNITS:
        own=[r for r in rows if r['unit']==unit]
        def brief(r):return {k:r.get(k) for k in ('unit','index','name','recommendation','record_file','record_sha256','fit_receipt',
            'flags','base05_flags','look_base_slot','required_base_flags','requires_companion_builtin',
            'unique_row_cost','full_exact_confirmation_status','build_block_reason','published')}
        lists['units'][unit]=dict(accepted=[brief(r) for r in own if r['accepted_for_existing_g155c_slot']],
            not_replaced=[brief(r) for r in own if not r['accepted_for_existing_g155c_slot']],
            new_targets=[brief(r) for r in own if not r['published']])
    dump(HERE/'dat_candidate_lists.json',lists)
    score_tables(rows)
    write_report(rows,variant_rows,capacity,stability)
    print('ROUND2 PUBLISHED',len(rows),'profiles;',len(replacements),'existing-slot candidates;',len(changed),'changed records',flush=True)


def write_report(rows,variants,capacity,stability):
    checkpoint=HERE/read(LOCAL/'round2_state.json')['checkpoint']
    previous=(checkpoint/'REPORT.md').read_text()
    atomic_bytes(HERE/'REPORT_PREVIOUS_MODEL.md',previous.encode())
    accepted=[r for r in rows if r['accepted_for_existing_g155c_slot']]
    lines=['电脑预测：新7张04中央60%区，冻结MOUNT映射中位ΔE00为0.785，比50mm迁移下降16.60%；中央重标定留出回退，保留原输入。',
        f'以g155c实际10个Looks为发布基线；105项已重新比较，当前{len(accepted)}条现有槽位候选通过模型门；28mm仅合成。',
        f'10项默认候选先按最多新增1条数据行的约束选最低整数训练损失，再过留出门；完整共享模型另列，不按照片成绩换旧解。',
        '需要机主素材：MOUNT多节点/负向探针的现场分析、更多整场景原厂04；28mm仍缺可用RAW。',
        '本轮不构建DAT；格式和主分配只作静态核算，代数、主机运行与相机验收由后续构建任务负责。',
        '', '## 发布基线与记录身份','',
        '发布基线为firmware/package_v310_g155c，release SHA为69fa85104fcb449e613950bb58c802b9b64464769ae524fe3f7303e06093c2ad。每单元实际10个Looks，逐条由DAT解码并对照g156的before map；原生04的552 B与既有模型输入相同。g154 Looks18只保留历史研究身份。',
        f'本轮改动{stability["changed_count"]}条研究记录，另{stability["unchanged_count"]}条SHA不变。上一轮供构建读取的38条原路径与字节全部保留；新内容使用SHA命名的文件。差异收据见record_sha_changes.json。',
        '', '## 10项共享曲线重拟合，电脑预测','',
        '三组均使用flags=1和S=04。free允许共享曲线、Y系数与对称扇区重拟合；reuse_tone_matrix保留g155c横轴、曲线和完整矩阵，只拟合扇区；reuse_hue_matrix保留横轴、扇区和完整矩阵，只拟合共享曲线。后两组最多新增一条96 B或33 B行。模板原字节在量化后保留，避免负零或矩阵舍入造成多余行。',
        '默认部署策略在两组紧凑模型间只按整数训练损失选型，不读照片分数。之后应用逐场景中位/P95、MOUNT七张自然RAW整组、exact的0.1百分点及None绝对误差门；失败就保留g155c行，不改挑另一组或旧解。其他模型作为单独声明的候选对照保留。',
        '每组先迭代，再由exact重跑全部原声明起点、父候选、已有可行整数解及横轴，并把迭代整数解作为额外起点和可保留状态。所有选择都用保存后解码的整数训练目标；记录、预测、全部夹具及门控均独立复算。']
    vrows=[]
    for v in variants:
        doc=read(HERE/v['fit_receipt']);s=doc['scores'];p=s['photo_iso200'];gain=p['candidate']['similarity_percent']-p['current']['similarity_percent'] if p['candidate']['similarity_percent'] is not None else None
        owner=next(r for r in rows if (r['unit'],r['index'])==(v['unit'],v['index']))
        chosen=owner['record_sha256']==v['record_sha256'] and owner['compat_family']==v['compat_family']
        vrows.append([v['unit']+' '+v['name'],v['compat_family']+('，默认' if chosen else ''),
            f(p['current']['similarity_percent']),f(p['candidate']['similarity_percent']),f(gain),
            v['full_exact_confirmation_status'],'、'.join(v['scene_regression_review']) or '通过',
            str(v['unique_row_cost']['new_unique_rows_by_size']), '可供构建验证' if v['accepted'] else '保留当前'])
    lines+=table(['单元/Look','模型','g155c照片%','候选照片%','提升pp','exact门','场景门','新增行62/33/96/56','该模型结论'],vrows)
    exact_rows=[]
    for row in accepted:
        proof=row['exact_confirmation'];group=row['primary_score_group']
        exact_rows.append([row['unit']+' '+row['name'],
            f(proof['source_scores']['train']['candidate']['similarity_percent']),
            f(proof['exact_scores']['train']['candidate']['similarity_percent']),
            f(proof['source_scores'][group]['candidate']['similarity_percent']),
            f(proof['exact_scores'][group]['candidate']['similarity_percent']),
            proof['exact_confirmation_solver_attempts']])
    lines+=table(['构建候选，电脑预测','确认前训练%','完整exact训练%','确认前主要留出%','完整exact主要留出%','实际起点数'],exact_rows)
    lines += ['', '完整训练、合成、ISO200照片、其他ISO诊断、中位/P95和逐照片结果在local/round2_replay；compatible_look_candidates.json绑定30个精确记录、SHA和full-start exact证据。共享曲线不依赖未验收的独立RGB幅度修正。',
        '', '## 容量核算','',
        '新增唯一行按实际g155c全部行池逐字节比较，计数包含跨角色和跨单元复用。净字节另计未用行消失、四字节对齐和Look描述符按单元拆分。仅核算，没有序列化或构建DAT。原g155c保留表容量5588 B；最小去重重排是4992 B，两者不能混作同一个基线。']
    lines+=table(['包','预测DAT B','预测主分配B','上限B','超出B'],[[p['profile'],p['predicted_DAT_bytes'],p['predicted_main_allocation_bytes'],p['limit'],p['over_limit_bytes']] for p in capacity['packages']])
    two=read(HERE/'g155c_row_budget.json')['MOUNT_50mm_only']
    lines+=table(['仅MOUNT和50mm候选','预测DAT B','预测主分配B','上限B','超出B'],[[p['profile'],p['predicted_DAT_bytes'],p['predicted_main_allocation_bytes'],p['limit'],p['over_limit_bytes']] for p in two['packages']])
    lines += [f'',f'当前现有槽位候选合并后的数据表为{capacity["data_table_bytes"]} B，Look描述符{capacity["look_descriptors"]}个。逐条新增行数、负载字节与单项净表差见g155c_row_budget.json。此结果不关闭g156发现的代数检查或实际主机运行问题。',
        '', '## 全部105项，电脑预测','',
        '没有g155c槽位的研究目标使用该单元base05作明确的离线参考，不能把差值说成相对已发布Look的提升；仍保留全部目标，没有删除Looks。10项彩色Looks引用05，必须flags=1。Tri-X引用03，50mm已确认的03和Tri-X均为flags=7，必须成组采用或一起保留g155c；此依赖已写进清单，原记录SHA不变。任何与实际引用base不一致的Look及会破坏既有Looks的05候选均不列替换。原C的fx_area_valid按e[0]选择base并比较d[1]与e[1]，证据是g156冻结的fx_pool.c第69至72行。']
    full=[]
    for r in rows:
        d=read(HERE/r['scores_receipt']);s=d['scores'];g=r['primary_score_group'];cur=s[g]['current']['similarity_percent'];candidate=s[g]['candidate']['similarity_percent']
        full.append([r['unit'],r['name'],'g155c' if r['published'] else 'base05离线参考',
            f(s['train']['candidate']['similarity_percent']),f(s['synthetic']['candidate']['similarity_percent']),
            '仅合成' if r['unit']=='a12-28' else f(candidate),f(d['gain_over_current_pp'][g]),
            r['flags'],r['full_exact_confirmation_status'],r['recommendation']])
    lines+=table(['单元','配方','比较基线','训练%','合成%','照片%','主要提升pp','flags','全起点exact','处理'],full)
    lines+=['','## 28mm与MOUNT两项复核','',
        '28mm的32项待确认均按原计划独立执行全起点exact；每项是否通过0.1门与当前flags兼容性分开记录。只有合成预测，没有照片或相机实测成绩。待确认与失败项见pending_exact_confirmations.json。',
        'MOUNT Agfa LeBox与千禧回声A增加至每起点1000预算，仍相对原固定照片参考下降1.045151与0.124622百分点，均超过0.1门。两者不在g155c实际10个Looks内，决定不新增；原先“保留发布行”的说法已更正为保留历史g154参考，不冒称g155c有该槽位。证据见MOUNT_REEXAMINATION.md。',
        '', '## 实测范围、素材与方法','',
        'MOUNT节点16的+2只有密集灰阶已采离散点得到复现，RAW_WB端点约为R585–752、G578–758、B590–773；点间空档、其他色相、其他节点与完整幅度继续标为模型外推。分段线性是工作假设，未加入统一RGB增益或色度修正。probe2现场分析尚未交接，未虚构负向或节点8/19的响应系数。',
        'R8051894–1900由机主在2026-11-03口头确认原厂04、拍摄间不切配方或微调；白平衡为日光预设。继续作为整组独立留出，不混回既定训练目标。1895小色卡按普通场景。镜头为35mm f/2七片式Mandler设计复刻手动M口；探针f/5.6，自然七张光圈未知。采样避开边缘；既有中心区域标定、镜头暗角及色偏诊断见LENS_SPATIAL.md和素材身份表。',
        '逐单元04标定、日期/光源整场景划分、数据清单、GR目标限制及05/06先前证据保留在REPORT_PREVIOUS_MODEL.md；其中历史18个发布Looks与旧构建清单已由本报告和新registry替代。此轮没有改变标定系数，不以七张新照片的分数冒充重新训练的标定改善。',
        '', '## 求解器、复跑和封存','',
        '本轮共享模型全部实际运行SciPy TRF/SVD。色相罚项直接调用least_squares；紧凑模型在活跃参数列上解精确子问题。L0/L1没有调用guarded_normal普通分解，因此不借用1530项门为本适配器背书。每个fit回执绑定实际分支、起点清单、停止条件与代码快照；有限预算不代表全局最优。',
        '批次清单、源版本和复跑步骤见RERUN_ROUND2.md；最终SHA256SUMS覆盖脚本、报告、输入与本地候选。全部派生数据只在被git忽略的local/，最终逐文件git check-ignore -v核对。没有访问卡、机主Studio或修改上游工具。当前仍在运行阶段，Scratch尚未最终清理。',
        '', '可交后续DAT构建验证的现有槽位候选如下。所有分数均为电脑预测，28mm仅合成。']
    for unit in UNITS:lines.append(unit+'：'+('、'.join(r['name'] for r in accepted if r['unit']==unit) or '无'))
    lines+=['需要的机主素材：MOUNT probe2现场分析及后续多节点响应、更多原厂04整场景；28mm原厂04 RAW+JPG。清理状态见cleanup.json。']
    atomic_bytes(HERE/'REPORT.md',('\n'.join(lines)+'\n').encode())


if __name__=='__main__':main()
