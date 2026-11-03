有缺陷

两小时时间盒内验收未收齐，状态为 INCOMPLETE_TIMEBOX。未观察到产品断言失败；中止记录来自旧参考接口、适配假设和诊断目录围栏，不能当作产品结论。尚缺：settings_cases-mount, batch-safety-50mm, batch-locked-50mm, batch-nested-50mm, batch-cutpoints-50mm, batch-exits-50mm。

DAT SHA256：`5ca22d7b3115c9d7a4a556ee1fcb9105b7768e9fac4250873ea10689f1db3980`，89,556 B。主请求 107,744 B，上限 108,124 B，余量 380 B。BSS 10,684 B。第七段 20,776 B 与 gen 129 相同，包内 29 个固定文件与 gen 120b 相同。

相对 gen 129，九个同名源码文件变化，构建入口改名为 build131.py，91 个文件不变。三个服务源文件与 g130 冻结清单一致，唯一产品行为变化为 H07 归属规则及入口绑定。knobs 与 resident 源码不变。完整差异见 source-change-vs-g129.patch 和 evidence/source-scope.json。本轮没有改产品源码或重建包。

变化文件为 candidate/engine_services/services.c、engine_services.h、native_seed.c，以及 candidate/containers/product/adapter.c、src/firmware/card_container_v2/gate.c、src/firmware/engine/core/eng_data.c、ui_v2_data.c、candidate/common.py、candidate/containers/product/pack.py。服务层使用 g130 规则，adapter 绑定入口；三个校验点和构建脚本只改 generation 或路径。

| 编号 | 队列项目 | 返回码 | 状态 |
| --- | --- | --- | --- |
| 0 | h07-parent-28mm | 0 | PASS |
| 1 | h07-parent-mount | 0 | PASS |
| 2 | h07-parent-preview-50mm | 0 | PASS |
| 3 | h07-parent-preview-28mm | 0 | PASS |
| 4 | h07-parent-preview-mount | 0 | PASS |
| 5 | host-and-static | 0 | PASS |
| 6 | preview-window-50mm | 1 | OPEN_P2_03 |
| 7 | preview-window-28mm | 1 | OPEN_P2_03 |
| 8 | preview-window-mount | 1 | OPEN_P2_03 |
| 9 | preview-window-observed-50mm | 1 | OPEN_P2_03 |
| 10 | preview-window-observed-28mm | 1 | OPEN_P2_03 |
| 11 | preview-window-observed-mount | 1 | OPEN_P2_03 |
| 12 | preview-window-confirm-50mm | 1 | OPEN_P2_03 |
| 13 | final-h07-parent-50mm | 0 | PASS |
| 14 | final-h07-parent-28mm | 0 | PASS |
| 15 | final-h07-parent-mount | 0 | PASS |
| 16 | final-h07-parent-preview-50mm | 0 | PASS |
| 17 | final-h07-parent-preview-28mm | 0 | PASS |
| 18 | final-h07-parent-preview-mount | 0 | PASS |
| 19 | final-target-gate | 0 | PASS |
| 20 | ownership_settings-50mm | 0 | PASS |
| 21 | ownership_settings-28mm | 0 | PASS |
| 22 | ownership_settings-mount | 0 | PASS |
| 23 | target-math | 0 | PASS |
| 24 | cold_reentry-50mm | 0 | PASS |
| 25 | cold_reentry-28mm | 0 | PASS |
| 26 | cold_reentry-mount | 0 | PASS |
| 27 | cold_exit-50mm | 0 | PASS |
| 28 | cold_exit-28mm | 0 | PASS |
| 29 | cold_exit-mount | 0 | PASS |
| 30 | settings_cases-50mm | 0 | PASS |
| 31 | settings_cases-28mm | 0 | PASS |
| 32 | settings_cases-mount | 未完成 | INCOMPLETE_TIMEBOX |
| 33 | batch-safety-50mm | 未完成 | INCOMPLETE_TIMEBOX |
| 34 | batch-locked-50mm | 未完成 | INCOMPLETE_TIMEBOX |
| 35 | batch-nested-50mm | 未完成 | INCOMPLETE_TIMEBOX |
| 36 | batch-cutpoints-50mm | 未完成 | INCOMPLETE_TIMEBOX |
| 37 | batch-exits-50mm | 未完成 | INCOMPLETE_TIMEBOX |

H07 两类用例共六个最终记录均通过，晚到 S store 和预览计数均为 0，首发 mode=1、WB=9/9。三个单元的 H01 重开记录均为 mode=1、WB=9/9。全菜单点 S 计划 3,430 项与 gen 127 相同。目标 M32R 计算分别 1,133、1,134、1,163 项通过；12 个改动函数的四类编译码检查绑定当前 DAT 与 ELF。通信复核状态 PASS，完整记录 23627 条。

P2-03 保持 OPEN。七次 preview-window 队列项原返回码均为 1；三个单元的补充观察各命中一次，晚到 S store 为 0、晚到预览为 1。此窗口未改动。

旧参考把 knobs v2 默认向量按旧 tone 等级解释。新 reference_v2.py 适配十维向量、旧默认值以及旧 DAT 解码器清零的 36 个未映射字节；3,430 点与 24 个旧解码默认值复核通过。旧比较断言保留。失败准备记录在 local/preparation，当前结果及未运行范围以 evidence/timebox-result.json 为准。

用户已停止上一轮两个 cold_reentry-50mm 孤儿进程。本轮第 24 项重新完整执行并返回 0，旧残留不计结果。结束时停止本轮仍在运行的检查进程，未完成项不记作通过。

写入围栏仅允许三个指定目录，拒绝网络。冻结输入 28,614 项和 103 个源码及清单文件均未变化。理光字节只在被忽略的 local/。没有访问相机、存储卡或网络，没有启动子代理。

静态已证：源码范围、布局、四类编译码、包及最终 DAT 身份。
主机已证：表中 PASS 项、S 计划、H01、目标计算及上述通信记录。
推断：入口绑定与已通过 H07 计数一致。
未知：未完成队列项，以及相机端调度、显示、拍摄、存储持久性和物理断电表现。完整 81 组回归未运行。
