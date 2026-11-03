建议采用 A＋C：以后逐张写入拍摄标记，旧照片只给出“推断／未知”；B 作为辅助记录。
有拍摄顺序记录的 8 张街景，RAW＋JPG 强制识别对了 7 张；保留不确定结果后，接受的 7 张都符合记录，样本不足以承诺通用准确率。
原厂 JPG、DNG 已有 264 B 的 UserComment；文件格式可用，可靠绑定每次曝光仍需要机身回调和 DAT 配合。
这不是仅换 DAT 即可交付的功能：v3.10 驻留余 92 B，g155 测试版主请求余 1,180 B，完整集成尺寸尚未证明。
主要风险是把后来切换的配方标给早先曝光的照片；普通追加日志还复现了 150 B 内容变成 225 B 文件的问题。本轮没有上卡构建。

## 1. 结论所依据的范围

本轮只读官方映像、已有固件、Studio 源码和 `captures/`。没有访问存储卡、相机、机主正在运行的 Studio 或其图库／应用数据；没有 Git 写操作，没有子代理。新增源文件、数据和报告在本目录，临时介质与编译文件在指定 Scratch 目录。

证据级别分别表示：

| 级别 | 本轮实际做的事 | 不能据此声称的事 |
| --- | --- | --- |
| 静态确认 | 按官方段表换算地址，逐指令核对已有反汇编与映像字节；比较 v3.9 对应窗口。 | 新回调已经接通，或所有拍摄分支都经过该入口。 |
| 模拟器确认 | 原厂注释函数的 C／Python 局部重放；原厂文件调用在原 task 8 上下文操作独立 FAT16 镜像；文件封装的 C／Python 重放。 | 实体 SD、FAT32、真实断电、完整相机拍摄链或 RTOS 最坏等待已经通过。 |
| 电脑实测 | 读取真实 DNG＋机内 JPG，用 Studio 模型评分；在副本上写固定长度注释并检查图像数据。 | 新相机固件已经生成带标记的照片，或模型结果就是拍摄事实。 |
| 未定 | 曝光快照与文件回调的最终入口、完整链接尺寸、日志安全调度及部分生命周期。 | 默认可以用现有 DAT／机身包上线。 |

先读了 `docs/HANDOFF.md` 和 `decisions.tsv` 末尾记录。HANDOFF 的主体停在旧版本，本报告以当前 g154／g155 源码及较新记录为依据。并行中的 v3.10 包装结果没有作为本功能已可用的前提。

绑定的主要输入：

| 输入 | SHA-256 或边界 |
| --- | --- |
| 官方 `ilaunch3` | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。 |
| 已有 v3.9 `ilaunch3` | `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d`。 |
| g155 release DAT | `308c7096b535ab4ce08407311439494b496dea2b4b855e228b8c8a1e2acd046c`，BOOT off。 |
| g155 test DAT | `a1e731f1751135d074af469f4e21f7b5eeedf1da7cd8ac0c4171d06654fa6f45`，BOOT on；不是本轮构建。 |
| 原始照片、模型与调用源码 | 每次运行的 `*-receipt.json` 记录实际读取的文件摘要与运行期变化检查。 |

## 2. A：在照片内写标记

### 2.1 原厂已经预留了字段

[metadata_inventory.json](metadata_inventory.json) 检查了 69 个原始 JPG／DNG，包括 50mm、28mm 和 MOUNT 的照片。它们都有下列字段；本批 UserComment 均为空白。

| 字段 | 现有类型／长度 | 判断 |
| --- | --- | --- |
| ImageDescription，`0x010E` | ASCII，64 B。 | 可装短文本，但容量较小；Studio 已用此字段描述电脑端渲染。 |
| Copyright，`0x8298` | ASCII，70 B。 | 原厂有共享文本缓冲来源；没有闭合 GXR 菜单中可设置该文本的操作路径。 |
| UserComment，`0x9286` | UNDEFINED，264 B，前 8 B 为 `ASCII\0\0\0`。 | 优先候选。保留字段大小和所有偏移，只替换最多 256 B 内容。 |
| Artist | 本批未见。 | 不作为首选。 |
| MakerNote，`0x927C` | 本批常见 22,880 B。 | 没有证据确认某个未知保留区归扩展所有；不建议占用。 |

原厂生成位置并非只在单元里：机身也重建 JPG／DNG 头。地址均为装载地址，不是闪存擦写地址。

