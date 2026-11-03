修改后再开工

# 工作室“相机管理”设计复审

日期：2026-10-31。复审对象是 `research/studio_camera_manager/DESIGN.md`，并核对两份被合并设计、现有工作室源码、g139 固件检查和本机发布包。

A1 的身份绑定、备份持久化、失败恢复和白名单还存在阻塞。尤其是继续按挂载目录名使用照片导入缓存，会把另一张卡上的新照片当成已经导入；用户随后格式化卡会丢失尚未备份的照片。先修改下列设计约束，再进入实现。

本报告只规定复审结论和验收用例，没有修改设计或产品代码，没有运行工作室测试套件、服务或相机模型，没有访问用户工作室实例、用户图库/应用数据或存储卡，没有联网、git 写操作或子代理。实际写入仅为本目录的 `REVIEW.md` 和 `SHA256SUMS`。本轮执行的只读小检查与待实现验收用例分开记录。

工作室 HEAD 为 `1407830ee7c32fff892b23f2ddbfeb2bafd95b45`。开始时已有 `src/gxr_studio/raw/PROVENANCE.json`、`src/gxr_studio/raw/tiff.py` 的未提交改动；本报告不改动它们。结论绑定文件摘要，不把 HEAD 当成全部工作区内容的身份。

P1 表示必须先修正设计中的安全约束；P2 表示应在对应分期实现前明确的行为、事实或验收缺口。下文路径均相对仓库根。

## P1

### P1-01：沿用挂载目录名 seen 缓存会漏导照片，可能在随后格式化时造成照片丢失

位置：主设计 `:200-201、:209`；`studio/src/gxr_studio/cards/discovery.py:25-28、:91-94`；`cards/importer.py:457-465、:650-659`；`library/store.py:200-206`。

当前 `Card.key` 确实是 `sha256(label)[:12]`，但 `label` 实际来自挂载目录名 `entry.name`，不是通过系统接口读取的卷标。两张卡先后复用同一个挂载目录，或多个配置的卷根下出现同名目录，都会复用该 key。不能据此断言在 macOS 同一个卷根下，同卷标双卡同时插入必然得到相同 key；挂载目录名可能不同。本轮没有枚举或读取实际卡。

问题不只影响未来写卡选卡。`seen_hit` 只比较卡 key、相对路径、大小和 mtime；默认导入一旦命中，直接返回，根本不读文件，不进入内容 SHA 去重。只读内存检查用现有 `Card.key`、`Library.seen_hit`、`_import_shot` 函数体及内存 SQLite 复现了内容不同却 `seen_shots=1` 的结果。设计所说“seen 仍用卷标，不改语义”必须删除。

最小修改：写卡身份和导入缓存同时迁移。新 seen 使用可信卷身份分区；旧卷标缓存按不可信处理，首次重新读内容后再建立新记录。无 UUID、身份歧义及无法判断是否重新格式化时，不得仅凭元数据跳过照片，更不能据此提示照片已经完整备份。验收：ID01、ID02、ID04、DC02。

### P1-02：VolumeUUID 适合作卷身份，不能单独充当物理卡身份或恢复授权

位置：主设计 `:190-202、:245、:265-266、:310-322、:647-648`；`studio/src/gxr_studio/api/routes.py:103-107`、`api/camdata_routes.py:129-141`。

改用 VolumeUUID 的方向正确，能解决挂载名复用。但设计仍把 UUID 缺失时的 `卷标 + st_dev` 当作可恢复身份，并将“UUID 不同”直接解释为“原卡格式化了”。插入另一张卡也会得到不同 UUID；复制的卷身份还可能相同。短哈希也必须处理碰撞，不能沿用 `next(... if key == card_id)` 的取第一项行为。

最小修改：完整 UUID 用于历史关联；每个发现结果另绑定唯一的本次挂载会话，写入和推出均验证该会话。UUID 缺失的卡只允许只读识别，或在用户明确选择后仅于当前挂载内写入，禁止跨插拔自动恢复。重复 UUID/短 id 歧义返回冲突。B 卡的出现不得使 A 卡的日志自动“已放弃”；只有能够明确关联的事件或显式放弃操作才能改变原日志。多卡枚举、备份、导入、写入、恢复、推出必须使用同一套解析规则。验收：ID02-ID05、ID08。

### P1-03：按“每个文件前检查一次”不足以约束换卡、过期 plan 和审计放行

位置：主设计 `:265-279、:285-302、:803-806`；原写卡设计 `:131、:277`；`studio/src/gxr_studio/audit.py:113-145、:174-190`。

A1 只有一个文件，如果只在开始时检查一次，备份后至 rename/清理前的换卡、同卷 DAT 被外部修改、草稿变更都没有明确处理。复用挂载路径后，按路径进行的清理、rename 或 eject 可能落到新卡。主设计还漏掉原设计“DAT SHA/长度变化也使 plan 失效”的明确约束。

现有审计也不能直接承接目录 fd 方案。`_norm` 把相对路径按 cwd 展开，忽略整数 fd；`os.rename` 的源/目标 dir_fd 没有参与归一化。模拟审计参数的只读检查确认，`open("GXRCE.TMP", dir_fd=...)` 一类事件会被记到仓库 cwd 下。审计钩子本身也不能覆盖所有 fd 写入，不能作为唯一隔离边界。

最小修改：plan 固定源 DAT 的存在性、SHA/长度、目标文件集合及摘要、草稿/配方版本和挂载会话。使用经验证且不跟随链接的目录句柄，所有修改只能相对该句柄执行；在每次修改、清理和推出边界验证会话及预期文件状态。写卡 I/O 收敛到专用对象，作业权限必须限定到持有该能力的作业，不能向进程内所有调用放行同名文件；审计按真实 dir_fd/fd 与作业归属记录，rename 两端均须属于同一作业和目录，退出时关闭 fd 并撤权。验收：ID06-ID08、DC05-DC10。

### P1-04：备份/日志的持久化顺序与恢复冲突尚未定义，断电后不一定能恢复

位置：主设计 `:272、:285-319、:321-322、:629-639`；原写卡设计 `:150-164、:180-186`；`studio/src/gxr_studio/lut/service.py:105-112`。

“备份读回 SHA 一致”和“日志写临时文件后 replace”不能证明断电后备份、目录项和日志仍在。现有 JSON 帮助函数会 fsync 文件，但没有提交父目录；不能直接把它当成跨电源中断的事务证明。设计也没有定义创建 TMP 后、所有权日志提交前崩溃时能否删除该 TMP，或旧日志遇到第三份 DAT 时是否仍可覆盖。

“最终读回错了就重写一次”还须保留最初的有效备份，不能让重试备份的坏 DAT 成为唯一恢复源。F_FULLFSYNC 的真实 I/O 错误、目录同步失败、F_NOCACHE 失败、短写和重挂载均需要明确的失败状态，不能吞掉错误后标 verified。

