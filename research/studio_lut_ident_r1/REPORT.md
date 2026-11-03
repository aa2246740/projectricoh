已修 LUT 输入声明优先级、输出传递函数、自动库条目迁移，并开放 MOUNT、28mm DNG 的 Log LUT 照片路径；可以交复审。
真实 35 项：14 项错误或冲突输入改为 V-Log，31 份 V-Log 均为 known，4 份创作者 LUT 保持 unknown；10 项输出按声明或命名调整。
5 张 MOUNT DNG 的研究路线对比 ΔE00 中位、P95、最大均为 0；50mm 的既有 5 例及新增半分辨率、全尺寸基线均逐字节不变。
最终完整 make check：1579 passed，覆盖率 92.80%，0 失败、错误、跳过、重跑；3 条警告见下文。

基线为 Studio `6df3ff3606efcf8d6f6e075b1696b52de06ab1a8`，动手前工作区干净。改动留在工作区，不做 Git 写操作。下面的回执都来自本轮实跑，真实 LUT 只由本机脚本读取，未把原文件、数值表或数值片段加入源码、测试或报告。

输入识别先采用文件内声明，包括 LUMIX 头和注释中的 input 字段。TITLE 和文件名先一起检查明确的 input 标记，再检查转换源域，最后检查其他关键词。相同优先级互相矛盾时保留 conflict；文件内明确声明不受风格名或灰轴形状覆盖。没有声明或输入关键词时保留 unknown，灰轴只核对已有猜测。F-Log2C 的独立色域没有加入现有空间表，因此其名称单独出现时保留 unknown。

输出先采用 output 字段，再检查 TITLE、文件名和其他注释。Rec709、BT.709 选 rec709，BT1886、Gamma 2.4 选 gamma24，sRGB 选 srgb。gamma24 使用既有零黑位假设；单独的原色名称不作为传递函数。无明确输出时保持 sRGB 默认。现有输入、输出控件和手选能力沿用；冲突气泡只有在灰轴确有分类时才追加原有内容说明。新增界面词为 0，无待确认新词。

真实文件前后对比见 [before-imports.json](before-imports.json)、[after-imports.json](after-imports.json) 和 [comparison.json](comparison.json)。所有 35 份文件的原始字节及 SHA-256 均核对通过。

| 范围 | 修改前 | 修改后 |
| --- | --- | --- |
| 富士 V-Log，12 项 | 11 项 guessed flog2，1 项 conflict | 12 项 known vlog |
| 徕卡 V-Log，2 项 | 2 项 guessed llog | 2 项 known vlog |
| 其他 V-Log，17 项 | 17 项 guessed vlog | 17 项 known vlog |
| LUMIX 创作者，4 项 | 4 项 unknown | 4 项 unknown |
| 哈苏 Rec709，4 项 | 默认 srgb | 按 output 声明选 rec709 |
| Nikon BT1886，4 项 | 默认 srgb | 按名称选 gamma24，零黑位假设 |
| 另 2 项带 Rec709 名称 | 默认 srgb | 按名称推测 rec709 |

最后两行属于名称所给的输出解释，不宣称已恢复其原始烘焙工程。ARRI Classic709 等仅有风格名称、没有明确显示传递函数的文件继续采用原有默认，允许手选。没有导入 Panasonic Standard 相机输入适配器。

库迁移使用独立的 `identification_version=2`，空间版本仍为原有 `version`。规则已写入 [architecture.md](../../studio/docs/architecture.md)。

1. `input_space_manual=true` 的条目整个空间配置保持原样。只改过输出、色域或范围也属于手选，沿用此前标记规则。
2. 自动条目首次读取时重新识别。输入或输出空间改变，只升一次空间版本，清空 fit、recipe、camera_lut。仅依据或状态更新不升空间版本。
3. 原始 cube、名称、分组、收藏和署名保持不动。迁移原子保存；失败保留旧索引，下一次重试，成功后重复打开不再改写。
4. 现有渲染 token、磁盘缓存键和图片 URL 随空间版本改变，旧缓存不再命中。迁移前拟合的版本检查返回 lut_changed，保存旧拟合返回 409。
5. 原先仅凭灰轴默认成 sRGB 的自动条目可迁移为 unknown，需要手选；已手选的同类条目保持原样。

