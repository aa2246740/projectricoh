可以复审：第 2 轮复审的 5 组 P1 和 2 项 P2 已按类修复；复审自带的 147 例独立测试 145 例通过，剩下 2 例是复审用例的取行前提不成立（见第 3 节，已按用户决定保持"拒绝"）；前台完整 `make check` 退出 0，681 例全部一次通过，覆盖率 91.61%。

# A1a 第 2 轮复审的修复报告

对象：独立仓库 `studio/`，HEAD `1407830ee7c32fff892b23f2ddbfeb2bafd95b45`，相对 HEAD 的全部工作区改动（`changed-files.txt`，52 个文件）。
本轮依据：`research/review_studio_a1a_r2/REVIEW.md`。开工前核对过该目录的 `SHA256SUMS`（94 项全部一致），也核对过第 1 轮的
`research/studio_a1a_r1_fix/SHA256SUMS`（53 项全部一致，说明复审看的就是当时的工作区）。

没有做 git 写操作，没有开子代理，没有碰存储卡、用户图库或工作室实例。同一时间最多 2 个测试进程，都在前台阻塞等待。

## 1. 数字

| 检查 | 结果 |
|---|---|
| 复审自带独立测试（147 例，只读运行，见第 4 节） | 修复前 127 通过、20 失败（与复审记录相同）；修复后 **145 通过、2 失败**，失败的 2 例见第 3 节。日志 `evidence/review-r2-suite-after.log` |
| 本轮新增的同类用例 `tests/test_a1a_review_r2.py` | 49 例全部通过；修复前的失败证据见第 5 节 |
| 完整 `make check`（前台阻塞等待，新生成） | 退出 0；681 passed、0 failed、0 次重跑；覆盖率 91.61%；lint、format、mypy strict、bandit、秘密扫描、私有字节检查（仓库加 `uv build` 分发包）、大文件、OpenAPI、import-linter、deptry、vulture、pylint 全部通过。日志 `evidence/make-check.log`，起止 2026-11-01 03:49:57 至 03:59:11（UTC+8） |

`make check` 里的 `--reruns 1` 不是这几轮加的：开工时 Makefile 就有，AGENTS.md 也把它写成 CI 规则，所以没有去掉。本次日志里没有任何重跑。

## 2. 逐项修法（按类）

### R2-P1-01 图库路径经过链接指向卡

按类：图库里的**每一次写入**都按真实解析后的位置判断，而不只是复审举的几处。

- `Library.is_local(path)`：顺着所有链接解析后必须在图库目录里，而且不在任何登记了写保护的目录（发现到的卡根）里。
- `Library.check_write(rel)`：导入照片（建日期文件夹、放文件、改时间、编辑记录）、补全另一半（`cards/complete.py`）、导入视频、修复图库副本，
  动手之前都先核对；不合格抛 `LibraryPathRefused`，这个文件记进 `write_refused`，卡上零写入。
- 图库自己的暂存区、编辑记录临时目录、缩略图、日志、索引（`.studio/…`）在每次导入开始时核对；不合格整次导入失败，
  提示"无法写入图库文件夹。请检查图库位置后重试。"，不清理、不记日志（这些也是写入）。
- "已有同内容文件"：`current_sha` 对不在图库里的位置返回"未知"，卡上的原件不会被当成电脑上的副本；`_conflicts` 和视频去重都改用它。
- 审计钩子：所有写入事件都解析到真实位置（上级目录解析后的位置、整条路径解析后的位置），对两者和原路径都核对写保护；记录的是真实路径，不是别名。
  这也是界面编辑（编辑记录等）的兜底：经别名写进卡里会被拦下并报错。
- 界面：`write_refused` 算"未能导入"，横幅说"有 N 个文件未能导入。请勿格式化存储卡，重新插入后再试一次。"，状态行是"存储卡：有未导入的照片"，不说"可以推出"。

用例：`test_r2_library_writes_resolve_real_location`（年目录、日期目录、文件本身是链接 × 照片、视频，共 6 例）、
`test_r2_studio_dir_linked_into_card_refuses_whole_run`、`test_r2_audit_records_and_blocks_the_real_location`（打开、建目录、改时间、改名、复制）、
`test_r2_library_copy_must_really_be_local`、`test_r2_refused_library_writes_show_as_not_imported`。

### R2-P1-02 内容证明绑定

- `current_sha`：哈希前后各取一次状态（inode、长度、mtime、ctime），不一样就重读重算，三次都稳定不下来返回"未知"；
  缓存只把 SHA 记到"读字节那一刻"的状态上。
- `note_verified` 不再拿新的 `lstat` 给旧 SHA 签名：读回实际字节核对，不是刚放进去的内容就返回 False，导入把这个文件记成校验不一致。
- 覆盖核对收到"未知"时这个文件算未覆盖，不会发布"全部已导入"。

用例：`test_r2_hash_that_never_settles_is_unknown`、`test_r2_note_verified_reads_actual_bytes`；复审的 `test_library_changes_during_final_hash`、
`test_verified_cache_binds_current_file` 通过。

