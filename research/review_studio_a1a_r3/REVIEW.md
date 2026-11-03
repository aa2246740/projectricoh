修改后再提交

仍有 2 组 P1：正常启动会沿图库链接写卡；多段压缩文件首段为 tar/zip 时，后续受限内容仍会被当作检查通过。R2-P1-01、R2-P1-04 不关闭。R2-P1-02、R2-P1-05 关闭；R2-P1-03 的原问题关闭，另有一项按本轮范围归为 P2 的精确目录换向问题。未发现 P0。

这是提交并推送到公开仓库、供用户日常使用的复审。没有提交、推送或其他真实 Git 写操作。

对象为独立仓库 `studio/`，HEAD `1407830ee7c32fff892b23f2ddbfeb2bafd95b45`。开始先核对本轮清单，63/63 项一致，覆盖相对 HEAD 的全部 52 个改动文件及实现证据；清单自身 SHA-256 为 `fec1d92ba9b7b3fec3fffa0211df7391af65721eff1f8f4578d6a6198d8db46e`。上一轮清单 94/94 项一致。另冻结仓库 235 个文件和上一轮目录全部 95 个文件，结束再次核对。见 [输入收据](input-receipt.json)、[结束核对](input-after.json)、[最终收据](final-receipt.json)。没有查看再上一轮复审目录。

逐项复核如下。原测试结果见 [test-summary.json](test-summary.json)，新增用例在 [test_r3.py](test_r3.py)，逐项观察见 [observations-final.json](observations-final.json)。

| 上轮项目 | 本轮判定 | 独立证据及新增变体 |
| --- | --- | --- |
| R2-P1-01，图库真实位置 | 不关闭整类 | 上轮照片、视频的新导入及修复链接用例通过；年、日期、文件、暂存区等实现者新增用例随完整检查通过。本轮补了两级相对链接，照片、视频均拒绝，卡的文件及目录状态不变。但启动前已存在的 `.studio`、索引或图库根链接仍会写卡，详见 R3-P1-01。 |
| R2-P1-02，内容证明 | 关闭 | 上轮哈希中变化、`note_verified` 绑定错误的照片/视频用例均通过。新增原位改写与替换 inode 两种变体，保留旧 mtime，首次读取后换内容，均重新读取，返回实际新 SHA，稳定后才命中缓存。再让文件每次完整读取后改变状态，照片、视频均有界结束，列入未覆盖和校验不一致；恢复稳定后可继续，索引仍各 1 行，随后导入复制数为 0。源码位于 `studio/src/gxr_studio/library/store.py:237`、`:263`。 |
| R2-P1-03，实际父 fd | 原问题关闭，余项 P2 | 上轮私有子目录移入假卡和临时 Git 标记目录的两例通过；实现者逐操作父 fd 用例随完整检查通过。新增递归删除的更深一层目录换向，在已经获得子目录 fd 后移动该层，后续删除被拒绝，移走的文件保留原字节。另在文件已打开、尚未写字节之间移动目录，仍会留下字节，按用户明确的范围记为 R3-P2-01。 |
| R2-P1-04，完整内容检查 | 不关闭整类 | 上轮 CRLF、未完成流、解码上限等用例通过。新增 CR、转义 CR、URL-safe base64、四类多段压缩的干净内容与后段不完整对照均符合预期。但首段是归档时仍跳过后段，详见 R3-P1-02。当前仓库及实际分发包没有 R0 误报。 |
| R2-P1-05，计算结果有限 | 关闭 | 上轮标签非有限、零 ForwardMatrix、黑白电平相等等用例通过。新增有限但极小的白平衡值，半分辨率、全分辨率路径均明确报 RawDecodeError；逐行、逐列偏移只在一个角点叠加超过白电平也被拒绝；负白点 Y 报 `bad_matrix`，`xyz()` 非有限结果报 `bad_colour`。正常计算对照及真实 MOUNT、50mm 出片通过。对应 `raw/dng.py:155`、`:255`，`raw/codes.py:39`、`:71`，`raw/render.py:64`、`:75`，`lut/scene.py:45`、`:57`。 |
| R2-P2-01，首次导入请求失败 | 关闭 | 实际执行原 `import.js`。首次 POST 失败后，横幅有可点击的「导入」按钮，5 次刷新没有新 POST；点击后才发第 2 次请求，完成状态正常。 |
| R2-P2-02，旧私有名字 | 接受更正后的说明 | 原兼容性检查通过，仓库没有旧私有名字的调用方。实现报告已明确 `_done_message` 不再提供，不要求增加别名。公开导入名字的检查通过。 |

