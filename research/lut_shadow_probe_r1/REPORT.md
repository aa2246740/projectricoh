有缺陷。离线候选已生成；以下主机验收尚未关闭：cold-native-latest, cold-reference-latest。

# 3D LUT 影子测速探针 r1

2026-11-05。只在主机离线工作，没有操作相机、SD 卡或网络，没有安装依赖、commit 或 push。交付范围为本研究目录、firmware/engine_lutprobe_r1/ 与 firmware/package_v310_lutprobe/。其他任务原有改动没有纳入本实现。

## 设计依据与产物身份

合同为 [v311 可行性研究 B1、B2 与 D3](../v311_feasibility_r1/REPORT.md)，并沿用 [H40 主编码入口研究](../body_lut_r2/REPORT.md)、[tick 静态依据](../cpu_speed_r1/REPORT.md)和[内核成本研究](../look_ceiling_r1/REPORT.md)。本任务不把这些报告的条件估算变成实机秒数。

DAT 当前使用独立 generation 171。续验发现两处真实缺陷，按约定换代重建：169 的 UI_TEXT 参数顺序错误，快与参考后端在同一步、同一指令复现；170 已修正为 source、source bytes、glyphs、language，171 保留该修正，生成器与模型也使用同一 ABI。170 把 OK 改成 DISP，实际进入 H06，未执行 H07 中的确认动作；171 保留原生 OK，走 resident 已有的 H07 关闭路径。旧候选、完整链接输入和首错分别保存在 local/resume-20261105/g169-invalid/ 与 g170-invalid/。旧 SHA 的通过项不计入 171 验收。

初始化使用等价字节表 CRC，仍校验全部 29,478 B 节点。250 tick 预算、完整四面体内核、Q8.8 精度、每级行数和软退出条件均未放宽。g171 的快后端冷启动能完成装载、归一化字节比较、原生字体发布及 OK 经 H07 返回待机，但初始化在模拟时基下记录 1,550 tick 并锁住会话，后续校时启动断言失败。快、参考在相同的 232M 步与按键状态下失败，H07 观察的 JSON 字段也逐项相同，记录见 local/resume-20261105/cold-failures-g171.json。两项冷启动仍为 OPEN。

已搜索现有代数定义，171 没有先前使用记录。resident 仍是当前 v3.10 的原字节。它的两个 envelope 验证门只要求 generation 非零，并不把 157 或 158 写死。此探针不链接配方 gate、eng_data_accept 或 uv_validate，bootstrap 自己同时要求头中的 generation 和引擎版本恰好为 171。无需修改 resident 或旧配方 gate。

实际 DAT、ELF、适配器、固件地址、冻结输入和原始回执只在被忽略的 local/。最终 SHA、容量及验收汇总由 seal.py 从真实包生成，详见本页末尾的封存区。header 中的 body trust 标识沿用当前 resident 的原厂源身份；完整已修改机身另以实际 SHA 绑定，不能混为同一摘要。

## 内核与主图边界

选用三通道 Q8.8，完整 17³ 共 4,913 个节点、29,478 B；另有 1,024 B 坐标表。identity 节点间隔为 4,080 个 Q8.8 单位。Q8.8 保留此前完整内核的精度和 halfword 访问成本，u8 会改变节点精度及访存，不能把它的测速当作同一种内核。

每对输入按原始四字节读取，两个 Y 各自做一次完整四面体插值，共享两个色度输入。每个像素稳定排序三个分数，读四个顶点的三个通道，执行三通道插值；没有 identity、相同 Y、灰色、分离表或跳像素分支。结果写进 DAT 自有 8,576 B 行缓冲，随后消费滚动校验值。内核单独编译且禁止 LTO，节点指针为 volatile。混合表和极值表测试防止只复制 identity 也能通过。

只支持普通入口的 4288×2848、stride 8576、对齐主图，共 6,106,112 对、24,424,448 B 有效数据。未知调用者、几何、槽位、源范围或对齐直接透传并锁住本次会话。固件适配器中的源范围是保守读取窗；真实主图是否落入该窗由 L1 现场确认。它不构成图像池归属或 DMA 可见性的证明。

