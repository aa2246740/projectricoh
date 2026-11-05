可以上卡（release）；可以上卡（test）

仅放行下列完整 SHA 对应的 DAT，在机主先按已批准步骤刷好 body v3.10、无 DAT 普通开机正常后，做有监督的现场测试。release 有 14 条换入记录，BOOT 恢复关闭；test 有 9 条，BOOT 恢复开启。本轮未发现阻止这次现场测试的 P1。当前 Studio 无法读写 g156，不能把本结论理解为 Studio 兼容验收。

本轮没有访问卡、相机或网络，没有改产品、包或既有研究证据。所有新文件都在 `research/review_g156_r1/`。计算使用 nice 15，重计算最多两个进程，审查脚本用两个文件锁限制槽位。开始时间为 2026-11-03 18:36:13 UTC，封存时间为 2026-11-03T19:21:22.846362+00:00，用时 45.2 分钟，未超过 2.5 小时。

## 冻结对象

| 包 | DAT 字节 | 代码字节 | BSS 字节 | 主分配 / 107,612 B | 余量 |
| --- | ---: | ---: | ---: | ---: | ---: |
| release | 88,684 | 65,748 | 9,284 | 105,596 | 2,016 B |
| test | 90,532 | 68,656 | 9,296 | 107,456 | 156 B |

```text
f42b81a854d86b66ee7f65ac0123153c7e54e59d6e3d2079834490771d0ce1e0  firmware/package_v310_g156/GXRCE.DAT
0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7  firmware/package_v310_g156_test/GXRCE.DAT
69fa85104fcb449e613950bb58c802b9b64464769ae524fe3f7303e06093c2ad  firmware/package_v310_g155c/GXRCE.DAT
c3017d3663e9501b43c921e3b46333b74d751eaa170781c4e1a00d90118f0335  firmware/package_v310_g155c_test/GXRCE.DAT
a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8  firmware/image_v310/local/ilaunch3
```