| 位置 | 地址／本轮确认的行为 |
| --- | --- |
| 机身 DNG 构造器 | `0x20121C38`；`0x20124D08/4D50` 写 `0x9286`、type 7、count 264。 |
| 机身 JPG 头路径 | `0x201286C0` 写同一标签和长度，随后调用 `0x201273C4`。另有 `0x2012A110` 分支。 |
| 机身注释内容函数 | `0x20126DCC` 从共享模板 `0x201419E9` 复制 264 B；`0x201273C4` 从 `0x20141AFD` 复制 264 B。均不接收配方、曝光或文件编号。 |
| 机身版权文本 | DNG 的 `0x20122894..28D0`、JPG 的 `0x20127F0C..7F74` 读取共享字符串 `0x201428B6`；JPG 还有条件来源 `0x20550B24`。存在缓冲不等于已证明用户菜单可设。 |
| 50mm 单元 | `jlaunch3:0x20162DD8/2E24`、`0x20164760` 等 UserComment 目录项生成点。 |
| 28mm 单元 | `qlaunch3:0x201661D8/6224`、`0x20167B60` 等对应生成点。 |
| MOUNT 单元 | `l08firm3:0x201621D8/2224`、`0x20163B60` 等对应生成点。 |

[static_evidence.json](static_evidence.json) 绑定完整映像摘要、文件偏移、窗口摘要和三个单元的限定范围检索。13 个机身窗口与 v3.9 字节相同；原始窗口放在 [local/](local/)。没有把单元地址按一个全局差值平移。

### 2.2 现有入口为什么不够

H40 位于 `0x2015F9D8` 的主 JPEG 编码前。其后 `0x2015F584` 仍会调用 JPG 头构造路径，原生 UserComment 函数重新从共享模板复制内容。RAW 的 `0x201676F0 → 0x20121C38` 是另一条头构造路径；RAW-only 分支可以不运行主 JPEG H40。

因此，在 H40 改输入元数据里的一个猜测偏移，不能证明最终注释保留；在切配方时改全局模板，也没有把文本绑定到某次曝光。前一帧还在排队时换了配方，后写的头会读取新模板。

[native_metadata_c.json](native_metadata_c.json) 与 [native_metadata_python.json](native_metadata_python.json) 各运行 6 个原厂函数用例：原始模板、模板为 01、已假定曝光为 01 后模板改成 02。两个函数都精确复制调用当时的模板，相邻字节不变。这是测试指定顺序下的共享来源反例，不是一次完整连拍或真实任务交错。

现有 H40 的失败合同还不适合可选标记：对未备份区域写入后设置 `IMG_TOUCHED`，失败可跳过编码并锁存。注释失败应降为“未知”，不能因此丢掉照片。改变现有像素回调合同需要单独设计和验收。

### 2.3 推荐实现形状与尺寸

建议把格式化、配方身份解析和状态核对放在 DAT，把必要的原生时机桥放在机身。第一版不改 A12 单元映像。

1. 在拍摄参数真正冻结的入口保存当时已核对的配方状态，绑定拍摄序号、K 槽代次、单元和相关 epoch。不能从当前光标或 S 尾部的“上次意愿”取值。
2. 在 JPG／DNG 头完成、提交存储任务之前，向 DAT 传 K、文件类型及已经验证的 UserComment 地址／264 B 长度。只写该字段内容，不改 IFD、偏移、文件长度或像素。
3. 任一身份、生命周期或指针检查不通过就跳过标记；半写记录由 CRC 检出。每个 K 槽复用前撤销旧记录。没有成功快照时禁止沿用上一张的状态。

这是设计，尚未找到并验收覆盖全部曝光生产者的最终冻结入口。已有 H09 不能直接扩大为连拍后续帧、自定时及 C07–C11、C14/C15 全覆盖。v3.9 在第一次 ADJ 前不加载 DAT；v3.10 的启动加载入口可作未来基础，但“启动加载”与“自动套用成功”需要分别核对。

不占固定驻留窗口的备选是 DAT 在 RAM 中重定向原厂入口，或安装一个独立堆内小桥。这在机制上未被排除，但属于新的原生调用机制。`resident/resident.c:rv_retire()` 会撤销 block、lease 和 code 归属并停用会话；源码明确已发布块不由它主动 free。RAM 重定向若未同步撤销，会绕过这个退役边界，也不能继续相信归属失效后的代码和状态。入口原值、缓存同步、重入、卸钩和独立堆块寿命均未验收。因此不把“固定窗口可新增 0 B”写成已可用的 DAT-only 方案；优先研究受现有退役机制保护的正式机身桥。

