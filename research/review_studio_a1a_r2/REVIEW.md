修改后再提交

仍有 5 组 P1：图库目录换向会写卡并把卡上原件当作图库副本；图库内容证明仍能失效；私有目录的子目录句柄换向仍能留下文件；私有字节检查仍有静默放行；渲染仍能产生非有限值。原 P1-03、P1-05、P1-07、P1-08 不关闭。未发现 P0；另列 2 项 P2，不影响本次阻断判定。

本轮审查的是公开 GitHub 仓库提交与用户日常使用的门槛。没有执行提交、推送或其他 Git 写操作。

对象为独立仓库 `studio/`，HEAD 为 `1407830ee7c32fff892b23f2ddbfeb2bafd95b45`。开始时先核对 `research/studio_a1a_r1_fix/SHA256SUMS`，53/53 条吻合；其中 48 个源码、测试与配置文件，正好覆盖相对 HEAD 的全部改动。清单自身 SHA-256 为 `ced2bb332f98cc254fe7425f0cb926645bfb6306f8ed6104e389b09dcb743766`。另冻结工作树 233 个文件，复审后摘要与 Git 状态均未变化。见 [输入收据](input-receipt.json)、[源文件摘要](source-before.json)、[结束核对](input-after.json)。

上一轮报告只输出并使用第 1–104 行；没有打开其受限的两份隐私复现文件。本轮脚本与证据全部新写在本目录，数据仅在指定临时目录中生成。所有故障输入均为合成数据，真机 DNG 只读使用。

逐项关闭情况如下。下表的用例名均在本目录脚本中；最终记录见 [独立复测结果](independent-summary.json)、[逐项观察](observations-final.json)。

| 原编号 | 判定 | 独立证据 |
| --- | --- | --- |
| P1-01 | 关闭原复现 | 原始 `import.js` 与 `import_summary.js` 在 Node 中实际执行，只替换 API、状态与 DOM 边界。同卡完成、A 卡任务结束前换 B、B 在 A 结束前移除、旧结果缺少来源号，4 个时序均通过。B 在空闲后收到自己的导入请求，A 的完成状态没有套给 B。真机样本的实际 API 任务也携带并返回同一 `card_id`。见 `frontend.json`。 |
| P1-02 | 关闭原复现 | `test_session_changes` 共 40 例：照片和视频，各在首次读取前、读内容中、暂存核对前、单项结束后、最终核对返回前，分别改变 fsid、设备来源、可见状态或根 inode。均中断，不发布全量完成；早期中断没有入图库，后期中断保留已完成的副本，暂存目录清空。另外 4 例在读取后等长改写或更换源 inode、恢复 mtime，会重新核对并列为未覆盖。 |
| P1-03 | 不关闭 | 照片和视频的普通等长替换、原位改写、截断、删除均已识别并修复。但最终哈希期间变化仍返回旧 SHA；`note_verified` 也能把旧 SHA 绑定到已经变化的文件状态。4 例仍错误报告全量完成，见 R2-P1-02。 |
| P1-04 | 关闭原复现 | Pillow 可解码的 5 个 JPEG 分别置于 `._*`、`.Spotlight-V100`、`.Trashes`、`.DS_Store` 和普通隐藏名。全部进入“不会被导入”，没有进入系统文件；真实 AppleDouble 魔数的合成元数据作为对照仍被识别。结果不再报告全部导入，假卡字节和文件状态不变。见 `test_system_names_keep_media_visible`。 |
| P1-05 | 不关闭 | 根目录检查后换成链接会拒绝；根目录 fd 移入受保护目录后，真实 `dir_fd` 的 mkdir 被拒绝。常规 mkdir、open、rename、utime、unlink、rmdir 的路径记录也正确。但子目录 fd 已打开后移动该子目录，根 fd 不变，实际创建仍可落到受保护目录或带 `.git` 标记的目录中，见 R2-P1-03。 |
| P1-06 | 关闭原复现 | 用真实 HEAD 中的 README blob，配合符合 Git raw 格式的暂存列表，覆盖工作文件内容不同、工作文件不存在、重命名路径。真正的 `git cat-file --batch` 返回 blob 字节，按该 blob 的哈希命中 R4。diff 出错、真实对象不存在两例均停止检查。未执行 Git 暂存写入；列表边界是合成的，对象读取是真实的。见 `staged_reads_real_blob`、`staged_errors_stop_check`。 |
| P1-07 | 不关闭 | 连续、LF 换行和 JSON `\n` 的 base64/hex 共 6 例通过；4、5、7 层 ZIP 均被拦下，深度超限明确 R0；损坏 ZIP、成员尺寸及展开预算超限也失败。但 JSON CRLF、GZIP 后续段、未完成 GZIP、超过解码上限的编码串仍有退出 0 的路径，见 R2-P1-04。 |
| P1-08 | 不关闭 | 6 种矩阵标签的零分母、NaN、Infinity 共 18 例均报 `bad_matrix`；其他渲染字段 21 例拒绝；白平衡缺失或非有限值 3 例拒绝；LinearizationTable 的 RATIONAL、DOUBLE、LONG 类型均拒绝。缺少矩阵仍报 `no_matrix`，标签存在但非法报 `bad_matrix`，旧用例改码正确。LensInfo 的 0/0 仍可读，真实 MOUNT 导入出片成功。但有限输入计算出的零分母仍产生 NaN，见 R2-P1-05。 |
| P2-01 | 关闭原复现 | 照片、视频各覆盖等长替换、原位改写并恢复 mtime、截断、删除，共 8 例。全部把卡上原件放回原位置；有修改版本时逐字节保留为 `.modified-*`；文件、照片和编辑索引不变。另有 RAW+JPEG 配对的 3 例，两个文件一起恢复，照片 id 和含编辑字段的 sidecar 字节不变。见 `library_repair`、`raw_jpeg_pair_repairs`。 |

