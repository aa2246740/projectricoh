可以交复审。离线实现与要求的主机、快模拟器和参考模拟器检查通过，实机秒数待机主采集。

# 3D LUT 影子测速探针 r2

2026-11-05。本轮从 12:56:20 UTC 开始，截止 16:56:20 UTC。只在主机离线工作，没有操作相机、SD 卡或网络，没有安装依赖、commit 或 push。r1 的源码、DAT、首错及原封存保留；本轮产物独立放在 `firmware/engine_lutprobe_r2/`、`firmware/package_v310_lutprobe_r2/` 和本目录。

设计合同仍是 [v311 B1、B2 与 D3](../v311_feasibility_r1/REPORT.md)，入口依据为 [H40 研究](../body_lut_r2/REPORT.md)，tick 与成本依据为 [CPU 研究](../cpu_speed_r1/REPORT.md)及[内核研究](../look_ceiling_r1/REPORT.md)。这些依据和主机模型都不提供真实每张秒数。

## 旧初始化为何用了 1,550 tick

用原 g171 DAT、fresh MAIN、相同虚拟介质与设置、原 GNU reference 时基，只加读断点，逐段复现如下。原 DAT SHA 为 `d3af026e6e2455e242e3e50e1c474b0e36a670304c043da21420ffef385287e3`。

| 操作 | 模型 tick | 实际工作 |
| --- | ---: | --- |
| 重复清空 `LpState` | 230 | 逐字节清空 10,956 B。resident loader 已先清过整片 BSS。 |
| 私有内核自检、比较与边界开销 | 1 | 原四对输入经过完整四面体内核，再与原输入比较。 |
| 64 次空调用 | 0 | 确实调用 64 次，当前模型不足一个 tick。 |
| 完整节点表 CRC | 1,319 | 校验所有 29,478 B，查 CRC 字节表。 |
| 合计 | 1,550 | 原 250 tick 预算因此锁住会话。 |

identity 表在 DAT 内编译完成，没有运行时建表。被计时的 `ig_init` 区间内，native allocation 记录为零。resident 分配、DAT 读取、envelope 验证及全 BSS 清零在计时区间外；UI snapshot 分配和文字发布发生在之后的菜单入口。逐段 tick、目标步数、旧包身份及零分配回执在 [local/profile-g171/result.json](local/profile-g171/result.json)。这些 tick 由未标定毫秒的指令模型产生，不能称为实机 1,550 ms。

## 初始化改为显式待机切片

`ig_init` 只核对代数、设置少量状态与护栏，保留原 250 tick 上限。它利用 resident loader 在 bootstrap 前已清零 BSS 的合同，去掉重复的大清空。`lp_reset` 仅用于这一新加载的 BSS；中途重启调用独立的进度重置函数，不会对活动样本清零。

初始化共 17 片。前 15 片每次最多校验 2,048 B，最后一片校验剩余字节，随后一片执行原四对私有内核自检，最后一片执行原 64 次空调用。CRC 连续保留 offset 和累积状态，完整覆盖全部 29,478 B。内核、表、私有输入和比较标准没有改。

每次进入 Image Setting 只执行一片，返回原生代码后才能执行下一片。页面提示 `OK EXIT / REOPEN NEXT`；机主按 MENU/OK 退出，再用 ADJ 重开推进。没有创建 resident、RTOS 或定时任务，没有把连续 17 片藏在一个回调中。既有 apply 回调若被原生调用，也最多执行一片，但现场步骤只使用已验证的重开入口。

每片须满足 IRQ 开启、图像状态空闲、匹配的 Image Setting 活动和页、当前 UI 分区有效。第一片绑定会话 epoch，后续片核对该绑定。开始和结束读取原 tick，保存 last、max、total、片数和进度。单片超过 250 tick、tick 差异常、IRQ 或 epoch 变化就锁住初始化，L0 和所有 arm 均不可用。这里的 250 tick 与旧检查一样约束初始化计算，不把 UI 字体服务或原生页面绘制的既有耗时记为内核工作。它是软退出，不能提供 native 调用或调度延迟的硬实时保证。

确认退出保留进度。非确认退出、非安全菜单入口和 shutdown 会撤销未完成初始化，清掉 offset、累积 CRC、自检和 table_ok，不保留主图指针。ABORTED 页面必须显式按 MENU/OK 选择重启，重开后才从第一片继续。FAILED 锁住本会话，原始 CRC 与进度保留；末尾的时基、预算、IRQ 与 epoch 检查均须通过，本会话不可重新 arm。完整表、自检和空调用都通过后才进入 L0。

## MENU 夹具与确认选择