用户决定保留的“拒绝”满足上一轮最小修正。

原 147 例原样复跑为 145 通过、2 失败。两例均停在 `test_review_media.py:251` 的空表取首行，未执行后面的断言；原失败没有改记为通过。本轮前提正确的版本是 `test_refusal_has_no_database_row_and_can_recover`，覆盖照片、视频和直接、两级相对链接，共 4 例通过：

- 连续两次导入都不登记，复制数为 0，`write_refused` 明确列出文件；整棵假卡的文件字节、inode、mtime、ctime，以及目录状态均不变，审计没有卡上写入事件。
- 结果有 `uncovered`，`all_imported=false`，后端明确提示未能导入。原始前端模块显示“存储卡：有未导入的照片”，没有“可以推出”。
- 按用户修正图库链接的情形移除本机链接后，可以正常导入一次；再导入复制数为 0，索引仍只有 1 行，卡不变。测试在这一步暂时解除假卡审计保护，只为模拟用户在程序外修正本机链接，随后立即恢复保护。

“未知”状态同样不会停住或自动重复导入。照片、视频的持续变化用例各进行 15 次实际哈希读取后结束，最终未覆盖且有校验不一致；恢复稳定后重试成功，后续重复导入不再复制。前端共 7 个场景通过，其中 4 个拒绝、2 个未知均不可推出，重复刷新不再发 POST，显式点击「导入」才重试。见 [ui-results.json](ui-results.json) 和 [verify_ui.mjs](verify_ui.mjs)。这里是原始 ES 模块加 DOM/API 边界对象的实际执行，没有宣称浏览器视觉验收。

R3-P1-01：卡根保护建立得太晚，启动本身仍会沿图库链接写卡。

位置：`studio/src/gxr_studio/library/lock.py:25`，`studio/src/gxr_studio/cli.py:34`，`studio/src/gxr_studio/app.py:79`，`studio/src/gxr_studio/library/store.py:162`；卡根保护直到 `studio/src/gxr_studio/cards/discovery.py:138` 才登记，导入布局检查在 `studio/src/gxr_studio/cards/importer.py:414`。

触发条件：启动前，用户的图库根、`.studio` 或 `.studio/index.sqlite` 已通过符号链接指向已插卡的目录。只需静态配置和正常启动，不要求在操作中移动目录、修改应用私有数据或掌握时间点。这是上一轮已接受的图库目录链接情形在冷启动阶段的变体。

复现使用普通临时图库及带 DCIM 的假卡，尚未进行第一次卡扫描，真实执行 `create_app(settings)`，没有替换文件写入、SQLite 或审计实现。

| 静态链接位置 | 真实结果 |
| --- | --- |
| `.studio` 指到假卡 `reserve` | 正常返回应用对象；假卡新增 `index.sqlite`、`staging`、`thumbs`、`tmp`，目录状态改变。 |
| `.studio/index.sqlite` 指到假卡 | 正常返回应用对象；假卡新增 SQLite 文件。 |
| 图库根指到假卡 `reserve` | 正常返回应用对象；假卡新增整套 `.studio` 目录及索引。 |
| `.studio` 指到假卡，执行真实 `LibraryLock.acquire()` | 假卡新增 `studio.lock`；这是 CLI 在创建应用之前调用的方法。 |

复审外层记录器正确记录了真实卡路径，但这些事件的 `blocked=false`，因为保护还没有登记。3 个应用启动用例及 1 个锁用例均失败，见 `startup_library_location`、`startup_lock_location` 观察及 `new-tests-final.log`。应用工厂与锁方法的写入为主机已证；CLI 调用先后为静态已证，没有为复现启动监听端口。

最小修正：把当前卡根的只读识别和真实图库位置核对放到首个图库写入之前，覆盖 `LibraryLock.acquire()`、`Library.open()` 的目录创建、清理及 SQLite 打开。不能只在 `run_import` 入口检查；图库根本身解析入卡也必须拒绝。

R3-P1-02：首段归档的提前返回仍使后续压缩段未被检查。

位置：`studio/scripts/private_bytes.py:285` 至 `:288`，以及 `:250`、`:302`。`_decompress_all` 确实解完了全部段，但拼接结果一旦识别为归档，就直接返回内层成员；后面的逐段检查不再执行。tar/zip 的正常读取只检查自己的成员，后段普通文件的字节因此没有进入 `scan_bytes`。

