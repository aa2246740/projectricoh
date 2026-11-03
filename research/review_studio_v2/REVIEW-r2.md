不能交付

验收对象为 `e6952acb89de95e089c8e7080c5d92de99057cc4` 上的未提交工作区，日期为 2026-10-31。第一轮 20 项问题中，11 项已关闭，9 项部分关闭。新增问题表共 10 项：3 项 P1、7 项 P2。未发现 P0 原文件损坏。

交付阻塞是实际导出改变了未选配方照片的画面、零编辑竖拍 JPG 的方向错误，以及新增可移植测试依赖 macOS 字体。最后一项已在主机上模拟缺字体复现；Ubuntu CI 的失败是依据工作流和字体路径作出的推断，没有实际运行远端 Linux CI。

主机已证：`make check` 488 passed，覆盖率 91.12%，总耗时 372.75 秒；源码隔离快照 350 passed、138 skipped，覆盖率 87.60%，耗时 62.99 秒。产品文件 216 项最终哈希与开验时一致。只写验收脚本、证据和本报告，没有改产品代码或执行 Git 写操作。

1．第一轮问题逐项复验

| 编号 | 状态 | 复验结果与证据 |
| --- | --- | --- |
| V2-01 | 部分关闭 | 后端 `source=auto` 已统一。JPG 曝光 +1.5 的导出相对零编辑 MAE=59.8583，预览与导出 MAE=0.2708；其他 9 项调整/曲线也改变导出。实际前端仍强制 `source=recipe`，未选配方 RAW+JPG 的平均 ΔE00=2.2745，见 R2-01。[acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/acceptance.json)、[ui-regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-regression-r2.json)。 |
| V2-02 | 已关闭 | 真实 RAW-only 的 full 和零编辑/调整/配方导出均为 4288 × 2848；白边成片为 4632 × 3192，照片本体保持全尺寸。[regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/regression-r2.json)。 |
| V2-03 | 部分关闭 | 640 × 480 向左旋转后的 frame 与 uncropped 均为 480 × 640，1:1 输出 480 × 480。大于 1200 像素的画布仍采用近似尺寸，1600 × 1200 垂直 +80 的 API frame 为 1804 × 1231，实际为 1794 × 1217，见 R2-03。[geometry-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/geometry-r2.json)。 |
| V2-04 | 已关闭 | 拉直、垂直、畸变保存后都有收缩框，成片角不再是填充色。对 640 × 480、1600 × 1200 的拉直、垂直、水平、畸变、组合变换共 10 个有效像素蒙版检查，保存框内无效像素均为 0。[acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/acceptance.json)、[geometry-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/geometry-r2.json)。 |
| V2-05 | 已关闭 | 按住空格真实请求 `stage=original&size=preview`；白边照片显示为 640 × 480，无边框。[ui-acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-acceptance.json)、[ui-space-original.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-space-original.png)。 |
| V2-06 | 已关闭 | 水平线图当前 0°、10° 都返回最终建议 0°、vertical 整数 0；原样保存 200，再次建议相同；平面图 confident=false。[auto-level-lines.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/auto-level-lines.json)。 |
| V2-07 | 已关闭 | 本机“上海”和“北京”的时间戳、拍立得文字像素均不同，截图字形正常。缺系统中文字体时会明确拒绝，新增测试对该环境的处理见 R2-08。[stamp-chinese.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/stamp-chinese.png)、[frame-chinese.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/frame-chinese.png)。 |
| V2-08 | 部分关闭 | “复原”已写 none/false，刷新后保持 640 × 480；后来修改默认值也不会重新启用。但“复原→撤销”把原先继承的装饰固化为照片设置，见 R2-09。[ui-acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-acceptance.json)、[default-states-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/default-states-r2.json)、[ui-latency-defaults-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-latency-defaults-r2.json)。 |
| V2-09 | 已关闭 | rev=0 的照片套默认白边后缩略图改变，Cache-Control 为 private, no-cache。独立复验中侧写版本不变，列表 thumb URL 的 d 版本改变，返回字节也改变。[focused.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/focused.json)、[lock-trace-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/lock-trace-r2.json)。 |
| V2-10 | 已关闭 | 请求 long_edge=512，白边最终输出 512 × 353。7 个 size=thumb 样式响应最长边均为 240。[acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/acceptance.json)、[visual-check.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/visual-check.json)。 |
| V2-11 | 已关闭 | 原来的 EXIF 丢失已修，装饰导出保留 270、271、272、274、305、306、34665，并更新输出尺寸。零编辑竖拍的方向回归另列 R2-02。[acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/acceptance.json)、[focused.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/focused.json)。 |
| V2-12 | 部分关闭 | 纯 24 字时间戳会缩小，原来的宽度越界已修。日期+时间+24 字仍在格式化时直接截短，末尾 4–5 字丢失，见 R2-04。[stamp-long-text.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/stamp-long-text.png)、[text-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/text-r2.json)。 |
| V2-13 | 已关闭 | 非法日期保存 422，随后预览和导出仍均为 200；format=tiff 返回 422。[focused.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/focused.json)。 |
| V2-14 | 已关闭 | 未知 id、目录外链接、同目录替换链接均为 404；请求体注入路径仍只打开登记产物。授权的一次真实 Finder 调用返回 200。[acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/acceptance.json)。 |
| V2-15 | 部分关闭 | 纠正拖动请求已改成 preview；独立 HTTP 中位 0.3688 秒。但真实垂直滑块松手到新图显示中位 2.3397 秒，5 次全部超过 1.5 秒，保存时的图库锁阻塞已实测，见 R2-10。[focused.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/focused.json)、[ui-latency-defaults-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-latency-defaults-r2.json)、[lock-trace-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/lock-trace-r2.json)。 |
| V2-16 | 已关闭 | 1360 × 860、1024 × 768 下，7 个边框缩略图均为 contain，约 155.5 × 116.1 CSS px，标志和参数没有被裁切。[visual-check.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/visual-check.json)、[ui-frame-settled-1360.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-frame-settled-1360.png)、[ui-frame-settled-1024.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-frame-settled-1024.png)。 |
| V2-17 | 部分关闭 | 原 116 项的术语、长解释与异常原文问题已大幅修正。按新裁定仍有 35 个 API 非法参数反例，涉及 34 个后端位置；界面还直接显示 original/prediction，并有错误详情丢失。见 R2-05、06、07及下附全文。[COPY_VIOLATIONS-r2.tsv](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/COPY_VIOLATIONS-r2.tsv)。 |
| V2-18 | 部分关闭 | 导出 JSON 的 render_label 已为机器枚举，另有 render_text；运行时 OpenAPI 与文件一致。预览响应头却也改成机器枚举，前端直接显示并漏掉“未校准”，见 R2-05。[acceptance.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/acceptance.json)、[ui-prediction-label-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-prediction-label-r2.png)。 |
| V2-19 | 部分关闭 | 方向断言、自动建议应用及近似开关命名已改，成片服务覆盖率提升。长文本断言仍只检查画布内已画出的像素，拦不住截字；新增 portable 测试还依赖 macOS 中文字体。见 R2-04、08。[tests/test_portable_finish.py:72](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/tests/test_portable_finish.py:72)。 |
| V2-20 | 部分关闭 | 本机源码隔离门槛已过：350 passed、138 skipped、87.60%，无相邻私有夹具。Ubuntu 工作流未补 macOS 字体依赖；主机模拟缺字体时该 portable 测试 1 failed，见 R2-08。[portable.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/portable.json)、[portable.log](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/portable.log)、[no-cjk.log](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/no-cjk.log)。 |

