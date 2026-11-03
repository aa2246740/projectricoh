"""Bind final candidates to their exact confirmation and discrete ramp evidence."""
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind_row(row, fit):
    if row['unit'] == 'mount-a12':
        ramp = next(r for r in read(HERE/'mount_ramp_scope_summary.json')['profiles']
                    if r['index'] == row['index'])
        assert ramp['record_sha256'] == row['record_sha256']
        assert not ramp['quantitatively_accepted_continuous_intervals']
        row['mount_ramp_sample_scope'] = ramp
        row['hardware_model_scope'] = ('native04 bytes retained' if row['index'] == 30 else
            'node16 +2 responses at sampled grey points only; gaps, other hues, nodes and amplitudes remain model extrapolation')
        if fit.get('no_independent_mode_switch_required'):
            row['hardware_model_scope'] = ('Equal RGB curves use the existing shared-curve control; '
                'MOUNT interpolation and downstream colour response remain working models; '
                'no independent RGB amplitude acceptance is inferred')
    if row['recommendation'] not in ('replace_candidate', 'add_candidate'):
        return
    summary = read(HERE/'exact_confirmation_summary.json')
    matches = [r for r in summary['profiles']
        if (r['unit'], r['index']) == (row['unit'], row['index'])
        and (row['record_sha256'] in (r['source_record_sha256'], r['exact_record_sha256'])
             or fit.get('canonical_equivalence_parent') == r['exact_fit'])]
    assert matches, ('Accepted record lacks exact confirmation', row['unit'], row['index'])
    proof = min(matches, key=lambda r: (r['exact_objective'], r['exact_fit']))
    exact = read(HERE/proof['exact_fit'])
    assert sha(HERE/proof['exact_fit']) == proof['exact_fit_sha256']
    assert exact['backend'] == 'fast' and exact['exact_confirmation_solver_attempts'] == 1
    assert exact['objective'] <= proof['source_objective']+1e-9
    assert proof['target_sha256'] == fit['target_sha256']
    row['exact_confirmation'] = proof
    row['exact_confirmation_certified_record_sha256'] = row['record_sha256']
    row['exact_confirmation_via_canonical_equivalence'] = row['record_sha256'] not in (
        proof['source_record_sha256'], proof['exact_record_sha256'])


def bind_registry(registry):
    for name in ('solver_provenance', 'exact_confirmation_summary', 'mount_ramp_scope_summary'):
        registry[name+'_sha256'] = sha(HERE/(name+'.json'))
    registry['all_build_candidates_exact_confirmed'] = True
    registry['MOUNT_continuous_full_colour_accepted_intervals'] = []
    registry['main_solver_config_switch'] = 'Completed exact batches preserved; unstarted batches use guarded_normal; L1 uses delivered exact fallback; unit failures force exact'


def sections(registry):
    lines = ['', '## 求解批次与逐候选精确确认', '',
        '已完成批次保持原求解器。切换通知后的新批次用guarded_normal、plain factor配置；交付引擎在L1调用精确回退，本任务没有启用未验收的L1近似分解，也不据此声称得到整轮1.8倍提速。solver_provenance.json逐批列配置、实际路径与失败回退。MOUNT接入曾发生回执目录错误，数值检查通过后仍按用户规则保守回退exact。',
        '下表每条构建候选都另有一次从候选整数记录出发的exact拟合。按相同冻结训练目标和护栏计算，保留原候选及确认记录，不按照片留出挑参数。精确确认若改善guarded_normal候选的训练目标，该单元后续求解回退exact；已完成批次保留。全部组别和目标函数见exact_confirmation_scores.csv，记录和回执SHA见candidate_registry.json。', '',
        '| 单元及配方，电脑预测 | 原候选训练% | exact确认训练% | 原候选主要留出% | exact确认主要留出% |',
        '| --- | --- | --- | --- | --- |']
    def f(value):
        return '—' if value is None else f'{value:.2f}'
    for row in registry:
        if row['recommendation'] not in ('replace_candidate', 'add_candidate'):
            continue
        proof = row['exact_confirmation']
        group = 'synthetic' if row['unit'] == 'a12-28' else 'photo_iso200'
        scores = [proof['source_scores']['train'], proof['exact_scores']['train'],
                  proof['source_scores'][group], proof['exact_scores'][group]]
        lines.append('| '+' | '.join([row['unit']+' '+row['name'],
            *[f(s['candidate']['similarity_percent']) for s in scores]])+' |')
    provenance = read(HERE/'solver_provenance.json')
    for fallback in provenance['unit_fallbacks']:
        lines += ['', fallback['unit']+'回退exact：'+fallback['reason']+'。回执为'+fallback['receipt']+'。']
    ramp = read(HERE/'mount_ramp_scope_summary.json')
    lines += ['', '## 密集灰阶的离散实测与外推', '',
        'FIELD_20261103_RAMP.md第144行起的结论优先于先前上午和曝光阶梯诊断。正式8对RAW+JPG用于分析，参考8对不混入实测。节点16、+2、ISO200、同一手动M镜头f/5.6的已采灰点有可复现局部响应；没有全颜色定量验收通过的连续亮度区间。',
        'RAW_WB端点为R约585–752、G约578–758、B约590–773。端点之间的空档、其他色相、其他节点、负向和更大扰动都属模型外推。分段线性只是工作假设；没有改成节点保持，没有重标节点位置或曲线单位。',
        f'肤色R扰动共有{ramp["skin_R_points"]}个测点，其中{ramp["skin_R_Cb_opposite_sign_points"]}个Cb方向与模型相反。局部灰阶校准未通过有色留出，不对全局RGB幅度、G曲线或固定色度矩阵作修正。',
        'mount_ramp_scope_summary.json按配方列出落入RAW端点包络内外的电脑收益分组。包络内比例只用于定位模型依赖，不代表端点间空档或色相已验收。对所有修改后的完整L1候选，定量实测支持仍不足以覆盖整条曲线，整档效果按电脑预测处理。', '',
        '| 通道 | 已采受激灰点数 | RAW_WB最小值 | RAW_WB最大值 | 相邻实测点最大空档 | 全颜色连续验收区间 |',
        '| --- | --- | --- | --- | --- | --- |']
    for row in ramp['sampled_control_evidence']:
        lines.append('| '+' | '.join(map(str, [row['channel'], row['active_grey_points'],
            round(row['RAW_WB_min'], 2), round(row['RAW_WB_max'], 2),
            round(row['largest_RAW_WB_gap_between_active_samples'], 2), '无']))+' |')
    lines += ['', '后续机主素材为负向扰动、有色块和多节点探针；R当前采样空档仍需补点。50mm补原厂04自然RAW+JPG，28mm有素材后再标定。1894至1900的自然场景实际光圈未知，不能套用屏幕探针f/5.6。']
    return lines
