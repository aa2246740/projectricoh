# FIX_R2：显卡预览复审 r2 的修复

**能交复审，但 Windows 部分有条件。** 复审 r2 的 4 项 P1 和 1 项 P2 都改了，复审的 5 个反例脚本（改编版，见第 7 节）在新代码上都不再复现。
`make check`：全部通过：lint、两遍 mypy（darwin + win32）、bandit、前端构建逐字节核对、OpenAPI 核对、import-linter、deptry、vulture、pylint，测试 1007 passed、697 skipped、0 rerun，覆盖率 90.12%（日志 `fix_r2/make-check.log`）。

**条件**：Windows 现在走一套新写的句柄后端（`osplat` 里的 ctypes 调用 `NtCreateFile` 等）。它在本机只做过 `mypy --platform win32` 和逐行复核，
**没有在任何 Windows 机器上运行过**。如果 windows-latest 上 `tests/test_platform_io.py` 等测试失败，最可能的原因在这套后端（见第 6 节"遗留"）。
请推送后重点看第 5 节列出的测试。

工作树 `/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview`（HEAD `72d9b44`），没有任何 git 写操作。改动 12 个文件（相对 `72d9b44`），见第 8 节。

---

## 1. 一览

| 编号 | 改了什么 | 证明它的测试 / 复跑 |
| --- | --- | --- |
| P1-01 图库根目录被替换 | `open_media` 先取 realpath，再从文件系统根逐级不跟随链接打开（`osplat.open_dir`：根目录本身和每一级祖先都在内），任何一级变成链接都失败；位置核对改到已经打开的根目录句柄上（句柄的真实位置 = 那个 realpath，且 `is_local`），之后的子目录、文件、Range 发送和 RAW 布局解析都绑定这个句柄 | `test_platform_io.py::test_media_refuses_when_the_library_root_or_an_ancestor_becomes_a_link[root / parent_of_root]`、`test_media_reads_through_the_handle_it_checked`、`test_media_refuses_a_library_root_outside_the_allowed_place`、`test_gpu_api.py::test_open_media_refuses_a_file_replaced_by_a_link_at_open`；改编复跑 `media_root_race.py`、`http_boundary_extra.py` |
| P1-02 LUT 删除后重新导入 | `render_token` 改为 cube 内容（cube_id = SHA-256）加完整色彩规范（`target()` 用到的 6 个空间字段）的哈希，不再用会从头再数的记录 version；新增 `target_and_token()`，表和标识来自同一次读取；服务器缓存键、表的 ETag、前端的 LUT 键、缩略图和预览地址用的都是这一个标识 | `test_gpu_api.py::test_lut_delete_reimport_and_space_change_get_a_new_table`（换回旧公式后失败：重新导入后 12 个样本值里 10 个与生产函数不符）、`test_render_token_follows_the_colour_spec_not_the_record_version`；改编复跑 `lut_reimport_probe.py` |
| R2-P1-01 Windows 删除越界 | 删掉按路径的 `_PathPrivateDir`。`PrivateDir` 两个平台同一套实现，只通过 `osplat` 的按句柄原语操作；Windows 的删除是"以父目录句柄为根打开要删的那个对象（不跟随重解析点）→ 按这个句柄删除" | `test_platform_io.py::test_delete_after_the_parent_became_a_link_never_touches_the_outside`、`test_delete_when_the_parent_is_already_a_link_is_refused`、`test_rmtree_deletes_links_themselves_not_their_targets`、`test_write_and_read_stay_inside_when_the_parent_becomes_a_link`；改编复跑 `path_delete_race.py` |
| R2-P1-02 Windows 读卡伪句柄 | 删掉 `PathCardReader`。`CardReader` 两个平台同一套：严格扫描的目录句柄是真句柄，列目录（Windows 按句柄 `GetFileInformationByHandleEx`）、看属性、读开头都相对这个句柄 | `test_platform_io.py::test_strict_scan_lists_the_directory_it_opened`、`test_card_file_open_refuses_a_linked_folder`；改编复跑 `card_reader_retarget.py` |
| R2-P2-01 Range 数字和 fd | Range 正则限定每个数字最多 20 位，更长的头按"看不懂"处理（发整个文件，200）；`FdResponse` 构造失败时立刻关闭 fd | `test_gpu_api.py::test_huge_range_numbers_do_not_crash_or_leak`（5,000 位起点、终点、后缀长度各 3 次，全是 200，fd 不增长；20 位的起点是 416）、`test_fd_is_closed_when_the_response_cannot_be_built`；改编复跑 `http_boundary_extra.py` |