仓库起始 HEAD 为 `7ba9cb4a2d921cd5ad88f037c1e9693323bad05f`，已有其他研究任务的未提交改动，见 [起始状态](evidence/initial_git_status.txt)。包中的 `SD_ROOT/GXRCE.DAT` 与包根 DAT 相同。resident build 为 `c1ab47ee43436ceca0a252184201f4e2e93ab04d81e56c47a1ae8e2274e686f5`，ABI 为 `7e565c859676937eda68a4b8d0c63b05`。DAT 中的原厂 body-source SHA 为 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`，它和待刷的修改后 ilaunch3 SHA 是两个不同字段，均已核对。

## P1

未发现需要先改产品才能做这次有监督测试的 P1。

旧记录有错选配方的实际索引风险，不能靠索引碰巧没变来判断安全。例如 g155c 的 a12-50 索引 `0x42` 原来表示 Tri-X 400，在 g156 release 的全局 Look 表中已经表示 HNCS HiCon。当前记录格式把 DAT 头部两项 CRC 放在 40 B 记录的 28..35 字节，随后校验完整 40 B。g155c 与 g156 的 CRC 对已经不同，所以旧索引不能在新表中冒充当前配方。

最终 DAT 的 `memory_build` 原 M32R 指令在纯 Python 指令后端处理了 33 份有效 g155c 设置记录，分别对两包检查，共 66 次，全部与 g156 应有记录不相等。`eng_boot_run` 在 `memory_decode` 全记录相等检查通过之前不会调用颜色写事务。另用原 g156 reference 已成功恢复的 4096 B 设置作对照，只换成同单元、同索引、同非零档位的有效 g155c 记录，并重算设置校验和。新的 Python reference 冷启动确认单元 W 为 0，9 行与 T 重建的完整 552 B 是原生 04，Standard/WB 归零条件正常，首菜单档位为默认值，旧 40 B 原样保留。见 [配对指令检查](evidence/instructions.json)、[仅换旧记录的夹具](evidence/old-record-fixture.json)、[独立冷启动](evidence/review-old-g155c-reference.json)。

因此这里的拒绝是“忽略旧记忆并保持原生默认颜色”，不是清空那 40 B，也不是把旧档位迁到新配方。包括未改配方的 28mm 在内，旧包记忆都会因全 DAT 的 CRC 对改变而失效。release 和 test 之间切换也会使记忆失配。机主若要保留旧微调值，先记下它们，再在最终选用的 g156 包中重新设置并保存。

## P2

### P2-01：当前 Studio 拒绝 g156

反例可直接复跑 `static_audit.py`。两份最终 DAT 调用当前 `studio/src/gxr_studio/camdata/datcodec.py:198` 的 `parse`，都抛出 `UnsupportedGeneration: 代数 156 未登记`。`PROFILES` 在第 102 行只登记到 155。

只在内存中新增一个 generation=156 的 Profile，解析器仍抛出 `DatError: 配方库头、CRC 或代数不合格`。原因是 g156 保留了 g155c 的 bank 段，而 codec 第 316 行把 bank 头中的代数与外层 Profile 代数绑定；pack 第 657 行也按外层代数写 bank。支持 g156 时必须明确处理这两个代数的关系，并用这两份实际 DAT 证明 parse/pack 逐字节往返、原生 04 和 pin 不变。仅添加 Profile 不足以修复。

这不影响相机加载本次固定 DAT，当前 C gate、semantic 和 UI-extension parser 对两包三单元共 6 例均通过；最终 M32R 代数门也通过。此轮不能使用 Studio 编辑或回写 g156，也不能把外层代数改回 155 绕过拒绝。codec 结论来自模块主机调用，未启动 Studio 服务或界面。见 [静态反例](evidence/static.json)、[当前 C 解析器](evidence/parsers.json)。

### P2-02：既有关闭回执没有覆盖“每条配方 × 两种关闭”

六条正常流程确实逐条覆盖所有换入记录的选择、完整 552 B 读回、光标和 DISP；OK/ADJ 是每条流程各关闭一次。具体反例是 `r4-reference-release-mount-flow.json` 中 05 F-CC 的检查只有该条读回、光标和 DISP，`OK_close` / `ADJ_close` 位于顶层，不能据此说这条配方分别经过两种关闭。

本轮另从冷机对 release/50mm 的 03 HC BW 和 Tri-X 400 各做 OK、ADJ 关闭，并在重新打开菜单后核对完整 552 B、实际单元行和 T，均通过。它补了两条改动黑白配方的原生模拟证据，不能替代其余条目的逐条 reference 交叉验收。现场检查单要求对每条实际换入配方分别关闭一次，补这个范围。见 [本轮抽样](evidence/runtime_samples.json)。这项是覆盖范围限制，未复现颜色或关闭故障。

## P3

### P3-01：包内说明仍停在旧验收状态

两包 README 第一行仍是“有缺陷”，MANIFEST 的 `status` 仍为 `ACCEPTANCE_INCOMPLETE`，`acceptance_verdict` 为“有缺陷”，主机覆盖数组为空。当前九条 reference 回执与这些文字不一致。它们是被冻结的旧说明，不是本次查到的新运行缺陷。正式交付前应同步说明、MANIFEST 和各自校验清单；本轮没有改包，放行只按本文完整 DAT SHA 和新审查证据识别。

`adapter.c` 中诊断用 `ig_engine_version` 仍为 `g155c`，`G155_BOOT` 也保留旧宏名。它们不是 build_number 准入门。不要仅靠诊断字符串区分这次包。

### P3-02：test 仅余 156 B

按 `7,628 + align4(DAT长度 + BSS长度)` 独立重算，test 主分配为 107,456 B，满足 107,612 B 上限。余量真实但很小。它不是当前越界；任何增加记录、重新打包或改编译产物的结果都应重新核算，本文不放行另一个 SHA。

## 代码与记录核对

用户的快速判断成立，偏移以 engine.bin 起点为零。若按 DAT 文件偏移表示，需加 0x100。

| 项目 | release | test |
| --- | --- | --- |
| DAT 增长 / BSS 起点后移 | +1,972 B | +912 B |
| ELF 的 BSS HI/LO 重定位 | 584 处，其中 292 个低半字改变 | 626 处，其中 313 个低半字改变 |
| 其余指令变化 | 0xffc、0x9f5c、0xa3a0 | 0x11ec、0xaab8、0xaefc |
| 三处变化内容 | `add3 …,#-155` 改为 `#-156` | 同左 |
| 其余代码差异 | 0 | 0 |

