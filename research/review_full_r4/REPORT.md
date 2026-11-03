不可以上卡

阻断原因是更换条目后保存微调会停用引擎，见 R4-01。你接受的 full-r3 F02 限制单独保留，不作为新增阻断。

审查对象为 `firmware/full_r4/local/card_update/GXRCE.DAT`，generation 106，59,516 B。SHA-256 已从文件重算：

```text
f874b5cd3da3dd1af749bf759a5e94e574886f55200cb61e6f2ea39cc0db971e
```

P1 · R4-01：旧 GXTS 文件使三条目的首次新保存失败，并停用扩展。

具体场景：full-r3 在 50mm 01、02 或 Mount 01 保存过微调，留下 A，或 A/B 两份；按题设删旧 OK、替换 DAT，成功装入 106。旧微调绑定不匹配，浏览和冷加载确实回到默认，面板也没有 SaveFail。但随后正常调整 Cont 并按 OK，若原生 rename 拒绝已存在目标，TMP→A 返回 -1，保存返回 `RV_UNCERTAIN=-8`，resident 进入 `RV_DISABLED_UNTIL_REBOOT=6`。重启后再次保存仍失败。三条目、单 A 和双副本均已复现，无须注入读写错误。

根因在 [gxts.c](../../firmware/engine_fix_r2/containers/product/src/firmware/card_container_v2/gxts.c) 85 行和 [gxts_io.c](../../firmware/engine_fix_r2/containers/product/src/firmware/card_container_v2/gxts_io.c) 56–83 行：两份旧绑定都被视作 MISSING，`have_old=0`，选择 A，又跳过删除正式目标；文件实际仍存在。[panel_store.c](../../firmware/engine_fix_r2/containers/product/src/firmware/engine/panel/panel_store.c) 408–415 行把 rename 失败锁存为 uncertain；[adapter.c](../../firmware/engine_fix_r2/containers/product/adapter.c) 241–244 行返回 FAULT；[resident.c](../../firmware/resident_v32/resident/resident.c) 38–45、70 行停用引擎。

停用时，刚才预览的 408 B 原生配方行仍保留，没有恢复已提交值；原生菜单则恢复到 7 行。本轮没有观察到菜单卡死。见 [50mm 01](local/logs/case-binding-one-0.log)、[50mm 02](local/logs/case-binding-slot2-one-0.log)、[Mount 01](local/logs/case-binding-one-2.log) 和 [双副本](local/logs/case-binding-both-0.log)。前后 GXTS 正式文件逐字节相同。

这是继承的存储逻辑缺口，由 full-r4 的三处绑定变化引入新的正常升级触发条件。必须先证明旧绑定文件存在时仍能安全保存，且失败能恢复预览，再复审。仅删除 GXRCE.OK 不能解决它。

P2 · R4-02：卡流程不能涵盖两份都残缺的 IROM 状态。

具体场景：A/B 都存在，但各只保留 full-r3 的前 1,024 B。清理卡 DAT/OK 后复制 106，菜单可正常运行，安装却返回 `RV_VERIFY=-6`，没有写入，DAT 也没有变 OK；此时移除 DAT，扩展无法加载。三个单元均复现。单独 A 残缺、单独 B 残缺及遗留 TMP 都能成功安装。

依据为 [panel_store.c](../../firmware/engine_fix_r2/containers/product/src/firmware/engine/panel/panel_store.c) 167–179、296–303 行：没有有效副本时，两份目标又都已观察到，提交被拒绝。见 [反例日志](local/logs/case-partial-both-0.log)。这是继承的保护行为，说明“失败安装留下任意 partial 状态也足够”缺少前提；该双残缺输入由夹具构造，不是相机掉电读回。

其余主张的核验结果如下。

