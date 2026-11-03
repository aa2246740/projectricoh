# 实拍测量与回拟工具

工具已经跑通，明天可直接读成对 DNG/JPEG。13 张旧实拍、10 项行为测试，以及 2 张由模型生成的合成 DNG/JPEG 完整流程均通过各自检查。还没有 v4r2 六槽的新实拍，不能宣称达到原机 95% 相似度。

本轮只写 `research/closed_loop/`，另创建了 `/tmp/closedloop/`。没有接触相机、SD 卡或其他卷，没有 Git 提交。写入前核对了可写 APFS、指定 UUID，并运行 `df -h /Volumes/Workspace`。

## 明天怎么用

先按 [拍摄清单](SHOOT_LIST.md) 拍摄。每组所有槽位的曝光必须完全相同。色环图在 `research/hue_ring/hue_ring.png`，实体卡保持 DIOPTIX 标志朝左上。

把已经复制到电脑的照片成对放入本目录的 `local/incoming/`，或修改 [帧清单示例](frames.example.json) 中的路径。路径相对仓库根目录解释，JPEG 旁必须有同名 DNG。示例中的 `screen/04.JPG` 对应相邻 `screen/04.DNG`，其他槽位同理。也可以在 `local/` 自建清单，保留原始文件名。

在仓库根目录运行：

```sh
python3 -I -B research/closed_loop/bootstrap.py
python3 -I -B research/closed_loop/measure.py research/closed_loop/frames.example.json --out research/closed_loop/local/tomorrow_measurement.json
python3 -I -B research/closed_loop/refit.py research/closed_loop/local/tomorrow_measurement.json --out research/closed_loop/local/tomorrow_candidates
```

`bootstrap.py` 只把现有辅助代码复制到自己的 `local/vendor/`。示例清单绑定的 v4r2-noprobe DAT SHA-256 为：

```text
7f951a4dc5193dd6c5d00173f0016ab8804f33675c330a50c74b76fbdef4c4dd
```

测量生成 JSON、中文 Markdown、目标误差色相图、模型误差色相图，以及各槽位的“色相 × 明度”模型误差图。JSON 保存每个色块的来源、目标、实测值、预测值、排除原因和起止输入哈希。无效拍摄仍有诊断报告，命令退出码为 2；输入或计算失败退出码为 1。回拟拒绝不合格拍摄。单槽的数据不足或整数修复失败，会保存拒绝原因并继续其他槽。

## 目标如何得到

实测目标链不调用 Nominal04。Fuji ceiling 报告中，Nominal04 在原 24 块色卡上的重建中位误差为 2.822 ΔE00，因此不能把它当实拍真值。

每张照片都从自己的 DNG 取 CFA 色块均值，扣黑电平、除白电平，再用该张 AsShotNeutral 得到线性白平衡输入。JPEG 与 DNG 使用对应区域，并检查配准。环图复用四角定位及失焦边框定位；实体卡复用原 2e 点阵定位与朝向检查。

- 05/06 沿用真实色卡目标的 DNG 场景色度链：DNG 双光源矩阵、D65 适应、冻结的中灰锚、F-Log2、官方 LUT 四面体插值和 passthrough 输出。组内共用 04 定下的场景比例，每张的颜色和亮度仍来自自己的 DNG。官方 zip 从 `artifacts/downloads/fuji-luts/` 读取，并核对其 SHA256SUMS。
- 01/02 沿用各 fit 文件夹的真实色卡相对目标。先反算同组实测 04，再按“本张 DNG / 04 DNG”的逐块、逐通道响应调整输入，得到本张对应的 04 颜色。实体卡应用该标签的 GR III 相对 Lab 变化；色环应用原来的色相插值。两槽在冻结的 24 块输入上均与原目标逐值一致。这里没有经过 Nominal04，也没有把 GR 测光锚未知的问题当作已解决。
- 03 沿用 round 2 的两张 GR IV 高反差黑白照片、平坦块筛选与相机颜色映射。601,340 个参考块确定性抽稀为 150,335 个，在对数线性 RGB 中用 32 个近邻插值目标亮度。最近参考点距离大于 0.5 的色块排除。它是有适用范围的照片参考插值，不是完整 GR IV 渲染器。

