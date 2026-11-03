可以复核：第 3 轮复审的 R3-P1-01、R3-P1-02、R3-P2-01 已连同同类情况一起修复；本轮复审的 41 例全部通过，上一轮 147 例保持 145 通过（剩下 2 例是已知的取行前提问题）；前台完整 `make check` 退出 0，725 例全部一次通过，覆盖率 91.56%。

# A1a 第 3 轮复审的修复报告

对象：独立仓库 `studio/`，HEAD `1407830ee7c32fff892b23f2ddbfeb2bafd95b45`，相对 HEAD 的全部工作区改动（`changed-files.txt`，56 个文件；本轮新增 4 个、修改 6 个，见第 5 节）。
依据：`research/review_studio_a1a_r3/REVIEW.md`。开工前核对过：本轮复审目录 `SHA256SUMS` 59 项一致；上一轮实现清单
`research/studio_a1a_r2_fix/SHA256SUMS` 63 项一致（复审看的就是当时的工作区）。

没有做 git 写操作，没有开子代理，没有碰存储卡、用户图库或工作室实例。同一时间最多 2 个测试进程，都在前台阻塞等待。

## 1. 数字

| 检查 | 结果 | 日志 |
|---|---|---|
| 本轮复审 41 例（`test_r3.py`、`test_samples.py`，只读运行） | 修复前 27 通过、14 失败（与复审记录相同）；修复后 **41 全部通过** | `evidence/review-r3-suite-before-fix.log`、`evidence/review-r3-suite-after.log` |
| 上一轮复审 147 例 | **145 通过、2 失败**；2 例是已知的取行前提问题（第 3 节） | `evidence/review-r2-suite-after.log` |
| 本轮新增同类用例 `tests/test_a1a_review_r3.py` | 修复前 36 失败、8 通过（第 4 节）；修复后 **44 全部通过** | `evidence/regression-before-fix-r3-own.log`、`evidence/regression-before-fix-zip-stub.log`、`evidence/zip-unlisted-bytes-check.log` |
| 完整 `make check`（前台阻塞等待，新生成） | 退出 0；**725 passed**、0 failed、0 次重跑；覆盖率 **91.56%**；lint、format、mypy strict（91 个文件）、bandit、秘密扫描、私有字节检查（仓库加 `uv build` 分发包共 240 个文件，无误报）、大文件、OpenAPI、import-linter、deptry、vulture、pylint 全部通过。2026-11-01 05:06:48 至 05:16:11（UTC+8） | `evidence/make-check.log` |

`make check` 里的 `--reruns 1` 是开工前 Makefile 就有的（AGENTS.md 写成 CI 规则），没有去掉；本次日志里没有任何重跑。
覆盖率 91.56% 比上一轮的 91.61% 低 0.05 个百分点（新增的拒绝分支里有少数只在真机上才会走到的出错路径），仍高于开工时的基线约 91.1% 和仓库门槛 85%。

## 2. 逐项修法（连同同类情况）

### R3-P1-01 启动本身写卡

新增 `library/location.py`，在**第一次写图库之前**核对图库的真实位置：

- `card_roots(volumes_roots)`：只读地找出当前插着的卡（卷根下有 DCIM 目录、或卡根有 GXRCE.DAT 的目录），不打开文件、不登记任何东西。
- `check_library_location(root, cards)`：
  - 图库根解析链接以后，不能在任何卡根里（也包括已登记写保护的目录）；
  - 图库自己会写的每个位置——`.studio`、`index.sqlite` 及其 `-journal`/`-wal`/`-shm`、`studio.lock`、`import-log.jsonl`、`thumbs`、`staging`、`tmp`——
    解析链接以后都必须还在图库根里；指到卡上或图库外面一律拒绝。
- 接入点：`LibraryLock.acquire()`（建 `.studio`、建锁之前；锁文件另加 O_NOFOLLOW）、`Library.open()`（建目录、清临时目录、打开 SQLite 之前）、
  `create_app`（把只读找到的卡根交给 `Library`）、`cli.main`（拿锁前先找卡根）。`Library.is_local` 也把这些卡根算进去，启动之后、第一次扫卡之前的写入同样受约束。