| 部分 | 放置位置／尺寸 | 证据级别 |
| --- | --- | --- |
| 固定长度编码器 | DAT。独立 M32R 对象 `.text=592 B`、只读常量 88 B、BSS=0，总计 680 B。最大单函数栈帧 24 B，不是完整 task／IRQ 栈峰值。 | 独立目标对象尺寸已测；未链接进 DAT。 |
| 每帧快照 | DAT BSS。若先按 48 B × 原厂 18 个 K 槽预留，则为 864 B。 | 设计预算，不是实际布局验收。 |
| 曝光／头完成桥、失效处理 | 机身桥与 DAT adapter。新增代码字节数未定。 | 未实现、未链接。不能把现有 92 B 视为已经足够。 |
| 电脑读取 | Studio 导入与 sidecar。 | 本轮只提供研究解码器；未改 Studio。 |

尺寸依据见 [encoder_size.json](encoder_size.json)、[tag_encoder.c](tag_encoder.c)。仅上述 680＋864 B 就比 g155 test 的 1,180 B 主请求余量多 364 B，尚未计算桥接和校验；压缩快照或回收其他空间后仍须重新严格链接。g155 release 主请求余 4,068 B，也不能据此推定集成通过。没有构建 DAT 或机身安装映像。

格式原型 [metadata.py](metadata.py) 使用 `GXRCP1`、目录身份、配方引用、拍摄时名称、单元、10 个 int16 UI 值、结果校验码、有效性和记录 CRC。名称用 UTF-8 字节的十六进制，最长 39 B。10 值遵循 DAT 的 `UvLevels.v[10]` 顺序，包含 Amount；不能混同数学核心的 `dose[10]`。

目录身份应预先对不含本标记字段的规范配方目录计算，算法／控制表版本也要绑定。它不是向 DAT 内嵌“该 DAT 文件自身的完整 SHA-256”。现有 g155 的两个头 CRC 可作原 DAT 查找键，Studio 唯一匹配后另存完整 DAT SHA-256。原型没有实现目录身份生产与原生时机桥，这些开销不在 680 B 内。

[encoder_host_check.json](encoder_host_check.json) 记录 104 个 C／Python 编码对照，含有符号极值、39 B UTF-8 名称及超长拒绝。[metadata_copy_checks.json](metadata_copy_checks.json) 记录 JPG、DNG 各一个副本检查：只改 264 B、文件大小不变、JPG 解码像素相同、DNG RAW strips 相同；264 个单字节破坏均被解码器拒绝。均不是相机输出验收。

### 2.4 模式、失败与最小机主验证

| 情况 | 应有行为／目前边界 |
| --- | --- |
| RAW＋JPG | 两份文件取同一次曝光快照；不是在两个保存时刻分别读“当前配方”。有冲突时 Studio 保留两份记录并显示未知。 |
| 连拍 | 每帧独立快照；迟到的写入、下一次切换和 K 槽循环复用不能改变早先帧的身份。当前未运行完整连拍。 |
| 16:9／其他比例 | 不依赖固定 EXIF 文件偏移，定位已构造的字段。裁切不能改变配方记录语义。本轮没有完整相机 16:9 标记输出。 |
| RAW-only | 必须走 DNG 头回调，不能依赖 H40。 |
| 首次 ADJ 前、MY、原生覆盖 | 没有可信当前状态就未知。不能把上次高亮当成本张已应用。MY 未核对时不替它写“纯 04”。 |
| 原有非空注释 | 保留原内容；只接受空白或已支持的自有版本，不覆盖用户文本。 |
| 标记无效 | 固定字段内容 CRC 失败只影响识别，正常编码和保存继续。指针／长度不可信时零写。这个失败合同还须新桥实现与验证。 |

DAT 异常时先关机并移除／替换研究 DAT；新增机身桥自身若有故障，仍须另验独立官方恢复路径。本轮未验证新桥、物理更新或恢复，不能承诺任意机身故障都可由同一动作恢复。

未来原型的最小现场检查如下，共 7 张，三单元分别覆盖一部分路径；本轮未执行，也不将这组最小检查当作完整组合验收。

1. MOUNT 正常冷启动、不进 ADJ 拍 1 张 RAW＋JPG；再选一个 Look 并改一个微调值拍 1 张。第一张不得继承上次配方，第二张应记录 Look 引用及完整 10 值。
2. 50mm 选择 07 拍 1 张 16:9 JPG-only，再选 08 拍 1 张 16:9 RAW＋JPG，核对引用和两份文件的一致性。
3. 28mm 选择用户配方拍 1 张 RAW-only，再连拍 2 张 RAW＋JPG；导入后核对全部记录与实际选择。MY 冷启动、更长连拍及各单元其余组合仍需另列覆盖，不能由这 7 张代替。

## 3. B：卡上的配方变更日志

### 3.1 文件接口存在，安全追加与安全时机没有随之成立

