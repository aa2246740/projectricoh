"""Chinese product report for fixed g159-candidate evaluations; no fitting or tuning."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r2_common import C,R1,PLANNED,decision
import html
import statistics

REGIONS={'neutral':'中性色','dark':'暗部','middle':'中间调','bright':'亮部','red':'红色','yellow':'黄色',
         'green':'绿色','cyan':'青色','blue':'蓝色','magenta':'品红色'}


def f(x,n=2):return '未定义' if x is None else f'{x:.{n}f}'
def signed(x,n=2):return f'{x:+.{n}f}'
def pair(d):return f(d['median'])+' / '+f(d['p95'])
def table(header,rows):
    return '\n'.join(['| '+' | '.join(header)+' |','| '+' | '.join('---' for _ in header)+' |',
                      *['| '+' | '.join(str(x) for x in row)+' |' for row in rows]])+'\n'


def chart(summary):
    rows=[]
    # Fixed common scale: -50 to +5 pp. It is not adjusted to hide either red flag.
    for r in summary['planned_table']:
        value=r['change_pp'];left=min(50,abs(min(value,0)))/55*100
        positive=max(value,0)/55*100
        bar=(f'<i class="neg" style="left:{(50/55*100-left):.3f}%;width:{left:.3f}%"></i>' if value<0 else
             f'<i class="pos" style="left:{50/55*100:.3f}%;width:{positive:.3f}%"></i>')
        rows.append(f'<div class="row"><span>{html.escape(r["name"])}</span><div class="track">{bar}<b class="zero"></b></div><em>{signed(value,1)}</em></div>')
    doc='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{margin:0;font-family:var(--font-sans);color:var(--foreground)}p{margin:8px 0 16px;line-height:1.5}.row{display:grid;grid-template-columns:130px minmax(100px,1fr) 52px;align-items:center;gap:8px;margin:10px 0;font-size:13px}.track{position:relative;height:16px;background:var(--secondary);border-radius:3px}.track i{position:absolute;top:0;height:16px;min-width:2px;border-radius:2px}.neg{background:var(--chart-1)}.pos{background:var(--chart-2)}.row:nth-child(10) .neg,.row:nth-child(11) .neg{background:var(--destructive)}.zero{position:absolute;left:90.909%;height:16px;border-left:1px solid var(--foreground)}em{font-style:normal;text-align:right;font-variant-numeric:tabular-nums}.note{font-size:12px;color:var(--muted-foreground)}.axis{display:flex;justify-content:space-between;font-size:11px;color:var(--muted-foreground);margin-left:138px;margin-right:60px}@media(max-width:420px){.row{grid-template-columns:115px minmax(80px,1fr) 48px}.axis{margin-left:123px}}</style></head><body><main><p>13 条计划记录相对旧留出的变化 · pp</p>'''+''.join(rows)+'''
<div class="axis"><span>−50</span><span>−40</span><span>−30</span><span>−20</span><span>−10</span><span>0 / +5</span></div><p class="note">新旧均用同一场景光目标。M9、HNCS HiCon、HNCS LowSat 的源目标含 04 后处理，旧留出已按本轮直接场景输入重算；原表分数另列在报告中。</p></main></body></html>'''
    (C.LOCAL/'chart.html').write_text(doc)


def previews(summary,styles):
    C.numerical()
    np=C.np
    style=next(r for r in styles if r['name']=='Kodachrome25')
    frames={r['id']:r for r in C.read(R1/'inventory.json')}
    root=C.LOCAL/'previews';root.mkdir(exist_ok=True)
    rows=[]
    for pid in ('R8052067','R8052081','R8052103'):
        src=R1/'frames'/pid
        with np.load(src/'preview-input.npz',allow_pickle=False) as z:raw=z['raw_codes']
        model=C.camera_model(200,frames[pid]['metadata']['color_raw13'])
        x=C.input_codes(raw.reshape(-1,3))
        for mode in ('Look','full'):
            b=Path(style['variants'][mode]['file']).read_bytes()
            C.save_jpeg(root/(pid+'-'+mode+'.jpg'),C.predict(model,b,x).reshape(raw.shape))
        for tag,filename in (('actual','actual.jpg'),('target','target-scene.jpg')):
            (root/(pid+'-'+tag+'.jpg')).write_bytes((src/filename).read_bytes())
        figures=''.join(f'<figure><img src="{pid}-{mode}.jpg" alt="{label}"><figcaption>{label}</figcaption></figure>'
                        for mode,label in (('actual','g157 实拍'),('full','新满配预测'),('Look','新 Look 预测'),('target','场景光目标')))
        rows.append(f'<section><h2>{pid}</h2><div>{figures}</div></section>')
    (root/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\';img-src \'self\';style-src \'unsafe-inline\'">'
        '<title>Kodachrome 25 本地预测对照</title><style>body{font:16px system-ui;margin:28px;background:#f6f5f0;color:#252525}section{border-top:1px solid #ccc;padding:16px 0}section div{display:flex;gap:10px;flex-wrap:wrap}figure{margin:0}img{width:256px;height:auto}figcaption{padding:8px 0}</style>'
        '<h1>Kodachrome 25 本地预测对照</h1><p>新满配与新 Look 均为 RAW 的离线预测，未在相机中拍摄。256 像素颜色预览不模拟空间 ISP，不参与评分。</p>'
        +''.join(rows)+'</html>')


def main():
    C.admit('r2-report')
    s=C.read(C.LOCAL/'summary.json');v=C.read(C.LOCAL/'verification.json')
    assert v['status']=='PASS'
    b=C.read(C.LOCAL/'blue.json');coverage=C.read(C.LOCAL/'coverage.json');assert 'history' in coverage
    for path,digest in coverage['protected_sources'].items():assert C.sha(path)==digest
    styles=C.read(C.LOCAL/'styles.json');photos=C.read(C.LOCAL/'photos.json')
    results=s['all_results'];k=results['Kodachrome25']
    failed=next(r for r in b['poster'] if r['id']=='R8052093')
    avail=v['library_availability']
    hist=coverage['history']
    hist_exact=[r for r in hist if r['exact_box']]
    hist_near=[r for r in hist if r['nearby_box']]
    first=f"g159 候选实拍评估：{s['planned_count']} 条，平均相对旧留出 {signed(s['mean_change_pp'],1)} pp"
    ordered=[r['name'] for r in s['planned_table']]
    mainrows=[]
    for r in s['planned_table']:
        label=('满配 '+r['slot']) if r['placement']=='full' else 'Look'
        flag='下降超过10pp' if r['drop_over_10'] else '未超过10pp'
        if r['target_convention_changed']:flag+='；源目标含04'
        mainrows.append([r['name'],label,f(r['original_holdout']),f(r['comparable_scene_holdout']),
                         f(r['real55']),signed(r['change_pp']),flag])
    regionrows=[]
    for key in ('neutral','dark','middle','bright','red','yellow','green','cyan','blue'):
        old=k['old_g157_k25_actual_regions'][key];new=k['results']['full']['k25_regions'][key]
        regionrows.append([REGIONS[key],str(old['de00']['n']),pair(old['de00']),pair(new['de00']),
            signed(old['actual_minus_target_Lab_median'][0]),signed(new['actual_minus_target_Lab_median'][0]),
            f(old['similarity_percent'],1),f(new['similarity_percent'],1)])
    safe_rows=[]
    for name in ordered:
        r=results[name];gap=r['full_minus_Look_pp']
        safe_rows.append([name,f(r['results']['Look']['scores']['all55']['similarity_percent']),
            f(r['results']['full']['scores']['all55']['similarity_percent']),signed(gap['all55']),
            signed(gap['strict96']),signed(gap['r1held']), '满足' if gap['all55']<=2 else '不满足'])
    extended=[]
    for style in styles:
        if style['planned']:continue
        r=results[style['name']];q=r['results']['full'];gap=r['full_minus_Look_pp']['all55']
        extended.append([style['name'],f(q['same_scene_holdout']['similarity_percent']),f(q['scores']['all55']['similarity_percent']),
                         signed(q['change_pp']),signed(gap),'满足' if gap<=2 else '不满足'])
    noon06=[r for r in coverage['noon'] if r['setting']=='06 F-CN']
    body=[first,'',
        '本轮只评价既有记录。13 条指你明确列出的 4 条满配与 9 条 Look，另评估 14 种扩展胶片作为位置对照，不计入首行平均。'
        '每种均比较冻结的满配 / Look 两条记录，共 54 条 MOUNT 记录；所有记录都在今天 55 张 DNG 上前向预测，没有拟合、调参或用这些照片挑路线。'
        '本报告的“实拍评估”是实景 RAW 上的离线预测，尚无 g159 候选的相机 JPEG。','',
        '## 候选记录与旧留出对照','',
        table(('候选','计划位置','film_looks_r2 原表 %','同场景目标旧留出 %','本批55张 %','变化 pp','标记'),mainrows),
        '变化为“本批减同目标旧留出”，每条计划记录等权，首行平均不是按样本数加权。'
        '相似度均为 100×[1−median ΔE00(记录预测,目标)/median ΔE00(04预测,目标)]，D65。'
        '不同风格各有自己的 04 分母，百分比不是跨风格的绝对质量排名。','',
        '这里有一项必须分清的目标定义冲突。`film_looks_r2` 的 M9 STD、HNCS HiCon、HNCS LowSat 仍声明 `after04`，旧表分数包含 04 后处理。'
        '按你本轮明确的场景光决定，三项改用“场景 XYZ 编码为源 LUT 声明的 sRGB，再直接进入同一 LUT”，旧留出和新照片用完全相同的函数；记录字节未变。'
        '这是统一场景输入的定义，不是新取得的 Leica/Hasselblad 场景相机标定。原表分数单列，不能直接与换口径后的新值相减。','',
        f"13 条按统一场景输入的可比平均为 {signed(s['mean_change_pp'],2)} pp。"
        f"只看原本就使用场景光目标的 10 条，平均为 {signed(s['mean_unchanged_target_change_pp'],2)} pp。"
        f"若完全保持源文件原来的目标口径，全部 13 条平均为 {signed(s['mean_original_convention_change_pp'],2)} pp。"
        '因此，HNCS 两项的红旗同时暴露数字目标的定义问题，不能说是整套新配方在真实场景普遍崩坏。','',
        'HNCS HiCon 与 HNCS LowSat 在统一场景目标下分别下降 45.24 和 17.67 pp，超过约 10 pp。'
        'M9 下降 3.18 pp；其余原生场景目标的计划记录均未下降超过 10 pp。instax mini 的下降 6.33 pp 值得保留，尚未跨这条线。','',
        table(('候选','午间44张 %','早上11张 %','严格曝光筛选 %','R1固定平滑块 %'),
            [[r['name'],f(r['lunch44']),f(r['morning11']),f(r['strict96']),f(r['r1held'])] for r in s['planned_table']]),
        f"主表复用旧留出每张最多 96 个 RAW 点的取样方法，55 张合计 5,280 点；"
        f"另一个固定的曝光筛选保留 {sum(r['strict96'] for r in photos):,} 点，R1 的固定奇数空间半区保留 {sum(r['r1held'] for r in photos):,} 个平滑块。"
        '严格曝光筛选和 R1 平滑块不会改变 HNCS 两条红旗或 Kodachrome 25 的主要结论，三种方法没有用于选记录或调参数。','',
        '## Kodachrome 25：主要差距已在预测中修复，尚有约1.8 L*偏暗','',
        f"满配预测在 55 张 RAW 上的相似度为 {f(k['results']['full']['scores']['all55']['similarity_percent'])}%，"
        f"旧留出为 {f(k['results']['full']['same_scene_holdout']['similarity_percent'])}%，下降 {f(-k['results']['full']['change_pp'])} pp。"
        f"同一组 RAW 的 Look 为 {f(k['results']['Look']['scores']['all55']['similarity_percent'])}%，比满配损失 {f(k['full_minus_Look_pp']['all55'])} pp。"
        '这支持把它保留在满配槽。','',
        '下面严格复用 R1 暂定为 Kodachrome 25 的 24 张照片、同一批平滑块和同一目标。左侧是 g157 实际 JPEG，右侧是新满配的电脑预测。'
        'L* 差为“输出减目标”，正数偏亮，负数偏暗；没有用新拟合去逼近这些数值。','',
        table(('区域','块数','g157实拍 ΔE 中位/p95','新满配预测 ΔE 中位/p95','原 L*差','新 L*差','原改善 %','新改善 %'),regionrows),
        '中间调由约 +9.6 降到 −1.8 L*，中性色由约 +8.7 降到 −1.7 L*。主要偏亮已消除，剩余是约 1.7 至 1.8 L* 的偏暗，不能写成完全吻合。'
        f"黄色从比 04 更差的 −45.5% 转为改善 {f(k['results']['full']['k25_regions']['yellow']['similarity_percent'],1)}%，"
        f"青色从 −19.7% 转为改善 {f(k['results']['full']['k25_regions']['cyan']['similarity_percent'],1)}%；这两项回退也在预测中修复。"
        '品红仅 6 块，未据此作广泛色彩结论。','',
        f"只取 R1 中 13 张高置信 Kodachrome 25 照片，新满配在固定平滑块上为 {f(k['results']['full']['scores']['k25_13']['similarity_percent'])}%；"
        f"24 张全组为 {f(k['results']['full']['scores']['k25_24']['similarity_percent'])}%。"
        '这些是相同评估输入上的结果，不是训练后重新命名的留出。'
        '少量本地颜色预览见 [Kodachrome 25 对照页](local/r2/previews/index.html)。','',
        '## 06 蓝色残差：原生C040修正已经生效，尚不能唯一归因C040或C080','',
        '本节模型对相机JPEG的残差沿用R1的D50口径，前表记录对风格目标的相似度采用D65，两种分数没有混算。','',
        'R8052093 蓝色域仍为中位 / p95 ΔE00 2.99 / 4.44。当前模型的 24 个 C040 节点与 model_c040_r1 的 MOUNT 原生节点逐值相同；'
        '再次套用同一个节点修正不会改变输出。剩余角向核、k 耦合与 gain 仍来自 50mm 标定，是明确需要验证的 MOUNT 响应环节。'
        'C080 记录字节没有被证明错误，未闭合的是 C040、曲线、C100、C080 和输入映射的组合响应。','',
        f"这张蓝色域进入查表前的色度中位只有 {f(failed['input_chroma_quantiles'][1])} code，色相中位为 {f(failed['input_hue_quantiles'][1],1)}°。"
        '照片内容中的“蓝色”并不等于 C040 的某个蓝色节点；06 的曲线与矩阵已经改变了查表入口。低色度处的输入误差、角向模糊和量化会相互影响。','',
        table(('固定诊断假设','整张中位 / p95 ΔE00','蓝色域中位 / p95 ΔE00'),
            [['完整06','1.21 / 2.89',pair(failed['blue_de00'])],
             *[[f"仅把 {field} 换成04",pair(r['all']),pair(r['blue'])] for field,r in failed['fixed_04_component_controls'].items()]]),
        '替换 C080 反而让蓝色域更差；替换矩阵虽局部改善，整张变差。它们都不是修复候选，也不能证明哪一部分未写入相机。'
        '现有证据倾向于局部的单元响应 / 输入路由耦合，不足以唯一认定 C040 经验节点、C080 核或 RAW→04 输入映射中的哪一项。','',
        '先查现库，没有要求重拍：','',
        table(('现有证据','数量或结果'),[
            ['MOUNT RAW/JPEG 配对',str(b['census']['MOUNT_paired_DNGs'])],
            ['合并RAW和JPEG两侧标签后的蓝色线索',str(avail['labelled_blue_pairs'])+' 对'],
            ['其中自然场景标签',str(avail['content_labels'].get('natural',0))+' 对'],
            ['其中ISO200',str(avail['ISO200'])+' 对'],
            ['其中ISO200且手动/日光WB',str(avail['fixed_WB_ISO200'])+' 对'],
            ['配方身份仍unknown',str(avail['identity_unknown'])+' 对'],
            ['与今天55张的重叠',str(avail['overlap_with_today'])],
            ['本轮重放的旧ISO200、已认定04/05/06','10 张，零读取错误'],
            ['历史04蓝色域',pair(b['history']['04']['blue_de00'])],
            ['历史05蓝色域',pair(b['history']['05']['blue_de00'])],
            ['历史06蓝色域',pair(b['history']['06']['blue_de00'])],
            ['Probe2 / Probe3中央彩色响应','36 / 18 项，分别只有3个彩色对象']]),
        '索引标签是检索线索，不是配方或对象真值。unknown 项没有转成训练可用的 06；历史重放沿用之前冻结的响应身份，没有用今天的误差重新认定。'
        '历史照片与当前记录的曲线、矩阵、查表入口不同，不能用历史蓝色域约 0.58 的中位数承诺本张也能达到。','',
        '对失败区域的查表入口作了覆盖核对。其 5% 至 95% 矩形为色相 24.61° 至 52.47°、色度 3.55 至 4.15 code，矩形只用于统计数据覆盖，没有估计参数。'
        f"受控 noon 的 06 T/V/色卡在这个窄区域中分别为 {noon06[0]['exact_box']} / {noon06[1]['exact_box']} / {noon06[2]['exact_box']} 点；"
        '扩展到色相额外 ±15°、色度额外 ±2 code 后，分别只有 0 / 2 / 1 点。Probe2/3 的扩展区域仍均为 0 点。','',
        f"另把全部 {len(hist)} 张已有冻结身份的 MOUNT ISO200 历史曝光按各自实际记录重放查表入口："
        f"窄区域有 {len(hist_exact)} 张、{sum(r['exact_box'] for r in hist_exact)} 点，扩展区域有 {len(hist_near)} 张、{sum(r['nearby_box'] for r in hist_near)} 点。"
        f"窄区域且 C080 字节与当前06相同的曝光为 {sum(r['same_C080_as_current06'] for r in hist_exact)} 张。"
        '不能把不同配方下“都拍了蓝色”的照片当成同一种查表输入。','',
        'Probe2/3 的独立变化在 R/G/B 曲线，C080 和矩阵字节均保持不变。它们能约束组合响应，但不是独立的 C080 扇区扰动实验；'
        '此前 R+ 肤色 Cb、B+ 蓝色 Cr 的弱响应缺口也尚未闭合。','',
        '若继续 model_c040_r1 这条研究路线，应先利用已有的原厂04标定、noon T页、实体色卡与上述有身份的历史RAW，按实际查表入口而非“蓝色物体”标签整理样本。'
        '先核对 RAW→04，再研究受约束的 MOUNT 低色度角向核 / 增益残差，保留 V 页和整场景作独立验证。'
        '要把 C040 经验残差与 C080 响应单独拆开，仍需要足够的独立色相、色度和变换方向；当前受控数据在失败入口附近稀少。'
        '现库能启动这项研究，现阶段不能承诺一个唯一修复项。本轮没有拟合任何新模型，也没有索取补拍。今天55张始终只作评估。','',
        '## Look位置安全性','',
        '本节只判断 MOUNT 的“满配分数减 Look 分数 ≤约2 pp”。两边使用各自已有、按旧训练选择的记录；负损失表示当前冻结的 Look 在这批输入上反而更接近目标，'
        '不代表 Look 的表达能力高于满配。没有利用今天照片在两条记录之间重新选路线。','',
        table(('风格','Look %','满配 %','主取样损失 pp','严格曝光损失 pp','R1平滑块损失 pp','≤2pp'),safe_rows),
        '明确计划的 9 条 Look 均满足整体约 2 pp 的位置预算，且严格曝光筛选与 R1 固定平滑块复核也满足。'
        '其中 HNCS HiCon、HNCS LowSat 只是“放 Look 没多损失”，满配也没有解决它们在纯场景目标下的贴近度问题；M9 也有目标输入定义冲突。'
        '位置安全和目标是否合适分别判断。','',
        '13条计划中，Gold 200 也满足位置预算，但仍按你的产品决定保留满配槽。Eterna BB、Leica Classic、Kodachrome 25 的位置损失分别约 4.50、4.64、10.30 pp，支持保留满配。'
        '在本批整体数据上满足位置预算的全部风格为：'+'、'.join(s['primary_Look_safe'])+'。','',
        '扩展胶片只作对照，不擅自加入 g159 清单。下面“变化”针对满配，“位置损失”仍为满配减 Look。','',
        table(('扩展胶片','旧留出满配 %','本批满配 %','变化 pp','位置损失 pp','≤2pp'),extended),
        '这些结论只覆盖 MOUNT、本批场景与名义整数输出；不代表每张照片都损失 ≤2 pp，不扩展为其他单元、完整128量化分支、装包依赖或相机验收。','',
        '## 输入、复核与复跑','',
        '满配胶片来自 `film_looks_r2/local/full_library_manifest.json`；官方 Acros 来自 `acros_official_handoff.json`。'
        'Eterna BB、Leica Classic 的两个位置和数字风格对照来自该研究的 `style_analysis/*/mount-a12.json`。'
        '六个锁定 Look 使用 `locked_shared_flags7_handoff.json` 的共享RGB曲线记录，保持其默认响应等价；没有从 g157 取候选字节。'
        'g157 的原厂04仅作固定模型锚点，g157的实际JPEG仅用于上一轮残差和Kodachrome区域对照。','',
        '保留每条记录的原路径、SHA、旧分数、固定目标与选定路线，未改变配方字节、曲线、矩阵、扇区、目标曝光或WB。'
        '主模型仍为原生 MOUNT C040，加 model_c040_r1 的输入映射；55张全部ISO200，均用各自DNG的WB和场景矩阵。'
        '没有 legacy50，没有逐照片曝光或WB拟合。','',
        '主取样逐式复用 `recipe_redo_r1/prepare_inputs.py::sample`：32点宽、2×2 CFA、排除RAW裁切、每张最多96点。'
        '旧留出也按原来的整数输出 `np.rint` 评分，04分母保持连续预测。额外严格筛选排除 RAW≤0.002 和场景 L* 不在10至95的点；'
        'R1固定平滑块还排除原JPEG极端值、过暗过亮和纹理变化。所有掩码在候选误差计算前确定，没有按误差删点。','',
        f"独立复核重读114个照片原件，SHA、大小、修改时间均未变；DAT未变。54条记录共重放 {v['literal_points']:,} 个输入点，"
        f"独立字面方程最大RGB差为 {v['literal_max_RGB']:.3g} code。"
        '每条记录的原目标旧留出分数均重算吻合，另用独立场景输入路径核对三个改口径的数字目标。'
        '今天的55张与之前的输入照片没有哈希重叠。','',
        '库检索的首次查询只在DNG上找标签，漏掉了挂在JPEG上的标签；已改为按配对合并两侧，旧结果留在 local/r2/history/。'
        '源照片、索引和记录均只读，索引查询使用本地只读快照。其它首轮I/O、负载延后与回执原样保留。','',
        '运行均为隔离Python `-I -B`、nice 15、数学库单线程。队列调用 `loadgate.cap(len(running))`，独立作业调用 `loadgate.workers()`，返回0时延后。'
        '没有另设load1门槛，没有网络、相机、SD卡、安装依赖、commit或push。图片内容和派生数组仅在 local/r2/。','',
        '可复查文件：','',
        '- [主汇总](local/r2/summary.json) 与 [54条记录及来源](local/r2/styles.json)。',
        '- [蓝色诊断和现库盘点](local/r2/blue.json)、[入口覆盖](local/r2/coverage.json)、[库可用性](local/r2/library-availability.json)。',
        '- [独立复核](local/r2/verification.json)、[原件复核](local/r2/originals-after.json) 与 [决策记录](local/r2/decisions.tsv)。',
        '- [本地Kodachrome预览](local/r2/previews/index.html) 与 [汇总图数据页](local/r2/chart.html)。',
        '- [本轮公开文件哈希](SHA256SUMS_R2)。R1报告和原封存清单保持原样。','',
        '复跑入口如下。默认跳过已有产物；完整重算应先归档本轮输出，保留旧回执，不覆盖源记录和照片。','',
        '```sh',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_run.py prepare',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_run.py evaluate',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_run.py blue',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_summarize.py',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_coverage.py',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_run.py verify',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_run.py report',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_seal.py',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/r2_seal.py --verify-only',
        '```','']
    text='\n'.join(body)
    assert all(x not in text for x in ('data:image','<img','![','GPSLatitude','GPSLongitude'))
    (C.HERE/'REPORT_R2.md').write_text(text)
    chart(s);previews(s,styles)
    decision('report','把原目标、统一场景目标和Look位置损失分别呈现','避免目标变更伪装成实景模型退化，也避免把离线预测写成实机通过',
             'REPORT_R2.md; local/r2/summary.json',first)
    public=sorted(C.HERE.glob('r2_*.py'))+[C.HERE/'REPORT_R2.md']
    (C.HERE/'SHA256SUMS_R2').write_text(''.join(C.sha(p)+'  '+p.name+'\n' for p in public))
    C.dump('report.json',dict(first_line=first,report_sha256=C.sha(C.HERE/'REPORT_R2.md'),
        public_files=len(public),source_boundaries_explicit=True,no_photo_content_in_public_report=True,created_utc=C.utc()))
    print(first,flush=True);print('REPORT',C.HERE/'REPORT_R2.md',flush=True)


if __name__=='__main__':main()
