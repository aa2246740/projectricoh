"""Chinese public-data report and local-only volunteer-derived ceiling appendix."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
import datetime


def pair(stats): return f"{stats['median']:.3f} / {stats['p90']:.3f}"
def interval(x,scale=1):return ' / '.join(f'{v*scale:.2f}' for v in x)


def main():
    sim=c.read(c.LOCAL/'bridge_simulation.json');fit=c.read(c.LOCAL/'sensitivity_fit.json')
    ex=c.read(c.LOCAL/'extraction.json');gr=c.read(c.LOCAL/'extraction_griv.json')
    hx=c.read(c.LOCAL/'chart_holdout_gxr.json');hr=c.read(c.LOCAL/'chart_holdout_griv.json')
    sources=c.read(c.LOCAL/'sources.json');p=c.read(c.LOCAL/'ceiling_propagation.json')
    native=c.read(c.LOCAL/'gxr_existing_validation.json')
    by={(r['dataset'],r['method']):r for r in sim['results'] if r['illuminant']=='D65'}
    natural=by[('natural_heldout','ColorMatrix')];smooth=by[('natural_heldout','shared_smooth')]
    oracle=by[('natural_heldout','oracle_smooth')]
    table=[]
    for key,label in [('ColorMatrix','现有 ColorMatrix'),('shared_linear','情景集合拟合的共同线性映射'),
                      ('shared_smooth','情景集合拟合的共同平滑映射'),('oracle_linear','知道模拟真响应的逐模型线性映射'),
                      ('oracle_smooth','知道模拟真响应的逐模型平滑映射')]:
        table.append(f"| {label} | {pair(by[('Munsell_heldout',key)]['pooled'])} | {pair(by[('natural_heldout',key)]['pooled'])} |")
    light_table=[]
    for name in ('D50','D55','D65','D75'):
        rows=[v for v in sim['results'] if v['illuminant']==name and v['dataset']=='natural_heldout']
        light_table.append(f"| {name} | {pair(next(v['pooled'] for v in rows if v['method']=='ColorMatrix'))} | {pair(next(v['pooled'] for v in rows if v['method']=='shared_smooth'))} |")
    central=fit['configurations'][0]
    known_today=datetime.datetime.now(datetime.timezone.utc).isoformat()
    source_list=[]
    for label,title in [('cc-average30','BabelColor Avg30 光谱'),('cc-modern-dcamprof','DCamProf 新版色卡通用光谱'),
                        ('camspec-data','Jiang 等相机响应数据库'),('camspec-paper','Jiang 等原论文'),
                        ('natural-readme','UEF 自然光谱说明'),('munsell-matt-page','UEF Munsell 说明'),
                        ('matrix-sensitivity-paper','从 DNG 矩阵估计响应的研究'),('cie-cmfs-tables','CIE 1931 表格的 Colour 转录')]:
        r=next(v for v in sources if v['label']==label)
        source_list.append(f"- [{title}]({r['url']})；实际取得文件的日期与 SHA-256 见 `local/sources.json`。")
    text=f'''现有 ColorMatrix 桥接在本轮双机色卡约束的日光情景中，中位 / p90 误差为 {pair(natural['pooled'])} ΔE00；共同平滑映射约为 {pair(smooth['pooled'])}。这是条件模拟，尚不能当成 GXR 与 GR IV 的实测误差。当前数据仍不能量出 01/02 到 95% 的差距中有多少物理上不可避免，更不能证明 95% 已被同色异谱排除。

现在继续使用冻结的共同白点 ColorMatrix 桥接生成正式目标。新光谱桥接作为并列诊断候选。理由是 GXR 端颜色家族留出仍有 {pair(hx['pooled_camera_matrix_Lab_residual'])} ΔE00，GR IV 为 {pair(hr['pooled_camera_matrix_Lab_residual'])}，均达不到用小量残差区分 95% 的精度。GR IV 已使用本轮新增的实拍 RAW，最终结论不再依赖“GR IV 只有先验”。

本轮最有价值的下一份数据已改为：GXR A12 50mm 对一张真 ColorChecker Classic 拍的完整、无遮挡、均匀自然日光 RAW，ISO200，清楚记录色卡的新旧配方版本。让色卡占足够面积，避开玻璃、瓶身、直射反光与深阴影。这张照片主要补 GXR 端缺失的肤色、蓝绿和完整灰阶约束；DFOPTIX CC24 没有已知光谱，不能替代。此前最高优先的 GR IV studio RAW 已收到并纳入。

报告生成时间为 {known_today}。全部操作为主机研究，输出只在 `research/bridge_public_r1/` 与 `artifacts/downloads/bridge_public_r1/`。没有固件构建、卡写入、相机、USB、上传或 POST。既有研究、原始照片与固件均未修改；`decisions.tsv` 不读、不写、不纳入摘要。私有风格函数产生的逐点目标、评分及差距比例只存于被 Git 忽略的 [本地附录](local/CEILING_PRIVATE.md)，不在本报告重印。

已核实的数据与提取

| 输入 | 黑电平 / 白电平 | 有效色块 | 证据 |
|---|---|---:|---|
| GXR A12 50mm，2010 DPReview，ISO200 | 0 / 4095，12 位；按 DNG 标签扣黑 | Classic {ex['usable']['ColorChecker']} / 24，其中彩色 10；Q60 {ex['usable']['Q60']}；Q60 灰阶 {ex['usable']['Q60-gray']} | `local/patches.json`、`patches.csv`、`patch_map.png` |
| GR IV，当前 DPReview，ISO100，Daylight | 64 / 16318，14 位；原生无损 JPEG CFA | Classic {gr['usable']} / 24 | `local/patches_griv.json`、`patch_map_griv.png` |
| 两场景 Kodak Gray Scale | 各自 RAW 黑白电平 | GXR 17、GR IV 20 个候选灰级 | `local/kodak_gray.json`、两份灰阶取样图 |

GXR DNG 的 SHA-256 为 `f6d19a3219a674a5a7f9b30284285eb6e6d7dd8252309e9d481419e0468fe5c5`。新增 GR IV 文件为 `artifacts/downloads/dpreview-gr4-studio/gr4_studio_daylight_iso100.dng`，35,265,434 字节，SHA-256 为 `2e438c7e9945591ed2a897a6a4df40da23adf0cb45b89b1a7a1ab7f2d6a967c4`。它由协调者经浏览器下载；本 worker 没有重下载或改写。已将 DNG、预览和 `SOURCE.txt` 加入冻结输入。

所有响应都直接来自 RAW 的 R/G/B CFA 位置，没有先去马赛克。脚本处理 ActiveArea、DefaultCrop、CFA 相位、LinearizationTable、重复黑电平和白电平；取样框从预览坐标映射到原始像素。每块保留均值、中位数、10% 截尾均值、标准差、均值标准误、样本数、饱和比例、四象限差异与平面梯度。拟合使用截尾均值。饱和阈值为归一化 RAW 0.98；任何通道触及即排除。空间变化超过 12% 或信号过低也排除。

GXR 的 6 个肤色行色块被瓶子遮住，cyan 与 black 被纸遮住；orange 的窄条与 white 的局部区域因梯度过大排除。其余窄条显式标为 partial，采用更宽的测量噪声。Q60 主区 A-H/20-22 的人像不是均匀色块，24 格均排除；底部羽毛遮挡也有独立遮挡记录。取样图中的绿框为主要区域、黄框为局部可见或较弱区域、红叉或红框为排除。未见裁切不等于没有镜头面纱式杂散光。

没有平场照片，因此没有凭单张照片估出一张全画幅“真平场”。模型只允许色卡局部的共同乘性亮度斜率，先验标准差每轴 0.035 个自然对数单位，并加入弱的中性面纱项及小量残余黑电平。中心情景拟出的面纱反射率为 GXR {central['source']['neutral_veiling_reflectance']:.4f}、GR IV {central['target']['neutral_veiling_reflectance']:.4f}；这是吸收失配的干扰参数，不是测得的镜头散射率。色彩阴影、纸张老化、照明梯度与真实面纱仍可能混在一起。

中性块在各机 DNG 矩阵条件下给出 GXR 约 {ex['matrix_conditioned_white']['cct_K']:.0f} K、xy={np.round(ex['matrix_conditioned_white']['white_xy'],5).tolist()}；GR IV 约 {gr['matrix_conditioned_white']['cct_K']:.0f} K、xy={np.round(gr['matrix_conditioned_white']['white_xy'],5).tolist()}。这些白点都不是直接测量的光源 SPD。GXR 尤其偏离标准日光轨迹。不能因场景说明写着高 CRI 或 daylight，就把两次拍摄当成同一个 D65 光源。估计器采用日光基函数乘以一个平滑绿段扰动，并允许相对电子增益变化；这种分解也不唯一。温度参数允许 3500–9000 K，低于 4000 K 的公式外推只作平滑光源模型，不是标准 CIE 日光或灯具实测。

两条 Kodak 灰阶是第二种共同标准物的类型，但不是同一张实物，也没有这两张条带各自的逐块光谱。它们用于检查中性轴、深灰和杂散光。GXR 深灰处通道比漂移明显，GR IV 较稳定；低信号、灰阶材料、光场和面纱都可能造成这种现象。本轮没有从它们生成伪造的有色光谱约束。

公开参考的边界

2010 GXR 色卡确定早于 2014 年 11 月改版，主参考是 BabelColor 30 张旧版色卡的平均光谱。CGATS 的编号按列排序，脚本按 A1/A2 等名称重排成常用 24 块顺序，避免把光谱配错块。GR IV 当前场景的色卡生产日期未核实；场景始建于 2013 年和照片拍于新机发布之后，都不能单独确定色卡版本。默认使用 DCamProf `cc24_ref-new.cie` 通用新版光谱，同时把旧版 Avg30 纳入独立压力情景。DCamProf 文档确认新旧版本文件的对应关系；该文件不等于 DPReview 这张卡的逐张实测光谱，原始制备与测量来源未在本轮闭合。

X-Rite 公开的前后改版 Lab 参考已分别保存。通用参考的色差、批次差异、老化以及荧光，都不是两机传感器差异。标准物的已发表平均光谱让两机约束可以连接起来，但它不能替代“同一个物体的光谱已知”这一条件。

Kodak Q-60R2 2008:03 的精确参考未找到。公开 GitHub 镜像的 R2 数据止于 2005 年附近；X-Rite 提供的网页是 2003–2007 集；指定 Kodak 旧 FTP 路径的 Wayback 索引查询返回空列表。没有用其他批次冒充 2008:03，也没有把 Q60 RGB 反拟成光谱。Q60 的 RAW 和几何已交付，取得准确文件后可另作色度留出。

公共相机库来自 Jiang、Liu、Gu、Süsstrunk 的 28 台实测相机，400–720 nm、10 nm 一档。Munsell 文件实际解析出 1,269 条，网站旧文字的数量与文件不完全一致；自然物文件实际有 219 条、每条 61 档，说明文字写 218。代码按实际完整记录数检查，没有静默删掉最后一条。自然物涵盖花、叶等，包含重复材料与测量噪声，不是 219 个独立环境的随机样本。

CIE 1931 2°、A/D50/D55/D65/D75 与日光 S0/S1/S2 来自 Colour 项目的标准数据转录，下载内容仅以 AST 字面量解析，绝不执行下载代码。官方 CIE 三个 CSV 地址本轮返回 404，保留了失败响应。自然物只有 400–700 nm，主模拟对 700–720 nm 作常值延伸，并额外跑了截到 700 nm 的对照，矩阵桥接误差为 {pair(sim['natural_400_700_only_CM'])}，与主表接近。400 nm 以下、720 nm 以上和荧光均未得到约束；不能据此覆盖任意光谱。

{chr(10).join(source_list)}

器件判断与响应估计

GXR A12 50mm 的 12.3 MP APS-C CMOS 和几何尺寸由 [Ricoh 官方规格](https://www.ricoh-imaging.co.jp/english/products/gxr/specs.html)及公开 DNG 核对。Sony 12 MP / IMX038 世代是低置信候选，精确厂家、料号没有一手标记或厂商对应表。Nikon D90、D300s 只在一个情景中给予 20% 的弱先验，其余情景没有绑定它们；不能把同代或像素数相近写成同一块硅。

GR IV 的约 25.74 MP APS-C BSI 已由 [Ricoh 官方说明](https://www.ricoh-imaging.co.jp/english/products/gr-4/feature/)核实。IMX571 族或定制变体是低到中置信候选；[Sony IMX571BQR 资料](https://www.sony-semicon.com/files/62/pdf/p-13_IMX571BQR_Flyer.pdf)的有效像素 6252×4176 与 Ricoh 保存裁切 6192×4128 并不相同，不能据此确认具体料号。Ricoh 明确写到新的 UV/IR 保护滤镜增加长波端的 R 通量。这足以说明同硅的其他相机也只能作弱先验。本轮没有取得已确认同硅同滤镜的 GR IV 实测响应。

估计的是有效相机系统响应，包含镜头、滤色和保护滤镜，不是裸硅量子效率。每通道按 D65 积分归一化；绝对辐射效率不识别。28 相机曲线先作小量平滑，再分通道 PCA。中心模型每通道 4 个主成分，另试 2/6 个、不同矩阵软约束、先验宽度、色卡噪声、弱同代先验、新旧色卡、无面纱模型，共 10 种配置、80 对局部参数抽样。两台相机都使用实际色卡 RAW，A/D65 两个 DNG ColorMatrix 仅作软一致性约束。矩阵来自厂商拟合，其原始训练样本未知，不能把矩阵约束当光谱实测。

这些配置及局部高斯抽样的分位数是情景范围，不是校准过的 90% 置信区间。它没有给未建模的荧光、异常滤镜、光谱截断或真实色卡偏差提供覆盖保证。完整归一化曲线与 5/50/95 分位在 `local/sensitivities.npz`、`local/sensitivity_intervals.csv`；拟合条件在 `local/sensitivity_fit.json`。

颜色家族留出时，同一色族全部移出，保留中性块只定曝光和光源。最终以各机中性白点确定一个固定显示转换，将预测 RAW 和真实 RAW 同时转为 D65 Lab 后计 ΔE00。GXR 彩色留出 10 块为 {pair(hx['pooled_camera_matrix_Lab_residual'])}，GR IV 18 块为 {pair(hr['pooled_camera_matrix_Lab_residual'])}。这是单机 RAW 响应预测检查，不是两机桥接精度。把 GXR 端纳入替换精度门槛时，它没有通过。

另做了 28 次留一相机的矩阵先验检查，使用由该相机实测响应生成的理想矩阵，在自然物上的合并误差中位 / p90 为 0.771 / 1.713。测试时该相机不在 PCA 训练集中。它验证的是理想矩阵条件下的方法，未复制厂商真实建档过程，不能给本轮相机提供准确度保证。

桥接情景与“不可避免”的区别

固定随机种子 714，把 1,269 条 Munsell 分成 634 条训练和 635 条留出。所有 219 条自然物均不参与桥接训练。线性映射显式保持中性；平滑映射使用 R、G、B 及二阶根多项式，保持曝光齐次。评估目标空间是 GR IV 白平衡 RAW 经其固定 DNG 逆矩阵、Bradford 白点适应后的 D65 Lab。

下表全部是 80 个响应情景与独立留出光谱的合并 ΔE00 中位 / p90，不是现场验收。

| 桥接 | Munsell 留出 | 自然物留出 |
|---|---:|---:|
{chr(10).join(table)}

“共同”映射不知道单次情景的真响应，而是对所有情景训练。最后两行逐模型知道模拟真响应，具有实际工作中没有的资料，只能说明受限函数在该模拟里的剩余误差。其平滑余差 {pair(oracle['pooled'])} 不能命名为这两台实机的同色异谱下限，也混有映射自由度与训练分布的限制。

| 日光条件 | ColorMatrix | 共同平滑 |
|---|---:|---:|
{chr(10).join(light_table)}

D65 自然物情景中，各模型矩阵桥接中位误差的 5/50/95 分位为 {interval(natural['per_model_median_p05_p50_p95'])} ΔE00。单个中心估计不能代表完整不确定度。

本轮还在自然反射率 6-PC 空间中构造了 120 对有界、平滑的模拟同色异谱。GXR 模型响应最大差为 {sim['conditional_metamer_examples']['same_gxr_max_abs_difference']:.2e}，GR IV 模型输出分离中位 / p90 为 {pair(sim['conditional_metamer_examples']['target_separation'])} ΔE00。这证明当前响应模型存在信息丢失的反例；它没有测量这些反例在日常照片中的频率，不能推出总体 median 的非零下限，也不能把该分离除二当作 ΔE00 的严格最小误差。

01/02 的传播保留原始相对风格目标、Standard-only 中灰锚和原指标，逐点改变目标 Lab 向量后重算分子与分母。没有把几个 median ΔE00 相加。逐点模型、共同支持、整色相留出、95% 差距比例与重新评分均在 [本地私有附录](local/CEILING_PRIVATE.md)及 `local/ceiling_propagation.json`。原冻结 LUT 没有重拟合，因此这些值表示其对桥接假设的敏感性，不是新的优化上限。桥接 oracle 的自然物余差也未被偷换成现有屏幕色块上的已知噪声。

GXR 现有真实 RAW/JPEG 检查也已保留。原生 CC24 图重新从冻结取样计算的 04 渲染余差与既有记录一致；四张高置信推断为 04、ISO200 的日常帧均重算了桥接候选的支持和目标变化。这些 JPEG 只提供 GXR 渲染真值，不能验证 GR IV 光谱准确度；没有把它们用于回拟本轮响应。细节只在 `local/gxr_existing_validation.json`。

能确定的是新 GR IV RAW 消除了“目标机完全没有真实色卡约束”这一缺口。仍未知的是实际光源 SPD、两张卡的逐张光谱、GXR 的面纱与空间颜色处理，以及真实自然场景中同色异谱的频率。现有证据给不出不可避免差距占比的非零下界；这不等于占比为零。现在把新的光谱点估计直接替换为正式目标，会把尚未闭合的 GXR 端失配一起固化。

复算与交付

```sh
python3 -I -B research/bridge_public_r1/pipeline.py run
shasum -a 256 -c research/bridge_public_r1/SHA256SUMS
```

新 RAW 的单命令录入与四角几何格式见 [README.md](README.md)。脚本不调用浏览器、设备或固件工具；无损 RAW 由已安装的 imagecodecs 解析，并由冻结的独立 Python SOF3 解码器逐值对照。新文件仍是不可执行的数据。`local/inputs.json` 是本轮实际消费的冻结输入；`local/frozen_verified.json` 是核对结果。下载失败、成功响应和所有内容摘要在 `local/sources.json`，新下载原件各自位于独立目录。

代码和公开数据研究报告可审阅；`local/` 含私有风格推导、照片取样和完整输入路径，不得公开。`SHA256SUMS` 包含本地证据的摘要与路径，也已设为本目录 Git 忽略。
'''
    (c.HERE/'REPORT.md').write_text(text)
    private=[]
    for r in p['results']:
        if r['subset']!='all_style_supported':continue
        reference=r['current_bridge_on_common_population']
        private.append(f"| {r['slot']} / {r['scheme']} | {r['n']} / {r['original_frozen_population']} | {reference['similarity_median']*100:.2f}% | {interval(r['conditional_score_p05_p50_p95'],100)}% | {interval(r['conditional_target_shift_median_p05_p50_p95'])} | {interval(r['conditional_gap_ratio_p05_p50_p95'],100) if r['conditional_gap_ratio_p05_p50_p95'] is not None else '原差距非正，不定义'}% |")
    appendix=f'''本附录含 GR IV 志愿者风格函数的衍生成果，仅留本地。这里的比例是桥接情景对既有评分的敏感性，实际不可避免的物理差距占比仍未知。

```text
S = 1 - median(配方到目标 ΔE00) / median(04 到同一目标 ΔE00)
条件差距比例 = (S_当前桥 - S_情景桥) / (0.95 - S_当前桥)
```

分子和分母都在同一共同支持总体逐点重算；不相加中位色差，不截断负值或超过 100% 的结果。每个情景都调用冻结 `gr4_lut_ceiling/style.py` 的相对目标函数与原 Standard-only 中灰锚。原目标逐点复现误差小于 1e-8。冻结的真实像素 33³ LUT 留出预测不变，没有用修改后的目标重新训练 LUT。

| 配方 / 留出 | 共同支持 / 原总体 | 原桥在共同总体 S | 情景 S 的 5/50/95 分位 | 目标位移中位的 5/50/95，ΔE00 | 条件差距比例的 5/50/95 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(private)}

在整色块留出中，01 的条件差距比例中位约 {next(r for r in p['results'] if r['slot']=='01' and r['scheme']=='patch' and r['subset']=='all_style_supported')['conditional_gap_ratio_p05_p50_p95'][1]*100:.0f}%，02 约 {next(r for r in p['results'] if r['slot']=='02' and r['scheme']=='patch' and r['subset']=='all_style_supported')['conditional_gap_ratio_p05_p50_p95'][1]*100:.0f}%。超过 100% 表示模型目标变化足以超过原本到 95% 的小差距，不是“超过 100% 的物理原因”，也不是不可避免下限。它还可能包含色卡、光源、标定、潜在输入坐标和函数近似的失配。

01 共同支持少于原总体，不能把其新分数与原完整总体分数直接相减。02 也有少量排除。自然光谱色域凸包内的严格子集另存在 `local/ceiling_propagation.json`。所有表均记录精确排除数、原总体分数和共同总体分数。

响应模拟的“真目标”来自估计曲线，不是 GR IV 对同一物体的实拍。屏幕测量生成的潜在 GXR `scene_x/320` 与物理白平衡响应的等价关系也没有独立标定。自然物上 oracle 根多项式的余差没有被附加为这个屏幕总体的真实噪声。因此该传播只能判断目前正式目标对桥接假设敏感，不能给新的 LUT 物理上限。

原生 R8051477 的 04 模型余差重新计算为 {pair(native['native_04_recomputed_error'])} ΔE00，共 {native['native_04_recomputed_error']['n']} 个冻结样本。日常 04 既有合并余差为 {pair(native['daylight_04_existing_pooled_residual'])}，四张真实 RAW/JPEG 的目标位移和覆盖另在 `local/gxr_existing_validation.json`；配方标签仍是推断。以上没有变成桥接准确度验收，也没有进入本轮响应拟合。

正式目标继续用共同白点 ColorMatrix。单一追加数据优先 GXR A12 50mm 的完整真 ColorChecker 自然日光 RAW。新的 GR IV studio RAW 已在本轮使用，无需重复提出取得同一份文件。
'''
    (c.LOCAL/'CEILING_PRIVATE.md').write_text(appendix)
    c.dump('summary.json',dict(bridge_error_conditional_natural_D65=natural['pooled'],
         alternative_shared_smooth=smooth['pooled'],conditional_oracle_smooth=oracle['pooled'],
         real_camera_bridge_error_identified=False,GRIV_chart_data_used=True,
         actual_01_02_unavoidable_gap_share=None,recommended_bridge='existing frozen common-white ColorMatrix',
         most_valuable_missing_datum='one complete genuine ColorChecker Classic GXR A12 50mm ISO200 natural-daylight RAW with known chart formulation',
         private_appendix='research/bridge_public_r1/local/CEILING_PRIVATE.md',
         source_holdout=hx['pooled_camera_matrix_Lab_residual'],target_holdout=hr['pooled_camera_matrix_Lab_residual']))
    print('Chinese report and local-only ceiling appendix written')


if __name__=='__main__':main()
