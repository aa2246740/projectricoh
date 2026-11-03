"""Render the Chinese research report from verified aggregate results only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as r


NAMES={'gr3_01':'GR III 01 正片','gr3_02':'GR III 02 负片',
       'gr4_hdf_01':'GR IV HDF 01 正片','gr4_hdf_02':'GR IV HDF 02 负片'}


def percent(v):return f'{100*v:.1f}%'


def pair(rec):
    def cell(x):return f'{x["median"]:.3f} / {x["p90"]:.3f} ({percent(x["similarity"])})'
    return cell(rec['new'])+'；'+cell(rec['round5'])


def main():
    m=r.read(r.HERE/'metrics.json')
    d=r.read(r.HERE/'diagnostic_review.json')
    assert m['candidate_count']==0 and m['fit_count']==312
    lines=[
        '现行 01/02 按密集真 GR 目标、ISO 200 观测覆盖点打分：GR III 为 63.5% / 60.9%，约 6.4 成 / 6.1 成；GR IV HDF 为 71.9% / 45.6%，约 7.2 成 / 4.6 成。',
        '',
        '加 T1 后，本轮 ISO 200 的 60° 色段留出实际相似度：GR III 01 为 62.0%～62.1%，02 为 43.4%～43.6%；GR IV HDF 01 为 54.2%～57.5%，02 为 43.3%～43.7%。这些是 (b)/(c) 两档的原始留出分数，全部未过灰轴门槛，也均低于对应留出集上的 round5。本轮没有证实可接受的 T1 提升。',
        '',
        '剩余误差中“只有色相 × 明度的三维能力才能消除”的份额未知。(c) 局部线性投影剩余误差中，色相 × 明度样条可在样本内解释 20.3%～51.6%，加入彩度可解释 57.2%～75.6%；两者的同源空间留出解释率均为负，不能把样本内可拟合部分认定为三维能力的独占收益。',
        '',
        'GR 正负片要冲 95%，必须靠独立场景真 GR 目标与实测闭环验证色相 × 明度 × 彩度联合校正；这是待验证的路线，目前没有 95% 的留出证据。',
        '',
        '## 分数的含义和证据范围',
        '',
        '相似度 = 1 − 候选相对目标的 ΔE00 中位数 / 原生 04 相对同一目标的 ΔE00 中位数。它表示相对 04 的误差减少比例。不同留出协议有不同的样本和分母，不能把全覆盖 63.5% 与色段留出的 68.9% 直接当成一次提升。',
        '',
        '已核实的是电脑上的映射和验证。GR 风格端使用观测 JPEG，GXR 端仍经过推定的桥接和前表模型；密集点来自少量已有图像，点数不代表独立场景数。ISO 1600 是同一目标下的 GXR ISO 1600 模型检查，没有新增 ISO 1600 真机测量。没有相机、存储卡或固件运行验收。',
        '',
        '| 目标 | 覆盖点数 | 现行 ISO 200 相似度 | ΔE00 中位数 / p90 |',
        '|---|---:|---:|---:|',
    ]
    for key,name in NAMES.items():
        b=m['baseline'][key]['models']['200']['observed_dense']
        lines.append(f'| {name} | {b["n"]} | {percent(b["similarity"])} | {b["median"]:.3f} / {b["p90"]:.3f} |')
    lines += ['',
        '## 拟合与留出规则',
        '',
        '(a) 为 Y + 24 个对称色度扇区，沿用已完成的 gr_pairs 控制结果。(b) 增加 RGB 各 33 节点的单调 T1 曲线，R/G/B 分别映射到 C/B5/D。(c) 再放开物理扇区 0、11、17、23 的一般 2×2 色度变换。量化后检查曲线范围、单调性以及矩阵和色度字的编码。',
        '',
        '18 色留一逐折排除对应锚点。GR III 的目标函数还排除同 RAW 的留出颜色邻域后重建。60° 色段折在训练端额外留 5° 缓冲，并在拟合目标函数前移除留出颜色；灰色点不计入彩色色段评分。每张密集来源的总权重上限为 18，留出后不重新放大余下权重。',
        '',
        '色段统计合并六折的实际留出误差后重新取中位数与 p90，没有平均各折百分比。GR III 01/02 各只有 5 个色段有可评分点；HDF 各有 6 个。各组彩色留出点数依次为 1161、1154、1161、1126。不能把空色段看成通过，也不能据此宣称覆盖所有色相和明度。',
        '',
        '候选要求 ISO 200 和 1600 的每个可用留出协议都降低中位数且不增加 p90，并通过灰轴、色度安全、整数往返与全数据全链门槛。结果是 12 组均被拒绝；所有结果保持 accepted=false、firmware_ready=false、deployable=false。',
        '',
        '## 每档与 round5 的留出比较',
        '',
        '下表每格先列新拟合，再列 round5。每项格式为“ΔE00 中位数 / p90 (相似度)”。同一格内才是相同样本的比较。',
    ]
    for iso in ('200','1600'):
        lines += ['',f'### ISO {iso}','','| 目标 | 档 | 18 色留一：新；round5 | 60° 色段合并：新；round5 |',
                  '|---|---|---|---|']
        for key,name in NAMES.items():
            for level,rec in m['groups'][key]['levels'].items():
                v=rec['validation'][iso]
                lines.append(f'| {name} | {level} | {pair(v["loo"])} | {pair(v["hue"])} |')
    lines += ['',
        '### HDF 整图留出及反向',
        '',
        '正向只用 bastibe 的 24 个锚点训练，留出整张 HDF 风格图。反向只用 HDF 密集样本训练，留出 bastibe RAW 的全部锚点，评分使用其中 18 个彩色点。反向的 round5 已见过 bastibe，比较对新拟合不对称；它只能检查跨来源迁移，不能当成严格独立基线。桥接、固定配方曲线和 ISO 模型也仍是既有标定，两方向都不是跨多场景盲测。GR III 的唯一 RAW 同时提供锚点和密集点，没有可独立留出的第二张源图。',
        '',
        '| 目标 | ISO | 档 | 正向：新；round5 | 反向：新；round5 |',
        '|---|---:|---|---|---|',
    ]
    for key,name in NAMES.items():
        if not key.startswith('gr4'):continue
        for iso in ('200','1600'):
            for level,rec in m['groups'][key]['levels'].items():
                v=rec['validation'][iso]
                lines.append(f'| {name} | {iso} | {level} | {pair(v["image_forward"])} | {pair(v["image_reverse"])} |')
    lines += ['',
        'HDF 01 的 (b)/(c) 在 ISO 1600 正向整图的中位数略好，但 p90 更差；HDF 02 的 (a) 正向也只改善中位数。没有一组满足中位数与尾部同时达标。',
        '',
        '### 全数据分数只作训练诊断',
        '',
        '| 目标 | round5 | a | b：T1 | c：T1 + 四扇区 |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for key,name in NAMES.items():
        values=[m['baseline'][key]['models']['200']['observed_dense']['similarity']]
        values += [m['groups'][key]['levels'][level]['full']['scores']['200']['dense_all']['similarity'] for level in ('a','b','c')]
        lines.append('| '+name+' | '+' | '.join(map(percent,values))+' |')
    lines += ['',
        'GR III 01 约 70%、HDF 01 约 79% 的全数据分数没有转化为留出收益。b/c 的浮点曲线更细也不代表整数表有效；报告中的候选分数全部来自整数解码后的渲染。连续训练诊断保留在 local/fits/，没有替换留出判定。',
        '',
        '## 灰轴、安全和整数编码',
        '',
        '灰轴门槛同时要求六个实测灰块相对 round5 的每点 ΔE00 增量不超过 +0.05，以及 77 点中性轴相对 round5 的最大 ΔE00 不超过 0.05。T1 两档合计 208 份拟合，在两个 ISO 下均未通过这个联合门槛。训练中的软惩罚没有保证整数结果达标，因此保留失败并拒绝候选。',
        '',
        '312 份拟合均独立解码矩阵和色度字，检查 row2 与 row1 的关系，并将三条色调行打包、解包往返；分数复算与记录一致。两个 ISO 的色度扫描使用 0.1°、17 个半径及节点边界邻域。安全阈值为最小色相导数 ≥0.1、最大 |d log 色度 / d 色相| ≤0.05、相对色度尺度 ≥0.25。',
        '',
        '| 目标 | 档 / 折数 | 收敛数 | 灰轴通过 200 / 1600 | 0.1° 安全通过 200 / 1600 | 最大实灰增量 / 中性轴变化，取两 ISO 最坏值 |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for key,name in NAMES.items():
        for level,rec in m['groups'][key]['levels'].items():
            a=rec['all_fit_checks'];p=a['iso']['200'];q=a['iso']['1600']
            lines.append(f'| {name} | {level} / {a["fit_count"]} | {a["converged_count"]} | '
                         f'{p["grey_pass_count"]} / {q["grey_pass_count"]} | '
                         f'{p["independent_0p1deg_safety_pass_count"]} / {q["independent_0p1deg_safety_pass_count"]} | '
                         f'{max(p["max_real_grey_increase"],q["max_real_grey_increase"]):.4f} / '
                         f'{max(p["max_neutral_ramp_change"],q["max_neutral_ramp_change"]):.4f} |')
    lines += ['',
        '细扫额外检出 gr3_01_c_hue_05、ISO 200 的安全失败。原 0.5° 扫描的最小色相导数为 0.10913，0.1° 复查为 0.09557，低于 0.1。该失败已经计入最终拒绝原因，原拟合文件保持原样。',
        '',
        '12 个全数据解另有 T1 在内的全链扫描：7 档亮度 × 6 个半径 × 0.5°。gr4_hdf_02_c_full 在 ISO 200 存在未裁切相邻色相反转，未过全链门槛。裁切边界反转和未形成完整圆环的区域单列在原检查里，没有被当成已验证安全区域。逐折的 0.1° 检查针对色度响应，全链扫描针对 12 个全数据解，两层证据没有混用。',
        '',
        '## 局部投影与三维能力的边界',
        '',
        '以下比例以 round5 观测残差的平方 ΔE00 为分母。投影是固定位置处无约束线性最小二乘的解，没有整数、灰轴和安全约束，也不是非线性全局最优证明。各单独杠杆的解释率存在重叠，不能相加或换算成相似度百分点。',
        '',
        '| 目标 | Y | 24 扇区 | T1 单独 | a | b | c |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for key,name in NAMES.items():
        p=m['projections']['projection_'+key]['tangent_projection']
        lines.append('| '+name+' | '+' | '.join(percent(p[x]['removable_squared_fraction']) for x in ('Y','sector24','T1','a','b','c'))+' |')
    lines += ['',
        '| 目标 | c 后尚余原始残差 | 色相×明度解释剩余，样本内 | 色相×明度×彩度解释剩余，样本内 | 色相×明度空间留出解释率 |',
        '|---|---:|---:|---:|---:|',
    ]
    for key,name in NAMES.items():
        p=m['projections']['projection_'+key];e=p['residual_extension']
        lines.append(f'| {name} | {percent(1-p["tangent_projection"]["c"]["removable_squared_fraction"])} | '
                     f'{percent(e["hue_L"]["explains_of_remaining_squared"])} | '
                     f'{percent(e["hue_L_C"]["explains_of_remaining_squared"])} | '
                     f'{percent(e["hue_L"]["same_source_spatial_cv_explains_of_remaining"])} |')
    lines += ['',
        '这些样条只在同源图像的经验坐标中分解残差，没有实现可部署的三维映射。空间留出负值表示该样条在留出块上比保留原残差更差；加入彩度后的空间留出也全部为负。此结果暴露了支撑不足和插值不稳定，不能用来证明三维校正必然获得样本内收益。',
        '',
        '原始误差中，亮度 L 项的平方 ΔE00 能量只占 GR III 01/02 的 3.9% / 7.2%，HDF 01/02 的 3.9% / 8.5%。扣除全局明度与彩度项后，额外色相×明度对亮度残差的样本内解释仅占原始总能量的 1.6% / 3.2% / 1.0% / 2.8%。把全部 ΔL 都归为“三维独占误差”没有依据。',
        '',
        '## 断点、诊断与处理状态',
        '',
        f'本次只补 20 份缺失拟合：gr4_hdf_02 的 b/c 色段各 6 份，以及 gr4_hdf_01/02 的 b/c 正反向整图共 8 份。总计 312 = 12 全数据 + 216 留一 + 72 色段 + 12 整图。原有 292 份的 SHA256 全部保持不变；没有 --force，也没有调用 resume 重拟合旧结果。',
        '',
        '- strict_hinge_diagnostic.json 明确标为 gr3_01_b_full，120 次求值耗尽预算，整数灰块增量在 ISO 200/1600 为 +0.1085/+0.0780。当前有效 full 文件已在 37 次求值后按 ftol 终止，但灰轴仍失败；历史 strict-hinge 试验没有被采用。',
        '- same_fold_resume_diagnostic.json 记录 8 次求值后成功终止。其 theta 在当前 gr3_01_b 的 full 和 hue_03 上均复现 cost=66.27258325949857，差约 1.4e-14。两者的训练集等价，且文件没有折标识，不能唯一认定是哪一个；该 theta 也不同于当前有效 full 的 theta，不能说它已修好当前结果。',
        '- convergence_diagnostic.json 只有 with_grey / without_grey 的求解统计，没有 group、slot、level、kind、index 或 theta。无法从现存文件唯一追溯折号，也无法核实该匿名试验是否处理。它被保留为历史记录。',
        '- initial_full_fits/gr4_hdf_02_a_full.json 是最初未收敛的 a 控制，还曾未过安全门槛。前一次续做已用冻结 gr_pairs 中收敛的同折控制替代，当前有效 a/full 的求值次数为 25；旧版本仍保留在 local/，本次没有重新拟合。',
        f'- 当前仍有 {d["current_nonconverged_count"]} 份触及 nfev 上限，完整折名清单见 diagnostic_review.json。收敛只指求解器停止条件，不代表全局最优；非收敛结果也没有被叫作能力上限。',
        '',
        '因此，“只剩一处未收敛”不适用于当前 312 份结果。此轮遵守只补缺失项的范围，不再改优化器或扩大预算。',
        '',
        '## 包与交付状态',
        '',
        '没有满足留出与安全门槛的候选，因此没有生成 artifacts/stage2j-packages/tables-v6-gr-t1/，tables-v5-fuji-test/ 只读且校验和未变。DAT0==DAT1、V/W/X、无 U、仅 T1 槽进出写 T、关闭颗粒、field_diff 和 T1 使用守则都属于候选包的后续验收项，本轮没有包可验，不能写成已通过。',
        '',
        '公开交付为本报告、metrics.json、comparison.csv、diagnostic_review.json、verification.json 和 SHA256SUMS，以及可重跑脚本。comparison.csv 含两个 ISO、所有档位、五类协议的 96 行新旧并排结果。原有 baseline_metrics.json、strata_round5.csv、residual_by_hue.csv、projection_*.json 均直接采用并保持字节不变。',
        '',
        '## 复核与重现',
        '',
        '写入前已核实 Workspace 是已挂载、可写的 APFS 卷，UUID 为 14BE04EB-AF49-497E-B36A-B078B2F7C5E8，并执行 df -h /Volumes/Workspace，可用约 1.6 TiB。823 个去重保护输入及 523 份冻结副本的哈希均复核不变；104 份数据集的哈希与折规则记录相符。原有 local/ 结果除本任务的运行完整性日志外保持不变，任务目录以外的 Git 状态及已有 .gitignore、decisions.tsv 哈希保持不变。',
        '',
        '照片、固件、LUT、曲线、矩阵字、theta 和像素派生数据只存 local/；local/ 由本目录 .gitignore 忽略且没有被 Git 跟踪。公开文件检查禁止 ≥48 字节原始十六进制串、长字节常量和像素/参数数组。SHA256SUMS 覆盖除自身外的每个公开文件，包括最终核验报告。',
        '',
        '工作目录为 research/color_fit_v2/gr_dense_t1/。以下命令列出缺失项或复核结果，不重新拟合：',
        '',
        '```sh',
        'python3 -I -B run_dense.py full --start 0 --end 12 --dry-run',
        'python3 -I -B run_dense.py loo --start 0 --end 216 --dry-run',
        'python3 -I -B run_dense.py hue --start 0 --end 72 --dry-run',
        'python3 -I -B run_dense.py image --start 0 --end 12 --dry-run',
        'python3 -I -B verify_research.py final',
        '```',
        '',
        '这次补算的前台批次如下，各子进程预算 160 次求值、超时 55 秒，没有重跑已存在项：',
        '',
        '```sh',
        'python3 -I -B run_dense.py hue --start 60 --end 63 --jobs 3',
        'python3 -I -B run_dense.py hue --start 63 --end 66 --jobs 3',
        'python3 -I -B run_dense.py hue --start 66 --end 69 --jobs 3',
        'python3 -I -B run_dense.py hue --start 69 --end 72 --jobs 3',
        'python3 -I -B run_dense.py image --start 2 --end 6 --jobs 3',
        'python3 -I -B run_dense.py image --start 8 --end 12 --jobs 3',
        '```',
        '',
        '整数与安全复核使用 verify_research.py fits，按排序后的拟合清单每批最多 32 份，区间依次为 [0,32)、[32,64)、[64,96)、[96,128)、[128,160)、[160,192)、[192,224)、[224,256)、[256,288)、[288,312)，原始复核记录在 local/verification/。它们复算分数，不执行拟合。',
        '',
        '需要重新生成聚合交付时依次运行：',
        '',
        '```sh',
        'python3 -I -B verify_research.py diagnostics',
        'python3 -I -B summarize.py',
        'python3 -I -B report.py',
        'python3 -I -B verify_research.py final --write-checksums',
        'python3 -I -B verify_research.py final',
        '```',
        '',
    ]
    (r.HERE/'REPORT.md').write_text('\n'.join(lines))
    print('Chinese report written from verified aggregates',flush=True)


if __name__=='__main__':main()