R2-P1-01：图库路径经过链接指向卡时，仍可写卡，且视频副本只存在于卡上。

位置：`studio/src/gxr_studio/cards/importer.py:660–674`、`cards/videos.py:58–68`、`cards/repair.py:24–33`；审计解析在 `studio/src/gxr_studio/audit.py:153–164` 和 `:220–236`。

复现方法：在普通临时图库打开后，把 `library/2026` 指向受保护假卡中的 `reserve`，再走真实 `run_import`。照片和视频的新导入、修复导入共 4 例都改变了假卡目录或文件，审计的 `writes_under(card.root)` 却为空，结果仍为 `all_imported=true`。绝对路径在审计中仍是图库别名，未解析到实际卡根。

更直接的一例，把 `library/2026/2026-10-31` 指向卡上 `DCIM/100RICOH`。视频内容相同，导入丢掉暂存文件，对卡上原件执行 utime，并把这个别名登记为图库文件。结果是 `copied_files=0`、`all_imported=true`、提示可以推出；移除假卡后，图库文件随之消失。此例没有从主机暂存区向卡移动文件的步骤。照片同样修改卡上文件状态并新增 sidecar，不过最终核对会发现新增的 sidecar，未报告全量完成。

证据：`test_library_directory_link`、`test_library_directory_points_to_card_source`；`observations-final.json` 对应同名 case。[后端结果对应的界面文字](backend-text.json) 也实际调用了原始汇总模块，视频情形为“存储卡：可以推出”。

最小修正：图库与修复写入也要约束真实目录归属，拒绝目录链进入任何当前卡根；已有同内容文件必须确实属于图库，不能沿链接把卡上原件当作本机副本。mkdir、替换、改名、utime 和 sidecar 写入共用同一约束。

R2-P1-02：内容证明没有绑定稳定的当前图库文件，错误完成状态可持续到下次导入。

位置：`studio/src/gxr_studio/library/store.py:203–227`、`:229–235`。

复现方法一：先正常导入。在单项结束后把图库原内容重新保存一次，使缓存失效；最终覆盖核对真正读取并算出 SHA 后、函数返回前，再等长改写目标文件。`current_sha` 已发现前后状态不同，却只停止写缓存，仍返回旧 digest。照片、视频均得到 `all_imported=true`；独立读回的实际 SHA 不等于原件 SHA。