实机研究记录的物理键是 MENU/OK，raw 24，native press 0x23。canonical strict_r4 原来仅注册 `OK`；本轮只补 `MENU: 24` 别名，再用仓库标准脚本在 17 个 fresh reference 进程重建 `NATIVE_REGISTRY.json`。CPU 库、wire 扩展和模型时基没有改。前后摘要及注册日志在 local/MENU-harness-change.json 和 local/logs/registry-refresh.log。

MENU/OK 是确认键，不能当作独立取消键。旧 cold 断言中的 MENU 取消假设已移除，实际取消使用非确认 ADJ 退出。原生上下键只移动光标，不调用 H08 的 apply 回调。g191 首错证明“UP 推进一片”不成立，因此初始化改用重开入口，文字也改正。

同一事实还暴露了旧确认逻辑读缓存光标的问题。新 DAT 在确认时读取 resident H08 同样使用的原生一基光标，先验证 1 至 8，再派发动作；不改变键义。冷启动用实际 GPIO 从第 1 行移到第 8 行，确认打开诊断页，再返回 L0。函数夹具另验证只改变原生光标也能选择正确动作。

## 身份、内核与读写边界

候选代数必须至少 191，161 至 190 不参与选择。全仓扫描包含 tracked、untracked、ignored 工作路径和文本，并读取所有 DAT 封装头。扫描原始命中、二进制偶合及非固件 `old_generation_heap_mib` 命中的分类均保存在 local/generation-scan*。g191 已占用并归档；最终代数与 SHA 以本页封存区为准。

resident 保持当前 v3.10 原字节。它的 envelope gate 接受非零 generation，没有固定为 g157 或 g158。本 DAT 同时检查封装头中的 generation 与引擎版本恰好等于自身代数，无需修改 resident 或配方 gate。DAT、ELF、固件字节、地址、适配器和原始回执均留在忽略的 local/。

完整 identity 表仍为 17³、4,913 节点、三通道 Q8.8，共 29,478 B；另有 1,024 B 坐标表。Q8.8 保持节点精度和 halfword 读取成本。`kernel.c` 与 `kernel.h` 和 r1 逐字节相同，单独编译且禁用 LTO。每对输入的两个 Y 各跑一次完整四面体，稳定排序三个分数，读四顶点三通道并插值。没有 identity 特判、灰色特判、同 Y 特判或跳像素。每对必须读 24 次节点 halfword、4 次坐标与一次输入字。

只支持普通单张 4288×2848、stride 8576 的主图。整帧是 6,106,112 对，有效字节 24,424,448 B。每批最多 64 对，输出只写 DAT 自有 8,576 B 行缓冲，再消费滚动校验值。样本保留源地址供显示，后续不解引用。H41 只保存返回 tick、IRQ、原始状态字和已返回标志，阶段结算留到安全待机入口。

| 时点 | 可读取 | 可写入 |
| --- | --- | --- |
| bootstrap 和初始化切片 | 已验证 DAT、表、context、root 状态与 epoch、tick、IRQ、安全 UI 状态。 | 本 DAT BSS、entry table、初始化 context、reply 和调用栈。 |
| H40 | request、context、root 状态与绑定、受限 K 几何、调用者、实际主图、表和坐标。 | DAT 行缓冲、样本、校验消费值、reply 和调用栈。 |
| H41 | request、context、返回状态、tick 和 IRQ。 | 当前样本的返回字段、reply 和调用栈。 |
| 待机 UI | 样本和 UI 所有权信息、原生光标。 | DAT 文本与 glyph、既有 UI 合同的独立 snapshot 和 UI 指针槽。 |

主图、K、RAW、DNG 子图、T、S、设置和文件均不在 DAT 写白名单。服务只开放 UI_LIST 和 UI_TEXT，不发布文件或颜色设置能力，不链接文件写入、preview 或 RPC 写桥。resident 装载 DAT 的文件读取不属于探针写入。

静态检查遍历拍摄回调的机器码调用闭包；唯一间接调用是原 tick wrapper。闭包不含 UI、分配、设置或文件服务，也没有关整帧 IRQ 的指令。动态捕获把主图、K 和其他 native 数据设为只读，resident 必须写的 root/session 单独按 writer PC 监控，DAT 在其中只可写 reply。每张核对完整 24,430,080 B 主图区域哈希，包含 5,632 B 对齐尾部，并逐字节核对 588 B K。

## L0 至 L3 与八行结果