合成测试覆盖手选保护、输入或输出单独变更、同时变更只升一次版本、无空间变更、迁移幂等、保存失败重试、已热缓存的缩略图和预览、旧拟合拒绝，以及无声明创作者的多种灰轴。LUT 均现场合成，没有第三方 LUT 夹具。

MOUNT 数值验收使用实际 `lut.photo.color_image` 半分辨率 RAW 路径。每张按评估脚本的 96 × 64 网格，独立读取 2 × 2 CFA 均值，在相同坐标取工作室像素；剔除 RAW 任一通道达到 98% 的点，五张共 30,381 个有效点。参考场景 XYZ 使用原评估保存的每张 DNG 矩阵、白平衡及冻结曝光锚，独立复写研究公式，不调用产品的 `SceneColour.xyz` 生成期望值。CIEDE2000 比较双方同样取整后的 sRGB 8 位像素，未用 JPEG 压缩误差替代颜色路线误差。

| MOUNT DNG | ISO | 有效点 | ΔE00 中位 | P95 | 最大 |
| --- | ---: | ---: | ---: | ---: | ---: |
| R8051530 | 800 | 5,961 | 0 | 0 | 0 |
| R8051533 | 800 | 5,988 | 0 | 0 | 0 |
| R8051562 | 200 | 6,144 | 0 | 0 | 0 |
| R8051691 | 200 | 6,144 | 0 | 0 | 0 |
| R8051839 | 3200 | 6,144 | 0 | 0 | 0 |

完整路径、输入哈希、XYZ 误差、量化前对照及输出哈希见 [after-photos.json](after-photos.json)。五张的场景 XYZ 最大绝对误差均为 0。另对 R8051691 运行实际全尺寸 RAW 条带路径，输出为 4288 × 2848，像素 SHA-256 为 `4cbd0ee5b622e3745c0d3b119ec7e07d665dadd81f60b6e532c36d91ae05be22`。

曝光锚保持 `u_m=0.10250885`、`f=-0.0022470695785486096`，来源为既有 50mm 测光标定。逐张以各自 DNG 矩阵、AsShotNeutral 核对 `u_m × 4095` 的中性码值：XYZ 的 Y 为 0.18，最大浮点误差 `2.78e-17`；V-Log 约为 0.42331145。未应用 BaselineExposure，也没有按 LUT 另调曝光。这证明与研究路线一致；MOUNT 的独立绝对曝光和测色标定尚未取得，输出仍标“电脑预测”。

50mm 的原评估 5 个成功案例全部重跑，4 个创作者 JPEG 路径及 1 个哈苏 Log RAW 路径的图像 SHA-256 与原评估逐字节一致，见 [50mm-existing-receipts.json](50mm-existing-receipts.json)。另冻结并重跑两张 50mm DNG 的整幅半分辨率图，以及 R8051131 的全尺寸图，全部哈希一致，见 [before-photos.json](before-photos.json)。全尺寸基线 SHA-256 为 `ef521cac5f45303bc2a435f68e250668097cc84c21f190c94873cbea75ff7ad3`。`spaces.py` 和 `scene.py` 未改。

50mm、28mm、MOUNT 均用合成 DNG 验证了编辑保存、实际预览和 PNG 导出，含已知常量 LUT 的像素断言。无 RAW 及缺色彩矩阵继续拒绝。真实 28mm DNG 未运行；没有把合成 28mm 结果写成实拍验收。MOUNT、28mm 的机内配方拟合仍保留原有未标定限制。

测试结果如下。全部 pytest 调用强制 `--force-reruns 0`，保留失败回执，没有以重跑替代修复。

| 检查 | 通过 | 失败 | 错误 | 跳过 | 回执 |
| --- | ---: | ---: | ---: | ---: | --- |
| 改前 LUT 基线 | 180 | 0 | 0 | 0 | [baseline-lut.xml](baseline-lut.xml) |
| 新增用例首轮 | 48 | 4 | 0 | 0 | [new-lut.xml](new-lut.xml) |
| 扩展 LUT 回归中间轮 | 236 | 3 | 0 | 0 | [all-lut.xml](all-lut.xml) |
| 最终定向检查 | 197 | 0 | 0 | 0 | [final-priority.xml](final-priority.xml) |
| 首轮完整 make check | 1574 | 0 | 0 | 0 | [make-check-before-named-fix.xml](make-check-before-named-fix.xml) |
| 最终完整 make check | 1579 | 0 | 0 | 0 | [make-check.xml](make-check.xml) |

