v3.4c 已暂存在 [SD_ROOT](local/package/SD_ROOT)，状态 STAGED_HOST_ONLY，独立审查 PENDING。未访问相机或卡，未刷写。

```text
ilaunch3      24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72
GXRCE.DAT     6cb63aa47c18086f5ade681ffe4dc97378394ff7a65c0688d19b3880d804c707
resident ELF  b69e0df4c3e7df0b46fd0c175312c128d38be5cb6a2fb046644cc7922ea4bb3e
engine.bin    174e00e5daef01546c240ba39638cdfd03cc5506fad1a1e0feebdb7b35846317
```

resident payload 7868 B、root 256 B、余量 216 B。full-r11 generation 113 为 64816 B，余量 720 B；只改编译设置省 736 B。缩减逐步为服务 fat LTO 408 B、禁止 partial inline 236 B、禁止 IPA SRA 52 B、禁止 small inline 40 B，完整表和源码 file:line 见 [resident 报告](../resident_v34c/REPORT.md)。机身使用复制的 image_v3 工具和既有 policy。

相对 v3.3 的 4588 个变化字节全部在 resident 窗口、七处既有桩和 checksum；H03/H04、H10–H37 及 30 个官方更新窗口相同。28 个官方兄弟文件与 v3.2 trial 全等。两次构建 68 文件一致，14/14 故障包拒绝，7 个 BRA、2048 组实际 constructor 重放通过。SD_ROOT 共 30 文件；CTL ON/OFF 单独位于 controls/。

250 个产品主机程序、44 例 resident/127607 断言通过，覆盖完整 v3.4b 和 R4/R6/R7/R33 反例。48 槽完整数据与 full-r10 全等。堆申请主块 83840 B、会话工作区 1460 B、UI 1968 B、loader 608 B、安装缓冲 2×65536 B；含头首装模型 215568 B，已有 UI 时 217548 B，均非设备水位。

卡上仅 OK、无 GXRCE 或无卡时，Fn2 草稿可由 OK 应用并写 GXTS，GXLS 记最后明确应用的配方。冷启动只恢复光标/微调，OK/Fn2 才写模块。旧/无效 DAT、present DAT 的 I/O 错误或 CONFLICT 仍黏性拒绝内部保存。默认 ON，完整有效的 CTL OFF 停用至冷启动；无法读取 OFF 时不会停用。保留双日志、两种回执和 64 项 ring。

剩余风险为真实 M32R、掉电/rename、堆栈、原生 UI/快门并发和照片未验收，持续 open=-1 的 DAT/IROM 歧义仍在。首刷另获批准后挂 28mm 或 Mount，关机换 50mm 冷启动；恢复用卡 A 加“+ & 回放键”。

原冻结输入 42680 项未变，排除 decisions.tsv。完整测量、每项改动行号、行为和原始证据见 [resident 报告](../resident_v34c/REPORT.md)，包摘要见 [manifest](local/package/manifest.json)。
