不能合并

| 核实项目 | 判定 | 独立证据与边界 |
| --- | --- | --- |
| r2 P1-01，图库根目录在检查后被替换 | macOS 已关闭；Windows 运行待验 | 原反例的替换动作确实发生。`/raw`、带 Range 的 `/camera-jpg` 都返回 409；`/gpu` 返回 `raw=null`、`raw_reason=refused:link`，没有解析目录外 DNG。另测祖先目录替换、文件末级替换及已打开根目录被换名，结果符合句柄绑定。[原反例复跑](r2-replay/http-boundary-extra.json)、[补充反例](extra-boundaries.json)。 |
| r2 P1-02，LUT 删除重导入后复用旧表 | 已关闭，macOS 正式 API 实跑 | 两次记录仍均为 version=2，但 key、ETag、表 SHA-256 均不同。输入 `[64,128,192]` 重导入改为 Rec.709 后得到 `[42,112,194]`，与生产函数相同，不再得到旧表的 `[55,124,202]`。[结果](r2-replay/lut-reimport-probe.json)。 |
| r2 R2-P1-01，Windows 按路径删除 | 原路径实现已删除；Windows 原生验收未关闭 | 在当前共用上层代码上保留最后删除前的替换点，目录外文件保留，原目录里的文件被删除。Windows 删除/关闭的控制流模型通过，但本机执行的是 POSIX 原语，不能代替 Windows 调用。[复跑](r2-replay/path-delete-race.json)、[Windows 模型](windows-contracts.json)。 |
| r2 R2-P1-02，Windows 严格扫描的伪句柄 | 原伪句柄实现已删除；Windows 原生验收未关闭 | 在 fstat 后、listdir 前替换目录，生产 `read_head` 只读原目录的 `.DS_Store`；照片只有 `DCIM/100RICOH/OWN.JPG`。普通导入还有另一条未封闭的读取路径，列为本轮 P1-02。[复跑](r2-replay/card-reader-retarget.json)。 |
| r2 R2-P2-01，超长 Range 返回 500 并泄漏 fd | macOS 已关闭 | 5,000 位起点连续请求 12 次均为 200，fd 保持 7→7。另测超长终点、后缀长度、200/206/416 发送失败，以及 Response 构造失败，相关 fd 均关闭。[API 结果](r2-replay/http-boundary-extra.json)、[所有权检查](extra-boundaries.json)。 |
| Windows 句柄后端 | 静态声明及宿主控制流核对通过，原生运行未通过 | Microsoft 文档与声明布局匹配；删除退回仍使用同一对象句柄。Windows CI 未完成，不能据此确认 NTFS 上的实际行为。[核对结果](windows-contracts.json)、[文档来源](windows-sources.json)。 |
| f47572e 的 Windows CI | 未通过，阻塞合并 | push job 4m0s 后失败；PR job 40m26s 后结束，GitHub 注释明确记为超过 40m0s 上限。两者均停在精确 LUT 表相关计算。[checks](ci-checks-final.log)、[push 日志](ci-windows-job.log)、[PR 日志](ci-pr-windows-job.log)、[超时注释](ci-pr-windows-annotations.log)。 |
| macOS、颜色与默认开关 | 本轮抽查通过 | 隔离完整检查 1007 passed、697 skipped、0 failure/error，零自动重跑；覆盖率 90.11586663513833%。13 个合成 GPU 颜色用例通过。`gpu_preview` 默认 false，关闭时不打开照片、不预热表，前端不请求 GPU。[回执](make-check-final-receipt.json)、[JUnit](make-check.xml)、[汇总](verification-summary.json)。 |
| 删除 path-io 后的覆盖 | 共用上层行为有接续，Windows 原生执行仍缺证据 | 原路径专用用例换成共用原语用例，A1a 两组测试函数未减少。Windows 后端有 291 条源码行在覆盖率中排除，90.12% 不涵盖它；Windows 的关键原语测试排在本次停住的位置之后。[函数变化](test-surface-changes.json)、[覆盖率](coverage.json)。 |
| 新改动的读取边界与资源 | 新增补充问题 1 项；所测异常路径未见 fd 增长 | 图库读取和私有目录失败清理符合预期；普通导入仍会读取已换成链接的上级目录所指向的内容。这是本轮修改的函数保留的存量行为。[补充结果](extra-boundaries.json)、[历史代码](card-reader-history.json)。 |

