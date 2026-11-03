可以刷

本判定只放行下列 SHA-256 对应的 v3.10 机身，刷写时卡上不放 DAT；刷完后可继续无 DAT，或使用指定 g155b release。当前 g155b test DAT 不能上卡：有一项尚未关闭的 P1，未知拍摄模式没有按 ABI 拒绝。机身 P1 为 0，DAT P1 为 1。

官方恢复在声明 AA 参数输入的模型条件下通过。这里证明的是从可执行的 v3.10 MAIN 进入原厂更新路径、写回官方 MAIN，并用实际最终 NAND 新建普通冷启动。没有证明 MAIN 已损坏、无法进入更新页、掉电或坏 NAND 时仍能自行恢复，也没有实机刷写或实机恢复结果。

## 冻结对象与包路径

| 对象 | SHA-256 |
| --- | --- |
| v3.10 ilaunch3，3,993,340 B | `a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8` |
| resident.bin，7,968 B | `92307253c5e634a9553955757862ffe18fa24648040acb1c7b8920cae5393ec4` |
| g155b release DAT，86,632 B | `1df64437d83629627fd4ba513b2988a014114f22cf5b184f7347f5437073bcfc` |
| g155b test DAT，89,544 B | `466bf5b7b523321f804700fc93fb6d53efccfe4006421b5ad462e0da222a1f56` |
| 官方 gxr-151.zip | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |
| 官方 MAIN | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |

resident build 为 `c1ab47ee43436ceca0a252184201f4e2e93ab04d81e56c47a1ae8e2274e686f5`，ABI 为 `7e565c859676937eda68a4b8d0c63b05`。

实际批准的 release 路径是 `firmware/package_v310_g155b/local/SD_ROOT`。题面所列旧 `package_v310_g155` 的 DAT 为 `308c7096…`，旧 test 为 `a1e731f1…`，均不是题面给定的 g155b DAT。四份包的机身相同，但不能把 DAT 判定按近似目录名互换。完整比较见 [static.json](evidence/static.json)。

输入冻结自前一轮保留，共 2,992 个文件、4,034,181,832 B。重启后先用 `ps` 确认没有本复审或模拟器残留，再核对 APFS 卷 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。恢复时的冻结核对变化为 0，见 [resume-preflight.json](evidence/resume-preflight.json)。最终稳定性与清理收据见文末。

## 逐项判定

