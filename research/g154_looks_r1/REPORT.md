可以交复审，结论限电脑构建与验证，尚未上卡或相机试用。
保留原 10 个 Looks，追加 Agfa LeBox、Y2K Plady、QianXi A、QianXi B、ARRI Classic709、Eterna BB、RED IPP2、Acros，8 个目标全部放入。
共 18 个 Looks，另有 8 个内置配方、3 个用户条目和 1 个提示行，共 30 个逻辑行；所有视图仍为 8 个物理行，每行最多 13 个字符。
主请求 103,644 B，余 3,968 B；DAT 86,736 B，余 11,568 B；代码 64,728 B，余 808 B。
代数沿用 154，机身绑定保持 v3.9 `8233a1c4…`；当前工作室编解码器可直接读取并逐字节往返，不需要登记新代数。

## 交付物与身份

测试包为 [package_v39_g154_looks18_test](../../firmware/package_v39_g154_looks18_test/MANIFEST.json)，DAT 为 `local/SD_ROOT/GXRCE.DAT`，SHA-256 为 `5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681`。
包中 29 个升级文件逐字节等于现用 [g154 测试包](../../firmware/package_v39_g154_test/MANIFEST.json)，本轮仅由机主在复审后更换 DAT，不需要刷机。

| 身份 | 值 |
| --- | --- |
| ilaunch3 SHA-256 | `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d` |
| resident build | `785706aa2323d8f1c313e37c4eab94fdd2899c2f66d40e3dda9d505f32235f81` |
| resident ABI | `dd55f5b9c81d35bd9f520b9449a6c463` |
| 恢复用 g154 测试 DAT | `ac4263a0083aff1f04ab1433029b7ba354d67083ad09292f2af49bbc59abb83e` |

源目录为 `firmware/engine_v65_g154_looks/`。原 `engine_v63_g154/`、`engine_v64_g155/`、官方固件与原包均未改动。含完整条目、DAT 或原厂底子数据的新增持久文件只在 `artifacts/downloads/g154-looks-r1/` 或新包的 `local/` 内。指定 Scratch 及误选旧驱动创建的本轮临时目录均已清理，后文保留该路径例外与清理回执。未访问存储卡，未做 Git 写操作，未开子代理。

新增素材与派生参数仅供机主自己的相机使用。LUT 版权属于原作者，本轮没有把本地自用范围扩大为公开分发授权。原包的署名与许可说明随包保留。

## 数据布局与源码差异

生产源码相对 g154 只改两处 Python 文件，见 [source.diff](evidence/source.diff)。`candidate/build154.py` 转到本轮构建脚本；`containers/product/looks_data.py` 改输入路径、`CAPACITY=18` 和 `CAPS=(0,18,16,18)`。`ui_data.py`、所有 C 文件、resident 和 engine_services 源码均与 g154 相同。运行时本来就按 GXFX 头部读取数量和行池容量，因此无需改引擎逻辑或机身身份。

原 10 项只用了 `0/10/9/10` 行，旧预留是 `8/28/32/32`。按实际去重行数收紧后，原 10 项 GXFX 从 6,636 B 减到 2,108 B，回收 4,528 B 空白；新增 8 项占 1,640 B，18 项 GXFX 合计 3,748 B。DAT 比现用 g154 少 2,888 B。全部目标已容纳，无需删除既有 Look。

逐项增加的字节包含 32 B 描述符、独有行和四字节对齐；以下是在收紧行池后的累计值。[data-budget.json](evidence/data-budget.json) 同时保存各项移除时的理论释放量，未实际删除任何条目。

| 新增项 | 累计 Looks | 该项新增 B | DAT B | 主请求 B |
| --- | ---: | ---: | ---: | ---: |
| Agfa LeBox | 11 | 216 | 85,312 | 102,220 |
| Y2K Plady | 12 | 216 | 85,528 | 102,436 |
| QianXi A | 13 | 220 | 85,748 | 102,656 |
| QianXi B | 14 | 216 | 85,964 | 102,872 |
| ARRI 709 | 15 | 216 | 86,180 | 103,088 |
| Eterna BB | 16 | 216 | 86,396 | 103,304 |
| RED IPP2 | 17 | 220 | 86,616 | 103,524 |
| Acros | 18 | 120 | 86,736 | 103,644 |