触发条件：离线打包或归集资料时，把普通 tar/zip 和相机私有文件作为多个输入压缩进同一文件，再把该文件纳入提交或分发。系统 gzip 的正常多输入命令即可生成，不需要损坏流、并发或目录变化：

```sh
/usr/bin/gzip -c notes.tar camera-sample.dat > combined.gz
```

本轮 `camera-sample.dat` 是 1,032 字节的全合成数据，只含规则已识别的头部及确定性字节。单独检查明确命中 R1，以该合成内容的 SHA 作为测试登记值时也命中 R4；首段为普通文字时，四种压缩格式的后段都能被识别。将首段改为普通 tar/zip 后，gzip、bzip2、xz、zstd 的 8 个组合均得到 `hits=[]`、退出 0，标准解压均还原完整的两段。本机 `/usr/bin/gzip -c` 的真实产物也复现同样结果，退出 0。共 9 个失败用例，不涉及任何真实相机私有字节。

证据：`test_archive_in_first_stream_does_not_hide_later_stream`、`test_system_gzip_checks_every_source_file`，以及 `later_stream_positive_control` 观察。提交、仓库和分发路径都复用该 `scan_bytes`。这说明公开内容检查仍有未检查却通过的路径，不表示本次实际工作树或分发包已经含有私有内容。

最小修正：去掉拼接结果被识别为内层归档时的提前返回。每个解压段都必须经过完整 `scan_bytes`，再按需要检查拼接内容；无法完整归属的剩余内容报 R0。保留现有干净归档及实际仓库、分发包的通过对照。

R3-P2-01：创建文件后、写字节前精确移动私有子目录，仍会留下私有字节。

位置：`studio/src/gxr_studio/privacy.py:249` 至 `:261`。父 fd 在创建之前和写完之后检查，中间的 `os.write` 前没有复核。

复现：真实打开 `app-data/temporary/sample.bin` 之后、首次 `os.write` 之前，精确将 `temporary` 移入同一 APFS 卷上的临时 Git 标记目录，再继续原写入。最终明确抛 PrivatePathError，但移走的目录里已经留下 630 字节。包装函数只在首次写入边界移动目录，随后调用原 `os.write`；打开文件和目录改名均为真实系统调用。

该条件要求对应用自己的私有目录做精确的并发移动；未发现正常操作可产生同样情形。按用户本轮明确范围记为纵深防护 P2，不阻断。建议在写字节之前复核实际父 fd，并明确处理发生换向后的临时文件清理结果。证据为 `test_write_checks_directory_after_open_before_bytes` 和 `directory_move_after_open` 观察。

真实样本及分发包结果如下。

指定的 `captures/street-g137-20261031/dng/` 共 15 份 DNG，元数据全部为 `GXR MOUNT A12`，其中没有 50mm。MOUNT 使用 `R8051530.DNG`；50mm 补用仓库完整检查已使用的 `captures/a12-50/2026-10-13/photos/A1-setting1/R8051129.DNG`，元数据为 `GR LENS A12 50mm F2.5 MACRO`。均只读，源字节、mtime、ctime 在结束时复核。

| 样本 | 源 SHA-256 | 实际结果 |
| --- | --- | --- |
| MOUNT | `274c014ea0c8a1a5cc787cce8d75c377af4d45da55beef45c25f2c09fe402dae` | 归一化/半分辨率码值和 XYZ 有限；半分辨率 RGB 为 2144×1424，全分辨率为 4288×2848。 |
| 50mm | `2c70631698dd659943bf14f9138a47060ae1a6bd72a6e43238314174f4183e46` | 同上，半分辨率及全分辨率实际渲染成功。 |

两者都通过真实 ASGI `/api/import`、任务完成、照片预览及中性 RAW 导出接口，预览 1600×1063、导出 768×510，假卡不变。两张导出 JPEG 已实际打开查看，可见街景及织物纹理，没有空白图或明显破损。原始像素和导出摘要见 `real_camera_render` 观察。此处核实中性 RAW 渲染及矩阵计算，没有使用用户私有相机数据验证配方颜色一致性。

完整 `make check` 中，仓库和分发检查无误报。扫描器报告 checked 238 files，对应 235 个仓库文件和构建目录的 3 个文件，包含 wheel、sdist 和构建工具生成的 `.gitignore`。另离线新建两个分发包，逐成员复查：wheel 120 个文件成员，sdist 240 个普通文件成员，无命中；wheel 中可映射回源码的 116 个文件全部与冻结源码一致。见 [package-audit.json](package-audit.json)。

