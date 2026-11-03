可以交复审

gen 126 只增加列表发布后的原生设置核对及引擎仍拥有界面时的 H07 核对，并同步本代 generation 校验。最终 DAT 为 58,360 B，SHA256 `a855adcf3aaeaaa427b5ea43816c2cb7acd71fc9ceb7973bf8db3af8d6b1610d`。交付目录为 `firmware/engine_v47_fix`、`firmware/package_v36_g126`、`research/g126_fix`。

## 修复

`list_bind_impl()` 在八行服务返回后调用 `eng_check_settings()`，不依赖 committed 或 recheck。H07 在确认前调用同一函数。永久锁定时仍走原有锁定路径，不恢复设置，不增加通信。

新函数复用 `settings_match()` 读取 settings 租约并逐字段比较原 `make_plan()` 的计划。没有成功应用记录时 current 初始化为纯 04；已有成功应用时采用当前已验证的配方及 RAM 档位，包含既有浏览预览，以保留原有浏览和确认规则。核对已确认配方时使用该配方计划。失败后的补偿目标仍由未修改的 `recover_confirmed()` 选取已确认配方或纯 04。

不一致时复用 `apply_impl()` 的 settings 服务及 preview 服务。`make_plan`、settings 服务、九行和 T 通信路径、RPC 类型、S 地址、锁定条件均保持原样。源差异见 [source-change-vs-g124.patch](source-change-vs-g124.patch)。本代的三个 C 校验只把 generation 124 改为 126；GXUI124 格式标识保持不变。当前三个单元的 24 条原配方记录均为原生 mode=1，实际计划包含 Image mode 与两条 WB；其他模式的专属字段分支由逐字未改的 make_plan 保留，本轮只核对源码和编译码，不列为本包真实数据的运行覆盖。

## 首次发布和退出

三个单元各四个 cold_reentry 切点全部绑定最终 DAT。七行窗口的原生方向键仍可写 `S+0x36e`；向下键短暂变成 5，向上键有同值写入。八行发布后及确认退出后均为 mode=1，WB 两字段符合纯 04，九行和 T 相符。预览服务入口观察到相同计划。这些记录证明最终状态恢复，不能描述成原生没有写入。

原始记录在 `local/cold-reentry/`，逐条哈希和切点结果在 [acceptance.json](evidence/acceptance.json)。参考代结果在 `local/cold-reentry-reference/`，分别保留 gen 124 与 gen 121 的首次发布状态。

设置补充案例分别改变 mode、WB 两字段以及组合，在纯 04 和确认配方 05 上走发布、OK、ADJ。正常服务案例要求最终完整计划、九行、T 和预览一致。服务失败情形单列，不计作成功恢复。

## 恢复失败边界

处理沿用原 settings 失败分支：已发生 W 且仍不确定时进入原确认配方补偿；没有 W 时清除本地 uncertainty 并返回原错误，不能据此触发永久 W 锁定。现有 finish/keep_view/release_view 处理失败。模拟 settings 失败后，错误设置可保留到撤回的原生七行视图；服务恢复后下一次打开再核对恢复。preview 服务失败时设置可已正确，但没有成功刷新证据，不能算预览一致。永久通信失败的部分 W 和 ERR 锁定仍是继承边界。

补充记录在 `local/settings-cases/`。它们分别记录正常恢复、模拟服务失败当次状态和下一次打开状态。最初补充测试把服务失败也要求立即成功，已更正为观察现有失败返回；固件未因此增加重试或改变锁定规则。

## 回归

| 套件 | 50mm | 28mm | MOUNT |
| --- | --- | --- | --- |
| 首次发布 | 4 例通过 | 4 例通过 | 4 例通过 |
| 未提交会话的 H07 | 2 例通过 | 2 例通过 | 2 例通过 |
| gen 122 反例 | 9 例通过 | 9 例通过 | 9 例通过 |
| 安全边界 | 8 例通过 | 8 例通过 | 8 例通过 |
| 锁定 | 8 例通过 | 8 例通过 | 8 例通过 |
| 锁定重入 | 30 例通过，10 个旧路径已删除 | 30 例通过，10 个旧路径已删除 | 30 例通过，10 个旧路径已删除 |
| IRQ 开启时切换 | 8 例通过，8 个旧路径已删除 | 8 例通过，8 个旧路径已删除 | 8 例通过，8 个旧路径已删除 |
| 锁定退出 | 24 例通过 | 24 例通过 | 24 例通过 |
| 逐屏六键 | 42 例通过 | 42 例通过 | 42 例通过 |
| 退出行数与 IRQ | 21 例通过 | 21 例通过 | 21 例通过 |
| 档位端点 | 7 例通过 | 7 例通过 | 7 例通过 |
| 七视图方向键重入 | 70 例通过 | 70 例通过 | 70 例通过 |
| 七视图六键重入 | 210 例通过 | 210 例通过 | 210 例通过 |
| 设置核对及服务失败 | 36 例通过 | 36 例通过 | 36 例通过 |
| 用户条目 | 25 条 FCC 通过 | 25 条 FCC 通过 | 25 条 FCC 通过 |
| 另外七个底子 | 7 条通过 | 7 条通过 | 7 条通过 |
| M32R 档位与窗口 | 1693 个档位 / 8686 个窗口通过 | 1693 个档位 / 8686 个窗口通过 | 1693 个档位 / 8686 个窗口通过 |
| 逐屏文字 | 通过 | 通过 | 通过 |

