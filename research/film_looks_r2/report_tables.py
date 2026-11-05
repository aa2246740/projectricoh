"""Aggregate report tables from private saved measurements, using the standard library."""
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'
UNITS=('a12-50','a12-28','mount-a12')
LABELS={'a12-50':'50mm','a12-28':'28mm','mount-a12':'MOUNT'}


def read(path):return json.loads(Path(path).read_text())
def f(x,n=2):return '—' if x is None else f'{x:.{n}f}'
def med(values):
    v=[x for x in values if x is not None]
    return statistics.median(v) if v else None


def absolute_and_routes(catalog,results):
    out=['## 绝对余差与每片路线对照','',
         '绝对余差表的每格为满配中位 / P95 ΔE00；位置差表与此表共用相同照片和同一场景光目标。量化未全过的配方仍列入研究库，不能当成默认安装候选。','',
         '| 胶片 | 50mm ΔE00 | 28mm ΔE00 | MOUNT ΔE00 | 稳健准入单元数 |',
         '| --- | ---: | ---: | ---: | ---: |']
    for film in catalog['films']:
        cells=[];admitted=0
        for unit in UNITS:
            doc=results.get((film['ordinal'],unit))
            if doc is None:cells.append('—');continue
            score=doc['routes'][doc['selected_route']]['scores']['photo_iso200']['de00']
            cells.append(f(score['median'])+' / '+f(score['p95']))
            admitted+=bool(doc['phase']=='final' and doc['quantization_passes']==128 and
                           doc['training_improved_vs_stock04'] and doc['primary_photo_improved_vs_baseline'])
        out.append('| '+film['name']+' | '+' | '.join(cells)+f' | {admitted}/3 |')
    out+=['','以下是满配三个拟合方法的逐单元照片分数。黑盒和结构代理都保留自己的整数训练优选；结构列不是“真实分层密度已取得”的证据。未入选的方法只作 guarded_normal 对照，表内 `E` 表示该路线另做了全起点 reference exact。','',
          '| 胶片 / 单元 | 黑盒 % | 结构代理 % | 敏感色加权 % | 训练选中 |',
          '| --- | ---: | ---: | ---: | --- |']
    short={'scene_rgb_matrix':'黑盒','scene_structure':'结构','scene_weighted':'加权'}
    for film in catalog['films']:
        for unit in UNITS:
            doc=results.get((film['ordinal'],unit))
            if doc is None:continue
            cells=[]
            for name in short:
                route=doc['routes'][name]
                cells.append(f(route['scores']['photo_iso200']['similarity_percent'])+(' E' if route['reference_exact_checked'] else ''))
            out.append('| '+film['name']+' / '+LABELS[unit]+' | '+' | '.join(cells)+' | '+short[doc['selected_route']]+' |')
    stalled=[]
    for doc in results.values():
        name=doc['selected_Look_route'];row=doc['routes'][name]
        if row.get('retained_unmodified_template'):
            stalled.append(doc['film']+' / '+LABELS[doc['unit']])
    out+=['','表中仍停留在模板、约 0% 的路线表示本轮未找到通过整数质量门的改进，不证明共享曲线的硬件上限就是 0。即使求解器报告收敛，量化后也可能全部被色相门拒绝；因此极大的位置差包含当前优化与护栏的影响。']
    if stalled:out.append('共享侧仍停留模板的项目：'+'、'.join(stalled)+'。')
    return out+['']


