# 收到午间照片后出配方误差报告

2026-11-04 的实际顺序使用逐帧 manifest，不使用下面的通用八组默认值。已核实该批有 74 张标准屏幕页、R8051974 一张额外非网格画面，以及 9 张笔记本前实体色卡照；没有真人皮肤、蓝物体、树叶或额外两张室内照片。正式结论见 [午间 r2 报告](REPORT_noon-20261104-r2.md)。

```sh
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/run_noon.py captures/noon-20261104 \
  --manifest research/noon_sweep_r1/local/noon-20261104-r2/intake-manifest.json --label noon-20261104-r2
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/local/noon-20261104-r2/finalize_r2.py
```

第一条命令完成取样与参考预测，OPEN 存在时返回 2；第二条独立重建最终参考输出、复核哈希、计算三 ROI 乘首/尾/插值参照的符号包络，并写只含统计的 r2 报告。正式映射及响应依据在 `local/noon-20261104-r2/intake-confirmed.json`。输入 manifest 不再被自动草稿覆盖。

把两批原始 DNG 和相机 JPEG 复制到同一个本地目录，保留文件名和拍摄顺序，等复制结束后运行。不要把 SD 卡挂载点作为输入。

```sh
nice -n 15 /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/.venv/bin/python -I -B \
  /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/noon_sweep_r1/run_noon.py \
  /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/captures/noon-20261104
```

脚本把统计报告写到 `research/noon_sweep_r1/REPORT_noon-20261104.md`，把逐块数值、输入哈希、ROI 叠图和 DAT 展开的记录写到忽略的 `local/noon-20261104/`。退出码 0 表示本次选择的检查通过；probe3 复跑只检查提取一致。退出码 2 表示已生成报告，但仍有缺帧、识别冲突、缺漂移参照或未跑预测。先看报告中的 OPEN，再引用配方统计。

也可直接运行 `research/noon_sweep_r1/run_noon.py <照片目录>`。脚本使用仓库现有 Python，强制 `-I`，自动把 nice 提到 15，数值库只用一个线程。本任务不安装依赖、不联网、不访问相机或其它挂载卷，不 commit 或 push。一次只允许一个 noon 任务，重复运行会复用按输入与代码哈希绑定的提取缓存。

## 核对分组

通用计划默认每 8 张一组，页面顺序为 T1、T2、T3、T4、V1、V2、V3、V4。设置依次为 04 Std、05 F-CC、06 F-CN、M9 STD、HNCS HiCon、Kodachrome25、HNCS LowSat、Vision3 500T。第 64 张之后识别出的额外屏幕页默认是尾 04。这个默认值只描述原计划，不能用于 11 月 4 日实际批次。

实物单独计数，前 8 张按相同设置顺序，第 9 张是日光尾 04，第 10、11 张是室内 04。屏幕与实物也可以分开放在两个目录，各运行一次。目录默认不递归，避免把叠图、缩略图和重复导出件算作新照片；确需遍历子目录时加 `--recursive`。

脚本逐帧找网格，并结合页角文字与色块排列识页。屏幕颜色代码只用于识别页面，不作为参考色值。每条配方的多个色块响应另做校验；报告分别写顺序默认、响应最佳、余量和冲突。unknown 不是已确认设置。冲突不会被重新贴标签后混入“通过”统计。

如果某帧提取失败，脚本保留其它帧的明细，但暂停受影响批次中依赖自动顺序的统计。实物补框失败不阻断已经完整的屏幕批次。用生成的 `local/<批次>/intake-manifest.json` 核对逐帧设置，补上未知页码或四角，再重跑。该文件是草稿，只有你核对后才能去掉 `manual_confirmation_required`。

## 补实物与疑难屏幕区域

离线打开 [roi_editor.html](roi_editor.html)，选择原始 JPEG。逐张点色卡的左上、右上、右下、左下四角，再拖框选皮肤、蓝物、绿叶。选好设置与场景，导出 JSON 到 `research/noon_sweep_r1/local/noon-manifest.json`。

```sh
nice -n 15 /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/.venv/bin/python -I -B \
  /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/noon_sweep_r1/run_noon.py \
  /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/captures/noon-20261104 \
  --manifest /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/noon_sweep_r1/local/noon-manifest.json
```

色卡自动定位按 6 列、4 行寻找平面网格，支持不足 80% 时要求四角。自动找到后仍要看 `local/<批次>/overlays/`，确认 24 个框确实落在同一块卡上。它不读取山寨卡的印刷参考值。