GR 结果始终列出 −0.3、0、+0.3 EV 三行。敏感度计算把本张及其 04 基准的线性输入乘以 `2**EV`，实际 JPEG 不变；同时报告目标位移、模型预测位移和各自误差。默认和回拟均固定用 0 EV，不选择最好看的行。这是条件敏感度，不是置信区间。

## 两种误差分别报告

“实测相机到目标”使用 JPEG 色块和该张 DNG 算出的目标。“实测相机到模型”使用相同 JPEG 和清单指定 DAT 的 v2 预测。两者都有 ΔE00 中位、p90、最大值及小于 1、2、3 的比例，并分别按色相统计。模型误差另按明度和“色相 × 明度”统计。色相来自该张 DNG 的 D65 XYZ，明度采用 DNG 驱动的同组 04 等效 L*；灰块不分配色相。

请求中的 similarity 保留原公式：

```text
1 − median(实测槽位到目标) / median(同组 04 到相应目标)
```

两项使用同一批有效标签，04 的目标也由 04 自己的 DNG 计算。分母小于 0.25 ΔE00 时返回“不定义”，负数照实保留。这个数是相对 04 的误差缩减率，不能直接当作原机风格相似百分比。过曝、摩尔纹、纹理污染、反算超出支持范围等色块会单列排除；报告也保留包含这些色块的统计。

04 自身的模型误差受“先反算 04”的条件限制，接近零不构成独立模型验证。07/08 只在诊断清单中允许，不能当作六槽风格目标。

## 回拟如何修正模型

回拟的主要修正信号是实测 JPEG 与现用 DAT 预测的差，而不是继续拟合旧的预测数字：

```text
偏差 r(x) = 实测 JPEG(x) − 模型(现用表, x)
候选输出估计 = 模型(候选表, x) + r(x)
```

偏差在每个实测输入处固定，v2 链的 Jacobian 给出改 Y 行、扇区后输出如何变化。用完整 RGB 偏差保留明度及两个色度方向，再通过 ΔE00 残差拟合目标。这个局部近似比仅按色相平均偏差保留更多信息；改表后的真实响应仍需下一轮拍摄验证。

曲线、分色行和偏移固定；01/02/05/06 拟合 Y 行和 24 个扇区的尺度、旋转；03 只改 Y 行。Y 行和保持 1024，row 2 按原规则推导。扇区使用原符号幅值编码、镜像字节和 ±127 范围；矩阵交给原加载器检查并完成编码往返。03 保持 round 2 的 Y 系数域。优化有平滑、偏离现表的正则和有限步长。

整数舍入后重新检查并有限修复扇区。候选还要通过 ISO 200/1600 的密集扫描、最低尺度、色相导数、色度对数斜率、完整 RGB 截断、灰轴保护，以及训练和留出色块的中位/p90 门槛。有两种图时只用色环训练、整张实体卡留出；只有一种图时按完整色相分箱留出。留出结果仍是带实测偏差的候选投影，不是新表实拍。

输出只在 `local/`，不生成 DAT。每份候选始终有 `accepted=false`、`firmware_ready=false`、`deployable=false`。`review_gate_passed` 只表示本轮数值门槛是否通过。

## 新 GR 目标接口

测量同时输出 `*_target_requests.json`，包含每张及其 04 基准对应的目标请求、槽位、标签、DNG 哈希、线性白平衡输入、桥接输入、DNG XYZ，以及需要的 EV 三行。新生成器可以直接消费这些实测输入，不需要生成 Nominal04 图片。

回填文件仅放 `local/`，结构如下；示例数值是接口占位，不是照片或固件派生数组：