重定位表、bank、tweak 和用户/UI 数据所在的 2/4/5/7 段按段对齐后逐字节相同。源码 C/H/汇编/链接脚本文件集合相同，只有 `gate.c`、`eng_data.c`、`ui_v2_data.c` 中三处 155 改为 156。每一个 BSS 改字都按原 ELF 的 HI_SLO/LO 重定位、旧符号值和新增长量重算；最终 DAT 代码与当前 ELF、engine.bin 相同，BSS 起点等于最终 DAT 长度。未重新编译或链接产品固件，host parser dylib 单列为审查工具。

最终 `eng_data_accept` 原指令对两包 × 三单元 × 155/156/157 共 18 例，只接受 156。UI extension 的严格代数门已改为 156。resident 的 envelope、身份和容量验证不固定在 155；loader 优先试 SD，SD 不可用或被拒后才在 IROM 候选中按有效性及较高 generation 选择。没有发现另一个 resident 的 generation==155 门。`G155_BOOT` 只选择是否编入 BOOT 恢复。

| 记录核对 | release | test |
| --- | ---: | ---: |
| 完整 552 B 精确等于当前 registry 的换入项 | 14 | 9 |
| 未换入且完整 552 B 逐字节相同 | 25 | 31 |
| 未换入且仅身份 CRC 字节 4..7 改变 | 15 | 14 |
| 三单元原生 04 | 全部相同 | 全部相同 |
| 每单元可见内置 / Looks | 8 / 10 | 8 / 10 |

逐项检查了 108 个可见展开条目。所有 Look 的 flags 均等于其对应单元 base slot 的 flags；release 的 50mm 03 HC BW 与 Tri-X 400 成组换入。两包的 9 条起始集合都等于 capacity profile，release 额外 5 条完全对应 registry。当前 registry 与构建封存副本相同，每个被换入 record552 文件也相同。见 [逐项记录](evidence/records.json)、[源码差异](evidence/source-delta.patch)、[静态字节检查](evidence/static.json)。

## 九条既有 Python reference 回执

| 包 / 单元 / 类型 | 回执后端 | 记录或恢复目标 | 独立核对 |
| --- | --- | --- | --- |
| release / mount / 正常流程 | Python-device-reference | 05 F-CC、06 F-CN、M9 STD、HNCS HiCon、Kodachrome25、HNCS LowSat、Vision3 500T | [PASS](../g156/evidence/r4-reference-release-mount-flow.json) |
| release / 50mm / 正常流程 | Python-device-reference | 03 HC BW、07 L-Chr、08 L-Viv、HNCS HiCon、Tri-X 400、Velvia 50、Metropolis | [PASS](../g156/evidence/r4-reference-release-50mm-flow.json) |
| release / 28mm / 正常流程 | reference | 04 Std | [PASS](../g156/evidence/r4-reference-release-28mm-flow-r2.json) |
| test / mount / 正常流程 | Python-device-reference | 05 F-CC、06 F-CN、M9 STD、HNCS HiCon、Kodachrome25、HNCS LowSat、Vision3 500T | [PASS](../g156/evidence/r4-reference-test-mount-flow.json) |
| test / 50mm / 正常流程 | reference | Velvia 50、Metropolis | [PASS](../g156/evidence/r4-reference-test-50mm-flow.json) |
| test / 28mm / 正常流程 | reference | 04 Std | [PASS](../g156/evidence/r4-reference-test-28mm-flow.json) |
| test / mount / 恢复 | Python-device-reference | 非零 [100, 1, 0, 0, 0, 0, 0, 0, 0, 0] | [PASS](../g156/evidence/r4-reference-test-mount-restore-r2.json) |
| test / 50mm / 恢复 | reference | 非零 [100, 1, 0, 0, 0, 0, 0, 0, 0, 0] | [PASS](../g156/evidence/r4-reference-test-50mm-restore.json) |
| test / 28mm / 恢复 | reference | 非零 [100, 1, 0, 0, 0, 0, 0, 0, 0, 0] | [PASS](../g156/evidence/r4-reference-test-28mm-restore.json) |

