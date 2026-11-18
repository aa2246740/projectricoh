generation 114 已暂存，可交新一轮独立对抗审查。修复可只换 GXRCE.DAT，不改机身。已锁定的实现缺陷是 H01 调用 seed 时，原生构造器尚未写入 type 5；旧 seed 却要求 type 已为 5。主机与最终 M32R 字节重放均复现了旧版拒绝、新版发布的差别。尚未在相机验收八行，也没有把旧日志未记录的现场 type 值写成已知事实。

暂存文件是 [GXRCE.DAT](local/staged/SD_ROOT/GXRCE.DAT)，65,088 B，SHA-256 为：

```text
132e56389808970b0db8a8c4a359c46f18f0fb2423ecbc11f671d18df19a49a5
```

本轮只写 `firmware/engine_v35_publish/`。未访问相机、卡或设备 USB，未联网、刷写、提交或派生代理。官方文件、两份 v3.4c 目录、卡备份和 Stage2l 共 5,564 个输入均已散列冻结并复核；未读取或写入 `decisions.tsv`，未触碰 `research/r28_bank_design/`。REA Binwalk 接口因要求 Linux 不可用，未安装替代工具，采用仓库 M32R objdump、原始字节核对和受限指令重放。

full-r11 从 acceptance 树的独立副本重建，实际得到 64,816 B、SHA `6cb63aa47c18086f5ade681ffe4dc97378394ff7a65c0688d19b3880d804c707`，与冻结卡 B 的 GXRCE.OK 逐字节相同。副本只调整目录守卫与相对头文件依赖，构建产物未变。之后才在 candidate 副本修改。两次源树与工具链配置、源散列、链接映射和原始编译输出均保存在各自 local/。