### R2-P1-03 子目录句柄换向

- `PrivateDir.check_fd(fd)`：核对**这次真正要用的父目录 fd**——它现在的真实位置必须还在核对过的目录里面，而且不在 Git 工作区、卡根或其他禁止目录下。
- 每一次创建、写入（写完再核对一次）、改名、读取、删除（递归删除的每一层）、建中间目录之前都调用；整体替换前核对根 fd。
- 审计的相对路径上下文保留目录 fd 本身，事件发生时再解析（以前存的是早先的路径字符串）。

用例：`test_r2_every_operation_checks_its_own_parent_fd`（写入、替换、删除、读取 × 卡、Git 工作区，共 8 例）、
`test_r2_mkdir_checks_the_intermediate_fd`（2 例）、`test_r2_audit_context_keeps_the_fd`；复审的 `test_calibration_inner_directory_move` 两例通过。

### R2-P1-04 私有字节检查的静默放行

原则：任何没有完整检查到的输入一律报 R0 并失败。按这个原则把所有解码路径过了一遍：

- 换行：CRLF、单独的 CR、字符串里的 `\r\n`、`\n`、`\r` 都归一成一个换行。
- 编码串：解码后超过上限报 R0，不再只看前缀；解出来的内容整个递归检查（编码里套压缩包、套编码）。
- gzip / bzip2 / xz / zstd：连接的每一段都要解完并正常结束，没结束、读不出、超限报 R0；每一段单独检查，多段时再查一次连起来的内容。
- zip：读不出、成员读不完、长度不符报 R0。tar：成员读不完或长度不符报 R0。认得出但解不开的格式（7z、rar）报 R0。
- 对照：能完整解开、内容干净的压缩文件照常通过；本仓库加分发包 238 个文件没有误报。

用例：`test_r2_content_check_never_passes_unchecked_input`（17 例）、`test_r2_complete_compressed_input_without_payload_passes`；
复审的 `test_encoded_content[json_crlf-*]`、`test_gzip_content`、`test_encoded_length_limit` 通过。

### R2-P1-05 计算结果非有限

- DNG：白电平必须高于任何位置的黑电平（含逐行、逐列偏移）；归一化码值、半分辨率码值、白平衡码值算出来必须全部有限；
  `render_half`、`render_full` 交给渲染器之前再断言一次。不满足抛 `RawDecodeError`。
- 场景色彩：矩阵换算抛出的异常、白点或矩阵非有限、白点亮度 ≤ 0，都抛 `SceneError("bad_matrix")`；`xyz()` 输出非有限抛 `SceneError("bad_colour")`。
- LensInfo 和未知镜头字段的 0/0 容忍保留（`test_r2_lens_info_zero_over_zero_is_still_tolerated`）。

用例：`test_r2_computed_values_are_finite_or_refused`（全零 ForwardMatrix、全零 ColorMatrix、黑白电平相等、黑电平高于白电平、偏移把黑电平推过白电平，共 5 例）；
复审的 `test_computed_values_are_finite` 两例通过。

### R2-P2-01 首个导入请求失败

请求失败后把这张卡从"已处理"里拿掉，横幅出现「导入」按钮；不自动连续重发。用例 `test_r2_first_import_request_failure_can_be_retried`。

### R2-P2-02 旧的私有名字

选择改正说法，不加兼容入口：复审自带的 `test_existing_repository_callers` 要求仓库里没有任何地方引用 `_done_message`，加别名会让它失败。
**第 1 轮报告里"原来的导入路径照常可用"的说法不准确，改正为：** `DONE_ALL`、`CHECK_FAILED`、`done_message`、`run_import`、`stage_file`、
`ImportOptions`、`ImportProgress` 可以从 `gxr_studio.cards.importer` 导入；HEAD 里的私有名字 `_done_message` 不再提供，仓库里没有调用方。
用例 `test_r2_public_import_names`。

## 3. 单列：复审用例 `test_library_directory_points_to_card_source` 的 2 例

- 结果：照片、视频各 1 例未通过，都在用例第 251 行 `fetchone()[0]` 报 TypeError。
- 原因：**复审用例的取行前提不成立（拒绝后没有记录）。** 图库日期目录是指向卡上 `DCIM/100RICOH` 的链接时，按用户要求"进入任何当前卡根就拒绝"，
  现在一个字节都不写、也不登记，所以 `files` / `videos` 表里没有可取的行。用户确认保持拒绝。
- 用例后面的断言"卡不变、不报全部导入"已用本仓库的同类用例证明，结果都是通过（`evidence/equivalent-tests.log`）：

