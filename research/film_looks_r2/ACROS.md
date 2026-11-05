# 富士官方 Acros：g157 数据交接

可以换进 g157 的既定兼容布局。三个单元均通过 reference exact、固定质量夹具、照片/场景门和 128/128 个输出量化分支。必须保持下述 flags=1 的 03 基础槽与 Tri-X 组合；不能直接放入原 g156 release 的 50mm flags=7 基础槽。

交接文件：[local/acros_official_handoff.json](local/acros_official_handoff.json)。它包含最终记录路径/SHA、flags、单元 mask、03/05 依赖及其 SHA、留出分数、每个量化分支和净字节。未生成 DAT，未触碰相机、SD 卡或网络，没有新候选实拍。

## 来源与固定口径

- 富士官方 GFX ETERNA 55 v1.10 包，`65Grid/F-Log2/FLog2_to_ACROS_65grid_V.1.00.cube`。沿用 `film_look_routes` 的 F-Log2/F-Gamut 输入与直接显示码比较，提升至已有的 65³ 原文件。
- ZIP SHA-256：`febfc7050999620651ca0cf162bf8b499970ef270b4da632765b61b958cf7940`。
- LUT SHA-256：`1e7b6c1b05924c5bdb9f2e922e962dcb608f2df15f38e628a9aac3a646293da4`。
- 输入为冻结场景 XYZ，转 F-Gamut/Rec.2020 后编码 F-Log2；目标不经过 04 影调。输出按此前富士研究的 BT.709 显示码约定直接比较。没有混用 F-Log2C/F-Gamut C。
- 三单元均用修正后的 native C040 与对应重建输入映射。50mm 沿用已验证逐值不变的输入；28mm/MOUNT 不读取 legacy50 映射。
- `look_ceiling_r1/local/target_14.json` 实际来自 Alchemy，并不是富士官方 LUT。本交接重新生成官方目标，没有把旧目标改名后沿用。

## 照片留出

下表全部针对同一官方 Acros 目标。Alchemy 列使用冻结 g157 release 建议布局中的旧 Acros 记录；28mm 已含此前 C040 重拟合的 Alchemy 版。百分比为 `100 × [1 − median ΔE00(记录,目标) / median ΔE00(04,目标)]`，D65；黑白的高百分比还应结合绝对余差判断。

| 单元 | ISO200 留出照片/点 | Alchemy 相似度 | 官方记录相似度 | 官方余差中位/P95 | 量化分支 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 50mm | 48 / 4,608 | 81.51% | 97.42% | 0.256 / 0.953 | 128/128 |
| 28mm | 189 / 18,144 | 84.39% | 98.26% | 0.200 / 0.981 | 128/128 |
| MOUNT | 67 / 6,432 | 78.99% | 96.23% | 0.375 / 0.835 | 128/128 |

MOUNT 另有 7 张独立 RAW 留出，余差 0.314/0.774，相似度 97.31%。50mm 其他 ISO 的余差为 0.217/1.126，MOUNT 为 0.398/2.032；非 ISO200 仍是既有模型的迁移诊断。28mm 的 189 张中有 181 张来自同一场次，不能当成 189 个独立光源。

相对冻结 release/test 两个布局各自的 Alchemy 记录，分别重跑了全部 128 分支，均为 128/128。门槛保留整数训练改善、主照片中位改善、P95 最多增加 0.25、MOUNT 逐照片中位相似度最多下降 0.1 pp、近零分母绝对门与整场景中位/P95 不回退。未用照片挑参数、改目标或挑量化相位。

## 最终记录与依赖

| 单元 | 记录 SHA-256 | bytes / flags / base slot |
| --- | --- | --- |
| 50mm | `141ad7c948d754508e84efb8fce6526acbc7f8f176005196b0601b089a4adac1` | 552 / 1 / 03 |
| 28mm | `48285540472797642ce68243fdb23295d6068d28bed84da13cc909be5684f162` | 552 / 1 / 03 |
| MOUNT | `3018cc4d0757965525c012b25ee484f9173e432019cbe40e29663ff73dba18c2` | 552 / 1 / 03 |

每条 Look flags 都等于相应 slot 05 的 flags=1。实际引用的 base 是 byte0 指向的 slot 03，也必须 flags=1。50mm/MOUNT 的已计划兼容 03 SHA 为 `76643d1fcd1748e99b55c476ade06b0493f4b834a3e673e0c29fc9bfccfb9ca8`；28mm release 稳健 03 SHA 为 `cdaf81df0edc2df237d5d2a36c89ebf9286ccb2148b4b8bdfd1893ccee355bcf`。test 对应 SHA 及 Tri-X 配对 SHA 均见 JSON。

依 `recipe_redo_r1/round2_replay.py` 的实际引用 base 规则，03/Tri-X 必须成组兼容。原始通用 assessment 正确地把 50mm 标为 `builtin_Look_flags_incompatible`，因为它查的是 g156 release；交接复核另查冻结的 g157 兼容布局，未删除或改写这条失败回执。若构建者改变 03 的 flags，本交接立即失效，不能只重写 Acros 的 flags。

记录使用共享曲线，type26 control=2；两半矩阵均将实际色度系数置零。评分执行普通 Standard 颜色链，未借用模型的 slot03 灰度捷径。

## 容量与复核

| 替换范围 | release 净增 B | test 净增 B |
| --- | ---: | ---: |
| 仅 50mm | 124 | 32 |
| 仅 28mm | 0 | 0 |
| 仅 MOUNT | 124 | 0 |
| 三单元一起 | 156 | 32 |

以 `model_c040_r1/local/layouts/{release,test}` 的 g157 计划为冻结基线，逐行重算去重池、旧行移除、跨单元描述符合并和 4 字节对齐。单项增量不能相加。552 B 是展开记录长度，表中才是净增量；未把 g157 正在变动的代码/BSS 预算算成已通过。

3 条记录均重建全部 552 B，CRC、字段域、Look 内容身份、ISO100 镜像一致。13 个 exact 起点全部收敛；迭代使用 fit_fast guarded_normal，exact 从原声明起点及 fast 候选/连续解复核，最终按整数训练损失和固定质量夹具选择。最终 62,163 点经独立字面曲线/矩阵/C080 重放，最大 RGB 差为 0，保存的留出分数重算一致。回执见 [local/acros_verification.json](local/acros_verification.json)。

资源回执纠正：首批调度重复加 nice，实际为 20。原产物和回执保留在 `local/history/nice20-first-run/`；随后按实际 nice=15 重跑全部拟合及量化评价，三个最终 SHA 与已交接版本逐条相同。数值批次仍在 load1≤10 时准入，数学库单线程；旧回执不计作最终资源合规证据。

复跑命令如下。批处理只补缺项；要独立重算应先使用新的输出目录，保留旧证据。

```sh
nice -n 15 studio/.venv/bin/python -I -B research/film_looks_r2/batch.py --max-workers 2
nice -n 15 studio/.venv/bin/python -I -B research/film_looks_r2/acros_handoff.py
```

官方 LUT 及派生记录仅留在 Git 忽略的 local/。本轮没有认定富士授予派生表公开再分发许可。结论仅覆盖研究记录和电脑留出；DAT 解包、引擎应用/恢复、LCD/JPEG、实际曝光及相机生命周期由 g157 构建/实机流程继续验收。