```json
{
  "schema": "closedloop-targets/1",
  "frames": {
    "screen01:01": {
      "slot": "01",
      "dng_sha256": "填写请求中的完整哈希",
      "labels": ["填写请求中的色块标签"],
      "lab": [[50, 0, 0]],
      "anchor_lab": {"-0.3": [[46, 0, 0]], "+0.3": [[54, 0, 0]]},
      "source": "生成器名称、版本与输入来源",
      "reference_grade": "surrogate"
    }
  }
}
```

还必须回填请求中的 `screen04:01` 等基准条目；所有标签和行数必须一致。使用 `--targets research/closed_loop/local/new_targets.json` 重测。缺少基准、EV 行，或 DNG 哈希不符会失败，不会用旧目标补齐。默认 01/02 照片目标保持原样，尚未接入另一工作者的 round 5 生成器。

## 实际验证结果

环图 R8051179–1182 共 620 个色块全部提取，元数据检查通过。07/08 与所选 DAT 模型的中位误差为 0.110 / 0.133 ΔE00。这组曾用于模型校准，且拍摄表不是明天的完整 v4r2 六槽，因此只用于诊断工具和数据路径。

2e 的 9 张图共 216 个色块全部提取。按原分析确认的实际身份标注：R8051153 为 03，1154 为 02，1155 为 01。ISO 500、自动白平衡及变化的 AsShotNeutral 被准确识别，整组禁止回拟。它与当前 DAT 的比较也不能作为 v4r2 模型验收。逐槽结果和 GR 三行敏感度在 [2e 诊断](local/dry_2e_measurement.md)，环图结果在 [环图诊断](local/dry_ring_measurement.md)。

10 项行为测试全部通过，覆盖 ΔE00 参考值、阈值比例、拍摄条件拒绝、缺失基准、路径边界、目标哈希绑定、冻结目标一致性、Jacobian、03 灰度及自身 DNG 依赖。测试把 Nominal04 替换为抛错函数，四个彩色槽位的实测目标仍正常生成。Jacobian 方向导数相对误差为 `1.83e-10`，官方 LUT 重放冻结色卡的最大 RGB 码误差小于 `1e-12`。

合成测试注入已知 Y 行和扇区误差。连续解恢复相反的 Y 改变量；整数编码和安全修复后，再用带注入误差的合成相机重新出图。398 个彩色输入的 ΔE00 中位从 0.438 降到 0.110，p90 从 0.867 降到 0.283，误差缩减 74.9%。这证明本次注入条件下修正方向和整数流程有效，不是原机 95% 验收。

另生成 2 张带元数据的完整合成 DNG/JPEG，逐张经过真实测量入口和回拟入口。每张提取 24 块，提色值与已保存 JPEG 的平坦像素一致，模型误差被测出。演示候选的完整 RGB 门槛没有全过，因此 `review_gate_passed=false`，没有把它当作可用配方。

```sh
python3 -I -B research/closed_loop/tests/dry_run.py ring
python3 -I -B research/closed_loop/tests/dry_run.py 2e
python3 -I -B research/closed_loop/tests/test_closed_loop.py
python3 -I -B research/closed_loop/tests/synthetic_capture.py
```

## 文件与校验

主入口为 [measure.py](measure.py) 和 [refit.py](refit.py)，辅助实现为 `common.py`、`model.py`、`targets.py`，复制器为 `bootstrap.py`。公开文件的校验和在 [SHA256SUMS](SHA256SUMS)，全部本地派生数据的校验和在 [local/SHA256SUMS](local/SHA256SUMS)。所有 LUT、照片、固件派生数组、图片和候选都在已验证 Git 忽略的 `local/`。

```sh
python3 -I -B research/closed_loop/verify_delivery.py
```

该命令检查公开文件语法、两份校验和、忽略规则、Git 索引和只读输入保全。环境版本及完整验证记录在 `local/delivery_verification.json`。明天需要补齐的证据是两组、六槽、同组曝光与手动白平衡一致的新 DNG/JPEG，以及候选表改动后的第二轮实拍。