2．新发现及残留问题

P1 阻止交付；P2 是已复现的功能、合同或质量缺陷。R2 编号包括本轮新增反例和第一轮修复后仍残留的分支。

| 编号 | 严重度 | 文件:行 | 说明与复现证据 | 建议 |
| --- | --- | --- | --- | --- |
| R2-01 | P1 | [web/assets/export.js:30](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/web/assets/export.js:30) | 相机配方与校准已导入时，未选配方的 RAW+JPG 从界面导出仍发送 source=recipe。预览用相机 JPG，导出改用 RAW 04；source=auto 与强制 recipe 的平均 ΔE00=2.2745。实际界面请求与 200 响应均已记录。[ui-regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-regression-r2.json)、[regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/regression-r2.json)。 | 界面导出交给 source=auto，由统一后端按照片自己的 recipe 状态选底图；批量也按同一规则。 |
| R2-02 | P1 | [src/gxr_studio/export.py:282](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/export.py:282) | 新鲜、零编辑且 EXIF Orientation=6 的 JPG，预览和 full 图显示 480 × 640，导出却为 640 × 480 且 Orientation=1。原始 JPEG 直接进入 write_with_exif 时没有转正像素，随后清除了方向。只加一项调整或白边后又恢复正确竖幅。[orientation 三组反例](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/regression-r2.json)。 | 在重编码前按 EXIF 转正，或保持原始像素与方向标记的一致性；用非对称竖拍图覆盖零编辑导出。 |
| R2-03 | P2 | [src/gxr_studio/finish/geometry.py:199](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/geometry.py:199) | 长边超过 1200 时，把 360 像素试算画布按比例放大，试算时的固定边缘留量也被放大。垂直 +80：1804 × 1231 对实际 1794 × 1217；畸变 +70：1369 × 1111 对实际 1352 × 1098。裁剪 API 的像素数也随之错误。[geometry-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/geometry-r2.json)、[regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/regression-r2.json)。 | 共享真实输出画布的边界计算，避免把低分辨率固定留量同比放大。 |
| R2-04 | P2 | [src/gxr_studio/finish/stamp.py:46](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/stamp.py:46) | 合法 text=ABCDEFGHIJKLMNOPQRSTUVWX，日期格式 yyyy.mm.dd、显示时间开启时，实际行只到 ABCDEFGHIJKLMNOPQRS，末尾 TUVWX 丢失。另一日期格式也丢 4 字。此处在绘制前截断，缩小字号无法补救。[text-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/text-r2.json)。 | 只限制自定义文本为 24 字，保留完整日期/时间/文字拼接结果，再按实际宽度排版；测试断言完整文本。 |
| R2-05 | P2 | [src/gxr_studio/api/render_routes.py:191](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/api/render_routes.py:191)；[web/assets/preview.js:514](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/web/assets/preview.js:514) | X-GXR-Label 传 original/prediction，stageLabels 原样显示。真实截图出现英文机器枚举；calibrated=false 的配方成片只显示 prediction，未出现“电脑预测”“未校准”。[ui-prediction-label-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-prediction-label-r2.png)、[ui-regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-regression-r2.json)。 | 分开机器类型和显示文字；前端按类型及 calibrated 生成中文标签，或使用单独的显示响应头。 |
| R2-06 | P2 | [web/assets/export.js:162](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/web/assets/export.js:162) | 界面将导出到填成临时图库时，后端 422 的主句为“无法导出到这个位置。请换一个文件夹。”并带 detail；界面却改成“导出失败。请重试。”，详情节点数为 0。[ui-export-error-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-export-error-r2.png)、[ui-regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-regression-r2.json)。 | 导出 catch 保留后端主句并调用 errorBody；有 detail 时提供默认收起的详细信息。批量错误也保留逐项原因。 |
| R2-07 | P2 | [src/gxr_studio/api/render_routes.py:170](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/api/render_routes.py:170)；[src/gxr_studio/render/params.py:113](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/render/params.py:113)；[src/gxr_studio/finish/spec.py:106](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/spec.py:106) | COPY 3.13-2 要求界面无法构造的非法参数使用统一主句。35 个真实 API 请求仍返回专用解释，如“品质要在 30 到 100 之间。请改小或改大一点再试。”、非整数档位和非法枚举等。均为 422，不是崩溃。[copy-api-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/copy-api-r2.json)、[COPY_VIOLATIONS-r2.tsv](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/COPY_VIOLATIONS-r2.tsv)。 | 在 API 参数边界使用“请求无效。请刷新页面后重试。”，把具体原因放 detail，保留 COPY 明文允许的固定例外。 |
| R2-08 | P1 | [tests/test_portable_finish.py:60](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/tests/test_portable_finish.py:60)；[src/gxr_studio/finish/stamp.py:49](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/stamp.py:49)；[.github/workflows/ci.yml:19](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/.github/workflows/ci.yml:19) | 新增 portable 测试无条件渲染中文，但回退路径全部在 /System/Library/Fonts。把字体候选置空的主机模拟结果为 1 failed，抛 missing_cjk。工作流是 ubuntu-latest，未提供这些字体，因此推断当前 CI 不能通过；并未实跑 Linux。[no-cjk.log](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/no-cjk.log)、[r2_no_cjk.py](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/r2_no_cjk.py)。 | portable 测试使用可分发、跨平台的字体夹具或明确模拟字体回退；保留 macOS 中文字形集成检查及 85% 门槛。 |
| R2-09 | P2 | [web/assets/preview.js:315](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/web/assets/preview.js:315)；[web/assets/preview.js:363](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/web/assets/preview.js:363) | 照片原先 frame=null、stamp=null，继承默认白边与文字 FIRST。“复原→撤销”后变成显式 gallery/FIRST。将默认改为徕卡水印/SECOND 后刷新，仍是旧白边 692 × 532。直接保留继承状态则应随新默认变为 640 × 544。[ui-latency-defaults-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-latency-defaults-r2.json)、[default-states-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/default-states-r2.json)。 | 撤销快照保存装饰的原始缺省/继承状态；撤销时恢复该状态，而不是把已经解析的默认值写成照片设置。 |
| R2-10 | P2 | [src/gxr_studio/render/edits.py:69](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/render/edits.py:69)；[src/gxr_studio/finish/geometry.py:366](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/geometry.py:366) | 真实垂直滑块松手到新图显示 5 次为 2.2631–2.5814 秒，中位 2.3397 秒，全部超过 1.5 秒。请求为 stage=uncropped&size=preview。独立诊断中，保存持有图库锁计算全尺寸 fitted_crop，预览 get_shot 等锁 2.33255 秒。[ui-latency-defaults-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-latency-defaults-r2.json)、[lock-trace-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/lock-trace-r2.json)。 | 把纯几何计算移出共享图库锁，并按版本校验提交；共享可复用的几何结果或只计算有效蒙版，避免保存时生成全尺寸 RGB。按真实松手流程复验。 |