## 2. 设计：去掉"按路径"的实现

复审 r2 的两个 Windows 反例同源：Windows 那条实现只保存路径，核对之后再按路径操作。只要还按路径做，就一定剩一段空隙。
所以这轮不再修补路径实现，而是给 Windows 做一套真正的目录句柄原语，让 `PrivateDir`、`CardReader`、`library.media` 在两个平台走同一套上层代码：

| 原语（`osplat`） | POSIX | Windows |
| --- | --- | --- |
| `open_dir(绝对路径)` | 从 `/` 逐级 `open_dir_at` | `CreateFileW` 打开盘符/共享根，之后逐级 `open_dir_at` |
| `open_dir_at(dfd, 名字)` | `os.open(O_DIRECTORY\|O_NOFOLLOW, dir_fd)` | `NtCreateFile`，`RootDirectory` = 父句柄，`FILE_OPEN_REPARSE_POINT`；打开后是重解析点就拒绝（ELOOP） |
| `open_file_at(dfd, 名字, create=)` | `O_NOFOLLOW`（新建：`O_CREAT\|O_EXCL`） | 同上，`FILE_NON_DIRECTORY_FILE`，新建用 `FILE_CREATE` |
| `lstat_at` | `os.stat(follow_symlinks=False, dir_fd)` | 相对打开（不跟随）后 `os.fstat` |
| `listdir_fd` | `os.listdir(fd)` | `GetFileInformationByHandleEx(FileFullDirectory[Restart]Info)` |
| `mkdir_at` | `os.mkdir(dir_fd)` | `NtCreateFile(FILE_CREATE, FILE_DIRECTORY_FILE)` |
| `unlink_at` / `rmdir_at` | `os.unlink` / `os.rmdir(dir_fd)` | 相对打开要删的对象（不跟随）→ `NtSetInformationFile(FileDispositionInformationEx)`，不支持时退回 `FileDispositionInformation` |
| `rename_at(dfd, 旧, 新)` | `os.rename(src_dir_fd, dst_dir_fd)` | 相对打开源 → `FileRenameInformationEx`（`RootDirectory` = 父句柄，替换已存在的目标），不支持时退回 `FileRenameInformation` |

- **句柄**：一律是整数 CRT fd（Windows 用 `msvcrt.open_osfhandle` 包装目录句柄），`os.close`、`os.fstat`、`osplat.fd_path` 都能直接用。
- **审计**：Windows 的这些调用不经过 `os.*`，原语里自己发出同名的审计事件（`open`、`os.mkdir`、`os.remove`、`os.rmdir`、`os.rename`、`os.listdir`），`audit` 的写保护照常生效。POSIX 打开文件时设 `audit.relative_to(dfd)`，相对名的 `open` 事件按句柄的真实位置记录。
- **测试接缝**：凡是模拟竞态的测试都挂在这些原语上（不挂 `os.open` / `os.unlink`），两个平台都会触发。

`GXR_FORCE_PATH_IO` 和 CI 的 `path-io` 任务一并删除：已经没有单独的路径实现可测。

## 3. P1-01 细节

