#!/usr/bin/env python3
"""Publish statistics and the two local candidates from independently reread tables."""
import os
for _key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[_key] = '1'
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location('gr5_finish_targets', HERE / 'gr_targets.py')
g = importlib.util.module_from_spec(sp)
sp.loader.exec_module(g)


def triple(d):
    return f"{d['median']:.4f} / {d['p90']:.4f} / {d['max']:.4f}"


def topic_statistics(slot, variant):
    d = g.Data(slot)
    f = g.read(g.LOCAL / f'{slot}_{variant}_fit.json')
    a, b = d.evaluate(d.current)['chart'], d.evaluate(f)['chart']
    topics = {'天空': ['A3'], '树叶': ['A4', 'C2'], '肤色': ['A1', 'A2'],
              '红色': ['B3', 'C3'], '黄绿色': ['B5'], '深蓝': ['B2', 'C1']}
    out = {}
    for name, labels in topics.items():
        idx = [d.meta['labels'].index(l) for l in labels]
        old, new = a['lab'][idx], b['lab'][idx]
        dl = new[:, 0]-old[:, 0]
        dc = np.linalg.norm(new[:, 1:], axis=1)-np.linalg.norm(old[:, 1:], axis=1)
        dh = (np.degrees(np.arctan2(new[:, 2], new[:, 1])-np.arctan2(old[:, 2], old[:, 1]))+180)%360-180
        out[name] = dict(mean_delta_L=float(dl.mean()), mean_delta_C=float(dc.mean()),
                         mean_delta_h_deg=float(dh.mean()), mean_delta_a=float((new[:, 1]-old[:, 1]).mean()),
                         mean_delta_b=float((new[:, 2]-old[:, 2]).mean()),
                         current_target_de00_median=float(np.median(a['error'][idx])),
                         candidate_target_de00_median=float(np.median(b['error'][idx])))
    return out


def plain_change(name, d):
    dl, dc, dh = d['mean_delta_L'], d['mean_delta_C'], d['mean_delta_h_deg']
    light = f"{'亮' if dl >= 0 else '暗'}约 {abs(dl):.2f} L*"
    saturation = f"色度{'增加' if dc >= 0 else '减少'}约 {abs(dc):.2f}"
    if name == '天空':
        direction = '略偏紫' if d['mean_delta_a'] > 0 else '略偏青'
    elif name == '树叶':
        direction = '黄味减轻' if d['mean_delta_b'] < 0 else '黄味增加'
    elif name == '肤色':
        direction = ('红味减少' if d['mean_delta_a'] < 0 else '红味增加')+'，'+('黄味减少' if d['mean_delta_b'] < 0 else '黄味增加')
    elif name == '红色':
        direction = '略偏橙' if d['mean_delta_b'] > 0 else '略偏品红'
    elif name == '黄绿色':
        direction = '略向绿移动' if dh > 0 else '略向黄移动'
    else:
        direction = '略偏紫蓝' if dh > 0 else '略偏青蓝'
    return f"{light}，{saturation}，{direction}。色块误差 {d['current_target_de00_median']:.2f} → {d['candidate_target_de00_median']:.2f}。"


