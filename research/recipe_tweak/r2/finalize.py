#!/usr/bin/env python3
"""Read accepted artifacts, write the Chinese report, then seal every output."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json
import hashlib
from statistics import mean
import runtime as r
import tweak as t


def main():
    r.setup()
    read=lambda name:json.loads((r.LOCAL/name).read_text())
    validation,metrics,frames=read('validation.json'),read('metrics.json'),read('frames.json')
    preview=read('preview-check.json');target=read('m32r/result.json');budgets=read('write_budget.json')
    edges=read('edge_checks.json');audit=read('visual-audit/visual-validation-report.json')
    assert edges['passed'] and audit['summary']['failures']==0
    params=json.loads((r.HERE/'parameters.json').read_text())
    assert [p['id'] for p in params['parameters']]==list(t.PARAMETERS)
    assert all(p['default_range']==[-5,5] and p['extended_range']==[-8,8] and p['default']==0 for p in params['parameters'])
    assert list(params['gain_q12'].values())==list(t.GAINS)
    assert preview['passed'] and preview['records']==len(frames)==2550 and len(metrics['pairs'])==2400
    assert validation['original_C_validator']['exit_code']==0
    assert target['core_source_sha256']==r.sha(r.HERE/'tweak_int.c') and target['linked_undefined']==[]
    original_inputs=read('validation_inputs.json');preview_inputs=read('preview_inputs.json')['direct'];r1=read('r1-inputs.json')
    for group in (original_inputs,preview_inputs,r1):
        assert all(r.sha(r.ROOT/p)==h for p,h in group.items())
    state_path=r.LOCAL/'state_example.json';state_payload=state_path.read_text()
    ids=json.loads(state_payload)['identities'];state=t.RecipeState.deserialize(state_payload,r.EXPECTED_SHA,ids)
    assert state.get('01').warmth==5 and state.get('06').saturation==8
    bad_states=0
    for bad in (state_payload.replace('"warmth": 5','"warmth": 9'),
                state_payload.replace('"warmth": 5','"warmth": true'),
                state_payload.replace(t.ALGORITHM,'wrong-version')):
        try: t.RecipeState.deserialize(bad,r.EXPECTED_SHA,ids)
        except ValueError: bad_states+=1
        else: raise AssertionError('bad state accepted')
    assert bad_states==3
    labels=dict(zip(t.PARAMETERS,('对比','饱和','高光','阴影','冷暖','色调')))
    # Central ±1 comparison uses only the same first-round scenes, masks and float domain.
    ratios=read('step_ratio_r1.json');ratio_summary=[]
    for param in ('contrast','saturation','highlight','shadow'):
        group=[x for x in ratios if x['parameter']==param and not (param=='saturation' and x['slot']=='03')]
        values=[x['region_ratio'] for x in group if x['region_ratio'] is not None]
        ratio_summary.append(dict(parameter=param,mean=mean(values),minimum=min(values),maximum=max(values),n=len(values)))
    ratio_rows='\n'.join(f"| {labels[v['parameter']]} | {v['mean']:.2f}× | {v['minimum']:.2f}–{v['maximum']:.2f}× | {v['n']} |" for v in ratio_summary)
    format_num=lambda x:'无样本' if x is None else f'{x:.3f}'
    center=[]
    for slot in r.SLOTS:
        for param in t.PARAMETERS:
            agg=next(x for x in metrics['aggregates'] if x['slot']==slot and x['parameter']==param)
            a,b=(next(x for x in agg['adjacent'] if x['from_level']==level) for level in (-1,0))
            center.append(f"| {slot} | {labels[param]}{'，近似' if param in ('warmth','tint') else ''} | {a['full_mean']:.3f} / {b['full_mean']:.3f} | {format_num(a['region_mean'])} / {format_num(b['region_mean'])} |")
    center_rows='\n'.join(center)
    _,_,_,entries=r.baseline()
    gain_rows=[];plateau_summary=[]
    for slot in r.SLOTS:
        g=[]
        for level in (-8,-5,-1,0,1,5,6,7,8):
            _,_,info=t.saturation(*entries[slot]['rows'][2:4],level,slot!='03')
            g.append((level,info))
        if slot!='03':
            gain_rows.append('| '+slot+' | '+' | '.join(f"{i['effective_coefficient_gain']:.3f}{'，受限' if i['matrix_headroom_reached'] else ''}" for l,i in g if l in (5,6,7,8))+' |')
        entry=entries[slot]
        for param in ('contrast','highlight','shadow'):
            for level in (-8,-5,0,5,8):
                rows,_=t.apply(entry,t.Levels(**{param:level}),320)
                pairs=[('b5',rows[1])]
                if entry['mask']&2:pairs.extend((('C',rows[6][:33]),('D',rows[6][33:])))
                plateau_summary.append(dict(slot=slot,parameter=param,level=level,
                    equal_adjacent_nodes={name:sum(a==b for a,b in zip(row,row[1:])) for name,row in pairs}))
    gain_table='\n'.join(gain_rows)
    scene_rows=[]
    for scene in metrics['scenes']:
        g=[x for x in metrics['pairs'] if x['scene']==scene['id'] and x['parameter']=='saturation' and x['from_level']==0 and x['slot']!='03']
        region_fraction=mean(x['region']['n']/x['full']['n'] for x in g)
        scene_rows.append(f"| {scene['title']} | `{scene['path']}` | {scene['iso']} | {region_fraction*100:.2f}% |")
    scene_table='\n'.join(scene_rows)
    clipping_rows=[]
    for scene in metrics['scenes']:
        for slot in r.SLOTS:
            group=[x for x in frames if x['scene']==scene['id'] and x['slot']==slot]
            default=next(x for x in group if x['level']==0)['model_rgb_clip_fraction']
            panel=max(x['model_rgb_clip_fraction'] for x in group if abs(x['level'])<=5)
            extreme=max(x['model_rgb_clip_fraction'] for x in group)
            clipping_rows.append(f"| {scene['id']} | {slot} | {default*100:.2f}% | {panel*100:.2f}% | {extreme*100:.2f}% |")
    budget_rows=[]
    for slot in r.SLOTS:
        for param in t.PARAMETERS:
            group=[x for x in budgets if x['slot']==slot and x['parameter']==param]
            panel=[x for x in group if -5<=x['from_level'] and x['to_level']<=5]
            budget_rows.append(f"| {slot} | {labels[param]} | {max(x['logical_row_bytes'] for x in group)} | {max(x['W_payload_bytes'] for x in panel)} / {max(x['W_payload_bytes'] for x in group)} | {max(x['T_control_bytes'] for x in group)} | {max(x['S_bytes'] for x in group)} |")
    r.dump(r.LOCAL/'analysis_summary.json',dict(r1_r2_region_step_ratios=ratio_summary,curve_plateaus=plateau_summary,
        host_state_file_reload=True,bad_state_rejections=bad_states,
        source_and_r1_inputs_unchanged=True,parameter_contract_matches=True))
    report=f'''# recipe-tweak 第二轮报告

六参数计算参考和验证产物已交付，面板范围 −5..+5、扩展 −8..+8。对比、饱和、高光、阴影在同一批原始场景上的中心单档作用区 ΔE00，较第一轮平均增至 {', '.join(f"{labels[x['parameter']]} {x['mean']:.2f} 倍" for x in ratio_summary)}。默认 ±5 的饱和请求均可分配；扩展高档的明确限制见下表。代码和模型产物均已生成，原 C/深层校验通过。

冷暖、色调的逻辑轴和整数编码已交付，但原生两个字段的轴序、正负方向与实际增益没有既有证据确认，接口要求显式绑定，不提供猜测的默认值。WB 图片只是近似模拟。接触表中 +5 饱和已经出现红苹果大面积红色细节丢失，不能宣称本轮所有默认极值都满足“画面不破”的审美要求；这套强度可供用户选型，尚不支持无条件整套定版。全部微调预览均为“模型模拟，非实拍”。`firmware_ready=false`，`camera_acceptance=false`。

## 已核实

- 写入前确认 `/Volumes/Workspace` 挂载、可写、APFS，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。输出限定于 `research/recipe_tweak/r2/`，派生条目、表数据、C 校验片段、目标文件、图像和日志均在 `local/`。
- 五个配方 01/02/03/05/06 × 六控 × 17 档，共 510 条单控记录全部通过。28,405 个多参数组合通过；原 C 共接受 28,916 张合法整表，包含原基表，拒绝 11 个损坏案例。整表通过 stdin 验证，没有写新的 DAT。
- 三个影调控件的全部 `17^3` 组合在每配方上核对端点、精确中灰、单调与 C/Python 字节。加上 06 三通道和 A20 哨兵分支，共 39,304 条曲线逐字节一致。85 个饱和组合的 colour、matrix 及增益值一致；11,560 组 WB 编码与原 `rv1_validate_recipe()`、`rv1_plan()` 一致。
- 五张 DNG 得到 2,550 条模型记录、2,400 组相邻整数档指标。HTML 对照页包含每配方每参数的指定七档和 ±8，另可选全部整数档。03 饱和停用，所有档位复用同一默认图。
- 模型 T1 适配层在 C=B5=D 时与 Engine 的 RGB 最大误差为 {metrics['T1_adapter_max_RGB_error']}。沿用第一轮 raw_input/predict/save_frame 函数体，固定 ISO200 模型、固定曝光和同一源白平衡。没有按档位重新匹配曝光。
- 固定 Playwright 1.61.1 / Headless Shell 1228 已检查 {preview['interactiveStates']} 个交互状态，320/390/768/1280 px 无页面横向溢出、坏图或控制台错误。视觉审计无失败项，初次发现的短按钮宽度不足44px已修正；排版扫描通过。为遵守“不sleep或轮询”，审计工具的本地副本以字体/图片完成事件和下一绘制帧替换固定延时，改动记录在 `local/ui-tools/adaptation.json`。模型 ΔE00 用 Sharma 参考值 2.0425 做了抽查。
- 独立合成的 colour=满幅、matrix色度=满幅条目仍通过原C与深层规则；全局预算限制保持字节而非逐系数钳位。正负零保留，10个WB越界配方被原C拒绝，结果在 `local/edge_checks.json`。
- 第一轮 {len(r1)} 个文件与初始清单一致；官方 ilaunch3/jlaunch3、日用基表和所用源码输入哈希一致。没有连接相机、访问其它卷或存储卡、刷机、生成上卡文件、提交或推送 Git。

## 参数契约与方向

机器接口为 `parameters.json`，算法版本 2，标识 `{t.ALGORITHM}`。每配方保存六个 int8 值；默认均 0，默认范围均 ±5，扩展硬上限均 ±8。UI 不含锐度。

| id / 数字 id | 正值行为 | 每档单位与算法 |
| --- | --- | --- |
| contrast / 0 | 压暗中灰以下、提亮中灰以上。 | 分段 odds 的 log2 强度 ±1/2，查整数表后略有量化。 |
| saturation / 1 | 增加颜色系数增益，03 停用。 | 请求系数倍率 `(5/4)^level`，Q12 四舍五入；不是 Lab C* 百分比。 |
| highlight / 2 | 提亮中灰以上。 | 高侧 odds 的 log2 强度 +2/3。 |
| shadow / 3 | 提亮中灰以下。 | 低侧 odds 的 log2 强度 +2/3。 |
| warmth / 4 | 逻辑 A-B 轴偏琥珀，负值偏蓝。 | 原生 WB 一格，不是色温 K 或曝光 EV。 |
| tint / 5 | 逻辑 G-M 轴偏品红，负值偏绿。 | 原生 WB 一格。 |

所有设置都从不可变默认配方与六档状态重算，不把上次结果当输入。`RecipeState` 以算法版本、基表 SHA-256、每配方默认 entry 身份绑定；JSON 文件重新加载、单配方恢复、其它配方保留、拒绝版本错误/超范围/bool 冒充整数已验证。这是主机状态参考，不是卡上原子持久化实现。

## 影调公式与任意组合的单调保证

保留 A、黑白端点，以及包围 `pivot_x=320` 的两个默认 B 节点。该点沿用 stock 04 输出 118 的模型锚，不把输入 18% 假充已标定中灰。对低、高两侧分别取默认输出段的 `lo, hi`，`L=hi−lo`、`t=y−lo`：

```text
k_low  = -3 * contrast + 4 * shadow
k_high =  3 * contrast + 4 * highlight
odds[j] = round(64 * 2^(j/6)), j=0..56
k > 0: n=odds[k], d=64
k < 0: n=64, d=odds[-k]
new_y = lo + round(L*n*t / (d*(L-t)+n*t))
```

`k=0` 或 `L=0` 直接保留原值。连续映射的导数为 `L²*n*d / [d*(L−t)+n*t]²`，在非空段严格为正；正分母的同向舍入保留非降。因此任意六控组合都不需要曲线钳位、累计最大值或事后单调修复。实际对 255 种段长、113 种 k 检查了 28,815 个整数映射域。全部0档还原原 entry 和原整表字节。

理论半段中点处，中心 ±1 的形变量约为第一轮对比的 1.86 倍、高光/阴影的 1.83 倍；实际图像差异见同域实测。单控 +5/+8 时，对比 odds 约 5.66/16，高光与阴影约 10.08/40.31。组合可把 |k| 推到 56，映射仍单调，但极端肩趾会压缩大量码值。

06 按 R=C、G=B5、B=D 对三个默认通道分别重算，各自锁住自己的中灰。启用 row20 时支持它自己的 A20/B20；本日用表没有启用 row20，C/Python 哨兵测试不代表验证了它的真实画面语义。

所有数值变换使用 32 位整数。最坏分子为 {validation['max_uint32_numerator']}，加舍入项仍小于 2^32。C 使用 uint32_t，不能改成有符号 int32_t 做同一乘法。

## 饱和的增益分配和限制

先以同一倍率缩放 colour 的全部 96 个符号幅值字节，保留符号，包括负零。可用 colour 增益上限为 `floor(127*4096 / 默认最大幅值)`。超过这一预算后，把剩余请求增益分配到两个 type-28 矩阵的 Cb/Cr 六个色度系数，各使用同一 Q12 倍率；不改 Y、偏移、符号、mask 或 control。矩阵增益的预算为 `floor(1279*4096 / 两行最大色度幅值)`。

这样不会逐个系数截到 127 或 1279，避免各扇区在不同位置突然停止增长。预算本身有明确上限；超过总空间时统一限制矩阵倍率并报告。全部相关彩色配方原来就启用 matrix mask，因此无需修改条目类型。所有新矩阵通过原 matrix_valid 和深层条目规则。

| 配方 | +5 实际系数倍率 | +6 | +7 | +8 |
| --- | --- | --- | --- | --- |
{gain_table}

−5 请求约 0.328 倍，−8 约 0.168 倍；+1 为 1.25 倍、−1 为 0.8 倍。乘法的正负档互为倒数，因而 −1 相对第一轮 −1 的幅度并非严格两倍。01/02 的 +7 和 +8 输出完全相同；05/06 的 +8 仍比 +7 强，但未分配完全部请求。默认 ±5 没有最终增益受限的档位。

矩阵增益位于扇区模型之前，并会放大默认配方已有的中性色偏；缩放还存在整数舍入。这里的倍率只是两组系数增益乘积，不能把它当作最终 RGB 或 Lab 色度的精确倍率。矩阵中性行和可能因舍入改变约 1 个 Q10 单位，原来非零的和也会随增益变化。没有声称与 HSV 饱和滑块相同。

## WB 的已知、接口边界与模拟

原 `recipe_apply.c` 已确认两个物理字段为 `S+0x6dd`、`S+0x6de`，各使用 `signed+9`，有效编码 1..17。默认逻辑轴 0 时，面板 −5/−3/−1/0/+1/+3/+5 对应本轴 −5/−3/−1/0/+1/+3/+5 格；扩展 ±8 用满原生范围。若物理符号为正，对应编码是 4/6/8/9/10/12/14，±8 对应 1/17；物理符号相反则对调。

`wb_axes()` 先在逻辑 A-B/G-M 坐标内把“默认轴+档位”限制到 ±8，并报告受限轴。`rt_wb()` / `wb_plan()` 必须显式传 AB lane 与两个符号，才输出物理字段顺序的两个字节。所有当前默认配方的两轴都是 0，所以单控 ±8 没有范围钳位；非零默认轴的边界已做主机一致性检查。

`research/hidden_processing/REPORT.md` 第5节明确指出“两轴对应 G/M、B/A 的顺序及最终增益运算尚未确认”。本轮没有发现能推翻它的证据。因此枚举八种 lane/sign 绑定并通过原 C，仅证明这些数值均合法，不证明其中哪一个方向正确。接手引擎必须在其已知的原生轴 API 中绑定；不能把这个枚举测试当标定结果。

预览只示意语义方向，在 DNG 相机 RGB 上乘 `2^[w/12+t/24, −t/12, −w/12+t/24]`。每轴 ±8 的相对通道比变化明显，但这不是原生 WB 灵敏度，也没有换算色温 K。03 保持真黑白，WB 只通过通道混合改变明度。真实“±1 能多大”与原生 AWB/补偿链是否启用仍未知。

## 素材和模型方法

| 场景 | captures/a12-50 下的 stem | 源 ISO | 默认图有色区比例，四彩色配方均值 |
| --- | --- | --- | --- |
{scene_table}

后两张来自原苹果静物的另两次近景拍摄，有色物体占比更高；85 组现存 DNG/JPEG 中没有另一组更丰富、独立的真实题材，多数是屏幕色表。这里没有拿屏幕色表充实景，也没有宣称增加了户外/人像覆盖。

模型直接读取 DNG，CFA 各平面先面积缩至 320 px 宽，扣黑电平、归一白电平并应用源 AsShotNeutral，固定 raw gain=1。指标从最终 0..255 裁剪后的浮点 RGB 转 sRGB/D65 Lab，再算 ΔE00；PNG 是同一结果四舍五入为8位。没有把原 JPEG 再套滤镜，没有按配方匹配曝光或白平衡。源 ISO 不是本轮模型的标定 ISO200，绝对颜色和高 ISO 画质没有验收。

## 相邻档 ΔE00

完整 2,400 组在 `local/adjacent_delta_e00.csv` 和 `local/metrics.json`，包含全部 −8→−7 到 +7→+8 的整数相邻对、全图和作用区的均值/p90/样本量。HTML 每个配方每参数都能看全部16组的五场景等权均值。下表单独列最关心的中心两档，单元格左为 −1→0、右为 0→+1。

作用区固定按默认图选：对比=全图，饱和=C*≥10，高光=Y≥118，阴影=Y<118，WB=中性 C*<10 且20≤Y≤235。没有样本的场景不参与区域均值；03 饱和区域为空。

| 配方 | 参数 | 中心两档全图均值 | 中心两档作用区均值 |
| --- | --- | --- | --- |
{center_rows}

与第一轮比较只用原三张素材、同一浮点域、同一作用区，分别比较默认到 ±1。以下均值是非零比值的等权平均，范围是场景/配方/方向的样本范围，不是置信区间。

| 参数 | 第二轮/第一轮作用区 ΔE00 均值 | 样本范围 | 样本数 |
| --- | --- | --- | --- |
{ratio_rows}

这些数值说明控件比首轮更强，不能单凭 ΔE00 阈值宣布所有场景都“一眼可见”或所有 ±5 都有审美保证。相机主人可直接看指定九档对照；WB 灵敏度不在这一对比中冒充原生实测。

## 钳位、出界与 ±8 使用限制

- 曲线钳位 0，单调修复 0，逐系数钳位 0。8位舍入会使部分相邻输出节点同值，这是量化，不是修复。逐配方、参数、档位的同值节点计数在 `local/analysis_summary.json`。
- 饱和的 colour 预算到顶后转移到矩阵；最终矩阵预算到顶的档位为 01/02 的 +7/+8、05/06 的 +8。03 饱和始终停用。完整22条预算转移/受限记录在 `local/validation.json`，其中只有6条达到最终矩阵上限。
- WB 非零默认轴叠加档位会在 ±8 限制，并返回受限标志；当前全零默认轴的单控范围内无此情况。物理字段顺序和符号不提供猜测默认。
- 高光控制不能恢复 DNG 已裁剪的信息；暗部提升不能生成纹理或消除噪声。极端影调组合虽单调，也会产生强烈肩趾和码值压缩。±8 不自动等于有用的照片外观。
- 输出 RGB 出界率是模型在显示前低于0或高于255的像素比例，不是条目编码钳位。纸张场景默认已有大量出界；以下不能解释成全是新算法造成。

| 场景 | 配方 | 默认出界率 | 单控 ±5 内最大值 | 单控 ±8 内最大值 |
| --- | --- | --- | --- | --- |
{chr(10).join(clipping_rows)}

已证明的是合法条目、有限模型输出、影调不反转、影调映射固定端点与各自中灰、0档还原默认。高饱和的红色细节损失仍是明确画面限制；不能把“合法”当“所有大档位都没有色域裁剪、量化或不受欢迎的风格”。超出 ±8 不能只改 UI：odds 表、16位常量、32位乘法上界和校验必须一起重算，WB 也不能超出原生 ±8。

## M32R 代码、内存和每档写入量

复用仓库既有 `m32r-elf-gcc`，以 `-Os -m32r -mmodel=large -msdata=none -G0` 编译并做可重定位链接。计算核心 {len((r.HERE/'tweak_int.c').read_text().splitlines())} 行 C，代码段 1,224 B、数学只读常量 148 B，总计1,372 B，data/bss均0，未解析符号0。除法编译为原生 divu，不依赖 libgcc。目标 ELF 是离线可重定位计算对象，不是可装载相机补丁或上卡文件。

编译器静态栈报告：rt_tone 176 B，rt_saturation 28 B，rt_wb 8 B，warp 0 B。每配方六档共6 B，五配方净状态30 B；两份448 B活动/待提交条目需要896 B，另计版本、身份、可靠持久化、RPC缓冲和UI。接入既有引擎的状态、差分、WB绑定和失败处理，估计仍需约150–300行C，尚未实现或测出目标代码字节。

以下按“相邻档时重写发生变化的整行”统计最大值。W是既有半字协议数据，B5的33 B按34 B覆盖且必须保留邻接字节；T1的06另需关闭/重开control各一半字，共4 B。WB列是最小差分的S字段字节，不是模块W数据。

| 配方 | 参数 | 整变化行逻辑B | 数据W B，面板/扩展 | T控制B | S字段B |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(budget_rows)}

饱和进入矩阵增益后，colour96 B + matrix56 B，共152 B；低档仅96 B或因舍入没有变化。01/02 从+7到+8完全不变，可跳过写入。多控合成只重写每条变化行一次：普通彩色最多185 B逻辑/186 B数据W；06最多251 B逻辑/252 B数据W，加4 B控制，共256 B W payload；两轴WB最多另2 B S字段。X/V定位、读前检查、读回、RPC头、状态文件CRC、持久化不含在这些数字里。

WB最小差分要求接手引擎在已有所有权内只更新所需字段。若直接复用完整 `rv1_plan()`，其额外字段/selector写入不属于本表的最小成本。应保留默认 Rv1Recipe 作为深层身份，不能改 WB 后再让完整字节匹配去识别深层配方。整组成功后才发布新 generation；保留旧活动快照与待提交缓冲，沿用sticky uncertain、T1安全顺序、邻接字节保护和失败拒绝。

没有测量M32R运行耗时、模块通信或按键到取景器延迟，不能从代码小或宿主通过推导实时性。

## 推断

更强的中心步长、完整整数域证明和模型九档对照，支持把默认±5作为第二轮用户选型候选。全局增益分配比逐系数硬截断更容易保留扇区间的比例，但最终视觉仍受扇区模型、色域和配方原有偏色影响。卡上引擎和容器可共用这份参数JSON与计算核心；生命周期、持久化及原生WB轴绑定由接手实现负责。

## 未知

原生WB的物理轴序、符号、每格增益、条件禁用与AWB交互未确认；近似模拟不能替代它。没有相机预览/JPEG一致性、相机接受、M32R执行时序、原子落盘/断电恢复、原生菜单并发、真实失败回滚证据。素材只有室内静物；没有本轮户外、人像、A12 28mm或MOUNT A12证据。

## 产出和复核命令

公共接口：`tweak.py`、`tweak_int.c/h`、`parameters.json`。可重跑工具：`verify.py`、`check_edges.py`、`preview.py`、`refresh_html.py`、`check_preview.mjs`、`measure_m32r.py`、`finalize.py`。视觉契约为 `DESIGN.md`。

主对照页：`local/preview.html`。原始证据：`local/validation.json`、`local/native/result.json`、`local/variants.json`、`local/metrics.json`、`local/adjacent_delta_e00.csv`、`local/step_ratio_r1.json`、`local/write_budget.json`、`local/m32r/result.json`、`local/preview-check.json`。五场景×五配方的全参数九档接触表在 `local/contacts/`。

首次M32R链接命令多加了不必要的 `-lgcc`，报错 `cannot find -lgcc: No such file or directory`。检查对象无未解析符号后移除该链接参数，可重定位链接成功；原始错误保留于 `local/m32r/first-link-failure.json` 和 `local/m32r-first-failure.log`，没有安装或修改工具链。

从共享仓库根目录复核：

```sh
python3 -I -B research/recipe_tweak/r2/verify.py
python3 -I -B research/recipe_tweak/r2/check_edges.py
python3 -I -B research/recipe_tweak/r2/measure_m32r.py
python3 -I -B research/recipe_tweak/r2/preview.py
TMPDIR="$PWD/research/recipe_tweak/r2/local/tmp" node research/recipe_tweak/r2/check_preview.mjs
TMPDIR="$PWD/research/recipe_tweak/r2/local/tmp" node research/recipe_tweak/r2/local/ui-tools/validate_html_visual.mjs --input research/recipe_tweak/r2/local/preview.html --out research/recipe_tweak/r2/local/visual-audit --viewports desktop=1280x1000,mobile=390x900 --wait 0
python3 -I -B research/recipe_tweak/r2/finalize.py
cd research/recipe_tweak/r2
shasum -a 256 -c SHA256SUMS
```

基表SHA-256：`{r.EXPECTED_SHA}`。最终 `SHA256SUMS` 覆盖本目录所有文件，唯独排除它自身；本报告不包含理光表的原始字节。
'''
    (r.HERE/'REPORT.md').write_text(report)
    # Seal the delivered files after all logs and visual artifacts have settled.
    lines=[]
    for p in sorted(r.HERE.rglob('*')):
        if p.is_file() and p.name!='SHA256SUMS':
            assert not p.is_symlink()
            lines.append(f"{r.sha(p)}  {p.relative_to(r.HERE)}")
    (r.HERE/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(report='research/recipe_tweak/r2/REPORT.md',sealed_files=len(lines),
        r1_files_unchanged=len(r1),frame_records=len(frames),region_step_ratios=ratio_summary),ensure_ascii=False))


if __name__=='__main__':main()