- 改编复跑 `media_root_race.py`：在新实现真正打开根目录的那一步，把根目录换成指向外面的链接，结果是 `MediaRefused:link`，不返回外部字节。
- 改编复跑 `http_boundary_extra.py`：
  - 根目录被替换后，`/raw` 和 `/camera-jpg`（Range `bytes=0-6`）都回 409；
  - `/gpu` 的布局 `raw=null`、`raw_reason=refused:link`，没有解析外部 DNG；
  - 中间目录换成链接时三个接口都拒绝；
  - 5,000 位 Range 发 12 次全是 200，fd 增长 0。
- 根目录句柄核对之后再被换掉：读取仍然绑定这个句柄，读到的是图库里的字节（`test_media_reads_through_the_handle_it_checked`）。

## 4. P1-02 细节

改编复跑 `lut_reimport_probe.py`：
- **key**：删除前 `…-73f97f4ca946f3fa`，重新导入并改 Rec.709 后 `…-d3bb40de9f5fce26`，不同；
- **表**：SHA-256 不同；
- **样本**：`[64,128,192]` 的表值 `[42,112,194]`，等于当前生产函数的输出；复审时是旧值 `[55,124,202]`。

同样的内容和同样的规范得到同一个标识，所以重新导入后改回原规范能复用旧表，这是正确的。

## 5. Windows：请在 CI 实跑结果里重点看

本机没有 Windows。以下测试在 windows-latest 上跑的是新写的 Windows 原语，最能暴露问题：

1. `tests/test_platform_io.py` 全部，其中最基础的是 `test_handle_primitives`（逐个原语：不跟随链接、排他新建、替换式改名、按句柄删除、按句柄列目录、名字校验）。它要是失败，后面多半跟着失败。
2. `tests/test_a1a_review_r2.py`（私有目录在操作途中被移走的整组）、`tests/test_a1a_privacy.py`、`tests/test_fix_review.py::test_interrupted_fallback_swap_is_recovered_at_startup`（Windows 走两步换法）。
3. `tests/test_gpu_api.py` 中照片文件相关的测试（链接拒绝、Range、大文件），`tests/test_import.py`、`tests/test_a1a_photos.py`（读卡严格扫描、按句柄读卡文件、读取审计）。
4. 锁和并发：`test_platform_io.py::test_lock_conflicts_between_two_handles_and_releases`、`test_two_processes_replacing_the_same_file_leave_one_whole_copy`，以及 `test_fix_review.py` 里的锁冲突测试。
5. `os.symlink` 在 runner 上要能建目录链接（GitHub 的 Windows runner 是管理员，应可用）；如果报权限错误，是环境问题，不是被测代码的问题。

## 6. 遗留（需要后续接手）

- **Windows 后端从未运行过。** 全部是盲写：ctypes 结构体布局、`NtCreateFile` 相对打开、`NtSetInformationFile` 删除/改名、按句柄列目录。下面几处是我最没把握的，CI 失败时先查：
  - `rename_at`：`FILE_RENAME_INFORMATION` 的 `RootDirectory` 用父目录句柄，目标名是相对名；
  - `_delete_open`：带 POSIX 语义的 `FileDispositionInformationEx` 不支持时的退回路径；
  - `listdir_fd`：`FILE_FULL_DIR_INFO` 的偏移（文件名在第 68 字节，长度在第 60 字节）；
  - `lstat_at` 用 `os.fstat` 取到的 `st_dev` / `st_ino`，要和 `os.stat` 一致（读卡严格扫描拿它核对卡根身份）。
- **重解析点一律当链接拒绝**，包括 OneDrive"按需下载"的占位文件。图库或私有目录放在这类位置时会被拒绝：照片接口回 409，前端退回服务器出图；私有目录拒绝写入。这是有意的保守选择，没有在实机确认影响面。
- **Windows 上目录不单独落盘**（`sync_dir` 是空操作），与上一轮相同。
- 上轮遗留仍然有效，这轮没有处理：WebGPU 走 D3D12 的硬件路径没有实测；Windows 上的「在访达中显示」和读卡器卷枚举本来就不可用。
- 复审 r2 记录的偏离（`make check` 的 import-linter 会更新工作树里既有的忽略缓存）这轮同样存在，没有改 Makefile。
- 这轮没有重跑真实照片的颜色对拍：颜色路径（着色器、精确表）没有改动，只改了 LUT 表的标识。

