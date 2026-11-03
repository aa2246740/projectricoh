# 刷写 Stage 1a probe v2 并核对新扫描

> **状态：BLOCKED_REVIEW_R2，不得刷写（2026-10-14）。** 对抗复核（[STAGE1A_PROBE_V2_REVIEW.md](../review/STAGE1A_PROBE_V2_REVIEW.md) 第 1 项）认定：每次有效 ISO 调用都完整扫描 8340 字节（约 5 万条指令），隐藏调用也不例外，而这些调用的启动、升级、中断与时序上下文没有证据。本包由 v2.1 取代：只在显示调用时扫描，并改为抽样扫描。

电脑端已通过，v2 真机检查尚未开始。使用新包 `stage1a-probe-v2-compact`，仅由用户操作相机和卡。Agent 本轮没有操作相机、SD 卡或 `/Volumes`。

探针 `ilaunch3` 的 SHA-256 必须是：

```text
67dc96048aa23bf1ed4032be130744c0b0ac0ddf45baa3551e1b960d74577437
```

2026-10-14 的 Phase 0 已在这台 GXR + A12 50mm 验证演练刷写、`ISX 200` 和正常刷回后的 `ISO 200`。证据见 [P0 recovery observation](../../captures/a12-50/2026-10-14/P0-recovery-confirmed/observation.json)。恢复仍要求相机能启动并进入正常更新器。

## 准备照片和卡

1. 在原厂固件上手动设置 ISO，拍一张 ISO 200 和一张 ISO 3200 的照片。记录文件编号，保留电脑备份。
2. 在回放显示信息页核对它们分别显示 `ISO 200` 和 `ISO 3200`。两张都使用数字 ISO，避免 Auto ISO 或 `ISO-LO`。
3. 如已有实际显示 `ISO-LO` 的照片，另记文件编号和原厂画面，用于核对低 ISO 路径。无法取得时，该项记 `BLOCKED`。
4. 确认机身和 A12 50mm 的 MAIN 均为 V1.51，使用满电电池。

可复用已核验的实验卡或恢复卡，无须为本轮重新格式化。同一张卡、同一套 29 文件未改且读回仍全部通过时，可以复用准备结果。换包、重新复制或怀疑文件变化时，重新读回校验。

新卡或未核验的卡先按已验证的官方流程准备。需要格式化时先备份照片，再由用户在相机内格式化。复制命令只覆盖这套 29 个升级文件，不删除照片。

由用户把 `CARD` 换成实际卡名后执行：

```sh
CARD="/Volumes/卡名"
PKG="/Users/wu/.t3/projects/projectricoh/artifacts/stage1a-probe/packages/stage1a-probe-v2-compact"
test -d "$CARD" || exit 1
cp -X "$PKG"/probe/SD_ROOT/* "$CARD"/
dot_clean -m "$CARD"
(cd "$CARD" && shasum -a 256 -c "$PKG"/probe/SHA256SUMS)
ls -A "$CARD"
```

必须看到该清单 29 个文件全部 `OK`。核对卡根没有 `._ilaunch*`、`._jlaunch*` 等 AppleDouble 升级文件，也没有另一套升级包残留。清单失败时停止刷写，修复复制结果。

## 刷写并核对首次结果

1. 安全弹出卡，断开 USB，关机，把卡插入相机。
2. 按已验证操作，按住 `+` 并按回放按钮 `2-3 秒`，进入更新确认页。
3. 核对机身、模块和版本。用 Fn2 选择 Yes，再按 MENU/OK 确认。识别不符、无法确认或出现错误时停止本轮。
4. 写入期间保持电源、卡和模块连接，等更新自动结束并重启。
5. 回放 ISO 200 照片，在显示信息页拍下完整 `OK 200` 和文件编号。
6. 切换到 ISO 3200 照片，拍下完整 `OK 3200` 和文件编号。
7. 切回 ISO 200 照片，确认文字再次变成 `OK 200`。

ISO 数字必须随切换变化。停在同一张照片重复拍摄旧 `OK`，不能证明本次又扫描过。

## 每个检查点都交替两张照片

完成下表每项操作后，先切到与上一张不同的照片，再切回另一张。两次都记录文件编号、完整文字和屏幕照片。

| 检查点 | 操作后核对 | 当前状态 |
|---|---|---|
| 首次回放 | `OK 200 → OK 3200 → OK 200` | NOT_RUN |
| 正常关机再开机 | 交替两个文件，数字分别匹配 200、3200 | NOT_RUN |
| 回放切到拍摄再回放 | 交替两个文件，数字分别匹配 200、3200 | NOT_RUN |
| 正常待机后唤醒 | 交替两个文件，数字分别匹配 200、3200 | NOT_RUN |
| 另一种实际回放布局 | 交替两个文件，记录布局和数字 | NOT_RUN |
| 低 ISO 照片 | 同一文件继续显示 `ISO-LO` | NOT_RUN |

每个数字 ISO 的新结果只表示该次读取的 `[0x2005276C,0x20054800)` 全部 8340 字节为 `FF`。`NG 200` 或 `NG 3200` 表示至少一次读取遇到其他值。

低 ISO 照片必须仍显示 `ISO-LO`。它来自原厂第二次 formatter，可能遮住第一次的 `NG`，因此只验收低 ISO 行为，不计作候选区通过。

两个入口的文字相同，布局名称也不能识别入口。某入口没有独立实机路径证据时，把该入口覆盖记为 `BLOCKED`，不要根据相同标签填 PASS。电脑端已单独重放两个入口。

出现 `NG`、乱码、不能切换照片、卡住或基本拍摄异常时，记录当前照片、ISO、操作和哈希，停止后续实验。更新尚未结束时保持供电，不把写入中的等待当成回放死机处理。

## 刷回官方并核对恢复

相机仍能启动、读卡并进入正常更新确认页时，使用包内官方恢复树。已核验的官方恢复卡可以复用。

需要重新复制时，由用户执行：

```sh
CARD="/Volumes/卡名"
PKG="/Users/wu/.t3/projects/projectricoh/artifacts/stage1a-probe/packages/stage1a-probe-v2-compact"
test -d "$CARD" || exit 1
cp -X "$PKG"/recovery-official-1.51/SD_ROOT/* "$CARD"/
dot_clean -m "$CARD"
(cd "$CARD" && shasum -a 256 -c "$PKG"/recovery-official-1.51/SHA256SUMS)
ls -A "$CARD"
```

必须再次 29/29 `OK`。官方 `ilaunch3` 的 SHA-256 为：

```text
da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7
```

安全弹出、断开 USB，再按相同正常更新步骤刷回官方。完成后核对机身和模块 MAIN 均为 V1.51，交替回放两张照片确认恢复 `ISO 200` 和 `ISO 3200`。再关机开机复查，记录本次恢复结果。

不能启动或不能进入更新器时，停止尝试未知 Monitor 或 USB 入口。本项目没有已验证的这类救援流程。

## 保存本轮实机记录

```text
package: stage1a-probe-v2-compact
ilaunch3 SHA-256: 67dc96048aa23bf1ed4032be130744c0b0ac0ddf45baa3551e1b960d74577437
card read-back: NOT_RUN
v2 flash: NOT_RUN
ISO 200 file / ISO 3200 file: 待填写
fresh OK 200 / OK 3200: NOT_RUN
cold boot / wake / playback-shooting switch: NOT_RUN
normal entry hardware coverage: NOT_RUN
alt entry hardware coverage: NOT_RUN
ISO-LO file / unchanged ISO-LO: NOT_RUN
official recovery after v2: NOT_RUN
Agent camera / SD / Volumes operations: none
```