| 项目 | 判定 | 独立核对及证据 |
| --- | --- | --- |
| v3.10 机身，无 DAT 或指定 release | 可以刷，限本文范围 | 机身重组、严格重链、官方校验函数、批量版冷启动和恢复链均有独立结果。 |
| 当前 test DAT 自动套用 | 不能上卡 | P1-01 未关闭。见 [C](evidence/mode-contract-c.json)、[Python](evidence/mode-contract-python.json) 和 [实际 DAT 绑定](evidence/qualification-binding.json)。 |
| v3.9 到 v3.10 的全部差异 | PASS，静态 | 421 段、7,524 B 全覆盖，无多报或漏报。校验 3 B、resident 与对齐 7,491 B、旧九分支位移 18 B、新三分支 12 B；逐段核对前后 SHA 和目标。见 [static.json](evidence/static.json)。 |
| 原厂到候选机身重组 | PASS，静态 | 从官方 MAIN、严格 ELF 的 resident/root/pins 和 12 个分支重新组合，最终逐字节等于候选 ilaunch3。头部只变校验字段。 |
| 28 个伴随文件 | PASS，包字节 | 四包中的每个伴随文件均与官方 ZIP 成员逐字节相同。见 [static.json](evidence/static.json)。 |
| 官方头部与内容校验 | PASS，实际函数 | 官方 `0x20087AF0` 对全部 3,992,828 B 数据计算；C/Python 均得 1,786,707,659，等于头部。原厂比较分支对相同值返回 0，对一位差异返回 -1。见 [C](evidence/candidate-checksum-c.json)、[Python](evidence/candidate-checksum-python.json)。不把短函数结果称为实体安装完成。 |
| resident 固定窗口 | PASS，真实重链 | 原严格 linker script 重链，bin 逐字节相同；代码止于 `0x2005468C`，到 root 有 116 B，扣 24 B 保留后剩 92 B。没有新增窗口外段或遗留重定位。见 [strict-link.json](evidence/strict-link.json)。 |
| DAT 身份门 | PASS，实际函数与控制流 | 两新 DAT 在 v3.10 接受，在 v3.9 返回身份错误 8；g154/g153/diag 在 v3.10 返回 8。测试时未映射 DAT 可执行代码；另查 loader 在头部通过之后才分配、完整验证并调用入口。见 [C](evidence/native-checks-c.json)、[Python](evidence/native-checks-python.json)。 |
| 无 DAT 首次及后续待机 | PASS，批量版 | 三单元均用独立空 FAT16 卡新冷启动，并用 ADJ 开关产生后续 32→5；各只有一次首次锁存，后续无固定字写、无 BOOT 和颜色写。见 [MOUNT](evidence/nodat-mount-empty-r2-batch.json)、[28mm](evidence/nodat-28mm-empty-batch.json)、[50mm](evidence/nodat-50mm-empty-batch.json)。 |
| release 的 BOOT | PASS，批量版 | MOUNT 新冷启动只执行一次 op 257，返回 RV_PASS/RV_UNSUPPORTED；颜色 W/T 为 0、BOOT S 写为 0、保护字为 2。见 [重启后独立补跑](evidence/release-mount-resumed-batch.json)。release 的该分支不含自动套用代码。 |
| 坏记录与跨单元门 | PASS，保留轨迹及字节核对 | 原任务独立 CRC/跨单元门的记录来源、最终 DAT 和零写收据可复核，未把旧 activity 提前拒绝当成记录门通过。见 [原 CRC 结果](../v310_body/fix/evidence/gate-bad-crc-acceptance.json)、[原跨单元结果](../v310_body/fix/evidence/gate-cross-unit-acceptance.json)。本轮未重跑全部完整冷矩阵。 |
| test 正常目标、首次菜单 | PASS，限定模型层 | 本轮独立重跑 MOUNT Look 完整冷事务，552 B、九行、单元 T、S 均等于目标，清 DIRTY 后正常返回，后续 32→5 不重复 BOOT/W。另对五组实际首次菜单快照重查完整颜色与高亮字形，C/Python 重跑原厂字形转换。见 [独立冷事务](evidence/valid-look-mount-batch.json)、[最终快照核对](evidence/final-behaviour-checks.json)、[菜单 C](evidence/menu-verify-c.json)、[菜单 Python](evidence/menu-verify-python.json)。五条完整 GPIO 到首次菜单轨迹来自保留运行，本轮未全部重跑。 |
| H52 的处理时合同 | PASS，实际入口 | DIRTY/GUARD 为 14 时取消 raw 13/14，成功后字为 2 时续接；按键入队时刻不参与本项判定。C/Python 实际入口均核对。见 [C](evidence/native-checks-c.json)、[Python](evidence/native-checks-python.json)。 |
| 错误 DAT 后冷启动的快门入口 | PASS，至 C01 续程 | 保留错误事务的真实脏状态与六次取消已核对；新的无 DAT 冷启动实际 GPIO HALF/FULL 都续接，另各用 C/Python 重放。见 [GPIO](evidence/cold-reset-GPIO-keys.json)、[C](evidence/cold-key-replay-c.json)、[Python](evidence/cold-key-replay-python.json)。完整照片仍未验收。 |
| MY1/MY2/MY3 与 pending | 部分 | 从实际冷资格输入作主机变体，MY 为 1/2/3、未知 255、pending 非零均拒绝；实际 MY1 冷流程在未声明单元 slot 72 前结束，未到首次待机。未知拍摄模式的独立问题列为 P1-01。 |
| S 非纯 04 | PASS，批量版声明设置输入 | 保留同一有效记录与 DAT 配对，只将原厂支持的 selector 从 1 改为 3 并重算块校验。实际 BOOT 前仍为 3，其他资格成立；BOOT 一次正常不适用并返回，完整 S、参数 T 不变，颜色 W/T=0、保护字=2、inflight=0。见 [完整冷启动](evidence/non-pure03-mount-batch.json)、[最终核对](evidence/final-behaviour-checks.json)。不是实机或手动保存所得输入。 |
| SD 长响应修正 | 有依据，限声明模型 | C/Python 实际原厂收集器和容量公式对 32/64/128 MiB 均得到正确容量；旧排列均错误。只改 CMD2/CMD9 的设备响应寄存器排列，不改原生容量、文件 API 或返回值。见 [C](evidence/native-checks-c.json)、[Python](evidence/native-checks-python.json) 和 [外部来源](evidence/primary-sources.json)。 |
| 官方恢复的两条声明 AA 收尾 | PASS，批量版 | 两条实际 7B 检查点、相同两项模型和精确独立 SD 副本续行，T 提交与组件结果均为 0，有成功页返回；独立尾段的新三入口计数为 0。全 resident/全部替换点的零计数另从保留全程收据独立读取，见 [覆盖范围说明](evidence/final-behaviour-checks.json)、[官方](evidence/official-tail-exact-up-batch.json)、[v3.10](evidence/v310-tail-exact-up-batch.json)。0→7B 前段未独立全程重跑。 |
| 最终 MAIN 与普通冷启动 | PASS，实际 NAND 字节与批量版 | 从本复审收尾的 NAND 页、布局和 remap 重组，官方字节只用于比较；两份均完整等于官方。全部 NAND 页与两个新建机器冷启动种子一致，状态依次 0→2→32→5，T 参数也逐字节等于实际 NAND。见 [独立读回](evidence/independent-recovery-readback.json)、[官方冷启动](evidence/recovered-official-batch.json)、[v3.10 冷启动](evidence/recovered-v310-batch.json)。 |
| 空 T 参数块 | OPEN | 原厂和 v3.10 都完成 MAIN 写回，但最终 T 提交拒绝 FF，不能称整个更新正常结束；C/Python 实际入口均重现。不能把新 MAIN 可开机等同恢复程序完整成功。 |
| 修正后的 v3.9 完整恢复对照 | 未加做，不阻止本次限定判定 | 本次直接核对的是 v3.10→官方与官方→官方，初始 MAIN、最终字节、成功收尾和冷启动都有来源。缺少 v3.9 对照使本报告不能声称修正模型下三方全程等价。 |