最小修改：先固定并持久化备份 blob、快照清单、恢复所需目标和写入意图日志，再允许第一次卡上修改；明确数据、文件改名与父目录的持久化步骤及错误处理。日志只是线索，恢复必须重新核对当前对象、旧/新摘要及所有权；无法证明归属或出现第三份内容时停为冲突。最终内容、独立校验、非目标保护断言及本地状态提交都通过后才报整个作业成功。启动/插卡只发现未完成作业并提供恢复入口，不启动新的写入。限定的一次重试不扩展成自动修复循环。

还须收窄“写坏了只是没配方”的说法。resident 拒绝坏 DAT 属于相机加载逻辑；它不能证明 FAT/exFAT 的分配表、目录及 SD 控制器在拔卡或断电时只损坏 DAT。F_NOCACHE 读回也不证明介质掉电后的持久性。发生卷不可读或分配链异常时，工作室应停止修改，保留电脑备份，不自动修复文件系统。用可丢弃镜像验证真实驱动语义，仍不得把镜像或打桩结果写成真卡断电安全。验收：TX01-TX18。

### P1-05：DCIM 读取异常不能被当作空卡，照片保护断言不能跳过不可检查部分

位置：主设计 `:220、:237、:246-249、:293-295、:624`；`studio/src/gxr_studio/cards/discovery.py:98-108、:111-161`。

现有 `scan_card` 在找不到或读不了 DCIM 时可以返回空列表，子目录错误只有调用者传 `errors` 才可见；顶层 `_find_dcim` 还使用会跟随链接的 `is_dir()`。设计没有要求这些错误使写前检查失败，且产品保护断言只看名字、长度和 mtime，忽略所有点文件，弱于验收表中的 SHA 断言。

最小修改：候选卷可以没有 DCIM，但“可写相机卡”必须有真实、可完整检查的 DCIM。扫描失败单列状态，禁止写入；照片数为 0 不能代表没有照片，更不能代表可以格式化。保护范围包含 DCIM 的全部内容与根目录非目标项，系统元数据例外只列明确的卡根项目，不把 DCIM 中所有点文件排除。运行时检查失败或非目标项改变不能报成功；测试用独立内容哈希证明正常路径未改照片，审计和 I/O 入口证明没有照片写调用，二者不互相替代。验收：DC01-DC04。

### P1-06：恢复未知 DAT 和按 role 放行候选/测试版，会绕过“只写已批准发布版”

位置：主设计 `:118、:171-188、:273-276、:321-322、:354-357、:509-512`。

§3.6 同一句同时要求“快照过白名单”和“未知 DAT 可以原样写回”，无法同时成立。§2.4 又把 `role∈{release,test}` 全部加入可写名单，没有约束 `status=candidate`。文件 SHA 等于版本 JSON 只能说明与该记录一致；导入的 JSON 不能成为授予写卡资格的新白名单。

最小修改：把“认识这份 DAT”和“允许把它写成目标”分开。诊断、未知、损坏文件可以只读收回，不可设为当前、生成可写版本或绕过恢复入口。A1 目标必须是工作室随代码登记、已批准用于该机身的发布文件；A3 对冻结的 g139 测试包作明确测试例外，不泛化为任意 test/candidate。用已批准发布版替换诊断/未知旧文件仍然允许，但先完整备份并带对应确认。所有 install、restore、resume、imported kit 共用目标校验。清空条目只允许规范化用户可变区及相关 CRC，不能先修复其他字节再算模板身份。验收：WL01-WL06、PR08。

### P1-07：默认存到仓库外不等于“理光字节绝不进公开仓库”

位置：主设计 `:111-132、:482、:503-513、:666`；`studio/src/gxr_studio/config.py:15-24、:53-60`；`studio/.gitignore:24-31`；`studio/.githooks/pre-commit:5-9`。

默认应用数据与导出目录确实在仓库外；但 `GXR_STUDIO_HOME` 和 `GXR_STUDIO_EXPORT` 可直接改到仓库内，设计没有路径约束。嵌套的 studio 是独立 Git 仓库，不能依赖父仓库的 ignore。只读 `git check-ignore` 证实，studio 中无后缀 `camera/blobs/<sha>`、根目录 `private.gxrkit`、`GXRFX.BIN` 和改名 DAT 都没有被忽略。88 KB DAT 也不会被 1 MB 大文件检查挡住，秘密扫描不会识别理光数据。

最小修改：每个会产生私有字节的入口都验证实际目标目录，拒绝落进主仓库、studio 或其他 Git 工作区，以及经链接进入这些目录；也拒绝应用数据/导出目录指向卡根、DCIM 或受保护图库。补齐受限产物忽略与提交/分发检查，覆盖 blobs、效果文件、归档、改名产物及失败附件；路径约束是第一道防线，检查不能只依赖文件名。测试夹具自己生成；真实 DAT 及其切片、hex/base64 不入仓库。本轮按已跟踪文件名检查没有发现 GXRCE.DAT、GXRFX.BIN 或 gxrkit，此结果不等于全仓字节来源审计。验收：PR01-PR05。

### P1-08：gxrkit 只规定核 SHA，缺少归档路径和整体提交约束

位置：主设计 `:503-512、:664、:799-800`。

包含正确 SHA 的 ZIP 仍可带越界成员、链接、重复名字、超大展开内容及不一致清单。若按“逐个核 SHA 即导入”实现，解包阶段就可能覆盖应用数据之外的文件；SHA 不能检查解包路径，JSON 也不能提供新的写卡文件名或发布身份。

最小修改：定义成员集合、单项/总量上限、schema 和引用规则；不直接 `extractall`。拒绝绝对/越界路径、链接、重复及大小写归一化冲突，先在受控私有暂存中完成全部验证，再一次发布不可变版本。DAT 元数据从已校验字节派生，导入不设当前、不写卡；任何失败均不覆盖已有版本、照片或其他文件。验收：PR06-PR08。

## P2

### P2-01：修正机身指纹和 g139 黄金夹具的事实

位置：主设计 `:54-55、:65-66、:114-115、:145-149、:184-186`；`research/g139_fix/REPORT.md:18-20`。

DAT 的 `[48,80)` 当前实际为原厂机身指纹 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。发布包中补丁后 `ilaunch3` 文件本身的 SHA 是 `d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90`。两者需要不同字段，不能把后者拿去核 DAT 头。resident 的 `rv_header` 是把 DAT 头与 trust 的 body/build/ABI 比较，不是计算发布包 ilaunch3 文件 SHA。离线识别只能给出“该 DAT 适用于哪个机身版本”，不能证明当前实体机身已经装好它。

