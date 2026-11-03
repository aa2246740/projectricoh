可以交复审

# gen 138：开机记住上次配方（A）、用户条目标题（B）、去掉端点 `!`（C）

日期 2026-10-31。机身沿用 v3.8（`ilaunch3` = `d4fa3b46…`，一字节未改），只换 DAT。全部验证都是**电脑上的主机模型**（M32R 解释执行，单元通信、S 存储等设备边缘是模型），**相机上一项都还没测**。没有碰卡或相机，没有 git 写操作，没有开子代理，没有 sleep 轮询。

## 1. 产物和尺寸

| 项 | 值 |
| --- | --- |
| GXRCE.DAT | `88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a`，91,432 B，generation 138 |
| 主请求（7,504 + DAT + BSS） | **108,060 B**，上限 108,124 B，**余量 64 B**（g137 是 108,124 B，余量 0） |
| BSS / 引擎段 | 9,124 B / 62,512 B |
| 机身 | `d4fa3b46…`，与 `package_v38_g137` 逐字节相同；常驻体 7,908 B，距 root 176 B |
| 包 | `firmware/package_v38_g138/local/SD_ROOT`：30 个文件，29 个与 v38_g137 相同，只有 GXRCE.DAT 不同 |
| 源码 | `firmware/engine_v55_g138`（从 g137 复制后修改） |
| 静态核对 | `artifact_check.py` → `artifact-results.json`：PASS_STATIC |
| 重现 | `build.py engine` 两次构建得到同一个 SHA；同一套脚本用 `--generation 137` 能逐字节重建 g137（`78dcbb9a…`） |

上限的来源、怎么腾出空间、以及放宽的依据和风险，见 [FEASIBILITY.md](FEASIBILITY.md)。**上限没有放宽。**

范围核对：`firmware/resident_v38`、`firmware/engine_v54_g137`、`firmware/package_v38_g137`，以及复用的 `research/emptystack_v38`、`g135_v37`、`review_g124`、`review_g135`、`review_g135_gpt`、`firmware/engine_v48_own`、`tools/`，在本任务开始（10-30 16:50）之后都没有文件变化。`package_v38_g137/SHA256SUMS` 30/30 一致。同期 `research/review_v38_g137` 里有变化，那是另一位复审者写的；本任务的回归在只允许写 `research/g138_persist` 和指定 Scratch 的沙盒里运行。

## 2. 改了什么

源码差异全文：[source-diff.txt](source-diff.txt)（g137 → g138，11 个文件）。

### A. 关机后记住上次配方（只改 DAT）

按 `research/persist_recipe_r2/REPORT.md` 第 6、7 节实现：

- **记录**：位于 S+0xFD4..0xFFB，共 40 B。格式：`GXR2`、版本 1、配方号 1..8、单元 0..2、完整位 1、十个大端 int16 旋钮值、DAT 头的两个 CRC（共 8 B，作数据标识，DAT 任何变化都会让旧记录失效）、前 36 B 的 CRC-32。用户条目写 40 个零（不支持把自定义条目当成开机恢复对象，也不偷偷存成内置配方）。
- **服务层**（`engine_services/services.c`）：
  - `RV_SETTINGS` 新增 op 4（读）和 op 5（整条替换为合法记录或全零）。每次都核对 op 1 的令牌和 epoch，并要求 S 长度 0x1000、S+0xE=0x0D24。
  - op 2（原有的 S 字段写入）和 op 5 共用同一个临界区：在 IRQ 内只试一次，计数恰为 −1 且 ID 为 55 才取得锁；否则返回 BUSY，**零写入、不等待、不排队**。写完在同一临界区内读回，再把计数写回 −1。
  - 不写 S+0xFFC，不提交 NAND，不写 T。
- **开机恢复**：只在开机后第一次推 ADJ（第一次 H01）时做一次（`boot_restore`），条件全部满足才恢复：
  - S=Standard 1、WB 9/9、S+8=0（机身来源）；
  - 九行逐字节与 stock 一致，T=2（完整读取，不用 `validate_live` 的提前返回）；
  - 单元和 epoch 有效；
  - 记录整条与重新编码的结果一致；
  - 该配方本身不需要写 S。

  条件满足时，走正常的写入流程恢复，再完整读回九行和 T。读回不一致就按原有流程补偿到规范 04（全行重写并读回）。