“零写”在开机行为行指颜色 W、单元 T、BOOT 对 S 的写入及 DIRTY/GUARD，不指 CPU 初始化没有 RAM 写，也不包括原厂固有的设置处理。恢复讨论中的 T 参数区是 NAND block 41 的 16 KiB；颜色事务中的单元 T 是 RPC 状态字，两者不是同一数据。

## 恢复前提与 SD 模型

声明输入来自原厂普通 MAIN 生成的 BB 模板，只改首字节为 AA，其余 16,383 B 及原校验字段不变。本复审核对了唯一字节差异、实际读取 SHA、原厂重算校验以及 NAND 写回；原输入校验字段为 0，最后由原厂写成 38,842,654。AA 输入 SHA 为 `d22aaf7ec9cba5607e70b09a74bc24cb9511b8baad78759d1f9b2861fa8f6529`，最终参数 SHA 为 `72b0573727a6b72c58adef53e3586d9f98552873565b33d21f8ea3017398507b`。见 [输入来源与最终数据](evidence/retained-receipts.json)。

这个输入足以核对 AA/55 标记允许的提交分支，不能称为实机校准转储，也不证明与任意出厂参数等价。它在 7B 检查点只改变 NAND，未改变原生寄存器或 RAM；没有重跑带该输入的整个开机前段。恢复程序确实会读写 T 区，故“恢复不碰参数区”不成立。空块失败也是原厂对照的共同结果，未显示 v3.10 新增了这一失败。机身放行沿用当前可正常运行 v3.9、原厂参数完好的使用前提；T 已损坏或无法进入更新页时不能承诺此法修复。

共同终点 `0x2005CCF0 / -1` 本身不表示成功。成功按实际 T 提交、全部组件返回 0、成功页返回以及最终 NAND 分开判定；原有保护退出和空块失败没有改写为 PASS。AA 模板只供模拟器使用，不是机主刷写文件；升级和恢复卡仍只放已登记的 29 个文件。

SD 修正不是把容量写成某个期望常数。原厂读取修正后的响应寄存器，自己算出实际容量并继续 CMD18/DMA；三个不同几何、两后端均核对。Renesas SDHI 的 R2 位段及 Linux tmio 的八位重组提供独立支持，但 GXR 控制器身份和实体时序仍未验证。两份恢复虚拟卡用两套 FAT 各自重组全部 29 文件，均与官方相同；保留的 FAT entry 2059 差异没有改写。见 [recovery-media.json](evidence/recovery-media.json)。这些结果不能代替 FAT32 实卡或实体 SD 控制器验收。

## P1-01：test DAT 未拒绝未确认的拍摄模式

位置为 [boot_adapter.inc.c](../../firmware/engine_v66_g155b/candidate/containers/product/boot_adapter.inc.c) 第 2 至 13、38 行。`boot_mode_known()` 只检查 MY 与 pending 两个字节；实际模式 `0x205D9A7F` 只写入诊断变量。`eng_boot_check()` 没有按该字段或其他已证原厂选择结果限定允许模式。