本机 `package_v38_g139_test/local/SD_ROOT/GXRCE.DAT` 已是 `2378a88c…`，条目为 `FCC-001`、`FCC*002`、`GRN*001`，第三条为 base=2、前四项 `[2,5,5,-5]`。设计与 g139 报告仍写旧的 `40bdfe76…`、`GRP-001`。两份都可归一化到同一个 g139 模板，但不是同一个黄金文件。不能以可变路径替代哈希钉子。详见后文只读核对表，验收 WL03、WL05。

### P2-02：cube 的主面板仍隐藏了成立条件，精度须测最终文件

位置：主设计 `:460-480、:687-690、:786`；`studio/src/gxr_studio/engine/model.py:18-23、:43-61`；`research/film_look_routes/ceiling.py:49-65、:85-101`。

“从 GXR 04 标准 JPEG 近似另一配方的电脑预测”这个定义诚实；“输出就是该配方在相机上的 JPEG”应收窄。模型仅对 50mm 有校准依据，04 的量化和剪切使某些场景无法反推，空间效果无法由颜色 LUT 表达。现设计把这些适用条件全部放进详细信息，主面板只叫“配方 LUT”或“GXR JPEG 用”，会把范围扩到其他 GXR 单元、图像设置和输入来源。

最小修改：导出按钮附近直接显示“GXR A12 50mm · 04 标准 · 默认设置 · sRGB JPEG · 电脑预测/近似”和设计规定的 ISO 范围；ISO100、其他单元及 RAW 的限制不能只藏在折叠区。指标定义为留出集 ΔE00 中位数/p95，不写成相机实测等效。达不到阈值时可导出，但主面板如实显示近似和质量结果。

研究拟合器使用三线性权重与自己的格点次序，工作室 Cube 使用四面体插值；精度必须针对最终导出的文件重读后计算，并用非对称通道向量检查格点/通道次序。现有只检查 33³、TITLE 和域的往返用例不足以证明颜色正确。验收：LU04-LU09。

### P2-03：十项用户决定应成为设计输入，手调保存还缺接口

位置：主设计 `:454、:508、:611、:706、:720-731、:786-800`；`studio/src/gxr_studio/lut/service.py:508-558`。

§8 的十项已由本轮用户决定，不再需要编排者选择。应同步删除 g137 单独上机、诊断/固件移除、效果分享等旧分支，修改默认“GXR 套件…”文件名，写入指定的备份警示和条件性 04 提示。README 采用 §6 草案，最终文案由用户定。

手调保存并入 A3 后，需要定义接受当前面板配方的保存入口、服务端合法性检查和 source.kind=manual；目前保存函数只能从 fit_job 取候选，接口草案也只改了拟合保存路径。它不能靠前端把手调值伪装成一次 LUT 拟合。验收：EN05、EN09-EN10、PR05、UI01、UI03-UI04。

### P2-04：不可变版本、卡上实际状态和外来条目保留须统一

位置：主设计 `:128、:150-156、:329-330、:451、:534-548、:584、:656-657`；原写卡设计 `:194-206、:321`。

设计和验收要求版本 JSON 不再修改，但示例把 written_to 放进版本，并写“相同字节时追加 written_to”。应统一为不可变版本加独立 state/写入日志。最近一次写另一张卡的版本也不能直接表示当前选中卡的“相机中”条目。

合并设计从“卡上列表为准”改为电脑当前版本为准，却仍继承“外来条目默认保留”的用例。电脑版本缺少卡上条目时，需要明确保存、合并或显式移除的行为；备份存在不能代替用户知晓条目被移除。删除导致合法改号后，保留应比较 base/levels 等语义，不能一面要求改号、一面要求所有原条目原字节保留。验收：EN07-EN08、UI02、ID06。

### P2-05：输入空间识别需要“未知”，storable_v1 必须约束整个搜索

位置：主设计 `:383-397、:424-430、:677-683`；`studio/src/gxr_studio/lut/fit.py:184-206、:311-334`。

少量灰轴阈值不能唯一识别 LUT 的输入空间，创意 S 曲线、反相或灰轴偏色也可能触发 Log 判断。结果必须允许未知，用户可以从全部支持空间中纠正，不能一旦判 Log 就只允许 Log 选项。

现有拟合的粗网格会遍历 amount 与色调起点，仅给 descend 的 names 参数设四项不足以保证所有候选都可存。新 profile 应约束全部搜索阶段及最终保存，范围由目标 v1 三单元交集决定。三档预测使用同一声明的评分口径，如实报告优化器结果，不能为了满足“后档必不差”而修改分数；近零分母需返回不适用。验收：LU02-LU03、LU10、EN03。

### P2-06：分享码最长 80 字符与 40 B 名字不相容

位置：主设计 `:488-498、:691-693`。

仅 v1 的版本、格式、基底、四档位加 40 B 名字就有 47 B。Base32 正文至少 76 字符，加 `GXR1-`、分隔符和 CRC16 表示后至少 86 字符，还没有计入可选名字长度字段。不能同时承诺 40 B 名字、完整往返和总长不超过 80。

最小修改：先定义完整 wire format，包括可选名字编码、CRC16 参数、规范化、字节数上限及总长；按真实上限验收，不截断合法名字。分享码仍只含条目，效果以后再说。验收：LU11-LU12。

## 只读核对结果

### DAT 和黄金向量

下表摘要均独立计算；未把任何 DAT、字节表或照片复制到交付目录。

| 对象 | 长度/B | 完整 SHA-256 | 本轮结果 |
|---|---:|---|---|
| g137 发布 DAT | 89936 | `78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8` | 当前 datcodec 可解析并逐字节往返。 |
| g139 发布候选 DAT | 88104 | `aab6c4f8d525dfda94fd33861c0a632b16f4d0df5481c7d9423e2bf820399e21` | 当前 datcodec 拒绝未登记的 139。 |
| 本机当前 g139 测试 DAT | 88104 | `2378a88c5f963ff58bb27e099d5e8668d721f043ce77d3f958b02d8e47c80dd5` | 与其当前 SHA256SUMS 一致；内容不是设计里的旧 TEST3。 |
| 旧 TEST3 逻辑向量，仅在内存生成 | 88104 | `40bdfe76482f0765f5f8f6be381d3f81862396010bb77b8fc3e09f975d16140a` | 从 g139 发布候选加入 base=5 全零、base=5 对比+1、base=1 全零后得到；未落盘。 |
| diag147a DAT | 27316 | `9e03675d6e8a26a214816c773949b9eb5cf0c055c73821c91223cb0ac2ea69ce` | 与已知诊断清单一致，只可作为识别/备份对象。 |

为验证布局，只在独立只读进程的内存模块里临时添加了 `Profile(139,98304,True)`，没有修改工作室源码或配置。此时 g139 发布候选和当前测试 DAT 均可逐字节往返；清空用户条目后都得到 `aab6c4f8…399e21`。这证明当前两份本机输入的模板关系，不证明 A3 已实现、全部非法条目已被独立检查或相机已接受。