原生证据来自真正官方 `ilaunch3`，SHA `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。下表的文件偏移按映像段表换算；相关 writer 字节也与已刷 v3.4c `24b1de0e…` 相符。完整字节、引用清单和限制见 [native/evidence.json](local/native/evidence.json) 及同目录反汇编。

| 对象 | VMA / 文件偏移 | 已核实的含义 |
| --- | --- | --- |
| 32 B 原生状态初值 | `0x2022F71C` / `0x1E491C` | 映像初始 type 为 5，随后各列表构造器会改 type。tag 33 表示通用 ADJ view，不能据此认定当前 type 为 5。 |
| 状态中的表指针 | `0x2022F720` / `0x1E4920` | 初值为 `0x2022F56C`，属于同一 32 B 状态的 +4 字段。直接引用清单中没有此指针字段的运行期 store。不能把这个清单当作全程序别名写入证明。 |
| ADJ writer | `0x20285904..0x20285914` / `0x23AB04..0x23AB14` | `0x20285910` 的 `ldi r0,0; stb r0,@r8` 把 type 写为 0。 |
| 另外两种原生 writer | `0x20286F30..0x20286F46` / `0x23C130..0x23C146`；`0x202876A4..0x202876BA` / `0x23C8A4..0x23C8BA` | 分别把同一字段写为 4、9，结构仍相同。 |
| Image Settings 入口 H01 | `0x2028709C` / `0x23C29C` | resident 在此同步调用 engine menu，继而调用 list_bind 和 seed。 |
| Image Settings type writer | `0x20287118..0x2028712E` / `0x23C318..0x23C32E` | `0x2028712C` 才执行 `stb r4,@r1`，写 type 5。它位于 H01、H02 之后，不会在同步 seed 返回之前执行。 |
| 表的消费与记录写入 | `0x202858A0..0x202858D4` / `0x23AAA0..0x23AAD4` | 从 state+4 读表，以 type×12 选记录，再复制一条 12 B 记录；这里修改表记录，不修改 state+4 指针。 |
| Image Settings descriptor | `0x2022F5A8` / `0x1E47A8` | 恰为 `0x2022F56C+5×12`，三字段为 names 指针、count/填充、hidden-map 指针。初值 names=`0x2022D610`、count=7、hidden-map=0。 |
| ui_state_capacity | `RvPrivateContext+72` | engine `rv_services_init` 在 context 初建时写 `RV_UI_CAPACITY=256`，见冻结 `engine_services/api.c:25`、`resident/resident.h:35`。不是原生 UI 决定的容量。主机实际入口验证为 256；新黑盒会记录现场值。 |

因此，正常进入 Image Settings 时 seed 可以看到上一列表的 type 0、4 或 9；这是同一状态结构在构造器切换前的值，不能解释成另一种未知内存布局，也不能等一个异步 type-5 写入来解决。H01 同步调用不返回，后面的 native writer 就不会执行。

现场两份黑盒都属于 jlaunch/50mm，均停在 receipt 15、rows=0，随后 ENG_IO/RV_IO，没有第一条 phase-16 文本事件。它们把失败锁在 rv_native_seed，尚不能直接区分 type、table 或 capacity 三项：gen113 没有保存这些输入。按已核实的正常初始化，table=`0x2022F56C`、capacity=256，失败项就是 `type!=5`。这项现场归因仍是有字节重放支持的推断；具体先前 type 是多少，须由 gen114 日志确认。官方 descriptor 的 7 与用户看到的 6 个原生项目也不能混为一项证据，本轮没有伪造第七个可见项的解释。

修复只改五个运行期源文件，见 [product.patch](local/product.patch)：

1. `rv_native_seed` 保留容量和表范围检查。原生 type 不为 5 时，额外要求表指针精确等于已核对布局的 `0x2022F56C`，才复制前六条 12 B descriptor。随后仅把私有快照的 type 置 5，私有区尾部 132 B 详情仍清零。type 5 原有分支保持兼容。
2. `services.c` 的第二层 ui_seed 使用相同条件，并在第二份私有快照里置 type 5。否则只改第一层，后续 UI_LIST 仍会失败。UI_LIST 原有零详情、lease、行数、指针与游标检查保持执行。
3. `list_bind` 在 seed 前记录诊断。黑盒复用原来全零的尾部 64 B，不增加 4,096 B 日志容量、BSS 或 ABI 字段。原生 type、表指针和任意未知结构都没有新增写入。原有 names/count 与游标发布、恢复代码保持原样。

选择私有 type 5 有明确的布局依据：H01 已证明当前意图是 Image Settings，type 只是固定状态头内的 descriptor 索引；索引 5 的记录位于已知表内第 60 字节，复制 72 B 足够覆盖它。不会按上一 type 去解引用相应的 type-9 详情表，也没有放宽为可写任意原生结构。50mm 与 Mount 使用同一机身布局；28mm 仍在可见行分支返回原生列表，没有新增禁用正常功能的保守门禁。

黑盒尾部以文件偏移 2,432 的 `GXSD3501` 开始，沿用原文件 payload CRC 和轮换写入校验。相对该尾部的字段如下：

| 偏移 | 内容 |
| --- | --- |
| 0..7 | 魔数 `GXSD3501`。 |
| 8..11 | seed 调用时的 ui_state_capacity，BE32。 |
| 12..19 | `RV_WORD(0x2022F5A8)` 与 `RV_BYTE(0x2022F5AC)`，各用 BE32 保存。 |
| 20..27 | `RV_WORD(0x205A27D8)` 与 `RV_BYTE(0x205A27D4)`，各用 BE32 保存。 |
| 28..59 | `0x2022F71C` 起的原始 32 B；首字节是 type，+4 是 table。table 另用 p32 写回同一日志位置，目标端字节不变，也可跨主机端序核对。 |
| 60..63 | 捕获时的事件序号。 |

诊断只读固定 native 槽，不跟随表或 view 的未知指针。失败沿用 safe-entry 的自动 flush；成功后通过 Fn2 或正常退出触发既有 flush。解码器兼容旧日志，并输出 seed_inputs 和旧 seed 会拒绝的条件。旧零尾部得到 seed_inputs=null，不会补猜历史值。

```sh
/usr/bin/python3 -I -B firmware/engine_v35_publish/decode_blackbox.py /绝对路径/复制出的/GXRBX0.BIN
```

已通过 259 个当前主机运行，使用 ASan/UBSan，含全部 250 个原 v3.4c 唯一运行及 9 个新增运行。新增运行分别覆盖三种单元的 native writer/旧实现负对照、明确坏输入的原生回退、真实 gen113 IROM 加 gen114 卡文件的升级。旧手工 type5/table=`0x2022F000` 用例被单列保留，不再作为正常初态。生成初态的代码直接读取官方状态/descriptor 字节，并执行从官方与已刷机身逐字节核对的 type writer；在主机边界转换 RV_WORD 的端序。

| 必保行为 | 本轮主机证据 |
| --- | --- |
| 50mm/Mount 恰好八行，28mm 原生 | basic、first、daily；新 writer 的 type 0/4/9/5 均覆盖，原生 descriptor/八行私有 descriptor 同时核对。 |
| GR IV Posi 01、Nega 02，03 Standard-mode mono | 48 槽完整 552 B entry/record 与 full-r10、full-r11 一致，effective-rows.bin 与重建 113 完全相同；daily/t 与实际字段比较通过。没有重新宣称拍摄验色。 |
| remember-last 只定位游标、live recipe 高亮 | first 的 9×256 输入投影、daily、历史用例及无菜单阶段 RPC/设置写入断言通过。未观察实际 LCD 高亮。 |
| Fn2 每配方微调，OK 保存、MENU 丢弃 | legacy、basic、store-fault、publish-failure、daily，以及新 type 0/4/9/5 入口均通过。 |
| IROM 防格式化、掉电恢复完整上次或纯 04 | irom、history、daily；新增 update114 验证保留旧 113、安装并选择 114，卡无产品文件后仍从 IROM 加载 114。 |
| ISO100 行、相邻字节 | iso、neighbour、RPC 故障与 T 门槛用例通过，数据与原候选一致。 |
| 黑盒与安全锁存 | ctl、quarantine、rejected、log-fault、service-quarantine 等原套件保持通过。新增条件只因明确容量不足或未知表失败；没有把 ambiguous open=-1 变成新锁存依据。 |

另有 21 个受限 M32R 用例执行最终 gen113/gen114 容器对应 ELF 中的 seed、字节复制、诊断编码与第二层快照指令，核对实际 packed engine 字节，证明非 type5 的差别和 64 B 诊断的精确内容，并断言没有新增 native 状态写入。receipt 记账用替身，未执行原生绘制任务、调度器、中断、异步竞争或 LCD。主机 C 的 native UI、文件系统与 RPC 仍是替身，不等于相机已显示八行。见 [verification.json](local/verification.json)、[machine/results.json](local/machine/results.json) 与原始 logs/。

| 预算 | gen113 | gen114 |
| --- | ---: | ---: |
| DAT 总字节 | 64,816 | 65,088 |
| engine | 55,404 | 55,676 |
| engine BSS | 11,520 | 11,520 |
| header 与 recipe 数据 | 9,404 | 9,404 |
| relocation | 8 | 8 |
| 65,536 B 容量余量 | 720 | 448 |
| resident payload / 现有余量 | 7,868 / 216 | 原实物不变 |

新增 272 B 全在 container engine 内；容量没有扩大，未删配方、持久化、微调、ISO100 或黑盒换尺寸。未构建机身，resident/hook/静态 descriptor 的改动成本是 0 B，216 B resident 余量未使用，因此无需触发 BODY 改动停止门槛。

DAT 仍绑定 resident build ID `eb96410f5224f76c1cf684a3bd6789eca4c80acf34019120e30dacaeb01da941`，ABI ID `b6353e4de1c89bd37c08ba6734efc8e0`，三枚 pins 为 `f09fe7b4 / fb3fbcb2 / 95f3dca9`。DAT 中的 body trust SHA 继续是官方基线 `da1980e9…`，与 113 字节相同；它不是已刷修改映像的 SHA。已刷机身身份另外核对为 `24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72`，没有重新生成身份来冒充另一机身。

卡 B 更新步骤供审查后由用户执行，本轮没有操作卡：

1. 相机关机，保留 50mm。把卡 B 上原 `GXRCE.OK` 和两个 GXRBX 日志复制到主机留档。
2. 删除卡 B 根目录原来的 `GXRCE.OK`。该文件是已安装 113 的收据，不是 IROM 副本；删除它不会删除机内 113。若根目录有上次未处理的 GXRCE.DAT，先移走，避免放错文件。
3. 从 `local/staged/SD_ROOT/` 只复制新的 `GXRCE.DAT` 到卡 B 根目录，核对大小 65,088 B 与上述 SHA。不要复制 staged/recovery/ 下的 CTL，也无需复制 ilaunch3、DEEPTBL 或任何机身包。
4. 安全推出卡 B，插回相机正常开机，M 档、Start Settings Readout=Body，打开 Image Settings。H01 的 loader 先验证并加载卡上 DAT；engine 在第一次 menu 尝试安装 114。IROM 中有效的 113 保留，114 经临时文件、读取校验和提交进入另一副本，之后 card DAT 与已安装内容逐字节比较，再把 DAT 改名为 GXRCE.OK。
5. 先记录 50mm 是否出现八个真实配方行。成功时打开 Fn2 再按 MENU 丢弃退出，以触发日志写入；失败时既有失败路径会自动写日志。关机后把卡 B 的 GXRBX0/1.BIN 和 GXRCE.OK 或仍在的 DAT 复制回主机，使用新版解码器。114 的 OK 应与本交付 DAT 同 SHA。gen113 已装在 IROM 不会阻止更新；残留旧 OK 的改名冲突才会干扰确认。
6. 50mm 成功后再关机换 Mount，核对八行和 Fn2；28mm 应继续显示原生列表。重新开关机以及无卡产品文件的测试由用户另行验收，主机通过不代替这些结果。

预期失败模式仍是原生列表可用。未知表或容量不足时，新 seed 在发布 descriptor 之前拒绝；模拟明确坏输入的 50mm/Mount 会退役 engine 至本次开机禁用状态，native descriptor 仍为七行、native type/header 未改、没有 RPC 写入，后续原生 writer 可继续执行。28mm 保持原生路径。这里的可用性是原生回放路径与状态不变量的主机证明，尚非硬件容错验收；若原生指针在允许检查之后发生异步变化，本轮重放不能证明相机行为。

恢复时先关机、从卡移走未处理的 `GXRCE.DAT`。若 114 已装入 IROM，移走 DAT 不会卸载它，格式化卡也不会降级。可以把已随包提供并经既有 ctl 套件验证的 [recovery/GXRCE.CTL](local/staged/recovery/GXRCE.CTL) 复制到卡根目录，再冷启动；它是有效 CRC 的 OFF 控制文件，走已有停用入口，不改机身。恢复正常配方功能前移走 CTL 并冷启动。机身需要回刷时，沿用用户已成功的卡 A Stage2l + 50mm，按“+ & playback”恢复；本轮没有重测恢复操作。真正官方 1.51 来源为 `artifacts/downloads/gxr-151.zip`，SHA `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`，不是本轮生成的新包。

复现与封存命令如下。所有 Python 均隔离运行；生成物只进入本任务目录，使用已有交叉工具链，无下载。

```sh
/usr/bin/python3 -I -B firmware/engine_v35_publish/finalize114.py protected
/usr/bin/python3 -I -B firmware/engine_v35_publish/baseline/build_r11.py
/usr/bin/python3 -I -B firmware/engine_v35_publish/native_evidence.py
/usr/bin/python3 -I -B firmware/engine_v35_publish/candidate/build114.py
/usr/bin/python3 -I -B firmware/engine_v35_publish/verify114.py compile
/usr/bin/python3 -I -B firmware/engine_v35_publish/candidate/verify_v34c.py vectors
/usr/bin/python3 -I -B firmware/engine_v35_publish/verify114.py seed
/usr/bin/python3 -I -B firmware/engine_v35_publish/verify114.py suites
/usr/bin/python3 -I -B firmware/engine_v35_publish/verify114.py history
/usr/bin/python3 -I -B firmware/engine_v35_publish/verify114.py decode
/usr/bin/python3 -I -B firmware/engine_v35_publish/machine114.py
/usr/bin/python3 -I -B firmware/engine_v35_publish/finalize114.py stage
/usr/bin/python3 -I -B firmware/engine_v35_publish/finalize114.py seal
/usr/bin/python3 -I -B firmware/engine_v35_publish/finalize114.py verify
```

交付摘要为根目录 [SHA256SUMS](SHA256SUMS)，仅复制到卡的文件另有 [staged/SHA256SUMS](local/staged/SHA256SUMS)。本轮自写工具遇到的路径迁移、主机端序、故障注入 flush 许可、坏输入回退断言和 CPU 指令子集问题已修正并保留失败日志，见 [dev-errors.log](local/dev-errors.log)。正常产品行为套件未因这些问题放宽断言。独立审查应重点检查 canonical descriptor 的依据、第二层 seed 一致性、最终指令/容器绑定，以及旧现场缺失值的证据边界；随后才是新的相机验收。
