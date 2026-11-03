可以交复审

对象：PR #16 第三轮问题；交接基线 `f47572e6ac524400b79f6bebf986be368525e0a6`，最终本地提交 `fb6bacc51a35ee56736f9af4de5aa624cfd4ac14`。工作树仍在 `feat/gpu-preview`，仅推送 `ci/win-fix-r3`。没有更新 PR 分支、main、仓库设置或 PR 评论。

同一最终 SHA 的完整 CI

| 任务 | 结果 | 完整套件记录 |
| --- | --- | --- |
| [tests (windows-latest)](https://github.com/aa2246740/gxr-studio/actions/runs/41581601112/job/125737481171) | success | 1028 passed, 703 skipped, 2 warnings in 1544.75s (0:25:44) |
| [tests (macos-latest)](https://github.com/aa2246740/gxr-studio/actions/runs/41581601112/job/125737481389) | success | 1025 passed, 706 skipped, 2 warnings in 352.98s (0:05:52) |
| [check](https://github.com/aa2246740/gxr-studio/actions/runs/41581601112/job/125737481305) | success | 1021 passed, 710 skipped, 3 warnings in 254.65s (0:04:14) |

[Windows 短任务](https://github.com/aa2246740/gxr-studio/actions/runs/41581601112/job/125737481285) 也通过，包含独立 I/O、事件循环、双工作线程矩阵和逆矩阵、64 MiB 精确表，以及原生句柄、盘符根读取、读卡边界、离线守卫、A1a r2/r3、恢复、启动脚本和 GPU API 用例。[原生断言清单](fix_r3/windows-native-evidence.json)逐项保存 9 个句柄与盘符根、7 个网络守卫、11 个读卡边界通过记录；[显卡颜色清单](fix_r3/gpu-colour-evidence.json)保存 13 组完整比较结果。短任务上限 15 分钟，用 `-x -vv` 保留首错，并在数值计算之前检查父进程终止与 worker 退出；完整任务没有省略测试文件，用 `-vv --maxfail=10` 保留首批异常，最终运行执行到套件末尾。完整任务均设零自动重跑。[运行元数据](fix_r3/ci-final.json) 与逐任务日志绑定同一 headSha。

P1-01：Windows 数值计算运行库

独立入口不导入 GXR 平台句柄层，也不分配完整 LUT：两个线程各做 256 次 65536×3 矩阵乘法，NumPy 2.4.3 所带 OpenBLAS 0.3.31.dev 仍在 120 秒上限停住；逆矩阵入口通过。旧轮子设置 `OPENBLAS_NUM_THREADS=1` 的对照通过。见[旧运行库分离试验](https://github.com/aa2246740/gxr-studio/actions/runs/41558033437/job/125661593199)及 [ci-matrix-probes.log](fix_r3/ci-matrix-probes.log)。

同一 Windows runner 中只换为 NumPy 2.5.4 / OpenBLAS 0.3.34.106.0，使用默认 BLAS 设置，双工作线程和完整表均通过。旧轮子的成功对照与新轮子的 67108864 字节表 SHA-256 都是 `0f87d0cb7e25e7b1c9cf03a5a1a852ff819d773b6de41f21bd97b3836f5df92c`。见[运行库 A/B](https://github.com/aa2246740/gxr-studio/actions/runs/41559002510/job/125664785485)、[原始配置和表哈希](fix_r3/ci-runtime-update-probes.log)。

因此只在 Windows 锁定 NumPy 2.5.4，其他平台继续 2.4.3。保留两个 LUT 工作线程，没有更换颜色算法。2.5.4 的[官方发布时间](fix_r3/numpy-release.json)为 2026-10-10，满足仓库七天规则。最终 Windows 短任务和完整任务均使用默认 BLAS 设置通过。历史访问违规没有原生 C 栈，本轮独立复现的是同一矩阵路径停住；证据定位到旧 Windows 数值运行库组合，没有确定具体原生指令。

颜色用例现在对全部 16777216 个 RGB 输入逐字节比较精确表与生产 `_apply`，包括 1D shaper、3D LUT 和 V-Log 输出空间。原来的样本比较已扩大为全量比较。20 个引擎、颜色函数、表实现及引擎产物文件与基线逐字节相同，详见[源码清单](fix_r3/final-source-manifest.json)。默认开关仍为 false；关闭时不预热、不打开照片的现有测试通过。

P1-02：普通导入和哈希读取

旧 `open_rb` 先解析照片父目录，逐级打开时起点已经落在链接指向的位置。现在要求显式卡根，先以不跟随链接的方式打开卡根并核对 dev/ino，再按卡内相对路径逐级打开目录和文件。拒绝父级分量和卡根以下任何链接，不再解析照片父目录。导入与覆盖核对在扫描前保存卡根身份，普通暂存、已知文件哈希和核对哈希都传递该身份。DAT 读取也改用卡根入口。

Windows 盘符根目录没有末级名称，原卡根入口会把它作为空分量拒绝。现在文件系统根直接使用平台层的根句柄入口，随后继续核对身份和逐级打开。新增 Windows 原生用例比较盘符根 dev/ino，并从该句柄逐级读取 pytest 临时目录内的全部 256 种字节及控制字节。没有读取盘根中的其他文件。

`test_card_read_boundaries.py` 实际执行暂存和哈希：父目录原本是链接、扫描后被换成链接都拒绝，卡根替换也拒绝，暂存目录为空，目录外读取审计为空；另以全部 256 种字节、CRLF、0x1a 和 NUL 确认二进制内容完整。Windows 原生与 macOS 完整套件均通过。[r3 原读取反例复跑](fix_r3/extra-boundaries.json)记录 `swapped=true`、`staged_content=null`、`CardReadError`。

P2-01：离线守卫与事件循环

仅识别 CPython socketpair 退回函数的代码对象、事件循环 self-pipe 创建函数、该次客户端 socket 对象及监听 socket 的本机地址。普通本地 TCP、外部 TCP、直接调用退回 socketpair 和 DNS 仍拒绝。事件循环不会留下网络记录；每个测试开始和结束都清空记录。子 pytest 的真实两用例检查确认：前一个测试的联网记录导致该测试报错，后一个测试仍正常通过。Windows Proactor 原生入口与强制退回路径均通过。

FIX_R2 四项 Windows 遗留

| 项目 | 最终 Windows 原生证据 |
| --- | --- |
| `rename_at` 的 RootDirectory | 父目录改名并放入链接后，Ex 与强制 classic 两条分支都只替换已打开目录里的目标；目录外目标保留。 |
| `_delete_open` 的退回 | 文件、目录各强制 Ex 不支持，classic 使用同一对象句柄；只删除原对象，目录外内容保留。 |
| `listdir_fd` 的偏移 | 700 个长 Unicode 与非 BMP 名称跨多个 64 KiB 缓冲区，两次完整枚举集合和数量相同，验证偏移与 Restart。 |
| `lstat_at` 的 dev/ino | 相对句柄结果与原生路径 stat/lstat 比较文件、目录和链接身份；另建立真实目录联接并确认拒绝读取、只删除链接本身。 |

这些是 [tests/test_windows_io.py 的实际 Windows 运行](https://github.com/aa2246740/gxr-studio/actions/runs/41581601112/job/125737481285)，不再以宿主模型代替原生结果。原 r3 Windows 布局和控制流模型仍通过，证据层级单独保留在 [windows-contracts.json](fix_r3/windows-contracts.json)。

完整 Windows 套件揭示的其他问题

- Windows `st_ctime` 是创建时间，写完恢复 mtime 后旧内容证明仍可能被复用。新增按已打开句柄读取 FILE_BASIC_INFO.ChangeTime 的状态接口，内容核对、扫描状态和图库证明统一使用；保留 birthtime 和 dev/ino。原生测试验证结构大小 40、ChangeTime 偏移 24，以及恢复 mtime 后 ChangeTime 仍变化。原 r2 的持续修改和证明失效用例通过。
- NTSTATUS 的目录类型错误会被 Win32 转成拒绝访问，媒体接口因此选错错误分支。平台层保留 EISDIR/ENOTDIR 与原始 NTSTATUS；实际目录读取测试通过。
- 测试文本读写和 Node 输出显式使用 UTF-8，私有字节扫描与引擎文件清单统一用 `/`。二进制参数只缩短测试 ID，保留全部归档内容与断言；1731 个用例的最长 ID 为 243 字符。
- Windows 在子文件仍打开时拒绝目录移动。旧 r3 写入反例现在核实系统拒绝确实发生在改名处、源目录仍在、目录外没有文件，以及原文件和短写字节状态；若移动成功，继续原来的清空字节和错误内容断言。macOS 的实际移动路径仍通过，未跳过该组用例。
- 导出失败用例原来写死 `/proc/...`，在 Windows 会先得到路径不完整的错误。改为隔离临时目录中的普通文件加子路径，使各平台都实际触发建目录失败，并核对原文件字节保留。
- Git 在 Windows 默认将源文件转成 CRLF，导致锁定引擎的原始字节哈希不符；`.gitattributes` 固定文本检出为 LF，保留原哈希断言。校准、相机数据和 LUT 任务的 JSON 读写显式使用 UTF-8，修复系统代码页导致的校准不可用。
- 父进程终止用例在 Windows 88% 处停在 `stdout.readline()`，旧启动器创建下一层 Python 时未显式传递标准句柄；Windows 默认关闭普通句柄继承，PID 未进入测试管道。现在显式传递 stdout/stderr，子进程 stdin 指向空设备；PID 等待限 30 秒，另存启动 PID 与 stderr，失败时也回收父子进程和管道。最终 Windows 进程记录是启动器 648、实际父 Python 8028、worker 2040，worker 的 `getppid()` 为 8060；生产传入的父 PID 是 8028。Windows 虚拟环境启动器使 `Popen.pid` 和 `getppid()` 都不能直接代表本用例要终止的 Python 父进程。用例改为按生产 `GXR_STUDIO_PARENT_PID` 协议传入实际父 PID，记录启动器、实际父进程、worker 和 `getppid()`，强杀实际父进程后要求 worker 自行退出。导入终止用例也在就绪消息中报告 `os.getpid()`，对实际进程发出终止，保留 20 轮、25 次终止与恢复并记录全部 PID。独立存活检查声明 64 位 HANDLE 的完整 ctypes 签名。短任务先实际运行两个父进程生命周期用例及 25 次导入终止，完整套件仍保留这些用例。
- Windows 不使用 POSIX 的 `0600` 位表达访问控制。偏好文件用例在 POSIX 继续检查 `0600`，在 Windows 读取原生 DACL 与文件所有者 SID，要求所有者是当前用户或 Administrators，允许项只含当前用户、所有者、SYSTEM 和 Administrators；原偏好值、原子替换和临时文件断言均保留。
- 测试隔离同时设置 Windows 的 USERPROFILE、HOMEDRIVE、HOMEPATH、APPDATA 和 LOCALAPPDATA，使 `Path.home()` 与默认应用目录都指向测试目录。卷守卫的基路径也先转为同一平台的绝对路径，修复 Windows 事件路径带盘符而守卫仍使用 `/Volumes` 字符串的差异；真实 listdir/open 的拒绝断言全部保留，stat 用实际测试目录作正向控制。
- 启动脚本的语法测试原来在 Windows 调用 PATH 中的 WSL 占位 `bash.exe`，未安装发行版时直接失败。Windows 改为显式使用 Git for Windows 自带 Bash，保留同一脚本的语法、执行权限和参数传递断言，增加 30 秒上限；短任务和完整套件都执行这项测试。
- Windows Chrome 的 WebGPU 初始化需要先向 ANGLE 取得 D3D11 设备。测试让 ANGLE 使用系统 WARP 软件设备，再由 Dawn 选择 SwiftShader；快速入口要求适配器明确报告 SwiftShader，随后完整运行 13 组颜色对照。初始化失败时保留 stderr 与内部日志。生产引擎和着色器没有改动。
- 终止恢复用例等待实际提交或核对阶段后再终止子进程，取代固定等待；保留 20 轮与 25 次实际终止。Range 用例直接追踪 13 个生产媒体 fd 的 dev/ino 并要求全部释放；独立复审脚本的全进程 fd 核对仍保留，结果 7→7。

最终本机及复审复跑

本机 `make check`：1025 passed、706 skipped、0 自动重跑，覆盖率 89.88393977%（11462/12752 条，排除 317 条）。[回执](fix_r3/final-check-receipt.json)、[JUnit](fix_r3/final-check.xml)、[coverage.json](fix_r3/coverage.json)均保留。nice 10、串行，源码前后哈希相同。本机覆盖率的排除项含 Windows 专用分支，其运行证据见 Windows 原生任务。中间主动终止的检查和失败 CI 单独保留，不计入最终通过证据。

| 复审脚本 | 最终结果 |
| --- | --- |
| r2 media_root_race | 替换发生，读取拒绝，无目录外字节。 |
| r2 path_delete_race | 替换发生，原对象删除，目录外文件保留。 |
| r2 card_reader_retarget | 列目录与读开头绑定原句柄，只读自己文件。 |
| r2 lut_reimport_probe | key、ETag、表随颜色规范改变，生产函数对照相同。 |
| r2 http_boundary_extra | 根和中间链接拒绝；超长 Range 12 次 200，fd 7→7。 |
| r3 extra_boundaries | 新的普通导入读取拒绝；响应、写入、改名、同步异常的 fd 与临时文件检查通过。 |
| r3 windows_loop_guard | 实际事件循环建立成功，联网记录始终为空。 |
| r3 windows_contracts | 布局和宿主控制流模型通过；Windows 原生结果见上表。 |

八个 `final-r2-*` / `final-r3-*` 回执都绑定 `fb6bacc51a35ee56736f9af4de5aa624cfd4ac14`，源码哈希稳定。原始复审输入 34 个文件哈希未变。脚本所需接口和预期结果调整均有原始哈希及 `.diff`，没有修改冻结输入。

改动文件（相对交接 SHA，共 61 个）

- `.gitattributes`。
- `.github/workflows/ci.yml`。
- `docs/dependencies.md`。
- `pyproject.toml`。
- `scripts/private_bytes.py`。
- `scripts/windows_probe.py`。
- `src/gxr_studio/audit.py`。
- `src/gxr_studio/camdata/calib.py`。
- `src/gxr_studio/camdata/intake.py`。
- `src/gxr_studio/camdata/store.py`。
- `src/gxr_studio/cards/coverage.py`。
- `src/gxr_studio/cards/discovery.py`。
- `src/gxr_studio/cards/importer.py`。
- `src/gxr_studio/library/store.py`。
- `src/gxr_studio/lut/service.py`。
- `src/gxr_studio/osplat.py`。
- `tests/conftest.py`。
- `tests/g152_support.py`。
- `tests/gpu_support.py`。
- `tests/perf/measure_m1.py`。
- `tests/test_a1a_identity.py`。
- `tests/test_a1a_photos.py`。
- `tests/test_a1a_privacy.py`。
- `tests/test_a1a_review_r1.py`。
- `tests/test_a1a_review_r2.py`。
- `tests/test_a1a_review_r3.py`。
- `tests/test_api.py`。
- `tests/test_camdata.py`。
- `tests/test_camdata_api.py`。
- `tests/test_card_read_boundaries.py`。
- `tests/test_clone_coverage.py`。
- `tests/test_confirmation.py`。
- `tests/test_crop.py`。
- `tests/test_datcodec.py`。
- `tests/test_engine_knobs.py`。
- `tests/test_engine_render.py`。
- `tests/test_fix_review.py`。
- `tests/test_g152.py`。
- `tests/test_gpu_api.py`。
- `tests/test_gpu_frontend.py`。
- `tests/test_gpu_state.py`。
- `tests/test_hdr.py`。
- `tests/test_hdr_review.py`。
- `tests/test_import.py`。
- `tests/test_import_summary.py`。
- `tests/test_launcher.py`。
- `tests/test_lut.py`。
- `tests/test_lut_ident_r1.py`。
- `tests/test_lut_library.py`。
- `tests/test_lut_review_fix.py`。
- `tests/test_network_guard.py`。
- `tests/test_onboarding_ui.py`。
- `tests/test_platform_io.py`。
- `tests/test_polish_p2.py`。
- `tests/test_prefs.py`。
- `tests/test_render.py`。
- `tests/test_security.py`。
- `tests/test_web_frontend.py`。
- `tests/test_web_smoke.py`。
- `tests/test_windows_io.py`。
- `uv.lock`。

交付与边界

[SHA256SUMS](fix_r3/SHA256SUMS)覆盖报告、进度、最终源码清单、补丁、CI 日志、回执和复跑证据。任务临时目录、pytest 临时文件及浏览器 profile 的最终清理见 [cleanup.json](fix_r3/cleanup.json)。本机浏览器使用固定 Playwright 1.61.1 / Chromium Headless Shell 1228，并正常关闭。未访问真实存储卡、机主 Studio、真实图库或导出目录；公开提交只含代码、合成数据与依赖锁。

本轮证明宿主行为、Windows 原生文件系统 API 和 CI 软件显卡颜色路径。Windows D3D12 硬件显卡、真实 Windows 读卡器与 FAT32 卡、OneDrive 实际部署、掉电落盘、相机和固件设备层均未运行。

门槛结论：可以交复审。最终本地 SHA `fb6bacc51a35ee56736f9af4de5aa624cfd4ac14`；`ci/win-fix-r3` 的 Windows tests、macOS tests、check 均 success，Windows 短任务也 success。任务临时目录已清理，结果见附带实际回执；调试分支保留给机主核对后删除。