每张先消费一次 arm，再读主图。可解引用的主图指针只存在同步调用的自动变量中；样本逐帧保留源地址值、槽号、几何、调用者、SP 和本扩展块信息。源地址值只供显示诊断，后续不解引用。H41 只保存 tick、IRQ 有效性、编码器状态和已返回标志。样本结算和阶段推进留到下一次安全菜单入口。

resident 只有在 H40 返回 CONSUMED 与 IMG_REPLY_DONE 时才开放 H41。探针使用这个握手取得返回观察，不设置 IMG_TOUCHED，也不写 K。缺 DAT 或无有效会话时继续原厂编码。异常样本不能重新 arm，关机后才重建会话。

H41 的原始字不是零成功 errno。复查当前机身的 1,536 个原生指令包，确认包装器把下层的 u16 返回字另行保存，然后自身返回 0。旧候选把所有非零字当失败，会阻断正常路径；首错和逐字节核对在 local/first-failure-encoder-zero-assumption.json 与 local/encoder-word-audit.txt。修正后完整保留原字，超出 u16 合同才锁住探针，普通非零值不作失败解释。软件 OK 表示探针记录完整，照片保存成功仍由机主现场确认，数值本身不替代该确认。

## 访问白名单

| 时点 | 允许读取 | 允许写入 |
| --- | --- | --- |
| 初始化 | 验证过的 DAT、完整 identity 表、私有 context 与匹配身份。 | 本 DAT 的 BSS、entry table、初始化 context 和 reply。 |
| H40 | 当前 request 与 context、root 的状态及绑定 epoch、受限 K 几何字段、原生 SP 的调用者、实际主图有效字节、完整表和坐标。 | DAT 自有行缓冲、样本、校验消费值、reply 和本调用栈。 |
| H41 | 当前 request 与 context、原生 tick 和 IRQ。 | 当前样本的返回观察字段、reply 和本调用栈。 |
| 待机菜单 | 本地样本与原生 UI 所有权信息。 | 本 DAT 的文本与 glyph、受既有 UI 合同保护的独立 UI snapshot 和 UI 指针槽。 |

主图、K、RAW、DNG 子图、T、S 和文件均不在 DAT 写白名单。服务实现只开放 UI_LIST 与 UI_TEXT，其他类直接拒绝；CAP_S、CAP_W、CAP_FILE_WRITE 都不发布。文件读写、rename、delete、preview、RPC 写桥不链接进本 DAT。resident 自己装载 DAT 的只读文件动作不是探针写文件。

机器码审计遍历 H40 与 H41 的传递调用闭包，唯一间接调用是已有 tick wrapper。拍摄闭包没有 UI、分配、设置、RPC 或文件服务调用，也没有关整帧 IRQ 的指令。运行时将主图、K 和其他 native 数据设为只读。真正 resident 跳板必须写的 root 与 session 单独开放，并按写入 PC 监视 DAT，DAT 只准写本次 reply。整帧哈希包含 5,632 B 对齐尾部，当前完整的 588 B K 描述符也逐字节比较。静态结论与动态回执分开保留。

## 阶段、预算与退出

| 阶段 | 显式动作 | 处理量 | 预算及晋级 |
| --- | --- | --- | --- |
| L0 | 两次手机录像校时；每次约 30 秒，保留实际秒数。 | 四对私有 identity 自检、完整表 CRC、64 次空调用。 | 初始化另限 250 tick；每段参考区间 20,000 至 45,000 tick，原始区间差异不超过 5%。取消、超时、IRQ 异常或不一致即停。 |
| L1 | 单次 arm 后普通单张。 | 只观察入口，LUT 为零。 | H40 观察预算标称 250 tick。几何、状态和 H41 都有效才开放 L2。SP 与本扩展块大小不等于任务栈余量或空闲堆总量。 |
| L2 | 每张重新 arm，逐级晋升。 | 1、4、16、64、256、1024 行。 | 分别为 250、500、1500、4000、12000、45000 tick；本级计算和 H41 返回有效才开放下一级。机主确认正常保存后才 arm 下一张。 |
| L3 | 每张重新 arm，固定 OFF、ON 顺序共三对。 | OFF 不读主图；ON 每次完整 6,106,112 对。 | 每张 ON 为 90,000 tick；只有三张 ON 全帧、正常返回才生成汇总页。 |

