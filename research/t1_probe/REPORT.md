# T1 逐通道曲线探针

2026-10-20。08 条目和基于 v1 的独立验证表集已生成，Stage 2j C 加载器、普通构建和 ASan/UBSan 验证均通过。相机效果、D 对应的通道及断电后的状态仍未知，本次没有相机验收。

仓库为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。设计沿用 [capability_ladder/REPORT.md](../capability_ladder/REPORT.md) 的 T 探针节；没有沿用旧 t-test 中 07 的控制单独开启探针。

## 交付物与合并

交付目录为 `artifacts/stage2j-packages/tables-t1-probe/`，包含：

- `DEEPTBL0.DAT`、`DEEPTBL1.DAT`，两份完全相同，各 3600 B，DEEPTBL v3。
- `entry08.json`，整条 448 B 条目的合并输入，schema 为 `gxr-deeptbl-entry-v3-1`。
- `manifest.json`，记录来源、差异、验证结果和输入哈希。
- `SHA256SUMS`，覆盖上述文件及 `NOTICE`。
- `NOTICE`，说明用途、相机验收状态和测试后回到 04 的步骤。

SHA-256：

```text
v1 DAT: e5c5d86fdeb61dc4ae4503fc9ac9f6aae9b90ce344b6b01eb0ff98eb3f4e96b9
T1 DAT: fed099d275f1bd06a0ce54cacbfea5d61c7da9d0515e4dc3bdec383ec8b1b7dd
08 entry: ae6216af07eb9dcb8b56bada8528f1517bfc79928d993d1419059296948fc5e9
```

组装时读取 `entry08.json` 的 `entry_hex`，解码为整条 448 B 数据，替换表体中的 entry index 7，即 slot 08。条目的 recipe CRC 绑定既有 08 配方，不能把 04 的 slot 标识或 recipe CRC 原样复制过去。脚本中的 `merge_entry(src, daily_blob, bank, document)` 会校验条目长度与哈希，替换 08，调用原有 `src.seal()` 重封文件，再用 `src.parse()` 检查。后续日用表若更换了配方库，须重新核对绑定关系。

本表集的 `host_validation=pass`、`camera_acceptance=pending`、`firmware_ready=false`。它保留 v1 的其余候选条目及其验收限制。

## 条目与文件差异

静态确认：08 的模式、WB 和参数与 04 一致；A5/B5、24 扇区色表、矩阵、A20/B20 均取 stock。C 为 B5 的 33 个输出值。D 在下标 4..28 加 24，先截到 255，再对全表累计取最大值。脚本独立计算 D，并与原有 `src.t_test_d()` 对照。C/D 都非递减，末值均满足至少 128。

08 的 mask 为 `0x06`，只开 AUX 和 CONTROL，控制半字为 `0x0000`。07 与 v1 的 07 逐字节相同，mask 为 0，没有任何 T 位；本集合中没有 control-only 条目，不需要 F4 例外。

与 v1 相比，总共改变 102 B：文件偏移 12..15 的 CRC 改 4 B，08 条目所在的 3152..3599 范围改 98 B。08 内的实际差异为 mask 1 B、色表 CRC 4 B、色表数据 24 B、C/D CRC 4 B、C/D 数据 64 B、控制值 1 B。其余字段不变。01、02、03、04、05、06、07 的整条 448 B 数据均与 v1 完全相同，entry 0 仍是 stock 04。

## 主机验证证据

构建只导入未改动的 `firmware/stage2j/tools/make_table_files.py` 格式函数及其 `src`，使用 `entry()`、`seal()`、`parse()`，没有调用生成器的 `main()` 或 `--fit`，也没有重跑 v1 拟合。

实际编译 `firmware/stage2j/tests/equiv_driver.c` 及 `verify.py` 指定的七个 C 源文件，沿用 `-std=c11 -O1 -g -Wall -Wextra -Werror`、`RECIPE_FW_HOST`、`RFW_DEEP_ENABLED=1`、`EQUIV_2H`、`EQUIV_2I`。两种构建都以 `extended` 运行 v1 和最终 T1 DAT。消毒构建另外使用：

```text
-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer
```

