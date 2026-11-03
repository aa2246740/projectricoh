有缺陷：gen 122 有两个已确认 P1，不能上卡。

已按编排者更新停止剩余回归。三条正在运行的确认命令自然结束后，调度进程退出，没有再启动下一条。只补完通信记录复核器、证据清单与实际状态记录。

DAT 为 firmware/package_v36_g122/SD_ROOT/GXRCE.DAT，63,380 B，generation 122，SHA256 `9724268c3d8a2c8c60650b903db1d536ca6ab594f95144d5991cb3b964ebb262`。固件源码、DAT、卡包均未改变；未写 engine_v45_verify、package_v36_g123、g123_fix，未操作相机、存储卡或网络，未启动子代理。

## 已确认缺陷

独立复审确认 P1-01：哨兵以外的行内部分复位会被当作核对成功；P1-02：H01 推迟核对后，原生半按退出可以不调用 DAT。50mm 的模型与原生反例已成立；28mm/MOUNT 的对应原生反例本轮未执行。来源为 [独立复审](../../review_g122/REVIEW.md)，本轮只读该报告，未修复或重复执行其用例。RPC 地址复核通过不关闭这两个行为缺陷，也不证明一条哨兵代表整行。

## A：通信记录复核器

正式入口为 `research/g122_keep_list/audit_records.py`，同内容副本在 `research/g122_keep_list/r2/audit_records.py`。仅依赖 Python 标准库，不导入某代构建目录或 common.py。DAT、记录位置和输出路径均显式传参，从 DAT 的 M+32+12j 解析九行映射及 T，按其真实 SHA 筛选记录。适用于本项目相同 DAT 布局的其他 generation，已用 gen 121 的原 DAT 和三份已有日志验证复用，未运行旧代回归。

完整 RPC 流必须有 cmd/value/page/result/t；故障事件摘要单独登记，不当作通信流。显式 rpc_log 缺少完整记录仍判失败。每次 X/V/W 检查映射范围，半字边缘 W 必须保留前序读回的相邻字节；失败无设备效果时不推进游标，先产生效果再报失败时依据 device_result 处理。带 page_before/page_after/address 的恢复轨迹另行识别。

在仓库根复核已有三份主矩阵：

```sh
/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py \
  --dat firmware/package_v36_g122/SD_ROOT/GXRCE.DAT \
  --records research/g122_keep_list/native/matrix-50mm.json \
            research/g122_keep_list/native/matrix-28mm.json \
            research/g122_keep_list/native/matrix-mount.json \
  --output research/g122_keep_list/r2/matrix-record-safety.json
```

三单元均 PASS，18 份故障事件摘要被正确识别。三份矩阵本身没有完整 rpc_log，结果中的 coverage.raw_streams_present 为 false；本次检查记录类型、原生写入来源、文件计数与矩阵已有的运行时范围记录，没有虚构不存在的原始通信流。

另对现存完整日志、三份 open-counts 与 machine-gates 重跑，三单元均 PASS，共 99 条去重流。两次正常重开的哨兵半字完全在行内。证据见 [主矩阵复核](matrix-record-safety.json)、[完整日志复核](record-safety.json)、[14 项复核器检查](auditor-checks.json)、[gen 121 复用结果](reuse-gen121.json)。旧 FAIL 保留在 [before/record-safety.json](before/record-safety.json)。

| 单元 | 完整流 | X | V | W | 边缘保留检查 | 结果 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| A12 50mm | 33 | 742 | 7040 | 5985 | 81 | PASS |
| A12 28mm | 33 | 716 | 7040 | 5985 | 81 | PASS |
| MOUNT A12 | 33 | 706 | 7025 | 5815 | 81 | PASS |

下一代执行者可替换以下三个路径参数复用：

```sh
/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py \
  --dat /absolute/path/to/GXRCE.DAT \
  --records /absolute/path/to/records-or-json \
  --output /absolute/path/to/record-safety.json
```

