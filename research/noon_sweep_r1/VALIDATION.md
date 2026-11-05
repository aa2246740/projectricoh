# 午间流程验证

下面保存午间收片前的软件流程验证，不能作为修改后源码的最终验收。实际午间收片、原生 03 和小色卡取样修复见 [r2 实拍报告](REPORT_noon-20261104-r2.md)。本批有九张实体卡照，没有真人皮肤、蓝物体和树叶。

午间前版本的 [验收回执](local/final-acceptance.json) 为 PASS，绑定当时源码、实际 g156 test DAT 和模型输入。复核脚本在 [local/final_acceptance.py](local/final_acceptance.py)，冻结副本的位置写在回执中。r2 使用独立的 `local/noon-20261104-r2/reference-audit.json` 和 `r2-completion.json`，不沿用这个旧 PASS。

r2 的数值回归已重跑：九条 MOUNT 记录的参考链 RGB 逐值相等，故意把 05 组一帧替成 06 仍报告设置冲突。新增小区域夹具确认屏幕旧门拒绝 15×15 ROI，实体门保留预期 CFA 均值并拒绝样本不足区域；两种取样器在大 ROI 上的 RGB、原生 YCbCr、RAW_WB 和多边形逐值一致。日志在 `local/noon-20261104-r2/verify-numeric-r2.log`。

| 验证层 | 输入与结果 | 证据 |
| --- | --- | --- |
| 真实 MOUNT ramp 提取 | probe3 八对原片重新定位，每帧 52 块；50% ROI 的 JPEG RGB、原生 YCbCr、RAW_WB 与既有明细逐值相等，最大差 0。新增 40% 主测及 30% 分支也有明细。 | [提取报告](REPORT_probe3-validation.md)、[逐值回执](local/probe3-validation/probe3-rerun.json) |
| 真实旧屏幕页 | 六对 50mm 原片识别为 T1、T1、T1、T2、T3、T4，与既有人工标签一致。288 个中央 40% ROI 均在既有逐块边界内，最小边距 99.7 原图像素。 | [提取报告](REPORT_historic-screen.md)、[区域包含检查](local/historic-screen/roi-containment.json) |
| 屏幕合成渲染 | T1 到 V4 八页均识别正确，每页 48 块。离线使用固定 Playwright 1.61.1、Chromium Headless Shell 1228。 | [渲染记录](local/synthetic-pages/render.json) |
| 透视与噪声 | 八页各自改变透视、位置、模糊、通道增益并加噪声。八页均识别正确，48 块中心相对生成几何的最大误差 1.093 像素，测试图为 1800×1200。 | [几何回执](local/verify-geometry/receipt.json) |
| 指定旧目录盘点 | g150 的 16 对、两批旧 ramp 各 8 对，共 32 对，没有可用的 T1 到 V4 页。灰阶 ramp 不再被当作 V1。showcase 目录没有成对相机原片。 | [盘点回执](local/verify-inventory/receipt.json) |
| 参考模型数值链 | 72 帧屏幕数组加 11 帧实物数组，共 11,259 条三 ROI 记录；除故意错配帧外，DE00 最大约 2×10⁻¹²。故意把 05 默认组中的一帧设成 06，响应校验报告冲突。 | [数值回执](local/verify-numeric/receipt.json)、[合成报告](REPORT_verify-numeric.md) |
| 实际文件入口 | 用独立 TIFF 写入器生成 83 对本地 DNG、JPEG，包含尾 04、24 块卡和三个手动区域。命令实际完成配对、哈希、RAW 解码、识页、取样、参考预测和 Markdown、JSON、CSV 输出。83 帧均提取成功，生成 73 组分页统计与 14 组配方合计，唯一 OPEN 是预埋的设置冲突。 | [文件批次报告](REPORT_binary-intake.md)、[运行完成回执](local/binary-intake/completion.json) |
| 最终版本按实际计划运行 | 去掉八张屏幕尾 04，保留 64 张屏幕和 11 张实物。最终命令成功处理 75 对文件，产出 8,955 条 ROI 明细、65 组分页与场景统计、14 组配方合计。缺尾 04 与预埋冲突均保留 OPEN，开头八张 04 的响应为 unknown。 | [75 对报告](REPORT_planned75-manual.md)、[最终完成回执](local/planned75-manual/completion.json) |
| 不补手动框的入口 | 同一 75 对文件不传 manifest，自动找到了每帧 24 块卡，同时对 11 帧分别报告缺皮肤、蓝物、绿叶框。屏幕统计仍正常输出，没有拿卡片区域冒充真人或树叶。 | [自动入口报告](REPORT_planned75-intake.md) |
| 离线人工框选 | 固定浏览器测试了四角、皮肤拖框、换照片、设置选择、共享模板、色卡跟踪开关与 JSON 导出。 | [编辑器回执](local/verify-roi-editor/receipt.json) |

真实旧屏幕的几何误差不能用合成图的 1.093 像素代替。相对旧版逐块拟合，本次全页单应矩阵的中心差 P95 为 12.8 至 15.7 原图像素，最大 23.5 像素；上表的包含检查确认中央取样仍有足够边距。详见 [中心差检查](local/historic-screen/geometry-comparison.json)。

合成文件使用 1600×1000 像素，JPEG 为有损编码，12 位 RAW 也经过量化。83 对样例中普通帧误差中位数约 0.49、P95 约 1.37，表示这个合成编解码闭环的残差，不是相机配方误差。有首尾 04 的 83 对入口测试耗时 263.87 秒；最终版本按 75 对实际计划运行耗时 167.88 秒，均包含解码、计算和报告写入。这台 Mac 当时有其它任务，真实 12MP 批次加人工补框尚未计时，不能把这里的耗时当成实拍交付保证。精确耗时见完成回执。

## 重跑验证

从仓库根依次运行。每个 Python 命令均使用现有环境、`-I -B`、nice 15；任务锁避免同时运行两个 noon 分析。

```sh
nice -n 15 node research/noon_sweep_r1/render_synthetic.mjs
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/verify_noon.py geometry
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/verify_noon.py inventory
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/run_noon.py captures/probe3-field-20261104 --label probe3-validation
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/run_noon.py captures/a12-50/2026-10-16/macbook-screen-chart --kind screen --extract-only --label historic-screen
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/verify_noon.py numeric
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/make_intake_fixture.py
nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/run_noon.py research/noon_sweep_r1/local/intake-fixture --manifest research/noon_sweep_r1/local/intake-fixture-manifest.json --label binary-intake
nice -n 15 node research/noon_sweep_r1/verify_roi_editor.mjs
```

`--extract-only` 返回 2，表示有意只验证取样。合成文件入口也返回 2，因为预埋冲突必须保留为 OPEN，不能改成 PASS。`verify_noon.py numeric` 另有断言确认这个冲突被正确识别。

## 收片后仍需闭合

- 计划中的 64 张屏幕照片缺尾 04。没有额外同页 04 时，报告保留单侧 RAW 条件误差，不能关闭首尾漂移。
- 自动卡网格要看叠图确认；皮肤、蓝物、绿叶要框选。色卡跟踪只提供平面配准，人物或叶片移动需单独重框。
- 完整配方的肤色 Cb、蓝色 Cr 方向检查不等于隔离了 probe3 单通道扰动机制。弱分量、ROI 不一致或缺漂移控制时保持未判。
- 相机、SD 卡、网络、依赖安装和固件修改均不属于本任务。本次没有验证新 g156 的实际机身颜色，也没有 commit 或 push。