| 阶段 | 显式动作和处理量 | 预算与晋级 |
| --- | --- | --- |
| 初始化 | 17 次待机切片，完整 CRC、原私有自检及 64 次空调用。 | 每片 250 tick；全部完成才开放 L0。 |
| L0 | 两段约 30 秒手机录像，记录各自真实秒数。 | 每段 20,000 至 45,000 tick，原始 tick 差异不超过 5%。 |
| L1 | 单独 arm 后一张普通照片，只观察入口，不跑 LUT。 | H40 250 tick，几何、状态、H41 都通过才进 L2。 |
| L2 | 每张 arm 一次，依次处理 1、4、16、64、256、1024 行。 | 分别 250、500、1500、4000、12000、45000 tick。 |
| L3 | 每张 arm 一次，OFF/ON 三对，共六张。 | 每张 90,000 tick；三张 ON 必须各处理 6,106,112 对。 |

arm 单次消费，60,000 tick 过期，绑定 boot、heap、link、unit、mode 和 power epoch。批前查预算及 IRQ，每行查绑定，结束再查。错误几何、过期、epoch、IRQ、重入、缺 H41、坏 tick、缓冲护栏或超预算都锁住后续 arm。未完成整帧只能报已处理量和下界，不外推整张秒数。90,000 tick 不是已证明的相机安全停留时间。

`kernel_ticks` 是首批开始到最后校验完成的连续影子区间，含批间检查和校验消费。它不累加每批毫秒差，避免量化误差累积。H40 到 H41 的 ON 减 OFF 是编码包装器内的增量，允许为负。H41 原始字是已核对的 u16 返回值，普通非零值不自动视为保存失败；超出 u16 才锁住，保存成功仍由机主观察。

最终八行显示代数、L3 六张完整样本、两段校时 tick、三张 kernel tick、三个有符号增量、三个校验值、整帧对数和六个原始状态字。一张手机照片可带回。逐张原始页给出 H40/H41、kernel 起止 tick、几何和状态；现场每张立即拍下，不依赖上下键浏览历史。所有发布都在安全 Image Setting 入口，拍摄回调不绘制菜单。

现场步骤见 [OWNER_STEPS.md](OWNER_STEPS.md)。分析工具仅接受本 DAT SHA、两段真实校时、三对完整 ON、有效状态、校验及机主保存确认。输出全部三张与最小、中位、最大值。H41 不等于写卡结束，录像中的总保存等待单独记录。

## 本轮验收与可复跑入口

C/Python 内核各验证 5,343 对私有输入，覆盖排序、边界、同 Y、灰阶、非可分离混合表和 u16 极值。短调用统计强制 13 对读取 312 次节点分量、52 次坐标、13 次输入，防止内核被优化成复制。初始化矩阵分别在 C、Python、GNU reference 上覆盖 pending 准入、单片进度、确认保存、abort、显式重启、非待机拒绝、IRQ、epoch、坏 CRC、250 tick 软退出和回绕。

状态矩阵保留 r1 的输入和断言，并增加原生光标确认检查。full-c 从 L0 校时经过 L1、六级 L2、L3 三对，共 13 张；full-reference 以明确声明的 L3 准入函数输入复核一对完整 OFF/ON。两者都经过真实 resident H40 跳板、DAT、声明编码器和 H41，并比较主图、K、处理对数、校验、状态及几何。reference 的已修正相邻映射合并保留，32 段容量断言不变，进度回执按进程分开。 C 的 13 张矩阵已通过，三张 ON 都是完整 6,106,112 对，所有主图与 K 比较通过，fallback 为零；最终八行汇总的文本和 glyph 也通过。 GNU reference 的完整 OFF/ON 也已通过，ON 为完整 6,106,112 对，24,430,080 B 主图与 588 B K 不变；实际 resident 跳板及 DAT reply 写入监控通过，与 C 的第一对处理量、校验、状态、几何和整帧哈希一致。内核、完整帧及校验函数的 AST 与 r1 相同，原状态断言全部保留，见 local/assertion-audit.json。

两种冷启动均从 fresh MAIN、全新虚拟介质和相同设置开始，不用 checkpoint。覆盖装载完成、BSS 零值、第一次 ADJ、MENU/OK 退出、保存进度、17 片初始化、原生光标诊断选择、L0 开始、ADJ 取消及最终安全待机。保留 650M MAIN 和原有按键、发布收敛指令预算。快模拟器的新 SHA 冷启动已通过 58 次 GPIO 操作，17 片最大 111 tick、累计 1,462 tick，最终 view/activity 为正常待机，arm 与参考区间均关闭，unit 写命令为零。 GNU reference 冷启动也已通过，两种后端的全部 58 个 GPIO 状态与 L0 文字逐字段一致，17 片最大与累计 tick 相同，最终均安全待机、unit 写命令均为零。两种冷启动共执行的目标步骤各为 1,161,200,000；这是 MAIN 加全部 GPIO 流程，初始 MAIN 的 650M 独立上限没有放宽。8 行文本既核对 ASCII，也核对真实字体桥发布的 glyph 字节。模型不覆盖传感器、ISP、JPEG DMA 或真实文件保存，不把声明的 H40 主图输入称为 GPIO 快门生成照片。

