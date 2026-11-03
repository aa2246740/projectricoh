修改后再提交

本轮确认 1 项 P1：同场景照片的局部目标已经移动，对齐门槛仍放行，正常导入显示 `ready`、导出返回 `hdr=true`，没有 HDR 失败提示。错误增益也出现在 macOS ImageIO 的实际解码结果中。应先修复这一项，再提交并推送。

本报告只评价 `main`、HEAD `cb23e70d21f3cc63b809350942d3bc61513ec6c5` 上这批未提交的 HDR 改动。原实现清单 25 项 SHA-256 全部匹配；实际为 23 个未提交文件，即 15 个修改、8 个新增，与任务描述的 20 个有出入，和 `CHANGES.md` 一致。

复审日期为 2026-11-01，宿主为 macOS 27.0.1、Python 3.14.7。

## P1：局部移动超出搜索范围，仍被判为对齐

位置：[gain.py:159](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/hdr/gain.py:159)、[gain.py:216](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/hdr/gain.py:216)。导入和导出共用这一门槛。

输入是两张同场景照片的错配，用确定性的合成画面复现：384×576，背景相同，一个 40×40 像素的深色目标从 `(420,96)` 移到 `(500,96)`。JPG 使用后一张，DNG 使用前一张。没有修改运行中的产品函数。

| 检查 | 实测 |
|---|---|
| 已知局部位移 | 主图 80 像素，增益图网格 20 格 |
| 门槛给出的结果 | 相关系数 0.780，缩放 1.0，平移 `[0,0]`，`tiles_moved=0` |
| 正常导入接口 | `hdr=ready`，HDR 任务 `failed=0` |
| 正常导出接口 | `hdr=true`，`hdr_note=null` |
| 与正确 DNG 参考比较 | 旧目标位置的增益中位差 0.3032 档，最大差 0.8062 档 |
| ImageIO 实际解码比较 | 同一区域中位差 0.3044 档，最大差 0.7589 档 |

根因是局部核对只搜索 ±3 格，而且只在更优平移带来超过 0.1 的相关系数提升时计为错位。目标已经移动 20 格，在这个小范围内找不到对应位置，仍然可能得到零个错位块。全局相关系数被相同背景维持在合格范围内。

应增加局部对应关系的可信度或残差门槛。无法可靠验证的区域应导致 `HdrUnsupported`，不能把“没有在 ±3 格内找到更优位置”视为已经对齐。修复后，这个输入应在导入时记为不支持，导出时返回 `hdr=false` 及原因，同时保留现有正确配对样本的验收。

证据是 [alignment_detail.json](alignment_detail.json)、[edit_summary.json](edit_summary.json) 和 `evidence/` 中的 5 个合成文件。实际导入文件 SHA-256 为：

```text
a70d8c199f8d07d4daee52ec4c6fa8c798442b5afde53a936b0e6014405691f9
```