对象是 PR #16 的 `f47572e6ac524400b79f6bebf986be368525e0a6`，分支 `feat/gpu-preview`；上一轮对象是 `72d9b44aa62d5133565117d533041bad9a76cdc5`，PR 基线是 `edf01457cb8d941cda877cf6f5a1f84cd5c38324`。本轮自行读取原反例、源码、完整检查及 GitHub 原始结果，未将实现者的通过记录作为验收结果。[开工记录](preflight.json)、[本轮差异](round3.diff)、[CI 绑定](ci-push-run-valid.log)。

本轮问题

| 编号 | 级别 | 结果 | 最小修正建议 |
| --- | --- | --- | --- |
| P1-01，Windows 完整运行未通过 | P1 | 原生 Windows 后端仍缺少通过证据；精确 LUT 表在一轮发生进程访问违规，在另一轮阻塞到超时。 | 先以短任务单独跑句柄原语并保留首个异常，再单独跑 LUT 表病例，定位原生计算失败；修好后让同一最终 SHA 的完整 Windows 任务通过。40 分钟上限及打印栈只让失败可见。 |
| P1-02，普通导入读取目录外内容 | P1 | 扫描后、打开前将照片目录换成链接，`stage_file` 成功暂存目录外 19 字节内容，未拒绝。 | 普通导入和核对哈希都应以已核对的卡根句柄加相对路径逐级打开，保留根身份约束；不要先解析照片父目录的 realpath。补“父目录已是链接”和“扫描后替换”的生产读取用例。 |
| P2-01，离线测试守卫拒绝 Windows 事件循环的本机连接 | P2 | 使用 CPython 在 Windows 选择的 socketpair 实现时，事件循环初始化被 `audit.forbid_network(True)` 拒绝；失败记录又保留到后续测试。 | 将事件循环自己创建的 socketpair 连接限定为可识别的本进程内部通道，继续拒绝其它连接；按测试隔离网络记录。先用 `-x -vv` 留下首个失败，避免只剩 F/E 进度条。 |

P1-01 的 CI 证据