当前 g155 的 `candidate/engine_services/services.c` 明确对 `RV_STORAGE` 返回不支持，没有产品日志客户端。已有文件入口是原厂 `r4..r7` ABI：open `0x200A40B4`、create `0x200A41AC`、buffered read `0x200A449C`、buffered write `0x200A45E8`、close `0x200A437C`、seek `0x200A4F40`。

本轮 [native_log.py](native_log.py) 只在原厂 task 8 的已有检查点上下文操作独立合成 FAT16 镜像，没有修改模拟器。

| 操作 | 本轮结果 |
| --- | --- |
| 新建研究日志，写第一行 | write=75、close=0；独立读镜像得到精确 75 B。 |
| reopen → seek(75,0) → write 第二行 → close | seek=75、write=75、close=0；目录长度为 **225 B**，预期是 150 B，最后 75 B 为原缓冲内容。 |
| 改用 direct write `0x200A48C8` 追加 | seek=75、write=75、close=0；长度为 150 B，但第二行变成旧缓冲内容。内容一致性检查未通过。 |
| reopen 后从 0 顺序重写两行 | write=150、close=0；独立镜像解析及原厂接口重开读回均为精确 150 B。 |
| 新实例重挂载试验 | SD init 返回 0；mount 在 20,000,000 步内未回到 task 8 调用哨兵。此项 INCOMPLETE，不作为重启／断电通过。 |

首个失败见 [native_log.json](native_log.json)、[native_log.log](native_log.log)，完整失败介质压缩保存在 [local/first-append-failure.img.gz](local/first-append-failure.img.gz)。从 0 重写见 [native_log_rewrite.json](native_log_rewrite.json)。重挂载未完成记录在 `initial-native-log-remount.*`，与普通重开读回分开。

direct 路径见 [native_log_direct.json](native_log_direct.json)，首次失败的完整介质也保存在 `local/direct-append-failure.img.gz`。其高层封装在 C／Python 的“底层完整写入成功”替身下可以得到两行，实际 GNU 文件层却没有得到第二行。因此不能把这个局部 Python 结果称为底层内容问题已独立复现，`0x200AE360`、原生缓存与关闭之间的完整关系仍未定。

根因在两层位置的组合：seek 已令底层位置为 75；buffered write 把高层位置推进到 150；close 又向底层提交 150 B 的缓冲尾部。因此文件末端到 225。`0x200A43E0..43F4` 是关键提交处。[log_wrapper_c.json](log_wrapper_c.json) 和 [log_wrapper_python.json](log_wrapper_python.json) 都复核了相同的 75＋150 请求，也复核了从 0 重写以及 dirty close 失败后的句柄计数残留。

该 Python 复核执行原厂高层封装，锁和底层媒体提交是声明的替身；完整 FAT16 现象由 GNU C 模拟器观察。四个封装用例的 C 运行计数确认实际执行了 C core 指令。完整 Python RTOS／SD 介质复核未完成；设置 `GXR_HARNESS_BACKEND=python` 不会令 GNU 模拟器更换 CPU。direct 底层内容问题与重挂载等待问题仍未完成独立 Python 复核。

两种追加路径都失败后，没有继续尝试第三个 write 变体。被检验的前提是“已有文件的 seek、缓存和正返回 write 可以直接组成可靠追加”。`actor_census` 记录 open／定位／write 返回时的高层位置、底层位置、缓存字节、状态字和介质内容，供定位哪个环节保留了旧数据；不通过手改原厂内部位置、dirty 或 mode 字段补偿。

### 3.2 日志应怎样设计

不能把“选定配方”“ADJ 关闭”或 UI state=5 直接当成存储空闲。照片生产者 task 28 与文件任务 task 8 分开，已入队和尚在编码的文件都可能存在。已有研究定位 task 8／message buffer 2／`0x1F03` 照片消息，但没有现成 DAT 自定义完整事务 opcode。未经核对塞入未知 opcode 还会改变任务状态。

如继续研究 B，建议：

1. DAT 只记录成功应用／实际恢复后的完整状态，预览光标不直接产生日志。事件先留在有界 RAM 队列，交给已受理的原厂存储作业执行。
2. 先证明对原厂生产者、在途 RAW＋JPG、格式化、USB、换卡和退出的调度合同；不在 UI handler 外套原厂内部锁。
3. 避免这次已失败的任意位置 buffered 追加。下一原型可研究电脑预建的双定长文件、从偏移 0 全量顺写、CRC／序号／完整快照；本轮的 150 B 重写只关闭具体字节问题，不关闭并发和断电安全。
4. 出错后停止本次启动的自有文件 I/O；不把 open=-1 当成“文件不存在”后 create，不重复关闭不确定 fd，不无限重试。

