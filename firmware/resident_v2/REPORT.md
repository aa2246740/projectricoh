# resident-v2-spec 交付报告

规格与骨架量测已完成，尚不具备刷机条件。冻结了37个hook/观察位置、16个服务编号、引擎入口、IROM安装/停用语义和八项探针。精简骨架实占 **7632 B**，8340 B窗口余 **708 B**；完整校验版占 **11016 B**，超 **2676 B**。精简版仍有大量服务和生命周期桩，不能把“骨架放得下”当成最终常驻层容量通过。

用户补充的六参数已经纳入：对比、饱和、高光、阴影、冷暖A-B、色调G-M，不含锐度。ABI只传param_id和int32 value。范围、默认值由元数据决定，建议首发±5、颜色和影调单档约旧实现两倍；算法另做。容器data v2预留8位，支持-128..127的元数据范围，允许±8及以上。WB由引擎写原生S两轴，不改深层行。

本次仅写 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/resident_v2/`。没有操作相机、存储卡、单元、RPC或更新入口，没有制造机身映像、更新包、平坦payload、DAT或其它上卡文件，没有安装包、子代理、sleep、轮询、commit或push。

## 1. 已核实

### 1.1 本轮静态与构建证据

- 写入前及各脚本入口核对Workspace已挂载、可写、APFS，Volume UUID为`14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。盘使用率约20%，没有创建替代挂载目录。
- 按官方MAIN的16段记录逐段映射，37个位置原字节与官方文件相符；现有14项UI候选另逐项对照输入清单。8340 B候选窗口在官方文件中全为FF。机器码、段映射结果和GNU摘录均只在本任务local/。
- 官方机身SHA为`da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。三个stock pin用现有只读extract_module函数从各自官方单元重新提取，并与独立trust文件核对；没有运行上游打包器或改上游文件。
- 使用现有GCC13.4.0和GNU M32R工具，沿用Stage2l的freestanding/Os/m32r/msdata=none/G0等选项，C同样由large覆盖为medium。没有安装新工具链。
- 两个量测ELF均无未解析符号、无残余重定位。每版35个代码桩的原指令重放和最终续接地址与链接反汇编相符；两项descriptor数据恢复点不生成代码桩。
- H01覆盖8 B后应在`0x202870A4`执行原native调用；H02默认回`0x202870AC`。Fn2接管必须返回native0；返回2会触发事件1重建。这些控制流写入规格。
- 系统`python3 -I -B`驱动的372项主机检查在ASan/UBSan下通过，覆盖新执行前校验的边界/身份/pin、data v2外层布局、来源选择、单fd短读/close收尾/源重读变化、事件环覆盖以及64位移位helper。没有执行M32R代码或引擎代码。

主机检查包含一个刻意的差异用例：损坏bank语义、重算外层CRC后，精简gate接受外层而完整gxrce拒绝BANK。这证实精简方案需要引擎纯init继续校验，不能误称与完整解析器等价。任何产品写能力和READY发布必须排在纯init成功之后。

### 1.2 直接采用的任务事实

驱动器表两项、IROM/ATA1对应关系、全机两个fd上限、shooting返回0与1/2的区别、旧容器95个CLI/8416种截断/1024次随机损坏、旧微调4500条曲线/3125组颜色行，以及当前Stage2l和官方更新回退的设备事实均沿用户给定证据使用。

旧报告manifest中的camera_not_run仅描述当时主机打包，不能覆盖用户后来亲自核实的Stage2l安装和官方回退。本轮没有重新声称这些设备动作由我执行。旧±2算法的对照结果也不覆盖新的±5/约2倍强度。

## 2. 实测体积与预算

| 链接对象 | code+rodata | root | 实占合计 | 相对8340 B |
|---|---:|---:|---:|---:|
| 原样完整gxrce基线骨架 | 10504 B | 512 B | 11016 B | 超2676 B；严格链接拒绝。 |
| 精简gate，含data v2元数据入口 | 7120 B | 512 B | 7632 B | 余708 B；严格链接通过。 |

精简版payload从`0x2005276C`到`0x2005433C`。余708 B在代码与固定root起点`0x20054600`之间；root占`0x20054600..0x20054800`，NOBITS/NOLOAD，必须显式初始化。窗口总跨度仍是8340 B，不把中间空隙算已用，也不把旧probe尾另加一遍。

这里的字节数是链接后代码、常量和root的目标空间占用，不是含ELF头、符号表的主机文件长度。

完整版的严格链接错误为：

```text
resident code exceeds 7828B before 512B root
section .root VMA [20054600,200547ff] overlaps section .payload VMA [2005276c,20055073]
```

仅为取得完整尺寸，另链接`oversize-measurement-only.elf`，把诊断root放到0x20060000。该地址没有内存归属许可；这个ELF不在获准窗口内，不是替代布局，更不能用于机身。没有导出binary或容器。

| 精简版组成 | 实测字节 |
|---|---:|
| loader、来源选择、事件环、服务桩与API表 | 1628 B |
| 19个native桥、RPC8、cache与IRQ辅助 | 368 B |
| 35个共用现场保存的观察桩 | 984 B |
| 独立三单元trust及量测ID | 212 B |
| memcpy与64位逻辑右移helper | 76 B |
| gxrce原CRC/SHA核心及精简gate | 3852 B |
| root及16项事件环 | 512 B |
| 合计 | 7632 B |

原card_engine的3840–5632 B是未编译预算，加UI上限后约6528 B。实际骨架已经比这个上限高1104 B，且未实现全部服务。原预算不能继续当最终可行性证明。六参数data v2入口相对本次四参数基线增加304 B，元数据磁盘结构另增加640 B；两者是不同的量。

沿用`-fstack-usage`记录。可见单函数最大SHA块frame为308 B；loader/gate/SHA嵌套还要叠加，不能把308 B当峰值。基于调用链约有900 B以上的栈规划需求，另有hook、native服务及OS开销；没有测得相机任务栈余量或运行延迟。

### 带证据的容量选择

1. 保留完整执行前语义校验，就必须先压掉至少2676 B，再容纳尚缺功能。仅共享跳板已经做过，35桩984 B、native桥368 B；这份收益已经反映在数字中，不能再重复当作未来余量。
2. 建议保留当前精简边界，把bank/非stock行形状、完整配方身份和微调语义放在引擎纯init。与完整版相比减少3384 B。机身ID、入口、重定位、全包CRC、所有section边界和外部map/stock pin仍在执行前，不能再下放给未验证代码。
3. 仍可优化精简子集、service分派和额外post桩，但必须重新实测并证明没有删掉上述执行前信任边界。目前708 B无法证明足够；这是刷机前的容量门。
4. 若精简后仍装不下，只能另找并证明内存所有权、装载与覆盖生命周期。段7/10/13的3024 B目前归属未知，本任务未占用，诊断root地址也不提供许可。

## 3. 推断与已冻结设计

完整合同在[RESIDENT_SPEC.md](RESIDENT_SPEC.md)，包括每个位置的默认原厂路径、代次、16服务的操作/签名/错误码、入口表、root、加载最后发布和失败规则。

安装采用IROM A/B+TMP、有效性优先再比较generation、卡严格更新才安装。正式名完整回验后把DAT改为OK，解决正常安装后“格式化内置存储却自动装回”的冲突。只有送货确认也成功才显示已安装；写保护、rename不明或断电中断时不作这个承诺。没有把FAT改名说成原子或把close说成掉电持久化。

旧容器v1不改。新data v2使用带u32 param_id表的变长微调元数据，首发六项加两空位，8位时1408 B，min/max/default为signed8，容许±8以上。服务的param值是signed32。已编译并用RAM样本核对新版外层布局，但没有完整data v2解析器或六参数算法。

每单元16槽且全部48个entry独立时，新数据底座26960 B，32 KiB只余5808 B给engine+reloc。6 KiB引擎已经超336 B；未来引擎编译结果可能要求去重或格式调整，不能继续套旧预算。

视图、S、unit绑定和engine lease分离。菜单关闭/换unit/SD通知不释放代码；只由安全菜单任务调用引擎。异步hook只记录、停止或作废，不在回调中I/O、free或串行恢复RPC。任何已部分W的失败保留sticky uncertain/UNKNOWN，原厂UI恢复不能当作ISP恢复。

## 4. 未知及骨架的实际边界

这次真正实现并量测的是：默认观察/重放桩、共用ABI桥、单fd读取、三源摘要选择、完整gxrce调用基线、精简gate、事件环及服务表形状。loader停在VALIDATED，不重定位、不清BSS执行、不调用bootstrap/init、不发布READY、不写native UI/S/文件。

未实现的部分包括完整lease分配表、稳定UI恢复、所有代次更新与排空、通知post桩、完整服务dispatcher、送货确认、IROM安装、微调状态保存、引擎入口表受理、颗粒快照执行、模式/回放真正失败分支。当前服务能力全为零，大部分服务返回UNSUPPORTED；QUERY与单值EPOCHS只是桩的可测行为。

设备未知仍包括插卡读IROM、主堆跨真睡眠/USB保持、bootstrap/Monitor覆盖、物理卡/单元通知完整性、所有按键别名、九行面板与UI引用寿命、深层写后实际取景刷新，以及WB两轴字段的方向/模式使能。只读探针不能独立证明写入/改名/格式化或刷新因果。

八项探针的结果显示和恢复边界见[PROBES.md](PROBES.md)。一次机身升级、正常格式化停用、重新送货和官方回退步骤见[MIGRATION.md](MIGRATION.md)。两张“刷机前必须关闭 / 刷机后用探针关闭”清单在规格最后，未关闭项没有被本报告改成通过。

## 5. 产出与复核

| 文件 | 用途 |
|---|---|
| RESIDENT_SPEC.md | 冻结位置、ABI、root、加载/安装、data v2改动、Stage2l语义、两张验收清单。 |
| PROBES.md / MIGRATION.md | 八项只读探针映射；未来一次机身迁移与官方回退步骤。 |
| abi.h / resident.h | 请求/回复/通用参数/入口表和512 B root的机器布局断言。 |
| resident.c / bridges.S / resident.ld | 最小骨架、native桥和严格窗口链接约束。 |
| validate_full.c / validate_envelope.inc.c / runtime.c | 完整gxrce量测入口、精简gate和缺失的freestanding helper。 |
| inspect.py / build.py / verify.py / host_checks.c | 定点抽查、两个M32R构建、链接桩审计和主机行为检查。 |
| checksums.py / SHA256SUMS / .gitignore | 完整交付哈希和local忽略边界。 |
| local/HOOKS.md / hooks.json / H*.bin / H*.asm.txt | 官方原字节、段映射与GNU摘录，全部为私有静态证据。 |
| local/size.json / verification.json / inputs.json | 精确尺寸、验证结果、实际依赖输入的哈希快照。 |
| local/commands.json / *-link.log / failures.log | 可复跑命令、完整校验溢出证据、早期失败记录。 |
| local/compact/resident.elf / local/full/oversize-measurement-only.elf | 仅量测ELF，不含机身更新头，不供安装。 |

首次尝试的失败包括把64 B bank record先压成49 B identity后又被helper二次转换、GNU分支对裸地址的语法限制、ld PROVIDE的赋值格式，以及现有freestanding GCC没有安装libgcc.a造成`__lshrdi3`未解析。均已修正；原始错误保留在local/failures.log。结构体复制产生的memcpy也由本任务小helper满足，没安装运行库。64位helper的0..64移位已有主机对照，但不是M32R运行验收。

在共享检出根目录执行，写入只落本任务目录：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
git check-ignore -v firmware/resident_v2/local/HOOKS.md
python3 -I -B firmware/resident_v2/verify.py
python3 -I -B firmware/resident_v2/checksums.py
```

只验证当前交付快照而不重建：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/resident_v2
shasum -a 256 -c SHA256SUMS > local/checksums-check.log
tail -3 local/checksums-check.log
```

复跑会重写本任务local的构建/证据；需要先保留本次快照时先验现有SHA256SUMS。清单覆盖全部任务文件及local，排除自身和`local/checksums-check.log`。依赖输入在验证前后哈希一致；共享检出的其它既有修改未清理、未覆盖。
