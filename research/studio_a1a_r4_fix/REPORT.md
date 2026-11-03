结论：已修好。根因是 reveal 测试改了整个进程的 `sys.platform`，不是 F_GETPATH；本地 `make check` 通过（727 passed，0 次重跑，覆盖率 91.55%）；在 macOS 上模拟 Linux 宿主，旧提交按 CI 一样失败，修好后全部通过。没有在真 Linux 上跑过。

# A1a 第 4 轮：Linux CI 上 reveal 三个用例失败

- 基线：`import-safety` 分支 126829b（PR #6），CI run 41243951681
- 改动文件：见 `changed-files.txt`（源码 3 个，测试 2 个）
- 没有做任何 git 写操作；没有访问存储卡、用户自己的工作室实例和数据

## 1. CI 上看到的现象

`evidence/ci-run-41243951681-failed.txt`（从 `gh run view 41243951681 --log-failed` 摘出来的）：

- `test_reveal_opens_only_the_file_this_export_wrote`、`test_reveal_of_a_batch_uses_the_first_exported_file`、`test_reveal_requires_the_file_and_macos` 三个用例失败，都在 `find(client, ...)` 里报 `StopIteration`：导入结束后图库里没有那张照片
- 汇总：3 failed, 580 passed, 142 skipped, 3 rerun；重跑一次以后还是失败
- 同一个文件里另外两个用例（off-macOS 501、拒绝导出目录外的文件）是通过的，这两个不需要先导入

## 2. 根因

reveal 测试用 `monkeypatch.setattr("gxr_studio.export.sys.platform", "darwin")` 来钉住"在访达中显示"的平台判断。`gxr_studio.export.sys` 就是 `sys` 模块本身，所以这一句改的是整个进程的 `sys.platform`，不只是 export 里的判断。

导入卡时，挂载会话会反复核对挂载指纹（卡根 dev/ino、f_fsid、设备名）。`VolumeProbe.statfs` 原来按 `sys.platform == "darwin"` 选实现：

- 在 Linux CI 上，它于是按 macOS 的 `struct statfs` 布局调用 glibc 的 `statfs`（`_darwin_statfs_fn` 拿到的是 glibc 的同名函数）
- glibc x86-64 结构体偏移 48 处是 `f_ffree`（空闲 inode 数），正好是 macOS 结构体里 `f_fsid` 的位置
- 导入一写文件，空闲 inode 数就变，"f_fsid"跟着变 → 会话核对认为换了挂载 → 导入按设计中断，一张都不进图库 → 测试在图库里找不到照片，报 `StopIteration`

所以 Linux 上的安全核对并没有坏：它看到"指纹变了"，就按规则停下了。只是这个"变了"是测试改 `sys.platform` 造出来的假象。

## 3. 为什么不是 F_GETPATH

- `privacy.fd_path` 拿不到 `fcntl.F_GETPATH` 时，会去读 `/proc/self/fd/<fd>`（Linux 上走的就是这一支），之前就有
- 同一次 CI 里，用到 `PrivateDir` 和 `fd_path` 的导出、隐私类用例都通过了（580 passed）
- 失败的三个用例都是在导入那一步就没拿到照片，还没走到导出写文件

## 4. 修法

只改"按哪种平台选实现"的依据，安全逻辑一行没动：

| 文件 | 改动 |
| --- | --- |
| `src/gxr_studio/cards/session.py` | 新增 `HOST_IS_DARWIN = os.uname().sysname == "Darwin"`，在导入模块时按内核报告的系统名定一次；`VolumeProbe.statfs` 按它选 statfs 布局，不再看 `sys.platform`。Linux 上照旧用 `os.statvfs` 的 `f_fsid` |
| `src/gxr_studio/privacy.py` | `_exchange_at`（renameatx_np）和 `_full_sync`（F_FULLFSYNC）同样改看 `_HOST_IS_DARWIN`。这两处在 Linux 上本来就会退回通用写法，改它们是为了以后测试改 `sys.platform` 也带不偏 |
| `src/gxr_studio/export.py` | 新增 `_host_is_macos()`，reveal 只问它。真实运行时行为不变：仍然是"不是 macOS 就返回 501" |
| `tests/test_export_reveal.py` | 改成替换 `export._host_is_macos`，不再改整个进程的 `sys.platform`（和 1407830 一样的思路：测试只替换自己要测的那个判断） |
| `tests/test_a1a_platform.py`（新增） | 2 个同类用例，见第 5 节 |

## 5. 先失败的同类用例

`tests/test_a1a_platform.py`：

1. `test_patched_sys_platform_does_not_change_the_fingerprint`：把 `sys.platform` 改成另一种系统以后，同一个挂载的指纹不变
2. `test_linux_host_with_platform_patched_to_darwin_still_imports`：在 macOS 上复现 CI 的情形——宿主当作不是 macOS、libc 的 statfs 按 glibc 布局填结构体（空闲 inode 数随文件数变化）、`sys.platform` 被改成 darwin——导入必须照常完成，R0000102 进图库