- **非正常开机**：不恢复、不显示 `>4`（不称为 04），也不再像 g137 那样在首次打开时把 S 强制改成 04 的计划，保留原厂状态，直到用户自己选配方。
- **记忆时机**：每次用户选择（含浏览预览、Default、取消预览后恢复到已确认状态）在完整生效后立即写记录。启动整理、内部补偿、回退到 04 不写。写失败（锁忙、过期）时旧记录保留，生效行的 `>` 显示为 `!`，并在下一个合法边界（下一次列表刷新或 H07）重新应用同一状态时补写。
- 8 行规则、H06/H07/H08 的严格归属都没改。

### B. 用户条目的卡片和逐项页标题显示条目名

`adapter.c` 的 `uv_text`：当前是用户条目时，第 0 行显示 `<` + 条目名，`*`/`-` 表示是否改过，例如 `<FCC-001`。与 gen 126 以前的显示约定一致。

### C. 去掉旋钮的端点 `!`

**改前核对**：`!` 只在一种情况下出现，就是档位等于该旋钮可选范围的两端（`endpoint()`）。出现在三处：
- 数值页，例如 `Cont! +9`、`Amt!150%`；
- 逐项页，例如 Fade 默认 0 就在下端，所以平时就显示 `Fade!  0`；
- 卡片简写格，例如 `S 0 F 0!`。

超过上限的档位**本来就选不到**：可选档位就是旋钮表里的点，上限已经写在表里。例如 50mm GR Pos 的 Satu 是 −9..+6，Std 的 Satu 是 −9..+5，见 [knob-ranges.json](knob-ranges.json)。数值页到端点本来就停住、不循环。我用真实计算路径把 3,430 个可选档位全部算了一遍：**没有任何一档与相邻档的输出相同**，也就是没有“选得到但不生效”的档位（`knob_ranges.py`）。所以 `!` 只是端点标记，不代表截断。

**改动**：删除 `endpoint()` 和 3 处调用。到端点照旧停住，不循环，没有任何标记。省下 60 B（主请求 108,120 → 108,060）。

## 3. 测试

所有测试同时最多 1 个进程，回归在沙盒里运行（只允许写本任务目录和指定的 Scratch）。

### 新测试（`persist_check.py`，50mm，主机模型）——27/27 通过

| 用例 | 检查的内容 | 结果 |
| --- | --- | --- |
| cold-none | 正常开机、无记录：显示 `>4 Std`，光标在 04，单元写入 0，S 4096 B 零改动，锁回到空闲 | PASS |
| restore-matches-select | 有记录（5 号、Cont +1）：首次推 ADJ 恢复到 `>5*F-CC`、光标第 5 行、8 行、光标缓存一致、S 零改动；恢复后的九行和 T 与按键正常选到同一状态**逐字节相同**；正常选择写下的记录与独立编码器的结果逐字节相同 | PASS |
| restore-once | 关菜单后换一条记录再开：不再恢复，写入 0 | PASS |
| bad-crc / magic / unit / dataid / slot0 / slot9 / flags / version / level / garbage | 坏记录整条不恢复：显示 `>4 Std`，写入 0，S 和记录都不变 | 10× PASS |
| inel-mode4 / wb / source / t0 / row | 每种非正常开机（Setting1、WB 10/9、S+8=1、T=0、一行非 stock），即使带着有效记录：不恢复，**不显示 `>`**，写入 0，S 零改动 | 5× PASS |
| inel-extension | S+0xE≠0x0D24：记录读不了，但基线仍是纯 04，显示 `>4`，不恢复 | PASS |
| inel-raw | 原始夹具 S（全部为 1）：不恢复、不标 04、S 零改动（g137 会把 WB 改成 9/9） | PASS |
| op2-idle | 锁空闲时 op 2 正常写 S（0x6DD 改为 9），记录也写入，锁回到 −1 | PASS |
| op2-held / op2-waiter / op2-id | 锁被持有（计数 0）、有等待者（计数 1）、ID 不符：**S 4096 B 零写入**，锁原样未动 | 3× PASS |
| record-busy | 锁忙时选 6：旧记录保留，行显示 `!6 F-CN`；按 OK 时有等待者，仍零写入；锁空闲后重开，补写成 6 号，之后显示 `>6 F-CN` | PASS |
| users | 用户条目夹具：恢复 5 → 进 FCC 条目后记录变为 40 个零；卡片和逐项页标题都是 `<FCC-001`；改值后返回；重启后是纯 04，写入 0 | PASS |
| value-ends（C） | GR Pos Satu 一路往上停在 `Satu  +6`、往下停在 `Satu  -9`，多按不动、不循环；卡片（`S 0 F 0`）、逐项页、数值页都没有 `!` | PASS |
| op2-held-extended（观察） | 锁一直被占用时，那次按键要走完原有补偿才结束：271 s（模拟器时间）、3,428 次单元通信，最后显示 `ERR 0SX0`；S 仍然零写入，锁未动，8 行 | 见 §6 |