代码应以 DAT 的事件队列、序列化和恢复逻辑为主；原厂任务受理／生命周期桥还需机身支持，不能报“驻留新增 0 B”。完整代码大小未定。可先按 DAT 代码 2–4 KiB、512 B 流缓冲加有界队列做工程预留，但这只是估算，未链接；仅代码预留便超过当前 test 版 1,180 B 主请求余量。

### 3.3 时间与文件号能得到什么

照片 EXIF 时间来自每帧元数据：机身 `0x20128254..8268` 取元数据 `+36` 的日期结构，经 `0x20138DB8` 转为 20 B 文本。相机年份为 2000 本身不妨碍同一时钟匹配；同秒切换、倒拨时钟和时区解释则不能靠最近时间猜。

命名代码 `0x201166E8` 读取／更新 `0x204F952C`，并结合 `0x204FFB60` 等字段生成名字。它们是队列／DCF 序号候选，不是本轮已经确认的“下一次曝光文件号”getter。该语义以及可从 DAT 安全调用的当前日历时钟入口都未闭合。原生 tick getter 不是日历时钟。

日志至少需要版本、卡／媒体 epoch、启动 epoch、事件序号、相机时间、完整 DCF 目录与编号边界、事件类型、配方引用、目录身份、名称、10 值、完整状态和 CRC。时间只作交叉检查。RAW＋JPG 应按同一捕获归组，不能把两个文件计成两次拍摄。

### 3.4 所列失败情况的处理

| 情况 | 能可靠说什么／所需处理 |
| --- | --- |
| v3.9 关机后、首次 ADJ 前 | DAT 没加载，无法产生日志。上一条记录不能继续覆盖这段照片。正常开机通常为纯 04，也不能据此替 MY 或未知启动路径补标签。 |
| v3.10 启动入口 | 可研究由 H51 先建立新会话记录；当前服务仍无日志实现，也未证明存储事务资格。缺少该记录的会话维持未知。 |
| MY／原生设置覆盖 | 使原配方区间失效；未完整核对的深层状态记未知，不沿用上次自定义配方。 |
| 卡满、短写、close 错误 | 本条不算提交；停止本次启动的自有 I/O，标记队列有缺口。dirty close 的计数残留可影响后续原厂文件打开，需关机重启。 |
| 拔卡／媒体变化 | 撤销旧媒体和队列身份；新卡不得沿用旧日志区间。真实热拔卡未测。 |
| 电池耗尽 | 丢失 RAM 队列或尾记录均可能发生，未闭合的最后区间只能未知。没有证明 FAT 元数据不会同时受影响。 |
| 日志被删除 | 相机继续正常拍摄是设计目标；Studio 显示未知，不从别的会话“补回”。重新预建／恢复日志由电脑处理。 |
| 日志损坏／缺序号 | CRC、序列、媒体和会话核对失败的区间不参与匹配。保存原始坏文件供核对。 |
| 时钟倒退／同秒事件／编号重置 | 没有可靠文件边界和 epoch 就拒绝唯一归属。相机年份不正确不能用电脑导入时间代替。 |

[log_match.py](log_match.py) 的 12 个电脑模型用例覆盖这些匹配边界。它只分配同会话、连续序号、两端已关闭的文件号区间；开放尾部、缺失启动记录和损坏数据均未知。模型还保留了简单 forward-fill 在未记录重启后把纯 04 错标成旧 02 的反例。模型要求的 epoch／文件边界目前并不存在于普通照片和 DAT-only 变更日志中，不能称产品已经解决。

未来原型的最小机主验证，本轮未执行：

1. 正常冷启动后不进 ADJ 拍 1 张；有已保存 MY 时再以 MY 冷启动拍 1 张。导入不能把这两张续接到上次会话。
2. 在相机时钟同一分钟内选 07、08 各拍 1 张 RAW＋JPG；必须按文件边界区分，不由时间距离决定。
3. 正常关机后在电脑仅移走研究日志，再开机拍 1 张。照片应正常保存，导入为未知。卡满、热拔卡与真实掉电仍是单独的存储验收，不能由以上几张覆盖。

日志失效的预期恢复是关机后在电脑检查／恢复研究文件，必要时移除研究 DAT。若已有 FAT 损坏，移除 DAT 不会修复已存字节；不把格式化照片卷或反复刷机当作恢复日志的方法。

## 4. C：电脑端识别旧照片

### 4.1 数据与标签来源

逐张路径、配方与来源见 [labels.csv](labels.csv)，文件摘要和排名见 [inference_results.json](inference_results.json)。没有用本次预测结果建立本次真值。

