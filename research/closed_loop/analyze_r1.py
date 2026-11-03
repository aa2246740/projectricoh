#!/usr/bin/env python3
"""Reproduce round-one summaries, ISO sensitivity, drift and the public report."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import copy
from collections import Counter
import numpy as np
from common import HERE, LOCAL, Provenance, read, dump, require, sha, mount_guard
from model import Engine
from measure import score_record, summarize_slot, stats, similarity
from targets import Targets


def unscored(frame):
    result = copy.deepcopy(frame)
    for patch in result['patches']:
        patch['flags'] = [v for v in patch['flags'] if v != '04-inverse-out-of-support']
    return result


def subset(measurement, frames):
    result = copy.deepcopy(measurement)
    result['frames'] = frames
    result['eligible_for_refit'] = bool(frames) and all(f['eligible_for_refit'] for f in frames)
    require(all(f['meta']['iso'] == 200 and f['measurement_valid'] for f in frames), '只导出合格 ISO 200 组')
    result['slots'] = {slot: summarize_slot([f for f in frames if f['slot'] == slot])
                       for slot in sorted({f['slot'] for f in frames})}
    result['metadata_checks'] = {s: measurement['metadata_checks'][s] for s in {f['set'] for f in frames}}
    result['sets'] = {s: measurement['sets'][s] for s in result['metadata_checks']}
    result['subset_rule'] = 'same-set camera frames; ISO 200 only; ISO 800 excluded from refit'
    return result


def drift(engine, baseline, repeat):
    mask = np.asarray(baseline['valid']) & np.asarray(repeat['valid'])
    raw0, raw1 = np.asarray(baseline['raw_wb']), np.asarray(repeat['raw_wb'])
    u0, u1 = raw0 @ [.25, .5, .25], raw1 @ [.25, .5, .25]
    ev = np.log2(u1/u0)
    grey = np.array([q['gray'] for q in baseline['patches']])
    direct = engine.fs.delta_e00(engine.fs.lab_from_codes(baseline['rgb']),
                                engine.fs.lab_from_codes(repeat['rgb']))
    return {'frames': [baseline['id'], repeat['id']], 'jpeg_repeat_de00': stats(direct[mask]),
            'raw_exposure_EV': stats(ev[mask]), 'grey_raw_exposure_EV': stats(ev[mask & grey]),
            'repeat_after_DNG_exposure_model_de00': stats(np.asarray(repeat['model_de00'])[mask]),
            'raw_exposure_EV_min': float(ev[mask].min()),
            'raw_exposure_EV_max': float(ev[mask].max()),
            'is_independent_stock_model_validation': False}


def iso_sensitivity(measurement, hook_paths, provenance):
    physical = {f['id']: unscored(f) for f in measurement['frames'] if f['set'] == 'physical'}
    scores = {}
    for iso in (200, 1600):
        engine = Engine(physical['physical04']['model']['table'], iso, provenance)
        for kind in ('interpolated', 'firmware'):
            target = Targets(engine, provenance, hook_paths[iso] if kind == 'firmware' else None)
            scores[kind, iso] = {}
            for fid, original in physical.items():
                frame = score_record(engine, target, unscored(original), unscored(physical[original['baseline']]))
                frame['iso_status'] = 'ISO 800 未标定；此处只更换 ISP 模型'
                frame['measurement_valid'] = frame['eligible_for_refit'] = False
                scores[kind, iso][fid] = frame
    rows, invariant = [], {}
    for kind in ('interpolated', 'firmware'):
        for slot in ('01', '02'):
            pair = [scores[kind, iso]['physical'+slot] for iso in (200, 1600)]
            common = np.asarray(pair[0]['valid']) & np.asarray(pair[1]['valid'])
            summaries = {}
            for iso, frame in zip((200, 1600), pair):
                matched = copy.deepcopy(frame)
                matched['valid'] = common
                summaries[str(iso)] = summarize_slot([matched])
            rows.append({'target_kind': kind, 'slot': slot, 'common_patches': int(common.sum()),
                'models': summaries,
                'target_shift_iso200_vs_1600': stats(
                    engine.fs.delta_e00(pair[0]['target_lab'], pair[1]['target_lab'])[common]),
                'model_shift_iso200_vs_1600': stats(engine.fs.delta_e00(
                    engine.fs.lab_from_codes(pair[0]['model_rgb']), engine.fs.lab_from_codes(pair[1]['model_rgb']))[common])})
    for slot in ('05', '06'):
        a, b = [scores['interpolated', iso]['physical'+slot] for iso in (200, 1600)]
        delta = engine.fs.delta_e00(a['target_lab'], b['target_lab'])
        require(float(np.max(delta)) == 0., '05/06 目标意外依赖 ISP 模型')
        invariant[slot] = {'target_shift_de00_max': float(np.max(delta)), 'patches': len(delta)}
    return {'captured_iso': 800, 'is_calibration': False, 'common_mask_used': True,
            'rows': rows, 'fuji_target_invariance': invariant}


def number(value, digits=2):
    return '不定义' if value is None else f'{value:.{digits}f}'


def percent(value):
    return '不定义' if value is None else f'{100*value:.1f}%'


def compact_stats(value):
    return ' / '.join(number(value[k]) for k in ('median', 'p90', 'max'))


def stats_table(lines, measurement, slots=None):
    lines += ['| 组 / 槽 | 有效 / 总块数 | 实拍→目标，中位 / p90 / 最大 | <1 / <2 / <3 | 相似度 | 实拍↔模型，中位 / p90 / 最大 |',
              '|---|---:|---:|---:|---:|---:|']
    for group in ('screen', 'physical'):
        for slot, q in measurement['sets'][group].items():
            if slots and slot not in slots:
                continue
            a = q['measured_vs_target']
            total = a['n']+q['excluded_patches']
            shares = ' / '.join(percent(a[f'share_under_{k}']) for k in (1, 2, 3))
            lines.append(f'| {group} / {slot} | {a["n"]} / {total} | {compact_stats(a)} | {shares} | '
                         f'{percent(q["similarity"]["value"])} | {compact_stats(q["model_vs_measured"])} |')


def concentration(lines, measurement, slots=None):
    lines += ['| 组 / 槽 | 目标误差最高的色相箱 | 目标误差最高的明度箱 | 最差有效颜色，ΔE00 |',
              '|---|---|---|---|']
    for group in ('screen', 'physical'):
        for slot, s in measurement['sets'][group].items():
            if slot == '04' or slots and slot not in slots:
                continue
            hues = sorted((q for q in s['per_hue'] if q['n']), key=lambda q: q['median'], reverse=True)[:2]
            light = sorted((q for q in s['per_lightness'] if q['measured_vs_target']['n']),
                           key=lambda q: q['measured_vs_target']['median'], reverse=True)[:2]
            hue_text = '；'.join(f'{q["hue_start_deg"]}–{q["hue_start_deg"]+15}° '
                                 f'{q["median"]:.2f}，n={q["n"]}' for q in hues)
            light_text = '；'.join(f'L* {q["Lstar_start"]}–{q["Lstar_start"]+10} '
                                   f'{q["measured_vs_target"]["median"]:.2f}，n={q["measured_vs_target"]["n"]}' for q in light)
            worst = '；'.join(f'{q["patch"]} {q["colour"]} {q["de00"]:.2f}' for q in s['worst_colours'][:3])
            lines.append(f'| {group} / {slot} | {hue_text} | {light_text} | {worst} |')


def write_report(analysis, measured, firmware):
    lines = ['# 2026-10-21 闭环测量第 1 轮', '',
        '14 帧完整测量已完成。06 实体卡的 JPEG 色序误判已修复；ISO 800 实体卡仅作诊断，回拟资格只给 ISO 200 屏幕组。'
        '现用表在屏幕有效色块上的实拍↔模型中位误差为 0.08–0.59 ΔE00，足以作为同条件、小步回拟的局部响应模型。'
        'GR 测光锚仍未确定，尚不能认定 01/02 的固件模型目标是真实 GR 相机输出，也不能宣称达到原机 95% 相似。', '',
        '## 输入和证据范围', '',
        '本轮读已有照片，没有接触相机、SD 卡或其他卷，也没有 Git 提交。照片、LUT、固件派生数组、目标回填和候选数据均留在 Git 忽略的 `local/`。'
        '写入前已核实 `/Volumes/Workspace` 为可写 APFS，UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，并运行 `df -h /Volumes/Workspace`。', '',
        '- 相机与安装表按已验证事实采用：GXR 2j、A12 50mm、tables-v4r3-probe；DEEPTBL SHA-256 为 `c4ba8cdb6564fb9e211428675dabc2f277a1dcc748cd2cecbe14837bacbed6a8`。',
        '- 屏幕组是 R8051198–1204，ISO 200，色环；实体卡组是 R8051207–1213，ISO 800，DIOPTIX CC24、室内光。两组都按 04/01/02/03/05/06/04b 拍摄。',
        '- 两组均为 M 档、1/60 s、f/4、手动白平衡；本轮测量的组内元数据检查通过。失误多拍的 `extra-iso200-chart/` 未进入 14 帧清单。',
        '- 帧路径、哈希、标签、配准、逐块数据在 `local/m20261021_r1.json`；公开报告只列统计和颜色名称。', '',
        '## 朝向检查修复', '',
        '`measure.py` 原先对所有彩色槽强制检查 JPEG 的蓝、青顺序。R8051212 中，06 把青色渲染得比蓝色更蓝，'
        '所以 JPEG 检查失败，RAW 灰阶和配准均通过。现改为读取本帧 DNG 的底行白到黑顺序，并要求前五个灰块的 R/G、B/G 偏差不超过 15%。'
        '非 04 槽的 JPEG 色序只记警告，04 保留原有 JPEG 硬检查；DNG/JPEG 配准仍是有效测量的必要条件。', '',
        '回归测试先在旧代码复现 physical06 失败，再验证修复后通过。使用本帧实际 RAW 色块重排的 90°、180°、270° 旋转及水平、垂直镜像均被拒绝；'
        '这覆盖朝向判断，不冒充新拍了一张旋转色卡。现有函数签名未变，prelim 文件保持原样。', '',
        '## 原有目标下的结果', '',
        '所有误差都是 ΔE00，阈值比例用严格小于。screen 为屏幕组，physical 为实体卡组。表中 04 汇总首尾两张控制帧，'
        '因此总块数是单帧的两倍；04 的目标就是自身反算所得的原厂响应，接近零不是独立模型验收。实体卡各行均标记为“ISO 800 未标定”，模型列默认借用 ISO 200 模型。', '',
        '相似度按任务公式 `1 − median(实拍→目标) / median(同组04→对应目标)` 计算，分子分母使用同一批有效标签。'
        '它表示相对 04 的误差缩减率；分母小于 0.25 时不定义，不是原机照片相似百分比。', '']
    stats_table(lines, measured)
    lines += ['', '原有目标中，01/02 的实体卡按标签转移 GR III 照片相对效果，屏幕按色相插值；03 使用 GR IV HC 平坦块近邻目标；'
              '05/06 使用 DNG 场景色度、冻结中灰锚和官方 Fuji LUT。', '',
              '## ISO 800 的边界与敏感度', '',
              '实体卡仍报告实拍→目标，`target_measurement_valid=true` 只表示拍摄条件和数据检查通过。'
              '`measurement_valid=false`、`eligible_for_refit=false` 明确阻止它进入回拟。'
              '完整 14 帧文件的总回拟标记为 false；另导出的 screen_refit 文件只含 7 张 ISO 200 屏幕帧。', '',
              '05/06 的目标链不依赖 ISP。`Targets.render` 直接用本帧 DNG 的 XYZ；`scene_scale` 用同组 04 的 DNG 灰块响应和冻结的 `u_m`、黑位偏移定比例。'
              '它不用 04 JPEG 反算、不调用 `Engine.predict`，也不使用 ISO 模型参数。把 ISP 调用替换为抛错对象，目标仍可生成；'
              'ISO 200、1600 两套模型下，两个槽全部 24 块的目标逐值相同，最大目标位移为 0。'
              '但默认测量的 04 反算筛选、坐标明度和实拍↔模型列依然依赖 ISP，不能把这几层也称为 ISO 800 已标定。', '',
              '01/02 需要反算 04。下表固定实拍和共同有效标签，分别借用 ISO 200、1600 模型；这只是敏感度，不是 ISO 800 标定，也不作两模型间线性插值。', '',
              '| 目标 / 槽 | 模型 ISO | 共同有效块 | 实拍→目标，中位 / p90 / 最大 | 相似度 | 实拍↔模型，中位 / p90 / 最大 | 两模型目标位移，中位 / 最大 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for row in analysis['iso800_sensitivity']['rows']:
        kind = '旧相对目标' if row['target_kind'] == 'interpolated' else 'GR 固件目标'
        shift = row['target_shift_iso200_vs_1600']
        for iso, q in row['models'].items():
            lines.append(f'| {kind} / {row["slot"]} | {iso} | {row["common_patches"]} | '
                         f'{compact_stats(q["measured_vs_target"])} | {percent(q["similarity"]["value"])} | '
                         f'{compact_stats(q["model_vs_measured"])} | {number(shift["median"],3)} / {number(shift["max"],3)} |')
    lines += ['', '## GR 固件模型目标与旧目标并排', '',
              '`firmware_targets.py` 消费今天的 target_requests，回填两槽实拍及同组 04 共 8 项，每项包含 −0.3、0、+0.3 EV，'
              '并用槽位、标签及 DNG 哈希绑定输入。随后通过 `measure.py --targets` 重测完整 14 帧。', '',
              '新目标复用 `gr_round5/gr_targets.py` 的固件矩阵组合、曲线和 GR 相对效果数值方法。'
              '本帧 DNG XYZ 按冻结 GXR 中灰曝光锚还原场景，再投影为 GR 相机 RGB，分别渲染 Standard 与 Positive/Negative，'
              '把亮度差、色度比和色相差应用到同组实测 04 的 DNG 驱动响应上。整条实测目标路径不构造或调用 Nominal04。'
              '零 EV 明确沿用冻结 GXR `u_m` 场景比例与 bastibe GR 灰阶场景比例，不代表已测得两机的测光对应关系。', '',
              '已验证的 bastibe DNG 相对效果误差 01/02 为 0.3068/0.4200 ΔE00，这里直接采用既有验证；'
              '该精度不能直接转移给今天的跨相机 DNG 场景投影。冻结报告中，场景反投影本身的中位误差约为 0.84/1.00 ΔE00。'
              'MultiAxial、局部 ToneControl 和最终色域处理未进入模型，新目标仍是 surrogate。', '',
              '| 组 / 槽 | 旧目标中位 / p90 | GR 固件目标中位 / p90 | 旧相似度 | GR 相似度 |',
              '|---|---:|---:|---:|---:|']
    for group in ('screen', 'physical'):
        for slot in ('01', '02'):
            old, new = measured['sets'][group][slot], firmware['sets'][group][slot]
            lines.append(f'| {group} / {slot} | {number(old["measured_vs_target"]["median"])} / {number(old["measured_vs_target"]["p90"])} | '
                         f'{number(new["measured_vs_target"]["median"])} / {number(new["measured_vs_target"]["p90"])} | '
                         f'{percent(old["similarity"]["value"])} | {percent(new["similarity"]["value"])} |')
    lines += ['', '两种目标使用相同有效标签；本轮 GR 相机 RGB 支持范围检查没有额外排除色块。'
              '01 屏幕的中位误差变大而相似度上升，原因是 04→目标的分母也随目标改变，不能把相似度上升解释为实拍变好了。'
              '02 屏幕中位略降但 p90 上升，也不构成全面改善。以下为新目标的完整统计。', '']
    stats_table(lines, firmware, ('01', '02'))
    lines += ['', 'GR 测光锚仍未确定。以下固定实拍 JPEG，只把目标和模型的线性输入乘以 `2**EV`。'
              '默认固定 0 EV，没有选误差最小的一行，也没有把 ±0.3 EV 当作置信区间或未知锚点的完整范围。', '',
              '| 组 / 槽 | 目标 | EV | 实拍→目标，中位 / p90 | 相似度 |', '|---|---|---:|---:|---:|']
    for group in ('screen', 'physical'):
        for slot in ('01', '02'):
            for kind, result in [('旧目标', measured), ('GR 固件', firmware)]:
                for row in result['sets'][group][slot]['gr_anchor_sensitivity']['rows']:
                    a = row['measured_vs_target']
                    lines.append(f'| {group} / {slot} | {kind} | {row["anchor_delta_EV"]:+.1f} | '
                                 f'{number(a["median"])} / {number(a["p90"])} | {percent(row["similarity"]["value"])} |')
    lines += ['', '## 首尾 04 的漂移', '',
              '直接 JPEG 差反映整组首尾总变化；DNG EV 是同标签 RAW 响应比的 log2，不能只凭它把原因归给照明或快门。'
              '最后一列用本帧 DNG 响应修正曝光后再看模型残差。', '',
              '| 组 | 首尾 JPEG ΔE00，中位 / p90 / 最大 | 全部 RAW EV，中位 / 最小 / 最大 | 灰块 RAW EV 中位 | DNG 修正后残差，中位 / p90 / 最大 |',
              '|---|---:|---:|---:|---:|']
    for group, q in analysis['drift'].items():
        lines.append(f'| {group} | {compact_stats(q["jpeg_repeat_de00"])} | {number(q["raw_exposure_EV"]["median"],3)} / '
                     f'{number(q["raw_exposure_EV_min"],3)} / {number(q["raw_exposure_EV_max"],3)} | '
                     f'{number(q["grey_raw_exposure_EV"]["median"],3)} | {compact_stats(q["repeat_after_DNG_exposure_model_de00"])} |')
    lines += ['', '## 误差集中在哪里', '',
              '色相取各帧 DNG 的 D65 Lab，灰块不进入色相箱；明度是该帧 DNG 驱动的 04 等效 L*。'
              '每箱列中位误差和样本数，实体卡单点箱只作定位。以下先列旧目标；每槽完整 24 个色相箱、10 个明度箱及模型误差二维图均在 local 结果中。', '']
    concentration(lines, measured)
    lines += ['', 'GR 固件目标改变了 01/02 的误差分布。', '']
    concentration(lines, firmware, ('01', '02'))
    lines += ['', '有效块筛选可能隐藏大误差，因此同时保留包含被标记色块的统计。', '',
              '| 组 / 槽 | 排除块数 | 主要排除原因，按标记计数 | 含标记全部色块，中位 / p90 / 最大 |', '|---|---:|---|---:|']
    for group in ('screen', 'physical'):
        for slot, q in measured['sets'][group].items():
            if slot == '04':
                continue
            reasons = analysis['exclusion_reasons'][group+':'+slot]
            reason = '；'.join(f'{k} {v}' for k, v in reasons.items()) or '无'
            lines.append(f'| {group} / {slot} | {q["excluded_patches"]} | {reason} | {compact_stats(q["all_patches_including_flagged"])} |')
    lines += ['', '03 的“超出近邻支持范围”是目标参考不足；同一块可能同时触发多个标记，原因计数不能直接相加。'
              'physical03 即使有效块中位只有 1.55，p90 仍达 11.10，不能只用中位数判它通过。', '',
              '## 模型是否能用于回拟', '',
              '可以把 ISO 200 屏幕组用于局部回拟。01/02/03/05/06 的模型中位误差分别约 0.43/0.34/0.08/0.34/0.59，'
              'p90 分别约 0.93/0.57/0.29/0.69/1.29；06 的有效块最大误差为 2.49，仍需保留现有实拍偏差修正。'
              '这些是现用 DAT 在今天输入处的模型验证，不能证明改表后的 Jacobian、跨曝光或跨光源泛化。'
              '01/02 的目标方向还受 GR 曝光锚和场景投影误差影响；03 受近邻目标支持范围与尾部误差限制。', '',
              'ISO 800 实体卡只作留出诊断。05/06 的直接 DNG→LUT 目标不依赖 ISP，并不免除场景颜色矩阵、曝光锚与官方 LUT passthrough 的假设。'
              'screen_refit 保留原有目标；另有 screen_refit_gr 供比较新 GR 目标，不能通过换目标或选 EV 宣称新配方实拍通过。'
              '本轮没有为今天实拍生成或接受候选表，下一轮仍需新表实拍才能闭环验收。', '',
              '## 测试槽，采用已验证事实', '',
              '- T1（08）功能通过。最佳 absolute_CBD，绝对语义为 R←C、G←B5 主表、B←D；残差 1.14 码，次选 no_effect 为 32.2 码。离开 08 后，04 灰块恢复到 ±2 码内，最大 1.19；关机重开无 `!4`。原输出为 `research/t1_probe/probe2/local/run_20261021/`。',
              '- T3（07）符合候选 H1，即 2×2 布局、1/32 尺度：`Cb_out=(a*Cb+b*Cr)/32`，`Cr_out=(c*Cb+d*Cr)/32`。残差 0.65 码，次选 H3_half 为 2.12 码；扇区 11、17 的尺度为 1.00、0.98，04 恢复通过。原输出为 `research/t3_probe/local/run_20261021/`。', '',
              '## 复跑与交付', '',
              '以下命令均从仓库根目录运行。完整 14 帧测量退出码为 2 是保留 ISO 800 后的预期结果，表示整份文件不能直接回拟，不表示少测了帧。'
              '无需重新 bootstrap，也不要覆盖 prelim。', '', '```sh',
              'export TMPDIR="$PWD/research/closed_loop/local/tmp"',
              'python3 -I -B research/closed_loop/measure.py research/closed_loop/local/frames_20261021.json --out research/closed_loop/local/m20261021_r1.json',
              'python3 -I -B research/closed_loop/firmware_targets.py --requests research/closed_loop/local/m20261021_r1_target_requests.json --measurement research/closed_loop/local/m20261021_r1.json --out research/closed_loop/local/gr_targets_20261021_r1.json',
              'python3 -I -B research/closed_loop/firmware_targets.py --requests research/closed_loop/local/m20261021_r1_target_requests.json --measurement research/closed_loop/local/m20261021_r1.json --physical-model-iso 1600 --out research/closed_loop/local/gr_targets_20261021_r1_iso1600.json',
              'python3 -I -B research/closed_loop/measure.py research/closed_loop/local/frames_20261021.json --targets research/closed_loop/local/gr_targets_20261021_r1.json --out research/closed_loop/local/m20261021_r1_gr.json',
              'python3 -I -B research/closed_loop/analyze_r1.py --write-report',
              'python3 -I -B research/closed_loop/tests/test_r1.py',
              'python3 -I -B research/closed_loop/tests/test_closed_loop.py',
              'python3 -I -B research/closed_loop/verify_delivery.py --write-sums',
              'python3 -I -B research/closed_loop/verify_delivery.py', '```', '',
              '分析脚本输出 `local/m20261021_r1_analysis.json`、两份仅含屏幕组的 `local/m20261021_r1_screen_refit*.json`，'
              '并可重建本报告。输入保护快照在 `local/tmp/r1_before.json`，prelim 和只读源保持不变；公开及本地校验和分别为 `SHA256SUMS`、`local/SHA256SUMS`。'
              '6 项 R1 回归及原有 10 项行为测试通过。R1 回归还把 Nominal04 替换为抛错函数后重新生成 GR 目标，'
              '并确认与交付文件逐字节相同；公开数据扫描测试拒绝 48 字节串，允许普通 32 字节 SHA-256。'
              '日志位于 `local/tmp/test_r1.log`、`local/tmp/test_closed_loop.log`；'
              '交付验证写入 `local/delivery_verification.json`。', '']
    (HERE / 'REPORT_R1.md').write_text('\n'.join(lines))


def run(write_public=False):
    mount_guard()
    p = Provenance()
    measured = read(p.add(LOCAL / 'm20261021_r1.json'))
    firmware = read(p.add(LOCAL / 'm20261021_r1_gr.json'))
    require(len(measured['frames']) == len(firmware['frames']) == 14, '必须完整测量 14 帧')
    frames = {f['id']: f for f in measured['frames']}
    hook_paths = {200: LOCAL / 'gr_targets_20261021_r1.json', 1600: LOCAL / 'gr_targets_20261021_r1_iso1600.json'}
    drifts = {}
    for group in ('screen', 'physical'):
        base, repeat = frames[group+'04'], frames[group+'04b']
        drifts[group] = drift(Engine(base['model']['table'], base['meta']['iso'], p), base, repeat)
    sensitivity = iso_sensitivity(measured, hook_paths, p)
    reasons = {}
    for group in ('screen', 'physical'):
        for slot in ('01', '02', '03', '05', '06'):
            f = frames[group+slot]
            reasons[group+':'+slot] = dict(Counter(flag for q in f['patches'] for flag in q['flags']))
            unsupported = f['target_definition'].get('unsupported_patches', [])
            if unsupported:
                reasons[group+':'+slot]['target-out-of-support'] = len(unsupported)
    for group in ('screen', 'physical'):
        for slot in ('01', '02'):
            require(np.array_equal(measured['sets'][group][slot]['measured_vs_target']['n'],
                                   firmware['sets'][group][slot]['measured_vs_target']['n']), '比较两种 GR 目标的样本数不同')
            old = next(f for f in measured['frames'] if f['id'] == group+slot)
            new = next(f for f in firmware['frames'] if f['id'] == group+slot)
            require(np.array_equal(old['valid'], new['valid']), '比较两种 GR 目标必须使用同一有效掩码')
    result = {'schema': 'closedloop-round1-analysis/1', 'drift': drifts,
              'iso800_sensitivity': sensitivity, 'exclusion_reasons': reasons,
              'sets_interpolated': measured['sets'], 'sets_firmware': firmware['sets'],
              'provenance': p.finish()}
    dump(LOCAL / 'm20261021_r1_analysis.json', result)
    for name, data in [('m20261021_r1_screen_refit.json', measured),
                       ('m20261021_r1_screen_refit_gr.json', firmware)]:
        eligible = [f for f in data['frames'] if f['set'] in data['eligible_refit_sets']]
        dump(LOCAL / name, subset(data, eligible))
    if write_public:
        write_report(result, measured, firmware)
    print('R1 分析完成，14 帧齐全；ISO 800 敏感度已保存，仅 ISO 200 屏幕组可回拟。')
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    run(args.write_report)
