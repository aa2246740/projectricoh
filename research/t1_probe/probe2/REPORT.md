# T1 probe2：用一次往返区分三张通道曲线

2026-10-20。probe2 已生成，主机加载、切换和 ASan/UBSan 验证通过。v2 模型下 21 个假设的 210 对比较全部可分，最小全块 RGB RMS 距离为 19.79 码，是现有两张 04 重复性 RMS 的 16.37 倍。21 个合成 JPEG＋DNG 假设及 420 次带实测噪声的数值试验全部识别正确。相机端的通道映射、曲线语义及重启后的状态仍待明天实拍。

## 改动和交付

以 tables-v3 为底，只改 entry index 7，即 slot 08 的 C。C 在 B5 下标 4..28 减 24，先截到 0，再累计取最大值；D 原样保留。A5、B5、色表、矩阵、mask 0x06、control 0x0000、配方绑定和其余七条 entry 均不变。两张辅助曲线都不下降，末值均为 255，高于生成器最低值 128。

旧探针 C=B5，只能辨认 D 的通道。新探针 C 下压、D 上抬，让 B5/C/D 的响应不同；如果 C 广播到所有通道，也会整体变暗，能够与无效果分开。

最终 DAT 各 3600 B，两份完全相同。与 tables-v3 共差 33 B：C 数据 25 B、C/D 整行 CRC 4 B、文件 CRC 4 B。允许差异区域仅为文件偏移 12..15、3432..3435、3531..3563，逐偏移检查通过。D 的 33 B 未变。

按公开仓库的数据边界，DAT 和完整 entry JSON 实际放在 [tables-v3-probe2/local/](../../../artifacts/stage2j-packages/tables-v3-probe2/local/)。上层提供 manifest.json、NOTICE 和 SHA256SUMS；没有在上层复制原始字节。`entry08_probe2.json` 沿用 `gxr-deeptbl-entry-v3-1`，可用原 `merge_entry()` 解码替换，再经 `src.seal()`、`src.parse()` 重建同一 DAT。两个 local/ 均由既有规则忽略，逐文件 `git check-ignore` 已核对。

| 项目 | SHA-256 |
|---|---|
| tables-v3 基线 DAT | `9f6b727fa9bf84b09b030a93338d0eaf49f7da2117278309c3683bf0c99bb2b1` |
| probe2 DAT0 = DAT1 | `5c643fdd8cbb9ffc4ad68fe27fd9a6480e0a3db1cff4256e3d67cd4b592e3456` |
| entry08 的 448 B 内容 | `cbbf5a1b035a10e509f982497e66e0b78d9f451d2ebf8c66f2773d216e5e9d5f` |
| entry08_probe2.json 文件 | `7ed81c488b91fdd06a4a1309eb17278ff4d78a3f81d62484c4d3037555ff802a` |
| ring_model_v2.json | `c4c9e55df225740ae7c9afddcf2aa4b4a386f5a0857a2e78db600076af44cded` |

## 主机验证

`build_validate.py` 只导入原 T1 的生成器、merge_entry 和逐事务核验函数，没有运行旧生成器的 main，也没有重做其他配方拟合。实际编译 Stage 2j 的 equiv_driver.c 和原验证器指定的七个 C 文件。短顺序在 /tmp/t1p2/host/ 复制驱动，只替换顺序声明；共享固件源文件只读。

普通与消毒构建都使用 `-std=c11 -O1 -g -Wall -Wextra -Werror -DRECIPE_FW_HOST -DRFW_DEEP_ENABLED=1 -DEQUIV_2H -DEQUIV_2I`。消毒构建另加 `-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer`。

| 顺序 | 每次 probe2 运行 V / W / X | 总 RPC | T 进入 / 恢复 | 颗粒 |
|---|---:|---:|---:|---|
| 04 → 08 → 04 | 15 / 260 / 13 | 288 | 1 / 1 | 无 |
| 04 → 01 → 02 → 05 → 06 → 07 → 08 → 04 → 03 → 04 | 41 / 1072 / 39 | 1152 | 1 / 1 | 无 |