3．统一流水线回归

以下通过真实临时 HTTP 实例逐项保存后读取 preview、full、图库 thumb 并导出。导出在这张表内统一使用 source=auto；实际界面另有 R2-01。所有图像都成功解码。色差统一把图像缩到 240 × 160 再算平均 ΔE00，包含不同分辨率采样和 JPEG 编码的影响。合同没有给出缩略图一致性的数值容差，下面保留实测值。

| 照片 | 状态 | 导出尺寸 | preview/导出 ΔE00 | thumb/导出 ΔE00 |
| --- | --- | --- | --- | --- |
| 只有 RAW | 零编辑 | 4288 × 2848 | 0.7067 | 2.6042 |
| 只有 RAW | 只调整 | 4288 × 2848 | 0.7493 | 2.6171 |
| 只有 RAW | 选配方 | 4288 × 2848 | 0.6058 | 1.9993 |
| 只有 RAW | 边框+中文时间戳 | 4632 × 3192 | 0.5821 | 1.9861 |
| 只有 JPG | 零编辑 | 640 × 480 | 0.2529 | 0.6052 |
| 只有 JPG | 只调整 | 640 × 480 | 0.1749 | 0.6028 |
| 只有 JPG | 选配方 | 不可用，按钮置灰，capabilities.recipe=none | 不适用 | 不适用 |
| 只有 JPG | 边框+中文时间戳 | 692 × 532 | 0.1559 | 1.1557 |
| RAW+JPG | 零编辑 | 4288 × 2848 | 0.2731 | 1.2222 |
| RAW+JPG | 只调整 | 4288 × 2848 | 0.2151 | 1.0582 |
| RAW+JPG | 选配方 | 4288 × 2848 | 0.4748 | 1.1657 |
| RAW+JPG | 边框+中文时间戳 | 4632 × 3192 | 0.2668 | 1.2566 |

