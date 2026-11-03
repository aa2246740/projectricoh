不可以上卡

本结论针对 r3 固定件 `firmware/lut_p0_timing/local/staged/GXRCE.DAT`，53,100 B，generation 1，tag `LUTP0001`，SHA256 `75edcedac2219d31a1cc2e789e9ecc7381df528ee1e94d4b5e08329a668c2e87`。独立重建与该文件逐字节相同。上轮两条错误参考计时反例已经修复，但四字段白名单的“每次退出精确恢复”条件仍不成立，留下一个 P1 阻断项。

本轮只做离线主机审查。没有存储卡、相机、相机 USB、网络、安装、刷写或提交操作；未改候选、官方文件、卡备份及其他 worker 的目录。所有新增文件均在本目录。下文 P 指 `firmware/lut_p0_timing/`，R 指 `firmware/resident_v34c/resident/`；证据文件未加前缀时均指本目录。

P0 / P1 / P2

- P0：未发现本候选可达的 IROM 安装或写入、照片缓冲改写、GXTS/GXLS/CTL/配方/GXRCE.OK 操作。
- P1-01，本轮白名单恢复反例，承接上轮 P1-03。`R/shared.c:68-70` 抓取两个 native cursor 后，把小于 1 或大于 7 的值改存为 1；`:83-84` 退出时写回钳位后的值。P0 在 UI_LIST 发布前没有拒绝这种输入。以 type=0、table=`0x2022F56C`、原生表第 0 项 count=13 为前态，执行官方 ADJ 游标 store 片段，将两个 cursor 设为 8..13。P0 正常发布后，用 MENU、确认 OK 或 H06 退出，两个字段都变成 1，未恢复原值。113/114 各有 6×3 个反例，共 36 个，均在真实 C 下通过 ASan/UBSan。列表指针、行数和 tag-33 指针恢复正常；问题是两个白名单字节的恢复值。见 `edge_cases.c`、`edges.stdout`、`edge-results.json`、`native-cursor-evidence.json`。普通 1..7 的 49 种游标组合全部精确恢复，不能据此推出入口永远只取 1..7。

  这不是任意损坏内存的假设。官方第 0 项确有 13 行；`0x20285984/90` 从 r10 写两个 cursor，`0x20285AC0` 与 `0x20285B14` 另有明确的 13、9 默认游标 store。相同字节在当前运行 body 中也存在。`0x20331D18` 这个 H01 前调用是直接返回，没有在此重置游标。证据见 `adj-constructor.disasm`、`native-enter-lock.disasm`。本轮仍未执行完整物理导航；测试给 r10 的 8..13 是边界输入，不能冒称相机已出现该现场状态。阻断原因是当前件接受这些输入，却没有证明入口排除了它们，也没有满足任务要求的精确恢复条件。

  放行前应在 P0 调用 UI_LIST 之前拒绝会被该服务钳位的原始游标，并验证拒绝时不改 native；或给出完整入口取值域的可核查证明再复审。这里不建议修改已冻结、已审的 gen 114 服务。本轮没有修改任何候选源码。
- P2-01，本轮日志新旧选择有误用风险。`P/probe.c:199-210` 开始新参考时不刷出开始记录。上一轮完成日志可在新一轮参考途中掉电后继续存在；它仍是合法的旧测量。中断产生了更高代次日志时，`P/REPORT.md:125` 的“选记录完整且 error=0 的最新一份”又会跳过最新的无效记录而选旧 DONE。独立案例中旧 DONE 的黑匣子代次为 2，新中断记录为 3。新记录被 decoder 拒绝，但旧记录配上另一轮的 8 秒读数仍输出 complete=true、tick_hz=1250；模型真实值为 1000 Hz。见 `edges/`、`decoder-results.json`。没有把新中断日志误判为有效；缺少的是日志与本轮秒表的关联。每次尝试前须备份并移走旧 GXRBX 日志，任何重启重测也如此。解码时先判最高代次，再检查是否完整有效，不能退回采用较旧 DONE。本目录的只读辅助工具 `decode_pair.py` 已按这个顺序验证，并要求匹配屏幕 REF DT；它无法识别没有开始记录的旧轮次，因此不能替代清理旧日志。
- P2-02，本轮指南缺备用卡路线。`P/USER_GUIDE.md` 是中文六步，卡 B 的 DAT/OK/CTL、机身更新文件、普通电源启动、中断重来和移除探针等说明已补齐，但只写了卡 B，也只说备份旧日志，没有要求移走旧日志。备用卡更便于隔离当前卡 B 上的机身文件、28 个官方文件、114 DAT 和照片。两种路线及修正后的六步流程见下文；不能把备用卡测试结束理解为应立即插回仍带产品 DAT 的卡 B。

