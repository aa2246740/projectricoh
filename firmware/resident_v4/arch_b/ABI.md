# 受信扩展 bootstrap ABI 1

这是可链接的窗口原型，不是完整机身或完整受信扩展。目标 `platform.c` 的 proof mask 为 0，`policy.json` 没有已批准扩展摘要。当前目标代码在文件 I/O 前返回 UNKNOWN。

## 信任和载入顺序

固定源是 `/IROM/GXRTR4.EXT`。IROM 是可写文件系统卷。窗口保存批准文件的完整 SHA-256；文件内自报的校验值不授予执行权限。窗口先检查 160 B 头和身份，再申请一次主堆块、整读、检查严格 EOF、关闭文件、校验完整文件 SHA、校验全部重定位、重定位、清 BSS、同步缓存，最后调用 INIT 并发布 READY。

`window_build` 由代码、工具链、ABI 和非 pin 配置派生，不包含待批准文件摘要，避免文件头和窗口 pin 的循环依赖。最终窗口 ELF 的 SHA-256 仍包含 pin。改变受信扩展需要重新批准摘要并重新链接窗口；普通 DAT 更新继续受独立 v4 合同约束。

INIT 只准备私有 BSS，不发布 UI、callback 或 DAT。该合同要由完整受信扩展的实现和审查证明。本轮没有完整扩展。

## 文件头

所有整数都是大端 u32。`file_bytes` 包含头，不含 BSS。代码区必须包含所有执行代码和需要持续保护的只读数据。

| 偏移 B | 内容 | 检查 |
| ---: | --- | --- |
| 0 | 8 B magic。 | `GXRB4E01`。 |
| 8 | header bytes。 | 160。 |
| 12 | file bytes。 | 160..65536。 |
| 16 | BSS bytes。 | 0..16384。 |
| 20、24 | code offset、bytes。 | 四字节对齐，非空，完整落在文件内，起点至少 160。 |
| 28、32 | INIT、hook 入口偏移。 | 四字节对齐，完整指令落在 code 内。 |
| 36、40 | relocation offset、count。 | 最多 1024 个 8 B 描述符，与 code 不重叠。 |
| 44 | 官方机身 SHA，32 B。 | 等于窗口固定身份。 |
| 76 | window build ID，32 B。 | 等于窗口固定身份。 |
| 108 | bootstrap ABI ID，16 B。 | 等于窗口固定身份。 |
| 124 | extension ID，16 B。 | 由批准文件的完整 SHA 约束；复制到窗口 root。 |
| 140 | firmware revision 和 CPU ID。 | `0x01514D32`。 |
| 144 | 16 B 保留。 | 全零。 |

重定位描述符为两个 u32：patch 和 target。patch 必须按递增顺序唯一、四字节对齐、完整落在 code 内；target 落在头之后的文件或 BSS 内，patch 原值必须等于 target。先检查全表，再把 patch 写为 `base + target`。没有从文件接收原厂 PC 或 native callback。

## 入口和根区

```c
int32_t init(uint32_t image_base, uint32_t bss_base,
             uint32_t bss_bytes, const Bv4Api *api);
int32_t hook(uint32_t native_hook, uint32_t *saved_frame,
             uint32_t bss_base, const Bv4Api *api);
```

两者使用 GCC M32R 的 r0..r3 参数 ABI。`Bv4Api` 是 16 B，只含 ABI major、字节数、窗口 root 地址及 required proof mask。saved_frame 仅传给受信常驻级扩展；DAT 不通过此接口取得寄存器帧。

窗口 root 仍占 `[0x20054600,0x20054800)` 的 512 B，实际 M32R 布局见 [arch-b-abi.json](../../../research/body_v4_w0/arch-b-abi.json)。它与 A 的 `Rv4Root` 语义不同。完整 v4 resident 状态须放在扩展 BSS，额外计入 RAM。

窗口 root 为 NOLOAD。未来镜像生成器必须建立已证明冷启动所需的全 FF 初值；现有 v3.6 或 r1 的 pins/root 不能直接沿用。未知暖状态不清零、不重载。

## native 接口与未闭合条件

`bv4_boot_native` 是 96 B 的真实保存、调用、重放 wrapper，候选站点为 `0x2010DDF8`。它保留 r0..r13、LR、PSW 和 SP，重放原厂 8 B 后到 `0x2010DE00`。本轮没有安装该挂点。它位于媒体初始化返回之后，只证明局部位置，不能证明早于所有 UI、拍摄、更新或其他 hook。

`Bv4Platform` 的 boot probe 和 lifetime probe 必须是非阻塞、无 I/O 的可信叶接口。前者证明正常冷启动、同一 task owner、媒体代次、主堆代次及尚未释放 hook 调用者的屏障；后者证明当前启动和主堆分配实例仍有效。目标两个 probe 均为 0。

`BV4_REQUIRED_PROOFS=15` 分别要求启动屏障、堆生命周期、文件 scope 和本扩展的 cache 合同。P0 的一次堆执行结果不自动授予这些位。所有堆重建入口必须在改内存前尊重窗口的 `active_calls` pin；只比较堆边界和分配头不能保证实例仍有效。

正常调用给扩展取得窗口级代码 pin；嵌套调用仍进入受信扩展，由扩展仲裁 UI、任务准入和 DAT 调用。这个 pin 不代替跨任务系统准入。退出后重查代码和绑定，计数不回绕，已执行块不释放、不热换。

失败发生在任何扩展执行前，且句柄、scope 和原生状态健康时，原七处 hook 走原厂重放。执行后失败或身份未知时，窗口保留隔离块，并使用固定 H01/H02、H05、H06/H08 和 H07 应急续程及 192 B 空说明；这些续程不构成完整系统恢复证明。

其余 29 个预留 hook 仍是 32 B 的 UNKNOWN 返回桩。它们的原厂 ABI、重放和拒绝语义尚未实现，未计作已迁入 DAT 或已闭合门禁。