复现方法二：在真实 `note_verified` 入口前等长改写刚就位的文件，再执行原函数。它把暂存原件的 SHA 绑定到改写后的 inode/长度/mtime/ctime，没有核对这份状态对应的字节。首次及第二次导入均报告全量完成，第二次 `copied_files=0`，错误缓存持续有效。用例只安排文件变化发生的时刻，哈希计算和原缓存函数都真实执行。

证据：`test_library_changes_during_final_hash`、`test_verified_cache_binds_current_file`，每项均有照片、视频两例。以 JPEG 为例，正确 SHA 为 `b6717ba5…60ed789`，第二种情形实际文件为 `b0cab8a3…f31e548`。`backend-text.json` 确认这些结果会显示“存储卡：可以推出”。

最小修正：哈希前后状态不同必须返回未知或重新核对；写入验证缓存时，必须把 SHA 绑定到实际读过的那个文件状态，不能仅凭新的 lstat 给旧 SHA 签名。覆盖核对收到未知时不得发布全量完成。

R2-P1-03：子目录句柄换向后，实际父目录与审计上下文不同，私有文件仍会写入禁止位置。

位置：`studio/src/gxr_studio/privacy.py:182–207`、`:226–230`；`studio/src/gxr_studio/audit.py:143–164`。

复现方法：通过真实 `calib.import_calibration`，使用全合成 stock、NPZ 和 JSON，内存核对正常完成。在 `_at` 已打开 `calib.new` 的父 fd、尚未创建 `ctx_200.npz` 时，把这个子目录移入假卡或带 `.git` 标记的临时目录，然后继续原来的写入。没有替换 os.open、os.write、改名或删除函数。

`F_GETPATH` 显示最终父 fd 已在目标目录，根 fd 仍在原应用数据目录；审计上下文却保留移动前的路径字符串。两个目标中都实际新增 `retained/ctx_200.npz`，878 B，SHA-256 为 `337c8abb84e6ccc0b364822c580eddb2a2dfb15a36372cac26008c06ecbe2fac`。后续读回报 FileNotFoundError，文件仍留在禁止位置，审计的 open 记录归到了旧路径。

证据：`test_calibration_inner_directory_move[card]` 和 `[repository]`，见 `observations-final.json` 的真实父 fd、根 fd、上下文路径和最终文件摘要。正常标定对照、根链接换向对照及常规 dir_fd 审计均通过。

最小修正：复核最终操作所用的父 fd，而不只复核最外层 fd；open 审计上下文应保留可重新解析的 fd，不能只保存早先的路径字符串。发现父目录已进入卡根或 Git 工作区时，创建前拒绝。

这是同一 APFS 文件系统上的目录移动模型，没有验证跨卷目录移动，也没有写真实存储卡。带 `.git` 标记的对照直接验证了同一缺口对私有字节目录规则的影响。

R2-P1-04：内容检查仍把未完整检查的输入当作通过。

位置：`studio/scripts/private_bytes.py:112–123`、`:127–151`、`:187–196`。

| 故障输入 | 独立反解或对照 | 实际检查结果 |
| --- | --- | --- |
| 76 列 base64、64 列 hex，以 CRLF 连接后放入 JSON 字符串 | 两者反解均逐字节等于能被识别的合成原件 | `hits=[]`、退出 0。`\r\n` 被分别替换成两个换行，每行短块被拆散。 |
| 两个标准 GZIP 段连接，第一段为普通说明，第二段为合成受限内容 | `gzip.decompress` 能完整还原两段 | `hits=[]`、退出 0。只处理第一段，忽略 `unused_data`。 |
| 只有头部的未完成 GZIP 流 | 标准解压明确报 EOFError | `hits=[]`、退出 0。没有检查解压器 `eof`。 |
| 解码后 4,194,473 B 的 base64 或 hex，规则标记位于 4 MiB 之后 | 未编码的同一内容命中 R2 | 两种编码均 `hits=[]`、退出 0。解码仅取前缀，未报 R0。 |

证据：`test_encoded_content[json_crlf-*]`、`test_gzip_content`、`test_encoded_length_limit`。共 6 个失败用例；所有字节均为合成输入。问题影响暂存区与分发包共用的 `scan_bytes` 路径。