`--records` 接受多个文件或目录，目录递归读取 JSON；单元顺序固定为 50mm、28mm、mount。不同 DAT SHA 的文件列入 excluded_other_dat，不计为本候选通过。可选 `--sentinel-records` 只用于显式提供 gen 122 的 20 次调用样本；下一代取消该路径时省略。它只证明读取地址在行内。

## B、C：已跑与未跑

本轮实际执行 15/66 条缺失命令，每单元五条，全部返回 0。加上前轮已确认的 retain、measure，各单元为 7/24，只有五条是本轮运行。完整 argv、cwd、输入摘要、耗时、返回值与日志 SHA 在 commands-50mm.json、commands-28mm.json、commands-mount.json；stdout/stderr 在 logs/，实际产物摘要见 [completed-check.json](completed-check.json)。

| 已跑功能 | A12 50mm | A12 28mm | MOUNT A12 |
| --- | --- | --- | --- |
| A–H 原路径 | PASS，rc=0，1474.7 s | PASS，rc=0，1476.4 s | PASS，rc=0，1460.3 s |
| H07 全状态 | PASS，rc=0，244.5 s | PASS，rc=0，244.8 s | PASS，rc=0，245.6 s |
| Fn2 失败情形 | PASS，rc=0，423.3 s | PASS，rc=0，419.8 s | PASS，rc=0，416.1 s |
| 原生退出 | PASS，rc=0，155.1 s | PASS，rc=0，155.3 s | PASS，rc=0，154.5 s |
| 确认与 ADJ | PASS，rc=0，≤ 280.6 s | PASS，rc=0，≤ 281.9 s | PASS，rc=0，≤ 301.6 s |

三条确认命令自然结束后，退出码从仍由调度器持有的僵尸进程 xstat 读回，均为 0。其耗时是日志创建至观察到退出的上界。停止过程与 PID/出生身份记录见 [scope-stop.json](scope-stop.json)。

每单元另外 17 条、共 51 条没有执行：latch_paths、native_names、entry_switch fn2；concurrent_menu 的 recovery/fallback/nested 与 other_menu 五个切点；ui_cutpoints 两项；coalescing 两个切点；failure_boundaries 两项。acceptance.json 对这些项目标记 NOT_RUN_SCOPE_STOPPED，record 保持 null。

工作区与 UI 分配失败后重试、ERR 原因码/单行光标/空说明、列表与面板各 16 轮三个新功能组均未运行。完整 keep-cases 36 例也未启动；只保留前轮每单元 12 例核心组合，不算完整覆盖。

## D：清单与输入

旧 EVIDENCE_SHA256SUMS 有 359 项，其中 100 项不符。已保留旧清单，并按 engine_v44_keep 重新生成 377 项，仅排除清单自身，路径以该目录为基准，hashlib 与 shasum 逐项自检通过。见 [evidence-manifest.json](evidence-manifest.json)、[自检输出](evidence-selfcheck.log)、[旧清单](before/EVIDENCE_SHA256SUMS)。

固件源码差异为零；engine 目录唯一修改为该证据清单；卡包 30 个文件未变，29 个固定文件仍与 gen 120b 相同。见 [input-stability.json](input-stability.json)。受保护输入检查覆盖 37,836 项。验收工具调整包括复核器、local/ 缓存与夹具路径，以及本轮未使用的强制重跑开关，见 [test-tools.patch](test-tools.patch)。

仓库根基准的 ../SHA256SUMS 最后重新生成，覆盖 g122_keep_list、engine_v44_keep、package_v36_g122 全部普通文件，仅排除清单自身；hashlib/shasum 自检和 CARD_SHA256SUMS 完整 30 项核对见 ../checksum-selfcheck.json。

范围缩小后交回时限为 30 分钟。报告写于 2026-10-28T08:13:33.300310+00:00。

## 三单元完整验收表

除本轮五条命令与 A 外，保留的 PASS 来自前轮同 SHA 的已核实记录；已接受的 resident、拍摄及说明区限制保持原状态。