DAT 长度变化还要求重新链接 BSS。构建先用原对象与旧长度重放，代码和重定位表逐字节等于 g154，再以 `BSS_START=86736` 链接同一批对象。代码长度仍为 64,728 B，实际改变 578 个字节，全部属于 289 处 `R_M32R_GOTOFF_SLO` 的 BSS 地址立即数；其余代码字节不变。BSS 为 9,280 B，范围为 `[86736, 96016)`，所有 BSS 符号均在分配范围内。平移到 `0x21004000` 的链接核对通过。完整对象哈希、链接命令和地址差异见 [relink.json](evidence/relink.json)。

| 项 | 实测 B | 上限 B | 余量 B |
| --- | ---: | ---: | ---: |
| 主请求 | 103,644 | 107,612 | 3,968 |
| DAT | 86,736 | 98,304 | 11,568 |
| 代码 | 64,728 | 65,536 | 808 |

链接值的计算为 `7628 + align4(86736 + 9280) = 103644 B`。另在三个单元的真实 resident M32R 装载路径记录 `rv_native_alloc` 参数、root 中的主请求、DAT 和代码尺寸，结果相同，见 [runtime-sizes.json](evidence/runtime-sizes.json)。堆和单元响应仍为主机模型，这不构成真实相机堆验收。

## 新 Looks 的预测相似度

以下数字摘自 [vlog_alchemy_eval/REPORT.md](../vlog_alchemy_eval/REPORT.md) 及其排序数据，未重新拟合。全部为“电脑预测，28mm/MOUNT 未独立标定”。相似度是相对原厂 04 的误差缩减，不是绝对色彩准确率；50mm 使用 ISO200 模型，28mm 没有独立实拍留出集。原有报告中的输入空间假设、灰轴偏色和可达色环未定项仍然适用，本轮只验证参数接入与执行。

| 新 Look | 50mm 合成 | 28mm 迁移合成 | MOUNT 迁移合成 | 50mm 照片 | MOUNT 照片 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Agfa LeBox | 72.40% | 68.97% | 68.11% | 78.40% | 60.13% |
| Y2K Plady | 52.65% | 43.67% | 36.19% | 75.45% | 71.19% |
| 千禧回声 A，列表名 QianXi A | 61.99% | 60.25% | 55.58% | 42.19% | 49.58% |
| 千禧回声 B，列表名 QianXi B | 60.06% | 58.39% | 53.31% | 42.16% | 48.87% |
| ARRI Classic709，列表名 ARRI 709 | 93.60% | 93.60% | 93.60% | 94.90% | 91.62% |
| Eterna BB | 90.15% | 90.30% | 90.30% | 89.81% | 87.07% |
| RED IPP2 | 91.04% | 91.12% | 91.05% | 91.20% | 83.97% |
| Acros | 96.12% | 96.12% | 96.13% | 94.53% | 96.32% |

`ARRI 709` 沿用评估输入的短名称，对应 ARRI Classic709。所有新增项的单元掩码均为 7，名称最多 12 个 ASCII 字符，含状态标记后最多 13 个字符。输入文件中的基础配方身份字段在封装时换为 GXFX 内容 CRC；颜色行、T、标志及其余字节保持原拟合值。

## 与改动相关的验证

使用 g154 的驱动与断言，扩到 18 项，并把测试行数、用户行起点和 49 行边界相应展开，见 [check-retarget.diff](evidence/check-retarget.diff)。没有改 `tools/gxr_emulator*`。最终所选作业串行，机器码使用 `GXR_HARNESS_BACKEND=c`，nice=10，每组超时 10,800 秒，超过所复用历史组耗时的三倍。

最终 [data-checks.json](evidence/data-checks.json) 记录原 g154 主机 C 查询、结构校验和数学代码的结果：三个单元各 8 个内置、18 个 Looks、3 个用户条目，共 87 份完整 552 B 输出。新 Looks 按最终 GXFX 内容身份核对全部 552 B，包含九段行、T、ISO100 行、CRC 与保留字节；没有只比较请求参数。原 10 个 Looks 在三单元的 30 份输出、8 个内置的 24 份输出和 3 个用户条目的 9 份输出均与原 g154 完全一致。完整二进制保存在新包的 `local/evidence/`。