最小修正：把 CRLF 归一为一个换行；处理 GZIP 全部段并确认流完整；遇到解码上限时完整检查受限预算内的全部内容，或明确报 R0 并失败，不能静默丢弃尾部。

R2-P1-05：只核对标签本身有限，尚未保证渲染计算结果有限。

位置：`studio/src/gxr_studio/lut/scene.py:45–50`、`:69–72`；`studio/src/gxr_studio/raw/dng.py:139–152`、`:246–252`。

复现一：合成有效 ColorMatrix、正常白平衡，同时设置全部为 0 的 ForwardMatrix1，每个有理数的分母都是 1。标签校验通过，`scene_colour(...).xyz(...)` 在白点 Y 为 0 时除零，返回 90/90 个 NaN，未抛明确错误。

复现二：合成有限的 BlackLevel=64、WhiteLevel=64。`open_dng` 接受；`half_res_codes` 的 90 个值有 1 个 NaN、89 个 Infinity；`render_half` 仍返回 5×6×3 的 uint8 图，仅留下除零和转换警告。

证据：`test_computed_values_are_finite[zero_forward]`、`[equal_levels]`，记录包含各类非有限值数量、警告以及实际渲染摘要。这不否定本轮对原始有理数零分母的修正，但尚不满足“渲染路径不产生 NaN”的门槛。

最小修正：核对色彩归一化所用白点与分母、矩阵实际换算结果，以及白电平减黑电平的有效范围；不可用时抛明确的 SceneError 或 RawDecodeError。保留 LensInfo/未知镜头字段的单独容忍规则。

P2 留给下一轮处理。

| 编号 | 位置与复现 | 影响及最小修正 |
| --- | --- | --- |
| R2-P2-01 | `studio/web/assets/import.js:24–28`、`:97–109`。首个自动导入 POST 报错后，再刷新同卡列表。`frontend.json` 的 `request_error` 仅有 1 次 POST，横幅为空，状态为已插入。 | 任务没有建立，卡号却留在 `autoTried` 和 `handled`，没有自动重试或横幅中的导入按钮。失败时恢复可重试状态并显示按钮。没有错误的完成提示，按 P2。 |
| R2-P2-02 | `studio/src/gxr_studio/cards/importer.py:49–52`。HEAD 原有 `_done_message`，当前模块没有该名字。 | `DONE_ALL`、`CHECK_FAILED`、`done_message`、`run_import`、`stage_file` 的现有导入可用，实际文案用例通过；AST 检查未发现仓库调用方仍引用旧私有名字。因此未发现现有调用方中断，但“所有旧路径仍可导入”的说法不成立。如需保留该私有入口，应加明确兼容入口。见 `compatibility.json`。 |

真实 MOUNT 样本与公开内容检查也已完成。

- 只读样本为 `captures/street-g137-20261031/dng/R8051530.DNG`，18,665,743 B，SHA-256 为 `274c014ea0c8a1a5cc787cce8d75c377af4d45da55beef45c25f2c09fe402dae`。识别为 `GXR MOUNT A12`；原始平面 4304×2862，半分辨率码值全有限，LensInfo 的 0/0 未阻止读取。实际 `/api/import`、任务结果、预览和导出接口通过；预览 1600×1063，JPEG 导出 768×510。源样本哈希与 mtime 未变，假卡也未变。记录在 `mount_sample_import_and_export`。
- 视频仍由 `run_import` 正常调用新模块，照片、视频及混合结束文案的字面结果通过。矩阵标签缺失为 `no_matrix`，存在但非有限为 `bad_matrix`，错误码变化正确。
- 仓库自带检查在完整 `make check` 中执行 `private_bytes.py --tracked --dist`，报告 checked 236 files。独立成员抽查另覆盖 233 个工作树文件、wheel 的 119 个文件成员及 sdist 的 238 个普通文件成员，没有命中登记哈希或内容标记；没有 DAT、NPZ、entry、ELF、BIN 后缀文件。wheel 中可映射回源码的 115 个文件全部与冻结源码相同。见 `package-audit.json`。这说明本次工作树和本次构建包在这些规则下未发现私有字节；检查器的能力缺口仍须按 R2-P1-04 修复。