旧发现和核心复测

| 上轮项目 | 本轮结果 |
| --- | --- |
| P1-01，首次发布失败后起点为零 | 已关闭。UI snapshot 分配连续失败 1..3 次、首批 16 个字形转换逐位置失败后重试，均不提交参考状态。旧 first-publish-retry 刺激得到 start=100000、end=110000、delta=10000；完整日志解码为合成的 1000 Hz。 |
| P1-02，MENU 后重开沿用旧起点 | 已关闭。MENU/H06、参考页发布失败和重复 H01 都使区间失效，INTERRUPTED/error=7 粘住。重开虽取新起点，确认后仍进 ERROR、样本为 0，decoder 拒绝。 |
| P1-03，native 写入 | 写入地址和服务来源符合本轮白名单；精确恢复存在上述 P1-01。不能继续称其为零 native 写入。 |
| P2-01，最大长度首次执行 | 已关闭。四个独立 H08 依次准入 4、64、512、4096 对；任一档超预算都会停在该档，后续 80 次回调也不再执行 kernel。 |
| P2-02，卡 B 说明不足 | 卡 B 旧包隔离和回退基线已补齐；本轮仍需补日志隔离与备用卡说明。 |

独立矩阵在每套 113/114 夹具下各跑 170 个场景、8,085 个 H08 回调，另以 O1+ASan/UBSan 重跑同一矩阵；两版产生的全部日志逐字节相同。覆盖 REF、准入前及四个档位后、正式样本 1/37、DONE、ERROR 的 MENU/H06/发布失败/H01 重试；OK 覆盖两个官方 caller `0x202C2D74/84` 与 keep=0/1。确认参考后的 BENCH 正常退出和重开允许继续；中断参考后的重开始终不能进入测速。见 `adversarial.c`、`adversarial-results.json`、`sanitized-results.json`。

冷启动模型在参考区间中重置 RAM 后，必须重新发布、取得新起点并重新确认。新完整日志起点为 50000，delta=10000；未携带旧未确认起点。单次 uint32 wrap 通过；零区间、半圈及倒退参考均被拒绝。两份冻结 r2 的错误完整日志因缺少 P0R3 协议也被拒绝。独立 decoder 检查共 54 项，包含 interrupted/未确认标记、零起点、预算、准入、DONE 错误、样本不全、无效外部秒数。无效参考直接报错，错误或未完成批次不输出 tick_hz。掉电保留旧 DONE 的边界单列为 P2-01。

白名单、服务与分批工作量

写追踪为全部真实 host C 单元的 LLVM O0 store 和 memcpy/memmove/memset 加观察器，共 3,126 个写入位置。观察器按函数区分发布与撤回，连同值 store 也捕获。只放行 UI_LIST 的 `ui_list`、已审 shared 的 `rv_ui_abort/es_ui_abort` 对四字段的精确地址和宽度；tag-33 state slot 另只允许原 UI_VIEW 发布和 shared 撤回。私有 P0State、resident root、有效扩展堆分配不算 native 结构。

| 原生字段 | 宽度 | 官方 ilaunch3 文件偏移 | 每套追踪次数 |
| --- | --- | --- | ---: |
| 0x2022F725 | 1 B | 0x1E4925 | 8787 |
| 0x2022F726 | 1 B | 0x1E4926 | 8787 |
| 0x2022F5A8 | 4 B | 0x1E47A8 | 8787 |
| 0x2022F5AC | 1 B | 0x1E47AC | 8787 |
| tag-33 state slot | 4 B | RAM 视图栈，无静态文件偏移 | 20 |