已删除的 op 2 更新切点保持 `REMOVED_UPDATE_PATH`，不计作触发成功。原生半按的独立记录另列在 acceptance.json。用户条目的 25 条 FCC 与另外七个底子分别执行，元数据保持只读。`commands.jsonl` 保留实际退出码；超时或失败不算通过。

## 通信和编译码

通信由未修改的 `research/g122_keep_list/audit_records.py` 复核，不传哨兵参数。默认 DAT 去重完整流 122 条，用户变体 6 条。默认结果见 [rpc-default-complete.json](evidence/rpc-default-complete.json)，变体见 [rpc-users-complete.json](evidence/rpc-users-complete.json)。通信切点摘要和完整流分开识别，半字边缘 W 保留最近读回的邻字节。

七个改动 C 函数逐一闭合地址与长度、文件操作、原生界面写入、循环与内存四类检查。DAT 内引擎与 ELF 段逐字相同，PIC 平移检查通过；45 个 switch word 由汇编标签和最终链接值核对，未分类可执行异常为零。最大静态函数栈帧 260 B，引擎 46,824 B，BSS 8,844 B。未测 RTOS 栈高水位。

结果见 [codegen-safety.json](evidence/codegen-safety.json)、[compiled-tables.json](evidence/compiled-tables.json)、[binary-inventory.json](evidence/binary-inventory.json)。编译差异中的 ig_init 为三个 generation 比较，ig_panel_open 和 rv_call 的同长度变化为随代码增加而平移的 switch 表基址；表目标仍由链接值核对。

## 保留限制及复现路径

P2-01 保留。最后一次归属核对到原生绘制之间仍有调度窗口，原生绘制会写全局 `0x205d4f64`。最终 DAT 在 50mm 的列表和面板各两个切点均重现旧行绘制及该全局写入，四例的迟到 S 写入为零。见 [p2-01-final.json](evidence/p2-01-final.json)。本修复不把这段描述成原子操作或只有像素写入。

P2-02 的正确原脚本路径是 `firmware/engine_v46_ui/candidate/reproduce124.py`。原目录及原说明保持只读；本目录 [REPRODUCE.md](REPRODUCE.md) 给出正确路径和输出只写新目录的包装命令。gen 124 与 gen 126 均已隔离重建，各自产出的 DAT、引擎、重定位和 48 槽位有效行分别与各自冻结候选逐字一致。48 槽位有效行在两代之间也逐字一致。

## 交付边界

`firmware/package_v36_g126/SD_ROOT` 指向包内的 `local/SD_ROOT`。实际 30 个文件均在该 local 目录，29 个固定文件与 gen 120b 逐字一致。根目录基准的 SHA256SUMS 包含三个交付目录的实际文件，不把符号链接重复计作文件。

冻结项 27,834 个，非预期变化 0 个。另观察到原复审 `research/review_g124/commands.jsonl` 有 20 条追加，冻结前缀逐字保留；其余冻结项均未变。追加命令属于原 gen 124 复审批次，该日志保持原样。本轮源码、编译输入和包输入未发生漂移，详情见 [protected-inputs.json](evidence/protected-inputs.json)。

本任务最终新增只保留三个任务目录。过程有一次补丁路径误写，在许可目录外短暂生成一个无关文本文件和空目录，发现后立即删除。本轮初次构建未带本代 UI 扩展，已同步代际校验并重建；该中间结果没有计入最终验收。

本报告的通过范围是源码、主机编译、最终打包和 M32R 原生重放。没有访问相机、存储卡或网络，没有启动子代理。预览图形叶函数、设备及 RTOS 边界由模型承接，未验实体 LCD、曝光完成、实体断电或上卡行为。