arm 有 60,000 tick 有效期，并绑定 boot、heap、link、unit、mode、power epoch。每批最多 64 对，批前查预算与 IRQ，每行查绑定，结束时再检查。取消只撤掉 token，不写原图。预算、epoch、IRQ、编码状态、缺 H41、重入、tick 异常和行缓冲护栏异常都会保留首个样本并锁住后续 arm。

这些是软退出。调度延迟、一次 native tick 调用或单批内核都不能由软件预算提供硬实时上界。未完成全帧时显示 LOWER BOUND 或错误，不做整张外推；90,000 tick 也不是已经证明的相机安全停留时间。

## tick、结果页与换算

`kernel_ticks = kernel_end - kernel_start` 使用 uint32 回绕差。这是一段完整影子窗口，含批间预算检查与校验消费；不累加各批的毫秒差，避免量化误差随批次数增长。H40 到 H41 的 OFF 与 ON 差值包含探针给包装器前后增加的停留。两者都不包含 DAT 首次装载。

全部阶段完成后，八行汇总页给出 generation、L3、六张有效样本、两段校时 tick、三张 ON 的 kernel tick、三组有符号增量、三个校验值以及整帧对数。末行按 OFF/ON 顺序显示六个原始状态字。机主一张手机照片可以带回汇总。DOWN 可查看逐张原始 H40、H41、kernel 起止 tick、几何、校验和完整状态字。L1 单独显示堆块、SP 和入口观察，地址照片留在本地。

所有页面只从安全的 Image ADJ 入口发布。拍摄回调不绘制菜单，也不提供产品 loading UI。本任务只测探针；产品模式的交互另做。

机主按 [OWNER_STEPS.md](OWNER_STEPS.md)留录像与结果。实际秒数使用 `analyze.py` 换算，输入模板在 local/field-template.json。脚本拒绝缺校时、秒/tick 不一致、错误或部分帧，也要求机主确认每对照片均正常保存，输出三张的最小、中位、最大值和全体数据，不只取最快一次。H41 是编码包装器返回点，不是完整写卡点。总保存等待从手机录像另记。

## 主机与模拟器验收

`check.py` 对最终 DAT 的真实 M32R 字节分别使用 C 与 Python 后端。每个后端验证 5,343 对私有向量，覆盖所有分数排序、边界、同 Y、灰阶、非可分离混合表和 u16 极值。只读源和表映射禁止相同字节回写。另对 13 对输入计数，必须读取 312 次节点分量、52 次坐标、13 次输入。当前 C 内核回执没有解释器回退；这些计数证明 identity 没有省掉插值。

阶段验证覆盖两个校时、八行文本的真实 glyph 发布、未准入的 arm、单次消费、取消、过期、epoch 变化、错误几何、正常非零状态字、越界状态字、缺 H41、超预算、IRQ 和 tick 回绕。声明的编码器自身返回 0，另把原始字写成 4，防止旧的零值假设重新通过。整帧组经未改的 resident H40 跳板，进入 DAT，再经 H41 返回 DAT。主图和 K 均做前后比较。

`cold.py` 用 strict_r4 快模拟器从新 MAIN 与新虚拟介质启动，GPIO ADJ 打开八行菜单，再从独立 reference 进程复核。快、参考模拟器的结论只覆盖登记的主机模型。传感器、ISP、JPEG DMA 和物理存储不在这些模型的验收范围；H40 整帧使用声明的函数输入，不冒称 GPIO 全按快门已经生成真实照片。

C 后端的整帧组从 L0 准入，依次跑 L1、六级 L2 和 L3 三对，共 13 张。g171 的该矩阵已通过，三张 ON 均处理 6,106,112 对；13 张均核对 24,430,080 B 主图区域与 588 B K 不变，捕获写入监控没有违规。目标执行计数为 4,744,239,975 步，fallback 为 0；最终八行汇总的文本与 glyph 字节也已通过。GNU reference 另复核状态矩阵、冷启动与 GPIO，并从明确声明的“L3 已准入”函数输入跑一对完整 OFF 与 ON。g171 的这一对已通过，ON 完整处理 6,106,112 对，整帧与 K 不变；每张捕获均监控到 DAT reply 写入，违规写入为零。参考状态矩阵通过，冷启动保持下文所列失败。该输入不是冷启动 checkpoint，不替代从 L0 晋级的覆盖。封存脚本将这一对的处理对数、校验、状态、几何及整帧哈希与 C 后端的第一对逐项比较。两者的 tick 都由主机模型供给，只用于验证记录与换算逻辑。C 与 GNU 的步数口径不同，不据步数比例估计相机耗时；交叉比较仍按处理对数、校验、状态、几何及整帧哈希逐项核对。

