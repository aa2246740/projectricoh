"""Generate score tables and the MOUNT-first progress report from saved receipts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_std as rt
import collections
import csv
from capabilities import main_level,mount_l1_enabled

UNITS = ('mount-a12', 'a12-50', 'a12-28')
GROUPS = ('train', 'synthetic', 'photo_iso200', 'photo_other_iso')


def f(value, digits=2):
    return '—' if value is None else f'{value:.{digits}f}'


def table(headers, rows):
    return ['', '| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |'] + [
        '| '+' | '.join(str(v).replace('|', '／').replace('\n', ' ') for v in row)+' |' for row in rows]


def csv_write(name, rows, fields=None):
    with (rt.HERE/name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def select(paths):
    # This second-stage consolidation follows exactly the single-fit training
    # criterion. It does not rank candidates by any held-out photograph.
    docs = [(p, rt.read(p)) for p in paths]
    docs = [(p, d) for p, d in docs if d['quality']['passes']]
    originals=[pair for pair in docs if not pair[1].get('canonical_equivalence_parent')]
    if not originals:return (None,None)
    best=min(originals,key=lambda pair:(pair[1]['objective'],str(pair[0])))
    parent=str(best[0].relative_to(rt.HERE))
    equivalent=[pair for pair in docs if pair[1].get('canonical_equivalence_parent')==parent
                and pair[1]['objective']==best[1]['objective']]
    return min(equivalent,key=lambda pair:str(pair[0])) if equivalent else best


def collect(include_new7=True):
    catalog = rt.read(rt.HERE/'target_catalog.json')['definitions']
    verification = rt.read(rt.HERE/'verification.json') if (rt.HERE/'verification.json').exists() else {}
    replayed = {(r['file'],r['record_sha256']) for r in verification.get('records', [])}
    new7 = {}
    suffix='_L1' if mount_l1_enabled() else ''
    new7_verification_path = rt.HERE/f'new7_raw_holdout_verification{suffix}.json'
    if include_new7 and new7_verification_path.exists():
        nv = rt.read(new7_verification_path)
        assert nv['status']=='PASS' and nv['summary_sha256']==rt.sha(rt.HERE/f'new7_raw_holdout_summary{suffix}.json')
        new7 = {r['index']:r for r in rt.read(rt.HERE/f'new7_raw_holdout_summary{suffix}.json')['profiles']}
    registry, scores, fixtures, scenes, pending_probe = [], [], [], [], []
    for unit in UNITS:
        level = main_level(unit)
        for target in catalog:
            index = target['index']
            base = rt.LOCAL/'targets'/unit
            paths = list((rt.LOCAL/'fits'/unit/f'{index:02d}').glob(f'L{level}_*.json'))
            path, doc = select(paths)
            meta_path = base/f'{index:02d}.json'
            meta = rt.read(meta_path) if meta_path.exists() else None
            row = dict(label='电脑预测', unit=unit, index=index, name=target['name'],
                kind=target['kind'], published=target['kind']=='builtin' or target.get('shipped_in_g154_looks18', False),
                main_level=level, status='pending_fast_engine',
                record_file=None, record_sha256=None, verified_record_replay=False,
                recommendation='pending', holdout_kind='synthetic_only' if unit=='a12-28' else 'whole_scene_RAW_computer_render')
            if doc:
                record_verified=(str(path.relative_to(rt.HERE)),doc['record']['sha256']) in replayed
                whole_scene = doc['per_scene'].get('photo_iso200', {})
                regressed = [name for name, values in whole_scene.items()
                    if values['candidate']['de00']['median'] > values['current']['de00']['median']+1e-10
                    or values['candidate']['de00']['p95'] > values['current']['de00']['p95']+1e-10]
                extra = new7.get(index) if unit=='mount-a12' else None
                if extra:
                    assert extra['record_sha256']==doc['record']['sha256'], 'New RAW holdout must match the selected record'
                    if not extra['scene_gate_pass']:
                        regressed.append(extra['scene'])
                row.update(status='refitted' if doc['origin']=='refit' else 'retained_current',
                    record_file=str(path.with_suffix('.record552').relative_to(rt.HERE)),
                    record_sha256=doc['record']['sha256'], verified_record_replay=record_verified,
                    fit_receipt=str(path.relative_to(rt.HERE)), S_mode=doc['S_mode'],
                    objective=doc['objective'], training_only_selection=True,
                    overfit_flags=doc['overfit_flags'], quality=doc['quality'],
                    scene_regression_review=regressed,
                    gain_over_current_pp=doc['gain_over_current_pp'],
                    recommendation=('review_scene_regression' if regressed and doc['origin']=='refit'
                        else 'replace_candidate' if doc['recommend_next_dat_build'] and record_verified
                        else 'keep_native04' if target.get('builtin_slot')==4 else 'keep_current_or_review'))
                if extra:
                    row.update(new7_raw_holdout=extra,new7_raw_holdout_replayed=True,
                        new7_verification_sha256=rt.sha(new7_verification_path))
                elif unit=='mount-a12' and mount_l1_enabled() and target.get('builtin_slot')!=4:
                    row['recommendation']='pending_new7_replay'
                row['mount_L1_response_amplitude_unclosed']=doc.get('mount_L1_response_amplitude_unclosed',False)
                for name, q in doc['quality']['gradients'].items():
                    fixtures.append(dict(label='电脑预测', unit=unit, index=index, name=target['name'], gradient=name,
                        integer_step_max_de00=q['integer_step_de00']['max'],
                        continuous_step_max_de00=q['continuous_step_de00']['max'],
                        negative_lightness_steps=q['negative_lightness_steps'],
                        longest_identical_output_run=q['longest_identical_output_run'],
                        new_reverse_hue_intervals=doc['quality']['new_reverse_hue_intervals'],
                        passes=doc['quality']['passes'], intended_grayscale=doc.get('gray', False)))
                for group, groups in doc['per_scene'].items():
                    for scene, values in groups.items():
                        scenes.append(dict(label='电脑预测', unit=unit, index=index, name=target['name'], group=group,
                            scene=scene, points=values['candidate']['de00']['n'],
                            current_percent=values['current']['similarity_percent'],
                            candidate_percent=values['candidate']['similarity_percent'],
                            current_median_de00=values['current']['de00']['median'],
                            candidate_median_de00=values['candidate']['de00']['median'],
                            current_p95_de00=values['current']['de00']['p95'],
                            candidate_p95_de00=values['candidate']['de00']['p95']))
                if extra:
                    a,b=extra['current'],extra['candidate']
                    scenes.append(dict(label='电脑预测',unit=unit,index=index,name=target['name'],
                        group='photo_new7_RAW_diagnostic',scene=extra['scene'],points=extra['points'],
                        current_percent=a['similarity_percent'],candidate_percent=b['similarity_percent'],
                        current_median_de00=a['de00']['median'],candidate_median_de00=b['de00']['median'],
                        current_p95_de00=a['de00']['p95'],candidate_p95_de00=b['de00']['p95']))
            registry.append(row)
            for group in GROUPS:
                values = doc['scores'].get(group) if doc else None
                current = values['current'] if values else meta['scores'].get(group, {}).get('current') if meta and meta['scores'].get(group) else None
                candidate = values['candidate'] if values else None
                scores.append(dict(label='电脑预测', unit=unit, index=index, name=target['name'], level=level,
                    group=group, status=row['status'], published=row['published'],
                    points=candidate['de00']['n'] if candidate else current['de00']['n'] if current else None,
                    current_percent=current['similarity_percent'] if current else None,
                    candidate_percent=candidate['similarity_percent'] if candidate else None,
                    gain_pp=doc['gain_over_current_pp'].get(group) if doc else None,
                    current_median_de00=current['de00']['median'] if current else None,
                    candidate_median_de00=candidate['de00']['median'] if candidate else None,
                    current_p95_de00=current['de00']['p95'] if current else None,
                    candidate_p95_de00=candidate['de00']['p95'] if candidate else None,
                    candidate_max_de00=candidate['de00']['max'] if candidate else None,
                    overfit_flag=doc['overfit_flags'].get(group) if doc else None,
                    recommendation=row['recommendation']))
            if doc and unit=='mount-a12' and index in new7:
                extra=new7[index]
                a,b=extra['current'],extra['candidate']
                scores.append(dict(label='电脑预测',unit=unit,index=index,name=target['name'],level=level,
                    group='photo_new7_RAW_diagnostic',status=row['status'],published=row['published'],points=extra['points'],
                    current_percent=a['similarity_percent'],candidate_percent=b['similarity_percent'],
                    gain_pp=None if a['similarity_percent'] is None else b['similarity_percent']-a['similarity_percent'],
                    current_median_de00=a['de00']['median'],candidate_median_de00=b['de00']['median'],
                    current_p95_de00=a['de00']['p95'],candidate_p95_de00=b['de00']['p95'],candidate_max_de00=b['de00']['max'],
                    overfit_flag=doc['training_improved'] and b['de00']['median']>=a['de00']['median'],
                    recommendation=row['recommendation']))
            if unit == 'mount-a12' and not mount_l1_enabled():
                pp, dd = select((rt.LOCAL/'fits'/unit/f'{index:02d}').glob('L1_*.json'))
                if dd:
                    assert dd['mount_probe_pending'] and not dd['recommend_next_dat_build']
                    pending_probe.append(dict(label='电脑预测', unit=unit, index=index, name=target['name'],
                        level=1, main_eligible=False, mount_probe_pending=True,
                        record_file=str(pp.with_suffix('.record552').relative_to(rt.HERE)),
                        record_sha256=dd['record']['sha256'], scores=dd['scores'],
                        quality=dd['quality'], gain_over_current_pp=dd['gain_over_current_pp']))
    assert len(registry) == 105
    rt.dump('candidate_registry.json', dict(label='电脑预测', created_utc=rt.utc(), profiles=registry,
        completed_main_profiles=sum(r['status']!='pending_fast_engine' for r in registry),
        expected_main_profiles=105, mount_L1_pending=pending_probe,
        new7_RAW_group_used_for_additional_scene_gate=bool(new7),
        consolidation='lowest integer weighted training DE00-square among fixed-guard-passing candidates',
        promotion_review='whole-scene ISO200 median or P95 regression requires review; parameter selection is unchanged'))
    csv_write('scores.csv', scores)
    if fixtures:
        csv_write('quality.csv', fixtures)
    if scenes:
        csv_write('scene_scores.csv', scenes)
        scene_summary = []
        for unit, index in sorted({(s['unit'], s['index']) for s in scenes}):
            ss = [s for s in scenes if s['unit']==unit and s['index']==index and s['group'] in ('photo_iso200','photo_new7_RAW_diagnostic')]
            scene_summary.append(dict(label='电脑预测', unit=unit, index=index, scenes=len(ss),
                worsened_median_scenes=[s['scene'] for s in ss if s['candidate_median_de00'] > s['current_median_de00']+1e-10],
                worsened_p95_scenes=[s['scene'] for s in ss if s['candidate_p95_de00'] > s['current_p95_de00']+1e-10],
                per_scene_gain_pp={s['scene']: None if s['candidate_percent'] is None or s['current_percent'] is None
                    else s['candidate_percent']-s['current_percent'] for s in ss}))
        rt.dump('scene_summary.json', scene_summary)
    return registry, scores, pending_probe, verification


def main():
    registry, scores, pending, verification = collect()
    hypotheses = []
    for path in sorted((rt.LOCAL/'hypotheses').rglob('*.json')):
        d = rt.read(path)
        for group, values in d['scores'].items():
            if values:
                hypotheses.append(dict(label='电脑预测，假设分支', unit=d['unit'], index=d['index'], name=d['name'],
                    level=d['config']['level'], axis=d['config']['axis'], order=d['config']['tail_order'],
                    tint=d['config']['tint'], group=group,
                    current_percent=values['current']['similarity_percent'],
                    candidate_percent=values['candidate']['similarity_percent'],
                    gain_over_current_pp=d['gain_over_current_pp'][group],
                    new_reverse_hue_intervals=d['quality']['new_reverse_hue_intervals'],
                    overfit_vs_parent=d['overfit_flags'].get(group),
                    main_candidate=False, max_solver_nfev=max((r['nfev'] for r in d['solver_attempts']), default=0)))
    if hypotheses:
        csv_write('hypothesis_scores.csv', hypotheses)
    lookup = {(r['unit'], r['index'], r['group']): r for r in scores}
    material = rt.read(rt.HERE/'materials_summary.json')
    calibration = rt.read(rt.HERE/'calibration_summary.json')['selected']
    new = rt.read(rt.HERE/'new_materials_summary.json')
    response = rt.read(rt.HERE/'new_capture_response_summary.json')
    response_bank = rt.read(rt.HERE/'capture_current_row_equality.json')
    catalog = rt.read(rt.HERE/'target_catalog.json')
    protocol = rt.read(rt.HERE/'input_protocol.json')
    completed = [r for r in registry if r['status']!='pending_fast_engine']
    replace = [r for r in completed if r['recommendation']=='replace_candidate']
    names = '、'.join(r['unit']+' '+r['name'] for r in replace) or '暂无'
    main_complete = len(completed) == 105
    stamp = rt.utc()
    closed = (rt.HERE/'stage_closure.json').exists()
    lines = [
        f'MOUNT 04 整场景留出的中位 ΔE00 从 0.918 降到 0.888，误差下降 {f(calibration["mount-a12"]["median_error_reduction_percent"])}%；50mm 从 0.532 降到 0.529。',
        '小子集电脑预测：MOUNT 03、05、06 的 ISO200 照片留出分别提高 10.83、5.58、1.77 个百分点；全量成绩尚待快速引擎。',
        f'下轮 DAT 构建候选为 {names}；03有一组场景中位误差回退，先复核；04保留原生。MOUNT L1待三曲线探针。',
        '还缺 MOUNT 有明确原厂04身份的自然光 RAW+JPG、拍摄设置记录与三曲线响应；28mm 无可用04配对素材，50mm也需自然场景。',
        f'状态：阶段封存，{len(completed)}/105 个主档案已有保存记录；全量重拟合和假设分支未完成，等待快速引擎切换通知。最后核验更新于 {stamp}。' if closed else f'状态：阶段报告，{len(completed)}/105 个主档案已有保存记录；尚未完成全量重拟合和假设分支。更新于 {stamp}。',
        '', '## 评分与证据范围', '',
        '本文所有相似度、ΔE00、质量夹具结果均为电脑预测。相似度为 100×(1−候选中位 ΔE00／原厂04中位 ΔE00)，不是与另一台相机的实拍一致率。分母小于0.25时不报百分比；04的目标是自身恒等输出，所以百分比为空。',
        '“照片留出”从真实 DNG 取输入，目标和候选均在电脑渲染。训练、独立合成点、ISO200整场景照片及其他ISO迁移诊断分开。未知配方的相机JPG不充当Standard真值。现有模型没有逐级硬件整数运算、MOUNT实测角向响应或实机生命周期验收。',
        '', '## 素材与身份核对', '',
        '逐文件清单在 [local/material_identity.csv](local/material_identity.csv)，完整EXIF、原始哈希、相机JPG配对和证据来源在 [local/materials.json](local/materials.json)。日常未确认照片保持未确认；文件名、Standard选择器或模型最小误差均不能单独证明原厂04身份。重复RAW同时比较完整文件和CFA负载，所有者明确废弃的原始拍摄不进入拟合。',
    ]
    lines += table(['单元', 'DNG路径数', '独立RAW哈希', '有JPG', 'ISO200 04标定帧', '标定场景组'], [
        [unit, d['files'], d['unique_raws'], d['paired_files'], d['primary_iso200_frames'], len(d['primary_scene_groups'])]
        for unit, d in material['by_unit'].items()])
    lines += ['', f'新增39对逐张核对结果：39对均为MOUNT，RAW/JPG拍摄时间、ISO、曝光、选择器、记录的滑杆字段和方向一致，JPG均为sRGB；其中{new["newly_unique_raws"]}份为新增独立RAW。ISO200共33张，ISO3200共4张，ISO400和640各1张。WB用户偏移、镜头校正菜单及未记录的配方身份仍未知。',
        f'与拍摄时已有的{response_bank["candidate_entries"]}个候选行、{response_bank["distinct_response_groups"]}个不同响应组比较，只有{response["supported"]}帧达到预先规定的误差、间隔及空间块重采样门槛；没有一帧成为04候选。最小误差组为M9 STD的34帧不等于34帧独立确认。它们留在“当前发布行响应对照”中；新RAW可用于留出，但JPG不加入04标定。候选行选择会降低最小误差，不能把它当独立模型准确率。',
        '拍摄时间先于g154 looks18包复制，分类使用拍摄时的g152行。两包24条内置行和共享10条Looks的完整552 B逐字节相同，见 [capture_current_row_equality.json](capture_current_row_equality.json)。本任务只读本地副本，没有读取存储卡。',
        '', '## 04响应与输入标定', '',
        '对黑白电平与CFA相位正确的RAW，以DNG AsShotNeutral归一化，在type26之前拟合每单元输入残差。使用固定12×12平坦区域、固定注册偏移和独立于预测误差的掩码；不按单张照片调整曝光或白平衡。按拍摄场次及光源整组留出，分别报告旧50mm响应迁移、单元原始静态参数、旧50mm输入映射和新输入映射。',
        'MOUNT用10月24日六张04训练，11月1日一张04整组留出；反向留出另保留。两组均主要为屏幕样本，其身份包含历史模型核对，不能当盲测。50mm从三个屏幕场次训练，以10月26日两张已确认原生04的实物图整组留出；仿射与二次模型仅在内部屏幕场次比较，按预定均方误差选择二次，外层实物图不参与模型选择。二次模型内部中位误差稍差，两种控制均保留。',
    ]
    rows = []
    for unit, d in calibration.items():
        q = d['group_scores']
        rows.append([unit, d['train_points'], d['holdout_points'],
            f(q['transferred_50mm']['median'], 3), f(q['legacy_50mm_input_map']['median'], 3),
            f(q['recalibrated']['median'], 3), f(d['median_error_reduction_percent']),
            f(q['transferred_50mm']['p95'], 3)+' → '+f(q['recalibrated']['p95'], 3)])
    lines += table(['电脑预测', '训练点', '外层留出点', '50mm迁移中位ΔE', '旧50mm输入映射', '新映射中位ΔE', '中位误差下降%', 'P95 ΔE'], rows)
    lines += ['', '完整场次与各控制见 [calibration_scores.csv](calibration_scores.csv)、[calibration_model_controls.json](calibration_model_controls.json)。逐单元静态参数已分开，角向响应核仍来自50mm；XYZ中灰锚点也沿用旧50mm假设。28mm仅有一张无配对JPG的DNG，不能标定04，也不报照片留出。',
        '输入映射在实际RAW域及覆盖照片范围的33³网格上检查局部雅可比，未检出非正行列式，前向闭合误差小于1e-6码；这不是全域可逆性证明。MOUNT ISO200照片约2.53%的点超出04训练RAW分量范围，50mm约13.19%，因此仍需要自然场景04覆盖。详见 [input_domain_summary.json](input_domain_summary.json)。',
        '', '## 目标、硬件层与主候选', '',
        '共35个独立目标定义，每单元35项，共105个主档案。27个Looks中18个与g154 looks18一一对应，包括QianXi与千禧回声、ARRI709与ARRI Classic709的名称映射；其余9个仅有look-ceiling参考行。详见 [target_catalog.json](target_catalog.json)。05/06主目标保留原历史F-Log2/F-Gamut 65³；F-Log2C33仅保留为单独目标控制。07/08保留S1RII数值反演残差和不受支持点，不用拟合结果删除点。',
        '50mm与28mm主层为L1，MOUNT主层为L0，另列L1等待探针。每条主记录含完整552 B，逐单元曲线、两半C100、ISO100镜像曲线及校验均有明确处理。新拟合只调整已确认的共同或独立三曲线、Y混色与对称24扇区；当前06的C100色度与中心保留，不拟合未知字段。04完整记录保持原生字节。',
        '当前只跑03/05/06和恒等04的小子集，使用nice 15、单数值进程、单BLAS线程。单次命令有25分钟上限；全量矩阵等快速引擎交付及等价检查通知后再启动，不启动预计超过30分钟的单块。',
        '', '### MOUNT阶段成绩', '',
    ]
    rows = []
    for r in completed:
        if r['unit'] != 'mount-a12':
            continue
        train, syn, photo, other = [lookup[(r['unit'], r['index'], key)] for key in GROUPS]
        rows.append([r['name'], f(photo['current_percent']), f(train['candidate_percent']),
            f(syn['candidate_percent']), f(photo['candidate_percent']), f(photo['gain_pp']),
            f(other['candidate_percent']), dict(replace_candidate='下轮换行候选',
                review_scene_regression='需复核场景回退', keep_native04='保留原生',
                keep_current_or_review='保留或复核')[r['recommendation']]])
    lines += table(['电脑预测', '当前照片%', '候选训练%', '候选合成%', '候选ISO200照片%', '提升百分点', '其他ISO诊断%', '处理'], rows)
    lines += ['', '全部105项的覆盖状态和分组成绩见 [scores.csv](scores.csv)，空值表示待运行或百分比分母不足，绝不填成0。[candidate_registry.json](candidate_registry.json)给出每项完整记录的本地路径、SHA256、选型及验证状态；参数、曲线和记录字节只在local/保存。各场景成绩见 [scene_scores.csv](scene_scores.csv)。',
        '场景审核单列于参数选择之后，不重选参数：任一完整ISO200场景的中位误差或P95回退，就标记需复核。03在10月31日两张DNG（R8051562、R8051627，共192点）中位ΔE00从0.527变为1.265，相似度下降7.54个百分点；P95却从22.740降到5.744。这是中位与尾部误差的取舍，03目前保留候选但不列入直接换行清单。05/06在三个ISO200场景的中位与P95均下降，见 [scene_summary.json](scene_summary.json)。',
        '已有50mm仿射输入控制仅供敏感性比较：03、05、06的照片留出分别为96.57%、88.74%、86.71%，对应提升17.25、6.19、4.38个百分点；它们没有替代选定二次标定后的正式主候选，文件保存在local/controls/affine_a12_50/。',
        '', '### 03的Standard约束', '',
        'look-ceiling的03约94%使用了原生纯灰度模型捷径，见其METHODS.md第55行及ceiling_model.py的bw分支。旧MOUNT L0/L1为94.10%/94.24%，旧50mm L0/L1为94.48%/94.69%；与本轮照片总体不同，不能直接相减。',
        '本轮主03保留S=04，在实际C100两半清零色度系数并清零色度表。保存记录通过普通彩色Standard链独立重放，与同一参数的抽象原生灰度输出差小于1e-7码；两种路径的本轮预测相同。MOUNT L0照片为95.55%，L1为97.15%，后者明确待MOUNT三曲线探针。关机恢复行为本轮未上机，552 B静态S字段与04一致只证明记录约束。',
        '为避免L1优化丢失已有L0结果，后续运行会按整数训练损失引入同节点的既有记录起点，并把该起点本身作为量化候选。MOUNT03/05/06已在59922个输入点上验证L1可精确嵌入当前L0的整数预测，见 [L1_inheritance_check.json](L1_inheritance_check.json)；这不替代MOUNT三曲线实测。',
        '', '## 质量护栏与分支状态', '',
        '主候选选择只看整数训练加权ΔE00平方和固定质量夹具；不按照片或合成留出挑参数。使用灰阶、天空、肤色各2049点和九个721点色相环。逐个色相区间与当前行比较，任何新增折返即拒绝，整数渐变最大步长须≤2 ΔE00。原本已有的折返仍报告；预期纯灰输出的色相记不适用。',
        '初次MOUNT05/06优化全部被新增折返门槛拒绝。加入训练阶段的色相环罚项后取得上表可行候选，最终仍按整数硬门槛验收。罚项解析导数在真实MOUNT05扰动上与数值差分核对，604个违规区间得到实际覆盖，见 [guard_derivative_check.json](guard_derivative_check.json)。',
    ]
    rows = []
    for r in completed:
        q = r['quality']
        rows.append([r['unit']+' '+r['name'], q['new_reverse_hue_intervals'],
            q['reverse_hue_intervals'], f(q['max_integer_gradient_step_de00'], 3),
            sum(g['negative_lightness_steps'] for g in q['gradients'].values()),
            '、'.join(k for k, v in r['overfit_flags'].items() if v) or '无'])
    lines += table(['电脑预测', '新增折返区间', '现有总折返区间', '整数最大步长ΔE', '负亮度步数', '过拟合标记组'], rows)
    lines += ['', '过拟合标记表示训练整数损失下降而该留出组中位误差未下降，不能由此单独判定原因。主候选未新增色相折返仅针对固定九环；这不是所有输入颜色的数学证明。完整渐变记录见 [quality.csv](quality.csv)。',
        'C120两种轴及前后次序、C100完整矩阵/偏移和C004两种方程均属于单列假设分支；全矩阵尚待快速引擎，未写入主候选。当前只用MOUNT05、每支最多6次求值核对Y/C后置及Y后置完整C100的运行流程。三支新增色相折返分别为73、71、73，均不能进主候选；低迭代控制不能支持收益排序。详见 [hypothesis_scores.csv](hypothesis_scores.csv) 和 [hypothesis_verification.json](hypothesis_verification.json)。未测方程不会因电脑分数提高而升级为硬件事实。不评估相机软件3D LUT或慢速模式。',
        '旧报告与原始JSON的质量计数存在差异，冻结两者并保留统计口径与哈希在 [prior_audit.json](prior_audit.json)。本轮护栏从本轮保存记录重新计算，不继承旧报告的通过结论。',
        '', '## DAT构建所需清单', '',
        f'目前可交给下轮DAT构建验证的候选：{names}。MOUNT03需复核场景回退；04保留原生；其他目标待全量重拟合，不能把待运行项目列为“不值得换”。MOUNT L1待探针，不进入本轮主更换清单。',
        '下轮构建需使用candidate_registry内精确记录及SHA，保留每单元独立曲线和S=04约束，重算GXFX单元掩码/身份、行CRC、全局描述符及池去重，再核对实际格式和容量。552 B单行可编码不等于105项已能装入现有DAT。本轮不生成DAT，也不操作固件或存储卡。',
        '', '## 重跑与文件核验', '',
        '约三小时节点的原始阶段报告已保留在local/checkpoint_3h/，对应哈希见 [checkpoint_3h_receipt.json](checkpoint_3h_receipt.json)。本次会话中断后已超出原时间盒，尚未收到快速引擎切换通知，因此封存已完成的准备工作，不启动待通知的全量矩阵。范围与未完成项见 [stage_closure.json](stage_closure.json)。' if closed else '本任务仍在阶段运行中。',
        '运行环境使用本任务冻结的历史源代码、Python隔离模式及单线程数学库。原代码与第三方参数复制到local/source；不导入机主Studio。本任务脚本不修改tools或上游研究。所有输入和最终输出摘要由SHA256SUMS绑定；阶段文件仍会更新，最终封存时重新生成清单。',
        '重跑入口见 [RERUN.md](RERUN.md)。运行fit_one时必须给新tag，禁止覆盖旧拟合回执。校准及输入数据准备会重写派生缓存，应在单独任务副本中重跑；不能在已封存候选目录中混用新输入和旧目标。',
        f'最新完整记录重放：{verification.get("status", "待运行")}，{verification.get("completed_record_fits", 0)}条记录，涉及{sum(r["points_replayed"] for r in verification.get("records", []))}个预测点。验证逐字节重建552 B、九个行CRC、S模式/参数、普通Standard独立模型、分数、质量夹具及Git忽略。见 [verification.json](verification.json)。',
        '', '## 机主素材与清理', '',
        'MOUNT优先需要有明确原厂04身份的自然光RAW+JPG：保留单元、镜头/光圈、反差/锐度/鲜艳度、WB模式及用户偏移、ISO、sRGB和镜头校正菜单记录。需要不同日期/光源的完整场景，包含灰、天空、肤色和饱和色，不要求色卡；另等现有三曲线探针。01/02/03的GR目标还缺独立实物桥接真值。50mm自然拍摄时按同样方式记身份；28mm后续有素材再做，不假设近期能收到。',
        f'可以进DAT构建验证的阶段候选：{names}；需要的机主素材为明确原厂04的MOUNT自然场景、设置记录与三曲线探针，之后再补50/28；当前仍在运行阶段，Scratch尚未最终清理。',
    ]
    (rt.HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
    progress = [f'MOUNT优先阶段结果，更新于 {stamp}。', '',
        'MOUNT 04整场景留出：中位ΔE00 0.918→0.888，下降3.23%；P95 3.248→2.910。屏幕场次训练与留出分离，自然光原厂04仍缺。',
        '新增39对已逐张核对，均为MOUNT；35份独立新增RAW，0份独立确认原厂04。现有响应推断只作对照，未把未确认JPG加入04拟合。',
        'MOUNT03已在S=04下重拟合；L0照片留出95.55%，比当前行提升10.83个百分点，但10月31日两张照片的场景中位误差回退，先标为需复核。05为85.76%（+5.58），06为79.31%（+1.77），三个ISO200场景中位和P95均改善。全部电脑预测，主候选新增色相折返为0。04完整原生记录不变。',
        'MOUNT03的L1照片97.15%只作待探针候选，不进入主候选或DAT更换清单。',
        '35个MOUNT目标与现行/参考行的质量基线已准备完；g154 looks18与27目标的对应全部核对。全量主矩阵、MOUNT其余L1及C120/C100假设分支仍等快速引擎交付和等价切换通知。C120/C100仅做MOUNT05三支低迭代流程验证，新增色相折返71–73，不进主候选。50mm保留标定与小子集敏感性控制，28mm最后，仅合成评分。',
        f'目前{len(completed)}/105个主档案有记录，{len(replace)}个为下轮DAT构建候选；待运行项目不冒充保留结论。',
        f'最新重放状态{verification.get("status", "未运行")}，{verification.get("completed_record_fits", 0)}条记录。所有派生参数、曲线、像素及整数行只在Git忽略的local/，未构建DAT，未访问卡、机主Studio或网络。',
        '约三小时阶段结果已落盘并保存在local/checkpoint_3h/；本次中断后已超出原时间盒，封存现有阶段产物。全量未完成，快速引擎尚未收到切换通知，后端入口保持拒绝运行。' if closed else '约三小时阶段结果已落盘；阶段细项见REPORT.md、scores.csv和candidate_registry.json。快速引擎尚未收到切换通知，后端入口保持拒绝运行。']
    (rt.HERE/'PROGRESS.md').write_text('\n\n'.join(p for p in progress if p)+'\n')
    print('Report updated', len(completed), '/105 main profiles;', len(replace), 'replacement candidates; full matrix', main_complete)


if __name__ == '__main__':
    if (rt.LOCAL/'continuation.json').exists():
        verification = rt.read(rt.HERE/'verification.json')
        if verification.get('full_recipe_matrix_complete'):
            from final_report import main as continuation_main
        else:
            collect()
            from continuation_progress import main as continuation_main
        continuation_main()
    else:
        main()
