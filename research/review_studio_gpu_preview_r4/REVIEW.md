不能合并

| 核实项目 | 判定 | 独立证据 |
| --- | --- | --- |
| r3 P1-01，Windows 完整运行失败 | 已关闭 | PR、push、调试分支的 Windows 完整套件均跑完 1,731 项，1,028 passed、703 skipped。两个表工作线程保留，未设置 Windows BLAS 单线程环境变量。[PR 检查](pr-checks-final.log)、[逐用例核对](ci-all-tests.json)、[运行库 A/B](runtime-ab-summary.log)。 |
| r3 P1-02，普通照片导入先解析父目录 | 指定路径已关闭 | 原替换点发生后，生产 stage_file 拒绝读取，暂存目录为空。另测原有父链接、扫描后父链接、根替换、已打开目录改名及异常关闭，共 18 项通过。[原反例](extra-boundaries.json)、[补充结果](additional-card-cases.json)。DAT 调用链另有下列 P1。 |
| r3 P2-01，Windows 事件循环内部连接被拒绝 | 已关闭 | 原脚本实际得到初始化成功、联网记录为空；新关闭条件通过。普通本地 TCP、非本地 TCP、直接 socketpair、DNS 仍拒绝，前一测试的错误仍被记到前一测试。[原脚本观察](original-windows_loop_guard.py.json)、[复跑](windows-loop-guard.json)、[Windows 日志](debug-probes.log)。 |
| 卡根身份被替换 | 未关闭，P1-01 | DAT 导入没有把已核对的挂载会话身份传给读取函数。替换普通根目录、替换其上级目录为链接，两种情况均实际读取另一目录的内容。根目录本身改为链接会拒绝。[API 结果](dat-root-variants.json)、[全新副本复验](reproductions/independent-selfcheck/receipt.json)。 |
| PR 上 fb6bacc 的三平台 CI | 全部通过 | pull_request 与 push 的 Windows、macOS、Linux check 均 success；不是仅采用调试分支结果。[最终检查](pr-checks-final.log)、[PR 元数据](pr-run-metadata.json)、[push 元数据](push-run-metadata.json)。 |
| 调试分支完整日志及跳过项 | 核对通过 | 调试分支同一 head SHA。Windows 与 macOS 测试集合相同，共同跳过 697 项夹具测试；其余差异均有平台原因。[差集](ci-final-comparison.json)、[跳过原因](ci-skip-comparison.json)。 |
| NumPy 平台锁定及七天规则 | 合理 | 两个平台标记互斥，uv.lock 对应两份解析；52 个 NumPy 轮子和源码包哈希与 PyPI 相符。2.5.4 在 2026-10-10 发布，已超过七天。[依赖证据](dependency-evidence.json)、[锁定哈希](numpy-lock-hashes.json)。 |
| 精确表与生产颜色函数 | 所测范围逐字节一致 | 两组原 r2 用例各穷举 256³ 输入，RGB 与 alpha 差异均为 0；第三组 64 MiB 表与 Windows 新旧版本对照 SHA 相同。[穷举](exhaustive-lut.json)、[本机表哈希](local-table-hash.json)。 |
| Windows 原生调用、资源与失败处理 | 所查路径通过 | 9 项原生文件句柄测试在 Windows 完整任务通过。核对 ChangeTime、ACL/所有者查询、进程 HANDLE 签名、标准句柄传递和关闭路径；未发现失败后改用完整路径读写。[原生日志](pr-windows.log)、[原声明模型](windows-contracts.json)、[新增声明模型](windows-new-contracts.json)。 |
| 新增与修改测试、CI 参数 | 未发现掩盖原失败的调整 | 44 份测试或辅助文件逐项核对，没有删除旧测试函数；断言节点由 2,032 增至 2,105。例外和触发窗口变化见正文。[断言差异](test-assertion-changes.json)、[语义核对](semantic-test-review.json)。 |
| macOS 主机回归及默认开关 | 通过 | 独立完整 make check 为 1,025 passed、706 skipped、0 自动重跑，覆盖率 89.88394%。默认关闭的 API 和前端用例通过。[回执](make-check-receipt.json)、[JUnit](make-check.xml)、[覆盖率](coverage.json)。 |
| r2/r3 原反例 | 原阻塞反例均通过 | 五组 r2 边界反例、原合成颜色反例，以及 r3 父目录、响应 fd、私有目录异常、声明、事件循环入口均复跑。签名与修复后预期的调整保留了原触发点，附逐文件 diff。[入口及回执](replay-receipts.json)、[r2 结果](r2-replay/http-boundary-extra.json)。 |
| 冻结输入与清理 | 通过 | 311 个跟踪文件前后相同，48 个先前审查输入哈希不变，工作树状态为空。3 次浏览器启动均正常关闭，任务临时根及 profile 已删除。[源稳定性](source-stability.json)、[清理](cleanup.json)、[SHA256SUMS](SHA256SUMS)。 |