原始驱动按 `04 → 01 → 02 → 05 → 06 → 07 → 08 → 04 → 03 → 04` 运行。另在 `/tmp/t1_gpt/` 复制驱动，只替换槽位顺序，运行 `04 → 08 → 04`，再逐一检查 04 与其余各槽的往返。仓库中的驱动未改动。

验证逐条核对 RPC 请求、返回值、七行 RAM、行外保护字节、B6/B19 邻接字节、T、设置区、颗粒行为、提交状态和重开菜单结果。08 成功提交为 active 7、uncertain 0，证明实际 C 加载器接受了最终表文件。

- 原始顺序每次 T1 运行共 1152 次 RPC，其中 V 41、W 1072、X 39、U 0。
- 补充顺序每次 T1 运行共 1692 次 RPC，其中 V 57、W 1580、X 55、U 0。
- 普通和 ASan/UBSan 构建均退出 0，无消毒器错误；对应的完整记录逐字节相同。
- 所有非 08 槽位的 RAM、设置、状态、颗粒及重开结果均与 v1 相同。没有经过 08 的切换，完整记录也与 v1 相同。08 退出到 04 时多出所需的控制恢复与 C/D 恢复，最终状态与 v1 的 04 相同。

进入 08 时，在任何行 W 之前先有以下预检；首次进入 deep 槽时可在此前读取 B6 邻接字节，但没有行写入：

```text
X12C0 → V2444 返回 0x0002
```

随后写入行数据。C/D 事务先执行地址选择、行首 V 检查和 33 次 W，每次 W 的返回值都与写入半字一致。最后才切控制，并显式回读：

```text
X12C0 → V2444 返回 0x0002 → W0000 返回 0 → V2444 返回 0
```

退出 08 时，下列事务位于任何行事务之前；控制恢复且回读为 2 后才恢复各行及 stock C/D：

```text
X12C0 → V2444 返回 0 → W0002 返回 2 → V2444 返回 2
```

以上为主机模块模型中的观察，不能代替相机端写入或图像效果证据。

## 复跑与保全

```sh
python3 -I -B /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/t1_probe/build_validate.py
```

构建脚本会重新核对外置卷、v1 哈希、配方库与 stock 输入，再生成并验证同一交付目录。原始 RPC 和 RAM 记录、文件偏移差异、保护文件起止清单位于被忽略的 `research/t1_probe/local/`；编译命令、运行命令、日志和临时驱动位于 `/tmp/t1_gpt/`。公开报告不含源表或派生数组。

写入前已核对挂载点 `/Volumes/Workspace`、APFS、可写状态和 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，并运行 `df -h /Volumes/Workspace`。共 4276 个受保护文件的内容哈希、长度、修改时间和模式起止一致，范围包括既有 stage2 固件、其他 stage2 包、官方固件及本任务读取的三个研究输入。没有写其他研究目录、SD 卡或相机，没有 Git 提交。共享检出有并行工作，不能把整仓 Git 状态宣称为未变。

## 上机检查单

1. 开机后先打开菜单，确认没有 `!4`。
2. 选 M 档，固定白平衡、ISO、曝光、照明和构图，拍同一灰阶或中性场景，屏幕上的色相环/灰阶图也可。按 `04 → 08 → 04` 各拍一张，每次选槽后关闭再打开菜单，核对光标确实停在该槽。
3. 预期 08 的灰区出现明显的单通道色偏，最后 04 的灰区各通道相对第一张回到约 ±2 码。严重异常或只剩单色时停止测试。
4. 测试后先选 04，重开菜单核对，再切换模式。关机、重新开机并打开菜单，确认没有 `!4`。
5. 若出现 `!4`，先关机重开一次。若每次开机仍出现，停止使用 deep 槽，运行完整官方更新包，须包含镜头单元更新，不能只更新机身。

推断仍待实拍验证：C/D 是否为绝对通道曲线，以及 D 对应哪个通道。08 的色偏方向用于判断 D 的通道；另一通道保持原曲线支持绝对表解释，大幅变亮或削顶则更支持增量解释。没有变化只能记为通道模式未确认。旧 [split_tone/REPORT.md](../split_tone/REPORT.md) 的判读表可辅助解释结果，本套不测试旧 07。LCD 未见 `!4` 只记录为未见 T 告警，不能证明整个 T 区没有持久化。