完整数值与 full/导出比较见 [regression-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/regression-r2.json)。六种边框及时间戳的可见性、同尺寸导出比较另见 [focused.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/focused.json)。

4．全分辨率速度、内存和界面等待

机器为 10 逻辑核、16 GiB 内存，测量时 load average 约 4.5–5.3，另有任务运行。每个场景使用独立进程，顺序执行 5 次 JPEG quality=95 导出；计时包含 API、完整渲染、编码和文件落盘。每个最终文件另行完整解码，核对尺寸和字节数。峰值是验收进程的 ru_maxrss，含应用、缓存及图像核验，不是单个 numpy 数组大小。

| 场景 | 中位耗时 | 范围 | 进程峰值内存 | 导出尺寸 |
| --- | --- | --- | --- | --- |
| RAW+JPG，未选配方，用相机 JPG | 0.1825s | 0.1719–0.2180s | 430.55 MiB | 4288 × 2848 |
| 只有 RAW，04 标准 | 1.5287s | 1.5109–1.6555s | 774.42 MiB | 4288 × 2848 |
| 只有 RAW，08 配方 | 1.5116s | 1.5009–1.5777s | 778.83 MiB | 4288 × 2848 |
| 只有 RAW，08+垂直 40+拉直 3°+白边 | 3.5071s | 3.3330–3.5454s | 3266.47 MiB | 4406 × 2952 |