[ABI.md](../v310_resident/ABI.md) 第 13 行明确要求未知模式或类别未确认时，在颜色写和 DIRTY 前返回不适用，且 MY=0 单独不足以启用。本复审从实际有效冷启动资格输入出发，分别只将该模式字节改为 127、255；C/Python 都仍返回 1，步骤数与基线同为 1,233。作为控制，MY 字节改为 255 会返回 0。该快照内全部 89,544 B DAT 与最终发布文件在唯一声明重定位后逐字节一致。

这是主机层的资格合同反例，没有证明实机拨盘会产生 127 或 255，也没有观察实机误写。它说明当前代码没有所要求的未知模式拒绝门。其最坏后果是其他条件恰好满足时，在尚未确认适用的拍摄类别中进入颜色/S 事务。因此阻止 test DAT 上卡，不阻止无 DAT 或 BOOT 关闭的 release 机身使用。

最小修正只在 DAT：依据原厂实际选择路径建立已证允许模式集合，资格检查与事务中的复核使用同一规则；不能确认的值正常跳过，W/S/T、DIRTY/GUARD 均为 0。集合尚不能证明时保持自动套用关闭。关闭条件是新 DAT 的实际代码在 C/Python 上拒绝这两个反例，保留普通模式成功用例，并核对 MY/pending 与真实选择路径。不能仅删除 ABI 中的要求。

## 机主步骤与 P2

[OWNER_STEPS.md](../v310_body/OWNER_STEPS.md) 的 28mm→MOUNT→50mm 顺序、刷写时不放 DAT、50mm 上用官方 1.51 恢复、不格式化，以及将运行故障时的退回和写入阶段分开处理，方向正确。本轮只批准机身阶段和指定 release，不批准稿中第 6 至 8 步的当前 test DAT。

P2-01：第 3 步和恢复段没有写出官方说明的两键保持时间，也没有把自动结束的正常终点写清。按字面短按播放键，可能只进入普通开机/播放，机主会把未进入确认页误判为恢复失败。最小改稿为“同时按住 + 与播放键 2 至 3 秒，直到出现升级确认页；Fn2 选 Yes，MENU/OK 开始；保持电池和卡连接，等待相机自动关机并重新开机”。本轮下载的 [官方 PDF](local/official-gxr-update-manual-cs.pdf) 第 5 页及 [提取收据](evidence/official-manual.json) 直接支持这些步骤。此项不改变机身字节判定。

各阶段的失败处理应明确如下，且本复审不执行任何设备步骤。

1. 文件不齐或 SHA 不符时不进入升级。只使用本文指定 release 路径及机身，恢复卡使用官方完整 29 文件，不混放 DAT/CTL。
2. 未出现升级确认页时不继续按 MENU。先核对两键保持时间、文件和单元；仍失败就停下保留画面。
3. 按 MENU 开始写入后保持电池与卡连接。运行期“拔电池 10 秒”的退回办法不能用于写入阶段。更新未正常结束时保留画面并停止后续单元，不格式化。
4. 每个单元完成后，先无 DAT 普通开机、查原厂菜单和普通拍照、再关开一次。任一步异常就停止后续单元；可进入更新页时按官方完整包恢复。
5. 当前 test 阶段不执行。将来 DAT 另获放行后，运行期出错才按稿中办法正常关机、移走 DAT，再无 DAT 冷启动检查；无法正常关机时的电池退回只适用于该运行阶段。
6. 官方恢复完成后仍须无 DAT 检查取景、原厂菜单和拍照。无法进入更新页或不能正常收尾时，本报告没有下一步自行修复保证。

## g155c 的增量复审

机身不变时不用重做全机身差异审查，但须先逐字节确认 ilaunch3、resident、build、ABI 和 28 个伴随文件仍为本报告对象。DAT 改动必须绑定新的完整 SHA，不能继承当前 test 的许可，因为当前 test 本来就未获许可。

- 先关闭 P1-01。保留未知模式、MY1至MY3、pending、activity、state 和非纯 04 的独立拒绝证据；不能用另一道提前失败替代被测门。
- 对“关机后微调丢失”核对真正的原厂保存路径：手动调整、确认、退出、正常关机、从实际持久字节冷启动，比较 40 B 记录、CRC、DAT 配对、十项 levels 和最终完整 552 B。只在 RAM 中记录或换一份声明设置输入不算关机持久化通过。
- 检查不同单元、内置/Look/用户条目、坏 CRC、旧 DAT 配对、未知记录以及相邻字节；release 仍须不支持 BOOT 且零写。
- 重验 BOOT 一次、首次八行与高亮、无重复套用、成功清 DIRTY/GUARD、错误补偿失败的 H52 取消，以及移走错误 DAT 后的新冷启动 HALF/FULL 续程。完整照片仍需独立验收。
- DAT 长度/BSS 变化后重新链接，核对普通及 `R_M32R_GOTOFF_SLO` 重定位、代码/内存上限和 Studio 原样读回；不能只修改包内 DAT 后沿用旧链接结论。

