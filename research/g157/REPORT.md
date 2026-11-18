可以交复审

# g157 复审修复 r1

P1-01 的旧版原样反例已复现；新包手动事务在首个 W 前设置 DIRTY/GUARD，失败后直接从可信纯 04 完整补偿，不再采集半写入的现场作为恢复前提。只有完整颜色及设置成功后才清除护栏；补偿失败保留保护，由原有 H52 拦半按及全按。正常取消预览仍恢复已确认配方。BOOT 门、机身、resident 和配方清单均未改。

本轮时限为 2026-11-04 17:57:05 至 21:57:05 UTC。最新回执时间 2026-11-04T21:20:34.644831+00:00。这份结论交给下一轮独立复审，不等于批准上卡。

| 包 | SHA-256 | DAT B | 代码 B | BSS B | 主请求 B | 上限余量 B |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| test | `2b8904592ce56ab03649ced52c8479b0bbac4e45bf9a47505d220795bb3ec56c` | 94,868 | 69,540 | 4,360 | 106,856 | 756 |
| release | `3ebc261cf290a376d59ffc24b4d5b6f9ab1dd5b9d5a8cd7242561d45707107b6` | 92,400 | 67,308 | 4,360 | 104,388 | 3,224 |

数字来自实际 ELF 链接；主请求上限 107,612 B、代码上限 69,632 B 均未放宽。两包各缩小 36 B，没有删配方或改变槽位策略。test 开 BOOT，release 关 BOOT；诊断和读回均开。

## 验收回执

| 项目 | 状态 |
| --- | --- |
| original-counterexample-native-and-reference | PASS |
| fixed-MOUNT-whole-MAIN-native-and-reference | PASS |
| g156-test-same-W8-fault | PASS |
| C-every-W-all-units-profiles-entries | PASS |
| fast-ISA-test-50mm | PASS |
| fast-ISA-test-28mm | PASS |
| fast-ISA-test-mount | PASS |
| final-Python-ISA-test | PASS |
| fast-ISA-release-50mm | PASS |
| fast-ISA-release-28mm | PASS |
| fast-ISA-release-mount | PASS |
| final-Python-ISA-release | PASS |
| actual-service-ISA-key-edges | PASS |
| persistent-whole-MAIN-test | PASS |
| persistent-whole-MAIN-release | PASS |
| native-test-50mm | PASS |
| reference-test-50mm | PASS |
| native-test-28mm | PASS |
| reference-test-28mm | PASS |
| native-test-mount | PASS |
| reference-test-mount | PASS |
| native-release-50mm | PASS |
| reference-release-50mm | PASS |
| native-release-28mm | PASS |
| reference-release-28mm | PASS |
| native-release-mount | PASS |
| reference-release-mount | PASS |
| host-C-and-final-Python-data-memory-services | PASS |
| S48 | PASS |
| all-byte-audit-against-reviewed-g157 | PASS |
| actual-UI-text-and-independent-glyphs | PASS |

产品 C 故障矩阵 33,996 例通过，覆盖两包、三个单元、Standard/Vivid09/WB 三种入口及 HC BW +1、Acros、用户项 3、05 四种目标。 最终 DAT 快指令矩阵已完成 6/6 组合，共 16,644 例；逐个实际 W 位置注入回执失败和 BUSY，并核对完整颜色或实际护栏以及 H52 半按/全按结果。 独立 Python 指令后端另完成 2/2 个 MOUNT 组合，共 220 例关键边复核。

逐项断言和完整身份在 `local/fix-r1/FINAL.json`。只接受正常收尾且最终 SHA 相符的回执；未完成项保留 OPEN。

两包 MOUNT 的原反例都已从新 MAIN 在 strict_r4 native 和独立 Python 参考设备后端重跑。新包输入仅更新 DAT 绑定及记录、整块校验，Vivid09、WB 9/9、HC BW +1 和单次故障策略不变。每次实际 W8 写入已经发生，只把一次原厂回执改为失败；四次均完整补偿为纯 04，设置为 Standard、WB 9/9，再清除护栏。旧版 native 两包及 test 参考则仍可观测到半套颜色、state 5 取景和零护栏。