- 拒绝时：抛 `LibraryLocationRefused`，一个字节都不写。命令行启动打印三行——"无法打开图库。图库文件夹（或其中的 .studio）在存储卡上，或经过链接指到了图库以外的位置。"
  "请把图库放在电脑上的普通文件夹里，再重新打开工作室。""位置：…"——并以退出码 78 结束；启动窗口（`GXR Studio.command`）遇到非 0 退出会停住，让人看到这段说明。不会静默退出，也不会绑定端口。
- 对照：图库放在卷根下的普通外接盘上（没有 DCIM，不是卡）照常打开。

### R3-P1-02 多段压缩首段是归档

- 去掉"拼接结果是归档就直接返回内层成员"的提前返回。多段压缩流（gzip、bzip2、xz、zstd）的**每一段都单独跑完整的 `scan_bytes`**，再检查一次拼接后的内容；只有一段时就检查这一段。
- 同类情况：
  - **tar 结束之后的字节**（例如 `cat notes.tar camera.dat`，或在一个压缩段里 tar 后面紧跟别的内容、两个 tar 首尾相接）：解 tar 时看不到，单独当成员检查。
  - **zip 里没有成员占用的字节**（第一个成员之前、成员之间、结束记录之后）：按本地头、数据、数据描述符、中央目录和结束记录算出占用区间，剩下的区间单独当成员检查；算不清布局报 R0。
  - **前面带着别的字节的 zip**（例如自解压脚本）：以前只认开头是本地头的 zip，这种会被当成普通字节，压缩在成员里的受限内容看不到（上一轮就存在）。
    现在末尾有结束记录、而且 zipfile 真的能打开时按 zip 检查，前面那段作为未占用字节一起检查；打不开的照常当普通字节，不会多出 R0。
- 归档、压缩容器的原始字节（压缩数据、tar 头）不再按"二进制里含魔数"去匹配：内容检查做在成员、每一段、tar 之后的字节、zip 未占用的字节上，这些合起来覆盖容器里的全部内容。
  这也消除了改动过程中出现的一个误报（sdist 的 tar 里有源码字符串字面量）。仓库和分发包 240 个文件无命中、无 R0。

### R3-P2-01 打开之后、写字节之前移动目录

- `PrivateDir.write`：每次 `os.write` **之前和之后**都核对实际的父目录 fd，写完 fsync 后再核对一次。
- 发现目录已经换了位置：把这个文件里已经写进去的字节清空（`ftruncate` 到 0，只动自己打开的文件），**不再对已移走的目录做删除、改名等目录操作**，然后抛 `PrivatePathError`。
  错误信息写清楚结果，例如"已把写进去的字节清空，那里留下一个 0 字节的文件：<路径>（不再对已移走的目录做删除等操作）"；清空失败也照实写出原因。
- 这样处理是因为：复审的用例在 `os.write` 调用里面、真正写字节之前移动目录，调用之前的核对看不到这次移动；写完立刻核对并清空，保证移走的目录里不留私有字节。
- `replace_file` 走同一个 `write`，也覆盖。

## 3. 上一轮 147 例里的 2 例（已知前提问题）

`test_library_directory_points_to_card_source[jpg]`、`[avi]` 仍停在复审用例第 251 行的空表取首行：按用户决定，图库日期目录链到卡上时保持"拒绝"，不写也不登记，所以没有可取的行。
后面的断言"卡不变、不报全部导入"由本仓库的同类用例证明，在最终工作区上重跑全部通过（`evidence/equivalent-tests-r2-premise.log`，8 例）：
`test_r2_library_writes_resolve_real_location`（年目录、日期目录、文件链接 × 照片、视频）、`test_r2_library_copy_must_really_be_local`、
`test_r2_refused_library_writes_show_as_not_imported`。本轮复审也以前提正确的 `test_refusal_has_no_database_row_and_can_recover` 4 例认可了这一处理。

## 4. 新增同类用例（`tests/test_a1a_review_r3.py`，44 例）