## 方法、偏差与未验收边界

本复审不改实现、包或 tools，不写 Git，不使用子代理，不访问相机或存储卡。结论所用整机运行采用原 `gxr_emulator_batch`/`gxr_emulator_standby`，保留实际 library SHA 和模型源码 SHA；快速后端的早期完成、失败和中断结果均不作为结论依据。[ADOPTION.md](../review_emulator_fast_r1/ADOPTION.md) 的限定范围保持有效。

`batch_extra.py` 共用驱动的顶层 `backend` 字段仍保留参数默认值 `native`；该参数没有选择本轮实际后端。实际执行模块在 `extra.actual_backend_module`，均指向原 standby，library 为 `018a6d97…`，`native_stats` 为 null，另有明确的 `native_machine_used=false`。见封存的 [后端来源汇总](evidence/backend-provenance.json)，不能只看该参数字段判断用了快速后端。

T3 重启前完成且有终点的收据保留；原生恢复的资源停止、模型组合不符而停止的参考续行、主机设置失败均不计 PASS。新的恢复从原批量版、相同模型组合的完整检查点开始，未把不同组合的快照混用。仅调试的输入变体和按键释放变体单列，没有替换原始结果。

早先“非纯 04”夹具使用 selector 2，实际被 MAIN 归一成 1；其两个 300M 预算终点没有测到预定门，也不说明事务卡死。该输入及结果保留，正式结论采用 selector 3 的新完整冷启动。菜单首次整份 DAT 比较还发现正常变化的 `t_seen` 四字节；重查 ELF 后，只将该字按实际单元 T 规范化，其余 DAT 全字节仍须相同，未扩大例外范围。

可从项目根验证和复跑下列函数检查。复跑接口只改变收据输出与私有临时目录，保留原输入、原 CPU、原断言和原指令；原封存收据不会被覆盖。每次使用新的 label，并遵守同一卷与两进程限制。

```sh
shasum -a 256 -c research/review_v310_body_r1/SHA256SUMS
nice -n 10 /usr/bin/python3 -I -B research/review_v310_body_r1/rerun_functions.py --kind mode --backend c --label independent-r1
nice -n 10 /usr/bin/python3 -I -B research/review_v310_body_r1/rerun_functions.py --kind mode --backend python --label independent-r1
```

后两项应得到 `CONTRACT_FAILURE`，四个资格结果依次为 `1, 1, 1, 0`，这是本报告 P1 的可复现反例。也可按同一接口选择 `menu`、`native`、`checksum`、`key` 重跑相应函数层。

本轮曾让两个短检查与两个在跑任务短暂重叠，最多四个复审 Python 进程，违反两进程上限。重叠的菜单检查、读回及非纯 04 运行被排除，原字节保存在 `local/overlap-excluded/` 或原用例名下；重跑由替换自身 PID 的 [review_launch.py](review_launch.py) 检查上限，nice 为 10。过程见 [process-limit-deviation.json](evidence/process-limit-deviation.json) 与 [process-allocation.jsonl](evidence/process-allocation.jsonl)。这项执行偏差明确保留，不声称全程从未超限。

未运行的设备边界包括 ROM loader、MAIN 损坏或掉电后的启动、实体 NAND 坏块/ECC及校准参数、FAT32 实卡、真实 RTOS 时序与单元业务、实体 LCD/按键、完整照片、连拍/自定时、真实 MY 冷启动，以及真实关机对设置的持久提交。主机、包字节和模型通过不替代这些验收。

最终核对 2,992 个冻结输入，变化为 0；Scratch 临时目录已删除，复审运行残留为 0。见 [inputs-after.json](evidence/inputs-after.json)、[cleanup.json](evidence/cleanup.json) 和 [介质保留清单](evidence/review-media-retention.json)。SHA256SUMS 覆盖冻结输入及本复审全部交付文件，自身除外。封存时间为 2026-11-03T05:24:29.805362+00:00，在本轮 2.5 小时时间盒内。

机身可以刷，限无 DAT 或指定 release；test DAT 不能上卡；P1 数量 1，属于 DAT；临时目录已清理，残留运行 0。
