有缺陷

# diag-v21-raw-r1

实现和 generation 132 包已生成，完整验收在原 90 分钟及获准追加 10 分钟内仍未完成，不能按本任务的全部验收项交复审。缺口是旧补充复审及其汇总、封存未跑完；当前没有把这项缺口记成产品通过。

## 已完成

H 页 BAD 第 2 至 7 行显示原始 32 位值。R 显示 base/end、链根、两个初始化字段及安全可读的链根首字；P/F 显示边界、失败地址和完整头的三个字；N/M/S 使用原保存字段。动态读取先要求四字节对齐及完整 12 B 头在 RAM 内，否则显示 `--------`。第 1 行和末行格式、原有校验条件、其他页面与行为保持原逻辑。差异见 [source-v2.diff](source-v2.diff)，每行含义和旧真机读数判读见 [READINGS.md](READINGS.md)。

| 检查 | 实际结果 |
| --- | --- |
| 原有堆情形 | 43 个完成，138,760 次排版检查通过。 |
| 新增原始值 | 24 个完整 C 采样情形通过，包含 R/P/F/N/M/S、链根不同、容量超限、哨兵非零、状态全字和 RAM 末端。 |
| 最终 DAT 的 BAD 显示 | 9 个情形直接调用编译后的 BAD 数据函数，再逐行核对真实 H 格式；RAM 读边界及 BSS/栈写边界检查通过。 |
| 三单元最终产物 | 50mm、28mm、MOUNT 各两次 ABCDFHA，共 42 次页观察通过。 |
| 旧矩阵 | 20/20 分组返回 0；独立 50mm 功能分组返回 0。旧 411 场景和 874 条复审记录的最终汇总未完成。 |
| review_diag2 | {"heap": "COMPLETED", "static": "PASS", "pages": "PASS", "baseline": "PASS", "capture": "COMPLETED"}。 |
| 独立复编 | DAT、engine.bin、engine.elf、reloc.bin、服务库逐字节相同。 |
| 包 | SD_ROOT 共 30 文件，29 个固定文件与 gen 120b 逐字节相同。 |
| 冻结输入 | 初始 1971 个文件的内容哈希未变。 |

最终 DAT 为 22,020 B，代码 12,412 B，BSS 26,372 B；每份快照 12,460 B。新增两份六字诊断值及有效位共 56 B，原快照字段和块数组偏移未变。主请求为 `1104 + align4(22020 + 26372) + 6144 + 256 = 55896 B`，原生跨度 55,908 B。

```text
097a178a936881583fee22b5c5dee54e15b3d27ad5bd11f147f5fea97bcab227
```

## 未完成项

旧补充复审已完成 4/14 个分组。其余分组标记为 INCOMPLETE_TIME_LIMIT：

- errors-28mm。
- prepublish-28mm。
- preserve-28mm。
- withdrawal-28mm。
- errors-mount。
- prepublish-mount。
- preserve-mount。
- withdrawal-mount。
- reopen-50mm。
- first-service-50mm。

旧复审的最终汇总与封存标记为 NOT_RUN_TIME_LIMIT。后续须按 [COMMANDS.txt](COMMANDS.txt) 继续原路径套件并使用 `review_extra_r2.py --resume` 保留已完成分组，然后运行汇总、验收和重新封存。完整状态见 [verification.json](verification.json)。

## 证据边界和继承事项

静态和主机检查只证明相应源码、包、C 读取器及指令模型层。没有相机、存储卡、网络或子代理操作；LCD、RTOS 调度、物理重启和真实原始 H 值未知。旧真机 BADR0000 只能说明边界或哨兵阶段失败，新版数值尚待真机记录。

P1-03 的既有变化边界仍保留，按任务方变更要求后的豁免处理。P2-03 仍为 OPEN；P1-01、P1-02 的既有例外保持原状。没有修改这些行为。

旧脚本只从原路径载入调用，未查看、复制或打印两个受限目录的脚本源码；异常记录不带源码行。旧 BAD 的显示断言按新格式适配，具体原值由新增固定期望检查；旧五页套件沿用 r2 的 H 检查后额外 DISP 方法。最终 DAT 的额外 9 组检查针对 BAD 数据函数，不能替代完整 capture。

构建和套件受三个新目录的系统写入限制及网络限制保护。理光二进制和反汇编只在被忽略的 local 中。SHA256SUMS 以仓库根为基准，自身除外。