三份 g137/g139/g139-test DAT 的绑定字段一致：

| 字段 | 当前值 |
|---|---|
| DAT `[48,80)` body 指纹 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| DAT `[80,112)` resident build | `79d8e2a2dfc322f3c2470c0369d736473f0b478dcf7c0e3bebf1feb0e82596f2` |
| DAT `[212,228)` ABI | `ca2d88a054ee3c2ae71b125cbdec285c` |
| g137/g139 发布包 ilaunch3 文件 SHA | `d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90` |

### A3 与固件检查的逐项对照

静态对比确认 g137 与 g139 的 `ui_v2_data.c` 只有 build_number 的 137/139 不同。格式支持不构成在 g137 单独上机的理由；本轮用户已经规定只随 g139 测试包验证。

| 规则 | g139 依据 | 工作室必须满足 |
|---|---|---|
| 条目结构与数量 | `ui_v2_data.h:4-5`；`ui_v2_data.c:31-35` | 每条 24 B，0..32 条，11 个有符号档位。 |
| base、保留字节、序号 | `ui_v2_data.c:61-62` | base=1..8；r[1]、r[9]、r[21] 为 0；序号从 1 按本组在存储顺序中的次数累计，大端。 |
| 名字 | `ui_v2_data.c:73-74` | GRP/GRN/HCB/STD/FCC/FCN/LCH/LVI，加全零时 -、否则 *，加三位十进制序号，共 7 个可见 ASCII，r[9] 为零结尾。不能让用户自定。 |
| 调节量 | `ui_v2_data.c:64-71` | 仅 levels[0:4] 允许非零，各项同时满足三个单元的配置范围；levels[4:11] 全为 0。不是四项都必须非零。 |
| 03 组 | `ui_v2_data.c:42-55`；本机 DAT 配置 | 配置不露出 saturation，其范围为 0..0，条目 saturation 必须 0。 |
| Amount 和控制映射 | `kv2/kv_ui.c:417-448` | legacy 前四项映射到 UvLevels 的 1、2、3、5；电脑 amount 固定 100，不能与 legacy Amt=0 混淆。 |
| 未使用区、配置和 CRC | `ui_v2_data.c:31-57、:76-77` | 未用记录全部为 0；配置表、配方库绑定及 KV 块继续有效。只检查名字和四档不足以接受 DAT。 |
| 最终可应用性 | `adapter.c:478-487` | 通过 uv_validate 后，还须每个条目通过 legacy 转换及当前单元 kv_data_request。主机校验要覆盖相应合法点。 |

选中条目删除后的安全性有静态依据：`eng_core.c:283-291` 对用户条目构造全零记忆记录；`adapter.c:485-489` 在新启动时重建 saved[] 并从 04 初始化；`eng_core.c:675-698` 在基线、完整记录或数据标识不匹配时不预选且不自动写单元。此结论要求关机换卡和冷启动，不覆盖开机热换卡，也不证明机身实际九行已经恢复纯 04。基线不符时的完整写入/读回仍须由 g139 的相关主机用例与同次上机证据支持。

### 已决产品约束

| 项 | 本轮固定要求 |
|---|---|
| 可见术语与主按钮 | 只用“相机配方文件”“我的配方”“备份”“版本”；主按钮为“写入存储卡”。内部 kit 标识无需变成界面词。 |
| A3 上机 | g139 测试包，与 g139 同次上机；不另做 g137 上机。 |
| 第一版删除能力 | 不提供从卡上移除诊断或固件文件。 |
| 写后提示 | 条目或代数改变且写入成功时显示“相机下次开机会回到 04”。 |
| LUT 格式 | 第一版只支持 .cube。 |
| 手调保存 | 配方面板可“存储为我的配方”，并入 A3。 |
| 分享码 | 只含条目，不含效果。 |
| 备份导出 | 提示“包含相机配方文件，仅供自己备份，请勿公开分享”。 |
| README | 按主设计 §6 草案更新，最终文案由用户定。 |
| 后续分期 | B1/B2 继续单列依赖和验收；B2 的效果格式/读法还受设计中的 g141 与拟合器前提约束。 |

## 补充验收用例

以下是待实现的验收规范，本轮全部未执行。新增 A1/A2/A3 用例 77 项，B1/B2 预留 3 项，共 80 项；参数化故障点须逐项保留结果，不能以一个 happy path 代替整行。

已有用例继续有效，但必须先修正以下相互冲突的断言：

- `test_writer_reformatted_card_abandons_journal` 不能以任意不同 UUID 自动放弃原卡日志，按 ID04 改写。
- `test_card_uid_missing_fallback` 不能只在多卡时才处理缺失 UUID，按 ID02 绑定本次挂载。
- `test_restore_snapshot_roundtrip` 只能恢复允许的目标；未知快照保留，不通过恢复绕过白名单。
- `test_writer_rename_four_outcomes`、`test_writer_crash_restart` 只覆盖文件系统仍能正常挂载的模型结果，增加 TX11 的不可读/分配异常分支，不能断言任何断电后必有新旧文件之一。
- `test_codec_golden_test_package` 按完整 SHA 固定输入，旧黄金向量与当前本机测试包分开，不能要求不同字节相等。
- 原写卡设计的 `test_reject_g138` 不能无条件搬到 A1。是否允许写某代由冻结的发布资格决定；A3 上机只针对本轮批准的 g139 测试输入。
- 外来条目保留与删除改号按语义检查；版本不可变时，written_to 只进独立 state/日志。
- 本机夹具缺失允许普通干净 CI 标出未运行，但对应发布验收仍属未通过；不能以 skip 代替交付证据。

### A1：卡身份与计划绑定