```sh
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/static.py
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend c --check kernel
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend python --check kernel
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend c --check init
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend python --check init
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend reference --check init
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend c --check state
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend python --check state
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend reference --check state
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend c --check full
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check.py --backend reference --check reference-one
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/cold.py --backend native
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/cold.py --backend reference
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/check_analysis.py
nice -n 15 /usr/bin/python3 -I -B research/lut_shadow_probe_r2/seal.py
```

调度只用 `loadgate.workers()`，0 才延期，记录 load.jsonl 的完整 info，全部 nice 15。 参考函数夹具把同一进程内的短调用合成最多 16M 条实际目标指令的一批，额度耗尽才再次采样；每个函数的原 max_steps 仍独立保留，没有跳指令或删断言。原整帧参考进程继续运行，未完成的 state-reference 作业保存停止记录后重启，队列从六个已完成作业之后续跑。状态 19 项与初始化 10 项的 C、Python、GNU 回执已逐字段交叉比较，全部一致。这里没有按主机墙钟判定通过或失败的测试，也不从主机耗时估算相机速度。MAIN/按键上限是指令数，初始化和每帧上限是原模型 tick。`quiet_for_timing()` 只适用于真正依赖宿主墙钟的性能测量，本轮没有此类结论。四小时截止只是任务执行预算，到点只能交阶段结论。

## 首错、完整性与尚待现场的项

g191 的 GPIO 首错及停止前已完成的部分回执、DAT、ELF 和包留在 local/g191-invalid/。真正失败与主动停止的 KeyboardInterrupt 分开记录，后者不算产品失败。build 脚本说明文字与链接时摘要的短暂漂移也保留首错、原脚本和 AST 相同证明；不把它当作 DAT 缺陷。 g192 首次冷启动还揭示夹具过早判稳：它先观察到待机，2M 指令确认段后却处于原生过渡页。原失败与夹具源码保留，随后要求确认段后 view 和 activity 仍一致。每个 GPIO 动作总上限仍为 902,400,000 指令，MAIN 与 tick 模型均未改，未因此重建 DAT。

r1 原有 29 个公开文件与 722 个封存项已逐项核验，原清单字节也与本轮基线完全相同；最终封存会再核验一次。r2 新增独立 init.c，公开文件集合为 30 项。公开与本地 SHA256SUMS 单独生成，并明确列出仅有的两个共享夹具文件变化。原始首错不会被后来的 PASS 覆盖。最终摘要、回执路径和交叉比较在下方封存区与 local/seal.json。

实机校时、L1 路径和源范围、逐级停留与看门狗反应、三对真实 OFF/ON、总保存等待、DMA 可见性和现场回退仍须机主采集。探针完全不写主图，不能替正式 LUT 模式证明颜色坐标、原帧独占、修改后 JPEG 或 CPU 到编码器的可见性。

正常待机后关机，卡上换回机主备份的 g157 test 或已获准 g158 DAT，再开机即可撤掉探针。探针不写 IROM 或设置，resident 仍优先检查卡。仓库回退副本不是原卡备份。

<!-- BEGIN generated seal -->
DAT SHA-256：`fd0aac89c0e9ce27d1cbe45c148aebc7cb7d69add88f1523b93b9b0b70c31546`。generation 192，完整文件 51,616 B，代码区含表 51,168 B，BSS 12,012 B。
主块请求 71,256 / 107,612 B，余量 36,356 B。

| 检查 | 当前状态 |
| --- | --- |
| static | PASS |
| kernel-c | PASS |
| kernel-python | PASS |
| init-c | PASS |
| init-python | PASS |
| init-reference | PASS |
| state-c | PASS |
| state-python | PASS |
| state-reference | PASS |
| full-c | PASS |
| full-reference | PASS |
| cold-native-latest | PASS |
| cold-reference-latest | PASS |
| analysis-check | PASS |

PASS 回执均绑定本 DAT SHA。整帧交叉比较已通过。[local/seal.json](local/seal.json)列出精确路径。
仓库 g157 test 回退副本 SHA-256：`2b8904592ce56ab03649ced52c8479b0bbac4e45bf9a47505d220795bb3ec56c`。它不是机主卡的备份。

实机校时、真实照片的三对 OFF 与 ON、保存等待、DMA 及现场回退均未执行。
<!-- END generated seal -->
