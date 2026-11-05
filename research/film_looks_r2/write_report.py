"""Publish aggregate evidence only; LUTs, records, curves and photo data stay local."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

assert sys.flags.isolated
HERE=Path(__file__).resolve().parent;LOCAL=HERE/'local';UNITS=('a12-50','a12-28','mount-a12')
sys.path.insert(0,str(HERE))
import report_tables as T
def read(p):return json.loads(Path(p).read_text())
def f(x,n=2):return '—' if x is None else f'{x:.{n}f}'
def median(v):
    v=[x for x in v if x is not None]
    return statistics.median(v) if v else None


def main():
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args()
    cat=read(LOCAL/'catalog.json');results={};finals=0
    summary=read(LOCAL/'summary.json') if (LOCAL/'summary.json').exists() else None
    for film in cat['films']:
        for unit in UNITS:
            root=LOCAL/'analysis'/f'{film["ordinal"]:02d}'/unit
            path=root/'final.json'
            if path.exists():finals+=1
            elif not a.final:path=root/'screen.json'
            if path.exists():results[film['ordinal'],unit]=read(path)
    if a.final:
        assert finals==60
        assert all(d.get('analysis_revision')=='r3_unweighted_primary_weighted_control' and
                   d['selected_route'] in ('scene_rgb_matrix','scene_structure') for d in results.values())
        assert all(x.get('placement_classification_complete') for x in results.values())
        assert summary and summary['complete']
        assert len(read(LOCAL/'full_library_manifest.json')['records'])==60
        assert read(LOCAL/'capacity.json')['complete_input']
        for (ordinal,unit),doc in results.items():
            path=LOCAL/'analysis'/f'{ordinal:02d}'/unit/'final.json'
            receipt=read(LOCAL/'final_verification'/f'{ordinal:02d}'/(unit+'.json'))
            assert receipt['status']=='PASS' and receipt['analysis_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    out=['# GXR 胶片配方库与槽位评估', '',
        '官方 Acros 已可交 g157 换数据，必须配套 flags=1 的 03/Tri-X 基底。见 [ACROS.md](ACROS.md)。', '',
        ('本报告仍在更新：' if not a.final else '本轮结果：')+f'三单元共 {finals}/60 份胶片最终评价；'+f'已有 {len(results)}/60 份评价记录。'+
        ('未完成项均保留空格，不外推成绩。' if not a.final else '全部成绩均是修正 C040 后的电脑预测。'), '',
        '## 先解决满配位的兼容条件', '',
        '当前 g157 的 Look 引用 03 和 05，flags=1。六个真实解析反例证明：原封保留这些 Look，只把 base 改成 flags=7 会失败。按这种不重编码的做法，只剩 01、02、06、07、08 五个 L1 位。', '',
        '另一个数据方案已通过现有解析器的 18 个正例：完整条目统一 flags=7，锁定 Look 也用 flags=7/control=0，但 R/G/B 三个引用指向同一条共享曲线。它没有增加拟合自由度或曲线池行，也没有给 Look 加 L1 引擎。曲线末端须≥128，并重新计算 mask/内容身份；前向与微调等价检查见最终重放回执。', '',
        '这个方案仍须固定 Look 所借用的 base 应用元数据。若未来允许用户配方任意改变选择器、WB 和旋钮剂量规则，则应把 Look 的应用元数据与用户槽解耦。固定 04 或隐藏基底是另一种架构方向；当前 C/Python 都拒绝 base=04，不能直接换指针。', '',
        '校验合同与反例在 [local/studio_installation_contract.json](local/studio_installation_contract.json)。本轮没有改引擎或 Studio。', '',
        '## 固定参考与曝光', '',
        '本轮选 15 个 spektrafilm 档案，加上它没有的 Tri-X 400、Velvia 50、Kodachrome25、instax mini、Metropolis 五个 fotufilm 档案，共 20 片，覆盖 g157 全部七个胶片 Look。按负片、反转片、电影卷、推片、黑白和即时片覆盖来分配名额。未选的 spektrafilm C200、Ultramax 400、Portra 800 +1、Vision3 50D/200T 属于同类档案的扩展，本轮没有给它们打分，也不外推已选同系列的成绩。', '',
        '参考固定为场景 XYZ → 胶片模拟 → 档案默认冲印或扫描 → sRGB 输出。所有候选共用这一个目标。04 JPEG 叠加仅作对照。', '',
        'EV0 定为 D65 中性场景 Y=0.18，沿用冻结 RAW 测光锚点；输入增益固定为 1，不逐照片拟合曝光或 WB，也不强制把冲印后的中灰拉回某个输出亮度。该锚点来自既有 50mm 标定，另外两单元的绝对测光迁移及每种胶片的物理 lux·s/EI 对标仍未独立实测。推片档案沿用其默认曲线，不另外补一个未声明的曝光偏移。', '',
        'spektrafilm 的原生 V-Log/V-Gamut 65³ 烘焙保留场景高光，声明 gain=1，约有中灰以上八档的输入域。场景光先编码 sRGB 再送入中灰版 LUT，也保持 gain=1，但其有限域在场景线性 1、即中灰以上约 2.47 档处裁切。作者默认 sRGB 烘焙的 gain=2.88 相当于另加约 1.53 档；它不是本轮的标准曝光。', '',
        '彩色负片使用档案默认相纸；电影卷使用默认 Vision 2383；反转片按原烘焙已纠正的 GUI 规则直接扫描胶片，bundle 中的相纸占位名不代表实际冲印。fotufilm 补充项使用各自默认介质和固定定时，关闭 Auto Levels。空间效果和颗粒未进入颜色参考。', '',
        '## 硬件对应与结构对照', '',
        '满配记录使用独立 R/G/B 曲线、C100 矩阵和对称扇区；Look 对照使用一条共享曲线。胶片试验的两个位置都可在合法域内拟合 C100，避免把矩阵自由度误算成三曲线收益。数字风格对照则保持既有 C100 色度行，比较共同曲线与独立曲线。', '',
        '曲线可近似各层趾部、肩部和反差差异；矩阵可近似通道串扰；扇区补色相和饱和度。GXR 的顺序是曲线→矩阵→扇区，缺少已验证的独立后级冲印影调。真实胶片的光谱混合、层密度和冲印不能逐段原样搬进这个次序。', '',
        '这些曲线作用于相机 RGB，不是直接作用于胶片各层的光谱曝光。矩阵只能近似本轮光源和颜色域内的对应，无法从三个传感器通道恢复已丢失的光谱信息；同色异谱、窄谱 LED、钨丝灯和强色光仍需额外实拍。', '',
        '本地 15 份 spektrafilm 场景光 bundle 都是合成后的 1-LUT，中间曝光/密度/冲印 wires 全为空；原隔离引擎已清理，缓存也未找到可用 spektrafilm。遵守不联网、不安装依赖的约束，本轮用总响应灰轴初始化 RGB 曲线、局部颜色 Jacobian 初始化矩阵，并加弱灰轴约束，明确称为“结构化代理”。这不等于用真实分层密度约束。', '',
        '共享曲线侧也加入同类结构初始化，保留冷启动对照。主配方只在黑盒与结构代理之间按未加权整数训练损失选择；加权单独评价，不混入主线选择。留出照片只作评价和准入，避免把 MOUNT 冷启动卡在 04 的求解失败算成 L1 收益。', '',
        '本轮沿用现有 33 个曲线横轴节点，未搜索节点位置；C100 在声明的合法参数盒内拟合，关闭 C120、偏移、C004、RLUT 和非对称扇区。结果说明这套可复跑方法目前能做到多少，不是所有硬件参数组合的最优上限。', '',
        '编码纠正：新模板曾继承原厂 04 的 flags=0，写成 0/6。最终已改为 1/7；592 个既有记录文件仅改 flags 与 Look 内容身份，所有拟合行、参数和起点不变。3305340 个 RGB 输出逐点比较，最大差为 0，因此复用原数学 exact 回执；入选最终字节仍另做独立重放、C 端应用检查与 128 分支评价。原错误字节、JSON 和变换清单保存在 local/history/c100-enable-first-failure/，回执在 local/flags_repair.json。官方 Acros 未受影响。', '',
        '## 路线汇总', '',
        '百分比是相对原厂 04 的误差改善：100×[1−median ΔE00(记录,目标)/median ΔE00(04,目标)]，D65。它不是主观“像胶片”的打分。表中是逐片相似度的中位数，各片等权；所有路线按相同场景光目标评分。', '',
        '每种胶片各有自己的 04 误差分母，跨胶片不能只按百分比排名；挑默认时同时看绝对余差、特征保留和量化准入。', '',
        '| 路线 | 50mm 中位 % | 28mm 中位 % | MOUNT 中位 % |',
        '| --- | ---: | ---: | ---: |']
    if summary and summary['complete']:
        gains=' / '.join(f(summary['paired_full_minus_Look_pp'][u]['median']) for u in UNITS)
        ready=sum(x['all_units_default_shortlist_eligible'] for x in summary['films'])
        verdict=f"建议 g158 把胶片库放满配，锁定 {len(summary['locked_Looks'])} 个共享曲线不吃亏的 Look。20 片在 50mm / 28mm / MOUNT 的配对中位提升为 {gains} pp；{ready} 片在三个单元均过本轮量化门和灰轴诊断线。分数含义及逐片边界见下文。"
        at=out.index('## 先解决满配位的兼容条件');out[at:at]=[verdict,'']
    choices=[('共享曲线位置，训练优选','LOOK'),('满配，黑盒初始化','scene_rgb_matrix'),
        ('满配，结构化代理','scene_structure'),('满配，敏感色加权','scene_weighted'),('满配，未加权训练优选','FULL')]
    for label,route in choices:
        vals=[]
        for unit in UNITS:
            scores=[]
            for film in cat['films']:
                d=results.get((film['ordinal'],unit))
                if not d:continue
                r=d.get('selected_Look_route','scene_shared_matrix') if route=='LOOK' else d['selected_route'] if route=='FULL' else route
                scores.append(d['routes'][r]['scores']['photo_iso200']['similarity_percent'])
            vals.append(f(median(scores)))
        out.append('| '+label+' | '+' | '.join(vals)+' |')
    out+=['', '## 每片在两个位置的成绩', '',
        '每格为 Look / 满配。Look 安全须三个单元均小于 2 pp 的位置差，额外中位 ΔE00 不超过 0.25，且 128 分支分类稳定，两侧在主留出均须优于 04。2 pp 是容量选择预算，不是 JND；它把让位给更多锁定风格所接受的误差限制在 04 到目标误差的 2%，同时用绝对 0.25 门防止大分母掩盖明显损失。黑白高分需结合绝对余差。彩色负片、反转片、电影卷即使数值上通过，仍按机主策略放满配。', '',
        '| 胶片 / 来源 | 50mm % | 28mm % | MOUNT % | 满配准入量化最低 | Look 安全分支最低 | 本轮位置判断 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for film in cat['films']:
        cells=[];rows=[]
        for unit in UNITS:
            d=results.get((film['ordinal'],unit));rows.append(d)
            if not d:cells.append('—');continue
            look=d['routes'][d.get('selected_Look_route','scene_shared_matrix')]['scores']['photo_iso200']['similarity_percent']
            full=d['routes'][d['selected_route']]['scores']['photo_iso200']['similarity_percent']
            cells.append(f(look)+' / '+f(full))
        complete=all(d and d.get('placement_classification_complete') for d in rows)
        safe=complete and all(d['provisional_Look_safe'] and d.get('quantization_Look_safe_branches')==128 and
            all(d['routes'][r]['scores']['photo_iso200']['similarity_percent'] is not None and
                d['routes'][r]['scores']['photo_iso200']['similarity_percent']>0
                for r in (d['selected_Look_route'],d['selected_route'])) and
            d['routes'][d['selected_Look_route']]['quality']['passes'] and d['routes'][d['selected_route']]['quality']['passes'] for d in rows)
        status='待完成' if not complete else ('Look 安全' if safe else '需要满配')
        if safe and film['family'] not in ('bw','instant'):status+='；策略仍放满配'
        quant='—' if not all(d and d['phase']=='final' for d in rows) else str(min(d['quantization_passes'] for d in rows))+'/128'
        position_quant='—' if not all(d and d['phase']=='final' for d in rows) else str(min(d['quantization_Look_safe_branches'] for d in rows))+'/128'
        out.append('| '+film['name']+' / '+film['provider']+' | '+' | '.join(cells)+' | '+quant+' | '+position_quant+' | '+status+' |')
    out+=['', '## 胶片特征逐项评价', '',
        '“能做”指本轮样本与模型中的颜色表达；实机响应仍需单独验收。灰偏色以 ab 余差≤0.5 记作能做，它是本轮诊断线，不是人眼阈值。高光曲线的误差与 RAW 宽容度分开判断。扇区缺独立亮度轴，但 RGB 曲线与矩阵本身会产生部分亮度相关色偏，因此没有把这项简单记成零能力。饱和色以十二个输入色相跨 EV 扫描；跨亮度残差跨度先对每个色相的有效 EV 求跨度，再取色相间 P95 和三单元最差值。剩余色相/色度误差包含整条流水线及拟合误差，不能全部归因于扇区缺少亮度轴，也不是已证明的硬件误差下限。', '',
        '| 胶片 | 高光肩部 / 宽容度 | 暗亮灰偏色 | 饱和色随亮度变化 | 颗粒、光晕、边缘 |',
        '| --- | --- | --- | --- | --- |']
    for film in cat['films']:
        rows=[results.get((film['ordinal'],u)) for u in UNITS]
        if not all(rows):out.append('| '+film['name']+' | 待完成 | 待完成 | 待完成 | 颜色路线做不到 |');continue
        shoulder=max((d['tone'].get('supported_shoulder_error_de00',d['tone']['shoulder_error_de00'])['median'] or 0) for d in rows)
        cast=max(d['tone']['bands'][band].get('supported_chroma_ab_error_median',d['tone']['bands'][band]['chroma_ab_error_median']) for d in rows for band in ('shadow','highlight'))
        hue=[d['brightness_dependent_color'].get('supported_input_hue_error_degrees',d['brightness_dependent_color']['hue_error_degrees'])['median'] for d in rows]
        hue=[x for x in hue if x is not None]
        gray=('能做' if cast<=.5 else '部分能做')+'；ab 余差 '+f(cast)
        color='不适用：黑白' if film['family']=='bw' else '低色度，色相覆盖不足' if not hue else '部分能做；色相余差 '+f(max(hue))+'°'
        saturation=[d['brightness_dependent_color'].get('supported_relative_chroma_error_percent',{}).get('median') for d in rows]
        saturation=[x for x in saturation if x is not None]
        if saturation and film['family']!='bw':color+='；相对色度余差 '+f(max(saturation),1)+'%'
        spans=[d['brightness_dependent_color'].get('brightness_dependent_hue_span_degrees',{}).get('p95') for d in rows]
        spans=[x for x in spans if x is not None]
        if spans and film['family']!='bw':color+='；跨亮度色相残差跨度 P95 '+f(max(spans),1)+'°'
        bright=[d['routes'][d['selected_route']]['scores']['photo_iso200']['color_regions']['highlights']['median'] for d in rows]
        bright=[x for x in bright if x is not None]
        real='；实景亮部 ΔE '+f(max(bright)) if bright else '；实景亮部无足够点'
        source_limit='；来源在 +2.47 EV 裁切' if film['provider']=='fotufilm' else ''
        out.append('| '+film['name']+' | 部分能做；肩部 ΔE '+f(shoulder)+real+source_limit+'，宽容度待实测 | '+gray+' | '+color+' | 做不到 |')
    out+=['', '## 加权、质量门与留出', '',
        '敏感色使用固定 Lab 色域代理，不是人脸/天空/树叶分割；三个色域的训练权重均为 2.5，其余为 1。加权路线只有整体相似度损失不超过 1 pp、P95 增量不超过 0.25，并且相应颜色改善，才值得推荐。它不改变主库的未加权路线选择；未入选加权记录也未自动获得主配方的 128 分支准入。逐色域成绩与样本数保存在 local/analysis/。', '',
        '训练集含合成样本及预先指定训练场景的照片输入，目标均由模拟器生成。留出照片按整场景隔离，不进入求解残差或单次拟合的参数选择。主留出也用于触发加权路线的额外 exact 复核及推荐准入，因此加权推荐成绩是本轮验证结果，不能再称作推荐后的新盲测；独立新场景确认仍待补充。', '',
        '主照片留出为 50mm 48 张、28mm 189 张、MOUNT 67 张；另有 MOUNT 7 张独立 RAW。其他 ISO 为迁移诊断，不构成逐 ISO 标定；28mm 的 181 张集中在一个场次。灰轴、色相环和合成留出不替代这些实景。', '',
        '本轮拟合第一半 C100；彩色记录的第二半保留模板，黑白则两半都将色度归零。ISO100 曲线镜像一致只是记录约束，不等于已做独立 ISO100 色彩标定。配方库 manifest 明示主模型为 ISO200；其他 ISO 照片也用该主模型回放，仅作迁移诊断，没有验证各 ISO 的实际响应分支。', '',
        '已对 577 张主/其他 ISO 留出读取只读 EXIF，按冻结采样统计有 50 张亮部比例不少于 10%，未读到正曝光补偿标记。亮部样本能检验高光段误差；原采样排除了 RAW 已裁切像素。缺少已知曝光量的同景包围，无法量出真实胶片与 GXR 的宽容度差。上表肩部来自有效输入内的中性轴，实景亮部为场景 Y≥0.72 的采样点，均取三个单元中最差的中位余差。', '',
        '128 个分支为两种 RGB/YCbCr 取整顺序与每分量 0/.25/.5/.75 相位。它是量化敏感性，不是实际 ISP、4:2:2 共色度和 JPEG DCT 的逐位仿真。保留训练改善、主照片中位/P95、逐照片近零分母绝对门、MOUNT 0.1 pp 门、场景门及固定 04 质量夹具。', '',
        '## 字节与 Studio 交接', '',
        '每条满配展开记录为 552 B，三单元×20 片共 33,120 B。L1 的 R/B 曲线本来就在该结构内。实际装卡增量由输入节点、曲线、96 B 扇区、56 B 矩阵行的共享/移除、描述符与对齐决定，不能把 552 B 直接当净增加。', '',
        '33,120 B 是电脑配方库总量。机内只装用户所选的七组、每组三单元记录，不要求把 20 片同时放入行池。', '',
        '本报告的净字节按使用行紧凑重打包，不计空余保留容量；若构建器保留空行或描述符空位，须按实际分配重算。', '',
        '交付 2 的容量基线为冻结 g157 计划布局加上已交接的官方 Acros 替换；原 Alchemy 布局仍保留作 Acros 对照，没有改写原始 manifest。', '',
        '最终库见 [local/full_library_manifest.json](local/full_library_manifest.json)，单条替换 06 的净行池增量见 [local/record_costs.json](local/record_costs.json)。该预算基于冻结 g157 数据布局，不包括正在变化的代码/BSS，也未生成 DAT。约 18 个是逻辑 Look 数；三单元都不同会需要最多 54 个描述符，超过当前 GXFX 的 48 上限，必须按实际共享重新计数。', '',
        'Studio 安装必须校验单元/模型来源、552 B 长度、行 CRC、字段域、单调曲线、flags 与 type26 control。独立曲线归档用 flags7/control0；共享归档用 flags1/control2，安装时也可用 flags7/control0 共用一条曲线。重绑槽位要同时重建元数据/描述符/内容身份，保护 04 pin，按内容身份作废或迁移旧微调，并检查实际 base、跨单元 mask、行池和总分配。03/Tri-X/Acros 依赖应作为整组处理。', '',
        '## g158 建议与锁定 Look', '',
        'g158 优先评估在 flags7 下让 R/G/B 共用一条曲线，统一完整条目的 Standard 应用元数据，再由 Studio 原子替换并校验依赖。若要开放 WB/选择器/剂量配置，则改用独立 Look 应用元数据。投票候选按负片、反转片、电影卷与特殊风格分组；胶片主库优先 spektrafilm，仅补它缺少的 fotufilm 档案。满配配方按整数训练选择，留出只决定准入。', '',
        '锁定 Look 的具体建议和 g157 逐项去留见下表。满配库首先按全部既有门槛准入，再让用户按题材与口味投票；未过 128/128、出现额外灰轴回落或依赖不兼容的记录不选作默认。三条独立曲线已属于现有 552 B 完整条目，本轮不建议给轻量 Look 扩展 L1 引擎。', '']
    out+=['扩大胶片选择放在 Studio 配方库中解决；机内按用户投票装七组满配。锁定 Look 不足约 18 个时保留空位，继续找共享曲线确实不吃亏的数字/创作风格，不用损失明显的胶片凑数。flags7 下 R/G/B 共用曲线不会增加独立曲线参数或池行。','']
    if summary:
        ready=[x['name'] for x in summary['films'] if x['all_units_default_shortlist_eligible'] and x['placement']=='full']
        pending=[x['name'] for x in summary['films'] if x['complete'] and not x['all_units_default_shortlist_eligible'] and x['placement']=='full']
        if ready:out+=['可进入后续主机/实机试装及用户投票的满配模型候选为：'+'、'.join(ready)+'。七个位由用户投票决定，可覆盖负片、反转片和电影卷，分数不代替口味。','']
        if pending:out+=['暂不列入默认组合的完整候选为：'+'、'.join(pending)+'。它们仍随研究库交付，具体量化失败和误差见逐片表；修复或实测闭环前不把高总分当成准入。','']
    out+=['锁定清单交付的是风格与位置建议。数字风格保持各自声明的输入约定，只作位置分配对照；g158 若替换其原有 Look 数据，还需走整组发布门。官方 Acros 已单独交接；本轮可供 Studio 导入的记录库是下述 60 条满配胶片候选。','']
    if summary:
        out+=T.locks_and_retention(summary)
    out+=T.absolute_and_routes(cat,results)
    out+=T.controls(cat,results)
    if summary:out+=T.weighting_and_diagnostics(summary,results)
    out+=T.weighted_validation()
    out+=T.byte_tables(cat)
    out+=['## Studio 替换约束的具体含义','',
        '01、02、03、05、06、07、08 是可配置完整条目的目标范围，不是当前可以任意替换的承诺。库中 byte0=06 是规范化归属，改装到别的槽时必须重新生成槽位绑定、身份与校验，不能只改 byte0。目标引擎、格式和链接布局须匹配；模型单元、校准来源和 native C040 也必须一致，不能把 50mm 的记录直接标成 28mm 或 MOUNT。', '',
        '用户只可替换这些满配位。锁定 Look 的名称、颜色 payload 和单元绑定由发布清单管理，Studio 应按发布哈希核对，不开放给用户改名、重拟合或换片；允许的格式重编码也须有已验证的前向和微调等价回执。', '',
        '解析器的强约束是 Look flags 等于 byte0 实际引用的基础槽 flags；本产品另按机主规则要求它也等于该单元 05 的 flags。大多数 Look 引用 05，所以替换 05 会牵动它们；Acros/Tri-X 原来引用 03，须按 recipe_redo 的兼容组原子处理。官方 Acros 已交接版本冻结了 03/05=1 的 g157 布局前提，新锚点布局不能直接套用该交接结论。', '',
        'flags 相等仍不充分。引擎还从 Look 的 base 读取选择器、原生参数字节、WB 偏移及旋钮剂量配置；同为 flags=1 的新配方也可能改变 Look 的应用结果。Studio 应绑定这组应用元数据的指纹，替换后保持一致或重新验证。', '',
        '完整条目也应保护 ISO100 镜像、两半矩阵、十个行引用及其 CRC、单调输入节点/输出曲线、矩阵域、独立 R/B 末端码约束、type26 control 与 flags 的对应。拟合归档的共享记录用 flags=1/control=2，独立曲线用 flags=7/control=0；共享记录也可在重编码后用 flags7，让 R/G/B 引用同一条曲线。不能把 flags7 当成“必有三条不同曲线”。升降格式都要重建身份并证明等价。', '',
        '库中评分按 S_mode=04 Standard 的普通颜色链执行；黑白通过物理色度系数归零得到。Studio 生成的选择器及参数字节必须与此一致，不能改用原生 BW 选择器。当前 03 的控件可见性还有按槽位写死的规则，把彩色胶片放入 03 时也要同步审核控件元数据和 UI；目的槽原有的 BW/颗粒能力位也不能盲目继承。', '',
        '整组替换后重算 Look mask 覆盖的所有单元、实际 base、GXFX 48 描述符上限、基础/额外行池上限及总分配；不能静默改 Look flags 来通过解析。04 原厂 pin 和恢复路径保持可用，旧 GXTS/微调按内容身份作废或迁移，不能让旧状态误套新配方。数据解析通过后还要验应用、恢复、菜单、保存与断电重启。合同和六个实际解析反例在 local/studio_installation_contract.json。', '',
        '显示名称与 DAT 描述符名称分开。Look 写入格式的短名为 1–12 个可打印 ASCII 字节，不能含星号或反斜线，其余位置补零；例如 Acros official 的实际短名为 Acros，ARRI Classic709 为 ARRI 709。新增名称必须无冲突，跨单元合并时重新计算 mask 和内容 CRC。', '',
        '当前菜单还要求 9 + 该单元 Look 数 + 已保存用户条目数 ≤ 49。七个满配位属于原有内置条目；额外保存的微调用户条目才进入最后一项。18 个锁定 Look 会把这部分上限压到 22 个，Studio 需和描述符/行池一起检查。', '',
        '## 来源与默认冲印', '',
        'spektrafilm 0.3.3，Andrea Volpato，commit 500bc429b7e93450ef228305c319dc03d8e185d1；[项目来源](https://github.com/andreavolpato/spektrafilm)。Pro 400H、Superia 使用 Fujifilm Crystal Archive Type II；Ektar、Gold、Portra 系列用 Kodak Portra Endura；Verita/Vision3 用 Kodak 2383；Provia、Velvia 100、Ektachrome、Kodachrome 64 直接扫描反转片。', '',
        'Fotufilm/MUAStudio Inc.，fotufilm-engine 1.14.1，commit 96623ba0831a52dbddcda35727a206d4123a8b5f；[项目来源](https://fotufilm.com)。仅补 spektrafilm 缺少的五片，保持原档案默认介质、固定定时与关闭 Auto Levels。其 sRGB 输入烘焙对高光有限域的限制单列为来源限制。', '',
        '上述胶片档案/派生颜色按 CC BY-SA 4.0 保留作者、版本、修改说明和相同方式共享义务，许可原文与来源 SHA 随 local/film_sources 和配方 manifest 保存。富士、徕卡官方 LUT 和包含 Ricoh 行的记录没有在本轮获得公开再分发许可，保持本地。', '',
        '## OPEN 与交付边界', '',
        '- 七槽数据方案需 Studio 原子重编码共享 Look、冻结 base 应用元数据，并完成整组应用/恢复/保存状态验证；若要允许这些元数据自由变化，仍需独立 Look 应用元数据。',
        '- 本地缺真实分层密度及独立冲印曲线，本轮仅测试结构代理；GXR 次序也限制一一对应。',
        '- 本轮分数衡量对指定胶片模拟器默认输出的逼近；没有同场景真实胶片扫描对照，不能据此声称已量出与真实胶片的误差。',
        '- 真实宽容度缺曝光包围，传感器已裁切的高光无法由颜色表恢复；完整曲线响应、非 ISO200、跨单元光谱/角向核及蓝色/肤色残差未闭合。',
        '- 降低数字采集曝光再补亮可以换取高光空间；例如少一档曝光意味着少一半光子。它保留同一场景光目标，但暗部噪声和实际收益须重新标定，本轮固定 EV0 的分数未计入此路线。',
        '- 达迭代预算的起点原样保留，不宣称全局最优。正式入选记录需 reference exact 全起点复核及独立字面链重放；实机新候选曝光数为零。',
        '- Leica Natural、Pure、Cine 的 MOUNT 两侧均停留在 04 模板，约 0%；本轮不能判定其位置，不列入锁定清单。',
        '- 颗粒、光晕和胶片锐度边缘不在逐像素颜色流水线内。现有 eng_grain.c 已提供场景 21 的独立颗粒入口和三级强度，但本轮没有按胶片标定颗粒统计，也没有重验实机范围。电脑端可接原胶片引擎做噪声、邻域光晕和边缘处理；Studio 仍需集成。机内光晕路线另需验证邻域缓冲与耗时，现有锐度档只能粗略近似边缘变化。', '',
        '全部 LUT、派生表、Ricoh 行、照片数据及逐照片证据都保留在 Git 忽略的 local/。spektrafilm/Fotufilm 派生颜色须保留 CC BY-SA 4.0 署名；富士/徕卡官方资料及嵌入 Ricoh 行未在此认定可公开再分发。没有 commit/push、网络、依赖安装、相机或卡操作。', '']
    (HERE/'REPORT.md').write_text('\n'.join(out))
    print('REPORT', 'FINAL' if a.final else 'DRAFT',len(results),'profiles,',finals,'final')


if __name__=='__main__':main()