证据：`local/checks/50mm-*.json`，日志：`local/logs/final.log`。

### 回归（复用 g137 套件，重定位到 g138）

| 组 | 实际运行 | 结果 |
| --- | --- | --- |
| 列表首尾（`es/list_check.py`，静态 C 检查） | 窗口 144,177、移动 56,756、帧 4,054、填充 226、端点 2,814、适配层移动 1,153,416，与 g137 完全相同 | PASS |
| 空栈（`es/empty_call.py` → `emptystack_v38/empty_check.py`，28mm） | 现场形态首次打开发布 8 行，getter 0，光标 04；6 个负例全部拒绝；文件写入 0 | PASS |
| user-tool（夹具） | 32 个条目、163 个拒绝用例；生成的夹具与我独立生成的逐字节相同（`3ccb0f3a…`） | PASS（退出 0） |
| users（review_g124，28mm） | 退出码 **0**，标题差异为空。g137 在这组因标题 P2 退出 1，这个 P2 已闭合 | PASS |
| values（review_g135 legacy，28mm） | 7/7 子项退出 0：四个数值子项（Cont/High/Shad/Satu 逐档 +1..+9..−9，每档用独立算法核对九行、T 和 S 计划）、L1 虚拟滚动、Default 双 DISP、从第二对返回；数值页两端按 C 读作 `Cont  +9`/`Cont  -9` | PASS |

**回归里改动的读取**（都写在 `legacy/legacy_call.py` 和 `es/` 里，运行时记录在各 job 的 `review-readings.json`）：

1. **夹具绑定（`fixture.py`）**：共享主机模型的 S 是 4,096 个 0x01，原厂锁停在 0/0。相机正常开机时，锁初始化为 −1/55，S 是 Standard、9/9、机身来源、0xD24、尾部全零。g138 依赖这两点：锁协议，以及“非正常开机不标 04”。不绑定的话，op 2 会一律返回忙，冷启动时也不会显示 `>4`。所以每次启动后都绑定成正常开机的状态，其余不动。
2. **C 的合同变化**：values 组第 118、124 行的期望从 `Cont! +9` / `Cont! -9` 改为 `Cont  +9` / `Cont  -9`；transitions 组第 68、71 行同理（本轮没跑）。`list_check.c` 只有一行从“端点必须有 `!`”改为“端点必须没有 `!`”。
3. 其余路径和身份替换（gen 138、包路径、DAT SHA 和长度），以及 g137 复审已有的循环读取，原样沿用。

**没有跑完整 81 组**，按要求留给复审。

## 4. 包里每个文件的 SHA256（路径以仓库根为基准）

