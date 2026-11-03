需要人工确认

main 已准备七条本地提交，未推送。公开提交与本地数据分开保留。仍需人工确认的内容是未提交的 `decisions.tsv` 新增记录、3,671 条来源或内容未确认的路径，以及封存后继续变化的并发工作版本。完整工作树不能直接整体暂存。

本轮起点为 `ae01c96c97be1d6edfa82d22e3109891dd906d5b`。仓库是公开的 `https://github.com/aa2246740/projectricoh.git`，物理目录是 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。开始时已核对 Workspace 为指定 UUID 的可写 APFS 卷，并读取盘根规则、仓库 `.gitignore`、`README.md` 和 `docs/HANDOFF.md`。

## 提交列表

| 提交 | 内容 |
|---|---|
| `dd95cda3e5fc90f7d5914511f9af03cd72da4e7b` | 工具和分析脚本、公开提交忽略规则、纯照片统计入口。 |
| `f0a568929f60164a103017cf9e961f42c28541c3` | 自编 C 源码、头文件、链接配置和 host 验证源码。 |
| `59166b8a8f4512079a8d6a18be6434d28a3dc7f2` | 可公开研究报告、决策记录、HTML 测试页及自编布局 JSON。 |
| `22e5e5582dd781ee73054b054cc81a014de59731` | README、历史交接提示、使用说明及第二台 Mac 的统计分工。 |
| `bfb8bcbb005dcc04f3c20616e23eaaa857453e6b` | 补审后加入纯统计入口所需的三个解析/数学辅助模块。 |
| `f7e322a2755dd2b0c260e496688325a3ed776c54` | 审计清单、回执和七张已重建核对的纯色测试图。 |
| `HEAD`，交付时的本报告所属提交 | `Record concurrent work left local after sync`，记录封存后继续写入的本地工作及其排除规则。 |

最后一条提交不能在自身内容里写入自身 SHA，使用本报告所属提交表示。交付时可用以下命令读出全部完整 SHA。

```sh
git log -7 --format='%H %s'
```

所有提交均在 main，保留原历史；每条提交正文最后一行都是用户指定的共同作者。