本轮重新计算了原始 RPC 日志的命令页、游标和每次 W 的地址。允许范围固定为 DAT map 的九行与 T；奇地址行的边缘字节必须与先前读到的半字相同，不能扩大白名单。设置写入仍逐字节限制在原 S 白名单；原厂 body 写入另按实际 PC 与冻结 ilaunch3 代码段核对，没有把未知 PC 一概豁免。三条 release 的冷启动单元 W 都为 0，BOOT 期间 engine/resident 设置写入都为 0。

完整 552 B 读回来自实际单元 peer 的九行与 T，加上容器身份/保留字段重建，另与 g.live 比较。恢复检查使用对应正常流程保存的非零目标，首菜单前后均相同，控件显示同一档位，旧 40 B 经过冷机输入仍保留。两条 reference 正常回执缺少 round/快照标记字段，本轮检查了已保存 driver 的 SHA 和新建 Machine 路径，未仅凭 PASS 或标记认定冷启动。

四条原 Python 设备参考流程接续各自已完成的 reference 冷启动检查点，其余五条为 strict_r2 的显式 reference 新 Machine。为重算原始日志，本轮用限制类白名单的只读反序列化检查既有文件，没有恢复或执行这些机器状态。新抽跑全部从新 Machine 冷启动，没有使用快照。加载的最终 DAT 已逐字节绑定；唯一允许的运行期改字是原有 `t_seen` 4 B 变量，已按 ELF 符号限定，未把它算成静态代码差异。见 [独立回执审计](evidence/receipt_audit.json)。

五条旧 native FAIL/OPEN 已保留，当前 reference 对应业务覆盖已复核；另外两条 r4 reference FAIL 的最终补跑也已核对相同 DAT 与输入/目标。问题分别涉及等待中间态、只读对象序列化和原厂 body 的 S 写入误归类，不是把失败直接改成通过。旧 50mm 的白名单外 S 偏移可逐项找到 body PC；最终 engine/resident 白名单未扩大。这里不声称按每份历史输入重新跑了一次。见 [七条历史项](evidence/history.json)。

## 本轮独立抽跑

| 抽样 | 后端 | 结果与实际范围 |
| --- | --- | --- |
| [review-release-50mm-native](evidence/review-release-50mm-native.json) | native | PASS，七条 release/50mm 换入项的完整读回、光标、DISP、OK/ADJ，W 范围通过 |
| [review-release-bw-close-native](evidence/review-release-bw-close-native.json) | native | PASS，03 HC BW、Tri-X 400 各自 OK/ADJ 关闭，重开后完整 552 B 保持 |
| [review-old-g155c-native](evidence/review-old-g155c-native.json) | native | PASS，旧记录干净拒绝；完整原生 04；W=0；记录 40 B 保留 |
| [review-old-g155c-reference](evidence/review-old-g155c-reference.json) | reference | PASS，旧记录干净拒绝；完整原生 04；W=0；记录 40 B 保留 |

另有一次 test/50mm 正常 reference 重跑在检查预算后主动 SIGINT，中止时只完成了 4 个按键，没有完成换入项验收，未计为 PASS，也未当作产品故障。原始 `KeyboardInterrupt` 回执与日志均保留，见 [中止说明](evidence/reference-normal-interrupted.json)。本轮没有修改固件来消除任何失败。

strict_r3 抽跑使用 `nand-word,preview-link,sd-long-response,nand-read-tail` 四项模型修正，均为模拟假设。完整参考恢复输入为经原逻辑读边界输入的 4096 B 设置；这不证明物理 NAND 写入与断电持久化。