20 次计时导出均成功，核验无缺文件或降分辨率。带几何的设置保存本身另耗时 2.3154 秒。没有测量相对基线的速度变化。独立、未计入以上计时的 full 导出 profile 为 3.334 秒，其中 warp 1.755 秒，RAW render_full 0.961 秒；主要成本是几何重采样与全尺寸 RAW 渲染。
各次数据见 [export-perf-paired.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/export-perf-paired.json)、[export-perf-raw_standard.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/export-perf-raw_standard.json)、[export-perf-raw_recipe.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/export-perf-raw_recipe.json)、[export-perf-raw_geometry.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/export-perf-raw_geometry.json)，诊断见 [export-full-profile.txt](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/export-full-profile.txt)。

单独 HTTP 纠正请求：preview 五次中位 0.3688 秒，范围 0.3680–0.4615 秒；full 五次中位 1.6160 秒，范围 1.4876–2.0392 秒。真实界面垂直滑块的五次等待为 2.5814, 2.4061, 2.2682, 2.3397, 2.2631 秒，中位 2.3397 秒。界面计时从 mouseup 到新 blob 图像 complete 且具有有效尺寸；之后才等保存请求和网络空闲，不把后续等待计入显示耗时。诊断运行确认了图库锁阻塞，见 R2-10。

补充界面脚本的第一次尝试等待了一个不必出现的第二次 crop PUT，60 秒后超时。已保留 attempt1 文件；移除该错误等待后，5 次界面显示计时及默认值撤销流程均跑完，0 个页面异常。该脚本超时不计产品缺陷。

5．第一版图库与默认装饰

基线源码重新通过 git show e6952ac 取出到本轮 Scratch，再调用基线自己的导入器和编辑写入函数造库。5 张照片、7 个媒体文件，首次由 v2 打开时，5 份 sidecar 均与基线内容相同，媒体哈希全相同；GET edit/crop 均正常。旧 RAW 的配方 08、旋钮记忆、调整和曲线保留，省略角度重存裁剪后仍为 +3.5°，可导出 640 × 640。旧 JPG 仍为 −2°，调整和曲线保留，可导出 360 × 640。原来的普通 JPG 调整丢失已修；新零编辑方向回归见 R2-02。
本轮 [baseline-fixture.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/baseline-fixture.json) 与 [baseline.log](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/baseline.log) 都是新生成的，不使用被覆盖过的首轮记录。

直接复原已能区分“继承”和“关闭”：缺键时默认白边输出 692 × 532；显式 none/false 输出 640 × 480；后来将默认改为徕卡/新文字，显式关闭仍为 640 × 480；删掉照片设置后继承新默认，输出 640 × 544。真实界面的“复原→撤销”仍丢失继承语义，见 R2-09。

6．文案复跑与剩余字符串

原 copy_audit.py 已独立复跑，抽取 173 个错误表达式，输出 16 条候选。其中 15 条是首轮写死行号的人工项，不能沿用原评语；移除旧行号表后只有 lut/service.py:365 的动态 fallback 候选。该调用在 render unavailable 时 status.hint 为两短句，因此没有把未命中的短 fallback 计入当前可达文案问题。
前端另抽取 437 条中文字符串字面量，未发现禁用术语字面量。运行时却暴露出机器枚举 original/prediction。根据 COPY 3.13-2 补测 API 非法参数，35 个反例涉及 34 个后端位置，详见下面全文及 TSV。以下 API 主句应统一为“请求无效。请刷新页面后重试。”，原有具体原因放 detail；该项是合同格式不符，均正常返回 422。
脚本和原始结果：[copy_audit.py](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/copy_audit.py)、[copy_r2.py](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/copy_r2.py)、[copy-api-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/copy-api-r2.json)、[COPY_VIOLATIONS-r2.tsv](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/COPY_VIOLATIONS-r2.tsv)。