最小复现只在内存中构造照片，不写文件。当前版本输出 `rejected=false` 并退出 1：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/nice -n 10 studio/.venv/bin/python -I -B research/review_studio_hdr/reproduce_local_motion.py
```

## 六项重点复核

### 1. 主图、MPF、XMP、ISO 字段

独立解析器是 [format_oracle.py](format_oracle.py)，没有复用产品的 JPEG/MPF/ISO 解析函数。39 份相机派生文件包含 MOUNT 15 对、50mm 16 对和 8 种方向的合成输入；另核对正常导入的 4 份派生文件及 20 份实际导出对照，合计 63 组主图与封装检查，均通过。

主图按原有保留段及完整 `SOS…EOI` 比较字节，另核对 Pillow 解码像素完全相同。封装替换旧 MPF/XMP/ISO；原文件和不勾 HDR 的 SDR 导出是各自的比较基准。

| 字段 | 核对结果 |
|---|---|
| EXIF、ICC、DQT、SOF、DHT 及压缩扫描 | 未替换段字节相同，`SOS…EOI` 字节相同，主图像素相同 |
| MPF TIFF 头和目录 | 大端，标识 42，B000=`0100`，B001=2，B002 为两条共 32 字节的记录，后续 IFD=0 |
| MPF 主图记录 | 属性 `0x030000`，偏移 0，长度等于主图 EOI 后的位置 |
| MPF 增益图记录 | 属性 0；偏移以 TIFF 头为基准，准确指向第二幅 SOI；两幅首尾相接到文件末尾 |
| 主图 XMP | `hdrgm:Version=1.0`；Container 为 Primary、GainMap，两者 MIME 均为 JPEG；GainMap Length 等于第二幅实际长度 |
| 增益图 XMP | Version=1.0、BaseRenditionIsHDR=False，7 个数值字段与 ISO 分数一致 |
| 主图 ISO | 命名空间正确，minimum/writer version 均为 0，仅有 4 字节版本内容 |
| 增益图 ISO | 版本均为 0，flags=`0x40`，单通道，命名空间后的内容为 61 字节；分数符号和分母有效 |
| ISO 数值 | GainMapMin、HDRCapacityMin=0；Gamma=1；两种 Offset=1/64；HDRCapacityMax=GainMapMax |
| 增益 JPEG | 8 位灰度，宽高分别为主图尺寸除以 4 后向上取整 |

字段布局依据冻结原型的定义，另用系统解码交叉核对，没有联网获取规格文本。4 张 MOUNT 与原型的增益图解码像素及 ISO 数值完全一致。

ImageIO 验证覆盖 26 份上述输入和 20 份实际导出，46/46 识别成功。采用双线性放大的增益图、规格公式及 4×4 亮度块比较，提亮误差 p99 最大为 0.0342 档。此计算方法与原实现自检的整块重复放大不同，不应直接比较两份报告的 p99 数字。

真实相机 JPG 的系统 SDR 解码最大差为 1；合成 JPG 和这些合成导出的最大差为 3。ISO 版本段单独增加的对照产生同样差异，且与完整 HDR 的系统 SDR 像素完全相同。原压缩字节和 Pillow 像素均未改变。这是系统解码路径的差异。

详见 [format_summary.json](format_summary.json)、[format_cases.jsonl](format_cases.jsonl)、[export_imageio_cases.json](export_imageio_cases.json)。P1 文件本身也能被系统正常解码，局部增益错误仍在。

### 2. 写入边界和原片

新增派生 JPG 和原因 JSON 依次经过 `Library.check_write`、`privacy.PrivateDir`、`replace_file`。启动路径检查已包含 `.studio/hdr`。用户导出的 JPEG 沿既有照片导出通路处理，使用 `check_destination` 核对实际位置；它不调用 `PrivateDir`。

主机上的 11 个缓存路径场景和 3 个 HDR 导出路径场景结果如下，均使用 Scratch 内的合成卡，未访问真实存储卡。

| 场景 | 结果 |
|---|---|
| 启动前图库根、`.studio`、`.studio/hdr` 指向合成卡 | 启动拒绝，卡目标未变 |
| 运行中 `.studio`、HDR 根或分片子目录指向合成卡 | JPG 和 JSON 写入均拒绝，未出现卡写入事件 |
| HDR 目录指向图库内部已登记的卡根 | 拒绝，卡目标未变 |
| 目标位于含 `.git` 目录或 `.git` 文件的工作区 | 拒绝创建 HDR 文件 |
| 最终 JPG 文件名是指向卡文件的链接 | 只替换本地链接；卡文件哈希不变，没有写打开卡文件 |
| 已打开的 HDR 目录被移入合成卡 | 目录句柄真实位置核对拒绝，卡目标未变 |
| HDR 导出到合成卡、指向卡的链接、图库内部 | 全部 HTTP 422、`bad_destination`，卡文件哈希不变，卡写入事件为 0 |

最终文件链接这一项有一条 `os.rename` 审计记录被解析成卡目标路径；实际改名操作替换本地链接，未打开或改写卡文件。因此没有把该场景报告成“零条审计记录”。详见 [path_cases.json](path_cases.json) 和 [export_path_cases.json](export_path_cases.json)。

正常导入时，合成卡原件与图库原件的 JPG/DNG 哈希相同；本轮结束重新核对的全部真实样本哈希也未变。完整检查中的 HDR 失败隔离、默认开关及原片保留测试通过。未发现新增的写卡、丢片、原片改写或推出状态误报问题。

`make check` 的仓库及分发包内容检查通过，输出 `private bytes: checked 249 files`。本轮没有把真实照片或相机数据复制到工作室仓库；留下的 5 个图像证据文件全部为合成数据。

### 3. 对齐样本

| 独立样本组 | 结果 |
|---|---|
| MOUNT 正确配对 15 对 | 15/15 生成 |
| 50mm 每 10 张取一张，共 16 对 | 16/16 生成 |
| 50mm 相邻另一张 DNG 16 对、MOUNT 另一张 DNG 4 对 | 20/20 拒绝 |
| 同场景局部目标移动 5 组 | 4 组拒绝；40×40 目标移动 80 像素的一组放行，即 P1 |
| 对真实 MOUNT JPG 合成径向校正 5 组 | 4 组拒绝；系数 0.002 的一组放行，角点最大位移 10.29 像素，相关系数 0.907、错位块 0 |

这些结果不能支持“做过畸变校正就一定会拒绝”的保证。径向校正的较小误差没有单列另一个 P1，明确的阻断依据是上面的局部移动及实际增益错误。数据见 [alignment_cases.jsonl](alignment_cases.jsonl)。28mm 仍无样本。

### 4. 编辑后导出

28 项独立检查通过。包含实际导入、方向 1/6/7、旋转、翻转、拉直、裁切、256 像素长边、6 种边框、日期戳、曝光和主曲线。

用 Pillow 独立计算旋转、翻转、裁切及画布位置，3 组浮点 RAW 亮度层比较的最大差均为 `1.1921e-7`，照片区域掩码相同。20 份实际 HDR 导出均与对应 SDR 导出的保留主图字节和像素相同，也全部通过 ImageIO 检查。

编码后的边框增益最大 0.06892 档，各场景均值最大 0.00144 档；日期戳像素增益最大 0.06203 档，均值最大 0.00588 档，符合“接近 0”。不能称编码后的每个像素严格为 0。曝光 +0.7 EV 及曝光 -0.5 EV 加主曲线两组重新拟合、封装和系统解码均通过。详见 [edit_cases.jsonl](edit_cases.jsonl)。

### 5. Linux CI

新增 ImageIO 条件确实使用 `os.uname().sysname` 和 `swiftc` 是否存在。四个独立进程核对了宿主判断组合：Linux 即使 `sys.platform=darwin` 且存在 Swift，也会跳过；Darwin 即使 `sys.platform=linux`，仍按真实宿主判断。详见 [platform_cases.json](platform_cases.json)。

无样本检查使用逐文件相同的 246 个工作室文件、保留只读 Git 元数据入口，并关闭 ImageIO 条件。两个串行进程合计 619 passed、1 failed、146 skipped，覆盖率 89.64%，零重跑。失败是动态 HDR 状态的快照比较，见下节 P2。

未发现新增代码使 Linux 分支必然失败的证据。本机实际内核仍为 Darwin，这不是 Linux 内核上的执行结果，也没有在线 CI 结果。

### 6. 完整 make check

在原工作室仓库以前台等待方式跑完整检查，未改 Makefile、源码或测试。`nice -n 10`，离线，缓存与临时目录在指定 Scratch 中，pytest basetemp 同样隔离；总超时 7200 秒。使用 `--force-reruns 0` 覆盖 Makefile 的默认重跑设置。

首次实际 pytest 结果为 763 passed、3 failed，覆盖率 92.00%，802.65 秒；整个 `make check` 813.56 秒、退出 2。没有再次跑全量 `make check` 来取得绿色结果。

| 失败 | 分类与依据 |
|---|---|
| `test_rebuild_endpoint` | 产品新增动态状态与旧测试比较方式冲突，属下述 P2；无样本复验同样失败 |
| `test_studio_shuts_down_cleanly_on_sighup` | 本轮最初沙箱禁止了本机监听；允许本机绑定后，在无样本检查中通过 |
| `test_cli_binds_only_loopback` | 同上；原始异常明确发生在 `sock.bind`，无样本检查中通过 |

Lint、类型、秘密及内容检查、依赖/分层检查等前置项通过。原始完整结果保留在 [make_check_full.log](make_check_full.log) 和 [make_check_full_result.json](make_check_full_result.json)。实现者声称的“766 项全部通过”没有在本轮零重跑检查中复现。

## P2，留到下一轮

1. [test_api.py:208](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/tests/test_api.py:208) 对两次完整照片 JSON 做相等比较，新增后台 `hdr` 状态会从 pending 变为 ready/unsupported。本轮有样本、无样本检查均因此失败。应等待 HDR 任务结束，或只比较重建应保持不变的字段。这会影响 CI 稳定性，但尚不能归为“Linux 必然失败”。
2. [app.py:106](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/app.py:106) 关闭图库前没有收束 HDR 线程。[derived.py:129](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/hdr/derived.py:129) 的待处理查询又在逐张异常处理范围外。原始日志已有 HDR 任务访问已关闭图库、触发 `on_job_failed` 的记录。应在关闭图库前取消并等待任务退出，并处理整轮枚举失败。未观察到照片丢失、写卡或推出误报。

## 记录完整性和未运行部分

- 开始和结束共核对 1479 个冻结文件，包括 246 个仓库工作文件、2 个 Git 元数据文件、1221 个样本目录文件和 10 个实现/原型文件。结束时没有变化，HEAD 和 Git 状态相同，初末 diff 字节相同。见 [frozen_inputs.json](frozen_inputs.json)、[input_verification.json](input_verification.json)、[source_diff_receipt.json](source_diff_receipt.json)。
- 运行期间没有联网、Git 写操作或子代理；没有访问真实存储卡、指定禁用端口或用户实际图库。行为检查串行运行，测试及其必要子进程最多 2 个；测试进程均继承 nice 10。
- 全量检查之前有一次前置打包停止，原因是复审复制离线缓存时漏了 `tomlkit`；pytest 尚未开始。补齐本机已有缓存后才进入上述完整检查。原始记录是 `make_check.log`，没有删除。
- 独立格式脚本最初把合成 JPEG 的系统 SDR 差也限定为 1，观察到 3 后停止。后续 ISO 单段对照确认了原因；最初日志和数值保留在 `format.log`、`format_initial_system.json`。路径脚本最初把最终链接的改名审计记录也视为卡写入，已按实际文件变化和操作语义核实，原始 `paths.log` 保留。
- 首次无样本检查在 75% 提前以退出码 0 结束，未写 pytest 汇总和覆盖率，未计为通过。既有 `test_worker_result_files_and_parent_watch` 留下的监视线程会受后续全局进程状态测试影响，随后终止测试进程。复验把此项与其他项分在两个串行进程，不改测试文件、不自动重跑，并以 session-finish 收据核对全部 766 项。见 [portable_summary.json](portable_summary.json) 及 [portable_detail.log](portable_detail.log)。
- 本轮没有 iPhone 实机、真实 Linux 内核或 28mm 验证。主机格式、解码和路径结果不替代这些验收。
- 指定 Scratch 根目录已删除，包含 TMPDIR、pytest basetemp、源码副本和缓存。见 [cleanup.json](cleanup.json)。报告、原始结果、复验脚本、覆盖率数据及合成证据留在本目录；`SHA256SUMS` 的路径均相对 projectricoh 根目录。
