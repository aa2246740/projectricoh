# 阶段 1a：刷写执行探针、检查 OK/NG、恢复官方

预期回放显示 `OK 200` 一类文字。它表示探针本次执行，并在扫描时看到其余 8,260 字节全为 FF。`NG 200` 表示至少一个受检查字节被改动，应停止实验并恢复官方。

这是机身主程序代码实验。未知写入、执行条件或挂钩错误可能导致死机和无法开机；主程序不能启动时的救援尚未在本机证明。官方恢复包只能在相机仍能读取卡、进入正常升级确认并完成更新时使用。

日期：2026-10-13。目标仅为 GXR＋GR LENS A12 50mm F2.5 MACRO，机身和当前模块 MAIN 均为 1.51。本包的电脑检查已经完成；真机结果均待测。本任务没有连接相机，没有写 SD 卡或 `/Volumes`。下方上卡命令只供用户手动执行。

**前置状态（2026-10-14 更新）：** 阶段 0 演练已在本机完成：刷入演练包后回放显示 `ISX`，刷回官方 1.51 后恢复 `ISO`（证据 `captures/a12-50/2026-10-14/P0-recovery-confirmed/`）。因此**相机仍能启动、进入升级确认时**的官方回退已在本机证明。主程序损坏、不能启动后的救援仍未证明。本探针第一次在真机执行新代码；它是否会在开机或升级流程中被调用、从而影响官方回退，见 [对抗复核](../review/STAGE1A_PROBE_REVIEW.md) 第 1 项与 [升级路径隔离分析](UPDATE_PATH_ISOLATION.md)，结论出来之前不刷。

## 1. 刷写前检查

1. 给电池充满电。关机，按住 `-`，同时按住回放按钮超过 1 秒。拍下版本页，确认机身与 A12 50mm 的 MAIN 均为 `V 1.51`。记录 BKUP、MONI 和 CV 原值。模块或 MAIN 不符时停止，不在本实验中顺带升级其他版本。
2. 新卡或尚未验证的卡：先备份照片，再在相机中格式化（至少 64 MB）。阶段 0 已用过、读回校验通过的同一张卡可直接复用，不必再格式化。建议另备一张恢复卡，先装好下方官方恢复文件。
3. 用当前官方固件拍**两张 ISO 明显不同**的 JPEG＋DNG，例如一张 ISO 200、一张 ISO 3200。回放，按 DISP. 切到“显示信息”，拍下两张各自底部的 `ISO 200` / `ISO 3200` 作为对照。两张都必须是这台相机拍摄、ISO 在 1–9999、且未显示 `ISO-LO`。用两个不同数字，是为了区分"本次刚扫描过"和"屏幕上残留的旧 OK"（见第 4 节）。
4. 核对交付目录与下方包身份。探针版和官方恢复版各有 29 个升级文件；只有探针版 `ilaunch3` 有变化。不要混用两套文件。

完整步骤来源与按键证据见 [Phase 0 刷写手册](../phase0_drill/FLASH_AND_RECOVERY.md)。该手册也说明本机早先 A12 1.50 的升级前提；本次只接受已经到 1.51 的组合。

## 2. 核对包身份

包是目录，名称为 `stage1a-probe-ok-ng`。

```text
artifacts/stage1a-probe/packages/stage1a-probe-ok-ng/
  probe/SD_ROOT/                         29 个文件
  probe/SHA256SUMS
  recovery-official-1.51/SD_ROOT/         29 个官方原文件
  recovery-official-1.51/SHA256SUMS
  manifest.json
```