| 文件:行 | 仍不合规的字符串 |
| --- | --- |
| src/gxr_studio/api/render_routes.py:170 | 品质要在 30 到 100 之间。请改小或改大一点再试。 |
| src/gxr_studio/render/params.py:113 | 无法保存调整。请输入整数。 |
| src/gxr_studio/render/params.py:116 | 无法保存调整。数值超出范围。 |
| src/gxr_studio/render/params.py:127 | 有无法识别的调整项。请重新打开这张照片后再试。 |
| src/gxr_studio/render/params.py:130 | 曝光要在 ±5 挡以内。请改小一点再试。 |
| src/gxr_studio/render/params.py:153 | 只支持一条曲线。请重新设置后再试。 |
| src/gxr_studio/render/params.py:158 | 曲线要有 2 到 16 个点。请重新设置后再试。 |
| src/gxr_studio/render/params.py:166 | 无法保存曲线。点的格式不对。 |
| src/gxr_studio/render/params.py:169 | 无法保存曲线。输入要从小到大。 |
| src/gxr_studio/render/params.py:181 | 目前只支持内置配方。请改用内置配方后再试。 |
| src/gxr_studio/render/params.py:184 | 无法保存配方。请重新选择镜头单元。 |
| src/gxr_studio/render/params.py:186 | 无法保存配方。槽位要在 1 到 8。 |
| src/gxr_studio/render/params.py:193 | 无法保存配方。有一个旋钮无法使用。 |
| src/gxr_studio/render/params.py:196 | 无法保存配方。档位要是整数。 |
| src/gxr_studio/finish/spec.py:106 | 拉直要在 -45 到 45 之间。请改小一点再试。 |
| src/gxr_studio/finish/spec.py:113 | 垂直要是整数。请输入整数后再试。 |
| src/gxr_studio/finish/spec.py:125 | 有无法识别的纠正参数。请重新打开这张照片后再试。 |
| src/gxr_studio/finish/spec.py:128 | 向左旋转只能是 0 到 3 次。请重新设置后再试。 |
| src/gxr_studio/finish/spec.py:131 | 水平翻转只能打开或关闭。请重新设置后再试。 |
| src/gxr_studio/finish/spec.py:149 | 没有这个边框样式。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:152 | 边框颜色只能是白、黑或米白。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:155 | 边框宽度只能是细、中或粗。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:158 | 画布比例不在可选范围内。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:161 | 边框文字最多 24 个字。请缩短后再试。 |
| src/gxr_studio/finish/spec.py:164 | 边框的显示开关只能打开或关闭。请重新设置后再试。 |
| src/gxr_studio/finish/spec.py:184 | 时间戳内容只能是日期、文字，或日期和文字。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:187 | 时间戳字体只能是数码管、打字机或无衬线。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:190 | 时间戳颜色只能是橙、红、黄或白。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:193 | 时间戳大小只能是小、中或大。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:196 | 时间戳位置只能是四个角之一。请重新选择后再试。 |
| src/gxr_studio/finish/spec.py:199 | 时间戳文字最多 24 个字。请缩短后再试。 |
| src/gxr_studio/finish/spec.py:207 | 指定日期无效。请重新选择日期后再试。 |
| src/gxr_studio/finish/spec.py:210 | 时间戳的开关只能打开或关闭。请重新设置后再试。 |
| src/gxr_studio/finish/spec.py:213 | 没有这个日期格式。请从列表里重新选择。 |
| web/assets/preview.js:514 | original |
| web/assets/preview.js:514 | prediction |

7．视觉复验

界面以照片为主，右侧固定工具面板，使用系统中文字体和金色选中态。1360 × 860 与 1024 × 768 的截图中，主图、标签栏、裁剪参考线和面板底部动作没有重叠，页面无水平溢出。边框卡片完整容纳标志和参数；列表下方样式通过面板滚动访问。时间戳开启后中文可读，控件和结果同屏可见。
导出成功区域能显示长路径、输出尺寸和“在访达中显示”；长路径允许换行。LUT 实际解析错误的详情默认关闭，展开后内部错误留在折叠区内，布局正常。仍有成片标签显示机器枚举及导出错误丢失详情的问题，见 R2-05、06。