最终完整检查覆盖率为 92.80%，高于未改动的 85% 门槛，退出码为 0，见 [最终回执](receipt.json)、[完整日志](make-check.log) 和 [覆盖率](coverage.json)。首轮、最终完整检查各有 3 条警告：合成样本拟合的 polyfit RankWarning、portable finish 测试期间报告的未关闭 SQLite 连接 ResourceWarning、Sentry 配置弃用 DeprecationWarning。未隐藏警告；这三个来源文件本轮未改，警告原文均保留在日志中。

迭代失败均已说明并留证，详见 [iteration_notes.json](iteration_notes.json)。新增用例首轮 4 个失败是测试调用了不存在的 `LutLibrary.token`，已改用已有的 `render_token`。中间轮 3 个失败是新增 PNG 断言错误地要求理想未压缩像素逐字节相同；既有成片导出经过 JPEG，实测与理想值每通道差 1 码，导出断言改用项目既有的 2 码容差，RAW 颜色路线仍要求 ΔE00 为 0。另修了本机验证脚本缺少 ReadLibrary.root、一个 mypy 列表注解及两个文件的格式。

额外自查核对了“TITLE 为目标风格、文件名明确 input”这一层；本机两个反例都复现了错误，见 [named-priority-counterexamples.json](named-priority-counterexamples.json)。首轮完整检查没有覆盖该边界。最终实现先合并两处 input 标记，再处理转换名称，并补入回归测试。首轮完整检查的 223 个源码文件在检查前后哈希稳定，见 [first-check-source-stability.json](first-check-source-stability.json)。

本机真实文件验证可独立复跑，使用已冻结的 before 回执比对当前工作区。before 回执是在干净基线生成的，不要在修改后的源码上覆盖它。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-lut-ident-r1
mkdir -p "$TMPDIR"
nice -n 10 studio/.venv/bin/python3 -I -B research/studio_lut_ident_r1/verify_local.py --phase after
```

完整检查沿用 Makefile，串行运行，测试和子进程均继承 nice 10；BLAS、OpenMP 线程设为 1。复跑命令为：

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-lut-ident-r1
export PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 MAKEFLAGS=-j1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MYPY_CACHE_DIR="$TMPDIR/mypy" RUFF_CACHE_DIR="$TMPDIR/ruff"
export COVERAGE_FILE=../research/studio_lut_ident_r1/coverage
export PYTEST_ADDOPTS="--force-reruns=0 --basetemp=$TMPDIR/pytest-review --junitxml=../research/studio_lut_ident_r1/make-check.xml --cov-report=json:../research/studio_lut_ident_r1/coverage.json"
nice -n 10 make check
```

盘检查在写入前运行：APFS 卷 `/Volumes/Workspace`，UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，可写，起始约余 988 GiB。所有测试使用任务 Scratch 下的 TMPDIR 和 pytest basetemp，没有运行浏览器或创建浏览器用户目录。没有访问或重启 127.0.0.1:49667，没有访问用户图库、用户导出、用户应用数据或存储卡；真实输入只读仓库 captures、downloads 和指定研究证据。

封存时重新核对 223 个源码文件、49 个真实输入与参考文件的哈希，全部稳定，见 [源码清单](check-source-after.json)、[输入稳定性](input-stability.json) 和 [改动清单](changed-files.json)。HEAD 仍为基线，暂存区无变更。任务 Scratch 已删除，残留 LUT worker 为 0，见 [清理回执](cleanup.json)。报告及证据的逐文件哈希见 [SHA256SUMS](SHA256SUMS)。

可以交复审；改动 11 个 Studio 文件，另 49 个报告与证据文件；make check 为 1579 passed、92.80% 覆盖率，0 失败、错误、跳过、重跑；已清理。