| 编号 / 用例名 | 断言 |
|---|---|
| ID01 / `test_same_label_seen_isolation` | 两张合成卡先后复用同一挂载路径，卷标、照片相对路径、长度和 mtime 相同，照片内容不同；导入第二张时必须读取其内容并保存第二个 SHA，不能增加 seen_shots 后直接返回。旧卷标 seen 记录不能直接迁移为可信 UUID 命中。 |
| ID02 / `test_uuid_missing_is_session_bound` | VolumeUUID 缺失、空值、diskutil 失败或超时：只读发现仍可返回；不得按卷标自动选卡或恢复旧日志。若允许显式选卡写入，选择必须绑定唯一的本次挂载，重挂载、重启后立即失效。 |
| ID03 / `test_duplicate_uuid_and_truncated_id_collision` | 同时出现相同 UUID 的两个挂载，或两个完整身份映射到同一个短 card_id：接口返回身份歧义，不得用 next() 取第一张；写入、恢复、备份关联和推出都不能误选。 |
| ID04 / `test_new_uuid_does_not_abandon_other_card_job` | A 卡存在未完成日志，插入 UUID 不同的 B 卡：B 卡零写入，A 的日志保持待处理。UUID 改变不能单独证明 A 被格式化，也不能自动把 A 的日志标为已放弃。 |
| ID05 / `test_explicit_multicard_selection_all_routes` | 同时有空卡、带 DAT 的卡和无 DCIM 的候选卷：不指定目标不得写入或推出；指定有效会话目标后只操作该卷。另一张卡的全部内容、元数据及日志关联不变。 |
| ID06 / `test_plan_invalidated_by_source_or_draft_change` | plan 后分别更改旧 DAT 的 SHA/长度、原本不存在的目标、新目标版本、草稿或引用配方；即使 UUID、st_dev、f_fsid 不变也拒绝旧 plan。不得先写 TMP，再发现计划已过期。 |
| ID07 / `test_swap_at_every_mutation_boundary` | 在备份后、创建 TMP 前、TMP 关闭后、读回后、rename 前、清理 TMP 前、最终读回前和 eject 前替换挂载；新挂载零写入、零删除、零推出，原日志不能记成功。 |
| ID08 / `test_card_id_path_and_command_arguments_rejected` | card_id 为绝对路径、../、编码分隔符、选项或命令片段时拒绝；diskutil 使用参数数组和服务器已登记的挂载点，有超时。卷消失后不得 mkdir 重建挂载目录。 |

### A1：DCIM 与写入权限

| 编号 / 用例名 | 断言 |
|---|---|
| DC01 / `test_no_dcim_guard_covers_install_restore_resume` | 没有 DCIM、DCIM 是普通文件或链接的候选卷可列出，但 install、snapshot restore、resume 都拒绝写入；不由工作室创建或修复 DCIM。大小写正常变体按同一目录识别。 |
| DC02 / `test_dcim_scan_error_is_not_empty_card` | 根目录、DCIM、任意子目录或文件 stat 返回 EACCES/EIO/ENXIO，或扫描不完整：状态是扫描失败，不是 fresh、照片 0 张或可格式化；首次写卡调用前中止。 |
| DC03 / `test_dcim_and_non_target_bytes_preserved` | DCIM 内含嵌套目录、隐藏文件和非照片文件，根目录含 MISC 与未知文件；正常写入后独立核对全部非目标文件的路径、长度、mtime 和 SHA。DCIM 内不适用“所有点文件忽略”。 |
| DC04 / `test_invariant_failure_blocks_success` | 最终 DAT 已读回正确，但写后目录扫描失败，或非目标项出现、消失、长度/mtime 改变：作业不得 verified，不更新当前版本，不显示可以安全拔出；不得自动回滚或修复照片。 |
| DC05 / `test_writer_capability_exact_phase_and_operations` | A1/A3 的能力只准卡根 GXRCE.TMP 的排他创建及本作业 GXRCE.TMP→GXRCE.DAT；禁止 DCIM 下同名文件、GXRFX.*、其他卷、路径穿越、任意 truncate/chmod/utime/remove。B2 权限不得提前开放。 |
| DC06 / `test_audit_dirfd_and_integer_fd_coverage` | 以 dir_fd 的相对路径打开或 rename，以及整数 fd 写入时，审计与专用 I/O 入口均能对应真实卡根和作业；不能把相对路径误记到 cwd，也不能因路径是整数而绕过控制。 |
| DC07 / `test_rename_requires_both_endpoints_in_job` | 分别把 rename 的源或目标替换为另一个卷、DCIM、未知 TMP；即使另一端名在白名单也拒绝。失败前不删除目标，不出现跨卷复制降级。 |
| DC08 / `test_capability_revoked_on_all_exits` | 成功、异常、取消、超时和崩溃清理均撤销作业能力并关闭 fd；另一线程/异步任务即使知道 root、文件名、job_id 也不能借用权限。异常不得遗留全局放行。 |
| DC09 / `test_no_follow_and_exclusive_create_races` | 检查后把卡根、目标或 TMP 替换为链接、目录或外来普通文件；打开后再 fstat，使用不跟随链接及排他创建语义。外来路径内容不变，不先 unlink 以求写入成功。 |
| DC10 / `test_tmp_cleanup_requires_current_ownership` | 旧日志对应 TMP 已被外部替换、长度/SHA 与日志不符，或崩溃发生在创建与记下所有权之间：不凭日志存在就删除。不能证明当前对象归属时保留并报告冲突。 |

### A1：备份、同步、故障和恢复