两种构建分别运行 tables-v3 和最终 probe2，共四次编译、八次驱动运行，全部退出 0。普通与 ASan/UBSan 的完整记录逐字节相同。全部 RPC 都是 V/W/X，没有构造或发送 U 命令。进入 08 恰好写一次 T=0，离开恰好恢复一次 T=2；控制预检、行顺序、写入回读、七行 RAM、邻接保护字节、设置、提交状态和重开菜单均按原验证器检查。两套顺序最后的 04 状态与 tables-v3 的 04 相同。

编译/运行命令和无原始数据的日志在 `logs/`。含 RPC 和 RAM 的完整记录在 `local/host/`，汇总在 `local/host_validation.json`，精确差异偏移在 `local/changed_offsets.json`。以上是主机模块模型中的观察。

## 预测链和可分性

使用 `ring_model_v2.json` 与原 `ring_model_v2.PreTable`、sector_model.py、matrix_model.py。顺序为白平衡后的线性相机 RGB → 每通道 type-26 曲线 → stock type-28 矩阵 → 查表前色相坐标的 ring v2 → JPEG。没有把 04 JPEG RGB 直接当作曲线输入，也没有调用旧 model/1 的输出色相坐标。

04 基线只用 ISO 200 的 R8051179、R8051182。读取原标定 inset 40 的 10% 截尾均值和 DNG 相机 RGB，以 DNG 的查表前色相提示选择逆变换分支，再正向验证。两张 04 各自预测后取平均。全部 155 块都预测，包括 144 彩块、9 个 L*10..90 灰块和两个白块。1178 排除。stock 往返最大 JPEG 差小于 0.000040 码，只证明软件往返一致。

假设名称末尾三个字母按 R/G/B 顺序，B 表示主表 B5，不表示蓝通道。

- `absolute_*` 的六个排列直接把 B5、C、D 当作三个通道的绝对输出曲线。
- `offset_*` 的六个排列按每通道 `clamp(B5(x) + table(x), 0, 255)` 计算，包括分到主表 B 的通道。
- `aux_offset_*` 的六个排列只把 C/D 当偏移，分到 B 的通道仍用 B5。静态资料没有排除“主表绝对、辅助表增量”的解释。
- `broadcast_C`、`broadcast_D` 分别让所有通道使用 C 或 D；`no_effect` 全部使用 B5。

下表是 9 个灰块的 ΔRGB 算术平均，单位为 JPEG 码。色表会在曲线后改变色度，所以不能仅凭某个输出通道的正负号，直接认定它对应哪张曲线。

| 假设 | 灰块平均 ΔR | ΔG | ΔB |
|---|---:|---:|---:|
| absolute_BCD | +21.98 | -37.42 | +50.10 |
| absolute_BDC | -17.12 | +37.42 | -52.50 |
| absolute_CBD | -35.26 | +3.78 | +41.34 |
| absolute_CDB | -46.43 | +38.87 | -14.80 |
| absolute_DBC | +31.16 | -2.21 | -33.51 |
| absolute_DCB | +41.48 | -32.83 | +11.33 |
| offset_BCD | +75.90 | +48.49 | +88.73 |
| offset_BDC | +57.78 | +83.12 | +40.18 |
| offset_CBD | +49.39 | +68.10 | +85.41 |
| offset_CDB | +42.99 | +83.58 | +59.58 |
| offset_DBC | +80.45 | +65.28 | +51.08 |
| offset_DCB | +84.10 | +50.54 | +72.39 |
| aux_offset_BCD | -33.78 | +60.96 | +89.54 |
| aux_offset_BDC | -44.58 | +89.09 | +39.66 |
| aux_offset_CBD | +73.99 | -30.07 | +95.83 |
| aux_offset_CDB | +40.94 | +88.02 | -55.34 |
| aux_offset_DBC | +90.09 | -28.29 | +70.16 |
| aux_offset_DCB | +82.57 | +54.96 | -36.32 |
| broadcast_C | -20.43 | -20.52 | -20.48 |
| broadcast_D | +21.86 | +21.95 | +21.91 |
| no_effect | +0.00 | +0.00 | +0.00 |

