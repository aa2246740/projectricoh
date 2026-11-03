2026-10-25 P1 开始。卷身份、可写 APFS、df 已核实；冻结输入排除 decisions.tsv。
基线 resident payload 7800 B，root 256 B，窗口 8340 B，实余 284 B。
覆盖决定：默认启用；仅有效 CRC 的 CTL OFF 锁定停用；RPC 仅明确应用时准许。
保留 v3.3 全部既有 hook/H09 行为，不使用 H40。未访问相机或卡。

P1 主机通过。payload 7832 B，root 256 B，实余 252 B；预留改为 200 B，卡源拒绝/未知锁存增加 32 B。44 例 C / 127607 断言；IRQ 131072、hook replay 896、H07 桩 256、H01/H02/H05 指令 147、v32 负对照 8。栈为编译帧模型，原生深层调用与设备水位未知。未新增 H40。

P2 源码已接入纯 init、默认 ON/完整 OFF、仅 OK/Fn2 应用、服务与 adapter 隔离、4 KiB 黑盒与 decoder。交叉编译发现并修正新代码缩进告警；行为验收将在 P3 格式合并后执行，不把编译等同产品通过。

P3 初次容器构建通过。full-r10 generation 112，65200 B（上限 65536，剩余 336 B），engine 55788 B，BSS 11520 B，三枚 pins 与研究候选一致。full-r9 全部 48 槽旧行/控制值保留，九行新数据已输出。研究候选 07/08 的差异仅为身份 CRC 的 4 字节，保留 full-r9 身份；功能矩阵尚待 P5。

P4 初次机身构建/审计通过，映像 4e5cc4c1dfc93900773093c6a3f2f6c478b4b06916e9392335c683893fd239b0。7 个 BRA、28 个禁用点均逐点审计；首次传入未归一化 hooks 被工具拒绝，已改用保留官方字节的显式 hook 清单。P5 启动，尚未暂存 SD_ROOT。

P5 补充 card-none 的真实菜单路径，复现 IROM 已加载但无 SD 身份时被存储预载停用。已在 engine 预载入口跳过不可用 SD 的 GXLS/GXTS，保留默认配方与明确应用，并继续禁止保存。不是绕过隔离或放宽默认启用断言。将重新构建并复跑最终候选矩阵。

P5 主机通过：204 个最终候选程序运行，44 例 resident / 127607 断言，IRQ 196608，hook replay 896，constructor 2048，首帧输入 6912，新增 RPC 故障 624，旧绑定显式保存 3584，IROM 状态 189。保护输入 38988 项未变。开发中修正旧 pin、回执偏移，以及测试器的副本选择、Mount 06 control、反汇编 endian 和未触发设置写分支；没有放松产品断言。

P6 已暂存 STAGED_HOST_ONLY。SD_ROOT 30 文件；CTL ON/OFF 单独放 controls。没有设备验收或刷写授权。

P5 追加“GXLS 光标进入后 MENU 关闭再重开、仍未应用”的产品断言，发现未 committed 时会重置为 01。当前暂存包先保留为历史，修复后全量复跑并重新暂存。不得把旧 package 当本轮最终交付。

P5 主机通过：204 个最终候选程序运行，44 例 resident / 127607 断言，IRQ 196608，hook replay 896，constructor 2048，首帧输入 6912，新增 RPC 故障 624，旧绑定显式保存 3584，IROM 状态 189。保护输入 38988 项未变。开发中修正旧 pin、回执偏移，以及测试器的副本选择、Mount 06 control、反汇编 endian 和未触发设置写分支；没有放松产品断言。

P6 已暂存 STAGED_HOST_ONLY。SD_ROOT 30 文件；CTL ON/OFF 单独放 controls。没有设备验收或刷写授权。