```text
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

提交邮箱沿用仓库已设置的 GitHub 隐私邮箱。本轮没有删除工作文件、改写历史、推送或操作相机、存储卡。唯一网络操作是只读 `git fetch --no-tags origin main`；该次 fetch 时本地和远端 main 均在起点提交。

## 每条路径的分类

开始时常规 Git 状态为 583 条。用 `--untracked-files=all` 展开后，冻结清单共有 117,086 条路径，包括大量生成证据和重复验证树。独立的 `studio/` 仓库按主仓 Git 状态中的一个目录项记录，没有改成子模块。

| 初始清单分类 | 数量 | 处理 |
|---|---:|---|
| commit | 6,185 | 审核后提交的源码、报告、说明和自编测试数据。 |
| keep-local | 107,230 | 固件、生成证据、数据快照、包、日志及独立仓库等，保留本地。 |
| unsure | 3,671 | 内容命中或来源未确认，保留本地并单列。 |

另新增 18 份公开交付文件，包括统计/审计工具、依赖版本、跨机说明、七份审计记录，以及原先被忽略的七张自编测试图。最终公开变更共 6,203 个文件。初始已经被忽略的固件、照片、`deep_tables.c` 和各任务 `local/` 不在上述初始计数中，继续留在本机。

逐条分类和原因保存在以下文件。

- `local/classified.jsonl` 是完整清单，含初始每条路径和本轮新增交付文件。它约 27 MB，留在本地。其 SHA-256 写在 [SUMMARY.json](SUMMARY.json)，没有把大文件提交到公开仓。
- [ADMISSION.tsv](ADMISSION.tsv) 列出 6,203 个公开文件及审核原因。已有源码和数据带 SHA-256；审计记录自身按最终提交对象核对，避免循环哈希。
- [UNSURE.tsv](UNSURE.tsv) 逐条列出全部 3,671 条不确定路径及原因。
- [KEEP_LOCAL.tsv](KEEP_LOCAL.tsv) 将初始 107,230 条及后续新增 13 条本地路径归为 1,216 组，共 107,243 条；组内精确路径在完整本地清单中。
- [LATE_LOCAL.tsv](LATE_LOCAL.tsv) 记录封存后产生的 17 个本地工作版本，含 4 个已跟踪文件的新版本及 13 个新路径。它与初始路径分类按版本区分。
- `local/initial-status.nul`、`local/initial-paths.json` 和 `local/initial.json` 保存开始时的原始状态、起点和时间。

完整本地清单及排除项的新增内容没有进入 Git。所有公开文件均低于 5,000,000 字节。

## 留在本机的内容

初始 keep-local 共 107,230 条，后续另加 13 条。以下是代表项，完整分组见 `KEEP_LOCAL.tsv`。

- `artifacts/` 中的固件卡包、恢复包、构建结果和证据，包括带 `SD_ROOT` 的目录。
- `research/color_calibration/firmware_parameters.json`、`research/contrast_curve/conditional-nine-levels.csv` 等数值数据和生成快照。
- 各验证树的 decode、disasm、candidate、baseline、evidence、build、host、runs 等输出与复制目录。
- `studio/` 的独立仓库。
- `decisions.tsv` 的当前工作文件。新增记录中有原厂混合系数和具体字节改动，本轮整份不暂存；完整原件另保存在 `local/frozen-decisions-original.tsv`。

`decisions.tsv` 已经被 Git 跟踪，`.gitignore` 无法屏蔽它的修改；后续三份报告的新版本也有同样限制。它们均保留为未暂存修改。不要用 `git add -A` 或 `git commit -a` 将本地工作版本直接带入公开提交；审计脚本也会拒绝本轮暂存 `decisions.tsv`。

新增 10,078 条目录/路径排除规则，并补上整个 `artifacts/`、所有 `local/`、固件文件名、DAT/bin/elf、DNG/JPG、反汇编和构建文件规则。逐项 `git check-ignore --no-index` 已核对初始全部 110,900 条未跟踪排除项及后来新增的 13 条；已跟踪的本地新版本单独报告。自编测试图只允许固定七个文件名，其它页面输出仍被忽略。

## 来源尚未确认的内容

unsure 共 3,671 条，不参与本轮提交。以下是例子。

- `firmware/stage2j/tools/build.py` 等含原字节校验、长十六进制或数值常量的工具。
- `firmware/stage2j/abi.S` 等汇编源，尚未逐一排除原厂指令重放或摘录。
- `research/chart_v2/analyzer_selftest.py` 等带字节/数值测试常量但本轮未确认其来源的脚本。
- 含疑似反汇编、反编译代码块或表参数的报告、HTML 和证据文件。
- `research/g156/` 中原计划公开的 32 个文件。哈希复核发现 `r4_acceptance.py` 和 `r4_mount_restore.py` 在审查期间被修改，因此整块工作留在本机，避免混入正在变化的快照。

“unsure” 表示本轮没有足够依据公开，不表示已确认侵权或泄密。文件均保留，详细原因在 `UNSURE.tsv`。

## 封存后的并发工作

本地时间 2026-11-04 01:15:05，收尾检查发现另外的活跃任务仍在写文件。`LATE_LOCAL.tsv` 记录该时点的 17 项路径、分类、工作版本哈希及已有公开版本哈希。

- 已跟踪的 `research/emulator_fast_r1/PROGRESS.md`、`REPORT.md`、`strict_r3/PROGRESS.md` 出现新工作版本。此前审核的快照已提交；这些后续版本保留未暂存。
- `research/emulator_fast_r1/strict_r3/` 新增报告、哈希清单和 HTML；`research/review_emulator_fast_r4/` 新增审查脚本与输出，共 13 个新路径。本轮保留本地并补上排除规则。
- `decisions.tsv` 仍按原有本地保留决定处理。

清单计数以记录的截止时间为准。活跃任务之后继续写入的内容属于后续本地工作，不属于这次封存的公开快照。

## 扫描和验证

候选文本经过凭据模式、长十六进制/字节串、数值数组、原厂表措辞、反汇编格式和源码字面量检查。凭据扫描不输出匹配值。初始内容审查覆盖 16,547 条候选或来源未明路径；提交前另扫描实际暂存的 Git 对象，并与审核 SHA-256 核对。

最终提交对象的禁止路径、超限文件、未知二进制和凭据检查均通过。词语与字面量命中保留了具体解释：格式标识、PNG 签名、合成自检数组、排除路径，以及只在运行时读取本地表的解析/数学代码。没有把含原厂数据的命中自动当作可公开。

另用本机 Gitleaks 8.30.1 对新增提交范围做离线补扫，没有发现泄露。脱敏扫描回执保存在 `local/gitleaks-commits.json`，最终提交后再核对一次。

可重跑的对象检查如下。输出写入被忽略的 `research/git_sync/local/`，不会暂存或修改源码。

```sh
/usr/bin/python3 -I -B research/git_sync/audit_sync.py verify --ref HEAD
```

该命令检查起点至指定提交的实际 Git blob，列出需人工解释的内容命中。原始逐组检查结果和最终读回结果均保留在 `local/`。本轮检查的是新增提交范围，没有将它写成旧历史的完整数据清理结论。

照片入口另做了实际交付文件验证，回执见 [PROBE_CHECK.json](PROBE_CHECK.json)。从 Git 暂存对象导出 20 个公开文件，包含 11 个 Python 文件、依赖版本和 8 个测试数据文件。在这个没有固件包、私有模型或旧 `closed_loop` 代码的副本中，读取了三对原始 DNG/JPG。

| 帧 | 识别 | 色块数 | 通过全部块级质量门槛 |
|---|---|---:|---:|
| R8051269 | 50mm 白页，P0 | 1 | 1 |
| R8051270 | 50mm 测量页，P1 | 116 | 10 |
| R8051262 | MOUNT 测量页，P1 | 116 | 81 |

三帧解析和 RAW/JPG 配准通过，输入哈希前后相同，MOUNT 的未知光圈保留为空。233 个块均导出读数，只有 92 个通过全部块级质量检查；其余块保留标记，不作为有效拟合样本。七张纯色测试图与布局 JSON 还从生成器重新构建，8/8 SHA-256 与待提交原件一致。

这是本机公开文件副本与既有照片的验证。没有在第二台实体 Mac 运行，没有重跑全部固件构建、host 测试或相机/卡验收。

## 第二台 Mac 的照片分析分工

完整文件名、包版本、命令和旧色环入口见 [PROBE_ANALYSIS.md](PROBE_ANALYSIS.md)。

第二台 Mac 需要准备 Python 3.14.7、NumPy 2.4.3、Pillow 12.2.0、SciPy 1.17.1，以及私下复制的同名 DNG/JPG 和可选人工帧 manifest。公开代码、测试图及布局随 Git 提供；不需要 M32R、rawpy、OpenCV、ExifTool，也不需要从第一台 Mac 复制理光固件或提取表。

第二台 Mac 只跑 `extract_probe_stats.py`，负责配对、页码识别、RAW/JPG 配准、逐块统计与质量标记。配方槽号由人工拍摄记录填写；不能从彩色 EXIF 选择器自动猜。RAW 元数据从输入 DNG 读取，留在本地输出里。

它私下交回逐帧 JSON、`patches.csv`、manifest、`provenance.json` 和 `SHA256SUMS`。第一台 Mac 按原图哈希绑定统计，再用本地 DAT、原厂行、surface bank、标定模型和目标数据做拟合或评分。这些依赖包含理光及第三方来源数据，继续留在第一台 Mac，保持解析统计与模型回拟分开。