探针版 `ilaunch3` SHA-256：`6818c492c7a9d9e1025650e2d514bea3bb7996add5a080f6b25b93573abf526b`。官方恢复版：`da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。其余文件必须与 `manifest.json` 的官方哈希表一致。完整落盘复核记录见 [PACKAGE_VERIFICATION.md](PACKAGE_VERIFICATION.md)。

改动范围：候选区末尾文件 `[0x99B0,0x9A00)` 的 80 字节，回放调用文件 `[0x2CEE7C,0x2CEE80)` 与 `[0x2CD664,0x2CD668)` 各 4 字节，头部校验 `0x16C..0x170`。相较官方，实际变化共 **89 字节**（含校验），文件长度、段表、版本和兼容字段保持原值。两份原厂 `ISO %d` 字符串没有改动。

在电脑上先复核两份目录，命令不接触 SD 卡。

```sh
PKG=/Users/wu/.t3/projects/projectricoh/artifacts/stage1a-probe/packages/stage1a-probe-ok-ng
(cd "$PKG/probe/SD_ROOT" && shasum -a 256 -c ../SHA256SUMS)
(cd "$PKG/recovery-official-1.51/SD_ROOT" && shasum -a 256 -c ../SHA256SUMS)
```

两次都必须是 29 行 `OK`。对应文件名如下。

```text
ilaunch0 ilaunch3 ilaunch4 ilaunch8
jlaunch0 jlaunch3 jlaunch4 jlaunch8
klaunch0 klaunch3 klaunch4 klaunch8
l06firm0 l06firm3 l06firm4 l06firm5 l06firm8
l08firm0 l08firm3 l08firm4 l08firm8
nlaunch0 nlaunch3 nlaunch4 nlaunch8
qlaunch0 qlaunch3 qlaunch4 qlaunch8
```

## 3. 用户手动上卡与刷写

确认 Yes 后开始更新。更新期间不得关机、取电池、拔卡或拆卸模块。没有经验证的更新超时阈值，不用强制断电处理等待。

1. 关机后取卡。只把 `probe/SD_ROOT` **里面**的 29 个文件复制到卡根目录。不要复制 SD_ROOT 文件夹、SHA256SUMS、manifest 或恢复文件夹。Mac 上可由用户执行以下命令；先将卡路径替换为实际挂载路径。

   ```sh
   CARD="/Volumes/卡名"
   PKG=/Users/wu/.t3/projects/projectricoh/artifacts/stage1a-probe/packages/stage1a-probe-ok-ng
   cp -X "$PKG"/probe/SD_ROOT/* "$CARD"/
   dot_clean -m "$CARD"
   (cd "$CARD" && shasum -a 256 -c "$PKG"/probe/SHA256SUMS)
   ls -A "$CARD"
   ```

   29 行哈希必须全部 OK。升级文件只应有上述一套；相机生成的 DCIM 等目录可保留。`dot_clean -m` 的用途和 macOS 附属文件实测见 [Phase 0 主代理核验](../phase0_drill/ROOT_VERIFICATION.md)。
2. 安全弹出卡并断开 USB。关机状态装回卡，保持 A12 50mm 连接。
3. 按住 `+` 不放，同时按住回放按钮 2–3 秒，进入更新确认画面。
4. 核对画面实际显示的更新对象与版本。确认页没有显示的字段用事先版本照片核对。若不识别文件、报 `Incorrect rewriting file`、对象不符、电量不足或读回哈希不全，停止，不确认 Yes。
5. 用 Fn2 选择 Yes，再按 MENU/OK。保持电源、卡和模块连接，等更新完成及相机自动重启。记录实际状态画面，包括是否写入机身。若同版本更新被拒绝，停止并记录，不改版本号或绕过检查。

## 4. 检查执行与区域完整性

每项记录 PASS、FAIL 或 BLOCKED。没有做的项目不能记 PASS。两个回放生产函数共用同一个文字缓冲区，屏幕可以在不重新调用探针的情况下重画旧文字，所以"看到 OK"本身不证明这一次又扫描过。**每个检查点都在两张测试照片之间来回切换**，拍下文件编号和对应的完整文字（例如先 `OK 200` 再 `OK 3200`）。数字随照片正确变化，才说明探针这一次确实重新运行并完成了扫描；只是重复同一张静态画面不算新的扫描证据。

| 检查 | 用户操作 | 预期与记录 |
|---|---|---|
| 首次启动、初次调用 | 更新完成后启动，回放第 1 节的 ISO 200 照片，按 DISP. 到“显示信息”；再切到 ISO 3200 那张 | 先 `OK 200`、再 `OK 3200`，数字与原照一致；两张都拍照 |
| 另一份回放绘制 | 切到“详细信息＋直方图”，再返回“显示信息” | 拍下实际 ISO 文字。同一张照片在两种画面都显示 OK，不能单独证明两条挂钩各自运行过；第二条路径没有独立证据时记 BLOCKED |
| 冷启动 | 正常关机、开机、进入回放，共 3 次 | 每次重新绘制仍是 OK，菜单正常 |
| P/A/S/M 与拍摄 | 各模式用 A12 拍 1 张 JPEG＋DNG，再回放并重新绘制 ISO | 4 次均 OK；电脑可打开 JPEG 与 DNG。拍摄画面的 ISO 仍是原厂 ISO |
| ADJ 与菜单 | 打开、关闭 ADJ 和拍摄/设置菜单，重复 5 次，再回放 | 菜单可读，回放仍 OK。探针没有配方或设置写入 |
| 休眠/唤醒 | 使用相机已启用的休眠功能，唤醒后退出、重新进入回放 | 重新绘制仍 OK；无法触发休眠时记 BLOCKED |
| USB | 正常连接电脑，读取照片，安全断开后回放 | 重新绘制仍 OK；记录是否实际经历了 USB 模式 |
| 恢复官方 | 按第 6 节恢复，再回放同一照片与拍摄检查 | 回到 `ISO 200` 一类，正常关机/开机，菜单及拍摄正常 |

若显示 `ISO-LO`，换一张数字 ISO 的照片。原厂低 ISO 路径会在探针之后用 `ISO-LO` 覆盖显示，不能据此判断成功或失败。若普通数字 ISO 仍显示 `ISO` 或 `ISX`，可见执行检查未通过：记录版本、更新状态和各回放画面，停止继续实验，不反复刷探针。

`OK` 的证据范围是本次扫描。它不检查探针自身 80 字节，也无法发现一次检查之间的短暂改写后复原。多模式的 OK 结果只能证明这些已执行检查点；没有证明全部 DMA、错误/维修路径或所有时刻均不改写。探针每次逐字节只读扫描 8,260 字节，新增开销没有真机测量。

## 5. NG、死机或不能开机

- **出现 NG**：拍下完整画面，记下刚才的模式与操作顺序，停止拍摄及进一步模式测试。相机仍正常时，按第 6 节刷回官方。不要用 NG 结果批准后续配方代码放入此区。
- **更新过程中卡住或黑屏**：保持电源、卡和模块连接。保留状态与等待过程记录，停止自行试探。不要把仍在更新的异常当作普通回放死机处理。
- **确认更新已结束后的回放死机**：记录最后画面和触发动作，先尝试正常关机。只有确定已经不在更新时，若正常关机无响应，取出电池使其关机；换上准备好的官方恢复卡、装回满电电池，按正常更新按键尝试进入确认页。进入正常确认页后按第 6 节恢复；这一步不保证死机后的升级入口仍可用。
- **不能开机、读卡或进入更新确认**：停止自行反复重刷、未知按键和维修文件试探。保留本包、哈希、原版本照片、异常过程及已做的检查，交项目负责人或具备该机维修能力的人评估。本机没有已经验证的 Boot/Monitor、USB 维修、备用程序块或外部编程器救援步骤。

上述恢复边界直接沿用 [Phase 0 手册第 4 节](../phase0_drill/FLASH_AND_RECOVERY.md)。原厂文件齐全不保证升级入口在主程序损坏后仍可达。

## 6. 相机仍能正常更新时恢复官方

1. 给电池充满电，正常关机。取出探针卡，换用已准备好的官方恢复卡，或由用户把根目录中的 29 个更新文件全部替换为 `recovery-official-1.51/SD_ROOT` 内的官方文件。

   ```sh
   CARD="/Volumes/卡名"
   PKG=/Users/wu/.t3/projects/projectricoh/artifacts/stage1a-probe/packages/stage1a-probe-ok-ng
   cp -X "$PKG"/recovery-official-1.51/SD_ROOT/* "$CARD"/
   dot_clean -m "$CARD"
   (cd "$CARD" && shasum -a 256 -c "$PKG"/recovery-official-1.51/SHA256SUMS)
   ls -A "$CARD"
   ```

2. 确认 29 行全部 OK，安全弹出并断开 USB。保持 A12 50mm 连接。
3. 关机状态下按住 `+`，同时按住回放 2–3 秒。核对对象，用 Fn2 选择 Yes，再按 MENU/OK。
4. 保持电源、卡、模块连接，等更新完成及自动重启。同版本重刷被拒绝时停止并记录。
5. 复查 BODY MAIN 与 A12 MAIN 为 1.51，回放同一照片变回 `ISO 200`，菜单、JPEG＋DNG 拍摄、正常关机和重新开机均通过后，才记录“本机官方恢复 PASS”。

## 7. 留存真机证据

在 `research/stage1a_probe/` 下另建一个日期目录，保存刷写前版本/ISO、更新状态、首次 OK、各模式 OK/NG、异常及恢复后的照片。结果表须带包 SHA-256、机身/模块 MAIN、每项实际操作、PASS/FAIL/BLOCKED 和照片路径。电脑构建成功与相机验收分别记录；本轮相机验收状态均为待测。