冷启动首错保存在 local/first-failure-cold-native.json。续验进一步核对 resident 枚举：LOADING=1、VALIDATED=2、READY=3。原夹具在 LOADING 时把原生待机画面当作装载完成，过早发 GPIO；现等待 READY，再按同一 ADJ、ADJ_RIGHT 输入顺序打开八行列表，并要求按键确实改变状态后才判收敛。650M MAIN 上限及既有按键步数预算不变。实际装载后仍核对 generation、卡来源、重定位和完整 DAT 字节。

完整帧函数夹具的 tick 由明确的确定性模型提供。冷启动则保留 strict_r4 的原生计时器模型，该模型按模拟器指令推进，合同明示没有 MHz 或毫秒标定。因此初始化 1,550 tick 只说明当前夹具触发了既有 250 tick 软退出，不能称为实机 1,550 ms。没有修改时钟输入、放宽预算或删除失败断言来取得通过。冷启动后续取消步骤还含未登记的 MENU GPIO 名称；当前先失败于初始化锁定，尚未执行该步骤。本轮保留原 GPIO 输入，也未扩大工具目录的写入范围；该取消路径仍属 OPEN。

参考函数夹具还发现内存区间容量问题：原映射在初始化时有 36 段，捕获白名单时有 43 段，超过 GNU 桥接的 32 段共享 RAM 容量，转入逐步 Python 转发。已保留未完成回执与调用栈，仅合并地址相邻且权限相同的区间，保持原栈区边界；捕获时降至 28 段。独立逐段比较在初始化、主图建立、捕获白名单和恢复四个时点验证了覆盖、每个字节及读写权限完全相同，见 local/resume-20261105/reference-map-equivalence.json。GNU 库、DAT、函数输入和原有断言不变；同步前新增容量断言。此前参考状态 PASS 已归档，修正后重跑的 18 项状态回执与旧回执逐字节完全相同，见 local/resume-20261105/reference-state-equivalence.json。只重跑受影响的参考状态与整帧，完成的 C/Python 检查不重做。

首个阶段失败发生在宿主解码缓存的字节核对，位置属于 session request。原 fixture 将可变 session 与代码放在同一个解码区。现已为真实代码建立独立只读映射，保留字节核对，不放宽指令支持；首错留在 local/first-failure-state-c.json。负载延期也保留日志，不能计为产品测试通过。

从仓库根复跑，所有脚本都要求 nice 15 和隔离 Python：

```sh
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/static.py
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/check.py --backend c --check kernel
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/check.py --backend python --check kernel
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/check.py --backend c --check state
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/check.py --backend python --check state
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/check.py --backend c --check full
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/check.py --backend reference --check state
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/check.py --backend reference --check reference-one
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/cold.py --backend native
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/cold.py --backend reference
```

机主在 2026-11-05 批准改用仓库 tools/loadgate.py。common.gate 调用 workers()，按实测 CPU 空闲与内存准入，保留两核；每条 load.jsonl 记录完整 info。串行验收队列与独立冷启动作业各自先检查准入，全部 nice 15，不安装依赖。父任务随后澄清：冷启动与完整帧的 tick 由模型提供，主机负载不改变其结果。全部主机检查和现场数据换算现使用普通 gate，不等待 quiet_for_timing()。GNU 执行批次仍为最多 1,600 万步，没有跳过目标指令。仅调度修改时，cold 的 14 个和 check 的 45 个断言 AST 与原文相同，记录在 local/resume-20261105/assertion-audit.json。随后为修复真实缺陷，同步更新代数与页面身份，H10 断言改为保留原生 OK，冷启动的 READY 条件收紧；其余内核、完整帧、校验、预算和状态断言保留。