| 运行 | SHA | Windows | macOS | check |
| --- | --- | --- | --- | --- |
| [push 41440256137](https://github.com/aa2246740/gxr-studio/actions/runs/41440256137) | f47572e6ac524400b79f6bebf986be368525e0a6 | [失败，4m0s](https://github.com/aa2246740/gxr-studio/actions/runs/41440256137/job/125260036857) | 通过，6m25s | 通过，7m46s |
| [PR 41440261853](https://github.com/aa2246740/gxr-studio/actions/runs/41440261853) | f47572e6ac524400b79f6bebf986be368525e0a6 | [40 分钟上限超时，job 含清理共 40m26s](https://github.com/aa2246740/gxr-studio/actions/runs/41440261853/job/125260056840) | 通过，6m39s | 通过，7m36s |

push 日志在 2026-11-02 11:56:49 UTC 记录 `Windows fatal exception: access violation`。两个 `gxr-lut-table` 线程位于 `lut/spaces.py:106 → lut/photo.py:84 → gpu/tables.py:67`，主线程等待 `display_lut_u8` 的结果，当前测试是 `test_gpu_api.py:176`。该运行的 Python 是 3.14.9。

PR 运行在 12:01:03 UTC 打印 5 分钟超时栈，主线程同样等待精确表，工作线程位于 `spaces.py:92/117`；最后在 12:33:22 UTC 被取消。API 的 conclusion 是 `cancelled`，检查注释明确写出超出 40m0s 上限。该运行使用 Python 3.14.10。因此这次上限确实生效，Windows 测试仍没有跑完。[原始注释](ci-pr-windows-annotations.log)、[运行元数据](ci-pr-run.log)。

两个栈把未完成的位置缩小到 `display_lut_u8 → _apply → spaces`。现有日志没有原生 C 栈，也没有逐项异常详情，尚不能确定底层原因是数组计算、线程、运行库还是另一处状态问题；没有证据把访问违规归因于 ctypes 声明。以下保留的 Windows 小入口将 I/O、事件循环和 LUT 分开，单次 120 秒打印栈并退出：[windows_runtime.py](windows_runtime.py)。该入口本轮未在 Windows 上运行。

本地 JUnit 中 `test_gpu_api` 位于第 967 至 1031 个用例，`test_platform_io` 位于第 1494 至 1506 个用例。CI 的已知停点在前一组，现有 Windows 日志不能证明后一组已经运行。Windows 锁、真实目录联接、CRT fd、删除退回和实际 dev/ino 比较仍须原生通过。

P1-02 的生产读取反例

位置是 [CardReader.open_rb:84](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/cards/discovery.py:84)，由 [stage_file:222](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/cards/importer.py:222) 和 `coverage.hash_card_file` 调用。

反例先保存 `DCIM/100RICOH/R0000001.JPG` 的目录信息；进入生产 `open_rb` 前把 `100RICOH` 改名，原位置放入指向另一个合成目录的链接。新实现先对 `p.parent` 调 `realpath`，因此之后逐级不跟随链接打开的起点已经是目录外位置。文件本身是普通文件，长度相同，读取前后状态相同，`stage_file` 全部核验通过。

原内容是 `OWN-SYNTHETIC-PHOTO`，实际暂存内容是 `OTHER-SYNTHETIC-PIC`，均为 19 B。实际暂存 SHA-256 是 `979b6ccfaf88e11286d0f433baec317059360f506b0f1d1eb19185951042cf9a`。没有附加读取来制造结果，观察的是生产 `stage_file` 写出的临时文件。[原结果](extra-boundaries.json)、[从全新副本再跑的结果](independent-selfcheck-extra-boundaries.json)。

这不是 f47572e 新增的回归。72d9b44 和 PR 基线的 `open_rb` 也只限制最后一级，先前没有封闭父目录替换。这里按当前读取边界的 P1 记录，不将它算作 r2 严格扫描旧反例仍然失败。当前 `test_card_file_open_refuses_a_linked_folder` 只断言末级文件链接被拒绝；对父目录链接只检查 `target.exists()`，没有调用读取并要求拒绝。[历史代码](card-reader-history.json)、[测试位置](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/tests/test_platform_io.py:175)。

P2-01 的因果链与证据边界

`tests/conftest.py` 全程打开 `audit.forbid_network(True)`，每个测试结束还要求全局 `network_attempts()` 为空。[audit._hook:168](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/audit.py:168) 拒绝所有 AF_INET `socket.connect`，只放行 Unix socket。

CPython 的 Windows Proactor 事件循环建立 self-pipe 时调用 `socket.socketpair()`；Windows 所用的标准库退回实现会先监听自己的 `127.0.0.1` 随机端口，再连接该端口。[CPython Proactor 源码](https://github.com/python/cpython/blob/3.14/Lib/asyncio/proactor_events.py)、[socketpair 源码](https://github.com/python/cpython/blob/3.14/Lib/socket.py)。

本轮在 macOS 上强制选择这同一个标准库函数，实际创建事件循环，得到 `PermissionError: offline: socket.connect`，网络记录从 0 增为 1。[脚本](windows_loop_guard.py)、[结果](windows-loop-guard.json)、[完整日志](windows-loop-guard.log)。这是可重现的守卫冲突，并能解释 CI 的部分 F/E 模式；没有 Windows 首个异常详情，不能把所有失败都归到它，也不能把它当成 LUT 原生计算问题的根因。这个测试配置问题同样早于本轮存在。

Windows 逐项核对

| 项目 | 源码核对 | 结论与证据层级 |
| --- | --- | --- |
| `UNICODE_STRING`、`OBJECT_ATTRIBUTES`、`IO_STATUS_BLOCK` | x64 大小分别为 16、48、16 B；Buffer 偏移 8，RootDirectory 偏移 8，ObjectName 偏移 16，Information 偏移 8。NTSTATUS 使用 Windows 的有符号 32 位 long。 | 固定 Windows 宽度的宿主 ctypes 布局检查通过，实际函数签名与 [NtCreateFile 文档](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntcreatefile) 一致。[结果](windows-contracts.json)。 |
| `FILE_FULL_DIR_INFO` | 六个 64 位字段后是 FileAttributes、FileNameLength、EaSize、FileName；长度偏移 60，文件名偏移 68。下一条以 NextEntryOffset 推进，首轮 Restart=15，后续=14，错误 18 结束。 | 声明与 [Microsoft 结构体](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_full_dir_info) 一致；宿主模型用两条含中文、非 BMP 字符的记录通过。缓冲在 Python bytes 中解析，未见用户态直接越界读取。 |
| 重命名结构与相对目标 | Flags/ReplaceIfExists 共用首字段，RootDirectory=父句柄，FileNameLength 为 UTF-16 字节数，FileName 是单个相对名。x64 字段偏移为 0/8/16/20。Ex 失败后将首字段置 1，用同一结构走 classic。 | 与 [FILE_RENAME_INFORMATION 文档](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information) 的相对名形式一致；布局检查通过。实际替换、共享、目录重命名仍待 Windows。 |
| 删除 Ex 不支持时退回 | 先以 DELETE 权限相对打开对象且不跟随重解析点，Ex flags=0x13；失败后用同一 h 调 classic，1 B BOOLEAN=1；再次失败即抛异常，finally 关闭 h。 | 与 [删除语义文档](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-_file_disposition_information_ex) 一致。宿主执行实际生产函数的成功、退回成功、两次失败三条控制流，均恰好关闭一次，无按路径退路。classic 的实际删除时机须 Windows 验证。 |
| 相对打开及重解析点 | 每次 NtCreateFile 的 RootDirectory 是父 HANDLE，名字拒绝分隔符及点段；设置 FILE_OPEN_REPARSE_POINT，随后按已打开对象查询属性，任意重解析点均拒绝。祖先逐级打开。 | 符合 [NtCreateFile 文档](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntcreatefile)；宿主控制流模型中链接、类型不符均拒绝并关闭。图库根路径先取 realpath 的行为已按 r2 时点实测。 |
| 原始 HANDLE 与 CRT fd 所有权 | `_open_checked` 查询或校验失败会关闭；`_to_fd` 失败会关闭，成功后交给 os.close；删除/改名的原始 HANDLE 在 finally 关闭；逐级目录旧 fd 被关闭。 | 宿主模型及 POSIX fd 计数未见泄漏；与 [CRT 所有权文档](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/open-osfhandle?view=msvc-170) 一致。Windows 原生计数未运行。 |
| `st_dev/st_ino` 与 os.stat 一致性 | `lstat_at`、根 fstat 均用 CPython `os.fstat`，没有自行拼造 inode。CPython 3.14 的 stat/fstat 都从卷标识、FileId 生成身份。 | [fstat 实现](https://github.com/python/cpython/blob/3.14/Python/fileutils.c)、[stat 实现](https://github.com/python/cpython/blob/3.14/Modules/posixmodule.c) 支持预期；本机不能给 Windows 实测结论。保留的小入口明确比较两者。 |
| 失败处理 | 不再有 `_PathPrivateDir`、`PathCardReader`、`GXR_FORCE_PATH_IO`。位置未知、重解析点、类型不符、NT 操作失败均抛错；删除/重命名只在句柄 API 内退回。 | 未发现新代码在失败后改用不受约束的完整路径操作。普通导入的提前 realpath 是上述单列问题。 |

r2 反例适配是否保留触发点

本轮从 r2 原始脚本生成副本，没有执行实现者的改编脚本。每个副本与原文件的差异、原文件 SHA-256 都在 [r2-replay](r2-replay/media_root_race.diff) 及相邻 `*.diff`、`*-input.json` 中；全部先前输入的哈希在 [prior-input-hashes.json](prior-input-hashes.json)。

适配包括临时/输出路径、将保护路径换成合成路径、删除已不存在的路径类和旧参数。图库根原绝对 open 条件保留，并增加新实现相对父 fd 打开根目录名时的条件；目录替换发生在真正 open 之前。删除仍在实际 unlink 前替换父目录；严格扫描仍在 fstat 后、生产 listdir 前替换，观察生产 read_head。所有对应替换标志都必须为 true，否则复跑入口报失败。LUT 仍使用上传、改空间、取表、删除、重传、再改空间的正式 API 顺序；Range 仍为实际 API 的 12 次请求。[入口](replay_r2.py)。

回归与颜色范围

最终完整检查在临时逐字节副本执行，306 个跟踪文件与被审工作树一致，前后均未改变；Git 状态为空。前端类型检查、构建逐字节核对、darwin/win32 mypy、公开字节及其它 make check 门槛均通过。完整命令耗时 524.99 秒，其中 pytest 494.57 秒，覆盖 11433/12687 条可计入语句，零自动重跑。[日志](make-check-final.log)、[覆盖率](coverage.json)、[源稳定性](source-stability.json)。

18 个 frontend/、GPU 源码及 engine.js 文件与 r2 逐字节相同。提交的 engine.js 为 37859 B，SHA-256 为 `4e284ab4cc5add892e4b834015458ee8957766bb545c69f644551556da4fa1eb`。[颜色源哈希](colour-source-stability.json)。

固定 Playwright 1.61.1、Chromium Headless Shell 1228，以 SwiftShader 参数运行 13 个合成 RAW/JPG、LUT、色调及几何用例，含两项先前合成反例，均过颜色门槛；显示类精确表的 67108864 B 长度、alpha 及 20004 个输入样本对照测试也通过。开关关闭的后端零打开/零预热测试及前端零 GPU 请求测试通过。[JUnit](make-check.xml)、[汇总](verification-summary.json)、[浏览器生命周期](browser-lifecycle.jsonl)。

697 个跳过项主要缺真实照片、DAT/标定及研究夹具；本轮没有补成整套私有输入回归。没有跑本轮 Metal 真实照片对拍、Windows D3D12 或 Windows 原生句柄验收，没有上卡或相机操作。源码相同和宿主模型通过都不能补这些执行记录。

执行记录与复跑

首次检查因隔离 HOME 下未准备 pnpm 缓存而停在前端检查；复制已经缓存的固定 pnpm 10.33.2 后继续。另一次运行被会话中断，日志停在 pylint，未生成完成回执。随后完整运行中，临时源码副本缺少 `.git` 标记，引出唯一一个夹具失败；添加仅用于该副本的空目录标记后，最终整套重新执行通过。所有首次日志与 JUnit 均保留，没有修改被审源来消除失败。[夹具记录](fixture-adjustment.json)、[首次完整结果](make-check-copy-initial.xml)、[最终回执](make-check-final-receipt.json)。

有一处执行偏离：开工时 5 个只读磁盘/文本预检命令曾并发且未设置 nice 10，超过用户要求的进程上限。之后计算入口均为 nice 10；没有并行 pytest、子代理、sleep 轮询、Git 写操作或 PR 评论。测试、缓存、源码副本、HOME 及浏览器临时状态均放在指定 Scratch 内。会话中断后先核对了残留进程与卷身份，才恢复工作。

下列入口已从另一个全新源码副本自检过。它核对卷 UUID、冻结 SHA 和源文件哈希，只在指定 Scratch 下创建新运行，拒绝复用旧名称，不改本报告目录。`extra` 的退出 0 表示探针完成；缺陷判定看 `ordinary_import_parent_change.read_other_directory`，当前为 true。[入口](reproduce.py)、[自检回执](independent-selfcheck-receipt.json)。

```bash
nice -n 10 /usr/bin/python3 -I -B /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_gpu_preview_r3/reproduce.py --case extra --run-name r3-extra-01
```

其余 `--case` 可选 `media_root_race`、`path_delete_race`、`card_reader_retarget`、`lut_reimport_probe`、`http_boundary_extra`、`windows-contracts`、`windows-loop-guard`，每次使用新的 `--run-name`。前五项分别重跑原 r2 反例；后两项是宿主模型，不是 Windows 验收。

指定临时根目录已删除，两个浏览器均经 `browser.close()` 正常退出，本轮浏览器进程与其测试监听端口均无残留。未访问机主的 Studio 端口及数据目录，未访问真实卡。[清理回执](cleanup.json)。全部交付文件的 SHA-256 见 [SHA256SUMS](SHA256SUMS)。

不能合并；P1 共 2 项；Windows CI 一轮失败、一轮达到 40 分钟上限超时；指定临时文件已清理。