```
88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a  firmware/package_v38_g138/local/SD_ROOT/GXRCE.DAT
b896f40d9f330c4235d99bd6e32963876f9701293530a927672fd6fab7281e65  firmware/package_v38_g138/local/SD_ROOT/ilaunch0
d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90  firmware/package_v38_g138/local/SD_ROOT/ilaunch3
c9271288f8d395296623a3fe5358b2d83dec8730a89ed138a48ff8a2e8f14a5a  firmware/package_v38_g138/local/SD_ROOT/ilaunch4
071d207858c5863f72fda37274372ab881d86f6ecd2b1a826ad825f90047e478  firmware/package_v38_g138/local/SD_ROOT/ilaunch8
0606a54c673e6db2b7708598f4ad7f1bebb93ade534087b1d0e28f7aff8e2de9  firmware/package_v38_g138/local/SD_ROOT/jlaunch0
951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673  firmware/package_v38_g138/local/SD_ROOT/jlaunch3
377e980401d98ba303246f00b4633468ef5affa54ffbc22d24659cc4b1c5e8ca  firmware/package_v38_g138/local/SD_ROOT/jlaunch4
92554edf413e0090550f192973d0555ee13770cee0764802be209f491f2c424f  firmware/package_v38_g138/local/SD_ROOT/jlaunch8
4b8c1fd4c24cc7112d49290e94f8d9d75523df395aec7c8fff7ad6ac881b0bf6  firmware/package_v38_g138/local/SD_ROOT/klaunch0
491f39a619e7d85eeb28ba5c55494ccaa274872b63b2a98169ee14e8f4757bee  firmware/package_v38_g138/local/SD_ROOT/klaunch3
2dd87ee852b4cea2aff881da9903871a57910da71b27402b1dd29c8dc77fdfe2  firmware/package_v38_g138/local/SD_ROOT/klaunch4
8fc3ff589088b90a8922a200a077aa3f9daed1dbb5d37992c0642c0b63f69f1a  firmware/package_v38_g138/local/SD_ROOT/klaunch8
d7b74b86ec829e90dd4b5c1092abc892b90422fd975942f3d4a6b99ea24e24ef  firmware/package_v38_g138/local/SD_ROOT/l06firm0
6538b919848ee979c3e92ac14a19a29fb8439a1297147c7e0e601afcd135ae8d  firmware/package_v38_g138/local/SD_ROOT/l06firm3
c0aa8256c682a41ad96277eea075e2c58dca5335dc9bc824e09e78fe69ab10d0  firmware/package_v38_g138/local/SD_ROOT/l06firm4
1ddd60028a33aa021169014f07abe263099404522097ad3a267d3fe0387a9c69  firmware/package_v38_g138/local/SD_ROOT/l06firm5
61aae4cfb39ee599eb9647fb72da7b4fd186edcbda298dcb6551fe1fd78d718d  firmware/package_v38_g138/local/SD_ROOT/l06firm8
05cc3f648f84dc1123dc8207a0edbd796a70bec9a01c36fa43199a5959b78e9f  firmware/package_v38_g138/local/SD_ROOT/l08firm0
0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44  firmware/package_v38_g138/local/SD_ROOT/l08firm3
0f787a6fa51893d98bcc778c9e91b2a46ce4fef139828332f418142aa4f36060  firmware/package_v38_g138/local/SD_ROOT/l08firm4
59a75b3ea1cb7dc71d79349e20d49e809eb1678731111678a7b0ef4c8df0db4d  firmware/package_v38_g138/local/SD_ROOT/l08firm8
480c5b195c983100a80ca3e3128cd2a0686de0f7b482c025ec23db3f8a78f527  firmware/package_v38_g138/local/SD_ROOT/nlaunch0
f96c5b84b8fb442706dd694828f51bea4f5f38ea11a7c6881d050d479df9aabf  firmware/package_v38_g138/local/SD_ROOT/nlaunch3
f2bbc71463d9272adc0da8801bc2997a2c147b0ce33c10aaeac01a506e4c678d  firmware/package_v38_g138/local/SD_ROOT/nlaunch4
52921ca9311de0f093d5dea1531e2c83876f2bf91d7032cf45f60a50328b26be  firmware/package_v38_g138/local/SD_ROOT/nlaunch8
3bbc37c6c12c6fedaa190927cdc0594d059919cffee29309ef211122734c6dc5  firmware/package_v38_g138/local/SD_ROOT/qlaunch0
e487d00b5539aa1e3ca9373829456e00676b37310dc717f0a5bcb5235bac6690  firmware/package_v38_g138/local/SD_ROOT/qlaunch3
eb2533fdb26ee61cc2135c40fa73a2d6f618bd6f1872f594b256ce4b586aa90b  firmware/package_v38_g138/local/SD_ROOT/qlaunch4
9d81ca7c1e33df4cd9f0c5532b22ad55b1c11a492707839705ab4e69f9019e45  firmware/package_v38_g138/local/SD_ROOT/qlaunch8
```

同样的清单在 `firmware/package_v38_g138/SHA256SUMS`。引擎 ELF：`2aac1ef2…`（`firmware/engine_v55_g138/candidate/local/full-r13/engine.elf`）。

## 5. 上机验收（用户操作，最多 3 张照片）

前提：卡上是本包，机身已经是 v3.8（版本号仍显示 1.51），装 50mm。只看屏幕，不需要拍样片。