def main():
    verify = g.read(g.LOCAL / 'verification.json')
    generator = g.read(g.LOCAL / 'generator.json')
    selected = verify['slots']
    metrics = {'schema': 'gr-round5-statistics-v1', 'evidence': 'host-model-only', 'firmware_ready': False,
               'effect_reproduced_definition': '1 - median(recipe_to_target_DE00) / median(stock04_to_target_DE00)',
               'same_definition_as': 'research/fidelity_ceiling/gr/analyze.py:effect',
               'fidelity_ceiling_denominator_audit': verify['fidelity_ceiling_denominator_audit'],
               'stock04_denominator': 'Actual neutralised stock04 rendering with stock input and output nodes',
               'input_integrity': verify['input_integrity'], 'original_checks': generator['original_checks'],
               'generator_validation': {s: v for s, v in generator['modes'].items()},
               'scene_exposure_scale': generator['scene_exposure_scale'],
               'neutral_scene_scale_statistics': generator['neutral_exposure_scale_spread'],
               'nominal04_fit_statistics': generator['nominal04_fit'],
               'auxiliary_colour_count': generator['auxiliary_count'],
               'minimum_aux_to_ring_linear_rgb_distance': generator['minimum_linear_rgb_distance_aux_to_ring'],
               'slots': selected, 'limitations': ['No camera acceptance', 'No independent photographs',
                   'Fixed DNG colourimetric approximation', 'MultiAxial and local ToneControl omitted',
                   'Ring checks and ISO model checks informed candidate selection',
                   'Slot01 uses both model grey constraints; ISO1600 is not fully held out']}
    downloads = g.read(g.LOCAL / 'downloads_verified.json')
    metrics['reference_downloads'] = [{k: r[k] for k in ('id', 'bytes', 'sha256', 'matches_manifest')} for r in downloads]
    for slot, record in selected.items():
        variant = record['variant']
        fit = g.read(g.LOCAL / f'{slot}_{variant}_fit.json')
        data = g.Data(slot)
        curves = g.fs.load_tables()[0]
        expected = curves['posi' if slot == '01' else 'nega']
        assert np.array_equal(expected[0], data.a['curve_x']) and np.array_equal(expected[1], data.a['curve_y'])
        curve_bytes = struct.pack('>31H', *data.a['curve_x'][1:-1].astype(int))+data.a['curve_y'].astype('u1').tobytes()
        fit.update(accepted=record['accepted'], status='Offline GR round5 candidate',
                   firmware_ready=False, T1_enabled=False, stage='v2-candidate',
                   decision='accept_host_gates' if record['accepted'] else 'reject_keep_current',
                   curve_sha256=hashlib.sha256(curve_bytes).hexdigest(),
                   curve_rows={'input31_u16': data.a['curve_x'][1:-1], 'output33_u8': data.a['curve_y']},
                   curve_unchanged=True, gate_vs_current={iso: m['gates'] for iso, m in record['models'].items()},
                   matrix_row2_note='Derived with matrix_model.row2_from_row1; no independent fitting',
                   iso1600_uses_grey_training_guard=(slot == '01'),
                   metrics={iso: m['candidate'] for iso, m in record['models'].items()})
        g.dump(g.LOCAL / f'fit_{slot}_r5.json', fit)
        record['candidate_sha256'] = g.sha(g.LOCAL / f'fit_{slot}_r5.json')
        record['plain_language_topic_statistics'] = topic_statistics(slot, variant)
    g.dump(HERE / 'metrics.json', metrics)

    verdict = '；'.join(f"{s} {'通过本轮主机门槛' if r['accepted'] else '未通过，保留现用配方'}" for s, r in selected.items())
    lines = ['# GR 配方第五轮：用固件补充颜色', '', '2026 年 10 月 21 日。'+verdict+'。两份候选均不等于已在相机上验收，也没有证据证明整体照片达到 95% 相似。', '',
             '本轮针对 GXR 机身 1.51 和 GR LENS A12 50mm 单元 1.51，只研究 01 Positive 与 02 Negative。01 基线是 round 3 的 `01_gr_positive/local/fit.json`；02 按任务指定，以 `02_gr_negative/round4/local/fit_v4_noT1.json` 为基线。后者历史文件里的接受标记不改变本轮的比较对象。', '',
             '## 颜色有没有变准', '',
             '下面均为 ΔE00，越低越好。每格依次是中位、p90、最大值。留一是藏起一个照片色块再预测；p90 表示九成样本不超过这个误差。旧插值环沿用 18 色的色相插值，固件合成环由本轮模型重新生成。它们是两个目标，不能互相替代。', '']
    for iso in ('200', '1600'):
        lines += [f'### ISO {iso} 模型', '', '| 配方 | 照片色块留一，18 点 | 旧插值环，144 色 | 固件合成环，144 色 | 照片灰阶，6 点 |',
                  '| --- | --- | --- | --- | --- |']
        for slot, record in selected.items():
            model = record['models'][iso]
            for key, label in [('current', '现用'), ('candidate', '第五轮')]:
                m = model[key]
                lines.append(f"| {slot} {label} | {triple(m['loo'])} | {triple(m['hue_interpolated_ring'])} | {triple(m['synthetic_target_ring'])} | {triple(m['grey'])} |")
        lines += ['']
    for slot, record in selected.items():
        failed = [f"ISO {iso} 的 {name}" for iso, m in record['models'].items() for name, passed in m['gates'].items() if not passed]
        lines.append(f"{slot}："+('全部检查通过。' if not failed else '没有通过 '+ '、'.join(failed)+'。候选保留供研究，不替换现用表。'))
    lines += ['', '01 另保护深、浅肤色。下表是完整整数配方在两套模型里的结果；这项保护不等于已经验证不同人物和光源。', '',
              '| 模型 | 色块 | v1 加 0.3 上限 | 现用 | 第五轮 |', '| --- | --- | --- | --- | --- |']
    for iso, model in selected['01']['models'].items():
        for label, s in model['skin_protection'].items():
            lines.append(f"| ISO {iso} | {label} | {s['limit']:.4f} | {s['current']:.4f} | {s['candidate']:.4f} |")
    lines += ['', '## 离 95% 还有多远', '',
              '这里的“效果复现率”沿用 fidelity_ceiling：1 减去配方中位误差与原厂 04 中位误差的比值。它描述削掉了多少目标误差，不是人眼认定的照片相似百分比。两种环的分母各用自己的目标，不能直接横比。', '',
              '| 配方 | 18 色照片，训练内 | 照片留一 | 旧插值环 | 固件合成环 |', '| --- | --- | --- | --- | --- |']
    for slot, record in selected.items():
        model = record['models']['200']
        for key, label in [('current', '现用'), ('candidate', '第五轮')]:
            f = model[key]['effect_reproduced']
            lines.append(f"| {slot} {label} | {f['chart_colour']:.1%} | {f['loo']:.1%} | {f['hue_interpolated_ring']:.1%} | {f['synthetic_target_ring']:.1%} |")
    lines += ['', '复现率与 fidelity_ceiling 使用同一公式，但本轮核对到其 01 分母有一个节点混用：`gr/analyze.py:161` 把 stock 的 33 个输出交给 `02_gr_negative/round4/run_round4.py:169`，后者仍按 Positive 输入节点插值，26 个输入节点与真实 stock 不同。旧写法的照片彩色分母为 6.089715，真实 04 链为 6.359878。本表使用真实 04；下表另列旧写法兼容值，便于直接对照既有报告。02 的两套节点相同，没有这项差别。原文件只读，代码快照及哈希保存在 local/ceiling_denominator_sources/。', '',
              '| 01 与旧报告兼容口径 | 照片色卡 | 照片留一 | 旧插值环 |', '| --- | --- | --- | --- |']
    for key, label in [('current', '现用'), ('candidate', '第五轮')]:
        f = selected['01']['models']['200'][key]['effect_reproduced_fidelity_ceiling_compat']
        lines.append(f"| {label} | {f['chart_colour']:.1%} | {f['loo']:.1%} | {f['hue_interpolated_ring']:.1%} |")
    lines += ['', '第五轮没有让每个颜色都更接近：两份完整配方在训练色卡上的中位误差都比现用表高。接受判据依照任务，优先看照片留一和两个环，并保住 p90、灰阶、肤色及模型约束。不能把某个合成环的进步写成“照片全面更像”。', '',
              '## 拍什么会看出变化', '', '以下都是主机模型的推断，比较第五轮候选与现用配方；若候选被拒绝，表内只是解释候选，不是换配方建议。色度是颜色浓淡的量值，L* 是明暗的量值。', '',
              '| 题材 | 01 Positive | 02 Negative |', '| --- | --- | --- |']
    for name in ('天空', '树叶', '肤色', '红色', '黄绿色', '深蓝'):
        a = selected['01']['plain_language_topic_statistics'][name]
        b = selected['02']['plain_language_topic_statistics'][name]
        lines.append(f"| {name} | {plain_change(name, a)} | {plain_change(name, b)} |")
    lines += ['', '## 合成目标本身有多可靠', '',
              '本轮重新下载了 bastibe 的 Target.DNG、Standard、Positive Film、Negative Film。四份 SHA-256 都与原清单一致，72 个 JPEG 色块均值、24 个 RAW 色块均值也重新算过并与冻结记录吻合。', '',
              '下表比较合成目标与原照片目标，仍是中位 / p90 / 最大 ΔE00。第一行直接用实测 DNG 色块，只检查固件模型；第二行从标准场景色反推 GR 相机 RGB；第三行再加入 GXR 近似底色，误差最大。', '',
              '| 验证步骤，18 色 | 01 | 02 |', '| --- | --- | --- |']
    for key, label in [('raw_relative_only', '实测 DNG，只转相对效果'), ('scene_relative_only', '场景色反推，只转相对效果'), ('full_with_nominal04', '加上 GXR 近似底色')]:
        lines.append(f"| {label} | {triple(generator['modes']['01']['validation'][key])} | {triple(generator['modes']['02']['validation'][key])} |")
    lines += ['', '结论是可以作辅助训练，不能代替照片。01 的 144 色总权重为 18，02 为 4.5；每个真实色卡点权重为 1，总权重 24。02 在较高辅助权重下，ISO 1600 的留一和旧环 p90 未过线，因此检查了更低权重。各合成点还按相近色相的目标误差降权；留一时，藏起的目标也从这项权重计算中移除。', '']
    patch_names = dict(A1='深肤色', A2='浅肤色', A3='天空', A4='树叶', A5='蓝花', A6='青绿',
                       B1='橙色', B2='紫蓝', B3='淡红', B4='紫色', B5='黄绿', B6='橙黄',
                       C1='深蓝', C2='绿色', C3='红色', C4='黄色', C5='洋红', C6='青色')
    for slot in ('01', '02'):
        uncertain = generator['modes'][slot]['uncertain_chart_hues'][:4]
        names = '、'.join(patch_names[r['label']]+f"（{r['target_difference_de00']:.2f}）" for r in uncertain)
        lines.append(f"{slot} 场景反推最不确定的色块是 {names}。这些是实测残差排名；不能仅凭颜色位置就断言是 MultiAxial 造成的。")
    lines += ['', '固件里的 MultiAxial 硬件像素处理和局部 ToneControl 没有进入模型。高饱和边缘、深蓝、极亮或极暗颜色、不同光源的泛化仍未知。参考照片只有一组；色环和模型检查也参与过选型，不是新照片的盲测。', '',
              '## 曲线与颜色顺序', '',
              '两份候选完整保留各槽现有曲线，没有 T，也没有三条独立通道曲线。只调 Y 行的两个自由度和 24 个颜色扇区，色度矩阵两行与偏置保持原值。所有发布候选及留一折表都读回整数后再计分。', '',
              '| 配方 / 模型 | 表平面采样数 | 最小色相导数 | 最大色度对数斜率，每度 | 表平面倒退数 | JPEG 裁切边界倒退数 |',
              '| --- | --- | --- | --- | --- | --- |']
    for slot, record in selected.items():
        for iso, model in record['models'].items():
            s, c = model['dense_sector_safety'], model['chain_safety']
            lines.append(f"| {slot} / ISO {iso} | {s['samples']} | {s['min_hue_derivative']:.4f} | {s['max_abs_dlog_chroma_per_degree']:.5f} | {s['hue_reversal_count']} | {c['adjacent_clipped_boundary_jpeg_hue_reversals']} |")
    lines += ['', '表平面以 0.1° 扫一周，另加节点附近样本，覆盖 17 个色度半径 0.05–180。硬门槛是 A/B 绝对值不超过 127、系数和输出相对尺度至少 0.25、色相导数至少 0.10、色度对数斜率绝对值不超过每度 0.05。另重放 7 档亮度、6 个色度半径、0.5° 步长的完整曲线链，单列输入无效和发生 RGB 裁切的点。未裁切输出没有色相倒退；若上表裁切边界计数不为零，就不能声称整个 JPEG 输出处处单调。', '',
              '01 在 ISO 200 拟合中与整数微调中都保留额外单调余量；此前只在连续解保留余量，整数微调会把余量用掉。01 的两套固定模型灰阶都进入保护约束，彩色训练仍只用 ISO 200；所以 ISO 1600 是同一表的模型交叉检查，灰阶部分不是完全留出的独立测试。02 的 ISO 1600 没有进入训练损失，但检查结果参与了候选选择。', '',
              '77 个理想无色灰输入的曲线输出也重算过。Y 行和保持 1024、色度行和保持 0，使它们的变化仅为浮点数值误差；这不能取代六个带实测残余色偏的照片灰块。', '',
              '## 技术附录与复算', '',
              f"DNG 没有 ForwardMatrix。沿用双光源 ColorMatrix、AsShotNeutral 和 Bradford 色适应，得到归一化的 camera→XYZ D50 矩阵 C。场景线性 sRGB 先转 XYZ D65，再适应至 D50；相机 RGB = {generator['scene_exposure_scale']:.12f} × C⁻¹ × XYZ D50。曝光比例只用 D2/D3/D4 三灰的 Y 比例中位数确定。它是三通道色度模型近似，不是传感器光谱模型。", '',
              'GR 渲染沿用已核验参数：E=1.374853851910、gain=11222、flag=0。前置矩阵按饱和度矩阵 × look × sensor CCM 的整数规则重建，并与冻结结果逐项相等。Gamma256 使用该参数下已经独立核验的 256 个整数节点，节点字节哈希再次检查。Positive 的 key/contrast/highlight/shadow 为 −1/+3/−1/−2；Negative 为 +1/+1/0/−1；Standard 全为 0。', '',
              '渲染公式为 Gamma256(clamp(E × front/256 × (WB ⊙ camRGB), 0, 1) × 4095) / 16384。GR 模式与 Standard 的差用 Lab D50 表示，取 ΔL、色度比例及包裹到 ±180° 的色相差，再应用到 GXR 04 的 Lab D65。此混合白点口径刻意沿用既有目标。近无色点只转 ΔL，不使用不稳定的色相比例。', '',
              '辅助训练色为 L*=35/60/80，色相 7.5° 起每隔 15°，色度为对应 sRGB 色域边界的 30%/65%。GXR 底色沿用中和后的 R8051160 建立 Nominal04，再用各 ISO 固定模型的 stock 链反解输入。辅助色与验收环没有相同线性 RGB 点。曲线链扫描的逆函数保留平坦段的两端，避免 Positive 黑端平台的通用逆函数近似误差。', '',
              f"共冻结 {verify['input_integrity']['files']} 份只读输入；结束时哈希全部未变。原件、照片或固件派生数组、曲线、表和依赖代码副本均只放在已忽略的 local/ 或 artifacts/downloads/bastibe-gr3/。公开的 metrics.json 只含统计。没有 Git commit，没有相机或 SD 操作，没有生成 DAT。", '',
              '从仓库根目录复算已保存整数结果：', '', '```sh',
              'OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 \\',
              '  python3 -I -B research/color_fit_v2/gr_round5/verify_round5.py',
              'OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 \\',
              '  python3 -I -B research/color_fit_v2/gr_round5/finish_round5.py',
              'cd research/color_fit_v2/gr_round5', 'shasum -a 256 -c SHA256SUMS', '```', '',
              '重新拟合 01 用 `fit_round5.py fit --slot 01 --name dualgrey --safety-margin .3 --grey-margin .025 --grey-strength 300 --dual-grey-guard`；02 用 `fit --slot 02 --name quarter_strict --synth-factor .25 --safety-margin .05`。留一把 `fit` 改为 `loo`，逐次指定 `--index 0` 至 `--index 17`；可用 `--end` 形成最多三折的前台串行批次。每次命令有 55 秒上限，所有数值命令使用上述线程限制与 `python3 -I -B`。', '',
              '`bootstrap.py` 负责首次冻结依赖，已有快照时拒绝覆盖。`refetch.py` 接受 `--repo` 和 `--destination`，后者固定为本仓库的 `artifacts/downloads/bastibe-gr3`，并调用原 `fetch_source.py`；`gr_targets.py --references <该下载目录的绝对路径>` 重算目标和原件色块检查。照片和派生数据都不依赖 /tmp 的旧副本。', '',
              '交付文件为 REPORT.md、metrics.json、local/fit_01_r5.json、local/fit_02_r5.json 及本目录脚本。SHA256SUMS 记录全部本轮文件的 SHA-256。']
    (HERE / 'REPORT.md').write_text('\n'.join(lines)+'\n')
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (HERE / 'SHA256SUMS').write_text(''.join(f'{g.sha(p)}  {p.relative_to(HERE)}\n' for p in files))
    print(json.dumps({'accepted': {s: r['accepted'] for s, r in selected.items()},
                      'sha256': {str(p.relative_to(HERE)): g.sha(p) for p in [HERE/'REPORT.md', HERE/'metrics.json',
                        g.LOCAL/'fit_01_r5.json', g.LOCAL/'fit_02_r5.json', HERE/'SHA256SUMS']}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