def controls(catalog,results):
    out=['## 旧 04 约定与曝光对照','',
         '以下七片把冻结 g157 原 Look 与新满配配方都对同一个场景光目标评分。差值可能同时包含胶片来源、曝光参考和拟合能力变化，不能全记作 L1 收益；隔离曲线能力应看前面的同目标 Look / 满配表。04 后叠加只作对照，不列入候选路线。','',
         '| 现有胶片 Look | 50mm 旧 / 新满配 % | 28mm 旧 / 新满配 % | MOUNT 旧 / 新满配 % |',
         '| --- | ---: | ---: | ---: |']
    for film in catalog['films']:
        if not film['existing_g157_film']:continue
        cells=[]
        for unit in UNITS:
            doc=results.get((film['ordinal'],unit))
            if doc is None:cells.append('—');continue
            old=doc['existing_baseline_scores']['photo_iso200']['similarity_percent']
            new=doc['routes'][doc['selected_route']]['scores']['photo_iso200']['similarity_percent']
            cells.append(f(old)+' / '+f(new))
        out.append('| '+film['name']+' | '+' | '.join(cells)+' |')
    out+=['','Tri-X 的旧目标已经采用场景光，且使用同一个 fotufilm LUT；它本轮的位置差不能归因于从 04 后移到场景光。黑白输出也可能受益于三个相机通道不同的亮度映射，不能仅凭输出无色度就推断共享曲线够用。旧 look_ceiling 的判断不包含本轮修正模型、三单元照片留出与量化协议，不能原样当成锁定名单。','',
          '下表直接比较三个“参考输出”与固定场景光参考的差异，单位是照片中位 ΔE00，再在 15 个 spektrafilm 档案间取中位。它衡量目标被改变多少，不是某条 GXR 拟合路线的成绩。中灰版保持输入 gain=1；作者默认 sRGB 版额外约 +1.53 EV。','',
          '| 单元 | 04 模型输出后叠加 | 场景 sRGB 有限域 | 作者默认增益 sRGB |',
          '| --- | ---: | ---: | ---: |']
    for unit in UNITS:
        cells=[]
        for key in ('want_jpeg','want_scene_srgb_control','want_scene_default_control'):
            values=[]
            for film in catalog['films']:
                doc=results.get((film['ordinal'],unit))
                if doc is not None and film['provider']=='spektrafilm' and key in doc['control_target_differences']:
                    values.append(doc['control_target_differences'][key]['target_difference_de00']['median'])
            cells.append(f(med(values)))
        out.append('| '+LABELS[unit]+' | '+' | '.join(cells)+' |')
    return out+['']


def locks_and_retention(summary):
    out=['## 锁定 Look 与 g157 去留','',
         '只推荐三个单元都通过统一位置规则、且两种位置在主留出均优于 04 的风格。两侧都停留在原厂模板时，即使差距为零也不能证明 Look 安全。下表是本轮固定目标下的选择；用户不能改锁定 Look。容量约 18 个是上限，空位保留。完整条目的彩色胶片由用户投票，研究排序不代替投票。','',
         '| 拟锁定 Look | 50mm Look % | 28mm Look % | MOUNT Look % | 最大满配收益 pp |',
         '| --- | ---: | ---: | ---: | ---: |']
    for item in summary['locked_Looks']:
        vals=[item['units'][u] for u in UNITS]
        out.append('| '+item['name']+' | '+' | '.join(f(v['Look']['similarity_percent']) for v in vals)+
                   ' | '+f(max(v['full_minus_Look_pp'] for v in vals))+' |')
    out+=['',f"共 {len(summary['locked_Looks'])} 个通过位置规则的锁定候选。该分类不替代 DAT、应用/恢复或相机验收。",'',
          '全部数字与创作风格的两种位置成绩如下，每格为 Look / 满配。量化列只表示位置判定稳定性，原表替换仍需发布门。','',
          '| 风格 | 50mm % | 28mm % | MOUNT % | Look 安全分支最低 | 位置判断 |',
          '| --- | ---: | ---: | ---: | ---: | --- |']
    for item in summary['styles']:
        cells=[]
        for unit in UNITS:
            row=item['units'].get(unit)
            cells.append('—' if row is None else f(row['Look']['similarity_percent'])+' / '+f(row['full']['similarity_percent']))
        quant=str(min(x['safe_branches'] for x in item['units'].values()))+'/128' if item['complete'] else '—'
        verdict=('待齐全' if not item['complete'] else '拟合未起效，位置 OPEN'
                 if not item.get('placement_evidence_sufficient',True) else 'Look 安全'
                 if item['numerical_Look_safe'] else '需要满配')
        out.append('| '+item['name']+' | '+' | '.join(cells)+' | '+quant+' | '+verdict+' |')
    out+=['',
          '| g157 现有 Look | g158 建议 | 依据 |','| --- | --- | --- |']
    actions={'replace_Alchemy_with_official_and_lock':'锁定官方 Acros，替换已交接','lock':'保留并锁定',
             'move_to_full_vote':'移入满配投票库','pending':'待该三单元对照齐全',
             'full_research_hold':'移入满配研究库，暂缓默认投票',
             'full_candidate_pending_release_gates':'满配候选，补准入后再投票'}
    reasons={'policy_full':'彩色胶片按机主策略使用满配','position_gap_or_quantization':'位置差或量化稳定性未通过',
             'all_units_Look_safe':'三单元 Look 安全','incomplete':'尚未给出结论',
             'full_quantization_or_gray_admission_failed':'满配主配方未全过量化/灰轴门',
             'full_position_only_release_gates_pending':'位置对照需要满配；完整发布准入待补'}
    for row in summary['existing_g157_actions']:
        out.append('| '+row['name']+' | '+actions[row['action']]+' | '+reasons[row['reason']]+' |')
    return out+['']