## 机主现场检查

1. 先按既有批准流程刷 body v3.10。取出 DAT 普通开机，确认原生 04、实时画面、快门、保存与回放正常，再使用本文 SHA 对应的一个 DAT。核对卡上最终文件的完整 SHA。这个步骤由机主执行，本轮没有刷机或摸卡。
2. 第一次带旧 g155c 记忆启动时，预期当前颜色保持原生默认，旧微调不会自动搬到新配方。确认白平衡补偿正常、没有半幅或部分颜色被套用。test 的恢复检查沿用已批准的非 MY、原生 Standard 与 WB 归零开机条件；资格不满足时允许干净跳过恢复。
3. 按下表逐条选中换入项。每条先看名称与实际行光标，再切 DISP 卡片并返回，确认名称、光标和颜色对应。分别用 OK 与 ADJ 关闭到正常待机，再重开检查同一配方，留意错误配方、残留色、卡住或画面突变。
4. release/50mm 重点看 03 HC BW 与 Tri-X 400 的黑白是否完整一致，07 L-Chr、08 L-Viv 的高光和渐变有无异常断阶；HNCS HiCon 的暗部与高光有无意外截断。MOUNT 的七条用同场景、同曝光、同 WB 与 g155c 对照，查看中性灰、肤色、高饱和色与高光。电脑预测提升不是实拍颜色保证。
5. test 在最终包中重新保存一个非零微调，普通关机再开机，确认配方、档位、实际画面三者一致，然后用 OK 与 ADJ 各关闭一次，再拍照和回放。只恢复标签或数值、画面仍是另一配方，应立即停止。release 的 BOOT 不应自动写入恢复颜色，不能用 test 的预期判定 release。
6. 28mm 没换配方，但也要做普通开机、04 选择、DISP 和两种关闭，确认共享 Look 拆分没有影响它。需要停测时先去掉 DAT，用原生 04 检查；需要回退时用已批准且校验正确的 g155c 包。新旧包的记忆不通用，不要期待回退后自动获得 g156 的档位。

| 单元 | release 要逐条检查 | test 要逐条检查 |
| --- | --- | --- |
| mount-a12 | 05 F-CC、06 F-CN、M9 STD、HNCS HiCon、Kodachrome25、HNCS LowSat、Vision3 500T | 同左 |
| a12-50 | 03 HC BW、07 L-Chr、08 L-Viv、HNCS HiCon、Tri-X 400、Velvia 50、Metropolis | Velvia 50、Metropolis |
| a12-28 | 原生 04 与未改 Looks 回归 | 同左；另查本包新保存微调的关机恢复 |

未跑的实物边界是实际刷写结果、真实卡及 FAT32 读写、相机真实单元通信、物理 NAND 持久化、快门/JPEG/回放和实际颜色。模拟器、host C 与记录哈希均不能替代这些现场项目。

## SHA256SUMS 与复跑

[SHA256SUMS](SHA256SUMS) 覆盖冻结输入、当前脚本、报告与证据；[封存回执](seal_receipt.json) 另绑定该清单与报告。校验路径以仓库根为基准。冻结文件末次核对改变数为 0，见 [末次核对](evidence/final_freeze.json)。

以下命令只向本审查目录写入。冷启动样本需另选未使用的 label，避免覆盖已有证据。CPU 计算保持最多两个进程。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
nice -n 15 /usr/bin/python3 -I -B research/review_g156_r1/static_audit.py
nice -n 15 /usr/bin/python3 -I -B research/review_g156_r1/receipt_audit.py
nice -n 15 /usr/bin/python3 -I -B research/review_g156_r1/instruction_audit.py
G156_REVIEW_OLD_RECORD=1 nice -n 15 /usr/bin/python3 -I -B \
  research/review_g156_r1/cold_sample.py --backend reference \
  --unit 50mm --profile test --label reviewer-new-old-record-run \
  --settings research/review_g156_r1/local/g155c-record-in-g156-settings.bin
```