对象是 [PR #16](https://github.com/aa2246740/gxr-studio/pull/16) 的 `fb6bacc51a35ee56736f9af4de5aa624cfd4ac14`，分支 feat/gpu-preview。相对 f47572e 有 24 个提交、61 个改动文件。结论来自本轮读取的源码、独立复跑和 GitHub 原始日志；实现者的 FIX_R3.md 只用作待核实线索。

本轮问题为 P1 1 项、P2 0 项。

| 编号 | 级别 | 位置与影响 | 最小修正及关闭条件 |
| --- | --- | --- | --- |
| P1-01，DAT 读取没有保持所选卡根身份 | P1 | [read_dat_from_card:119](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/camdata/intake.py:119) 只传 root，未传 expect。[import_from_card:196](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/api/camdata_routes.py:196) 已核对的 MountSession 身份没有继续传递。[open_rb:102](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/cards/discovery.py:102) 因此在实际打开前重新 lstat 当前路径，把替换后的根当成预期身份。 | 在显式 card_id 和自动单卡选择两条分支都保留所选 MountSession，把 fingerprint.root_dev/root_ino 作为必需参数传给 DAT 读取，再传给 open_rb。两种现失败场景都应在读取前返回 409，_read_limited 调用数必须为 0；补入两平台回归。 |

反例使用全合成目录和字节，通过真实 `/api/camdata/status` 取得 card_id，再调用真实 `/api/camdata/import-card`。会话核对后、生产 open_rb 之前，由独立短进程替换目录，读取仍调用生产实现；观察函数只记录 _read_limited 的真实返回字节和打开的 fd 路径，没有替换其返回值。

| 合成场景 | HTTP | 生产内容读取次数 | 实际结果 |
| --- | --- | --- | --- |
| 根目录被另一个普通目录替换 | 422 | 1 | 读取替换字节，根 dev/ino 已变化，expect=None。 |
| 根目录本身变成链接 | 409 | 0 | 正确拒绝。 |
| 根的上级目录变成指向另一目录的链接 | 422 | 1 | fd 实际指向 other-parent/SYNTH/GXRCE.DAT，读取卡根外的合成字节。 |

两次读入的 SHA-256 都是 `193193df6d8fa3640e0db74e27473046f27f83c6ba1a289b6aee4d9105bd2d27`。合成内容不符合 DAT 格式，所以之后被原有校验拒绝，没有安装相机数据。这里证实的是读取边界失效；不能用后续格式拒绝代替读取前的身份核对。全新 311 文件副本再次得到相同结果，临时副本随后删除。

该行为不是本轮新产生的回归。旧 DAT 调用也没有保持会话根身份，本轮改动只补了 root 参数，仍保留这条未封闭的读取链。[前后函数](dat-read-history.json)。普通照片导入与覆盖核对已经传 expect，本轮补充的 18 项用例均通过，不将 DAT 的问题混算成原照片父链接反例仍失败。

可独立重跑以下入口。它先核对卷 UUID、HEAD 和冻结哈希，只在指定 Scratch 范围创建新副本，结果保存在本审查目录的 reproductions/，随后清理该次临时副本。脚本以零退出表示成功复现当前记录的行为；关闭问题仍须满足上表的 409、读取次数为 0。

```bash
/usr/bin/nice -n 10 /Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/.venv/bin/python -I -B \
  /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_gpu_preview_r4/reproduce.py \
  --case dat-root --run-name dat-root-check
```

CI 结果已与最终 head SHA 绑定。

| 运行 | Windows 完整 tests | macOS 完整 tests | Linux check | windows-probes |
| --- | --- | --- | --- | --- |
| [PR 41587899044](https://github.com/aa2246740/gxr-studio/actions/runs/41587899044) | success，1,028/703，通过/跳过 | success，1,025/706 | success，1,021/710；另有 DAST 25 passed | 按条件跳过 |
| [push 41587891484](https://github.com/aa2246740/gxr-studio/actions/runs/41587891484) | success，1,028/703 | success | success | 按条件跳过 |
| [调试 41581601112](https://github.com/aa2246740/gxr-studio/actions/runs/41581601112) | success，1,028/703 | success，1,025/706 | success，1,021/710；另有 DAST 25 passed | success |

PR Windows 日志逐项列出 1,731 个不同用例，结束汇总为 1,028 passed、703 skipped，耗时 1,538.55 秒；没有中途截断、失败或自动重跑。push 的 Windows 也完整结束。macOS 的测试集合与 Windows 相同。共同跳过的 697 项缺少 DAT、标定、研究代码或照片夹具。macOS 另跳过 9 项 Windows 原生测试；Windows 另跳过 6 项：POSIX 权限位读取、macOS 中文字体、两项目录原子交换、ImageIO HDR、SIGHUP。相关跳过条件没有在本轮新增。

`windows-probes` 仅对 ci/** 或手动事件运行，适合作为诊断入口；PR 和 push 的完整 tests 仍包含其原生、离线和读卡边界测试。`--force-reruns 0` 覆盖 make 中的 `--reruns 1`，保留首个失败。`--maxfail=10` 只限制失败后的输出；本次成功运行的收集数、逐项结果和最终总数一致。15 分钟短任务及 40 分钟完整任务没有靠增加上限获得通过。

数值运行库的独立日志把问题缩小到 Windows NumPy 2.4.3 / OpenBLAS 0.3.31.dev 的并发计算组合。旧版本的纯矩阵入口不导入 Studio 句柄代码，两个工作线程各做 256 次 65,536×3 乘法，仍到 120 秒上限；旧版本 BLAS 单线程对照通过。同一 A/B 运行只改 NumPy 版本后，2.5.4 默认设置通过。[旧运行](runtime-old.log)、[同一次 A/B](runtime-ab.log)。两次历史运行的入口源码字节相同，最终入口仅把有限值检查加强成数值结果检查；计算规模和两个工作线程未减少。[源码对照](runtime-probe-source-comparison.json)、[差异](runtime-probe-value-checks.diff)。这支持更换运行库组合的修正，尚不能确定历史访问违规对应的具体原生指令。

Windows 2.4.3 的成功对照、Windows 2.5.4 默认设置和本机 2.4.3 的 67,108,864 字节表均得到 `0f87d0cb7e25e7b1c9cf03a5a1a852ff819d773b6de41f21bd97b3836f5df92c`。本机保留两个生产表工作线程，BLAS 线程按资源限制设为 1。

NumPy 2.5.4 还有其他变化。已核对与锁定源码包哈希相符的 [2.5.0 说明](numpy-2.5.0-notes.rst) 和 [2.5.4 说明](numpy-2.5.4-notes.rst)：包括 eig/eigvals 的返回类型、where 越界整数处理、默认内存分配器和构建工具链要求。项目未调用 eig/eigvals 或 from_dlpack，SciPy 1.17.1 允许 numpy>=1.26.4,<2.7，Python 要求也相容。[API 清单](numpy-api-inventory.json)、[源码来源与哈希](numpy-source-review.json)。所测颜色路径和完整 Windows 套件通过，不将此扩展为所有 NumPy 行为完全相同的结论。

测试差异中需要区分的几项如下。

| 调整 | 核对结果 |
| --- | --- |
| 精确表原样本检查改为全输入 | 加强为 256 个蓝色平面，逐字节比较全部 256³ 输入，包含 1D shaper、3D 表和 V-Log 输出。 |
| Range 的全进程 fd 集合改为媒体 fd 身份 | 新测试追踪 13 个实际媒体 fd 并要求结束后释放；本轮仍独立复跑旧 12 次超长 Range 反例，均 200，fd 7→7。 |
| Windows 目录移动先被系统拒绝 | 只接受实际移动点的 WinError 5，并检查调用次数、原文件、空文件或短写内容；移动成功时继续原清空字节断言，没有整组跳过。 |
| 进程终止由固定等待改为阶段信号 | 保留 20 轮、25 次实际终止、部分导入和恢复哈希检查。当前证据覆盖提交后及校验前两个确定时点，不代表复制中任意时点终止。 |
| POSIX 0600 改为平台权限检查 | POSIX 原断言保留。Windows 实际查询 DACL 和所有者 SID，检查允许主体；转换分配的 SID 文本和安全描述符在 finally 释放。 |
| 网络记录按测试清空 | 子 pytest 用例证明前一测试仍因联网记录报错，后一测试不受污染；没有清空后直接取消断言。 |
| UTF-8、路径分隔符、参数 ID、导出失败夹具 | 保留数据、来源哈希及错误码断言；导出目标改为临时普通文件的子路径，实际触发不可写目标，并检查原字节保留。 |

Windows 新增的 FILE_BASIC_INFO 为 40 B、ChangeTime 偏移 24，100 ns 到 Unix ns 的换算及 stat_result 额外字段保留均核对。查询失败会抛错，lstat_at 的 fd 在 finally 关闭。ACL/所有者查询只出现在测试辅助函数；进程存活辅助函数声明 64 位 HANDLE 并关闭它。生产父进程协议和测试实际 PID、标准句柄传递均由 Windows 日志验证。原删除、改名退回仍使用同一对象句柄。宿主模型只作为补充，没有代替 Windows 原生执行。

本机完整检查从逐文件副本运行。第一次准备因缺少隔离构建缓存和 pnpm 缓存停住；第一轮完整套件又因副本缺少仓库标识，得到 1 failed、1,024 passed、706 skipped。给临时副本补上合成仓库标识后，原失败用例先单独通过，再从头运行完整 make check，通过 1,025 项。没有修改被审工作树或放宽测试。所有首错、缓存准备和最终回执均保留。[夹具修正](fixture-adjustment.json)、[首轮完整日志](make-check-copy-first.log)、[单项复查](fixture-recheck.log)、[最终日志](make-check.log)。本机覆盖 11,462/12,752 条语句，排除 317 条，Windows 分支的结论来自实际 CI。

45 个前端、GPU、RAW、引擎、生产 LUT 颜色及相关文件与 r3 逐字节相同。[清单](stable-colour-sources.json)。本轮另跑的原合成 RAW/JPG 反例在 SwiftShader 上 mean=0、max_code=0；完整 GPU 颜色测试通过。[原反例结果](synthetic-lut-counterexample-swiftshader.json)。使用固定 Playwright 1.61.1、Chromium Headless Shell 1228，未使用系统 Chrome。

本轮未运行 macOS Metal 硬件路径、Windows D3D12 硬件路径、Windows 其他架构及 Python 3.12/3.13、真实读卡器与 FAT32 卡、OneDrive 实际部署、掉电落盘、相机或固件设备验收。缺失的实拍和校准夹具没有被当作通过。未访问机主 Studio、机主图库/导出/应用数据目录或真实存储卡；未改工作树、Git 状态、PR、远端或启动子代理。临时目录、pytest basetemp、浏览器 profile 均在指定任务根下；清理和浏览器退出有实际回执。

不能合并；P1 1 项；PR 上 fb6bacc 的 Windows、macOS、Linux CI 均通过；临时目录与浏览器 profile 已清理。