小色卡使用单独的取样门：中央区域至少 128 像素，每个 CFA 颜色至少 32 样本，4×4 子区域的 CFA 均不能空。原屏幕取样器的大于 300 像素门保持。样本数会写入逐块明细，不能把像素数当成独立重复次数。

机位相同时可以保存共享框模板。机位移动时，每帧单独找色卡四角，并选“用每帧色卡四角跟踪共享框”。色卡与人不在同一平面、人物移动或叶片晃动时，逐帧重框；平面变换不能证明身体区域始终一致。

屏幕定位失败时也能在编辑器补四角和页码。四角对应由色块中心外推的完整网格边界，最外色块边缘外约半个 gutter。所有坐标为原图的 0 到 1 比例，顺序为 TL、TR、BR、BL。压缩 DNG、旋转 Orientation、DNG 与 JPEG 裁切不一致会报告 OPEN，不自动猜测 CFA 或翻转方向。

## 看误差与漂移

报告按配方、页面列 DE00 中位数、P95、最差块和明度、彩度、色相偏差。肤色、蓝色、绿叶单列。主测取中央 40%，另算 30% 和 50%，并比较首、尾 04 两种输入校正分支。详细数据在 `patches.csv`、`all-patches.json`、逐帧 `comparisons/` 与 `summary.json`。

预测直接绑定 `firmware/package_v310_g156_test/GXRCE.DAT`，SHA-256 为 `0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7`。脚本展开实际 MOUNT 的 9 条记录，包含原生 03 HC BW。最终 RGB 使用冻结的 `Model.predict(..., quantize=False)` Python 参考路径，03 明确丢弃色度，没有重新拟合或改记录。记录和模型输入的哈希在 `model-provenance.json`。

04 的 JPEG 通过参考模型反演成条件输入，再逐块、逐通道按 RAW_WB 比值校正配方帧的输入。参考端在首、尾 04 之间按 EXIF 时间插值，04 自身只用另一个独立 04 检查。1/15 与 1/20 的输入变化会进入 RAW 比值，不把曝光变化当成配方响应。非 ISO200、滑杆上下文不符、RAW 截断或 04 反演不可用的块会排除并留明细。

DE00 使用 sRGB 经 Bradford 转到 D50 的 Lab，沿用 `analyze_pairs.py` 的颜色约定。RAW 的 YCbCr 是线性传感器代理，不能和 JPEG 直接解释为真实颜色误差。JPEG 同时保留原生 YCbCr 与从 RGB 复算的 BT.601，原生色度相对基线的偏移保留在预测比较中。

肤色 Cb、蓝色 Cr 会比较完整配方相对 04 的实测与预测方向。符号结论带三 ROI 和独立 04 的漂移包络，并留 0.25 输出码的诊断余量。缺独立参照时，预算写“未测”，不会填 0；设置冲突与单侧参照的方向反号也单独标成条件结果。完整配方含多个同时变化的字段，反号只能说明这一颜色响应仍有缺口，不能单独证明 probe3 的某个 R±、B± 节点机制。

## 保留这些 OPEN

- 原定屏幕 64 张只有开头 04。若没有额外尾 04，脚本仍给 RAW 条件误差，但无法检查这批的首尾漂移。若拍摄安排允许，末尾再用 04 补拍 T1 到 V4，才能给每页独立参照；只有 T1、T3 尾参照时，其余页仍是单侧参照。
- 首尾差与三 ROI 是敏感性包络，不是中间漂移的真实上界或统计置信区间。
- 既有屏幕摩尔纹处理继续使用中央 ROI、三种大小和逐块 RAW；报告列既有频谱门的诊断数。脚本不靠 CSS Lab 校准 P3-D65 屏幕，也不补偿未知局部调光或屏幕视角光谱变化。
- MOUNT 模型仍从 50mm 模型迁移。电脑预测和合成批次通过不等于 g156 相机实拍通过。照片也不能证明机身版本或卡上 DAT 哈希。
- 本批九张实体照片只有卡片，没有真人皮肤、蓝物体或树叶。r2 完成卡片测量，这三类真实物体明确记未测；不以印刷色块替代。响应余量不足时保留 unknown 和组内证据。

验证结果与重跑命令见 [VALIDATION.md](VALIDATION.md)。