| 集合 | 照片 → 配方 | 标签证据 |
| --- | --- | --- |
| MOUNT 街景，g137 | `R8051530..1537 → 01,02,03,04,05,06,07,08`。 | `decisions.tsv:769` 的同场景 1→8 拍摄顺序。是本轮最独立的顺序标签；仍不是机内标记或盲测。 |
| MOUNT 色卡，g150 | `1693..1701 → 04,01,02,03,05,06,07,08,GRN*001`。 | `research/mount_g150_field/REPORT.md` §2 及 `decisions.tsv:863,867`；旧报告在模型分析后与用户说明对上，列为条件性标签。 |
| MOUNT 实景，g150 | `1691,1692 → GRN*001`；`1702..1706 → 01`。 | 同报告 §2、§7 的旧模型归属，缺少独立逐张拍摄记录；不进入独立准确率。 |
| 50mm 历史六页色卡 | `1270..1275 → 04`；`1277..1282 → 01`；`1284..1289 → 02`；`1291..1296 → 03`；`1298..1303 → 05`；`1305..1310 → 06`。 | 捕获目录 README 的顺序假设和 `analyze_session.py:C_STARTS`。旧最终标签曾由模型按六页确认，不能当独立盲测。 |

错误拍摄的 A 组、白页、没有槽位记录的 daily 组均未补猜真值。`looks-g152-20261102` 的 4 对照片有成功拍摄的批次记录，但没有可靠逐张 Look 名称，未计入准确率。没有 28mm 配方识别验收集。

### 4.2 方法和实际结果

[infer.py](infer.py) 用 `studio/.venv/bin/python -I -B` 只读调用 Studio 的 `Dng`、DAT 解析、实际 DAT 的旋钮表、整数 `knobs.apply` 和 `Model.predict`。不启动服务，不导入机主数据目录，不重拟曝光、白平衡、标定或阈值。

RAW／JPG 拍摄时间、ISO 以及共有有效拍摄参数先核对。每帧按自己的 black／white／AsShotNeutral，取 36×26 网格的 12×12 小区域；排除高纹理、全黑白和 RAW 饱和区域。对候选配方预测量化 RGB，比较 ΔE00 中位数。该实验检验颜色链，不是完整去马赛克／降噪／锐化仿真。

Studio 的实拍标定只有 50mm ISO200／1600；MOUNT 使用跨单元模型，街景的 ISO800 实际选用 ISO1600 模型。这里的结果不能扩大为 MOUNT 或 28mm 已完成标定。标定训练样本与历史色卡的重叠本轮未另行审计，历史色卡集合只作回归检查。

候选包括当时已知 DAT 的 8 个默认配方，g150 另有 3 个真实用户条目。[candidate_equality.json](candidate_equality.json) 证明三个用户条目与此前独立 C 路径导出的完整 552 B 逐字节相同。没有穷举任意 10 值组合。

| 集合 | 对数／错误数 | 正确配方在最优同输出组内 | 唯一正确引用 | 满足保守规则／其中正确 |
| --- | --- | --- | --- | --- |
| 街景 g137，MOUNT ISO800 | 8／0 | 7/8，87.5% | 7/8 | 7／7。 |
| 色卡 g150，MOUNT ISO200 | 9／0 | 9/9 | 8/9 | 5／5。 |
| 实景 g150，MOUNT ISO200 | 7／0 | 7/7 | 7/7 | 7／7。 |
| 历史色卡，50mm ISO200 | 36／0 | 36/36 | 36/36 | 29／29。 |

60 对都完成评分，没有解码／配对错误。59/60 的已记录配方位于最优同输出组，58/60 得到唯一正确引用；52 张标签已有模型参与历史归属，不能将该结果表述为 98.3% 的独立识别准确率。8 张顺序标签只有一个场景，7/8 的 Wilson 95% 区间约为 52.9%–97.8%。

保守规则预先固定为：有效区域至少 48 个、最佳中位色差 ≤3、与下一非同输出候选差至少 0.75、空间分块 bootstrap 胜出比例 ≥0.95，且没有相同行别名。该比例是稳定性诊断，不是“配方正确概率”。接受了 48/60，样本内均符合记录，但该选择结果没有独立校准为产品置信度。

有顺序记录街景的完整混淆表如下，行是真值，列是强制单选结果。其余集合和全部数据见 [confusion.csv](confusion.csv)。

| 真值／预测 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 02 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 03 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 04 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| 05 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| 06 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| 07 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| 08 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |

![顺序标签样本的混淆图](confusion_street.svg)

图由 [render_results.py](render_results.py) 从正式结果生成；[HTML 版本](confusion_street.html) 使用相同计数。