在旧源码上这 2 个都失败（`evidence/regression-before-fix-platform.log`：2 failed），修好后通过。

## 6. 安全语义没变：核对不了就不写卡、不报全部导入

- Linux 上没有 `diskutil`：卷 UUID 读不到，记为 `missing`，`SEEN_TRUST_UUID` 默认关，不会因为 UUID 把卡当成"见过的那张"
- Linux 上 `statvfs` 失败、卡根不是目录或是链接：拿不到指纹，会话作废，导入中断，不会报"都已导入"，也不会显示"可以推出"
- 指纹真的变了（换卡、重新挂载）：会话作废，和 macOS 一样
- 卡根写保护（审计钩子）、图库位置核对、`PrivateDir` 的 fd 复核都不看平台，Linux 上照样生效

上面这些没有在 Linux 上关掉任何一项。模拟 Linux 宿主时（第 7 节），A1a 全部安全用例（卡身份、照片覆盖、隐私路径、导入、r1/r2/r3 复审同类用例）一共 220 个都通过，拒绝类用例照样拒绝。

## 7. Linux 怎么确认的

**没有在真 Linux 上跑。** 本机有 Apple Container，但缓存里没有带 Python 3.12+ 和 numpy/scipy 的镜像；装依赖要联网，那些镜像也属于别的工作，所以没用。

改为在 macOS 上模拟 Linux 宿主：`evidence/linux_sim_plugin.py` 是一个只用于这次复核的 pytest 插件（不进仓库），它把 `session.HOST_IS_DARWIN`、`privacy._HOST_IS_DARWIN` 设为 False，并把 libc 的 statfs 换成 glibc 布局（空闲 inode 数随测试临时目录里的文件数变化，和 Linux 上一样）。结果在 `evidence/linux-simulation.log`：

| 跑的是什么 | 结果 |
| --- | --- |
| 旧提交 126829b，模拟 Linux，reveal 5 个用例 | 3 failed（都是 StopIteration，和 CI 是同样三个）、2 passed，和 CI 完全一致 |
| 修好后的工作区，模拟 Linux，reveal 5 个 + 新增 2 个 | 7 passed |
| 修好后的工作区，模拟 Linux，A1a 安全用例 | 220 passed |

第一次写的模拟太严（每次调 statfs 都变），得到的是 404 card_not_found 而不是 CI 的现象；改成"建文件才变"以后，和 CI 的失败一模一样，才拿来做对照。

真 Linux 上通过与否，以推送后 CI 的结果为准。

## 8. 只能在 macOS 上跑的用例

这一轮不需要新加 skip：新用例和改过的 reveal 用例都不依赖宿主。CI 上的 142 个 skipped 是原来就有的跳过条件，这一轮没加也没改。

## 9. 本地 make check

`evidence/make-check.log`，09:13:50 开始，09:24:27 结束，前台等完：

- 退出码 0
- 727 passed，3 warnings，实际重跑 0 次（Makefile 第 22 行的 `--reruns 1` 是原来就有的，这一轮没加也没改）
- 覆盖率 91.55%（门槛 85%）
- private bytes：检查了 241 个文件，通过
- ruff、format、mypy（91 个文件）、秘密扫描、bandit（只有 nosec 提示）、死开关、大文件、openapi、import 约束、deptry、vulture、pylint 重复代码都通过

这次跑了 10 分 23 秒，比平时慢，因为当时机器负载约 12。

## 10. 复审脚本

复审目录都只读，没有改动。在项目根目录下跑 `shasum -a 256 -c research/<目录>/SHA256SUMS`：

- `review_studio_a1a_r2`：94 项，0 处不一致
- `review_studio_a1a_r3`：59 项，0 处不一致
- `review_studio_a1a`（第 1 轮）：261 项，36 处不一致，全部是这份清单里一起记下的 studio 源码和测试（`studio/src`、`studio/tests` 等），也就是第 1 到 4 轮修复改过的文件；复审目录自己的文件 0 处不一致

- r3（`research/review_studio_a1a_r3`）：41/41 通过
- r2（`research/review_studio_a1a_r2`）：144 passed、3 failed。其中 2 个是上一轮已经单独列出、按你的决定保持拒绝的情形；第 3 个 `test_staged_reads_real_blob[changed_work_file]` 是新出现的，原因是你提交了 README 以后，工作区的 README 和 HEAD 一样了，这个用例"工作区文件和暂存的不同"的前提不再成立。不是回归，代码没动这一块

## 11. 临时文件

临时目录 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-a1a`（复审脚本镜像、旧提交检出、模拟和检查日志）已删除。需要留的日志都已经复制到 `evidence/`。