结构检查接受最终 DAT 的三个单元，并拒绝 33 项结构、CRC 或字段损坏。正式 C 窗口函数覆盖 1–49 个逻辑行、每个游标及 50 个先前窗口位置，共 61,250 项；50 行请求拒收。

| 单元 | 原生列表导航 | 微调及返回原行 | 用户数量边界 |
| --- | --- | ---: | ---: |
| 50mm | 59 帧及双端循环 | 20 项 | 6 项 |
| 28mm | 59 帧及双端循环 | 20 项 | 6 项 |
| mount | 59 帧及双端循环 | 20 项 | 6 项 |

原生导航正反走过全部 30 行，检查实际单元行和 engine live 的完整 552 B，并检查两个方向的首尾循环。微调组覆盖全部 18 个 Looks、一个内置项和一个用户项，逐次比较默认与修改后的完整输出，检查卡片、参数和值页以及返回原列表行。每次发布都断言 8 个物理行，所有可见文字最多 13 字符。

用户格式容量仍为 32，运行时上限按 `min(32, 40-K)`。本包三单元均有 K=18，因此上限为 22；测试包保留原 3 项及整个 1,984 B GXUI 扩展，全部 11,296 B 第七段也与原 g154 相同。三个单元都验证 22/18 的 49 行接收、23/18 与 32/18 拒收；拒收后保持原厂 7 行、完整 S 和单元数据不变，单元写入为零。另保留 32/8、32/0、0/0 对照。

机身身份组覆盖最终测试与零用户 DAT 的匹配装载、旧机身和旧 DAT 的拒收、代数标记不符，以及原有匹配控制，详见 [identity-c.json](evidence/identity-c.json)。工作室编解码器 SHA-256 为 `73cc7b04f57c89b53575bb12f0b36aaaa88289eaae69e505259fc8826cb86aef`，实测 `parse` 得到 18 个 Looks 与 3 个用户条目，`pack(parse(raw)) == raw`，全部展开行一致。该结论限编解码 API，本轮未改 `studio/`，未测试工作室 UI。

| 最终作业 | 秒 | 结果 |
| --- | ---: | --- |
| [accepted-data-c](evidence/job-accepted-data-c.json) | 2.7 | PASS |
| [final-equality-c](evidence/job-final-equality-c.json) | 1.3 | PASS |
| [final-navigation-50mm-c](evidence/job-final-navigation-50mm-c.json) | 100.6 | PASS |
| [final-navigation-28mm-c](evidence/job-final-navigation-28mm-c.json) | 113.3 | PASS |
| [final-navigation-mount-c](evidence/job-final-navigation-mount-c.json) | 116.9 | PASS |
| [final-cards-50mm-c](evidence/job-final-cards-50mm-c.json) | 82.1 | PASS |
| [final-cards-28mm-c](evidence/job-final-cards-28mm-c.json) | 88.4 | PASS |
| [final-cards-mount-c](evidence/job-final-cards-mount-c.json) | 84.3 | PASS |
| [final-cap-50mm-c](evidence/job-final-cap-50mm-c.json) | 112.5 | PASS |
| [final-cap-28mm-c](evidence/job-final-cap-28mm-c.json) | 147.6 | PASS |
| [final-cap-mount-c](evidence/job-final-cap-mount-c.json) | 123.3 | PASS |
| [final-identity-c](evidence/job-final-identity-c.json) | 45.0 | PASS |
| [accepted-sizes-c](evidence/job-accepted-sizes-c.json) | 23.8 | PASS |

以上 13 个最终作业均绑定 DAT `5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681`，总耗时 17.4 分钟。构建重复性检查逐字节比较 104 个关键文件，见 [reproduce.json](evidence/reproduce.json)。受保护输入核对见 [audit.json](evidence/audit.json)，清理回执见 [cleanup.json](evidence/cleanup.json)。

起止核对覆盖 46,201 个原有文件。g154/g155、原包、官方固件和模拟器文件均未变；实际导入的 `datcodec.py` 起始、实测和结束哈希一致。工作室另有 7 个 LUT 与渲染文件在本轮期间发生同期变更，本任务未写这些路径，审计保留逐项前后哈希，未恢复或覆盖它们。编解码测试直接加载只依赖标准库的 `datcodec.py`，不导入这些变化模块，因此不把整个工作室误报为源文件未变。