1. **记住配方**：开机，推 ADJ，往下选到 5 号（F-CC），按 DISP 进卡片，再按 DISP 进逐项，选 Cont，按 DISP，往上按一下变成 +1，按 OK 关菜单。关机，再开机，推 ADJ。
   **照片 1**：拍这时的菜单。应该看到第 5 行是 `>5*F-CC`，光标停在这一行。如果回到了 `>4 Std`，就是没记住。
2. **端点不再有 `!`**：在菜单里往上选到 1 号（GR Pos），按 DISP 两次进逐项，选 Satu，按 DISP，一直往上按。
   **照片 2**：拍停住时的屏幕。应该停在 `Satu  +6`，再按也不动，屏幕上没有 `!`。
3. **用户条目标题**：回到第一层，往下选到 `MyRec`，按 DISP，选一个组（例如 FCC），按 DISP，选一个条目，再按 DISP 进卡片。
   **照片 3**：拍卡片。第一行应该是条目自己的名字（例如 `<FCC-001`），不是 `<5 F-CC`。

补充说明（不用拍）：选过用户条目再关机，下次开机会回到 04，这是设计如此。开机后**第一次推 ADJ** 时才恢复，开机到推 ADJ 之间拍的照片仍是 04 的效果。

## 6. 仍然开着的问题和风险

1. **只有主机模型验证。** 真实相机上没测过的部分：参数锁的实际时序、原厂关机保存是否把尾部 40 B 带进 NAND（r1 只在函数级证明过），以及 S 在正常开机时是否真是 1/9/9、机身来源。
2. **恢复时机**：DAT 在第一次 H01 才装入，所以开机后到第一次推 ADJ 之前是纯 04。这是已知限制，机身 v3.8 不改。
3. **锁被持续占用时的选择**（op2-held-extended）：只在“非正常开机（S 不是 1/9/9）、这次选择需要改 S、且原厂恰好在保存”时出现。S 零写入的合同成立，但原有补偿流程会再尝试 6 次（每次都忙、都零写入），约 3,400 次单元通信后显示 `ERR`。正常开机时，所有配方都不需要写 S，不会走到这条路径。如果要改成“忙时直接放弃、不补偿”，需要另开一版。
4. **“未记住”提示**：用的是生效行的 `!`（例如 `!6 F-CN`）。锁空闲后补写的那一帧，标签是在补写之前画的，所以那一帧可能仍显示 `!`，下一次重绘才变回 `>`。方向保守（只会多报“未记住”）。另外，用户刚说过看不懂 `!`。这个提示只在保存冲突时出现，很少见，但符号要不要换，请编排者决定。
5. **MY1–MY3、恢复默认值、Start Settings 改为单元来源之后的旧记录**：DAT 看不到这些事件。只要开机时三项 S、S+8、九行和 T 不满足条件，就不会恢复；但如果这些事件之后条件仍然满足，旧记录会被恢复（persist_recipe_r2 §3 已列为收窄合同的限制）。
6. **DAT 一旦更新，旧记录作废**：数据标识用的是 DAT 头的 CRC，换任何 DAT 都会回到 04。这是保守设计。
7. **余量只有 64 B。** 以后再加功能，要先腾空间，或者先在 v3.8 真机上实测连续堆再决定预算（FEASIBILITY §6）。
8. **新增的内存复用**：服务缓冲借用 `KvWork.stage`，适配层缓冲借用未使用的 `PsStore store`，trust 表借用 `g.work.result`。依据是这些区域在借用期间是空闲的：`compute()` 内部不调用任何服务。以后如果改动 `compute()`，必须保持这一点。
9. **回归只跑了要求的最小集**（values、users、列表首尾、空栈各一个单元，外加列表静态检查）。完整 81 组、三个单元、safety、target-math、通信复核留给复审。

## 7. 文件

- 构建：`build.py`、`package.py`、`artifact_check.py`；源码 `firmware/engine_v55_g138`
- 新测试：`g138_host.py`、`persist_check.py`、`held_lock_probe.py`、`users_fixture.py`、`knob_ranges.py`
- 回归包装：`fixture.py`、`legacy/legacy_call.py`、`legacy/users_gxui.py`、`es/list_check.py`、`es/list_check.c`、`es/empty_call.py`、`offline.sb`
- 证据：`local/checks/`、`local/logs/`、`es/local/`、`legacy/local/jobs/`、`artifact-results.json`、`knob-ranges.json`、`source-diff.txt`
- `local/superseded/` 是旧 DAT 上的作废结果，仅作历史，不采用