每套共 35,168 次，白名单外为 0。20 次 tag-33 store 是测试主动调用原 UI_VIEW 切到 snapshot、随后撤回的十组用例；正常 P0 本身不切换该指针。每个阶段都核对了切换后的精确恢复。原生构造器本身在追踪窗口外，不能把其合法的 type、游标及视图栈写入算作 P0。负控实际执行对 `0x2037F3BC` 的同值写，观察器以退出码 93 拒绝。见 `observer.c`、`trace/functions.json`、`adversarial.stdout`。这些通过项证明写入来源与地址，未掩盖上述恢复值反例。

独立将 P0 暂存服务对象、审查重建对象与 `research/review_publish_v114/rebuild/` 的八个已审对象逐段比较：所有 allocated section 和 relocation section 逐字节相同；服务源码和 shared/header 副本也逐字节相同。整个 `.a` 不同，差异涉及含路径的非分配 GCC LTO 元数据，不能声称整个归档字节相同。P0 通过 ld、不用 LTO 链接；从原冻结源码重建出的最终 DAT 又与待审件完全相同。见 `independent-audit.json`、`run/service-build.json`。

准入预算为 `reference_delta/200` ticks，每档结束后检查；测试覆盖四档各自超过预算一 tick 和恰等于预算的边界。它不能抢占一条尚未返回的 kernel。准入每回调最多 4096 对；正式样本每回调含预热最多 8192 对，单个计时窗最多 4096 对。每次 hook 返回后才开始下一块，没有循环调用下一条样本。约 10 秒参考对应约 50 ms 的准入内核预算，只是公式，不是实际菜单任务、I/O 或 watchdog 的时间上界。

容器、真实安装拒绝、回退与算法

resident build `eb96410f5224f76c1cf684a3bd6789eca4c80acf34019120e30dacaeb01da941`、ABI `b6353e4de1c89bd37c08ba6734efc8e0`、官方 body ID、运行 body 的 resident payload/root pins 和 hook 补丁均重新核对。generation 1 的卡包优先于 IROM；低代次本身不等于永不可安装。真正产品 gate 对 P0 返回 VERSION，真实 `ps_install` 返回 VERIFY；将 verifier 仅放宽至 resident envelope 后，真实 113/114/115 IROM 夹具均返回 CONFLICT，且无安装、写入或 DAT→OK。UINT32_MAX 另保留原有内存头部负例，未当成真实产品。

| 真实主机夹具 | 大小 | SHA256 |
| --- | ---: | --- |
| 113，resident_v34c full-r11 | 64816 B | 6cb63aa47c18086f5ade681ffe4dc97378394ff7a65c0688d19b3880d804c707 |
| 114，engine_v35_publish staged | 65088 B | 132e56389808970b0db8a8c4a359c46f18f0fb2423ecbc11f671d18df19a49a5 |
| 115，engine_v36_r28 staged | 65252 B | a9743bb9f0ace0ebba1d807af124210a2a098ad64f31c27083412923c841c4b8 |

三套真实文件都验证卡优先选择 P0/1；移除 DAT 后选回 IROM A，A 缺失时选 B。混合 A113/B114 与 A114/B113 选择较新 114；两种排列的原字节均未改变。产品入口仍是仅用于观察 loader 选择的替身，没有在主机执行完整产品，也没有证明相机当前实际装了哪一代。见 `independent-audit.json`、`mixed-loader.stdout`、`run/host-results.json`。

P0 的可达入口只做探针，申请 CAP_UI；文件系统替身拒绝除 GXRBX0/1.BIN 外的创建/写入和一切 rename/delete。最终 ELF 不含 ps_install、ig_menu、ig_init、ig_control_off。通用服务库包含其它接口，不能仅凭字符串出现与否断言可达性。唯一持久副作用是黑匣子日志写入或轮换覆盖；CTL OFF 不停用 P0，停用须关机移走探针 DAT。