| 编号 / 用例名 | 断言 |
|---|---|
| TX01 / `test_backup_all_failures_prevent_card_mutation` | 备份读取、blob 写入、快照清单写入、读回或目录提交分别注入 ENOSPC/EDQUOT/EACCES/EIO；卡根无任何写入，既有电脑备份不被截断，也不产生可恢复的假快照。 |
| TX02 / `test_backup_and_journal_are_durable_before_tmp` | 电脑备份数据、清单、日志临时文件及其 rename 所在目录尚未完成规定的持久化时，不得创建卡上 TMP。读回 SHA 正确但 fsync/目录提交失败，也必须中止。 |
| TX03 / `test_crash_between_action_and_journal_commit` | 在每个 I/O 成功但对应日志状态尚未提交的窗口注入进程退出；重启后依据当前文件与旧/新 SHA 重新判断，不能只按最后状态删除或覆盖。归属不明保持冲突。 |
| TX04 / `test_partial_zero_write_eintr_and_midwrite_full` | write 返回短写、0、EINTR，以及写过部分 TMP 后 ENOSPC/EDQUOT：短写被补齐或明确失败，0 不死循环；失败不 rename，旧 DAT 不变，仅保留可归属的残留。 |
| TX05 / `test_write_protection_changes_after_preflight` | 预检可写，创建、写 TMP、rename 或目录同步时改为 EROFS/EACCES：不 chmod、不改卷标、不尝试关闭写保护；保留真实失败阶段，旧目标未被替换时须逐字节不变。 |
| TX06 / `test_open_and_rename_busy_do_not_delete_target` | 文件占用导致打开或 rename 返回 EBUSY/EACCES 时，不能先删除旧 DAT 再重试；旧文件与备份保持。另一个进程只持有读 fd 且系统允许 rename 时，按实际结果核验，不伪造“已锁定”。 |
| TX07 / `test_fullfsync_errors_not_silently_downgraded` | F_FULLFSYNC 返回 EIO 等真实 I/O 故障时中止；仅对已记录的平台不支持错误走设计中的 fsync 降级。fsync 或目录同步再失败时不能当作成功，记录原始 errno 与阶段。 |
| TX08 / `test_nocache_failure_and_read_errors_abort_commit` | 设置 F_NOCACHE 失败、读回短读、读回 EIO 或 close 报错时，不能用普通缓存读替代并宣布核验通过；TMP 阶段不 rename，最终阶段保留失败和恢复入口。 |
| TX09 / `test_mismatch_retry_preserves_original_snapshot` | 最终读回不一致触发至多一次重写；重试不得把坏 DAT 的新快照替换为最初的有效备份。连续失败不更新版本；恢复仍指向最初经核验的旧字节。 |
| TX10 / `test_owned_tmp_mismatch_cleanup_after_recheck` | TMP 读回错一位后，在清理前再换卡或替换 TMP；只在原挂载及所有权仍匹配时清理。新卷或外来 TMP 不得被删除。 |
| TX11 / `test_power_loss_matrix_includes_unreadable_filesystem` | 对日志、TMP 数据、同步、rename、目录提交、最终读回各边界模拟丢失未持久写入。覆盖旧 DAT、新 DAT、仅 TMP、均无，以及文件系统不可读/分配链异常；异常卷只读失败，不自动 fsck、格式化或继续重写，不承诺必然能恢复。 |
| TX12 / `test_real_fat_image_sync_and_eject_contract` | 实现方在获准的可丢弃 FAT/exFAT 镜像上验证真实驱动的 F_FULLFSYNC、目录同步、F_NOCACHE 与 eject 返回语义，并保留错误和降级记录。打桩调用计数不能替代此用例，也不能证明 SD 控制器断电安全。 |
| TX13 / `test_corrupt_or_missing_journal_dependencies` | 日志截断、JSON 非法、状态未知、缺失 blob 或 blob SHA 不符：不恢复、不删除 TMP、不写卡；不能把解析失败当作从未写过或 verified，其他已完成版本保持可读。 |
| TX14 / `test_recovery_conflict_with_external_dat` | 恢复前 DAT 变成既非旧 SHA 也非新 SHA 的第三份内容，或预期不存在的 DAT 出现：停止并重新生成计划；不能用旧确认覆盖第三份文件。 |
| TX15 / `test_eject_busy_failure_and_identity_change` | 写入/导入中 eject 返回 card_busy；推出因占用、超时或换挂载失败时不显示已推出。fullfsync=false 的作业必须等实际目标成功推出，才显示可以拔出；不得强制卸载。 |
| TX16 / `test_restart_discovery_does_not_start_new_write` | 启动、插卡、查看状态与备份操作均不启动新的写卡或回滚。发现未完成日志只提供恢复入口；一次明确授权的恢复也须重新验证身份、目标和确认内容。 |
| TX17 / `test_local_state_failure_after_card_verified` | 卡上读回通过后，电脑 state.json/版本提交失败或进程退出：不能报告整个流程完成，也不能盲目再写卡。重启后按目标 SHA 补记一次结果，不重复建版本或丢失原备份。 |
| TX18 / `test_recovery_and_retry_are_idempotent` | 重复提交相同 plan/resume 请求或并发点击恢复：最多一个实际写入作业，同一结果只记一次；另一个请求返回同一作业或冲突。错误、取消后能力撤销，失败卡不能被自动换成另一张。 |

### A1/A3：DAT 身份与白名单

| 编号 / 用例名 | 断言 |
|---|---|
| WL01 / `test_recognition_and_installability_roles` | 分别登记已批准发布版、候选发布版、测试版、诊断版、未知版；识别成功不等于可写。A1 仅允许批准的发布目标，A3 对冻结的 g139 测试目标作显式例外；诊断和未知目标不能设为当前或经恢复写入。 |
| WL02 / `test_unknown_snapshot_cannot_bypass_whitelist` | 未知/损坏/诊断 DAT 可完整只读备份，但 snapshot restore、imported kit、resume 或仅修改 JSON role 都不能绕过目标白名单。用批准发布版替换它时，仍需对应确认并保留原始快照。 |
| WL03 / `test_fixture_hash_checked_before_golden_assertion` | 黄金向量固定为逻辑条目及完整 SHA，不能把本机路径当身份；本次旧黄金 40bdfe76… 与当前测试包 2378a88c… 分开命名。夹具缺失或不符在交付机验收中是未通过，不能 skip 后算 PASS。 |
| WL04 / `test_template_normalization_preserves_protected_bytes` | 对引擎、重定位、机身指纹、resident/ABI、行池、配置范围表分别翻位并重算 CRC：清空用户条目仍不能命中白名单。只准清空记录和条目数并重算相关 CRC，不得“修正”受保护内容后再核身份。 |
| WL05 / `test_profile_and_all_binding_fields_must_match` | 未登记代数不猜解析布局；登记代数但 profile、文件长度、模板 SHA、DAT 内 body/resident/ABI 任一不符则拒绝。不得把发布包 ilaunch3 文件 SHA d4fa3b46… 当成 DAT 内 da1980e9… 的期望值。 |
| WL06 / `test_recall_reads_complete_bounded_snapshot` | 未知 DAT、诊断文件、TMP 的读回发生短读、读取中改变或超过规定大小/总量时，快照不得标完整，不能继续替换旧文件。29 个固件文件只记录元数据；诊断名字匹配须有边界且不递归读取任意目录。 |

### A1/A2：私有字节与备份导入导出

| 编号 / 用例名 | 断言 |
|---|---|
| PR01 / `test_private_paths_cannot_resolve_inside_repository` | GXR_STUDIO_HOME、备份导出目录直接指向主仓库或 studio 仓库，或经符号链接进入其中：在写任何 blob、DAT、GXRFX、gxrkit 前拒绝；更改路径后的每次操作也重新检查，拒绝配置不能遗留半个输出。 |
| PR02 / `test_private_paths_cannot_alias_card_or_dcim` | 应用数据或导出目录指向存储卡、DCIM、受保护图库，或别名链接在检查后被换向这些目录：备份和导出也不得借此写卡或覆盖照片。该限制独立于通用写卡器的文件白名单。 |
| PR03 / `test_repository_and_distribution_guard_covers_renames` | 用自己生成的模拟文件检查无后缀 blobs、GXRFX.BIN、大小写变体、改名 DAT、改名 ZIP 和嵌套 gxrkit；仓库/分发检查均能拦住受限产物。只检查 GXRCE.DAT 和 .gxrkit 文件名不能算该用例通过。 |
| PR04 / `test_clean_ci_uses_generated_fixtures_only` | 通用写卡器、故障注入和归档异常用例仅用自造字节、目录、图像与 LUT，在无理光文件的干净环境可执行。真实 DAT 黄金对照保持本机外置输入，不提交复制件、切片、hex/base64 或包含字节的失败附件。 |
| PR05 / `test_gxrkit_warning_and_private_export_destination` | 导出前显示完整文案“包含相机配方文件，仅供自己备份，请勿公开分享”；只有校验完成的包才显示导出成功。包只写入通过路径约束的用户导出目录，导出失败不留看似完整的正式包。 |
| PR06 / `test_archive_paths_links_and_duplicate_members_rejected` | zip 成员含 ../、绝对路径、盘符、反斜线逃逸、链接、大小写/规范化后重名或重复清单时拒绝。不得直接 extractall；全部拒绝路径均在应用数据之外零写入，已存在版本和照片不变。 |
| PR07 / `test_archive_limits_and_manifest_reconciliation` | 解压总大小、单项大小、成员数、压缩展开量超过明确上限，或清单缺项、多项、SHA/长度不符、非法 id/name/schema 时拒绝；不能先发布部分版本。导入元数据不能指定任意卡根文件名。 |
| PR08 / `test_imported_metadata_derived_from_verified_bytes` | 归档 JSON 声称的 generation、entries、body、role 与经校验的 DAT 不同：拒绝或按 DAT 重新生成，不能信客户端元数据。合法导入仅生成不可变 imported 版本，不自动设当前、不写卡。 |