`R8051537` 实际顺序为 08，模型选 07：最佳中位 ΔE00≈2.280，间隔仅 0.142，bootstrap≈0.925，因此保留为待确认。`R8051697` 的 05 与 `FCC-001` 完整输出相同，像素无法区分菜单入口，应展示候选组，不能宣称识别到了用户命名。

候选库必须覆盖当时版本。[inference_limits.json](inference_limits.json) 在同一 g150 色卡上用旧 g137 库只得 3/9，且 0 张满足保守规则；加入已有 g153 十个默认 Looks 后仍为 9/9。本实验没有有真值的逐个 Look 实拍，也没有证明任意旋钮组合、任意历史 DAT 或库外配方可识别。推断结果的微调值不能自动补成默认值。

### 4.3 只有 JPG

[jpg_only.py](jpg_only.py) 做了固定的 16-bin Lab 直方图最近邻基线，街景与色卡互作参考，不使用 RAW、不调参。两个方向各 8 张，均只有 1/8 正确，见 [jpg_only_results.json](jpg_only_results.json)、[jpg_only_confusion.csv](jpg_only_confusion.csv)。它说明这个简单基线不能跨场景工作，不是所有 JPG 分类算法的准确率上限。

没有 RAW，场景颜色、曝光、白平衡和配方共同决定输出。即使能辨认黑白，也不能证明具体自定义配方名称或 10 个值。原生元数据可辅助排除已知原厂模式；对本项目统一 Standard 的自定义配方，不能恢复唯一身份。没有记录的单张 JPG 默认未知，可提供人工候选，不能回写为“相机记录”。

### 4.4 放置、失败和最小机主验证

识别代码全部在电脑侧，相机新增代码／驻留占用均为 0 B。当前交付是研究脚本和数据，不是 Studio 已上线的识别功能。没有 RAW、配对冲突、候选库不全、过少有效区域、残差过大或候选重叠时，应返回未知／待确认，不改原片，不静默套用任何电脑配方。恢复动作只是补充正确候选库、重新计算或人工记录。

最小新数据检查可在现有相机上拍摄，无需新固件；本轮未要求机主执行。

1. 在一个真实场景、固定曝光和白平衡下，对 07、08 和一个非默认用户配方各拍 1 张 RAW＋JPG，机主另记顺序，不把答案交给识别器。
2. 换一个光源／场景，重复这 3 张后揭晓顺序；报告命中数、待确认数和错误接受数。在照片副本中去掉 RAW 再导入，应保留“未知／推断”，不升级为相机记录。

## 5. Studio 应保存什么

新增独立的 `capture_recipe` 记录。它不能写进现有 `EditState.recipe` 或 `lut`；后两者表示电脑上后来应用的效果。当前图库 schema 没有拍摄配方字段，本轮没有修改它。

| 数据 | 保存内容 |
| --- | --- |
| 来源与状态 | `camera_tag / card_journal / raw_jpg_fit / operator / unknown`；`recorded / inferred / ambiguous / unknown`，以及拒绝原因。按时间区间归属的日志保留为推断。 |
| 拍摄身份 | 原始 DNG／JPG SHA-256、已核对的配对、相机原始时间、DCF 路径／编号、存在时的会话／媒体 epoch。不能虚构物理单元 UID。 |
| 拍摄配方 | kind、原始引用字节，内置 1..8／Look `0x40+i`／用户 `0x80+i`，索引从 0 起；拍摄时名称、单元类型、10 值和控制表版本。未知值为 null。 |
| 目录与有效输出 | 标记中的目录身份、g155 头 CRC 对、Studio 唯一解析得到的 DAT SHA-256、可重建的有效 552 B 摘要。名称相同不等于配方相同。 |
| 原始证据 | 264 B 标签原样、日志文件摘要／行位置／序号／CRC，或推断脚本版本、模型／候选库摘要、各候选分数和阈值。 |
| 可信度 | 明确的类别、候选组、残差、间隔和稳定性；不把 bootstrap 数值显示为已校准的正确概率。 |
| 电脑编辑 | 继续单独存 `recipe`、`adjust`、`curve` 和 LUT 身份／强度；更换电脑 LUT 不改拍摄配方。 |

优先读取原片内有效记录；两份载体冲突、版本不支持或 CRC 错误时保留原证据并显示未知。没有记录才运行受限推断。旧日志不能跨启动自动续接。用户手动校正另存为注释，不抹去原始来源。

导出还需单独处理：`export.py` 的 ImageDescription 已描述电脑渲染，完整 EXIF 路径会保留 UserComment，但精简 EXIF 回退只保留日期／ISO／镜头等字段，会丢掉它。后续实现必须让拍摄记录在 sidecar／导出元数据中保留，并继续把电脑效果写在自己的字段。这个导出保留能力本轮没有验收。