原回放与上一轮独立数值 oracle 分别重跑。两套各 16,384 对的 packed M32R kernel 回放通过；独立 oracle 的四份 mixed/identity/extremes/random 输出还与冻结 r2 输出逐字节一致。每对读 24 个节点 halfword、4 个坐标 word、一次输入 word 并写一次输出 word，寄存器、SP、IE 和私有写入范围检查通过。数值 oracle 从上一轮审查原样复制重跑；指令解释器仍共享既有有限 M32R 模型，不是独立硅片模拟器。另重跑九个 native seed 指令用例。见 `run/replay-results.json`、`independent-kernel-results.json`、`r2-output-comparison.json`、`run/seed-replay-results.json`。

17³×3 的 Q8.8 表仍为 29,478 B、坐标 1024 B；255 映射 cell15/frac256，六种四面体排序、稳定 ties、共享色度合并与舍入/clip 保持原算法。kernel、timing 目标对象与 r2 完全相同。参考换算 `tick_hz=Δtick/Δseconds`，净斜率 `b=lut_slope-empty_slope`，`ns_per_pair=b/tick_hz×1e9`。独立合成日志取 empty/decrement/LUT 斜率 1/2/3、10 秒对应 10000 ticks，准确得到 tick_hz=1000、b=2、2,000,000 ns/对；净全长少于 16 ticks 时不输出 ns/对。这是公式验证，不是相机测量。

真实 blackbox.c 除 include 外未改，参考终点在 flush 前取得，准入与正式样本均在第二个 tick 后才校验、发布及 flush。独立矩阵禁止在测量窗内创建/写日志或转换字形，均通过。预热、重填、CRC、UI 和 I/O 不计入 kernel 时间。33³、CPU MHz、全照片保存耗时和拍摄颜色不在本件测量范围内。

r2 → r3 的独立差异清单只含 probe.c/h 的状态、撤回与准入修复，decode.py 的协议/拒绝逻辑，以及 build/audit/freeze/stage/verify/host_checks 的对应验证、文档和四个新增 r3 验证文件。14 个其余源文件不变；r2 保存清单 254 项全部哈希通过；kernel/timing 对象不变。没有发现超出声明修复范围的运行期改动。见 `r2-to-r3.patch`、`independent-audit.json`。

尚未证明的现场假设

| 输入或边界 | 本轮证据及限制 |
| --- | --- |
| 首次 native state/type/table/cursor | state 和表从官方映像读取并比对运行 body。type0/4/9、游标 2/6、1..7 与 8..13 是覆盖输入；真实首次 H01 的游标值域没有现场证据。后者直接影响本轮 P1。 |
| 视图栈与构造 | 固定 part2、父 tag32、API 参数由模型提供；清栈后 count=1 的 tag33 push 执行官方指令片段，未执行完整图形和物理按键流程。 |
| 堆、任务栈、IRQ、native 边界 | host 堆为固定范围，PSW=0xC1、context=0、language=0、SD ID={1,2,3,4} 为替身。目标已知保留分配量为 83,216 B，退出不立即释放，不等于实际空闲堆或整个 UI 任务栈余量。 |
| 时钟与秒表 | tick、wrap 和耗时值为合成输入。实际 tick 单位、频率稳定性、睡眠行为、首次屏幕可见到取起点的延迟及按键反应误差仍待现场量。 |
| 掉电、I/O 与恢复 | RAM reset+保留 host 文件模拟冷启动；没有真实断电、卡 I/O、并发 IRQ、watchdog、LCD 或 Stage2l 恢复验收。不能把主机通过等同于相机通过。 |

认可的卡片准备和六步操作

当前 SHA 不获准执行探针步骤。以下是认可的流程，须先解决 P1，并对修复后的新 SHA 独立复审。不得把本件改名当作新件。所有步骤均由用户在本次主机审查之外操作。

卡 B 路线：先在电脑备份并移出卡根的产品 GXRCE.DAT/OK/CTL、v3.4c 机身更新文件、用户所述 28 个官方文件及其它实际存在的固件更新文件。需要隔离的文件族包括 `ilaunch*、jlaunch*、klaunch*、l06firm*、l08firm*、nlaunch*、qlaunch*、DEEPTBL*`。不要只在卡根改名。把 GXRBX0/1.BIN 也备份并移出，避免旧轮次混入。照片目录保留，不格式化，卡 A 不动。本轮未读取当前卡 B，28 个文件的现状来自任务说明。