| 页面 | 本轮截图 |
| --- | --- |
| 边框，1360/1024 | [ui-frame-settled-1360.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-frame-settled-1360.png)、[ui-frame-settled-1024.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-frame-settled-1024.png) |
| 裁剪，1360/1024 | [ui-crop-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-crop-r2.png)、[ui-crop-1024-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-crop-1024-r2.png) |
| 时间戳关闭/开启 | [ui-stamp-current.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-stamp-current.png)、[ui-stamp-enabled-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-stamp-enabled-r2.png) |
| 导出完成/失败 | [ui-export-complete-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-export-complete-r2.png)、[ui-export-error-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-export-error-r2.png) |
| 详细信息收起/展开 | [ui-error-details-closed-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-error-details-closed-r2.png)、[ui-error-details-open-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-error-details-open-r2.png) |
| 配方标签/撤销继承状态 | [ui-prediction-label-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-prediction-label-r2.png)、[ui-undo-inheritance-r2.png](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/ui-undo-inheritance-r2.png) |

8．复跑命令与证据边界

持久脚本位于 r2-evidence。再次复跑时，先复制到指定 Scratch 的 evidence 子目录，保持脚本的 HERE 指向临时证据目录；所有命令顺序执行。首轮脚本副本只调整工作仓库、Scratch、输出路径及缓存目录。新脚本不写产品源码。各 subprocess 的整体上限为 1800 秒，make check 的历史约 6 分钟。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio
REVIEW_TMP=/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r2
mkdir -p "$REVIEW_TMP/evidence"
cp ../research/review_studio_v2/r2-evidence/*.py ../research/review_studio_v2/r2-evidence/*.mjs "$REVIEW_TMP/evidence/"
export TMPDIR="$REVIEW_TMP" PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
export PYLINTHOME="$REVIEW_TMP/pylint" XDG_CACHE_HOME="$REVIEW_TMP/cache"
.venv/bin/python -B "$REVIEW_TMP/evidence/run_checks.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/portable_check.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/serial_checks_r2.py"

# 单独终端启动，读取 server-ready.json 中的新端口；测试结束后关闭这个实例。
.venv/bin/python -B "$REVIEW_TMP/evidence/temp_server.py"

# 服务启动后，顺序执行。
.venv/bin/python -B "$REVIEW_TMP/evidence/focused_checks.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/auto_check.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/regression_r2.py"
node "$REVIEW_TMP/evidence/ui_acceptance.mjs"
node "$REVIEW_TMP/evidence/visual_check.mjs"
node "$REVIEW_TMP/evidence/ui_regression_r2.mjs"
.venv/bin/python -B "$REVIEW_TMP/evidence/api_contract_r2.py"
node "$REVIEW_TMP/evidence/ui_latency_defaults_r2.mjs"

# 关闭临时 HTTP 实例后，顺序执行，每个场景 5 次导出。
.venv/bin/python -B "$REVIEW_TMP/evidence/export_perf_r2.py" paired
.venv/bin/python -B "$REVIEW_TMP/evidence/export_perf_r2.py" raw_standard
.venv/bin/python -B "$REVIEW_TMP/evidence/export_perf_r2.py" raw_recipe
.venv/bin/python -B "$REVIEW_TMP/evidence/export_perf_r2.py" raw_geometry
.venv/bin/python -B "$REVIEW_TMP/evidence/lock_trace_r2.py"
```

缺字体模拟的独立命令如下。r2_no_cjk.py 仅在测试进程里把系统字体候选置空，产品文件不变；预期是复现 1 failed。

```bash
cd "$REVIEW_TMP/source-only/studio"
PYTHONPATH="$REVIEW_TMP/source-only/studio/src:$REVIEW_TMP/evidence" \
/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/.venv/bin/python -B -m pytest \
  tests/test_portable_finish.py::test_frames_stamp_and_valid_crop_cover_the_synthetic_paths \
  -q -p r2_no_cjk --reruns 0 --no-cov \
  --basetemp="$REVIEW_TMP/no-cjk-pytest" -o cache_dir="$REVIEW_TMP/no-cjk-cache"
```

本轮使用固定 Playwright 1.61.1、Chromium Headless Shell revision 1228，所有启动均调用 launchPinnedChromium。没有启动系统 Chrome、其他 agent 的浏览器、容器或远端 CI。源码隔离检查复用本机锁定虚拟环境，证明无相邻私有夹具时的覆盖率，不等于重新安装依赖后的 Linux 验收。

清理核对见 [cleanup-r2.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/cleanup-r2.json)：临时实例与 Chromium 已关闭，指定 Scratch 已删除；基线媒体、相机配方文件输入和 216 项产品文件哈希未变，首轮 62 个已有证据文件也未变。没有访问真实图库、127.0.0.1:49667 或存储卡。持久证据清单见 [EVIDENCE-SHA256.json](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r2-evidence/EVIDENCE-SHA256.json)。
