"""Rebuild the Chinese report from measured session artifacts."""
import html
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import session_runtime as s

NAMES = {'01': 'Posi', '02': 'Nega', '03': 'HC B&W', '04': '原厂 Standard', '05': 'Classic Chrome', '06': 'Classic Neg'}
SLOTS = ('01', '02', '03', '05', '06')


def read(path):
    return json.loads(path.read_text())


def pc(value):
    return f'{value * 100:.1f}%' if value is not None else '未定义'


def main():
    s.guard()
    out = s.LOCAL / 'analysis-final'
    scores = read(out / 'scores_C/scores.json')
    slots = scores['slots']
    predictions = read(out / 'scores_C/model_comparison.json')
    identities = read(out / 'identities.json')
    frames = read(out / 'frame_assignments.json')
    stability = read(out / 'stability.json')
    diag = read(out / 'diagnostics.json')
    verified = read(out / 'verification.json')
    assert verified['passed']
    bins = read(out / 'scores_C/lightness_chroma.json')['bins']
    lines = [
        '01 Posi：暂不能给稳定的“几成”；主表 −14.4%，换成五配方共同的 26 块是 20.9%。',
        '02 Nega：本次约 4.2 成。',
        '03 HC B&W：支持范围内约 9.9 成，但只有 46 块、18 个色相扇区。',
        '05 Classic Chrome：本次约 8.6 成；06 Classic Neg：本次约 8.1 成。',
        '这些“成数”是相对原厂 04 的误差缩减率；04 有 600/696 块被排除，不能当作原机照片的绝对相似度。',
        'M 模块六页数据能保留作校色输入，489 块通过测量质量检查；实际光圈、镜头标识和校正设置未确认，正式拟合仍被拦住。',
        '', '## 已核实', '',
        '最终只用 M 组 8 对和 C 组 43 对，共 51 对。用户确认 A 组拍错后，32 帧均在 manifest 中标为 exclude/trial，没有分配配方，也没有进入评分、标定或验证。初次解析在收到排除消息前已生成的 A 组记录留在 local/extraction/，不参与最终结果。',
        '',
        '卷预检通过：/Volumes/Workspace 已挂载、可写、APFS，UUID 为 14BE04EB-AF49-497E-B36A-B078B2F7C5E8。只写本任务目录；没有使用获准的另一个 chart_v2 run 输出位置。captures、官方固件、上游解析器及依赖均保持只读。没有访问相机或存储卡，没有生成上卡文件、安装包、启动子代理、commit 或 push。',
        '',
        f"使用的 DEEPTBL SHA-256 为 `{s.TABLE_SHA}`。本次沿用 ISO200 响应模型和原 closed_loop 目标，未重拟合。EXIF 不能证明机身加载了哪份 DAT，表身份仍依赖用户已核实的安装状态。",
        '', '### 自动识页和配方身份', '',
        'C 组 36 张色卡全部自动识为相应的 P1 至 P6，7 张白页为 1269、1276、1283、1290、1297、1304、1311。未按文件顺序强行覆写页码。逐帧页码证据、单应矩阵和取样框在 frames/ 与 quality.html 中。',
        '',
        '| 推定槽 / 模型最佳槽 | 帧号 | 自动页码 | 参与身份比较的块 | 最佳模型中位 ΔE00 | 次佳槽 / 中位 ΔE00 |',
        '|---|---|---|---:|---:|---|',
    ]
    for slot in ('04', '01', '02', '03', '05', '06'):
        group = identities['C_segments'][slot]
        ranked = sorted(group['candidate_model_de00'], key=lambda k: group['candidate_model_de00'][k]['median'])
        best, second = ranked[:2]
        q, other = group['candidate_model_de00'][best], group['candidate_model_de00'][second]
        lines.append(f"| {slot} / {best} | {group['frames'][0]} 至 {group['frames'][-1]} | {','.join(map(str, group['pages']))} | {q['n']} | {q['median']:.3f} | {second} / {other['median']:.3f} |")
    lines += ['',
        '六段的最佳槽均与 04、01、02、03、05、06 顺序一致，采用六页合并的高置信度身份。每个候选用同一 DNG 输入：先从同页 04 JPEG 条件反演，再按本帧 / 04 的原生 RAW 白平衡响应比例缩放；比较六个槽的预测与本帧 JPEG，不用目标相似度来挑槽。逐帧候选值、次佳差距及 500 次色块重采样胜率保存在 identities.json。重采样胜率不是槽号正确率的标定概率。',
        '',
        '04 作为条件反演锚，接近零的模型误差不是独立准确率。另用 RAW×4095 直接预测六候选，04 段六页的最佳槽也全部为 04，未依赖 04 JPEG 反演来确认这一步；候选值保存在 identities.json。06 使用绝对 T1 通道 R=C、G=B5、B=D；512 组输入与独立 np.interp 实现逐值一致，把三通道曲线设成相同时也与原 Engine 一致，两项最大 RGB 误差均为 0。',
        '', '### 50mm 实测总表', '',
        '相似度为 `1 − median(配方 JPEG→本槽目标) / median(配对 04 JPEG→本槽目标)`，分子分母用同一批有效块，固定 0 EV，不选最佳曝光锚。低于 0.25 ΔE00 的分母不定义；负值不截成 0。下表每槽都实拍了 696 块。',
        '', '| 配方 | 评分有效 / 696 | 色相覆盖 / 24 | 实测相似度 | 模型预测相似度 | 实测→目标 中位 / p90 | 04→目标 中位 | 实测↔模型 中位 / p90 |',
        '|---|---:|---:|---:|---:|---|---:|---|']
    for slot in SLOTS:
        q = slots[slot]; err = q['measured_vs_target']; model = q['model_vs_measured']
        lines.append(f"| {slot} {NAMES[slot]} | {err['n']}/696 | {sum(h['n'] > 0 for h in q['per_hue'])}/24 | {pc(q['similarity']['value'])} | {pc(predictions[slot]['predicted_similarity']['value'])} | {err['median']:.3f} / {err['p90']:.3f} | {q['similarity']['baseline']['median']:.3f} | {model['median']:.3f} / {model['p90']:.3f} |")
    lines += ['',
        '01/02 的目标是原有 GR III 实拍相对迁移 surrogate；03 是 GR IV HC 实拍平坦块近邻插值；05/06 是官方 Fuji F-Log2 LUT 通路。这些目标等级不同，以上数字不代表另一台相机的绝对相似百分比。04 控制的中位误差约 0.000008 ΔE00，来自以自身为条件的反演，不单列“100% 相似”。',
        '',
        '| 共同取样敏感性 | 01 | 02 | 03 | 05 | 06 |',
        '|---|---:|---:|---:|---:|---:|',
        '| 主表，各槽自身有效掩码 | ' + ' | '.join(pc(slots[k]['similarity']['value']) for k in SLOTS) + ' |',
        '| 五槽共同 26 块 | ' + ' | '.join(pc(diag['common_mask']['scores'][k]['value']) for k in SLOTS) + ' |',
        '',
        '共同 26 块只是取样偏差诊断，不能取代主表。01 从负分变成正分，说明当前样本不足以给稳定成数。GR 曝光锚敏感性如下，既不是置信区间，也没有用于挑选最终分数。',
        '', '| 槽 | −0.3 EV | 固定 0 EV | +0.3 EV |', '|---|---:|---:|---:|']
    for slot in ('01', '02'):
        lines.append('| ' + slot + ' | ' + ' | '.join(pc(q['similarity']['value']) for q in slots[slot]['gr_anchor_sensitivity']['rows']) + ' |')
    lines += ['', '### 与以前实拍、以前模型的对照', '',
        '| 配方 | 2026-10-21 R1 屏幕实拍 | 本次 C 组实拍 | 本次输入下模型预测 |', '|---|---:|---:|---:|']
    history = {'01': 33.2, '02': 71.3, '03': 88.1, '05': 72.9, '06': 74.1}
    for slot in SLOTS:
        lines.append(f"| {slot} | {history[slot]:.1f}% | {pc(slots[slot]['similarity']['value'])} | {pc(predictions[slot]['predicted_similarity']['value'])} |")
    lines += ['',
        '历史来源为 [REPORT_R1.md](../closed_loop/REPORT_R1.md) 的“原有目标下的结果”屏幕组；没有把同报告另一套 GR 固件目标混进来。旧样本是旧色环、旧表和另一组曝光，本次是新六页及当前表，掩码也不同，不能把两列相减当作配方升级收益。',
        '',
        '[Fuji round5 报告](../color_fit_v2/fuji_round5/REPORT.md) 为 05 主选(a)、06 主选(b) 给出的全屏模型预期是 90.91% / 93.38%，色相留出预期是 84.60% / 90.49%。它们来自旧数据和有限预算选型，不是今晚的盲测承诺。本次同输入、同掩码模型预测为 88.5% / 82.9%，实测为 85.7% / 81.1%，这两对才是本次可直接比较的实测与预测。',
        '', '### 24 个色相扇区', '',
        '每格为“相似度 / 有效块数”，采用本帧 RAW 的 D65 场景色相，每段 15°；中性块不进入色相表。不是色卡名义 P3 色相，也不是固件 CbCr 扇区。n<3 的格子仅保留读数，不据此决定调整。',
        '', '| 色相范围 | 01 | 02 | 03 | 05 | 06 |', '|---|---:|---:|---:|---:|---:|']
    for i in range(24):
        cells = []
        for slot in SLOTS:
            h = slots[slot]['per_hue'][i]
            cells.append(f"{pc(h['similarity']['value'])}/{h['n']}" if h['n'] else '缺测/0')
        lines.append(f"| {15*i}–{15*(i+1)}° | " + ' | '.join(cells) + ' |')
    lines += ['', '### 哪些颜色、明度和彩度拖后腿', '',
        '色相按 n≥3、明度和彩度组合按 n≥5 的实测→目标中位误差排序。L* 与 C* 来自本帧 DNG 驱动的配对 04 模型响应；L* 分为 <30、30–60、≥60，C* 分为 <15、15–40、≥40。坐标不是配方成片自身的色相或彩度。',
        '', '| 配方 | 较差色相区间：中位 ΔE00，n | 较差明度 / 彩度区间：中位 ΔE00，n |', '|---|---|---|']
    for slot in SLOTS:
        hues = sorted((h for h in slots[slot]['per_hue'] if h['n'] >= 3), key=lambda h: h['median'], reverse=True)[:3]
        bs = sorted((b for b in bins if b['slot'] == slot and b['n'] >= 5), key=lambda b: b['median'], reverse=True)[:2]
        hu = '；'.join(f"{h['hue_start_deg']}–{h['hue_start_deg']+15}°：{h['median']:.2f}，n={h['n']}" for h in hues)
        labelsL = {0: 'L*<30', 30: 'L*30–60', 60: 'L*≥60'}
        labelsC = {0: 'C*<15', 15: 'C*15–40', 40: 'C*≥40'}
        lc = '；'.join(f"{labelsL[b['L_min']]} / {labelsC[b['C_min']]}：{b['median']:.2f}，n={b['n']}" for b in bs)
        lines.append(f'| {slot} | {hu} | {lc} |')
    lines += ['', '### 排除的色块和质量瓶颈', '',
        '| 槽 | 本帧测量质量有效 / 696 | 疑似摩尔纹块 | JPEG 剪裁块 | 最终评分有效 |', '|---|---:|---:|---:|---:|']
    for slot in ('04', *SLOTS):
        q = diag['measurement_quality'][slot]
        lines.append(f"| {slot} | {q['valid']} | {q['flags'].get('moire-suspect', 0)} | {q['flags'].get('jpeg-clipping', 0)} | {slots[slot]['measured_vs_target']['n']} |")
    lines += ['',
        '质量原因可重叠，不能把两列相加。C 组色卡没有 RAW 饱和、闪烁条带或亮带标记；JPEG 剪裁同时包括黑端≤2和亮端≥253，不等于 RAW 过曝。疑似摩尔纹按冻结阈值“高频峰比>25且幅度>1.5码”排除，没有为了凑完整 696 块而放宽阈值。',
        '',
        '04 的 545 块疑似摩尔纹、253 块 JPEG 剪裁使共同基准只剩 96 块，是评分覆盖的主要瓶颈。其它配方即使本帧更干净，只要配对 04 被排除，也不能进入正式分数。03 还按原有目标支持域排除 361 个本帧点与 363 个配对 04 点，二者大量重叠。',
        '',
        '逐块清单为 local/analysis-final/excluded_patches_detailed.csv，精确区分本帧质量、paired04 质量与两侧目标支持域；包含 Mount 和白页的通用质量清单为 excluded_patches.csv。所有无效块的 RAW/JPEG 原测量仍保留，没有删行。已查看 C 组 04 P1 和 Mount P1 的取样框，ROI 位于色块内部；最终 Mount 叠加图已按修复后的有效性重画。',
        '', '### 漂移与屏幕均匀性', '',
        f"C 组 7 张白页 RAW 首尾变化为 {diag['white_raw_drift']['first_to_last_EV']:.5f} EV，全程范围 {diag['white_raw_drift']['range_EV']:.5f} EV，低于 0.03 EV 提示门限。对比先排除了 RAW 饱和；跨配方、跨 selector 的白页 JPEG 不当成原厂 04 重拍。",
        '',
        '原厂 04 没有首尾同页重拍，因此 JPEG 漂移为 unknown。跨页均匀性也是 unknown-incomplete：仅 2 个锚点能跨页比较，分别只有 2、5 个位置，没有一个完整覆盖六位置。观察到的最大 RAW 跨页跨度约 0.461 EV，去页公共曝光后约 0.107 EV；它们混有视角、镜头阴影和页面响应，不能认定为显示面板不均匀。完整数值在 stability.json。',
        '', '### Mount 逐帧结果与可标定性', '',
        '| 帧 | 自动页码 | 快门 | 质量有效块 | 本次用途 |', '|---|---:|---:|---:|---|']
    for f in frames:
        if f['group'] != 'M':
            continue
        purpose = '诊断重复，不进入主标定输入' if f['frame'] == 'R8051261' else '白页诊断' if f['kind'] == 'white' else '六页 04 主输入，元数据待确认'
        lines.append(f"| {f['frame']} | {f['page']} | 1/{round(1/f['shutter_s'])} | {f['measurement_valid']}/{f['total_patches']} | {purpose} |")
    lines += ['',
        '实际兼容故障包括 JPEG LensSpecification 标签 42034 和 DNG LensInfo 标签 50736 中的 0/0。薄适配只允许镜头/光圈描述标签的零分母记为未知；其它零分母仍报错。FNumber 没有有效正值，统一保留 null；请求过 f/5.6 不等于确认拍摄时用了 f/5.6。没有改 EXIF 或用名义镜头参数补成实际光圈。',
        '',
        'Mount 的 DNG/JPEG 元数据比较、识页和配准均通过。主交换输入只用 R8051262–1267 的六页、1/100 s，共 696 块，其中 489 块测量有效；1261 的 1/80 P1 重复保留在诊断 JSON，避免在主输入里重复加权。1268 白页带 JPEG 剪裁标记，没有冒充校色点。',
        '',
        '仍缺实际光圈、可区分实物镜头及转接环的稳定 lens_id、周边光量/R-B 阴影/畸变校正状态。Mount frames.json 因此明确 metadata_complete=false，aperture_f 和 lens_id 为 null，未伪造通过交换 schema 的完整帧元数据。拟合包装入口已实测在求解前拒绝这些缺项，日志为 local/mount_preflight.log。只拍 04 也无法验证 Mount 各配方的最终成像。',
        '', '### 交换数据及下一步命令', '',
        '| 数据 | 路径，均相对本任务目录 | 内容 |', '|---|---|---|',
        '| 50mm C 组 | local/analysis-final/exchange/50mm/patches.jsonl、frames.json | 36 帧，4176 行，1834 行测量有效；A 组未进入。 |',
        '| Mount 原厂 04 | local/analysis-final/exchange/mount/patches.jsonl、frames.json | 六帧，696 行，489 行测量有效；必要元数据未补猜。 |',
        '| 50mm 04 的配方目标 | local/analysis-final/exchange/50mm/targets_for_04.json | D65 Lab，按 page+patch_id+slot 绑定；使用 C 配对 04 自己的目标，不混入配方帧的不同 RAW 曝光。 |',
        '',
        '交换格式按 EXCHANGE.md 使用原生 CFA 均值及 JPEG ROI 均值，保留两侧空间 SD；评分仍用封存解析器的截尾中位数。两个估计量分别命名，不把中位数冒充均值。原始 RAW 未白平衡、未去马赛克、未写入屏幕 P3 设计值；gains 来自实测 AsShotNeutral 的倒数，G=1。',
        '',
        '原 calibrate.py 的输出边界只允许 module_adapt/local，本次没有在那里写数据。calibrate_session.py 只把 support.HERE/LOCAL 重绑到本任务，保留求解和验收规则。以下是后续获准重拟合时的确切输入；本任务没有执行这些求解。',
        '', '```bash', 'cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh',
        'task_root=research/chart_session_20261024',
        'data_root="$task_root/local/analysis-final/exchange/50mm"',
        'python3 -I -B "$task_root/calibrate_session.py" fit-04 \\',
        '  --patches "$data_root/patches.jsonl" --frames "$data_root/frames.json" \\',
        '  --unit 50mm --iso 200 --holdout-page 6 \\',
        '  --output local/future/50mm_iso200.json', '',
        'for recipe_slot in 01 02 03 05 06; do',
        '  python3 -I -B "$task_root/calibrate_session.py" learn-50mm-residual \\',
        '    --patches "$data_root/patches.jsonl" --frames "$data_root/frames.json" \\',
        '    --unit 50mm --iso 200 --slot "$recipe_slot" \\',
        '    --calibration "$task_root/local/future/50mm_iso200.json" \\',
        '    --output "local/future/50mm_${recipe_slot}_residual.json"', 'done', '',
        'for recipe_slot in 05 06; do',
        '  python3 -I -B "$task_root/calibrate_session.py" fit-recipe \\',
        '    --patches "$data_root/patches.jsonl" --frames "$data_root/frames.json" \\',
        '    --unit 50mm --iso 200 --slot "$recipe_slot" \\',
        '    --calibration "$task_root/local/future/50mm_iso200.json" \\',
        '    --targets "$data_root/targets_for_04.json" \\',
        '    --residual-prior "$task_root/local/future/50mm_${recipe_slot}_residual.json" \\',
        '    --output "local/future/50mm_${recipe_slot}_recipe.json"', 'done', '```', '',
        '50mm 逐槽通过原 calibrate.load_exchange 读取的可用数为 01=183、02=247、03=518、04=96、05=344、06=432。04 的 P6 留出有 12 块、其它页有 84 块，原生滑块与 Standard/control 契约通过。尚未执行 fit-04，不能预先保证求解收敛或留出验收。',
        '',
        '以现有独立目标与干净 04 相交，01/02/03/05/06 的 fit-recipe 可用目标点分别是 52/69/46/83/86。原入口要求至少 80 点，所以本轮只为 05/06 给出可尝试的 fit-recipe 命令；01/02/03 的残差可学，正式 fit-recipe 仍缺干净配对目标点。',
        '',
        'Mount 先在本任务 local/ 中另存经操作者确认的 frames.confirmed.json，补全真实光圈、lens_id 和校正状态，再使用下列输入；现有 frames.json 会在拟合前明确拒绝，不能绕过。',
        '', '```bash',
        'python3 -I -B research/chart_session_20261024/calibrate_session.py fit-04 \\',
        '  --patches research/chart_session_20261024/local/analysis-final/exchange/mount/patches.jsonl \\',
        '  --frames research/chart_session_20261024/local/analysis-final/exchange/mount/frames.confirmed.json \\',
        '  --unit mount --iso 200 --holdout-page 6 \\',
        '  --output local/future/mount_iso200.json', '```', '',
        '没有为 Mount 填用 50mm 的 targets_for_04.json。Mount 的 fit-recipe 还需根据 Mount 自己的 RAW 和后续 04 标定生成模块目标；50mm 残差借给 Mount 只是先验，不是 Mount 实拍验证。',
        '', '## 推断', '',
        '当前最先需要的是更完整、干净的 04 基准及固定目标口径。01/02 的成数大幅受曝光锚和有效掩码影响；05/06 的同条件模型误差约 0.58/0.84 ΔE00，可作为后续小步残差研究的起点。03 在其有限支持域中误差很小，没有证据要求立即调配方。以上是对本次样本的判断，不是改表后的响应验证。',
        '', '## 未知', '',
        '全 696 块、完整明度/彩度范围、不同光源与实际照片的相似度仍未知。01 的当前负分不证明它全面劣于 Standard，03 的 99.3% 不证明完整原机相似度。没有实体卡、Mount 配方实拍、完整首尾 04 重拍或六位置有效锚点，不能补出这些结论。',
        '', '## 复核与产出', '',
        f"verify_session.py 已独立复算五槽相似度，检查 51 对有效帧及 A 组排除，原交换解析器读取通过，源像素 ROI 均值复核误差为 0；{verified['unchanged_inputs_verified']} 项输入哈希保持一致。chart_v2 两份封存校验单分别核对 {verified['chart_seals']['SHA256SUMS']} / {verified['chart_seals']['ANALYZER_SHA256SUMS']} 项。T1 两项独立检查通过。",
        '',
        '关键交付：REPORT.md；session_runtime.py 与 repair_mount_metadata.py 薄适配；extract_session.py、analyze_session.py、diagnostics.py、quality_session.py、verify_session.py、make_report.py 可重跑流水线；calibrate_session.py 后续输出适配；local/analysis-final/ 下的 manifest、逐帧 JSON、配方与扇区 CSV、质量页、stability、排除清单、交换数据、verification；SHA256SUMS 覆盖本任务全部交付及私有证据，清单自身除外。',
        '', '```bash',
        'cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/chart_session_20261024',
        'shasum -a 256 -c SHA256SUMS',
        'git check-ignore -v local/analysis-final/exchange/50mm/patches.jsonl',
        'cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh',
        'python3 -I -B research/chart_session_20261024/verify_session.py', '```', '',
        '完整重跑使用新目录名，不覆盖已交付证据：', '', '```bash',
        'python3 -I -B research/chart_session_20261024/extract_session.py --out extraction-review',
        'python3 -I -B research/chart_session_20261024/repair_mount_metadata.py --extraction extraction-review --out mount-review',
        '# analyze_session 的 --mount 参数指向该次 Mount 适配输出。',
        'python3 -I -B research/chart_session_20261024/analyze_session.py \\',
        '  --extraction extraction-review --mount mount-review --out analysis-review', '```',
    ]
    (s.HERE / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    # Compact, self-contained inline table. Detailed research remains in the local report.
    rows = ''.join(f"<tr><td>{k} {html.escape(NAMES[k])}</td><td>{pc(slots[k]['similarity']['value'])}</td><td>{slots[k]['measured_vs_target']['n']}/696</td></tr>" for k in SLOTS)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>
    body{margin:0;color:var(--foreground,#222);font:14px/1.55 system-ui,sans-serif}
    table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:9px 7px;border-bottom:1px solid var(--border,#ddd)}
    th{color:var(--muted-foreground,#666);font-weight:500}p{margin:12px 0;color:var(--muted-foreground,#666)}
    @media(max-width:420px){th,td{padding:8px 3px;font-size:12px}}
    </style><table><thead><tr><th>配方</th><th>相对 04 的误差缩减</th><th>有效块</th></tr></thead><tbody>''' + rows + '''</tbody></table>
    <p>01 在共同 26 块上为 20.9%，当前成数不稳定。03 仅覆盖 18/24 个色相扇区。以上均为筛选后的屏幕色卡结果。</p>
    <p>Mount：六页 489/696 块通过测量检查。实际光圈、镜头标识和校正设置缺失，正式拟合尚不能启动。</p>
    <script>console.log(JSON.stringify({horizontalOverflow:document.documentElement.scrollWidth>window.innerWidth,rows:document.querySelectorAll('tbody tr').length}))</script></html>'''
    (out / 'summary.html').write_text(page)
    print('REPORT.md and local/analysis-final/summary.html rebuilt from verified measurements.')


if __name__ == '__main__':
    main()