两张 04 的 155 块 RGB 重复性 RMS 为 1.2094 码；9 个灰块 RMS 为 0.4979 码，单通道最大差 1.0593 码。最近假设是 offset_BCD 与 offset_DCB，全块距离 19.7930 码；灰块距离 16.6600 码，约为灰块重复性 RMS 的 33.46 倍。全部 210 对距离保存在 `local/predictions.json`，没有只挑最容易分开的假设。两张 04 单独给出的预测差，最大全块 RMS 为 1.5443 码，仍远小于最近假设间距。这些倍数以一对实拍的 RMS 为参照，不是统计置信区间。

同一链计算旧 v3 时，七对预测完全重合：absolute 的 BCD=CBD、BDC=CDB、DBC=DCB；offset 的同样三个配对；broadcast_C=no_effect。因此 21 个假设只剩 14 个不同预测类。其余类的最小距离为 16.2782 码。旧 v3 在绝对曲线模型下可找 D 的通道，却不能分清其余两通道的 B5/C；如果所有通道都走 C，则与无效果一样。probe2 去掉了这些等价关系。

这些图像数值是模型推断。静态资料没有确认 control=0 时硬件一定独立使用三张绝对曲线，实机也可能表现为未列出的机制；分析器在残差或领先不足时输出“未确认”。

## 分析器用法和判定

三个位置参数必须按 04a、08、04b 排列，每张 JPEG 旁有同名 DNG。不要只传 JPEG 或以 MakerNote selector 当作配方槽号。

```sh
python3 -I -B \
  /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/t1_probe/probe2/analyze_probe2.py \
  /absolute/04a.JPG /absolute/08.JPG /absolute/04b.JPG \
  --out /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/t1_probe/probe2/local/tomorrow
```

省略 --out 时写入 `local/analysis/latest/`，也支持 `--out /tmp/t1p2/任意子目录`。路径边界比较前，两侧都会 resolve，因此 macOS 的 /tmp 与 /private/tmp 视为同一目录；越出这两个输出根仍会被拒绝。输出 `verdict.json`、`SUMMARY.txt` 和含逐块数据的 `patches.json`；同名目录复跑会更新结果。文件缓存按 JPEG/DNG 内容及提取代码哈希识别，不凭文件名复用。

几何和取样复用原 hue-ring 工具。ISO 200 模糊帧会触发原定位失败，因此把原标定的外边框定位脚本复制为 `calibration_geometry.py`。08 很亮时，彩块会挤掉全局角标候选；此时以本次第一张 04 的位置作种子，重新找四个角标、拟合边框，并检查 3/4/6/8 棋格身份。没有直接把 04 的几何原样套到 08，也不依赖 /tmp/cal_gpt/ 的旧文件。

分析器逐对读取 JPEG/DNG EXIF 与 MakerNote。M、ISO 200、手动 WB、selector=1，以及三帧的 t、f、ISO、WB/AsShotNeutral、display、raw13 一致性均为硬检查，JPEG/DNG 元数据也须一致。selector 是 MakerNote record[0x28] 的原生图像模式，不区分 04 和 08；手动 WB 的 record[0x26] 须为 5。快门和光圈须存在且为有限正值，偏离标定的 1/60 s、f/4 只会把警告写入 verdict.json 的 warnings 和 SUMMARY.txt，不会导致失败。三张都用 1/30 s、f/5.6 可通过元数据检查，只有一张改变则报错。灰块 RAW 曝光及各通道漂移超过 0.03 EV 仍视为异常。

08 帧的 144 个彩块和 9 个灰块各内缩 40 屏幕像素，统计任一 RGB 通道恰为 255 的像素比例，同一像素只计一次，两个白块不计入分母。超过 0.5% 时同样只在 warnings 与 SUMMARY.txt 中提醒，不改变功能判定；`clipping_255_08` 保存分母、总削顶数、各通道计数和比例。恰好 0.5% 不触发警告。

先计算 08−04a、04b−04a，保存全部 155 块。评分给九个灰块和 144 个彩块各一半权重，分别取 RGB RMS 后合并；两个白块保留预测及测量，不参加评分。预测用当次 04a 重新反解，避免把标定时的屏幕曝光硬套到新照片。