def byte_tables(catalog):
    path=LOCAL/'record_costs.json'
    if not path.exists():return ['逐条净字节须等最终配方导出后填入。','']
    costs=read(path);rows={(x['film'],x['unit']):x for x in costs['individual']}
    out=['## 逐片净字节','',
         '每格为 Look / 满配净增 B，以冻结 g157 release 为基线。Look 替换该单元同名 Look，无同名时新增；满配替换该单元 06。两者占用的产品位置不同。所有配方展开后都是 552 B；以下净增已计旧行移除、共享、描述符与对齐，不能跨格相加。test 布局的逐条预算也在 JSON 中。','',
         '| 胶片 | 50mm 净 B | 28mm 净 B | MOUNT 净 B |','| --- | ---: | ---: | ---: |']
    for film in catalog['films']:
        cells=[]
        for unit in UNITS:
            row=rows.get((film['name'],unit))
            cells.append('—' if row is None else str(row['Look_replace_same_named_or_add_net_bytes']['release'])+' / '+str(row['release']))
        out.append('| '+film['name']+' | '+' | '.join(cells)+' |')
    path=LOCAL/'capacity.json'
    if path.exists():
        out+=['','| 整组组合 | release 行池 B | 相对 g157 净 B | 物理 Look 描述符 | flags / 池上限 |',
              '| --- | ---: | ---: | ---: | --- |']
        names={'frozen_g157_18_Looks':'g157 冻结基线','recommended_locked_Looks_original_builtins':'推荐锁定 Look，原内置槽',
               'five_L1_current_anchor_compatible':'推荐锁定 Look + 五个可换 L1',
               'seven_L1_shows_current_anchor_conflict':'七个 L1，保留原 flags1 Look 的失败对照',
               'seven_L1_shared_Looks_flags7_aliased_RGB':'七个 L1，Look 用 flags7 共用曲线'}
        for row in read(path)['scenarios']:
            if row['profile']!='release':continue
            out.append('| '+names[row['scenario']]+' | '+str(row['row_pool_bytes'])+' | '+str(row['net_bytes_vs_frozen_g157'])+
                       ' | '+str(row['physical_Look_descriptors'])+' | '+('通过' if row['layout_flags_pass'] else '冲突')+
                       ' / '+('通过' if row['pool_limits_pass'] and row['descriptor_limit_pass'] else '超限')+' |')
        out+=['','五/七个 L1 的容量示例选用 Portra 160、Pro 400H、Gold 200、Ektar 100、Provia 100F、Velvia 50、Verita 200D，按顺序分配。它只演示一组模型候选的容量，不代表用户投票，也不替代安装验收。原 flags1 Look 的七槽对照会冲突；flags7 共用曲线方案另需冻结 base 应用元数据并由 Studio 原子重编码。最终布局仍须重算代码、BSS、行池和状态预算。']
    return out+['']


def weighted_validation():
    path=LOCAL/'weighted_controls_summary.json'
    if not path.exists():return ['加权对照的独立量化准入仍待补齐；主库保持未加权选择。','']
    data=read(path);assert data['status']=='COMPLETE_LOCAL_CONTROL_EVALUATION'
    out=['## 加权可选记录的独立量化准入','',
         '仅对通过名义颜色/整体预算且已做 exact 的加权记录补测 128 分支。每个分支既要通过原照片/场景门，也须相对未加权主配方保持整体损失≤1 pp、P95 增量≤0.25，并满足敏感色改善及单色域最多退步 0.25。未通过名义预算的路线不作为加权候选。','',
         '| 单元 | 送检加权记录 | 原准入 128/128 | 颜色预算 128/128 | 全部门槛通过 |',
         '| --- | ---: | ---: | ---: | ---: |']
    for unit in UNITS:
        rows=[r for r in data['records'] if r['unit']==unit]
        out.append('| '+LABELS[unit]+f" | {len(rows)} | {sum(r['release_gate_passes']==128 for r in rows)} | {sum(r['color_budget_passes']==128 for r in rows)} | {sum(r['robust_optional_model_candidate'] for r in rows)} |")
    out+=['','| 加权对照 / 单元 | 原门 / 颜色预算 / 合并分支 | 可选记录 | 替换 06 净 B，release / test |',
          '| --- | ---: | --- | ---: |']
    for row in data['records']:
        c=row['net_row_pool_bytes_if_replacing_only_slot06']
        out.append('| '+row['film']+' / '+LABELS[row['unit']]+' | '+
            ' / '.join(str(row[k]) for k in ('release_gate_passes','color_budget_passes','combined_passes'))+' | '+
            ('可进入后续试装' if row['robust_optional_model_candidate'] else '不准入')+f" | {c['release']} / {c['test']} |")
    out+=['',f"共 {data['robust_optional_records']}/{data['evaluated']} 条加权记录通过独立研究准入。它们保存在 local/full_library/weighted_optional_v1/，完整回执为 [local/weighted_controls_summary.json](local/weighted_controls_summary.json)。这不改变主库的未加权配方，也不替代新场景盲测、Studio 安装或相机验收。",'']
    return out