| 用例 | 证明的内容 | 结果 |
|---|---|---|
| `test_r2_library_writes_resolve_real_location[day-photo]` | 日期目录链到卡上 `DCIM/100RICOH`：整棵卡目录（含目录 mtime）不变、审计没有卡上写入、不报全部导入、`write_refused` 列出该文件、提示"有 1 个文件未能导入。请勿格式化…" | 通过 |
| `test_r2_library_writes_resolve_real_location[day-video]` | 同上，视频 | 通过 |
| `test_r2_library_writes_resolve_real_location[year-photo]`、`[year-video]`、`[file_link-photo]`、`[file_link-video]` | 年目录链到卡、图库文件本身链到卡上原件 | 通过 |
| `test_r2_library_copy_must_really_be_local` | 卡上的同内容文件不算图库副本，核对不报全部导入 | 通过 |
| `test_r2_refused_library_writes_show_as_not_imported` | 界面：横幅"有 1 个文件未能导入。请勿格式化存储卡，重新插入后再试一次。"，状态行"存储卡：有未导入的照片"，不说"可以推出" | 通过 |

## 4. 复审独立测试怎么只读运行

复审目录末尾的复跑命令会往复审目录写日志、收据、JUnit XML、`.coverage`，测试本身也会往旁边写 `observations.jsonl` 和 `compatibility.json`。
为了不改复审目录，把 6 个 `test_review_*.py`、`review_support.py`、`review_results.py` 逐字节复制到 scratch（复制后 SHA-256 全部一致），
用链接让它们的 `REPO`、`BASE` 指回真实的 `studio/`、`captures/`，直接用 `studio/.venv` 的 pytest 只读运行
（`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`、basetemp 在 scratch）。命令见 `evidence/run_review_r2_readonly.sh`。
没有用复审的沙箱配置，所以不是复审环境的逐项复现，但测试代码一字未改。结束时复审目录 94 项 SHA-256 全部一致，没有新增文件。

## 5. 修复前的失败证据

- **2 项 P2 和界面的 `write_refused` 提示**：先写用例、在真实工作区上跑，确认失败，再修。
  日志 `evidence/regression-before-fix-p2.log`（2 例失败）、`evidence/regression-before-fix-write-refused-ui.log`（7 例失败：后台提示把只有"拒绝写入"的情况数成 0 个、界面没把它算成问题）。
- **5 组 P1**：这几类是先修代码、后补同类用例的，第 1 轮的源码没有留副本。为了证明新用例确实能抓住这些缺陷，用
  `evidence/revert_r1.py` 在 scratch 里复制整个 studio，只把某一类的修复退回第 1 轮的逻辑，再跑这一类的用例（日志 `evidence/regression-before-fix-p1-classes.log`）：

| 类 | 退回的内容 | 失败 / 通过 |
|---|---|---|
| R2-P1-01 | `is_local`、`check_write` 不核对；审计只记别名 | 9 / 0 |
| R2-P1-02 | `current_sha` 读时变化仍返回旧 SHA；`note_verified` 用新 lstat 签旧 SHA | 2 / 0 |
| R2-P1-03 | 只核对最外层 fd；审计上下文只认路径字符串 | 11 / 0 |
| R2-P1-04 | 第 1 轮的换行处理、单段压缩流、解码截断、无嵌套检查、只认 gzip | 15 / 2 |
| R2-P1-05 | 不核对电平、计算结果、白点亮度 | 4 / 1 |

  退回后仍然通过的 3 例（截断的 tar 成员、CRC 不符的 zip 成员、全零 ColorMatrix）是第 1 轮已经能拦住的情形，作为同类兄弟用例保留。
  这是"退回副本"的证明，不是第 1 轮原文件的逐字节复现。

## 6. 其他改动

- 第 1 轮用例 `test_r1_p1_01_job_progress_carries_its_card_session` 偶发失败（用固定 500 次、不等待的轮询等任务结束，慢的时候还没结束）。
  改用仓库已有的 `import_all`（有时间上限地等待），连续 5 次通过。
- `importer.py` 超过仓库 800 行上限，把"补全另一半"拆到 `cards/complete.py`；`raw/codes.py`、`raw/render.py` 加有限值断言。
- 文档：README（图库链接到卡时不写、`write_refused`）、`docs/privacy.md`（私有目录逐级核对父目录 fd、审计按真实路径、图库写入核对）。
- `raw/PROVENANCE.json` 里 `dng.py` 的说明补上本轮加的两项检查。

## 7. 没有验证的

- 真实 FAT/exFAT 卡、真实插拔、跨卷目录移动、真机相机：都没有做，本轮全是本机临时目录里的合成数据。
- 审计钩子对界面编辑（编辑记录、裁切等）的拦截是兜底：会报错，不会写卡，但没有做界面上的专门提示。
- 私有字节检查不认带偏移量的十六进制转储（`xxd` 格式）和图片里的隐写，这两类不在"解码路径"里，没有列入。

## 8. 文件

- 本报告：`research/studio_a1a_r2_fix/REPORT.md`
- 改动清单：`research/studio_a1a_r2_fix/changed-files.txt`（52 个），HEAD：`research/studio_a1a_r2_fix/HEAD`
- 校验和：`research/studio_a1a_r2_fix/SHA256SUMS`（路径相对 projectricoh 根目录；覆盖全部改动文件、本报告和 `evidence/` 下的日志与脚本）
- 复核：`cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh && shasum -a 256 -c research/studio_a1a_r2_fix/SHA256SUMS`