g156 test 已用相同 Vivid09、WB 9/9、合法 HC BW +1 记忆输入和实际 W8 单次回执故障复现：关闭 ADJ 后仍是半套颜色、零护栏的取景状态。因此该手动事务 P1 在 g156 已有。g156 在 Vivid 下不预选该记忆，实际使用 UP 选中 HC BW 默认参数；不能把它说成与 g157 记忆预选 OK 完全相同的入口。证据在 `local/fix-r1/g156/runs/same-W8-vivid-dismiss/`。

C 矩阵执行产品事务、配方计算及显式 peer 故障。全量快速指令矩阵执行最终 DAT 的事务、补偿和 H52，服务/peer 是声明边界，纯计算缓存来自该输入的真实 DAT 指令执行；它不计作冷启动整机次数。真实服务指令另测关键边，原生与参考整机分别从新 MAIN 启动，不恢复 CPU 或设备快照。S48 是完整逻辑 S 的原样/仅校验双组交叉重放，不证明实际关机 NAND flush。

LCD 没有像素输出。替代证据为实际发布的首次 ADJ、诊断及返回列表的八行文本、逐字符 glyph 和映射，原厂转换器用独立 Python 指令复核。这不是像素截图，路径为 `local/fix-r1/final/ui-text/ui-text-{normal,diagnostic}.{md,json,tsv}`。

## 字节与数据

相对 `local/fix-r1/before/` 冻结的上一版 g157，所有差异位置都有逐字节 TSV、ELF 函数及重定位归属。apply_impl 增加 104 B，recover_confirmed 减少 140 B；后续函数的调用地址和数据位置随链接移动。配方清单、各数据节、所有展开的 552 B、body/resident ABI 保持一致，仅 adapter.c、eng_core.c、eng_core.h 三个产品文件改变。

| 包 | 不同或删除位置 | 文件变化 B | 未解释 B |
| --- | ---: | ---: | ---: |
| test | 49,282 | -36 | 0 |
| release | 48,953 | -36 | 0 |

完整审计在 `local/fix-r1/byte-audit-{test,release}.{json,tsv}`。旧报告和旧 DAT、ELF、源码留在 `local/fix-r1/before/`；本轮首错和夹具修正保留，不用失败或半完成记录填 PASS。早期数据对照列不需要补：历史数据接入已经证明引擎归一后逐字节等价，本轮配方数据完全未变；本轮事务代码的改动另按新 SHA 全面验收。

验收脚本修正包括：首轮 MOUNT 遍历漏带本地数学库，已核对基础槽/Look 但不计整流程，通过新 r2 label 从 MAIN 重跑；C 新增 05 目标最初误取 03 的 identity，计算入口正确拒绝后修正；首次 ADJ 导出的 part=0 仍属构造阶段，函数探针改为显式声明合法的 part=1 手动入口。上述修正未改变 DAT，失败回执继续保留。

## 现场与保留项

P2-01 只改文档：必须先在 g157 成功保存纯 04，再换回 g156。仅在 g156 选 04 不能覆盖它不认识的高索引尾部。两个包的 README 和[现场步骤](OWNER_STEPS_MOUNT.md)均写明这个顺序。

P2-02 的 BOOT 门保持原样。机主固定 M 时，若模式/原厂选择组合仍被拒，预计 B11；activity 不合格优先 B10，未派发 B01。初次换包旧绑定可能另有 B21，Vivid/WB 不符为 B20。release 策略关闭时为 B02。真实 M 的内部值尚未采到，现场须保留首次 ADJ 的完整八行及开机首拍。

P2-03、P3 按用户要求保留 OPEN：现场掉表及装载责任、DAT 缺席或 resident 退役时的诊断、实机连续堆/碎片余量、真实关机与 NAND、单元持久状态、首拍及 JPEG。未实现配套 resident 诊断；未碰相机、实际 SD 卡或网络，未安装依赖、commit 或 push。

