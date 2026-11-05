有缺陷

# build-r2 停止：160 已被诊断包使用

本轮没有生成g160 test或release DAT，没有派生 `firmware/engine_v71_g160/`，没有更新任何引擎代数常量。全仓检查直接触发机主“绝不复用”的硬约束，未擅自改用161或其他代数。g158源码与两包、g159封存证据共281个文件核对无变化，其中g159为64个文件。

## 两包SHA与字节账

| 本轮目标 | 状态 | SHA-256 | DAT/代码/BSS/主请求/每单元行池 |
| --- | --- | --- | --- |
| g160 test | 未构建 | 无 | 没有成品，未产生新字节账。 |
| g160 release | 未构建 | 无 | 没有成品，未产生新字节账。 |

下表是已占用160的历史诊断文件，不是本轮配方交付。

| 既有文件 | generation | 长度B | SHA-256 | 当前核对 |
| --- | ---: | ---: | --- | --- |
| `firmware/package_v39_diagv4p/GXRCE.DAT` | 160 | 22,372 | `b3e5db12b42edf39f2fc4fe603ee83cdb9ba526b5c270efa736a97b5debbeeb4` | 实际文件长度、头CRC和载荷CRC均有效。 |
| `research/diag_v4p/round1/GXRCE.DAT` | 160 | 21,364 | `cb413b97379e83feada9782ea8ee24b9ec7d86b1519a9c252900e4fa1b9d2a70` | 实际文件长度、头CRC和载荷CRC均有效。 |

首个SHA还有引擎构建副本及历史卡归档副本，均逐字节身份相同。另找到两个1,024B头片段，其声明长度为22,372B；它们单列为片段，不计作完整DAT。总计4个完整且CRC有效的DAT副本、2个头片段，不能据此说有6个完整包。

扫描使用实际 `GXRCE001` 魔数，检查244636个二进制路径，找到2364个该格式头。两个已交付g158包、lutprobe包和EXIF探针中的159赋值分别作二进制/文本阳性对照。文本扫描指定仓库路径，不设8MB截断。扫描清单中的旧审计JSON提及只是引用，不重复计作独立包。原始结果见 `local/generation-scans/initial/result.json`，实际文件哈希与CRC复核见 `local/closeout.json`。

独立历史旁证为 `research/review_diag_v4p/REVIEW.md`，其首段明确绑定同一完整SHA与generation160。不存在仅凭文件名误判的情况。

## 三单元列表

MOUNT、28mm、50mm均未形成新的最终列表。以下仅保留build-r2的候选布局，未装入任何DAT。

| 单元 | 满配01–08候选 | 锁定Look候选 | 新胶片Look优先级 |
| --- | --- | --- | --- |
| MOUNT | GRPos、GRNeg、HC BW、Std、Eterna BB、Leica Classic、Kodachrome25、Gold 200。 | 官方Acros、ARRI 709、M9 STD、instax mini、HNCS HiCon、HNCS LowSat；Tri-X按依赖决定可见性。 | Ektachrome 100、Provia 100F、Portra 800、Kodachrome64、Portra160、Vision3 500T。 |
| 28mm | 同上，01–04逐字节固定。 | 同上。 | 同上，数量尚未做实际预算。 |
| 50mm | 同上，01–04及HC BW/Tri-X组逐字节固定。 | 同上。 | 同上，数量尚未做实际预算。 |

## 准入与路径检查

| 项目 | 本轮状态 |
| --- | --- |
| generation160唯一性 | FAIL，已有实际完整诊断DAT。 |
| 菜单、实际C解析器、BOOT及记忆的基底选择 | 已读关键源码，均看到按实际引用槽位取配置；尚未运行新的混合flags候选，不记作运行验收PASS。 |
| 旧Studio合同与研究打包器 | 已定位旧05统一策略字段和断言，不能原封复用为build-r2验收。 |
| Acros/03/Tri-X逐字节、Filt+1、Y矩阵对照 | 未执行新候选验证，不能把g159的失败反例改记为本轮通过。 |
| 其他5个锁定Look的逐code与全部原有旋钮等价 | 未执行。 |
| Eterna BB/Leica Classic三单元正式准入 | 未执行。保留集、场景、其他ISO、敏感性、整数和128分支全部OPEN。 |
| 记录颜色回执、实际容量、LCD字形 | 未执行。 |
| 原生29、参考整机P1、S重放、PASM、旧记忆拒收 | 未执行，没有本轮成品。 |

实际代码路径的读码记录位于 `local/path-audit.json`。`fx_area_valid`按Look自己的base与flags核对；菜单的默认值和旋钮、`project_compute`、`memory_decode`以及BOOT的compute也读取该base。用户项按自己的base恢复，没有从这些函数观察到统一05的运行时选择。

旧 `studio_installation_contract.json` 仍明确写有 `Look_flags_must_also_equal_unit_slot05_for_this_product_layout=true`，并注明它是额外产品策略。`research/g158/records.py:read_manifest` 也有全体Look对齐05的断言。机主已在build-r2撤销该策略；本轮保留历史文件，不把它当作新的引擎要求，也没有生成修改后的候选合同或调用旧断言打包。实际Studio快照的完整DAT代数表只登记到155，不能据其中的通用Look解析函数就声称Studio已支持新代数。

保留Tri-X的有效GXFX描述符会被 `fx_visible` 枚举；mask=0又会被解析器拒绝。因此隐藏依赖需要另证仅保留被实际配方引用的行，不挂可见描述符；本轮未构造或验证该方案，不宣称Tri-X已隐藏。

## OPEN与现场边界

下一轮首先需要指定并全仓确认未使用的代数。之后仍按build-r2的实际基底规则工作：Acros和03/Tri-X保持flags1，其余锁定Look必须保留已有操作的相同输出，新胶片Look再按flags7安装。任何未证明等价的项都不能出包。

两包的BOOT诊断预期还须按实际原逻辑区分。g158 test换代干净拒收为B21/R3；release关闭BOOT，原复审记录为B02/R3。若引擎逻辑保持不变，不能把release的B02改写成已经观察到B21。后续新包需重跑并报告真实诊断值。

未接触相机、SD卡或网络，未安装依赖、commit、push或开子agent。既有诊断DAT只读核对，未移动或清理。没有向 `firmware/engine_v71_g160/` 或两包目录写入任何文件。现场停止说明见 [OWNER_STEPS.md](OWNER_STEPS.md)。

所有Python用 `-I -B` 和实际nice15。扫描单作业通过 `loadgate.workers()`；未并发派发新计算队列、未做墙钟计时实验。固件、派生字节及原始扫描只保留在忽略的 `local/`，公开报告不写固件地址。

## 复核

下面命令只核对现有占用文件、受保护输入及停止条件，不生成DAT。

```sh
nice -n 15 python3 -I -B research/g160/closeout.py
```

若要重新扫描，使用新的tag保留现有清单；该脚本检查的是160，不会代选其他代数。

```sh
nice -n 15 python3 -I -B research/g160/generation_scan.py --generation 160 --tag independent-review
```
