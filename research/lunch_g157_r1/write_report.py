"""Publish aggregate Chinese findings and an entirely local owner review page."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import html
import statistics

NAMES = {'QianXi A':'千禧回声 A', 'QianXi B':'千禧回声 B', 'ARRI 709':'ARRI Classic709'}
REGIONS = {'neutral':'中性色', 'red':'红色', 'yellow':'黄色', 'green':'绿色',
           'cyan':'青色', 'blue':'蓝色', 'magenta':'品红色', 'dark':'暗部', 'middle':'中间调', 'bright':'亮部'}


def name(x):
    return NAMES.get(x, x)


def f(v, digits=2):
    return '未定义' if v is None else f'{v:.{digits}f}'


def pair(v):
    return f(v['median']) + ' / ' + f(v['p95'])


def table(header, rows):
    return '\n'.join(['| ' + ' | '.join(header) + ' |',
                      '| ' + ' | '.join('---' for _ in header) + ' |',
                      *['| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows]]) + '\n'


def status(row):
    if row['exact_record_ambiguous']:
        return '暂定；05 与默认用户项等价'
    return '通过' if row['accepted'] else '暂定；分差窄'


def frame_table(rows):
    return table(('照片', '时间', '第一名', '第二名', '分差 ΔE00', '留出中位 / p95', '判定'),
        [[f"[{r['id']}](local/index.html#{r['id']})", str(r['metadata']['when']).split()[-1],
          name(r['best']), name(r['second']), f(r['gap_de00']), pair(r['prediction_D50']), status(r)] for r in rows])


def accuracy_table(rows):
    return table(('配方响应', '张数 / 通过数', '留出块', '中位 ΔE00', 'p95 ΔE00'),
        [[name(r['name']), f"{r['photos']} / {r['accepted']}", f"{r['prediction_D50']['n']:,}",
          f(r['prediction_D50']['median']), f(r['prediction_D50']['p95'])] for r in rows])


def style_table(rows):
    out = []
    for r in rows:
        if r['name'] == '04 Std':
            continue
        old, new = r['style']['old'], r['style']['r2']
        out.append([name(r['name']), str(r['photos']), f(old['actual_similarity'], 1) if old else '无目标',
                    f(new['actual_similarity'], 1) if new else '无目标',
                    pair(new['actual_target']) if new else '无目标',
                    f(new['model_similarity'], 1) if new else '无目标'])
    return table(('配方', '张数', 'g157 原目标 %', 'film_r2 目标 %', '实拍到 film_r2 目标 ΔE00 中位 / p95', '模型到同目标 %'), out)


def local_page(summary):
    cards = []
    for r in summary['rows']:
        pid = r['id']
        images = [('实际 JPEG', f'frames/{pid}/actual.jpg'),
                  ('第一名预测', f"frames/{pid}/predictions/{r['best_index']:02d}.jpg"),
                  ('g157 原目标', f'frames/{pid}/target-original.jpg'),
                  ('场景光目标', f'frames/{pid}/target-scene.jpg'),
                  ('第二名预测', f"frames/{pid}/predictions/{r['second_index']:02d}.jpg")]
        figures = ''.join(f'<figure><img loading="lazy" src="{p}" alt="{html.escape(label)}"><figcaption>{html.escape(label)}</figcaption></figure>'
                          for label, p in images if (C.LOCAL / p).is_file())
        cards.append(f'<section id="{pid}"><h2>{pid} · {html.escape(name(r["best"]))}</h2>'
                     f'<p>{html.escape(status(r))}；第二名 {html.escape(name(r["second"]))}；分差 {f(r["gap_de00"])}；'
                     f'留出误差 {pair(r["prediction_D50"])}</p><div class="images">{figures}</div>'
                     f'<p><a href="frames/{pid}/result.json">响应排序与置信信息</a> · '
                     f'<a href="frames/{pid}/targets.json">两种目标的评分</a></p></section>')
    page = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'">'
            '<title>g157 实拍本地复核</title><style>body{font:16px system-ui;max-width:1500px;margin:32px auto;padding:0 20px;background:#f8f7f4;color:#252525}'
            'h1{font-size:26px}h2{font-size:18px}section{border-top:1px solid #ccc;padding:20px 0}.images{display:flex;flex-wrap:wrap;gap:12px}'
            'figure{margin:0}img{display:block;width:256px;height:auto}figcaption{padding:7px 0;color:#555}a{color:#245e94}</style>'
            '<h1>g157 实拍本地复核</h1><p>照片与派生图仅在 local/。预览宽 256 像素，是 CFA 颜色示意，不模拟空间 ISP；'
            '定量评分来自原分辨率的固定平滑块，预览不会参与选配方或评分。</p>' + ''.join(cards) + '</html>')
    (C.LOCAL / 'index.html').write_text(page)


def main():
    C.admit('report')
    summary = C.read(C.LOCAL / 'summary.json')
    verification = C.read(C.LOCAL / 'verification.json')
    assert verification['status'] == 'PASS'
    diag = C.read(C.LOCAL / 'diagnosis.json')
    lunch = summary['scopes']['lunch']
    morning = summary['scopes']['morning']
    confident = summary['scopes']['lunch_confident']
    board = summary['scopes']['final_scene']
    rows = summary['rows']
    lr = [r for r in rows if r['group'] == 'lunch']
    mr = [r for r in rows if r['group'] == 'morning']
    k = next(r for r in lunch['recipes'] if r['name'] == 'Kodachrome25')
    kc = next(r for r in confident['recipes'] if r['name'] == 'Kodachrome25')
    kb = next(r for r in board['recipes'] if r['name'] == 'Kodachrome25')
    kphotos = sorted(r['scene']['actual_similarity'] for r in k['similarity_photos'])
    ids = summary['final_scene']['group_ids']
    boardrows = [r for r in rows if r['id'] in ids]
    first = f"午间实拍：识别 {lunch['accepted']}/44，预测偏差中位 ΔE00 {f(lunch['overall_D50']['median'])}"
    body = [first, '',
        f"颜色模型基本能解释这批实拍，午间 p95 为 {f(lunch['overall_D50']['p95'])}。Kodachrome 25 的相机输出符合模型，但与场景光胶片目标仍有明显距离。"
        f"其原目标相似度为 {f(k['style']['old']['actual_similarity'],1)}%，按 film_looks_r2 的场景光目标只有 {f(k['style']['r2']['actual_similarity'],1)}%。",
        '',
        f"29 张通过沿用的严格识别线，另 15 张保留暂定第一名。首行误差合并 44 张第一名假设的 {lunch['overall_D50']['n']:,} 个空间留出块；"
        f"只看 29 张通过样本，中位 / p95 为 {pair(confident['overall_D50'])}，结论相同。N 表示达到响应判定门槛的照片数，不是有独立菜单记录的正确率。",
        '', '## 配方识别表', '',
        '下表分差是“第二名减第一名”的识别区中位 ΔE00。通过线为第一名中位 ≤5、分差 ≥0.75、240 次空间块重抽样胜率 ≥95%，且另一半画面仍选同一第一名。'
        '本批 15 张暂定项均在两半画面得到同一第一名，并赢得 240/240 次空间抽样；它们仍因分差不足 0.75 保留待定。', '',
        frame_table(lr),
        'R8052094 的 05 F-CC 与用户项 FCC-001 在颜色响应上等价，照片无法区分菜单名称。它的第二个不同响应为 FCC*002。'
        '候选包含实际 DAT 的 8 个基础配方、18 个 MOUNT Look 与 3 个用户项，未按口述顺序限制候选。', '',
        '与口述核对：R8052063 首张确为 04 第一名；R8052063 至 R8052066 连续四张均为 04。'
        f"Kodachrome 25 共获 {k['photos']}/44 张第一名，其中 {k['accepted']} 张通过严格线，是本批最多的配方。"
        f"广告牌段为 {ids[0]} 至 {ids[-1]}，共 {len(ids)} 张、17 种第一名响应；之后 9 张又回到 Kodachrome 25。"
        '这与机主描述的主要顺序吻合，但没有证据把未拍到的候选也算作已验证。', '',
        '早上 11 张也逐张核对，全部通过同一识别线。', '', frame_table(mr),
        '## 各配方的预测准确度', '',
        '以下为模型输出对实际 JPEG 的 ΔE00，采用 sRGB 经 Bradford 转 D50，便于与 model_c040_r1 的相机响应留出比较。'
        '张数包含暂定第一名，同时列出通过数；小样本行只说明这次曝光。', '',
        accuracy_table(lunch['recipes']),
        '早上 11 张另计，不能把黑白样本的低误差混进午间结论。', '', accuracy_table(morning['recipes']),
        f"早上合并中位 / p95 为 {pair(morning['overall_D50'])}；逐照片中位数的中位为 {f(morning['equal_photo_medians']['median'])}。"
        f"午间逐照片中位数的中位为 {f(lunch['equal_photo_medians']['median'])}，与按平滑块合并的 {f(lunch['overall_D50']['median'])} 接近。", '',
        '与旧留出比较时优先取同为 ISO200 的历史组。下面都是 D50；本轮曝光掩码更严格，场景和配方比例不同，因此这张表不作同景显著性检验。', '',
        table(('相机响应留出', '照片数', '中位 / p95 ΔE00'), [
            ['2026-10-31，native C040，ISO200', '8', '0.66 / 2.07'],
            ['2026-11-01，native C040，ISO200', '40', '0.67 / 1.95'],
            ['2026-11-02，native C040，ISO200', '3', '0.72 / 2.16'],
            ['本轮午间，ISO200', '44', pair(lunch['overall_D50'])]]),
        '本轮中位比这三组高约 0.04 至 0.09，p95 相当或更低，未见真实场景整体明显变差。'
        '屏幕 / 色卡的数字更低，例如旧记录 Kodachrome 25 为 0.306/1.227、0.363/0.906；它们不是同一配方记录、光谱和场景组成，不能当作每张实景都应达到的指标。', '',
        table(('午间输入色域', '留出块', '中位 / p95 ΔE00'),
              [[REGIONS[key], f"{lunch['regions'][key]['de00']['n']:,}", pair(lunch['regions'][key]['de00'])]
               for key in ('neutral','red','yellow','green','cyan','blue','magenta','dark','bright')]),
        f"中性色占午间留出块 {100*lunch['regions']['neutral']['de00']['n']/lunch['overall_D50']['n']:.1f}%。"
        '蓝色域和暗部的尾部误差较大；品红只有 7 个块，不能外推为品红表现已验证。色域来自固定 Lab 范围，不是物体语义识别。', '',
        '历史响应源见 [model_c040_r1 报告](../model_c040_r1/REPORT.md) 及其 local/regression-history-all.json。'
        '这里没有拿配方对 LUT 的误差，冒充模型对相机的误差。', '',
        '## 相似度', '',
        '按指定的投票口径计算：100 × [1 − median ΔE00(实拍 JPEG, 目标) / median ΔE00(预测 04, 目标)]，D65。'
        '04 是同一张 RAW 的反事实预测，现场没有逐张同曝光 04 对照。百分比表示相对 04 的误差改善，不是人眼相似度或正确率；负值表示比 04 离目标更远。'
        '04 自身分母为零，不填成 100%。', '',
        'g157 原目标保持其既有输入解释。film_r2 列使用场景光目标；数字风格沿用原目标，Acros 另对官方目标评分。'
        'Kodachrome 25、Velvia 50、instax 的变化主要是从 04 后处理改为场景光；Portra 400、Vision3 500T 的 film_r2 来源还换为 spektrafilm，不能把跨列差值当作相机退化。', '',
        style_table(lunch['recipes']),
        '早上另外观测到的风格，以及手动白平衡的 HNCS LowSat 如下。', '', style_table(morning['recipes']),
        f"Kodachrome 25 共 24 张，原目标合并相似度为 {f(k['style']['old']['actual_similarity'],1)}%，"
        f"场景光目标为 {f(k['style']['r2']['actual_similarity'],1)}%；13 张通过样本对应 {f(kc['style']['old']['actual_similarity'],1)}% 与 {f(kc['style']['r2']['actual_similarity'],1)}%。"
        f"逐照片场景光相似度的中位为 {f(statistics.median(kphotos),1)}%，范围 {f(min(kphotos),1)}% 至 {f(max(kphotos),1)}%，说明场景依赖很强。", '',
        f"按场景光目标，Kodachrome 25 的实拍到目标中位 / p95 为 {pair(k['style']['r2']['actual_target'])}；"
        f"04 到同目标的中位为 {f(k['style']['r2']['baseline_target']['median'])}。"
        f"模型预估的相似度也只有 {f(k['style']['r2']['model_similarity'],1)}%，所以这不是实拍突然偏离模型。", '',
        table(('Kodachrome 25 的场景区域', '实拍到目标中位 ΔE00', '04 到目标中位 ΔE00', '改善 %', '实拍较目标的 L* 差'),
              [[REGIONS[key], f(k['style_regions']['r2'][key]['actual']['median']),
                f(k['style_regions']['r2'][key]['baseline']['median']),
                f(k['style_regions']['r2'][key]['actual_similarity'],1),
                f(k['style_regions']['r2'][key]['actual_minus_target_Lab_median'][0])]
               for key in ('neutral','dark','middle','bright','red','yellow','green','cyan','blue')]),
        '主要差别在明暗关系。Kodachrome 25 的中间调比场景光目标亮约 9.6 L*，中性色亮约 8.7 L*；'
        '暗部仍比 04 更接近目标，而黄色和青色在这批照片中反而更远。不能靠再修一点 C040 蓝色节点解决这组目标差距。', '',
        '广告牌横向比较仅用 RAW 结构独立筛出的连续 17 张。相对组内中间帧的亮度结构相关系数为 0.940 至 1.000；'
        '每张仍使用自己的 RAW、AWB 和曝光生成目标，不把手持实拍当固定 WB、固定构图的色卡实验。', '',
        table(('照片', '第一名', '判定', '预测误差中位 / p95', 'g157 原目标 %', 'film_r2 目标 %'),
              [[r['id'], name(r['best']), status(r), pair(r['prediction_D50']),
                f(next(q for q in board['recipes'] if q['name']==r['best'])['style']['old']['actual_similarity'],1),
                f(next(q for q in board['recipes'] if q['name']==r['best'])['style']['r2']['actual_similarity'],1)] for r in boardrows]),
        f"广告牌中的 Kodachrome 25 为 {f(kb['style']['old']['actual_similarity'],1)}% / {f(kb['style']['r2']['actual_similarity'],1)}%。"
        '跨目标各有不同的 04 分母，不能凭这张表的百分比给不同风格排总榜。'
        'film_looks_r2 报告中的 Kodachrome 25 Look 64.33%、满配 76.81%，来自重新拟合记录及旧留出，不是当前这条 g157 记录在新场景中的承诺。', '',
        '本轮只评价既定目标的颜色与明暗，不评价胶片颗粒、光晕或真实宽容度。'
        '没有第一名响应的 g157 项不报实拍相似度，包括 07、08、Tri-X 400、Metropolis、ARRI 709、Eterna BB、RED IPP2 及三个用户项的独立身份；'
        '默认用户项与 05 的等价关系已单列。', '',
        '## 异常', '',
        f"55 张中没有留出中位 >5 或 p95 >10 的整张明显偏离；这不是相机所有功能的验收。"
        '需要保留的局部异常为 R8052093 的 06 F-CN。它的整体中位 / p95 为 1.21/2.89，蓝色域 194 块为 2.99/4.44；'
        '实际蓝色域的 Lab a* 较预测低 2.28、b* 低 0.94。它更符合现有模型在蓝色域的局部残差，照片本身不能唯一归因到相机。', '',
        '对首张 04、06 及较大残差的 Kodachrome 25 共 7 张做了独立诊断。'
        '把 RAW 横向位移改为 −2 或 0，不能明显消掉 06 的误差；把曲线、矩阵或扇区分别换成 04，也没有得到更接近该张 JPEG 的“少写一部分”解释。'
        '所有诊断只作对照，没有据此重选位移、曝光、白平衡或主评分。', '',
        f"早上 11 张均能识别，合并误差 {pair(morning['overall_D50'])}，未见与 P/A/S 切换同时出现的整套颜色失配。"
        '不同模式下用的配方不同，不能据此比较模式优劣。03 HC BW 与 Acros 对相机的误差都约 0.10；'
        '03 HC BW 对既定目标的相似度仍只有 30.9%，这是风格目标差距。', '',
        '机主报告全程没有 ERR、Unsaved 或列表消失。照片支持颜色输出连贯，但没有记录菜单或 BOOT 内部状态，不能代替这些状态的实机日志。', '',
        '## 对配方或模型的改进建议', '',
        '1. 先统一 Kodachrome 25 的产品目标。若要维持现有明亮的 g157 观感，就按原目标管理；若要接近 film_r2 的场景光目标，优先重做中间调响应并核对黄、青色。不要把两种目标的成绩混成一个百分比。',
        '2. 以场景光目标做新的满配候选，再用新场景验证。现有 24 张保留为评估集，不一边改参数一边把它们当新留出；优先改善中间调，保留这次已经接近目标的暗部。旧满配模型分数不能代替新候选实拍。',
        '3. 模型优先补 06 的蓝色域与偏色中性色。后续最小补拍可在同一稳定光源、ISO200、固定 WB 下做 04→06→04，并纳入同一蓝色和灰阶对象，区分输入映射、空间处理与配方响应；本轮不改相机或 DAT。',
        '4. 下一次切换配方时留一份本地顺序记录。05 和默认 FCC-001 需要菜单记录才能区分；Kodachrome/HNCS LowSat、千禧 A/B 等近似风格保留分差，补拍时增加能拉开它们的颜色，避免按记忆硬认。', '',
        '## 方法、证据与复跑', '',
        f"输入为 57 对 JPG+DNG，其中午间 44 对、早上 11 对、昨天 2 对仅核验完整性。DAT SHA-256 为 `{C.DAT_SHA}`。"
        '使用实际 MOUNT 记录、原生 C040 加既有实测偏移，以及 model_c040_r1 重建的 RAW→04 输入映射，没有用 legacy50。'
        '55 张均为 ISO200；午间全部 M/Auto WB，早上 Manual WB，含 M/P/A/S。没有逐照片拟合曝光或白平衡，也没有给未知 WB 补偿填 0。', '',
        '从每张原分辨率照片固定采 96×72 个位置，每块 12×12 像素，RAW 与 JPEG 固定横移 −1 像素。'
        '沿用平滑块条件，排除 RAW ≥0.98、RAW ≤0.002、JPEG 极端码值和 L* 在 10 至 95 之外的区域；'
        '识别只用 4×4 空间分区的偶数半区，误差和风格评分只用奇数半区。各候选用完全相同的掩码。'
        '旧掩码的逐配方对照保存在 summary.json，未按误差删点。', '',
        '每张均保存 29 个候选的本地预测 JPEG，共 1,595 张。定量比较采用解码后实际 JPEG 的平滑块均值和未二次压缩的模型 RGB；'
        '256 像素 JPEG 只是本地颜色预览，不模拟 demosaic、锐化、降噪或 JPEG 空间 ISP，也不参与定量评分。'
        '主结果按有效块合并；逐照片统计另存，空间抽样胜率不当作跨场景的统计置信度。', '',
        f"最终复核重读 114 个原始照片文件，SHA-256、大小和修改时间均未变，DAT 未变；{verification['model_input_files_unchanged']} 个模型输入文件未漂移。"
        f"独立曲线 / 矩阵 / C080 字面方程重放全部 55 张，最大 RGB 差 {verification['max_literal_RGB_difference']:.3g} code；"
        '还用既有冻结缓存重放两种胶片目标及黑白目标，确认目标解释一致。', '',
        '核验首错保留在 local/queues/verify-*/verify-0.log。首次目标缓存复核把“冻结旧目标”的旧 04 输入误换成 base_new，出现 30.38 code 差；'
        '按原缓存契约改回 base 后通过，本批照片的目标评分没有因这次核验修正而改变。'
        '新增色域汇总时一次局部变量覆盖了配方名，已修正并重算汇总；旧汇总与日志留在 local/history/ 和 queues/。', '',
        '计算均为隔离 Python `-I -B`、nice 15、数学库单线程。队列用 `tools/loadgate.py` 的 `cap(len(running))`，独立作业用 `workers()`；'
        '没有另设 load1 门槛。没有访问网络、相机或 SD 卡，没有安装依赖、commit 或 push。照片及派生图均在被忽略的 local/。', '',
        '主要证据：', '',
        '- [完整本地逐张复核页](local/index.html) 包含实际、预测、两种目标与第二名预览。',
        '- [数值汇总](local/summary.json) 包含全排序、区域、逐照片和两种目标的成绩。',
        '- [同景筛选](local/scene-matching.json) 只用 RAW 结构，与配方顺序独立。',
        '- [异常诊断](local/diagnosis.json) 保留固定配准及不完整配方假设。',
        '- [最终复核](local/verification.json) 和 [原件复核清单](local/originals-after.json) 记录只读完整性。',
        '- [决策记录](local/decisions.tsv) 与 [公开文件哈希](SHA256SUMS) 支持复查。', '',
        '在仓库根目录复跑。默认跳过已有产物；需要重算时用独立输出副本，或以 `--refresh` 归档旧回执后重算。', '',
        '```sh',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py inventory',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py analyze',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py targets',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py summary',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py diagnose',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py render',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py verify',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/queue.py report',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/seal.py',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/seal.py --verify-only',
        '```', '']
    report = '\n'.join(body)
    assert 'GPS' not in report
    assert 'data:image' not in report and '<img' not in report and '![' not in report
    (C.HERE / 'REPORT.md').write_text(report)
    local_page(summary)
    C.decision('report', '按机主关心的识别、准确度、目标风格写报告',
               '把模型误差与风格目标差距分开，并保留暂定身份', 'REPORT.md; local/index.html', first)
    files = sorted(C.HERE.glob('*.py')) + [C.HERE / 'REPORT.md']
    (C.HERE / 'SHA256SUMS').write_text(''.join(C.sha(p) + '  ' + p.name + '\n' for p in files))
    C.dump('report-receipt.json', dict(first_line=first, report_sha256=C.sha(C.HERE / 'REPORT.md'),
        public_contains_no_image_payload=True, private_review_page=str(C.LOCAL / 'index.html'), created_utc=C.utc()))
    print(first, flush=True)
    print('REPORT', C.HERE / 'REPORT.md', flush=True)


if __name__ == '__main__':
    main()
