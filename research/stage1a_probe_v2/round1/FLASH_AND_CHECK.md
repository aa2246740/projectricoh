# v2 刷机与检查操作稿

本轮为 `BLOCKED_R2_NO_PROVEN_GUARD`，没有 v2 刷机包，当前不能执行下面的 v2 刷写步骤。本文保留解除 R2 阻断后使用的检查流程，所有卡操作均由用户执行；Agent 没有访问 `/Volumes` 或相机。

已验证的背景继续有效：在这台 GXR + A12 50mm、两者 V1.51 上，带重算 checksum 的 `ilaunch3` 演练能启动，正常更新入口可用时刷回官方 1.51 已成功。本轮没有新增真机结果。

## 新包取得后才执行的准备

确认新包的 `manifest.json`、验证证据和最终 `ilaunch3` SHA-256。必须是新的 `stage1a-probe-v2-<short-name>` 目录，探针与官方恢复各 29 文件。REPORT.md 的 R2 状态必须已经解除；当前阻断规格不能用于制包。

先用未修改的固件拍两张照片，手动设置明确不同的 ISO，例如 `200` 和 `3200`，记下两张照片的文件名。避免 Auto ISO，并确认原厂回放的显示信息页确实分别显示 `ISO 200` 和 `ISO 3200`。测试照片保留在卡上，并在电脑上留备份。

可复用已经核验的同一张卡，无须为了本轮再格式化。改换探针包或恢复包后，都必须重新读回核验该套包的全部 29 文件。卡已格式化、升级文件未改且读回清单仍 29/29 OK 时，可以直接复用那次准备结果；重新插拔或有复制疑问时再次核验。

需要重新准备卡时，沿用 [phase0_drill/FLASH_AND_RECOVERY.md](../phase0_drill/FLASH_AND_RECOVERY.md) 的流程。先备份照片；仅在需要格式化时由用户在相机中格式化。不要混用两套升级文件。

未来新包的探针复制命令为：

```sh
CARD="/Volumes/卡名"
PKG="/Users/wu/.t3/projects/projectricoh/artifacts/stage1a-probe/packages/stage1a-probe-v2-<short-name>"
cp -X "$PKG"/probe/SD_ROOT/* "$CARD"/
dot_clean -m "$CARD"
(cd "$CARD" && shasum -a 256 -c "$PKG"/probe/SHA256SUMS)
ls -A "$CARD"
```

`<short-name>` 必须换成最终已核验的新包名字。当前这个包路径不存在。读回必须恰有 29 个升级文件全部 `OK`，没有 `._*` 升级文件。目录里的照片不属于升级文件；不要为了清理升级文件删除照片。

## 刷写与每次新扫描的证明

1. 使用同一 A12 50mm 和满电电池，安全弹出卡，断开 USB，关机。
2. 按住 `+`，同时按住回放按钮 `2-3 秒`，进入更新确认页。核对机身、模块与版本，按既有已核验操作用 Fn2 选择 Yes，按 MENU/OK 确认。
3. 写入期间保持电源、卡、模块连接，等更新自动结束和重启。新包若不能正常进入确认页、识别结果不符或报错，停止本轮，不改版本号或绕过检查。
4. 回放两张测试照片的显示信息页，交替检查 `OK 200` 和 `OK 3200`。每个检查项目都先切换到另一张照片，再读文字并拍下画面，禁止停在同一张照片上把旧文字当作一次新扫描。

新扫描的检查项目为：首次回放、正常关机再开机、回放切到拍摄再切回、相机正常进入待机后唤醒。每项都要出现新切换照片对应的 `OK 200` 或 `OK 3200`，并再切另一张确认另一 ISO。两次显示都发生变化，才能作为本项重新调用 formatter 与扫描的可见证据。

只有未来 v2 实现实际覆盖全区时，`OK` 才表示这次扫描看到 `[0x2005276C,0x20054800)` 的全部 8340 字节为 `FF`。`NG` 表示至少一字节不同。`OK` 仍只说明本次读取结果，不能证明全部生命周期永远不会写入该区。

ISO-LO 显示应保持原厂行为。两张照片的正常 ISO 文字检查不要依赖 ISO-LO 状态来判断探针是否运行。

出现 `NG`、无法切换照片、乱码、卡住或基本拍摄异常时，记录当时照片、ISO、检查项目与固件哈希，结束实验。恢复条件与操作如下。

## 官方恢复

正常官方恢复要求相机仍能启动、读卡、进入更新确认页并完成写入。该条件下既有真机恢复证据有效。相机不能启动或不能进入更新器时，本项目仍没有已验证的用户救援步骤，不试探未知 Monitor/USB 入口。

已有官方恢复卡且 29 文件哈希全部等于官方时可以直接复用，不需要再次格式化。重新准备未来新包内的官方恢复树时，由用户执行：

```sh
CARD="/Volumes/卡名"
PKG="/Users/wu/.t3/projects/projectricoh/artifacts/stage1a-probe/packages/stage1a-probe-v2-<short-name>"
cp -X "$PKG"/recovery-official-1.51/SD_ROOT/* "$CARD"/
dot_clean -m "$CARD"
(cd "$CARD" && shasum -a 256 -c "$PKG"/recovery-official-1.51/SHA256SUMS)
ls -A "$CARD"
```

当前没有新包，现成的官方恢复树仍在 `artifacts/stage1a-probe/packages/stage1a-probe-ok-ng/recovery-official-1.51/SD_ROOT`。它的 29 文件与官方相同，旧包未被本轮修改；可继续用于已有实验固件的有条件官方恢复。

安全弹出、断开 USB，按相同正常更新步骤刷回官方。完成后检查机身与 A12 50mm 的 MAIN 均为 V1.51，交替回放两张照片看到 `ISO 200` 和 `ISO 3200`，再关机开机复查。实际完成后再记录本次恢复 PASS。

## 本轮验收记录

```text
v2 package: none
v2 flash: NOT RUN
v2 fresh OK 200 / OK 3200: NOT RUN
v2 cold boot / wake / playback-shooting switch: NOT RUN
official recovery after v2: NOT RUN
Agent camera / SD / /Volumes access: none
```