## 7. 复审 r2 的 5 个脚本

原脚本把临时目录写死在复审自己的 scratch 下；有两个直接引用了已删除的类（`_PathPrivateDir`、`PathCardReader`），在新代码上会以导入错误结束，这不算"修好"。
所以在 `research/studio_gpu_r1/fix_r2/` 放了改编版：临时目录换成本轮的 scratch；触发点保留复审原来的位置，另外加上新实现真正打开的那一步，否则钩子在新代码里不会触发。
结果 JSON 在同一目录：

| 脚本 | 结果 |
| --- | --- |
| `media_root_race.py` | 替换确实发生（`swapped=true`），结果 `MediaRefused:link`，没有外部字节 |
| `http_boundary_extra.py` | 见第 3 节：409 / 409 / `refused:link` / 中间目录 409 / Range 12 次 200、fd +0 |
| `lut_reimport_probe.py` | `same_key_after_delete_reimport=false`、`same_table_after_space_change=false`、`wrong_current_table=false` |
| `path_delete_race.py` | 替换发生；外部文件保留；被删的是已移到私有目录里 `b.saved` 下的自己那份（与复审的 Unix 对照一致），没有报错 |
| `card_reader_retarget.py` | 替换发生；只读到自己的 `.DS_Store`，没有外部字节；照片只有 `DCIM/100RICOH/OWN.JPG` |

这些是在 macOS 上跑的 POSIX 原语。Windows 原语对应的是第 5 节那组测试，同样的竞态由 CI 在 windows-latest 上跑。

## 8. 改动文件（相对 `72d9b44`）

| 文件 | 内容 |
| --- | --- |
| `src/gxr_studio/osplat.py` | 按目录句柄的原语（POSIX + Windows NT），删掉 `USE_PATH_IO` |
| `src/gxr_studio/privacy.py` | `PrivateDir` 改用原语；删掉 `_PathPrivateDir`、`_routed`、按平台分派 |
| `src/gxr_studio/cards/discovery.py` | `CardReader` 改用原语；删掉 `PathCardReader`；条目先判链接再判目录 |
| `src/gxr_studio/library/media.py` | 根目录逐级不跟随打开 + 句柄位置核对；Range 位数限制；构造失败关闭 fd |
| `src/gxr_studio/lut/library.py` | `render_token` 按内容 + 规范；`target_and_token` |
| `src/gxr_studio/api/gpu_routes.py` | `/table` 用 `target_and_token` |
| `tests/test_platform_io.py` | 重写：复审 r2 的竞态 + 原语测试，钩子挂在原语上 |
| `tests/test_gpu_api.py` | LUT 重新导入、标识、Range、fd 关闭；链接替换测试改挂原语 |
| `tests/test_a1a_review_r2.py` | 恢复上一轮之前的版本，mkdir 那条的钩子改挂 `osplat.open_dir_at` |
| `tests/test_fix_review.py` | 断电模拟改挂 `osplat.rename_at`；源码检查改成新写法 |
| `.github/workflows/ci.yml` | 删掉 `path-io` 任务 |
| `docs/architecture.md` | 平台层一节按新设计重写 |

研究目录（不进 gxr-studio）：本文件、`fix_r2/` 下 5 个改编脚本和它们的结果 JSON。

## 9. 进程与清理

- 最多 2 个计算进程，都用 `nice -n 10`，没有超过 30 分钟的单次运行；
- 临时目录 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r2/` 结束时已删除，工作树里的 `__pycache__` 和 `.coverage` 已删除；
- 没碰机主的工作室和卡，没开子代理，没用 sleep 轮询。