噪声参照取当次 04b−04a 的全块 RMS，最低 0.5 码。最佳残差须不超过 max(4 码, 4×噪声)，领先次选须至少 max(5 码, 4×噪声)。9 个灰块的 27 个通道值全部在 ±2 码内才算 04 返回。

- “功能通过 / functional_pass”要求独立映射假设满足拟合、领先、元数据、RAW 和返回检查，才报告完整通道映射。
- “未确认 / not_confirmed”用于无变化、广播 C/D、模型残差或领先不足。广播虽能识别响应，仍不足以确认三张表各自的通道。
- “异常 / abnormal”用于元数据、RAW 漂移、返回或图像读取/定位失败。最佳假设名和领先会在能够评分时保留。

“功能通过”仅指这组三帧的图像功能检查。关机重开和菜单 !4 需要另记人工观察。

## 测试证据和复跑

真实 1179/1180/1182 干跑结果为“未确认”，最佳为 no_effect，加权残差 3.37 码，领先次选 19.35 码；灰块返回最大差 1.06 码，元数据和 RAW 检查通过。没有把这组既有标定帧判成 probe2 功能通过。

每个假设用两张 04 的实测差构造保留通道相关性的噪声，随机重排并翻转符号，固定种子，每假设 20 次，共 420/420 正确。另将每个预测与同样噪声加入真实 04a 的图像色块，保留原图像纹理，写成 JPEG，复制对应 DNG，只在本次 local/ 内生成。21/21 组从图像定位、RAW 解码和元数据读取开始完整分析，全部恢复正确，最大最佳残差 1.44 码，最小领先 17.16 码。18 个独立映射给出“功能通过”，两个广播与无效果给出“未确认”。这都是合成输入验证。

真实 04a 原样作为中间帧的无变化测试给出 no_effect / 未确认。末张灰块人为偏移 8 码、元数据失败会阻止通过；11 个元数据反例覆盖 ISO、selector、单帧快门/光圈、WB record、AsShotNeutral、M 模式、WB EXIF、display 和 raw13。三帧共同改变快门和光圈仍保留功能通过，只输出警告；缺失曝光值仍报错。另测削顶恰好 0.5% 与超过阈值、单通道及多通道并集计数、白块排除，以及 /tmp 和 /private/tmp 别名及越界路径。原实拍干跑通过 /tmp/t1p2/ 输出路径重跑。记录在 `local/tests/`，公开汇总在 `test_metrics.json`、`verification.json`。

```sh
python3 -I -B research/t1_probe/probe2/build_validate.py
python3 -I -B research/t1_probe/probe2/model_probe2.py
python3 -I -B research/t1_probe/probe2/test_probe2.py --arrays --images --nochange
python3 -I -B research/t1_probe/probe2/write_report.py
python3 -I -B research/t1_probe/probe2/verify_delivery.py
```

主机源文件、模型、标定 JSON、原片和原始包的哈希核对见 verification.json。六个原片文件还与原标定 input_manifest.json 的哈希相符。共享检出有并行工作，未把整个仓库 Git 状态宣称为不变。公开文件不含 48 B 以上源表字节串或原始派生数组；完整曲线、entry、RPC/RAM、照片和逐块数组仅在已忽略 local/。本次仅写指定两个新输出目录和 /tmp/t1p2/，未访问其他 /Volumes 路径、相机或 SD 卡，没有 Git 提交。

## 明天拍摄

1. MacBook 显示原 hue-ring 图，按标定时的构图拍摄。M 档、ISO 200，以 1/60 s、f/4 为起点，屏幕亮度不同时可调整快门或光圈，但三张必须保持相同。先用全白屏设手动 WB，再显示色相环，三张期间保持曝光和 WB。
2. 按 04 → 08 → 04 各拍一组 RAW＋JPEG。每次选槽后关闭并重开菜单，确认光标确实停在选定槽，再关闭菜单拍摄。
3. 最后再选 04，关机、重新开机，打开菜单，检查没有 `!4`。记录这项人工观察。
4. 按拍摄顺序把三张 JPEG 及其同名 DNG 交给分析器。结果会同时报告最佳映射、领先和 04 是否全部回到 ±2 码。