备用卡路线：使用已能被相机识别的备用 SD 卡。先备份其原内容并移走上述产品文件、固件更新文件和旧 GXRBX 日志；探针测试只用这张卡，卡 B 整张另存、不参与。结束后继续用已移除探针的备用卡核对 IROM 基线；卡 B 仍带旧产品 DAT 时，不把插回卡 B 当作自动回退步骤。

1. 关机，保持 50mm 连接，按所选路线准备卡片，确认照片和卡 A 保持原样，所选卡根没有产品 DAT/OK/CTL、机身更新文件或旧 GXRBX 日志。
2. 暂不放探针，用普通电源冷启动，打开 ADJ 的 Image Settings，只观察后按 MENU，记录原产品表现和新日志，再关机。把这两份基线日志备份并移出卡。这是回退基线，不能仅凭原卡上有 114 DAT 就认定 IROM 已装 114；不要按刷机组合键或 Fn2。
3. 只把新一轮独立复审批准的探针 GXRCE.DAT 放到所选卡根，核对该轮批准的大小和 SHA，安全推出卡；保持 50mm，普通电源启动，打开同一页。本报告开头的 r3 文件不满足这个批准条件。
4. 看到 P0 REF 就启动秒表，留在页内约 10 秒，按 OK 同时停表，记下实际秒数。若中途退出、休眠、掉电、首次显示失败或出现 RESTART，关机，备份并移出本轮日志后冷启动重来，丢弃本轮秒数。
5. 重开同一页，按住向下；不连发就逐次点按。经过四档 CHECK，直到 P0 LUT17 DONE。记录 REF DT，确认 SAMPLES 48/48 hex 即 72 条、ERROR 00000000、FLUSH 00000001 后按 MENU；任一项不符就不用本轮结果。
6. 关机，把两份 GXRBX0/1.BIN、REF DT 和实际秒数一起交回主机。先选最高黑匣子代次再判完整有效，最新无效时不采用旧 DONE。移除所选卡根的探针 DAT，确认没有另一个产品 DAT，再普通电源冷启动核对第 2 步基线。旧产品 DAT 留在电脑，不自动放回；备用卡路线继续用备用卡回退。卡住先关机移走探针；仍不能恢复时沿用既定卡 A Stage2l、50mm、“+ & playback”机身恢复路线，本轮未重测。

主机可用本目录的保守双槽读取器处理已复制到电脑的本轮日志。例如屏幕 REF DT 为 00002710，秒表实际为 10.12 秒：

```sh
/usr/bin/python3 -I -B research/review_lut_p0_r2/decode_pair.py /电脑副本/GXRBX0.BIN /电脑副本/GXRBX1.BIN --seconds 10.12 --ref-dt 00002710
```

可重跑证据与冻结

所有 Python 均使用 `/usr/bin/python3 -I -B`。原始编译命令、stdout/stderr 在 `run/commands.jsonl` 和 `run/logs/`。两个审查脚本开发错误已修正：观察器最初漏识别服务侧 es_ui_abort 名称；差异清单最初漏列了配套 audit.py。原错误保留于 `dev-errors/`，没有把它们当作候选缺陷，也没有改变冻结基线。

```sh
/usr/bin/python3 -I -B research/review_lut_p0_r2/run_review.py build verify native_evidence audit replay seed_replay
/usr/bin/python3 -I -B research/review_lut_p0_r2/run_adversarial.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/run_sanitized.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/run_edges.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/check_decoder.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/test_pair_consumer.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/audit_independent.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/independent_kernel.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/run_mixed_loader.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/artifact_audit.py
/usr/bin/python3 -I -B research/review_lut_p0_r2/guard.py
```

初始和封存均哈希核对 9,495 个输入，覆盖六个指定 firmware 树、原审查目录、114 审查依据、官方文件与已有卡备份输入。指定树还检查新增和删除；共享下载只核对初始已列项，不纳入并行新增资料。decisions.tsv 明确排除，不作为输入，也不进入摘要。未读取或写入 research/emulator_feasibility_r1。冻结结果见 `protected-inputs.json`、`frozen-verification.json`；`SHA256SUMS` 覆盖本目录除自身外全部文件。