- 数据范围属实。独立 Python 解码与重新编译的完整产品 C 对两代各 48 槽展开结果一致。指定三条目逐字节等于指定源条目经 slot、49 B identity 和 CRC 重绑定后的值；48 条 64 B 菜单记录全等，其余 45 槽 entry、GXTS binding 全等。50mm 02 标签为 `02 Nega`。Mount 01 无 T1，control=0x0002。三条目的描述符在候选文件偏移 54,380、54,396、54,588 B，详见 [static-results.json](local/static-results.json)。
- 引擎布局变化属实。两代 engine 都为 50,276 B，420 个差异字节全部位于 247 处 type-64 BSS 重定位低半部；BSS 基址下降 188 B，大小仍为 11,172 B。归一化后字节全等，运行时重定位表全等，链接源摘要全等。没有重建或重封装候选。
- 常驻身份属实。候选的 body/build/ABI 共 80 B 与批准 resident ELF 中的 rv_trust 全等，build=`2eea6eb324790b035d37d33395d60880a1909b4e693414a939dee45f96bfbae7`，ABI=`9583fdd751bebc36f3af305595559643`，pins=`DF2BCAF5/6700E6FF/1B3C7000`。批准 ilaunch3 的 SHA-256 为 `05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c`；其文件偏移 31,084 B 起的 7,772 B payload 与 resident ELF 全等。真实 resident C 接受容器，三单元均能初始化。
- 尺寸没有越界。主块 request=78,192 B；M32R 编译对象独立测得 SessionWork=912 B、loader 工作区=608 B。首次安装同时保留两块 64 KiB 缓冲时，计原生头为 209,920 B；若已有 UI snapshot，为 211,900 B。它们是申请量，不是相机连续堆余量。见 [target-layout.json](local/target-layout.json)。
- 卡流程对已装 105、105 从未运行、空卡配空 IROM、仅一份残缺 IROM 均通过，106 可持久化并从 IROM 冷加载。保留旧 OK 且 rename 拒绝覆盖时，确实会在 IROM 提交之后确认失败并停用；删旧 OK 是必要前提。依据为 [mark.c](../../firmware/engine_fix_r2/engine_services/mark.c) 44–45 行及 [对照日志](local/logs/case-old-ok-0.log)。
- 可读 IROM 为单 A=106，或 A=105/B=106 时，有效卡 DAT=105 仍优先运行 105；安装返回 CONFLICT，create/write/delete/rename 全为 0。移除 DAT 后，留 OK 或无卡容器均加载 106。见 [行为结果](local/behaviour-results.json)。这一结论有 F02 例外：持续三次 open(-1) 隐藏 106，且 rename 允许覆盖时，105 仍能覆盖它。本轮用真实 105/106 复现，见 [已接受限制](local/logs/case-accepted-f02-0.log)。
- GXTS 的读取主张成立。三单元各 16 槽都放入两份旧微调，升级后立即读取及冷加载逐槽核对：只有 50mm 01/02、Mount 01 回到默认，其余保留，全部文件未变，没有 SaveFail 或停用。见 [补充结果](local/extra-results.json)。
- 题设所问的同绑定重复保存风险没有复现。full-r3/full-r4 × 三单元各连续保存八次，A/B 都存在后先删除非保留目标再 rename，generation 依次为 1–8，拒绝覆盖语义下仍成功，没有停用。见 [重复保存日志](local/logs/case-repeat-old-0.log)。不能把 R4-01 写成“正常同绑定 A/B 的第三次保存必失败”。

未核实：真实相机 rename 的目标存在语义、物理掉电持久化、M32R 实际执行、堆碎片、按键时序和照片色彩效果。未发现新增 P0 证据；这些主机结果不证明没有变砖风险，也不证明源配方在相机上的颜色正确。

检查脚本只编译主机验证程序和一个 M32R 尺寸对象。产品 C、resident C、候选及 builder 目录的 716 个保护输入未变；decisions.tsv 不参与冻结。未访问相机卡、刷机、安装包、使用子代理或提交代码。全部派生字节、对象和日志均在本目录忽略的 local/。

复核入口只向本审查目录写入；不要重跑 freeze 覆盖起始证据。

```sh
/usr/bin/python3 -I -B research/review_full_r4/review.py inspect
/usr/bin/python3 -I -B research/review_full_r4/review.py compile
/usr/bin/python3 -I -B research/review_full_r4/review.py behaviour
/usr/bin/python3 -I -B research/review_full_r4/review.py extra
/usr/bin/python3 -I -B research/review_full_r4/review.py finalcases
/usr/bin/python3 -I -B research/review_full_r4/review.py layout
/usr/bin/python3 -I -B research/review_full_r4/review.py finalize
```