| 功能组 | A12 50mm | A12 28mm | MOUNT A12 |
| --- | --- | --- | --- |
| 原审查主矩阵 | PASS | PASS | PASS |
| 原始通信日志复核 | PASS | PASS | PASS |
| 四参数全部 RPC 与 preview 切点 | PASS | PASS | PASS |
| 其余原审查 24 条命令 | STOPPED_USER_SCOPE 7/24 | STOPPED_USER_SCOPE 7/24 | STOPPED_USER_SCOPE 7/24 |
| W 前失败保留列表和面板，三种入口重试 | PASS：前轮 12 核心例 | PASS：前轮 12 核心例 | PASS：前轮 12 核心例 |
| keep-cases 完整 36 例 | NOT_RUN_SCOPE_STOPPED；前轮仅 12 核心例 | NOT_RUN_SCOPE_STOPPED；前轮仅 12 核心例 | NOT_RUN_SCOPE_STOPPED；前轮仅 12 核心例 |
| H01 首开核对失败仍发布八行，三种入口重试 | PASS | PASS | PASS |
| d1：连续三次 W 前通信失败后重试 | PASS | PASS | PASS |
| d2：部分 W 后连续四次通信失败后恢复 | PASS | PASS | PASS |
| d3：ready 临时为 0 后恢复 | PASS | PASS | PASS |
| 四次确认配方、一次或两次 04、再试原目标 | PASS | PASS | PASS |
| DISP 原始键打开面板、循环四参数、保留结果 | PASS | PASS | PASS |
| Fn2 切走再回来 | PASS | PASS | PASS |
| W 前两个 ready 边界 | PASS | PASS | PASS |
| 工作区与界面分配失败后重试 | NOT_RUN_SCOPE_STOPPED | NOT_RUN_SCOPE_STOPPED | NOT_RUN_SCOPE_STOPPED |
| ERR 原因码、单行光标及空说明 | NOT_RUN_SCOPE_STOPPED | NOT_RUN_SCOPE_STOPPED | NOT_RUN_SCOPE_STOPPED |
| 列表与面板合并循环各 16 轮 | NOT_RUN_SCOPE_STOPPED | NOT_RUN_SCOPE_STOPPED | NOT_RUN_SCOPE_STOPPED |
| 四参数各 20 格通信计数 | PASS | PASS | PASS |
| 十六种相邻行转换计数 | PASS | PASS | PASS |
| resident 三种 H01 入口限制的边界核对 | PASS | PASS | PASS |
| H01 核对中视图切换：DAT 不改其他界面 | PASS | PASS | PASS |
| H07 keep=0 且重试仍失败后的界面保留 | INCOMPLETE_FIXED_RESIDENT：固定收尾会关闭 | INCOMPLETE_FIXED_RESIDENT：固定收尾会关闭 | INCOMPLETE_FIXED_RESIDENT：固定收尾会关闭 |
| 参数名预算与原生文字路径 | PASS：Shadow，其余保留短名 | PASS：Shadow，其余保留短名 | PASS：Shadow，其余保留短名 |
| 拍摄前缀 (a) ADJ 离开后半按、全按、重开 | INCOMPLETE_DEVICE_REGISTER | INCOMPLETE_DEVICE_REGISTER | INCOMPLETE_DEVICE_REGISTER |
| 拍摄前缀 (b) 列表内半按、全按、重开 | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION |
| 拍摄前缀 (c) Fn2 往返后半按、全按、重开 | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION |
| 说明区 DISP: Tweak 提示 | 未实现：非空说明记录不受当前接口支持 | 未实现：非空说明记录不受当前接口支持 | 未实现：非空说明记录不受当前接口支持 |
| 说明区非锁定短诊断码 | 未实现：依赖同一说明记录约定 | 未实现：依赖同一说明记录约定 | 未实现：依赖同一说明记录约定 |
| 哨兵检测行内部分复位 | FAIL P1-01：独立模型反例 | OPEN：数据枚举有未覆盖位置 | OPEN：数据枚举有未覆盖位置 |
| H01 推迟核对后半按退出 | FAIL P1-02：独立原生反例 | OPEN：未跑该原生反例 | OPEN：未跑该原生反例 |