## 首次失败与验证范围

初版 DAT `d19358d2…` 在缩短文件后直接复用了旧链接代码。BSS 仍从 89,624 开始，尾端超出新镜像分配 2,888 B，原生导航出现同一文字解码错误。C 用时 8.9 秒、Python 用时 153.6 秒，均确认失败。初版只通过了数据层检查，未计入最终通过；原始 DAT 和链接产物保留在新包 `local/initial-candidate/`，不能作为试用文件。修正是在原 C 对象上重新链接 BSS，增加 BSS 边界和逐项地址重定位核对，再重跑本轮所选组。[initial-candidate-rejection.json](evidence/initial-candidate-rejection.json) 与原失败回执均保留。

准备阶段的隔离模式导入错误，以及首次链接审计漏计 GOT 相对 BSS 立即数的断言，也按实际阶段保存于 [preparation-issues.json](evidence/preparation-issues.json)。这两项发生在构建或校验入口，不是模拟器后端差异。

辅助尺寸脚本曾因 `sys.path` 顺序误选 g153 的同名驱动，读到旧包的 107,072 B 主请求、90,164 B DAT 与 65,268 B 代码。环境变量分别选择 C 和 Python 的两次运行均失败，但实际均误走旧 Python 驱动，不能作为本包后端证据；补充观察也单列排除。修正导入顺序后，入口显式断言驱动绝对路径及本包 DAT 路径，三个单元的真实 resident 分配请求均通过。误选驱动曾在 `research/v39_g153/local/native/` 下新建 4 个本轮 PID 临时目录，已按创建时间与作业 PID 核对后全部清理，其父目录和原有文件未改动；旧 Scratch 的同 PID 子目录已由驱动退出清理。见 [misbound-cleanup.json](evidence/misbound-cleanup.json)。最终作业选择明示于 [job-selection.json](job-selection.json)，不把错误目标的结果计为通过。

本轮没有重跑与源码无变化的全套缓存、锁忙、跨退出和电源组。g154 报告中完整 keep=1 原厂续接、原始半按后的直接 part1 重显与关闭仍为 OPEN，本轮没有把这些路径记为通过。没有做存储卡、FAT32、实体相机、RTOS、真实单元通信、断电或实际照片颜色验收。机主后续步骤见 [OWNER_STEPS.md](OWNER_STEPS.md)。

## 重跑与哈希

三份上游拟合数据已迁至 `artifacts/downloads/vlog-alchemy-eval-20261102/`，目录由根 `.gitignore` 的 `/artifacts/downloads/` 规则忽略。移动保持数据字节与 DAT 不变，路径及哈希核对见 [fit_data_relocate_r1/REPORT.md](../fit_data_relocate_r1/REPORT.md)。

在项目根目录执行以下命令。所有持久二进制都落在新包 `local/`，拟合条目清单落在 `artifacts/downloads/g154-looks-r1/local/`，中间文件落在指定 Scratch。`check_all.py` 按组顺序串行运行；C 失败时保留回执，用 Python 后端确认后停止该批。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/g154-looks-r1
export GXR_HARNESS_BACKEND=c
nice -n 10 /usr/bin/python3 -I -B research/g154_looks_r1/prepare.py
nice -n 10 /usr/bin/python3 -I -B research/g154_looks_r1/prepare_checks.py
nice -n 10 /usr/bin/python3 -I -B firmware/engine_v65_g154_looks/candidate/build154.py
/usr/bin/python3 -I -B research/g154_looks_r1/check_all.py --prefix independent
nice -n 10 /usr/bin/python3 -I -B research/g154_looks_r1/reproduce.py
nice -n 10 /usr/bin/python3 -I -B research/g154_looks_r1/seal.py --prefix independent --cleanup
shasum -a 256 -c research/g154_looks_r1/SHA256SUMS
shasum -a 256 -c firmware/package_v39_g154_looks18_test/SHA256SUMS
```

每次使用新的 `--prefix`，避免覆盖既有作业回执。本轮 [SHA256SUMS](SHA256SUMS) 覆盖源码、脚本、报告、证据与包文件；新包另有自己的 [SHA256SUMS](../../firmware/package_v39_g154_looks18_test/SHA256SUMS)。
