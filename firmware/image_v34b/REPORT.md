v3.4b 已暂存在 [SD_ROOT](local/package/SD_ROOT)，状态 STAGED_HOST_ONLY，独立审查 PENDING。本轮未访问相机或卡，未刷写。

```text
ilaunch3      abd500a52931a8bbd13e7b4d3242664e15c53e19882a7ce5ddb4206ccdbac34d
GXRCE.DAT     18424a588fbbb80cf554b0c5a821d605fbac6326cc4a9111aad4eeb46e8cbf29
resident ELF  fcee63608ee0cafe5b86f27d1e69b7b88caa242bae9f8e8329c91cb4cb9b355d
```

映像沿用复制的 image_v3 工具与固定 policy；生成机身时只输入新 ELF 和现有 37 点清单。执行点仍为 H01/H02/H05/H06/H07/H08/H09，H03/H04 与 H10–H37 保持官方字节。相对 v3.3 的 3914 个变化字节全部限于原 resident 窗口、七处既有桩和头 checksum。30 个官方更新路径窗口逐字节相同。payload 7832 B、root 256 B、余量 252 B；预留 200 B。

复制工具的 14/14 故障包拒绝、两次构建 68 个文件一致、7 个实际 BRA 目标通过。独立重放 packaged constructor 2048 组。SD_ROOT 30 个文件包含新 ilaunch3、与 v3.2 trial 完全相同的 28 个官方兄弟文件，以及 generation 112 的 full-r10，65500 B。CTL ON/OFF 单独在 [controls](local/package/controls)，不在 SD_ROOT。摘要与审核状态见 [manifest](local/package/manifest.json) 和 [SHA256SUMS](SHA256SUMS)。

用户行为、完整检查和源码行号见 [resident 报告](../resident_v34b/REPORT.md)。启动原厂，进入只显示/定位，OK/Fn2 才应用；GXLS 不自动恢复模块。有效 CTL OFF 停用至冷启动，OFF 读 -1 不生效；退路是不进 Image Settings 或回刷 Stage2l。日志只在安全出口写卡根的 GXRBX0.BIN/GXRBX1.BIN。

剩余风险是实际 M32R、文件系统掉电、相机堆/栈、原生 UI、ISP 切换并发和照片未验收；容器仅余 36 B。无 DAT 的 -1 按未知源隔离，IROM 配方仍可用，但本次开机禁止 GXLS/GXTS 保存。

独立审查和用户批准后，首刷挂 28mm 或 Mount；关机换 50mm 冷启动，先确认能正常启动。恢复用卡 A 加“+ & 回放键”，必要时挂 50mm 刷 Stage2l 和官方单元。这条恢复由用户今日现场验证，本轮没有执行。
