有缺陷

# gen 129 knobs v2 集成报告

本轮以指定 gen 127 快照接入已验收的数据、菜单和数学模块。结论只覆盖本任务的聚焦检查，完整历史回归由独立验收承担。没有连接或操作相机、存储卡，也没有使用网络或启动子代理。

最终 DAT 为 `b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48`，generation 为 129。基线 DAT 为 `9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6`。

## 接线与冻结边界

运行态统一使用 `UvLevels` 的 `int16_t v[10]`。默认 Amount 为 100，其他项目为 0；会话、八个配方缓存、32 条只读条目的会话草稿、当前态和确认态都保存完整 20 B。补偿默认向量也保留 Amount=100，4+2 次边界保持原样。

`compute` 和 `project_compute` 从不可变配方重新展开，经 `kv_data_request` 后调用 `kv_apply_work`。2,288 B 的 `KvWork` 放在会话 BSS；先复制原配方，避免共用展开缓冲造成两份底子同址。旧调节数学不再进入最终符号表。没有增加目标堆分配或额外租约。

第七段为 `1,408 + 1,984 + 17,384 = 20,776 B`，三个长度 gate 同步更新。GXTM 与 GXUI v1 继续独立校验，新整数块按原 SHA 使用。旧只读记录仍校验 11 个字段，转换为新向量后再调用 `kv_data_request`。

S 计划保留 gen 127 的 Image 与配方 WB 对，顺序和值都不随新向量变化。`make_plan`、`settings_match` 和归属相关函数的冻结检查见 [编译复核](codegen.json)；`engine_services/services.c` 与基线逐字节相同。

## 尺寸

| 项目 | 实际 B | 设计估算或预算 B | 有效上限 B | 距有效上限 B |
|---|---:|---:|---:|---:|
| DAT | 89,308 | 88,700 | 98,304 | 8,996 |
| 引擎段 | 60,388 | 59,524 | 65,536 | 5,148 |
| BSS | 10,684 | 11,920 | 25,380 | 14,696 |
| DAT 与 BSS | 99,992 | 100,620 | 114,688 | 14,696 |
| loader 主请求 | 107,496 | 108,124 | 122,192 | 14,696 |

主请求另受本任务 108,124 B 预算约束，余量为 628 B。引擎段比设计估算多 864 B，BSS 比估算少 1,236 B；合计满足主请求预算。BSS 的有效上限随 DAT 长度变化。重定位表为 1 项、8 B，新整数块没有逐项指针。

本构建采用 `-Oz`，固定八行界面的字形与引用数组容量缩为八，较十六容量减少 720 B BSS。真实空闲连续堆尚未确认，不能用上述静态余量代替。

## 聚焦检查

在三小时时间盒内未收齐聚焦验收。没有观察到产品行为断言失败；“有缺陷”表示仍有验收缺项，不能标为“可以交复审”。下列结果只采用最终 DAT 的证据。

主机同一源码完整比较 13,330 例 r2 金标准及 2,504 例扩展请求，逐例比较 552 B、返回码及统计。集成路径检查 3,430 个菜单点，24 个默认值、3,430 个 S 计划与 gen 127 相同；18 组 Amount=0 和 66 组回零序列通过。

三个单元的实际 M32R 计算路径分别完成 1133 / 1134 / 1163 例，覆盖每个配方和项目。计算入口含外层调用链的最大观测栈深为 376 B；数学相关具名函数最大帧 96 B。适配器与原生模型路径的 SP 最大观测为 1276 B。编译码四类清单覆盖 142 个函数，最终 ELF 没有未解析符号、系统 libc 或浮点依赖。

已完成的菜单专项记录 26 次九行、C/D、T 和完整向量核对，以及 418 个实际适配器发布帧。50mm 七种视图与八个端点检查通过。28mm 与 mount 各完成 04、06 的 Splt 序列；其余菜单项目未收齐，详见 [部分运行记录](partial-menu.json)。

数值目标执行、菜单模型叶函数和物理相机的边界见 [专项模型边界](MODEL_BOUNDARY.md)。通信状态及流覆盖范围见 [通信结果](communications.json)。

| 检查 | 状态 |
|---|---|
| host | 已完成，绑定最终 DAT |
| codegen | 已完成，绑定最终 DAT |
| target-50mm | 已完成，绑定最终 DAT |
| ownership_settings-50mm | 已完成，绑定最终 DAT |
| cold_reentry-50mm | 已完成，绑定最终 DAT |
| product-50mm | 已完成，绑定最终 DAT |
| target-28mm | 已完成，绑定最终 DAT |
| ownership_settings-28mm | 已完成，绑定最终 DAT |
| target-mount | 已完成，绑定最终 DAT |
| ownership_settings-mount | 已完成，绑定最终 DAT |
| cold_reentry-28mm | INCOMPLETE |
| product-28mm | INCOMPLETE |
| cold_reentry-mount | INCOMPLETE |
| product-mount | INCOMPLETE |
| communications | INCOMPLETE |

## 证据与未知项

数学结果、完整深层条目与模型写入已分开核对。Amount=0 只表示深层条目恢复原厂 04，S 计划仍保留该配方原有 WB 对。06 的 Splt 回零保持自己的 C/D 和 T=0。

LCD、JPEG、真实堆余量、RTOS 水位和实际操作延迟均未知。没有把主机表的可见性预测作为相机验收。基线复审仍按用户安排独立处理，本轮没有合并其他变更。

源码差异见 [相对 gen 127 的差异](source-vs-g127.patch)，入口见 [复核步骤](REPRODUCE.md)，过程修正见 [开发记录](development.tsv)。[用户上机清单草稿](CAMERA_CHECK_DRAFT.md) 限定 50mm、9 分钟。

30 文件包位于 `firmware/package_v36_g129/SD_ROOT`，其中 29 个固定文件与 gen 120b 相同。理光派生字节只保存在被忽略的 `local/`；`SD_ROOT` 指向包内的该目录。`SHA256SUMS` 以仓库根为基准。

## 未完成项

三小时时间盒内未收齐 28mm 与 mount 的完整菜单专项、冷重入，以及三单元完整通信流。50mm 的菜单专项、冷重入和通信流已完成；其余项目保持 INCOMPLETE。

cold_reentry-28mm, product-28mm, cold_reentry-mount, product-mount, communications
