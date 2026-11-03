"""Render the Chinese report from aggregate statistics, never from image arrays."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import ROOT, HERE, LOCAL, guard, read
import json


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '|' + '|'.join(['---'] * len(headers)) + '|'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def pc(x):
    return f'{100 * x:.1f}%'


def main():
    guard()
    frames = read(HERE / 'metadata.json')
    scores = read(HERE / 'scores_summary.json')
    support = read(HERE / 'support_counts.json')
    out = ['# 网上 GR 新场景配对与 round5 整图留出评分',
'''已验证：五张新 DNG 中，只有 SC0134、SC0434 符合已解出的默认正片参数，归 A 组。Lecce、London 明确调过参数，归 B 组。R0011392 的键 0、高光 0、清晰度 +1 也偏离默认，归 C 组，不能补成“默认 GR III 独立场景”。

已验证：只有 DNG 也能提取拍摄时风格的全尺寸机内 JPEG，用作 RAW→风格配对。三份提供者导出的 JPG 与 DNG 内嵌图逐字节相同。它不能无条件替代高质量独立 JPG：两张 DPReview 的平均绝对码差是 1.205、1.478/255，原先“小于 0.5”的说法不成立；平坦区 ΔE00 中位为 0.520、0.416，p95 为 1.469、2.122。两对没有明显全局亮度或偏色差，但夜景压缩尾差会进入观测。

已验证：round5 01 在 A 组 ISO200 模型上的整图留出相似度，SC0134 为 64.1%，SC0434 为 78.4%，合并为 76.2%；相对旧 GR IV HDF 覆盖集 71.9%，分别差 −7.7、+6.5、+4.3 个百分点。ISO1600 模型分别为 64.3%、78.7%、76.6%。这些是不同场景分布的比较，不是改表后的提升。

已验证：SC0134 最大误差来自 GXR 04 色相 150–180° 的绿青段，主要是色相；黄色段另有彩度不足，且大部分高彩度黄花点因桥接范围或 Standard 支持不足而未评分。SC0434 主要误差在 60–120° 的黄至黄绿段。R0011392、London 的诊断误差主要是明度。GR III 默认正片和默认负片仍没有本批新增的合格整图验证。

推断：新数据足以研究 GR IV 正片的有限跨场景校正，但不足以支持一轮覆盖默认 01/02 的正式回拟。本轮只分析，没有回拟、生成表或写入固件；firmware_ready=false、deployable=false。''',
           '## 1. 元数据和分组',
'''“默认”指可解出的图像控制滑杆。依据是 DNGPrivateData 内的 RICOH 厂商注释：0x004f 为 ImageTone，0x0247 为滑杆记录。正片默认键/对比/高光/暗部为 −1/+3/−1/−2，负片为 +1/+1/0/−1；饱和、色相、锐度、暗角、清晰度默认均为 0。额外核对了既有 bastibe 与 HDF 正/负片，九项均符合该值，证据见 default_references.json。未解出的 GR IV 记录尾部和其他相机功能仍为未知。

EXIF Normal/High 不是滑杆值。R0011392 的 EXIF 与默认正片同为 Normal/High，厂商注释仍能确认它调过参数。''']
    rows = []
    for f in frames:
        m = f['metadata']
        rows.append([f['id'], m['model'].strip().replace('RICOH ', ''),
            m['firmware'].strip().split('Ver. ')[-1], m['datetime_original'],
            m['shutter_count'], m['decoded']['image_tone']['value'],
            ('默认正片，A' if f['group'] == 'A' else '非默认，' + f['group'])])
    out.append(table(['帧', '机型', '固件', '拍摄时间，无时区信息', '快门计数', 'ImageTone', '判定'], rows))
    out.append('快门计数按 0x005d XOR 日期 0x0006 XOR 左移一字节的时间 0x0007 XOR 0xffffffff 解扰。DPReview 的 134、434 同时与提供者 CSV 以及独立 JPG 对上；其余三帧为同一算法的读数，没有额外快门记录可交叉核对。文件名不用于推算计数。')
    rows = []
    for f in frames:
        c = f['metadata']['decoded']['image_control_0x0247']
        rows.append([f['id']] + [f"{c[k]:+d}" for k in ('saturation', 'hue', 'high_low_key', 'contrast',
            'contrast_highlight', 'contrast_shadow', 'sharpness', 'shading', 'clarity')])
    out.append(table(['帧', '饱和', '色相', '键', '对比', '高光', '暗部', '锐度', '暗角', '清晰度'], rows))
    out.append('五帧的复古调色均为不适用哨兵 −32768；黑白、漂白、HDR、交叉处理调色均为 −1、不适用，未见启用的调色项。0x0247 长度在 III 系列为 44 字节、IV 为 50 字节；不公开原记录字节。')
    rows = []
    for f in frames:
        m = f['metadata']
        n = '/'.join(f'{x:.6f}' for x in m['as_shot_neutral'])
        rows.append([f['id'], m['iso'], m['decoded']['dynamic_range_0x0069'],
                    f"{m['baseline_exposure']:.9f}", n, 'Auto / 0',
                    '/'.join(map(str, m['decoded']['shadow_correction_0x0079']))])
    out.append(table(['帧', '原片 ISO', 'DR 0x0069', 'BaselineExposure EV', 'AsShotNeutral R/G/B', '厂商 WB / EXIF WB', 'ShadowCorrection 0x0079'], rows))
    out.append('''DR 四字节均以 01 开头，按既有流程记开启；第二字节的 01/02 保留原值，不另猜强度或自动档。ShadowCorrection 是另一个状态字段，不能当作上表“暗部”滑杆。HDF 滤镜是否实际开启未知。

两张 GR IV 的 DNG 与独立 JPG，机型、固件、拍摄时间、快门计数、ISO、ImageTone 和完整已解滑杆一致。BaselineExposure、AsShotNeutral 来自 DNG，独立 JPG 没有这些字段。三份导出图没有 EXIF，其机型、拍摄参数和方向须与源 DNG 绑定，不能从导出 JPG 本身独立读出。原始路径、字段及逐项比较在 metadata.json。''')
    out += ['## 2. 内嵌 JPEG 能否替代单独 JPG',
'''已验证：两张 DPReview 的内嵌图和独立图均为 6192×4128，像素存储方向一致；DNG/独立 JPG 的 Orientation=1，内嵌 JPEG 自身没有方向字段。两边采样均为 Y(2,1)、Cb(1,1)、Cr(1,1)，即 4:2:2。没有旋转、缩放或重采样。

量化表明显不同；下表只公开统计，完整表以 SHA256 标识，避免公开连续原始字节。Q0/Q1 分别为亮度/色度表。''']
    rows = []
    for ident in ('SC0134', 'SC0434'):
        q = read(HERE / ('jpeg_' + ident + '.json'))
        for key, name in (('embedded', '内嵌'), ('provided', '独立 JPG')):
            qs = q[key]['quantization']
            rows.append([ident, name, f"{q['embedded_bytes' if key == 'embedded' else 'provided_bytes']:,}",
                '/'.join(f"{qs[k]['minimum']}–{qs[k]['maximum']}" for k in ('0', '1')),
                '/'.join(f"{qs[k]['mean']:.3f}" for k in ('0', '1'))])
    out.append(table(['帧', '图像', '文件字节数', 'Q0/Q1 范围', 'Q0/Q1 均值'], rows))
    rows = []
    for ident in ('SC0134', 'SC0434'):
        q = read(HERE / ('jpeg_' + ident + '.json'))
        d = q['flat_mean_delta_Lab_embedded_minus_standalone']
        rows.append([ident, f"{q['mean_absolute_code_difference']:.6f}", f"{q['flat_pixels']:,}",
            f"{q['flat_DE00']['median']:.3f} / {q['flat_DE00']['p95']:.3f}",
            '/'.join(f'{x:+.4f}' for x in d),
            f"{q['paired_observation_DE00']['median']:.3f} / {q['paired_observation_DE00']['p95']:.3f}"])
    out.append(table(['帧', '全图平均绝对 RGB 码差 /255', '平坦区完整像素数', '平坦 ΔE00 中位/p95', '均值 ΔL*/Δa*/Δb*，内嵌减独立', '配对 5×5 均值 ΔE00 中位/p95'], rows))
    out.append('''全图码差为所有像素、三个通道绝对差的平均值。平坦区取两张图共同满足 5×5 半尺寸四元组 RGB 标准差 <3.5、非裁切、边界 16 四元组、腐蚀 2 的区域，再对区域内全部原尺寸像素计算 sRGB→Lab D50 的 ΔE00。最后一列使用真正进入 gr_pairs 的同一坐标和邻域均值。未通过降低分辨率来计算全图码差。

已验证：平均 ΔL* 仅 −0.0076/−0.0179，最大平均颜色分量为 +0.0862 a*，没有足以解释配方主要残差的全局偏移。推断：主要差异来自更粗的 JPEG 量化；两图采样因子相同。不同压缩编码会在平坦区留下残差，邻域均值也不能完全消除夜景尾差。''')
    rows = []
    for ident in ('R0011392', 'Lecce', 'London'):
        q = read(HERE / ('jpeg_' + ident + '.json'))
        rows.append([ident, '6000×4000', '逐字节相同', q['embedded_sha256']])
    out.append(table(['帧', '尺寸', '提供者导出与 DNG 内嵌图', '两者共同 SHA256'], rows))
    rows = []
    for ident in ('SC0134', 'SC0434'):
        q = read(HERE / ('scores_' + ident + '.json'))
        for iso in ('200', '1600'):
            a = q['models'][iso]['score']
            b = q['embedded_same_coordinates_sensitivity'][iso]
            rows.append([ident, iso, pc(a['similarity']), pc(b['similarity']),
                         f"{100*(b['similarity']-a['similarity']):+.2f}",
                         f"{a['p90']:.3f} → {b['p90']:.3f}"])
    out.append('固定独立 JPG 的筛选坐标、Standard 和 GXR 预测，仅把观测风格替换为内嵌图，得到以下敏感性检查；没有为内嵌图重选更好样本。')
    out.append(table(['帧', 'GXR ISO 模型', '独立 JPG 相似度', '内嵌图相似度', '差，百分点', 'p90 ΔE00'], rows))
    out.append('明确回答：原始机内 DNG 在拍摄时已经选正/负片，且包含唯一、全尺寸、未被外部软件替换的相应机内 JPEG 时，可以作为成对数据；无需另存一个单独 JPG。必须读取真实滑杆并分组，使用 DNG 的几何、方向与 WB，保留非裁切平坦区和压缩误差。机型、固件或场景上的编码差异仍须复核；当前两对 GR IV 的数值不能保证所有 DNG 的压缩质量。London 已验证负片内嵌图的存在、配准及导出字节一致性，但本批没有可量化“负片内嵌对独立 JPG”差异的双文件对照，该差异未知。只有 DNG 本身不保证默认参数、未裁切范围、纹理/锐度或细小 ΔE 改善都可可靠评价。')
    out += ['## 3. 配对提取与覆盖',
'''原样引用 gr_pairs/extract.py 与 denoise.py，重定向 LOCAL、TMP 和解码器输出。2×2 RGGB 构成一个传感器四元组；c=(raw−black)/(white−black)，u_c=2^BE·c/AsShotNeutral·exp[−Σ a_i(r²)^(i+1)]。没有曝光重拟或按得分选择增益。

筛选与原流程相同：RAW 非饱和且各通道在 0.00005–0.985；JPEG 各原像素通道在 2–253 之间；5×5 的亮度 CV<0.055、逐通道 CV<0.10、JPEG 标准差<3.5；去边 16、腐蚀 2。按同一颜色格定额保留最多 60000 点，最后用各自 5×5 平坦邻域的均值作观测，原四元组值仍保存在 local/。五帧 RAW/JPEG 的边缘配准均通过，未重采样。

GR III HDF 用 GR III 径向系数；GR IIIx 同用该系数但明确为代理。GR IV 用既有共用系数。DPReview GR IV 1.01 与投稿 GR IV/HDF 的机身、固件和条件不同，共用系数不是逐机身重新标定。

coverage_<帧>.csv 每帧均为 180 个格，列名与 gr_pairs/coverage.csv 相同。坐标是输入 DNG 的 XYZ→Lab D50、参考白 Y=0.5；色相每 30°，L* 为 <20、20–40、40–60、60–80、≥80，C* 为 <8、8–25、≥25。下表的色相点数只计 C*≥8，中性色不伪计为色相覆盖。''']
    rows = []
    for f in frames:
        e = read(HERE / ('extraction_' + f['id'] + '.json'))
        c = e['counts']
        rows.append([f['id'], f['group'], f"{c['usable_quads']:,}", f"{c['retained_model_samples']:,}",
            f"{e['chromatic_150_270_eligible']:,}", f"{e['chromatic_180_240_eligible']:,}",
            '/'.join(map(str, e['chromatic_150_270_by_hue']))])
    out.append(table(['帧', '组', '可用四元组', '保留观测', '150–270° 有色点', '180–240° 有色点', '150/180/210/240° 起始四段点数'], rows))
    out.append('已验证：SC0134 确实补进青段；SC0434 虽有点，但只有 135 个原四元组。Lecce 为 0，London 仅 345；屏幕看起来有青/品红，不等于这些颜色通过了 RAW 非裁切与平坦筛选。R0011392 的 211511 个色段点属于非默认 C 组，不能并入默认目标。')
    out += ['## 4. 整张照片留出的定义与分数',
'''五个新 RAW 从未参与 round5 配方、曲线、Standard 模型或原风格函数的拟合。本轮先冻结表，再用新 RAW 和它自己的机内风格 JPEG 评分；没有将另一份 bastibe 导出或同 RAW 相邻块当独立照片。这与以前删除单个颜色邻域、空间块或色相段后回拟的验证不同。

分数仍是模型层证据。新照片提供实测 RAW→风格观测，GXR 端由既有 ISO200/1600 模型预测。由于新图没有同场景 Standard，先经共同白 ColorMatrix 桥接到 GXR，再读取冻结的 Standard 函数，在既有相对 LCh 规则下把“观测风格相对 Standard 的变化”施加到 GXR 04。没有用新照片回拟目标函数，也没有用旧 F_style 预测替代新风格 JPEG；旧风格支持域不限制新样本，Standard 无支持的点单独排除。

GR III/IIIx 使用既有 bastibe 联合模型的 Standard，域外按原流程使用 GR III pooled Standard；GR IV 使用旧 HDF Standard，属于不同机身的代理。中灰尺度固定为 GR III u118=0.08577678、GR IV 使用既有 pooled DR-off u118=0.0863322971，GXR 118 输入为 320；它是原有约定，不是新测出的 DPReview 或 IIIx 辐射定标。

先按 gr_pairs 的特征格 0.12/0.04/0.04、平坦权重每格选一点、上限 1600；再要求桥接后输入在 0–4095、GXR 04 各通道在 2–253、Standard 在支持域内。这个分数代表整张新照片中可评分的覆盖点，不是全图每个像素都通过。''']
    rows = []
    for f in frames:
        s = support[f['id']]
        rows.append([f['id'], s['feature_thinned_points'], s['physically_eligible_points'],
            s['excluded_unsupported_standard'], s['supported_points'],
            s['scene_D50_150_270_scored_chromatic'], s['scene_D50_180_240_scored_chromatic']])
    out.append(table(['帧', '特征抽稀点', '桥接/04 范围内', '其中 Standard 无支持', '主评分 n', '主评分 D50 150–270°', '主评分 D50 180–240°'], rows))
    out.append('相似度 = 1 − median ΔE00(配方→目标) / median ΔE00(原生04→同一目标)。不把负值截为 0。ISO1600 与 ISO200 使用同一观测目标和 ISO200 04 参照分母，沿用 gr_dense_t1 的协议；ISO 标签是 GXR 模型，不是把原片 ISO 改成该值。GR JPEG/Standard 的相对项按原流程在 Lab D50 计算，迁移后目标与 GXR 预测、误差分段使用既有 GXR Lab D65 坐标。')
    rows = []
    for q in scores:
        if q['group'] == 'A':
            rows.append([q['id'], q['iso'], q['n'], f"{q['median']:.3f} / {q['p90']:.3f}",
                pc(q['lt2']), pc(q['similarity']), f"{q['stock04_median']:.3f}",
                pc(q['reference_similarity']), f"{q['delta_percentage_points']:+.1f}"])
    out.append(table(['默认 A 组，01', 'GXR ISO 模型', 'n', 'ΔE00 中位/p90', '<2 占比', '相似度', '04 中位', '旧 HDF 分数', '差，百分点'], rows))
    out.append('合并按 353+1266=1619 个有效点重新求中位、p90、占比和分母，没有平均百分比；夜景贡献 78.2% 的点。A 组只有两张独立场景，1619 是观测点数。两张单图结果必须一起看。分布和分母不同，因此 +4.3 个百分点不能解释成配方提升，更不能代表所有自然照片。')
    rows = []
    for q in scores:
        if q['group'] != 'A':
            rows.append([q['id'] + ' / ' + q['group'], q['slot'], q['iso'], q['n'],
                f"{q['median']:.3f} / {q['p90']:.3f}", pc(q['lt2']), pc(q['similarity']),
                pc(q['reference_similarity']), f"{q['delta_percentage_points']:+.1f}"])
    out.append(table(['非默认诊断', '槽位', 'GXR ISO 模型', 'n', 'ΔE00 中位/p90', '<2 占比', '相似度', '旧 GR III 同槽分数', '差，百分点'], rows))
    out.append('R0011392 虽是独立 RAW，其 8.0% 不能当作默认 GR III 正片从 63.5% 跌落的证据；London 的 −111.6% 也不能当作默认负片泛化失败。它们检验的是固定默认配方面对非默认目标的差异。负相似度表示配方误差中位大于原生 04，不是计算异常。')
    out += ['## 5. 最大误差及 GR III/IV 黄色差异',
'''下文按 GXR 04 Lab D65 色相和明度分段，不能与 coverage 的输入 DNG D50 色相直接互换。误差贡献为 ΣΔE00² 占比；L/C/H 使用原 de00_components 分解，C/H 旋转交互项平分，三项严格加回总平方误差。这是当前样本上的误差归类，不是某种校正能力的因果收益。完整两 ISO、全部 30° 色相及 20 L* 分档在 scores_<帧>.json。''']
    rows = []
    for f in frames:
        q = read(HERE / ('scores_' + f['id'] + '.json'))['models']['200']
        ss = sorted([x for x in q['strata'] if x['kind'] in ('hue', 'neutral') and x['n']],
                    key=lambda x: -x['squared_error_share'])[:2]
        for s in ss:
            label = '中性 C*<8' if s['kind'] == 'neutral' else f"{s['start']}–{s['start']+30}°"
            rows.append([f['id'], label, s['n'], f"{s['median']:.3f} / {s['p90']:.3f}",
                         pc(s['squared_error_share']), f"{s['median_abs_delta_hue_deg']:.2f}"])
    out.append(table(['帧，ISO200', '最大两类色段', 'n', 'ΔE00 中位/p90', '平方误差贡献', '绝对色相误差中位°'], rows))
    rows = []
    for f in frames:
        q = read(HERE / ('scores_' + f['id'] + '.json'))['models']['200']
        e = q['residual']['exact_squared_DE00_energy_fraction']
        ll = sorted([x for x in q['strata'] if x['kind'] == 'lightness' and x['n']],
                    key=lambda x: -x['squared_error_share'])[:2]
        desc = '；'.join(f"L*{s['start']}–{s['start']+20 if s['start']<80 else '∞'}：n={s['n']}，{s['median']:.3f}/{s['p90']:.3f}，贡献{pc(s['squared_error_share'])}" for s in ll)
        rows.append([f['id'], f"{pc(e['L'])}/{pc(e['C_half_interaction'])}/{pc(e['H_half_interaction'])}", desc])
    out.append(table(['帧，ISO200', '全帧 L/C/H 平方误差贡献', '贡献最大的两档明度，ΔE00 中位/p90'], rows))
    out.append('''SC0134 的 150–180° 绿青段占平方误差 52.0%，绝对色相误差中位 10.41°，该段 H 项占 72.6%。90–120° 黄段 n=55，中位/p90=1.941/2.739，预测比目标少 2.62 C*。因此已评分区域首先暴露绿青色相问题，黄色主要是彩度问题。

已知 GR IV 黄色度不降、转 −9.5°，GR III 黄降至 0.77、只转 −2.7°；青在 GR IV 转 +19°。这说明把当前主要来源于 GR III 的正片关系直接用于 GR IV 黄/绿/青会遇到代际目标差。当前黄段彩度不足、绿青段色相误差与此方向相符，但场景的光源、明度、Standard 代理和桥接同时变化，不能把全部误差都归给该矩阵差。

尤其不能把“图中黄花很多”当作高饱和黄已验证：以输入 DNG D50 60–120°、C*≥25 定义黄花色域，1600 个抽稀点中有 468 个；其中 325 个未过桥接/GXR04 范围，余下 143 个又有 129 个缺 Standard 支持，主评分仅 14 个。这 14 个中位/p90=1.649/2.358，观测风格相对 Standard 色相转 −9.02°，只是有限覆盖诊断，不是恢复了整个 GR IV 黄矩阵。Standard D50 黄段另一定义的 n=23、彩度比 0.957 也不能与固件均匀色环的“度不降”逐数相等。相关计数与定义见 colour_diagnostics.json。

SC0434 的 60–90°、90–120° 分别贡献 55.5%、27.7% 的平方误差。其主体明度为 L*20–60；H/C 误差占 95.7%，全局明度偏移解释不了主要残差。R0011392 的 L 项占 93.3%，Lecce 97.0%，London 76.0%，与它们已确认的非默认键、高光和对比差异相符；压缩、DR 和 Standard 代理仍可能贡献误差，当前数据不能单独识别每项因果作用。''')
    out += ['## 6. 下一次回拟应如何留出',
'''推断：可以研究一次范围明确的 GR IV 01 回拟，因为新增两个默认、未用于训练的独立 RAW，且 SC0134 补进了旧数据缺少的有色区域。但应先解决 Standard 支持缺口，并保留 GR III/IV 的风格差异，不能把非默认 R0011392、Lecce、London 混进任何默认目标。

建议预先固定两个整图折：第一折只用既有默认数据加 SC0134 训练，SC0434 的所有 RAW/JPEG 点、目标函数和支持树全部留出；第二折反过来。Standard、ColorMatrix 桥接、118 锚和径向系数固定，禁止在留出帧上选参数。每张训练照片总权重封顶，不能让重复像素压倒独立场景。两个 ISO 都报相同点集的中位、p90、<2 占比以及色段、明度最坏项，不按较好的一折挑结果。

这些照片已用于本报告诊断，未来两折应称开发验证；最终验收另留一张此前未查看的新默认正片，最好含饱和 150–270° 及不同 L*。本批不支持默认 GR III 正片的新增整图折，也不支持默认负片回拟或负片跨代结论；负片矩阵跨代相同，不能抵消 London 的参数改变。若能补到 SC0134 同 DNG 的机内 Standard，可减少黄色目标代理的不确定性；本轮未获取该文件。''']
    out += ['## 7. 重跑和完整性核验',
'''所有脚本在本目录，以 python3 -I -B 从仓库根运行；源照片路径作为参数或 inventory 提供。依赖只用已安装 NumPy、SciPy、Pillow 和 C 编译器，没有网络、下载、安装、相机、存储卡或提交。原目录只读，新数据的 1/、2/ 按已知重复跳过。

第一次运行先逐目录调用 core.py 建立不可覆盖的 SHA256 基线。现有目录重跑时保留 local/protected_before_*.json，直接重跑分析及 verify.py。照片数组、逐点目标、源坐标、RAW 解码缓存、解码器临时文件全部在 local/；公开 JSON/CSV 只有元数据和聚合统计。SHA256SUMS 覆盖本目录全部公开文件，按清单惯例排除它自身。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
python3 -I -B research/gr_webpairs/metadata.py --data-root captures/contrib/2026-10-21-webpairs
for frame in R0011392 SC0134 SC0434 Lecce London
do
  python3 -I -B research/gr_webpairs/extract_pairs.py --frame "$frame" --inventory research/gr_webpairs/local/inventory.json
  python3 -I -B research/gr_webpairs/compare_jpeg.py --frame "$frame" --inventory research/gr_webpairs/local/inventory.json
  python3 -I -B research/gr_webpairs/score.py --frame "$frame" --inventory research/gr_webpairs/local/inventory.json
  python3 -I -B research/gr_webpairs/verify.py --pair "$frame"
done
python3 -I -B research/gr_webpairs/summarize.py
python3 -I -B research/gr_webpairs/diagnostics.py
python3 -I -B research/gr_webpairs/verify.py --sources captures/contrib/2026-10-21-webpairs
python3 -I -B research/gr_webpairs/verify.py --tree captures
python3 -I -B research/gr_webpairs/verify.py --tree artifacts
python3 -I -B research/gr_webpairs/verify.py --tree firmware
for part in 0 1 2 3 4 5
do
  python3 -I -B research/gr_webpairs/verify.py --tree research --part "$part"
done
python3 -I -B research/gr_webpairs/report.py
python3 -I -B research/gr_webpairs/verify.py --seal
python3 -I -B research/gr_webpairs/verify.py --final
```

已验证：五帧 lossless JPEG 解码均以独立 Python 前两行复核，像素不匹配为 0；五帧各抽查 64 个位置，共 320 个位置，重新计算归一化与 5×5 JPEG 均值。RAW 均值最大误差 <9.84×10⁻⁸，JPEG 均值最大差 1.53×10⁻⁵ 码。十项单帧及两项合并分数另用独立 CIEDE2000 实现复算。旧 gr_dense_t1 八项基线分数在 1×10⁻¹⁰ 内一致；01/02 整数曲线、矩阵、色度行与实际 DAT 对应条目一致，详见 round5_identity.json。

原仓库开始时已有修改和未跟踪目录，本报告不声称 Git clean。保护范围含 captures/、artifacts/、firmware/ 和已有 research/ 的全部文件，不限于本次读到的依赖；公开文件还检查了连续 ≥48 字节十六进制串、长字节常量和长原始整数数组。''']
    final = LOCAL / 'verification/final.json'
    if final.exists():
        out.append('终检命令的实际输出如下。')
        out.append('```sh\npython3 -I -B research/gr_webpairs/verify.py --final\n```')
        out.append('```json\n' + json.dumps(read(final), ensure_ascii=False, indent=2) + '\n```')
    (HERE / 'REPORT.md').write_text('\n\n'.join(out) + '\n')
    print(json.dumps(dict(report=str(HERE / 'REPORT.md'), sections=7, verification_included=final.exists()), ensure_ascii=False))


if __name__ == '__main__':
    main()
