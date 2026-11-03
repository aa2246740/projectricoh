#!/usr/bin/env python3
"""Render four-column evidence, select local candidates, and write the Chinese report."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-previews', action='store_true')
    args = ap.parse_args()
    preflight(); install_fence()
    import csv
    import shutil
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    Camera, Problem, score, stats, Cube, _, _, _ = converter()
    c = Camera()
    records = {}
    for p in sorted((LOCAL/'fits').rglob('metrics.json')):
        d = json.loads(p.read_text())
        records[(d['look'], d['basis'], d['concentration_percent'], d['variant'])] = (p.parent, d)
    assert len(records) == 56, f'Expected 56 fitted variants, found {len(records)}'
    with np.load(LOCAL/'prepared/dataset.npz', allow_pickle=False) as z:
        data = {k: z[k].copy() for k in z.files}
    with np.load(LOCAL/'prepared/S1RII.npz', allow_pickle=False) as z:
        pan = {k: z[k].copy() for k in z.files}
    scene_meta = json.loads((LOCAL/'prepared/scenes.json').read_text())
    models = json.loads((LOCAL/'prepared/model_comparison.json').read_text())
    anchor = json.loads((LOCAL/'inverse_anchor_evaluation.json').read_text())
    inputs = json.loads((LOCAL/'input_manifest.json').read_text())
    source = json.loads((DOWNLOAD/'SOURCES.json').read_text())
    looks = sorted({k[0] for k in records})
    font = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 18)
    small = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 15)
    basis_names = {'gxr04': 'GXR 04', 'panasonic_s1rii': '松下 S1RII'}
    def target(cube, base, alpha):
        return np.clip((1-alpha)*base+alpha*cube.apply(base/255)*255, 0, 255)
    def cell(v, n=2):
        return '不定义' if v is None else f'{v:.{n}f}'
    def pct(v):
        return '不定义' if v is None else f'{100*v:.1f}%'
    def de_text(s):
        return cell(s['median'])+'/'+cell(s['p90'])
    def range_of(d, group, metric):
        a = [m[group][metric] for m in d['model_uncertainty'] if m[group][metric] is not None]
        return None if not a else [min(a), max(a)]
    def linked(path):
        return str(path.relative_to(HERE))
    # Full quantized candidates and all comparative previews stay private.
    if not args.skip_previews:
        for look in looks:
            cube = Cube.read(ORIGINAL/(look+'.cube'))
            for basis in ('gxr04', 'panasonic_s1rii'):
                for concentration in (100, 70):
                    for variant in ('safe', 't1'):
                        dest, d = records[(look, basis, concentration, variant)]
                        output = dest/'preview.jpg'
                        candidate = json.loads((dest/'candidate.json').read_text())
                        prediction = Problem(c, data['train_x'], target(cube,
                            data['train_stock'] if basis == 'gxr04' else pan['train'], concentration/100),
                            variant=variant, sample_weights=data['train_weights'])
                        widths = 400
                        heights = [int(data[f'scene{i}_shape'][0]) for i in range(5)]
                        im = Image.new('RGB', (4*widths, 100+sum(h+65 for h in heights)), '#171a1b')
                        draw = ImageDraw.Draw(im)
                        draw.text((12, 9), f'模型模拟，非实拍 | {look} | 浓度 {concentration}% | 50mm', font=font, fill='white')
                        draw.text((12, 38), f'第4列：{basis_names[basis]}基底 / {variant.upper()} 整数配方预测；固定 DNG 曝光和白平衡', font=small, fill='#d0d6d8')
                        draw.text((12, 63), '五张整图均未参与拟合；非 ISO 200 只作代理诊断。所有列均为模型模拟。', font=small, fill='#d0d6d8')
                        y = 100
                        for i, meta in enumerate(scene_meta):
                            shape = tuple(data[f'scene{i}_shape'])
                            stock = data[f'scene{i}_stock']
                            ideal_pan = target(cube, pan[f'scene{i}'], concentration/100)
                            ideal_gxr = target(cube, stock, concentration/100)
                            pred = prediction.predict(np.array(candidate['theta']), data[f'scene{i}_x'])
                            columns = [stock, ideal_pan, ideal_gxr, pred]
                            labels = ['GXR 04 模型', '理想效果：松下标准基底', '理想效果：GXR 04 基底', f'配方预测：{variant.upper()}']
                            for j, (a, label) in enumerate(zip(columns, labels)):
                                draw.text((j*widths+8, y+3), label, font=small, fill='white')
                                scene_label = Path(meta['path']).stem+f' / ISO {meta["iso"]}'
                                if not meta['model_calibrated_for_scene_iso']:
                                    scene_label += ' / ISO 200 模型代理'
                                draw.text((j*widths+8, y+28), scene_label, font=small, fill='#b7c0c4')
                                tile = Image.fromarray(np.uint8(np.clip(np.rint(a.reshape(shape)), 0, 255)))
                                im.paste(tile, (j*widths, y+59))
                            y += heights[i]+65
                        im.save(output, quality=91, subsampling=0)
                        print('preview', look, basis, concentration, variant, flush=True)
    neutral_diagnostics = []
    for look in looks:
        cube = Cube.read(ORIGINAL/(look+'.cube'))
        for basis in ('gxr04','panasonic_s1rii'):
            for concentration in (100,70):
                base = data['ramp_stock'] if basis=='gxr04' else pan['ramp']
                target_ramp = target(cube,base,concentration/100)
                lab = c.fs.lab_from_codes(target_ramp)
                for variant in ('safe','t1'):
                    dest, _ = records[(look,basis,concentration,variant)]
                    candidate = json.loads((dest/'candidate.json').read_text())
                    P = Problem(c,data['train_x'],target(cube,data['train_stock'] if basis=='gxr04' else pan['train'],concentration/100),
                                variant=variant,sample_weights=data['train_weights'])
                    pred = P.predict(np.array(candidate['theta']),data['ramp_x'])
                    err = c.fs.delta_e00(c.fs.lab_from_codes(pred),lab)
                    neutral_diagnostics.append({'look':look,'basis':basis,'concentration':concentration,
                        'variant':variant,'gray_node_diagnostic_de00':stats(err),
                        'target_max_chroma_lab':float(np.linalg.norm(lab[:,1:],axis=1).max()),
                        'scope':'33 physical curve-node grey inputs; diagnostic, not an independent holdout'})
    dump(LOCAL/'neutral_diagnostics.json',neutral_diagnostics)
    selections = []
    for look in looks:
        concentration = 70 if look.startswith('Leica ') else 100
        safe_path, sd = records[(look,'panasonic_s1rii',concentration,'safe')]
        t1_path, td = records[(look,'panasonic_s1rii',concentration,'t1')]
        # A restrictive T1 candidate earns preference for split toning or a clear
        # held-out gain; never label the result daily-eligible or deployable.
        split = look in ('Leica Brass','Kodak 5219','Polaroid 600')
        gain = sd['synthetic_holdout']['de00']['median']-td['synthetic_holdout']['de00']['median']
        scene_gain = sd['iso200_scene_holdout']['de00']['median']-td['iso200_scene_holdout']['de00']['median']
        v = 't1' if split and gain > .25 and scene_gain > 0 else 'safe'
        src, d = records[(look,'panasonic_s1rii',concentration,v)]
        slug = look.lower().replace(' ', '_')
        dest = LOCAL/'best_candidates'/slug
        dest.mkdir(parents=True, exist_ok=True)
        for name in ('candidate.entry','candidate.json','recipe.identity49.bin','metrics.json','sector_residuals.csv','LIMITATIONS.txt'):
            shutil.copy2(src/name, dest/name)
        if (src/'preview.jpg').exists():
            shutil.copy2(src/'preview.jpg',dest/'preview.jpg')
        selection = {'look': look, 'basis': 'panasonic_s1rii', 'concentration': concentration,
                     'variant': v, 'path': linked(dest), 'source_path': linked(src),
                     'synthetic_holdout': d['synthetic_holdout'], 'iso200_scene_holdout': d['iso200_scene_holdout'],
                     'split_toning': split, 't1_median_gain_de00': gain, 't1_iso200_median_gain_de00': scene_gain,
                     'sector_scan_passed': d['sector_safety']['passes'],
                     'candidate_status': 'research_only_static_scan_passed' if d['sector_safety']['passes'] else 'research_only_static_scan_failed',
                     'camera_acceptance': False, 'firmware_ready': False, 'deployable': False,
                     'reason': 'split-tone research target' if v == 't1' else 'prefer daily controls for limited T1 gain'}
        selections.append(selection)
    baseline_safety = c.E.safety(c.A, c.B, dense=True)
    dump(LOCAL/'best_candidates/INDEX.json', {'basis': 'panasonic_s1rii', 'entries': selections,
         'status': 'personal-use research candidates; none camera accepted',
         'identity49': 'all entries retain the converter slot-05 template identity; integrator must rebind',
         'baseline_sector_safety': baseline_safety})
    flat = []
    for key, (dest, d) in records.items():
        s, r = d['synthetic_holdout'], d['iso200_scene_holdout']
        flat.append({'look': d['look'], 'basis': d['basis'], 'concentration': d['concentration_percent'],
             'variant': d['variant'], 'similarity': s['similarity'], 'de00_median': s['de00']['median'],
             'de00_p90': s['de00']['p90'], 'iso200_median': r['de00']['median'], 'iso200_p90': r['de00']['p90'],
             'all_scene_median': d['all_scene_holdout']['de00']['median'],
             'all_scene_p90': d['all_scene_holdout']['de00']['p90'],
             'solver_status': d['solver']['status'], 'solver_nfev': d['solver']['nfev'],
             'sector_scan_passes': d['sector_safety']['passes'], 'directory': linked(dest)})
    with (LOCAL/'SUMMARY.csv').open('w', newline='') as f:
        w = csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    dump(LOCAL/'SUMMARY.json', {'rows': flat, 'selections': selections,
         'baseline_sector_safety': baseline_safety, 'input_dependencies_sha256': sha(LOCAL/'input_manifest.json')})
    scan_failures = sum(not d['sector_safety']['passes'] for _,d in records.values())
    lines = []
    def add(s=''):
        lines.append(s)
    add('建议以 S1RII 的松下标准反演模型作为胡子 LUT 的默认比较基底，保留 GXR 04 代理版供对照。日常旋钮优先比较 Chrome 70% safe，其次 VIVID 70% safe；它们通过了当前扇区扫描。Brass、Kodak 5219、Polaroid 600 若要保留明暗分色需 T1。Teal 所有版本均未通过扫描，只保留研究。这里交付的是个人使用的本地研究候选，尚无相机验收。')
    add()
    add('已完成 7 个 LUT × 2 种基底 × 2 种浓度 × safe/T1，共 56 组整数化拟合、24 扇区残差和四列预览；5 张实景 DNG 全部留出。未接触相机、存储卡或官方固件写入，未生成上卡容器，未 commit/push。')
    add(f'密集扇区扫描 {scan_failures}/56 组未通过，原厂 04 模型自身也未通过；这项检查不能被总体色差代替，候选均未获装机或日常使用批准。')
    add('目标器材按用户提供为 GXR 机身 1.51、GR LENS A12 50mm 单元 1.51；本任务没有连接设备核对固件，前向计算固定用已有 50mm ISO 200 模型。')
    add()
    add('## 已核实')
    add()
    add(f'- 工作卷通过 APFS、可写及 UUID `{UUID}` 检查；任务 `.gitignore` 忽略 `/local/`，由 `git check-ignore -v` 复核。')
    add(f'- 原始 7 个 33³ LUT 和用户说明逐项匹配提供的 SHA256SUMS；输入只读，所有派生参数、49 B 身份和图像均在本任务 `local/`。')
    add(f'- V-Log-Alchemy 固定为 [{source["commit"]}](https://github.com/shenmintao/V-Log-Alchemy/tree/{source["commit"]})，下载 {len(source["files"])} 个相关数据文件；逐文件 SHA-256、原始 URL 和 Git blob 校验见 `local/artifacts/downloads/vlog-alchemy-20261024/SOURCES.json`。许可文件为 Apache-2.0。')
    add('- 上游只提供 Standard→V-Log，没有直接提供 V-Log→Standard；本任务实现有界数值反演，使用原转换器的四面体插值。所有机型数据均独立读取，未把 S1RII 表复制给其他机型。')
    add()
    add('## 松下模型的证据与边界')
    add()
    add('管线为 GXR DNG、沿用 camera.py 的固定中灰锚与逐帧 DNG 矩阵转场景 XYZ、官方 V-Gamut/V-Log 编码、有界反演至松下 Standard 显示 RGB、胡子 LUT、显示 RGB 浓度混合。没有为不同 LUT 自动调整曝光或白平衡。')
    add()
    add('V-Log 系数与 V-Gamut 原色沿用 `research/lut_convert/spaces.py`，并对照 [Panasonic 官方参考手册](https://pro-av.panasonic.net/en/cinema_camera_varicam_eva/support/pdf/VARICAM_V-Log_V-Gamut.pdf) 的 §3–4；黑、18% 灰、90% 白的 10 bit 编码复核及矩阵误差见 `local/inverse_anchor_evaluation.json`。')
    add()
    add('上游 v1.6 从 SILKYPIX Developer Studio 8 SE 8.0.30.4 的机型前向表配对拟合适配器：Standard 129 点、V-Log 主表 257 点、暗部 17 点，先解 9 点控制格再采到 33 点。作者用 S1RII 固定灯光、白平衡和四档曝光约束共同 V-Log 端点。S1RII 有定量实拍，S9 只有作者声明的定性外拍支持，其余机型缺少配套实拍。原始解码前向大表和所有原始实拍对不在本次下载数据中，无法独立从零重建或确认作者的留出实拍成绩。')
    add()
    add('作者报告的手部整组留出平均 RGB 距离为 V-Log 0.00392、后接 Classic Neg 0.00961。这是上游报告值，单位不是 ΔE00。上游还观测到相同名义曝光下原生 V-Log RAW 信号约为 Standard 的 0.397 倍；本任务没有把该采集增益差当成 GXR 的曝光修正。详见固定提交的 [方法说明](https://github.com/shenmintao/V-Log-Alchemy/blob/'+source['commit']+'/Luts/Panasonic-Standard/README.md)。')
    add()
    add('反演先从邻近输出节点启动 Gauss-Newton，用不同起点复查困难点；色域面上的受限步长枚举 27 种活跃约束，再检查真实前向残差。残差以归一化 V-Log code 的最大通道差统计。小于 1e-5 记为近似精确，超过 1e-3 记为“未找到近似原像”。后者是数值结果，不等于已经证明目标在色域外。')
    add()
    add('| 机型 | 负 Jacobian 比例 | 多解检出 /512 | 合成近似原像比例 | Standard 与 04：合成 ΔE00 中位/p90 | 五景 ΔE00 中位/p90 | ISO 200 两景 中位/p90 |')
    add('|---|---:|---:|---:|---:|---:|---:|')
    for name, m in models['models'].items():
        di, b, v = m['diagnostic'], m['boundary']['test'], m['difference_to_gxr04']
        add(f'| {name} | {100*di["negative_determinant_share"]:.1f}% | {di["multiple_preimages_detected_n_of_512"]} | {100*(1-b["no_close_preimage_found_share_linf_gt_1e_3"]):.1f}% | {de_text(v["synthetic"])} | {de_text(v["all_scenes"])} | {de_text(v["iso200_scenes"])} |')
    add()
    pair = models['pairwise']
    add(f'机型之间两两比较，合成中位 ΔE00 范围为 {min(r["synthetic"]["median"] for r in pair):.2f}–{max(r["synthetic"]["median"] for r in pair):.2f}，最高 p90 为 {max(r["synthetic"]["p90"] for r in pair):.2f}；五景中位范围为 {min(r["scenes"]["median"] for r in pair):.2f}–{max(r["scenes"]["median"] for r in pair):.2f}，最高 p90 为 {max(r["scenes"]["p90"] for r in pair):.2f}。S5II/S5IIX、G9II/GH7 的数值映射相同，所以十个名称不代表十份独立证据。范围是模型差异，不是置信区间。')
    add('各机型共用 S1RII 实拍端点约束，因此这个范围不能覆盖胡子未知机身、白平衡、风格调整和适配器的共同系统误差。')
    add()
    di = models['models']['S1RII']['diagnostic']
    add(f'S1RII 的 4096 点 Standard 自往返中，V-Log 残差中位数为 {di["roundtrip_vlog_linf"]["median"]:.2g}，但找回的 Standard 色差最大达 {di["roundtrip_standard_de00"]["max"]:.2f} ΔE00，并检出 {di["multiple_preimages_detected_n_of_512"]}/512 个相距超过 0.02 code 的不同原像。因而“残差接近零”不能证明反演回原来的颜色。')
    add()
    sb = models['models']['S1RII']['boundary']
    sr = sb['test']['vlog_input_linf_residual']
    add(f'实际合成查询的 S1RII 反演残差中位/p90/最大为 {sr["median"]:.3g}/{sr["p90"]:.3g}/{sr["max"]:.4f}，未找到近似原像的比例为 {100*sb["test"]["no_close_preimage_found_share_linf_gt_1e_3"]:.2f}%。五张实景依次为 '+ '、'.join(f'{100*sb[f"scene{i}"]["no_close_preimage_found_share_linf_gt_1e_3"]:.2f}%' for i in range(5))+'。逐机型的输出包围盒、边界贴附、域外输入比例和各层残差完整保存在 `local/prepared/<机型>.json`。')
    add()
    add(f'用作者打包的 {anchor["anchor_n"]} 个 Standard/原生 V-Log 校准点逆向回放，Standard 重建 ΔE00 中位/p90 为 {de_text(anchor["standard_reconstruction_de00"])}。这些点参加过上游拟合，只能说明校准集吻合程度。独立 SciPy 两起点复核最差及分散样本共 {anchor["hard_case_checks_n"]} 点，其中 {anchor["hard_cases_scipy_improves_linf_gt_1e_3"]} 点还能把最大通道残差改善超过 0.001，完整记录保存在 `local/inverse_anchor_evaluation.json`。')
    add()
    add('## 拟合口径')
    add()
    add(f'训练集 {inputs["synthetic_train_n"]} 点、合成留出 {inputs["synthetic_test_n"]} 点。额外灰轴在训练中权重为 4；测试使用另一组灰阶，并剔除夹紧后重复的 {inputs["shared_gray_input_rows_removed_from_test"]} 个黑点，精确共用输入为 {inputs["synthetic_exact_shared_input_rows"]}。合成 XYZ 沿用第一张 DNG 的白平衡和矩阵，不代表任意照明的传感器匹配。')
    add('每张实景从 RAW 未裁切位置均匀抽取 3000 个像素评分，全图参与预览。第一张仅借用 DNG 元数据构造合成 XYZ，没有任何实景像素用于拟合。')
    add()
    add('相似度严格使用既有定义 `1 - median(配方到目标 ΔE00) / median(原厂04到目标 ΔE00)`。它衡量消除了多少原厂 04 到目标的差距，不是与松下、徕卡或真实照片的绝对还原率。分母小于 0.25 时不定义。松下基底版本包含从 04 改到松下基底的差距，不能把两种基底的百分比直接排名。')
    add()
    add('70% 浓度定义为显示编码 RGB 的 `0.3 × 基底 + 0.7 × LUT(基底)`，全浓度为 100%。这是普通显示参考 LUT 的交叉混合定义，符合“减弱造型、保留基底”的要求；胡子未公开其 App 浓度算法，不能声称完全复刻了该滑杆，也没有把它解释为场景线性混合。')
    add()
    add('safe 仅使用共同曲线、Y 矩阵行与 24 个对称扇区，不用 T/C/D；T1 增加 R=C、G=B5、B=D 三通道曲线并启用 T 控制。所有分数都在整数化曲线、矩阵和扇区之后重算。safe 的“日常”只指旋钮类型，每份候选仍为 `daily_eligible=false`、`camera_acceptance=false`。')
    add('本次未搜索独立色度矩阵、四个自由 C/D 扇区或 D8 节点移动；结果是既有转换器范围内的近似，不代表 GXR 所有配方控制的色彩上限。')
    add()
    for basis in ('gxr04','panasonic_s1rii'):
        add('## '+basis_names[basis]+'基底的 28 组结果')
        add()
        add('ΔE00 均列中位/p90；实景列只合并两张 ISO 200，其他三张逐帧列在各 `metrics.json`。')
        add()
        add('| LUT | 浓度 | 控制 | 合成相似度 | 合成 ΔE00 | ISO 200 实景 ΔE00 | 机型范围：相似度 | 机型范围：中位 / p90 |')
        add('|---|---:|---|---:|---:|---:|---:|---:|')
        for look in looks:
            for a in (100,70):
                for v in ('safe','t1'):
                    _, d = records[(look,basis,a,v)]
                    rr = range_of(d,'synthetic','similarity')
                    spread = '不适用' if rr is None else pct(rr[0])+'–'+pct(rr[1])
                    mids = [m['synthetic']['de00']['median'] for m in d['model_uncertainty']]
                    p90s = [m['synthetic']['de00']['p90'] for m in d['model_uncertainty']]
                    erange = '不适用' if not mids else f'{min(mids):.2f}–{max(mids):.2f} / {min(p90s):.2f}–{max(p90s):.2f}'
                    add(f'| {look} | {a}% | {v} | {pct(d["synthetic_holdout"]["similarity"])} | {de_text(d["synthetic_holdout"]["de00"])} | {de_text(d["iso200_scene_holdout"]["de00"])} | {spread} | {erange} |')
        add()
    add('松下的机型范围把同一份 S1RII 候选分别与十个机型目标比较，没有为每个机型另拟合。逐机型中位/p90、相似度和五景分数均保存在 28 份松下 `metrics.json` 的 `model_uncertainty`；没有借助排除不佳反演点提高主表分数。')
    add()
    add('## 推荐与还原不了的部分')
    add()
    add('默认选 S1RII 基底，是因为它接近用户声明的“松下标准输入”，且十个模型中只有它有上游定量实拍支持。04 代理更容易以较低绝对误差拟合，但会把 GXR 04 的底色带进结果；它适合用户更喜欢其预览时采用。S1RII 基底仍是研究假设，不能据此确认胡子使用的机身或实际处理链。')
    add()
    add('| LUT | 先比较的本地候选 | 合成相似度 / ΔE00 中位/p90 | 扇区扫描 | 还原不了什么 |')
    add('|---|---|---|---|---|')
    notes = {
        'Leica Chrome': '低饱和和总体青调可以近似；共同曲线不能完整保留灰轴轻微偏色与随明暗变化的青色。',
        'Leica Teal': '青色造型可以近似；同一青绿在不同饱和度、明暗下的独立转色仍会偏。',
        'Leica Brass': '灰轴明暗分色需要 T1；safe 只能保留整体暖感，T1 也不能表达完整三维交叉耦合。',
        'Leica VIVID': '灰轴保持中性；鲜艳色的选择性色相与饱和度耦合仍超出固定扇区表达。',
        'Canon Elegant Portrait': '灰轴中性和低饱和可以近似；这里缺少真实人像留出，不能把猫或物件分数当肤色验收。',
        'Kodak 5219': '暗部与亮部分色需要 T1；胶片颗粒、局部反差和真实胶片响应不在 LUT 或配方模型内。',
        'Polaroid 600': '低饱和与灰轴明暗偏色需要分开处理；safe 会丢失分色，T1 也不能复制相纸质感。',
    }
    for s in selections:
        d = s['synthetic_holdout']
        add(f'| {s["look"]} | {s["concentration"]}% / {s["variant"]} | {pct(d["similarity"])} / {de_text(d["de00"])} | '+('通过' if s['sector_scan_passed'] else '未通过')+f' | {notes[s["look"]]} |')
    add()
    add('日常旋钮优先比较 Chrome 70% safe 与 VIVID 70% safe，两者通过了当前扇区扫描。Chrome 的松下基底相似度约 76%，VIVID 约 69%；VIVID 在 04 代理上的绝对误差很低，而相似度百分比受原始差距小影响。Teal 的八组都未通过扫描，即使松下 safe 相似度约 78%，也只保留研究。Kodak 的 safe 可近似整体风格且通过扫描，若要保留完整明暗分色，应与 Brass 一起等 T1。Canon Portrait 的松下基底相似度约 54%，Polaroid 即使 T1 也只有约 63%，且所选条目均未通过扫描，不归入高还原日常候选。T1 对 Polaroid 有帮助，但不足以解决全部误差。最佳候选的实际选择、静态扫描结果、T1 改善及路径见 `local/best_candidates/INDEX.json`。')
    add()
    add('明暗分色的灰轴诊断如下。输入为 33 个物理曲线节点，不充当独立留出；完整两种基底、两种浓度的 56 组诊断保存在 `local/neutral_diagnostics.json`。')
    add()
    add('| LUT / 松下基底浓度 | safe 灰轴 ΔE00 中位/p90 | T1 灰轴 ΔE00 中位/p90 |')
    add('|---|---:|---:|')
    for look,a in [('Leica Brass',70),('Kodak 5219',100),('Polaroid 600',100)]:
        ns = next(r for r in neutral_diagnostics if (r['look'],r['basis'],r['concentration'],r['variant'])==(look,'panasonic_s1rii',a,'safe'))
        nt = next(r for r in neutral_diagnostics if (r['look'],r['basis'],r['concentration'],r['variant'])==(look,'panasonic_s1rii',a,'t1'))
        add(f'| {look} / {a}% | {de_text(ns["gray_node_diagnostic_de00"])} | {de_text(nt["gray_node_diagnostic_de00"])} |')
    add()
    failures = [d for _,d in records.values() if not d['solver']['success']]
    add(f'优化器有 {len(failures)}/56 组未报告收敛，原始状态、求值次数和耗时均保留。密集扇区扫描 {scan_failures}/56 组未通过；原厂 04 模型自身 `passes={str(baseline_safety["passes"]).lower()}`、色相反转计数为 {baseline_safety["hue_reversal_count"]}。本轮未把模型既有的低彩度问题改写为安全通过，也未完成整条相机生命周期验收。')
    add()
    add('## 实景四列预览')
    add()
    add('每份候选都有 `preview.jpg`，固定列序为 GXR 04 模型、松下标准基底的理想效果、GXR 04 基底的理想效果、该候选预测。每张都标“模型模拟，非实拍”，同一行使用完全相同的 DNG、曝光、白平衡和采样位置。稀疏 2×2 CFA 均值不是完整去马赛克，不能用于纹理或锐度判断。')
    add('人工抽查看过 Brass 70% 的 safe/T1 两张完整四列对照；最终验证器检查全部 56 张预览的编码和尺寸。人工抽查不等于逐张视觉验收。')
    add()
    add('| 实景 DNG | ISO | 用途 |')
    add('|---|---:|---|')
    for m in scene_meta:
        add(f'| `{m["path"]}` | {m["iso"]} | '+('整张留出，匹配 ISO 200 模型' if m['model_calibrated_for_scene_iso'] else '整张留出，仅 ISO 200 代理诊断')+' |')
    add()
    for s in selections:
        add(f'- [{s["look"]}：推荐候选的四列预览]({s["path"]}/preview.jpg)。')
    add()
    add('## 产出与复核命令')
    add()
    add('- `local/prepared/` 保存十个反演基底、原像残差、边界统计、机型两两差异与全部整景样本。')
    add('- `local/fits/<LUT>/<基底>/p100或p70/safe或t1/` 保存 56 组指标、各 24 行扇区残差、限制说明、四列预览、448 B 单条深层条目、49 B 模板身份及其 CRC。')
    add('- `local/best_candidates/` 保存 7 个优先比较候选；它们没有表头、卡文件或安装入口。49 B 身份仍绑定转换器 slot 05 模板，后续组表须重新绑定名称、原生模式和 recipe CRC。')
    add('- `local/SUMMARY.csv`、`local/SUMMARY.json` 提供汇总；`local/verification.json` 提供最终独立条目回放、输入不变与范围检查。')
    add('- `local/diagnostics/` 保留首次灰轴交叉及色域面反演问题的原始记录；各脚本日志保留在 local/。`SHA256SUMS` 覆盖本任务所有最终普通文件，排除自身。')
    add()
    add('```bash')
    add('cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
    add('python3 -I -B research/huzi_luts/acquire.py')
    add('python3 -I -B research/huzi_luts/prepare.py')
    add('python3 -I -B research/huzi_luts/audit_inverse.py')
    add('python3 -I -B research/huzi_luts/fit_luts.py --max-nfev 120')
    add('python3 -I -B research/huzi_luts/deliver.py')
    add('python3 -I -B research/huzi_luts/verify.py')
    add('git check-ignore -v research/huzi_luts/local/best_candidates/INDEX.json')
    add('cd research/huzi_luts')
    add('shasum -a 256 -c SHA256SUMS')
    add('```')
    add()
    add('## 推断与未知')
    add()
    add('推断：上游实拍校准的数值吻合与机型间范围支持把 S1RII 反演当作一个比 04 更贴近声明输入的研究模型。T1 有表达明暗分色的结构能力。两点都不是 GXR 实拍效果确认。')
    add()
    add('未知：胡子的松下机身、固件、Photo Style 调整、白平衡、具体提取/转接过程、sRGB 与 Rec.709 的精确传递函数、App 的浓度算法，以及本候选在 GXR 机身 1.51 / A12 50mm 1.51 的真实效果。现有样本没有真实人像、标准色卡跨照明配对或胡子本人的参考成片；没有新设备实拍或原生菜单验收。')
    add()
    add('## 许可与个人使用范围')
    add()
    add('7 个胡子 LUT 包含徕卡 FOTOS Looks、佳能及胶片仿色的二次加工。来源说明不等于原厂授权，本任务只为用户个人使用保存候选，不发布 LUT、派生参数或图片。V-Log-Alchemy 的 Apache-2.0 文件保留在隔离下载目录；其开源许可不替代这些第三方 Look 的许可。所有 LUT 派生参数、固件派生条目和图像只位于被 Git 忽略的本任务 local/。')
    (HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('Wrote REPORT.md and seven local best candidates', flush=True)


if __name__ == '__main__':
    main()
