"""Render the review handoff from the final acceptance and cleanup receipts."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    acceptance=json.loads((HERE/'evidence/acceptance.json').read_text())
    package=json.loads((HERE/'evidence/package.json').read_text())
    cleanup=json.loads((HERE/'local/cleanup.json').read_text())
    assert acceptance['status']==package['status']==cleanup['status']=='PASS'
    digest=sha((PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes())
    assert digest==acceptance['dat_sha256']==package['dat_sha256']
    assert cleanup['temporary_directory_absent'] and not TMP.exists()
    assert sha((PACKAGE/'local/GXR-probe2.zip').read_bytes())==package['archive_sha256']
    s=acceptance['sizes'];plan=json.loads((HERE/'local/page-plan.json').read_text())
    counts=[]
    for phase,node,label in [('p1',16,'P1，节点 16'),('p2',8,'P2，节点 8'),('p2',19,'P2，节点 19')]:
        rows=[r for r in plan['pages'][phase]['coverage'] if r['node']==node and r['transfer']=='srgb' and r['scale']==1]
        by={r['channel']:r for r in rows}
        counts.append('| '+label+' | '+' | '.join(str(by[c]['left_points'])+' / '+str(by[c]['right_points']) for c in 'RGB')+' |')
    cold_rows=[]
    for u in acceptance['units']:
        cold_rows.append(f"| {u['unit']} | {u['owner_close_reopens']} | {u['foreign_rejections']} | 纯 04，完整 552 B / T=2 |")
    text=f'''可以交复审

P1 负向节点 16 与 P2 双节点 8/19 已合入同一个 v3.9 测试 DAT。C 逻辑和对象不改，只换配方、条目及按新 DAT 长度重链接的 BSS 引用。P1 拍 5 张，P2 拍 8 张，均固定 1/15、f/5.6，合计 13 张。

本结论针对交付字节、主机和声明过边界的模拟器验收。完整 GPIO→字体→LCD、实体存储卡、物理 NAND 保存和断电时序没有通过本轮实机验证。新屏幕页的输入覆盖是拍前预测，须由新 A 的 RAW 确认。

本包只给仍是 v3.9 的相机用。刷 v3.10 后不能用这个包；本说明中的 G154L 恢复 DAT 也不能带到 v3.10。

## 文件与身份

- [拍摄包 ZIP](../../firmware/package_v39_g154_probe2/local/GXR-probe2.zip) 含卡目录、完整步骤、页面及 ZIP 内校验清单。
- [卡目录 SD_ROOT](../../firmware/package_v39_g154_probe2/local/SD_ROOT/) 只有 `GXRCE.DAT` 和 `README.txt`，没有机身、resident 或单元固件。
- [OWNER_STEPS_PROBE2.md](OWNER_STEPS_PROBE2.md) 一次列完 13 张步骤；电脑打开 [ramp2.html](ramp2.html)。
- [研究 SHA256SUMS](SHA256SUMS)、[local 清单](local/SHA256SUMS)、[包清单](../../firmware/package_v39_g154_probe2/SHA256SUMS) 与 [MANIFEST.json](../../firmware/package_v39_g154_probe2/MANIFEST.json)。

| 输入或交付物 | SHA-256 |
| --- | --- |
| v3.9 ilaunch3 | `{BODY_SHA}` |
| looks18 / G154L 基底 | `{BASE_SHA}` |
| 旧探针 a30675fa | `a30675fa8450a7dcb258ca494f5f0615d054743b738190b4ef3b6c0a227b6de5` |
| 新 DAT | `{digest}` |
| 新 ZIP | `{package['archive_sha256']}` |

## 探针规格

只新增 MOUNT 的 P1/P2。50mm 和 28mm 的四条旧探针逐字节保留，机主本轮只拍 MOUNT。效果共 15 条，三个单元各能看到 4、4、7 条；无用户配方。逻辑列表各有 13、13、16 行，由虚拟滚动投射到固定 8 行。

| MOUNT 条目 | 修改内容，节点为零基 | 相对 A 的曲线载荷变化 |
| --- | --- | ---: |
| `M26 A` | 原 a30675fa 的 MOUNT A，完整 552 B 相同 | 0 字节 |
| `P1 R-2` | 仅 R 的节点 16 减 2 | 1 字节 |
| `P1 G-2` | 仅 G 的节点 16 减 2 | 1 字节 |
| `P1 B-2` | 仅 B 的节点 16 减 2 | 1 字节 |
| `P2 R+2` | 仅 R 的节点 8 和 19 各加 2 | 2 字节 |
| `P2 G+2` | 仅 G 的节点 8 和 19 各加 2 | 2 字节 |
| `P2 B+2` | 仅 B 的节点 8 和 19 各加 2 | 2 字节 |

表内只数曲线载荷，相关身份及 CRC 字段独立重算。所有曲线保持单调；另两通道、C100、其它参数及控制字节与 A 相同。没有 C120 改动。

唯一修改的原生基底是 `06 T26 A`，标题部分 `T26 A` 为 5 字符。所有效果名至多 7 字符，只用 ASCII 字母、数字、空格、`+`、`-`，不含反斜杠或星号。原生 01/02/03/04/05/07/08 的记录与完整 552 B 在三个单元共 21 份都与 looks18 相同。

A 使用已验证的独立三曲线模式，沿用旧探针；它与原生 04 的控制模式不同。不能把 A 的照片当作纯 04。原生 04 保持 Standard，恢复或结束拍摄时明确选 `04 Std`。

## 为什么选节点 8 与 19，以及怎样用一档曝光覆盖

沿用今天的 35mm f/2、七片式 Mandler 设计复刻版手动镜头，实际光圈 f/5.6。屏幕为 MacBook 内建屏、摄影（P3-D65）预设。按上午、午休、正式密集灰阶的已有逐块 RAW 数据规划，不使用忘切预设的第一遍作为定标输入。

节点 8 和 19 的相邻节点响应带分离，按当前局部插值工作模型不重叠。候选 8/20 在午休传递模型、亮度 −10% 时，R 的高端未跨过高节点支持区；8/19 在全部敏感性分支都能跨过两端，所以选 8/19。完整候选、覆盖与输入哈希只在 [page-plan.json](local/page-plan.json) 和 [候选数据](local/page-plan-candidates.json)。这项选型不宣告硬件插值算法已被确定。

两页各有 49 个灰块及蓝色、肤色、绿叶三个彩块。灰码按正式组两张 A 的逐块 RAW 反推，同一屏幕灰码在不同位置的相机输入不再强行视为相同。P1 灰码范围 110–216，P2 为 41–252。P1 保留原肤色，蓝块调到 B 的节点 16 响应带；P2 彩块分别调到高节点附近。允许灰码重复，49 指采样位置数。

以下是名义 sRGB 光传递下，落在峰值左右且仍在响应带内的灰点数。P1 的 R/G/B 最近峰值预测偏差约为 3.5/3.5/3.4 输入码；这是 RAW_WB 代理轴上的预测，不能替代真实 ISP 内部输入。

| 页 / 节点 | R 左 / 右 | G 左 / 右 | B 左 / 右 |
| --- | --- | --- | --- |
{chr(10).join(counts)}

另检查 gamma 2.2、午休 PCHIP、上午投影到 1/15 的 PCHIP，共四种传递；每种再检查 0.9、1.0、1.1 倍输入。全部分支的每个通道、每个节点，左右各至少有 2 点，并有点跨过支持区两端。没有在相机上读到新页的 RAW；屏幕亮度、构图或空间照度偏离旧组时，覆盖仍须重算。相机直方图不能核对通道节点，所以步骤写明“曝光固定 1/15，拍完由我们检查”。

页面继承封存 ramp 的 640×468 图板、标签带、中央 50% 采样区和四角编码。P1/P2 切换不移动图板；离线、零网络请求。固定 Playwright 1.61.1 / Chromium 1228 验证两页共 18 个窗口／显示状态，包含约半屏且不全屏的布局。936 个中央取样区逐像素色值相同，72 次四角定位解码通过，最小编码距离为 4。浏览器正常退出。

[P1 半屏截图](local/page/p1-864x900-capture.png)、[P2 半屏截图](local/page/p2-864x900-capture.png)、[页面回执](local/page/check.json)、[像素与角标检查](local/pixels.json)。标签均未压到采样区。相机透视、失焦、摩尔纹和角标裁切仍按实际照片定位检查。

## 最终 DAT 的验收

全部下列回执绑定上表的新 DAT 哈希，未用旧候选的运行替代最终版本验收。聚合入口为 [audit.py](audit.py)，结果在 [acceptance.json](evidence/acceptance.json)。

| 项目 | 结果及证据 |
| --- | --- |
| BSS 重链接 | 774 项 GOTOFF 全查，含 289 个 HI、289 个 LO BSS 引用；差异全限 BSS 引用，平移链接一致，所有符号在分配内。[独立审计](local/bss-audit.json)。 |
| 全部 552 B | 独立解析描述符和行池、从 looks18 04 推导 A 及各扰动、独立 CRC；15 条与生产 C 展开逐字节相同。21 份保留原生配方也相同。[独立结果](local/independent.json)。 |
| 真实 MAIN 冷启动 | 三单元均从第 0 步，原生顺序 0→2→32→5；无预置原生 UI、设置或锁字。使用现有 batch 版，三次冷启动与三次 post-B 重启都留有快照。 |
| 原生菜单 | 在真实 MAIN RAM 上执行原生父菜单、构造器及 DAT/resident。MOUNT 完整走本轮 13 步；另两单元各走 7 步。每次九类参数及控制字节回读、完整 552 B、OK 关闭／重开、回 A 与最终回 04 均通过。 |
| Python 复核 | 单元官方 packer 每后端 27 次，C/Python 相同；MOUNT 原生 13 步的 frames、四种视图、拒绝、关闭及诊断也完全相同。C 后端最终用例无非 PASS。 |
| 固定 8 行 | 三单元四种 DAT 视图全是 8 行；生产 C 穷举 61,250 个虚拟窗口，49 行边界通过，50 行拒绝。[主机回执](evidence/host.json)。 |
| CRC 拒绝 | header、payload、effect CRC 三种破坏 × 三单元，主机 9 次及原生入口 9 次均拒绝；无单元写入，设置不变。拒绝时保留原生列表，不发布 DAT 视图。 |
| 跨单元拒绝 | 三单元实际引擎投影入口共 30 次，全部拒绝；输出哨兵、设置、当前引用和单元写入数不变。 |
| post-B 重启 | MOUNT 的 9 份及另两单元各 3 份实际 post-B 设置，序列化后按单元全等；只更新原生校验尾部，4092 B 载荷不变。每单元各一次逻辑 NAND 读边界冷启动消费该 4096 B，回读一致，随后完整 552 B 为纯 04、T=2。 |
| 条目文字 | 生产 C 生成 24 个原生标题和 15 个效果名；原生菜单缓冲完整、未截断。所有新名字字形均来自同版本原生标题或旧探针，无新字形。字体／LCD 的实机可读性见后述边界。 |
| 可复现与封装 | 隔离重建 DAT、engine、reloc、trust 四件字节相同；Python 检查 48 份记录 CRC、15 效果及只读 codec roundtrip。ZIP 五文件、内层哈希、解压字节与原件一致。 |

| 单元 | 关闭／重开步数 | 跨单元拒绝 | 从 post-B 重启后的读回 |
| --- | ---: | ---: | --- |
{chr(10).join(cold_rows)}

| 容量 | 实际 B | 上限 B | 余量 B |
| --- | ---: | ---: | ---: |
| DAT | {s['file_bytes']:,} | {s['file_limit']:,} | {s['file_limit']-s['file_bytes']:,} |
| 代码 | {s['code_bytes']:,} | {s['code_limit']:,} | {s['code_limit']-s['code_bytes']:,} |
| 主块，含 BSS 与既有开销 | {s['main_request']:,} | {s['main_limit']:,} | {s['main_limit']-s['main_request']:,} |

BSS 为 {s['bss_bytes']:,} B。原生运行实际请求主块 {s['main_request']:,} B，与静态预算一致。{acceptance['protected_inputs']:,} 项冻结输入哈希全部保持不变。

冷启动使用现有 `tools/gxr_emulator_standby` 的批量路径。回执 `mode=fast` 指该后端要求的记录模式；另核对了 `batch=true` 与非零 `batch-steps`，没有把单步路径当作批量验收。

## 验证边界与拍摄后的判定

原 r1 的完整 GPIO→字体／LCD 路径停在既有模型错误 `NAND read exceeds provisional page geometry`。本轮沿用 r1 的 MAIN RAM→原生菜单执行方式，文件、RPC、绘字和字体引用有明确主机模型；没有把这条完整路径记作通过，也没有声称物理 NAND 或断电保存已验收。开拍前机主要滚动核对七种 MOUNT 名称完整可读，有方框或截断就按步骤停止。

三单元冷启动指主体 MAIN 与现有单元链路模型；官方单元 packer 另在隔离配置下执行，不等同于单元 MCU 的完整启动或真实像素管线验收。

工程验收证明新 DAT 写的是所列负向／双节点扰动、能在模型中恢复。它没有提前证明负向对称、多节点迁移或全颜色 L1 模型闭合。P1 与今天正向结果按输入位置对照；P2 两次同扰动做重复检查，首尾 A 检查漂移。仍分别分析 Y/Cb/Cr，不能用单一通道倍率吸收已发现的肤色色度反号，也不能把节点 16 的局部结果自动推广到新节点。C120 继续留作独立生命周期任务。

## 复查与清理

在项目根目录可复查最终收据和哈希，命令为：

```sh
nice -n 10 env GXR_HARNESS_BACKEND=c PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -I -B research/probe_pack_r2/audit.py
shasum -a 256 -c research/probe_pack_r2/SHA256SUMS
shasum -a 256 -c firmware/package_v39_g154_probe2/SHA256SUMS
```

`reproduce.py` 可在 local 和指定 Scratch 中隔离重建；重新执行后须再次清理它创建的 Scratch。批量冷启动与原生运行脚本在 local，完整调用参数留在回执／日志。固件字节、地址、DAT、ELF、RAM、截图和详细运行日志均留在忽略的 local 目录。未改封存的 r1 文件，未启动 Studio，未访问存储卡或刷机，未做 Git 写操作。

临时目录 `{TMP}` 已删除，共清理 {cleanup['files']:,} 个文件、{cleanup['bytes']:,} B；浏览器正常退出，无本任务计算进程残留。清理详情见 [cleanup.json](local/cleanup.json)。最终 SHA256SUMS 在清理后封存，覆盖报告、脚本、回执与包。
'''
    (HERE/'REPORT_PROBE2.md').write_text(text)
    print(json.dumps(dict(status='PASS',report='REPORT_PROBE2.md',dat_sha256=digest,archive_sha256=package['archive_sha256']),ensure_ascii=False))


if __name__=='__main__':main()