### A3：与 g139 一致的条目和手调保存

| 编号 / 用例名 | 断言 |
|---|---|
| EN01 / `test_g139_exact_name_ordinal_and_reserved_bytes` | 8 个组名、组内累计序号、三位十进制、零结尾和 r[1]/r[9]/r[21] 分别逐项变异，并重算 CRC：独立检查必须拒绝全部不合格输入。0、1、32 条可接受，33 条拒绝；base/档位的 bool、浮点和越界整数不得截断编码。 |
| EN02 / `test_all_seven_legacy_reserved_controls_zero` | 原始 levels[4] 到 levels[10] 每项分别置 +1/-1：全部拒绝，即使落在配置表范围内。电脑 amount=100 必须编码为 legacy Amt=0；不能把 100 写进第 11 个字节。 |
| EN03 / `test_range_intersection_and_legal_knob_points` | 对每项取三单元配置范围交集，并做与 kv_data_request 对应的合法点检查；只在一个单元合法的值拒绝。03 的 saturation 只能 0；不以全局 ±5 或悄悄钳位替代目标模板规则。 |
| EN04 / `test_interleaved_groups_and_unused_tail_zero` | 交错存储多个组、全零和非零条目时，编号各组独立累计，* 只由有效调节是否非零决定；未用 24×(32-count) 字节全零。改变未用尾部或计数字段并重算 CRC 仍拒绝。 |
| EN05 / `test_manual_panel_recipe_saved_without_fit_job` | 在配方面板直接调节后存储，生成 source.kind=manual 的我的配方，关掉重开后值不变，无需 fit_job。非法点/非默认受限旋钮在服务端返回明确原因；仅禁用前端按钮不足以通过。 |
| EN06 / `test_selected_entry_deleted_g139_model` | 在 g139 主机模型中覆盖删除当前第一/中间/最后/唯一条目：冷启动重建 saved[]，不保留旧索引或误选改号后的条目；基线不符时入口零单元写入，首次选择走完整写入读回。记录 host 证据，不能写成实机已证。 |
| EN07 / `test_entry_removal_diff_requires_explicit_plan` | 卡上含当前电脑版本没有的合法条目：正常添加或升级不能默默丢弃它们；要移除时 plan 明确列出删除和改号并获对应确认。保留断言按 base/levels 的语义比较，发生合法改号时不错误要求原记录逐字节相同。 |
| EN08 / `test_camera_mapping_updates_only_after_verified_write` | 失败、取消、未写草稿和删除 LUT 不改变最近成功卡版本的相机名映射；写回核验后才更新 camera.name/index。多卡版本不同时，界面按当前选中卡显示，不能用另一张卡最近一次写入的记录表示选中卡状态。 |
| EN09 / `test_reset04_notice_and_identical_reinstall` | 条目或代数改变且最终写入核验通过时显示“相机下次开机会回到 04”；失败、未写、完全相同字节和格式化后重装同一字节不显示该变更提示。 |
| EN10 / `accept_g139_shared_camera_run` | A3 仅随 g139 测试包同一次上机；记录最终发布/测试 DAT 完整 SHA、工作室版本、读回条目和 MyRec 照片/观察。不得拿 g137、主机模型或原始测试包截图代替工作室本次生成结果；未上机时保持未验收。 |

### A2：LUT、导出质量与分享码

| 编号 / 用例名 | 断言 |
|---|---|
| LU01 / `test_cube_only_and_untrusted_names_are_data` | 仅接受可解析的 .cube；.3dl、Hald PNG 不隐式转换。文件名/TITLE 含 ../、换行、引号、HTML 时不能逃逸路径、注入额外 cube 指令或作为 HTML 执行；__MACOSX 元数据跳过。 |
| LU02 / `test_space_inference_unknown_and_manual_override` | 恒等、强 S 曲线、反相、偏色、灰轴不单调和关键词冲突的自造 LUT 均可返回未知/需选择；不能强制把创意显示 LUT 判成 Log。用户始终可从全部支持空间中改选，选择持久化并使旧拟合/预览缓存失效。 |
| LU03 / `test_storable_profile_restricts_entire_search` | 对粗网格、起点、descend、pairs、候选排序和最终保存记录取值：全程仅用目标 v1 三单元交集允许的四项，amount=100，其余默认；不能只在最终返回时清零或钳位。 |
| LU04 / `test_export_cube_axes_and_independent_consumer` | 用自造非对称 RGB 变换及固定角点/内部点，检查导出 33³ 的通道次序、格点顺序、域、插值和舍入。独立读取/字面预期与实际文件一致，不能只让同一个写入器与解析器互相证明。 |
| LU05 / `test_quality_measured_on_serialized_cube` | 质量统计针对最终序列化后重新读取并按实际 .cube 插值执行的表；训练与留出样本按场景/来源分离。记录 seed、样本数、模板/校准/配方/模型 SHA、中位 ΔE00、p95 与覆盖定义，不能沿用拟合器内存表的分数。 |
| LU06 / `test_poor_quality_export_is_marked_approximate` | 用超出 04 可逆范围的自造映射造成质量阈值失败：可以按设计导出，但主面板必须说明是近似并显示真实质量结果，不能显示达标、相机等效或把阈值检查记 PASS。缺少真实 JPEG 样本只能记未测。 |
| LU07 / `test_export_applicability_visible_without_expanding_details` | 未展开详细信息时即可看到输入限定为 GXR A12 50mm、04 标准、默认图像设置、sRGB JPEG、设计规定 ISO，以及“电脑预测/近似”。其他相机、RAW、手机、28mm/MOUNT 或 ISO100 不被承诺等效。 |
| LU08 / `test_identity_clipping_and_unsupported_spatial_effects` | 04 默认在有效覆盖范围满足既定恒等误差；已剪切高光/阴影和碰撞到同一个 8 位 04 码值的场景不得承诺还原。锐度、降噪、颗粒不进入颜色 LUT 的效果承诺，黑白滤镜只标近似。 |
| LU09 / `test_original_recipe_and_jpeg_lut_exports_are_distinct` | 原 LUT 导出与导入文件 SHA 相同；来源已删或手调配方没有原 LUT 时明确不可用。配方 LUT 与 GXR JPEG 用 LUT 各按对应链路测试，不相互替代，也不写照片 sidecar。 |
| LU10 / `test_similarity_scores_not_forced_into_order` | 三档使用相同固定留出集和已声明公式；实际分数不满足预期顺序时如实返回，不调换标签、夹值或伪造数值。基准色差近零时返回不适用；后两档保持将来/需升级标记，28mm/MOUNT 保持未校准。 |
| LU11 / `test_share_wire_format_full_length_and_validation` | 先固定 CRC16 参数、字段编码、名字长度及规范化规则；40 B 名字的最长合法 v1 码可完整往返，不截到 80 字符。逐项检查版本、base、类型、长度、CRC、余位、档位范围及 amount 映射，非法输入不落盘。 |
| LU12 / `test_share_contains_entries_only` | 分享码只有条目所需参数与可选名字；不能包含 LUT、DAT/深层行、效果字段、照片、用户路径或 blob。v2 不能降级时保留“需要 g140”，不得默默丢失旋钮；第一版不新增效果分享路径。 |