四项续验的成败边界是指令数、模型 tick、字节比较和状态断言。冷启动待机上限仍为 650M 指令，GPIO、publication 与函数调用的既有步数上限均不变；没有按主机墙钟判定产品失败的项目。host_seconds 只记主机验证耗时，不参与断言，不换算成相机速度。唯一墙钟截止是本轮约三小时的执行预算，达到它只能报告未完成，不能判作相机性能结论。真实每张秒数只来自机主现场。

queue.py 在作业边界从已完成清单续跑，真正的测试失败立即停，不自动重复。首轮六小时已于 09:26:47 UTC 截止；父任务另授权约三小时续验，本轮截止为 12:27:58 UTC。独立复审的单条复跑命令和现场分析工具没有这个日期限制，仍检查准入与写入范围。宿主调度和回执保存修正没有触发重建；冷启动确认真实 DAT 缺陷后，先升 170 修正 ABI，再升 171 修正 OK 路由，并重新验证。169、170 的通过项不能代替 171 的验收。

现场数据先复制 local/field-template.json 为 local/field-results.json，再填入汇总页的 R、K、D、C 和六个 S。S 是十六进制，JSON 中填转换后的十进制整数，例如 `0014` 填 `20`；校验值保留八位字符串。每对的 saved_ok 只有在两张都正常保存时才填 true。两段 phone_seconds 从录像读实际区间。

```sh
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r1/analyze.py research/lut_shadow_probe_r1/local/field-results.json --output research/lut_shadow_probe_r1/local/field-analysis.json
```

## 回退与 OPEN

探针没有持久化写入口。机主正常待机后关机，卡上换回原先备份的 g157 test 或已获准的 g158 DAT，再开机即可撤掉探针。resident loader 优先检查卡上的文件；探针不会把更高代数复制进 IROM。卡上原 DAT 和仓库回退副本的摘要要分别核对，不能声称仓库副本就是原卡备份。

尚待机主关闭的项包括：两段真实校时、实际 L1 路径与源范围、逐级停留和看门狗反应、三对真实 OFF 与 ON、总保存等待和现场回退。DMA 到 CPU 的主图可见性仍需现场证据。本探针完全不写主图，不能替正式 LUT 模式验收 CPU 到编码器的可见性、输入颜色坐标、原帧独占、取消或修改后主 JPEG。

以下封存区列出主机尚未完成的项；未通过的项不会由“已生成 DAT”替代。

## 续验封存与完整性

原清单共 434 项，含 29 项公开文件和 405 项本地条目。最终公开文件集合仍为 29 项：19 项为本轮有意更新，10 项字节不变；原本地条目 33 项因重建、回执或封存更新，372 项不变。原 8 份首错逐字节保留，内核与阶段软预算均未改。逐项摘要及新旧 SHA 在 local/resume-20261105/integrity-final.json；公开与本地 SHA256SUMS 由同一审计脚本重算并逐项核验。

参考整帧在预算边界前完成。队列随后因 TASK_DEADLINE 没有再次运行换算检查；此前独立运行的同 SHA 换算检查已经通过，未被覆盖。没有在截止后继续目标指令计算。

<!-- BEGIN generated seal -->
DAT SHA-256：`d3af026e6e2455e242e3e50e1c474b0e36a670304c043da21420ffef385287e3`。generation 171，完整文件 50,252 B，代码区含表 49,804 B，BSS 11,980 B。
主块请求 69,860 / 107,612 B，余量 37,752 B。

| 检查 | 当前状态 |
| --- | --- |
| static | PASS |
| kernel-c | PASS |
| kernel-python | PASS |
| state-c | PASS |
| state-python | PASS |
| state-reference | PASS |
| full-c | PASS |
| full-reference | PASS |
| cold-native-latest | OPEN |
| cold-reference-latest | OPEN |
| analysis-check | PASS |

PASS 回执均绑定本 DAT SHA。整帧交叉比较已通过。[local/seal.json](local/seal.json)列出精确路径。
仓库 g157 test 回退副本 SHA-256：`2b8904592ce56ab03649ced52c8479b0bbac4e45bf9a47505d220795bb3ec56c`。它不是机主卡的备份。

实机校时、真实照片的三对 OFF 与 ON、保存等待、DMA 及现场回退均未执行。
<!-- END generated seal -->