## 6. 复跑

先重复本轮的挂载／UUID 核对，建立临时目录；不要把下面路径替换为存储卡或机主 Studio 数据目录。

```sh
df -h /Volumes/Workspace
diskutil info /Volumes/Workspace
mkdir -p /Volumes/Workspace/Scratch/tmp/projectricoh/recipe-tag-r1
# 可用 /usr/bin/python3 -I -B research/recipe_tag_r1/run_final.py 顺序运行本轮正式证据组。
nice -n 10 studio/.venv/bin/python -I -B research/recipe_tag_r1/infer.py
nice -n 10 studio/.venv/bin/python -I -B research/recipe_tag_r1/jpg_only.py
nice -n 10 studio/.venv/bin/python -I -B research/recipe_tag_r1/inference_limits.py
nice -n 10 studio/.venv/bin/python -I -B research/recipe_tag_r1/metadata.py
GXR_HARNESS_BACKEND=c /usr/bin/python3 -I -B research/recipe_tag_r1/native_metadata.py
GXR_HARNESS_BACKEND=python /usr/bin/python3 -I -B research/recipe_tag_r1/native_metadata.py
GXR_HARNESS_BACKEND=c /usr/bin/python3 -I -B research/recipe_tag_r1/log_wrapper.py
GXR_HARNESS_BACKEND=python /usr/bin/python3 -I -B research/recipe_tag_r1/log_wrapper.py
GXR_HARNESS_BACKEND=c GXR_EMULATOR_BATCH=1 nice -n 10 /usr/bin/python3 -I -B research/recipe_tag_r1/native_log.py --strategy rewrite
/usr/bin/python3 -I -B research/recipe_tag_r1/log_match.py
/usr/bin/python3 -I -B research/recipe_tag_r1/static_evidence.py
/usr/bin/python3 -I -B research/recipe_tag_r1/render_results.py
```

`native_log.py --strategy append` 用于重现长度异常，`--strategy direct` 用于重现内容异常；两者的诊断状态都不是可靠追加通过。`--restart` 是另列的未完成试验，默认不运行。这里不改模拟器的默认输出或缓存路径。

编码器只测独立对象，不构建 DAT／机身包。编译、执行均顺序运行：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/recipe-tag-r1 research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc -m32r -Os -ffreestanding -fno-builtin -fPIC -fstack-usage -c research/recipe_tag_r1/tag_encoder.c -o /Volumes/Workspace/Scratch/tmp/projectricoh/recipe-tag-r1/tag_encoder.o
/usr/bin/python3 -I -B research/recipe_tag_r1/measure_encoder.py
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/recipe-tag-r1 /usr/bin/clang -Os -fPIC -dynamiclib research/recipe_tag_r1/tag_encoder.c -o /Volumes/Workspace/Scratch/tmp/projectricoh/recipe-tag-r1/libtag_encoder.dylib
studio/.venv/bin/python -I -B research/recipe_tag_r1/check_encoder.py
/usr/bin/python3 -I -B research/recipe_tag_r1/verify.py --cleanup
```

## 7. 审计与未运行边界

最终输入摘要、交付核对与清理结果见 [audit.json](audit.json)、[cleanup.json](cleanup.json) 和 `SHA256SUMS`。正式结果与早期工具错误分开；早期路径错误、用户条目参数修正及 StopInfo 输出适配错误保存在 `initial/`，没有算成有效相机测试。

最初快照包含 18,939 个源码／库文件。其后有 7 个 Studio API／LUT 文件发生变化，路径列在 `audit.json:source_tree_drift`；本轮没有写入这些文件，也未核查变化归属。它们与本轮正式测试读取的输入集合无交集。不能把“实际测试输入不变”扩大成“整个并行工作区不变”。

执行约束有一项偏差：初始并行只读检索及一次进程盘点管道超过了严格的 3 进程上限。后续测试使用单个 Python 进程、线程上限 1，编译器单独执行；未启动子代理或操作其他重任务。该偏差保留，不宣称全程进程上限合规。

未运行的边界包括：新 DAT／机身集成与严格链接、完整曝光／JPEG／DNG 链、MY 全路径、首拍全部消费者、完整连拍及自定时、物理键／LCD／回放、三单元现场输出、FAT32、热拔卡、真实电池耗尽、原生等待上界、新桥官方恢复及机主 Studio UI／导出验收。direct 追加的完整底层及日志重挂载试验也未完成独立 Python 复核。以上均不由主机模型或副本检查代替。