### A1/A2/A3：已决文案、版本和隔离

| 编号 / 用例名 | 断言 |
|---|---|
| UI01 / `test_user_decisions_applied_to_all_visible_text` | 页面、菜单、确认框、通知及默认导出文件名不出现“套件”；主按钮为“写入存储卡”。备份警示和 04 提示使用本轮用户指定文本，§8 不再作为待决选项。 |
| UI02 / `test_immutable_revisions_and_deduplicated_writes` | 新版本 JSON 建立后 SHA/mtime 不再变化；写卡历史只追加到独立 state/日志。相同文件集合不建新版本，恢复、命名、第二张卡写入和失败重试均不修改旧版本；最近 20 条之外仍可查全。 |
| UI03 / `test_no_diagnostic_or_firmware_removal_surface` | 第一版页面和 API 均不提供移除诊断/固件文件；伪造请求也不能删除。对这些文件只有分类提示和设计允许的只读快照，不扩宽 audit 删除名单。 |
| UI04 / `test_readme_promise_matches_explicit_operations` | README 与架构/隐私说明按设计 §6 草案及最终用户文案同步；照片导入、扫描和备份继续只读，写入/恢复是明确操作。首次发现卡、打开页面、LUT 拟合和更新预览数据不会写卡。 |
| UI05 / `test_acceptance_environment_cannot_touch_real_profile` | 验收运行前即封住用户实际图库、应用数据、127.0.0.1:49667、真实卡和外网；仅使用隔离临时目录、假卡和获准镜像。夹具缺失不能回退真实用户路径，日志与失败附件不能泄露理光字节。 |

### B1/B2：进入相应分期前启用的门槛

| 编号 / 用例名 | 断言 |
|---|---|
| BF01 / `test_b1_generation_profile_and_migration_frozen` | g140 定稿后冻结 profile、模板、字符集及共享校验向量；v1→v2 每条参数与可用单元一致，迁移差异逐项显示。未具备这些输入时 B1 保持未验收。 |
| BF02 / `test_b2_two_file_interruption_and_binding` | 效果和 DAT 两个文件之间及各自 rename/同步边界均注入故障；两个原始备份先持久化。旧 DAT 配新效果只能拒绝不匹配绑定，恢复不能把未知效果应用到旧条目；不把文件系统损坏简化为四种文件存在状态。 |
| BF03 / `test_b2_cluster_space_and_delete_failure` | 簇大小必须来自经核对的分配单元，不能未经验证就把任意 f_bsize 当簇；文件长度等于一簇拒绝。卡满与 DAT 核验后删除无引用效果失败分别保留明确日志，不删除仍被旧 DAT 引用的文件。 |

## 交复审前的完成条件

实现者先把原有适用用例与本报告新增用例整理成一份可执行清单，保留用例名、所属分期、输入 SHA、故障点、实际结果和证据路径，再实现功能。对应分期的全部用例通过后才能提交该分期复审；缺夹具、跳过、未上机和仅有静态结论不计为通过。后续 B1/B2 的 3 项在启用该分期时成为必过门槛，不要求 A1 提前实现效果写入。

A1 提供通用写卡器故障矩阵、真实 FAT/exFAT 镜像同步语义、独立接口/界面操作和隔离记录；A2 提供最终 cube 文件的独立读取、真实留出指标与可见适用说明；A3 提供与 g139 一致的校验向量和同次上机记录。单元测试、镜像、主机模型、真卡和相机结果分别标注，不互相代替。

本报告的已证范围是源码、包摘要及少量纯只读检查。新功能未实现；真实 FAT/exFAT 驱动、卡的 UUID 行为、SD 控制器断电结果、现有用户机身和 A3 相机行为均未在本轮验证。

## 输入与交付校验

SHA256SUMS 包含本报告及 47 个关键复审输入的摘要，其中 46 个自首次读取以来未变，scene.py 按终检后的只读增量复核固定新摘要；清单不包含任何理光原始字节，也不列它自身的摘要。所有条目相对仓库根。复核命令：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
shasum -a 256 -c research/review_studio_camera_manager/SHA256SUMS
```

主设计、原 46 个关键证据文件和包摘要终检均与初始摘要一致。全工作区冻结检查未通过，具体变化见下节；不能把局部输入一致写成整个工作区未变。此后清单校验失败说明相应输入又有变化，应按新摘要重新判定，不能继续引用本报告作为当前实现或新发布包的验收结论。

## 写入范围与工作区变化记录

终检对开始时保存的 340 个文本/配置文件摘要作比较，检查返回 AssertionError，原因是下列 6 个文件已变化。该全工作区冻结检查没有通过，不以交付清单通过替代它。

- studio/.import_linter_cache/b8d11fd27c2119d3b5d573dfcf0374971ffd59b0.data.json。
- studio/.import_linter_cache/gxr_studio.meta.json。
- studio/src/gxr_studio/finish/meta_text.py。
- studio/src/gxr_studio/lut/scene.py。
- studio/src/gxr_studio/raw/dng.py。
- studio/tests/raw_support.py。

本复审未写入这些路径，也未运行会生成 import-linter 缓存的命令。未对其他工作中的修改作回滚或归因。最终工作室的已跟踪改动除开始时两项以外，增加了上述 4 个源码/测试路径。

只读查看 scene.py 的增量，变化是在 scene_colour 中拒绝非有限的白平衡与矩阵值；它不改变本报告引用的写卡实现、v1 条目布局和 cube 导出设计。该文件的当前摘要已补进清单，其他新增增量未在本轮作产品复审或运行验证。设计复审结论仍绑定列明的输入，不是整个工作室当前工作树的验收。

本复审的写操作只有本目录两份交付物；最终目录没有 DAT、照片、原始表、临时脚本或额外交付文件。