| 本轮实际构建包 | SHA-256 |
| --- | --- |
| `gxr_studio-0.1.0-py3-none-any.whl` | `8d1d0386f3a414af27ce4bf782719e7cd26fa494bddbc99a8173b6aaa8dc1329` |
| `gxr_studio-0.1.0.tar.gz` | `e66990b8e7946025081f54aa2f6c09552cbcc885392d584028fd8e4455ed24bf` |

执行结果及用时如下。命令、起始 UTC、退出码和耗时均保留在各自的 `*-receipt.json`。

| 检查 | 本轮新生成的结果 | 用时 |
| --- | --- | --- |
| 完整 `make check`，只跑一次 | 退出 0；681 passed、3 warnings；覆盖率 91.58%；681 个 call 都只执行一次，重跑事件 0，JUnit 无失败及跳过。 | 585.919 秒，其中 pytest 571.18 秒。 |
| 上一轮 147 例，逐字节副本 | 145 passed、2 failed；两例均为空表取首行的已知前提问题，保留失败。 | 6.913 秒。 |
| 最终新增独立用例 | 41 例，27 passed、14 failed；4 个启动 P1、9 个内容检查 P1、1 个精确换向 P2。 | 7.599 秒。 |
| 原始前端模块 | 7 场景通过；6 个拒绝/未知结果不可推出；首次失败可手动重试，自动重复请求 0。 | 0.147 秒。 |
| 额外离线构建及成员复查 | 两包构建成功，成员检查无命中，116 个源码映射一致。 | 构建 1.343 秒，复查 0.739 秒。 |

完整检查从 2026-11-01 04:04:24 至约 04:14:10，UTC+8，保留 Makefile 原有 `--reruns 1`，以本轮 JSONL 和 JUnit 独立确认重跑为 0。覆盖率是本轮实际的 91.58%，未沿用实现者的 91.61%。见 [make-check-counts.json](make-check-counts.json)、[make-check.log](make-check.log)。

新增脚本最初一轮为 18 passed、18 failed，其中 13 项为当时已存在的产品问题；4 项在已经验证完拒绝断言后，被审计守卫阻止测试自己移除本机链接，另 1 项因指定样本目录没有 50mm 而停止。只修改本轮测试的这些前提后，定点 5 例通过；补足对照和系统 gzip 用例后，最终 41 例结果如上。早期日志全部保留，没有把测试准备失败当作产品缺陷，也没有把产品失败改记为通过。完整 `make check` 没有重跑。

执行边界为主机已证。测试命令由前台 `subprocess.run` 阻塞收取退出码，继承 `nice -n 10`；同时最多一个主 pytest，用例中的系统工具子进程至多一个。完整检查超时 3600 秒，大于历史 467.905 秒的三倍；独立测试超时 2700 秒。复用既有虚拟环境，`UV_OFFLINE=1`、`UV_NO_SYNC=1`，只将离线构建缓存复制进指定临时目录。TMPDIR、pytest basetemp、各工具缓存均在该目录，coverage 和日志在本复审目录。

系统沙箱只允许写本复审目录和指定临时目录，并限制网络、真实卷及用户实际图库读取。make/git 的系统启动器尝试建立系统临时缓存，被沙箱拒绝，日志保留错误文本；相关命令仍成功，没有扩大写入边界或重跑完整检查。未操作真实卡、相机、现有服务或用户图库；未联网、未开子代理。所有故障输入为合成数据，临时 Git 标记目录不是真实 Git 写操作。上述目录与卷证据是本机文件系统模型，未做真实 FAT/exFAT、真卡插拔或相机验收。

本轮收据计时为 2026-11-01 04:04:00 至 04:26:09，UTC+8，共 22 分 9.8 秒；在此之前已完成卷空间、身份和初始清单的只读预检。指定临时目录已删除，清理结果和样本结束核对见 [final-receipt.json](final-receipt.json)。仅保留脚本、日志、摘要和报告。

复跑本轮独立用例可用下面命令，当前产品问题会使 pytest 退出 1。准备脚本仅复用本机离线缓存；复跑前仍须核对卷和被审输入。

```sh
review_dir=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_a1a_r3
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio
/usr/bin/python3 -I -B "$review_dir/prepare_environment.py"
/usr/bin/python3 -I -B "$review_dir/run_local.py" --name repeat-r3 --timeout 2700 -- \
  .venv/bin/python -B -m pytest -q -c pyproject.toml --rootdir="$review_dir" --noconftest \
  "$review_dir/test_r3.py" "$review_dir/test_samples.py"
```