| 用例 | 覆盖的同类情况 | 修复前 |
|---|---|---|
| `test_r3_startup_refuses_library_paths_linked_into_card`（9 例） | 应用启动：`.studio`、索引、索引日志、锁、导入日志、缩略图、暂存区、临时目录、图库根分别链到卡上 | 9 失败 |
| `test_r3_lock_refuses_library_paths_linked_into_card`（9 例） | 同样 9 处，CLI 先拿的锁 | 9 失败 |
| `test_r3_library_paths_linked_outside_library_are_refused` | `.studio` 链到图库外面的普通目录 | 失败 |
| `test_r3_cli_explains_and_exits` | 命令行启动：说明原因、退出码 78、不绑定端口、卡不变 | 失败 |
| `test_r3_library_on_a_volume_that_is_not_a_card_is_allowed` | 对照：普通外接盘上的图库照常打开 | 通过 |
| `test_r3_every_segment_and_trailing_byte_is_checked`（15 例） | tar/zip 首段 × gzip/bzip2/xz/zstd 后段；一个 gzip 段里 tar 后接内容；裸 tar 后接内容；zip 前缀、成员间、结束记录后夹带；文本段—tar 段—受限段；前面带脚本的 zip、受限文件压缩在成员里 | 13 失败；zip 前缀和"文本段在前"两例上一轮已能拦住 |
| `test_r3_clean_archives_still_pass`（5 例） | 对照：干净的 tar.gz、tar.gz 后接干净段、zip、tar、两个成员的 zip，不报任何命中 | 通过 |
| `test_r3_write_leaves_no_private_bytes_after_directory_moves`（3 例） | 第一次写之前移动、短写之后移动、`replace_file` | 3 失败 |

说明：
- 修复前第一次运行时，"zip 成员间夹带"的测试辅助函数有误（zipfile 写下一个成员时盖掉了夹带的字节），那次失败不算数。修好辅助函数后，用去掉"未占用字节检查"的检查器副本单独核对：成员间、结束记录后夹带都是 `[]`（会放行），现在的检查器都命中 R1（`evidence/zip-unlisted-bytes-check.log`）。
- "前面带脚本的 zip"是收尾时补的用例，先在当时的代码上确认失败（`evidence/regression-before-fix-zip-stub.log`），再修。
- 启动的 18 例在修复前因为新模块 `library/location.py` 还不存在而失败；同一缺陷按行为失败的证据是复审自带的 4 个启动用例（修复前卡被写，见 `evidence/review-r3-suite-before-fix.log`）。
修复前第一次运行时，`test_r3_cli_explains_and_exits` 在旧代码上一直跑到开服务，被我手动结束；之后在测试里把建监听端口替换成立即失败，旧代码上会马上失败而不会卡住。

## 5. 本轮改动的文件

- 新增：`src/gxr_studio/library/location.py`、`tests/test_a1a_review_r3.py`；`src/gxr_studio/cli.py`、`src/gxr_studio/library/lock.py` 第一次进入改动清单。
- 修改：`src/gxr_studio/app.py`、`src/gxr_studio/library/store.py`、`src/gxr_studio/privacy.py`、`scripts/private_bytes.py`、`README.md`、`docs/privacy.md`。

## 6. 复审测试怎么只读运行

两轮复审的复跑命令都会往复审目录写日志、收据、JUnit XML 和 `.coverage`，测试本身也会写观察记录。为了两轮复审目录都只读：
把测试文件和 `review_support.py`、`review_results.py` 逐字节复制到 scratch，用链接让它们的 `REPO`、`BASE` 指回真实的 `studio/`、`captures/`，
直接用 `studio/.venv` 的 pytest 运行（`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`、basetemp 在 scratch）。脚本见 `evidence/run_review_readonly.sh`。
没有用复审的沙箱配置，但测试代码一字未改。结束时：上一轮复审目录 94 项、本轮复审目录 59 项 SHA-256 全部一致，没有新增文件。

## 7. 没有验证的

- 真实 FAT/exFAT 卡、真实插拔、跨卷目录移动、相机：都没有做，全部是本机临时目录里的合成数据。
- 卡的识别以"卷根下有 DCIM 或卡根有 GXRCE.DAT"为准；在电脑上格式化、两者都没有的卡不会被当成卡（这时图库也不会被当成在卡上）。
- 私有字节检查不认 tar 的 PAX 扩展头里夹带的内容、带偏移量的十六进制转储（`xxd` 格式），以及图片里的隐写。

## 8. 文件

- 本报告：`research/studio_a1a_r3_fix/REPORT.md`
- 改动清单：`research/studio_a1a_r3_fix/changed-files.txt`（56 个），HEAD：`research/studio_a1a_r3_fix/HEAD`
- 校验和：`research/studio_a1a_r3_fix/SHA256SUMS`（路径相对 projectricoh 根目录；覆盖全部改动文件、本报告和 `evidence/` 下的日志与脚本）
- 复核：`cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh && shasum -a 256 -c research/studio_a1a_r3_fix/SHA256SUMS`