| 本次构建产物 | SHA-256 |
| --- | --- |
| `gxr_studio-0.1.0-py3-none-any.whl` | `729491ce9c87938b6f33f9c12f7ac161a2e424f78645fa2b8461452e91f834cd` |
| `gxr_studio-0.1.0.tar.gz` | `009a8fcff32f03012e2ec3bc60f88dd290cbd5f9b92848312636cdc5782bc289` |

执行结果与用时如下。每次命令、起始 UTC、退出码和耗时均在对应 `*-receipt.json` 中。

| 检查 | 新生成的结果 | 用时 |
| --- | --- | --- |
| 完整 `make check` | 退出 0；632 passed，3 warnings；覆盖率 91.61%；632 个 call 均一次通过，重跑事件 0 | 总计 467.905 秒，pytest 455.73 秒 |
| 最终独立 Python 复测 | 147 例，127 passed、20 failed，无重跑；20 个失败均对应上述 5 组 P1 | 10.264 秒 |
| 原始前端模块时序 | 4 个原问题相关时序通过；另一个请求失败用例证实 R2-P2-01，脚本据此退出 1 | 0.140 秒 |
| 后端结果的原始汇总文字 | 实际调用原汇总模块，记录问题结果对应的状态文案 | 0.205 秒 |
| 独立包成员抽查 | 退出 0，无内容命中，源码映射全部一致 | 0.732 秒 |

完整检查保留了原 Makefile 的 `--reruns 1`。`make-check-results.jsonl` 和 `make-check.xml` 均为本轮新生成，重跑数量不是依据实现者日志推定。解释器为 Python 3.14.7；当前平台已安装的 55 项锁定依赖版本一致，见 `environment-versions.json`。

为保持源码只读，`UV_OFFLINE=1`、`UV_NO_SYNC=1`，复用既有虚拟环境；将离线构建后端缓存复制到指定临时目录。ruff、mypy、coverage、pytest 和 import-linter 的缓存、临时文件均移到允许范围；import-linter 通过命令包装追加缓存目录，源码 Makefile 未变。使用系统沙箱限制写入到本目录和指定临时目录，禁止出站网络，禁止读取其他卷与用户真实图库。所有测试命令由前台 `subprocess.run` 收取退出码，继承 nice=10；完整检查超时为 2700 秒，大于历史 400.70 秒的三倍。没有后台 shell 或休眠轮询；没有同时运行多套测试，测试中的一个辅助子进程与主测试串行配合。

前期失败没有记作通过：两次 `make-preflight*.log` 在离线构建后端准备阶段停止；`make-fenced.log` 因目录读取规则过严，出现 43 failed、49 errors、92 rerun。修正仅涉及本轮沙箱配置，随后完整检查通过。独立脚本早期的合成字编码、HTTP 状态预期、文本匹配与归档容器分类问题也保留在早期日志中；判定采用最终 147 例和成员级抽查结果。

前端证据是原始 ES 模块的实际执行与 DOM/API 替身记录，没有宣称浏览器视觉验收。插拔和目录移动证据为本机文件系统及挂载模型；未操作真实卡、相机、现有服务或用户图库。普通路径的“保留用户版本”已证；全局“零写卡”和“副本确实留在电脑”未通过，不能以 632 个现有测试通过代替。

本轮总用时：50 分 13 秒（2026-11-01 02:18:54 至 2026-11-01 03:09:07，UTC+8）。临时目录、结束输入核对及清理结果见 `final-receipt.json`。分发包与导出图只在临时目录生成，结束时删除；保留成员摘要、样本摘要、日志和复测脚本。

复跑独立检查可用以下命令；当前缺陷仍会让 pytest 退出 1。所有路径均为本机路径，准备脚本只复用离线缓存。

```sh
review_dir=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_a1a_r2
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio
/usr/bin/python3 -I -B "$review_dir/prepare_environment.py"
/usr/bin/python3 -I -B "$review_dir/verify_inputs.py" --name repeat-input
/usr/bin/python3 -I -B "$review_dir/run_local.py" --name repeat-review --timeout 2700 -- .venv/bin/python -B -m pytest -q -c pyproject.toml --rootdir="$review_dir" --noconftest "$review_dir"/test_review_*.py
```