def weighting_and_diagnostics(summary,results):
    out=['## 敏感色收益与结构代理的质量代价','',
         '加权与未加权方法中训练优选的满配记录比较。肤色、天空、树叶均为固定 Lab 色域代理，非语义分割；每组至少 20 个点才纳入颜色改善判断。允许整体最多损失 1 pp、P95 最多增加 0.25，且三色域不出现超过 0.25 的中位退步。符合这些条件也需 exact 和原有量化准入。','',
         '| 单元 | 符合颜色/整体预算 | 整体分数变化中位 pp | 肤色 ΔE 变化 | 天空 ΔE 变化 | 树叶 ΔE 变化 |',
         '| --- | ---: | ---: | ---: | ---: | ---: |']
    for unit in UNITS:
        rows=[film['units'][unit]['weighted'] for film in summary['films'] if unit in film['units']]
        admitted=[x for x in rows if x['meets_color_and_overall_budget']]
        values=[f(med(x['similarity_change_pp'] for x in admitted))]
        values.extend(f(med(x['colors'][k]['delta_de00'] for x in admitted if x['colors'][k]['n']>=20))
                      for k in ('skin','sky','foliage'))
        out.append('| '+LABELS[unit]+f' | {len(admitted)}/{len(rows)} | '+' | '.join(values)+' |')
    out+=['','上表的变化中位只统计符合预算的配方，负 ΔE 表示改善；逐片、逐色域的样本数与变化保留在 [local/summary.json](local/summary.json)。没有给所有胶片统一打开加权。','',
          '| 单元 | 结构代理 − 黑盒中位 pp | 两侧均离开模板时，中位 pp / 配方数 | 结构代理照片分数较高 | 黑盒 / 结构仍停模板 |',
          '| --- | ---: | ---: | ---: | ---: |']
    for unit in UNITS:
        pairs=[];active=[];wins=black_stalled=structure_stalled=0
        for (ordinal,u),doc in results.items():
            if u!=unit:continue
            black,structure=(doc['routes'][name] for name in ('scene_rgb_matrix','scene_structure'))
            a,b=(row['scores']['photo_iso200']['similarity_percent'] for row in (black,structure))
            if a is not None and b is not None:
                pairs.append(b-a);wins+=b>a+1e-9
                if not black.get('retained_unmodified_template') and not structure.get('retained_unmodified_template'):
                    active.append(b-a)
            black_stalled+=bool(black.get('retained_unmodified_template'))
            structure_stalled+=bool(structure.get('retained_unmodified_template'))
        out.append('| '+LABELS[unit]+' | '+f(med(pairs))+' | '+f(med(active))+f' / {len(active)} | {wins}/{len(pairs)} | {black_stalled} / {structure_stalled} |')
    out+=['','结构代理同时改变初始化和弱灰轴约束；这里比较两种完整方法，不把差值全部归于某一个步骤。排除仍停模板的配方是解释优化失败的诊断，不是重新选参数或改准入。未入选路线的 exact 覆盖见逐片路线表。','',
          '| 方法 | 色相反转区间总数 / 有定义区间 | 有效中性轴最大回落 L* | 灰轴回落超过目标 0.5 L* 的单元数 |',
          '| --- | ---: | ---: | ---: |']
    method_hue_counts={}
    for name,label in (('scene_rgb_matrix','满配黑盒'),('scene_structure','满配结构代理'),('scene_shared_structure','共享曲线结构代理')):
        reversals=defined=0;drawdowns=[];warnings=0
        for doc in results.values():
            q=doc['routes'][name]['quality']
            reversals+=q['reverse_hue_intervals'];defined+=q['hue_defined_intervals']
            shape=doc.get('structure_comparison',{}).get(name,{}).get('gray_shape')
            if shape and shape['maximum_Lstar_drawdown'] is not None:
                drawdowns.append(shape['maximum_Lstar_drawdown'])
                warnings+=shape['maximum_Lstar_drawdown']>shape['target_maximum_Lstar_drawdown']+.5
        out.append('| '+label+f' | {reversals} / {defined} | '+f(max(drawdowns) if drawdowns else None)+f' | {warnings}/{len(drawdowns)} |')
        method_hue_counts[name]=(reversals,defined)
    black,structure=(method_hue_counts[name] for name in ('scene_rgb_matrix','scene_structure'))
    if black[1] and structure[1] and structure[0]/structure[1]>=black[0]/black[1]:
        out+=['','本轮反转比例未显示结构代理更少：黑盒为 '+f(100*black[0]/black[1],3)+'%，结构代理为 '+f(100*structure[0]/structure[1],3)+'%。黑盒卡在模板的项目很多，不能把这两项原始比例解释为结构方法的因果效果。结构代理的主要已证收益是改善 MOUNT 的优化可达性。']
    selected_shapes=[d['tone']['gray_shape'] for d in results.values() if d['tone'].get('gray_shape')]
    warnings=[d for d in results.values() if d['tone'].get('gray_shape') and
              d['tone']['gray_shape']['maximum_Lstar_drawdown']>d['tone']['gray_shape']['target_maximum_Lstar_drawdown']+.5]
    out+=['',f'训练选中的满配记录已测中性轴 {len(selected_shapes)} 份，其中 {len(warnings)} 份相对目标多出超过 0.5 L* 的回落。0.5 是本轮保守诊断线，不是已建立的人眼阈值，也未用于照片挑参。仅有负步数而没有回落幅度，不能判断是否有可见问题。']
    out+=['最终整数记录都先经过同一色相质量门，因此通过记录中的低反转计数本身不能证明结构代理更少产生反转；还须结合有效色相覆盖、被拒绝的候选及灰轴回落判断。']
    if warnings:out.append('')
    for doc in warnings:
        shape=doc['tone']['gray_shape']
        out.append('- '+doc['film']+' / '+LABELS[doc['unit']]+' 的有效灰轴最大回落为 '+f(shape['maximum_Lstar_drawdown'])+
                   ' L*，目标为 '+f(shape['target_maximum_Lstar_drawdown'])+'；不建议直接选为默认。')
    exact_paths=set()
    for doc in results.values():
        for name in (doc['selected_route'],doc['selected_Look_route']):
            row=doc['routes'][name]
            if row['reference_exact_checked']:exact_paths.add(Path(row['record_file']).with_suffix('.json'))
    starts=failed=0
    for path in exact_paths:
        doc=read(path);starts+=len(doc['attempts']);failed+=sum(not x['receipt']['success'] for x in doc['attempts'])
    out+=['',f'胶片最终入选两侧共 {len(exact_paths)} 条 exact 记录、{starts} 个起点，{failed} 个起点达到迭代预算仍未报告收敛。所有失败回执保留；reference exact 复核不等于已找到全局最优。',
          '色相统计同时报告有效覆盖。黑白输出的色相无定义，不能把它的零反转说成彩色色相能力通过；固定环和三条渐变也不是对全部图像的证明。','',
          '| 单元 | 中性轴最后支持的 EV | 饱和色扫描支持点 / 396 | 彩色档案有定义的色相点范围 |',
          '| --- | ---: | ---: | ---: |']
    for unit in UNITS:
        docs=[d for d in results.values() if d['unit']==unit]
        gray=[d['tone']['last_supported_gray_EV'] for d in docs if d['tone'].get('last_supported_gray_EV') is not None]
        support=[d['brightness_dependent_color']['supported_hue_test_points'] for d in docs]
        defined=[d['brightness_dependent_color']['defined_supported_hue_points'] for d in docs
                 if d['brightness_dependent_color']['defined_supported_hue_points']>0]
        span=lambda values:'—' if not values else str(min(values)) if min(values)==max(values) else str(min(values))+'–'+str(max(values))
        out.append('| '+LABELS[unit]+' | '+f(max(gray) if gray else None)+' | '+span(support)+' / 396 | '+span(defined)+' |')
    out+=['','支持范围同时要求 RAW 和校正后输入都在 0–4095；EV 相对固定 Y=0.18。最后支持 EV 是当前映射与模型的输入边界，不是传感器实测动态范围。色相点还要求目标与预测的 Lab 色度均≥5；低色度和黑白点不进入角度统计。','']
    return out
