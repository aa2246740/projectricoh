# Phase 0 演练：刷写与条件恢复

本演练的恢复路径是用完整官方 1.51 包执行正常 SD 卡更新，前提是相机仍能启动、读取卡并进入更新确认画面。主程序不启动后的救援尚未在用户的相机上验证。

核验日期：2026-10-13。目标组合是 GXR 机身与 **GR LENS A12 50mm F2.5 MACRO**。本次只读取官方文件、上游源码和报告，下载并核对官方手册；没有修改固件、运行修改器、构建更新包或操作相机。演练包随后已构建，并经主代理核验（[ROOT_VERIFICATION.md](ROOT_VERIFICATION.md)）和对抗复核（[PHASE0_DRILL_REVIEW.md](../review/PHASE0_DRILL_REVIEW.md)）。这些只是电脑上的文件与静态代码核验，不等于真机验收。

## 1. 刷写前逐项检查

全部满足后，才进入刷写步骤。

- 给电池充满电。上游要求满电；官方手册第 3 页要求电量充足。刷写和恢复都适用这一条件。
- 关机后确认装的是 A12 50mm，记录机身和该模块的版本。关机状态下按住 `-`，同时按住回放按钮超过 1 秒，查看版本页并拍照。此次演练预期 `BODY` 的 `MAIN` 和 `CAMERA UNIT` 的 `MAIN` 都是 `V 1.51`。若实际不同，停止并核对交付范围。`BKUP`、`MONI` 等其他字段没有被要求全部为 1.51，按照片记录原值。[官方手册第 1-2 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf#page=1)
- 备份卡中的照片，并在电脑上确认能打开。格式化会删除卡中的照片。
- 在相机中重新格式化容量至少 64 MB 的 SD 卡。使用设置菜单中的卡格式化项目，按 Fn2，选择 Yes，再按 MENU/OK。关机后取卡。推荐另备一张同样在相机中格式化的恢复卡，刷写前就装好官方文件，避免菜单乱码后还需要操作格式化菜单。[官方手册第 3、5 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf#page=3)
- 把未经修改的官方 `gxr-151.zip` 和其 29 个文件单独保留。恢复目录与演练目录分开，禁止混用。原包 SHA-256 必须是 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。本地 `artifacts/downloads/gxr-151.zip` 已匹配此值，其全部文件也匹配上游官方 SHA-256 表。[官方 ZIP 下载](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/exe/gxr-151.zip)
- 核对下方已填写的演练变化、包身份和差异证据与收到的目录包一致。最终卡文件必须恰好是 29 个升级文件，仅 `ilaunch3` 与官方不同，其余 28 个文件逐字节相同。最终包已于 2026-10-13 构建并核验。
- 刷写前，用**官方固件**回放一张照片，把显示 `ISO 200` 一类信息的画面拍下来，作为对照。

A12 50mm 的连接状态直接影响本次更新对象。官方升级器会依据机身和当前连接的模块选择对应文件。多个模块必须分别连接、分别更新和恢复，给一个模块刷写不会更新另一个未连接模块。本次演练仅覆盖 A12 50mm；更新中不得更换模块。[官方 1.51 页面](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/)，[上游 README 第 43-48 行](../../sources/gxr-language-patch/README.md)

交付负责人已于 2026-10-13 填写以下内容。

```text
PHASE0_VISIBLE_CHANGE = 回放照片时，ISO 标签由 "ISO" 显示为 "ISX"，例如 "ISO 200" → "ISX 200"；数字不变
触发步骤 = 开机 → 按回放键 → 选一张本机拍摄、ISO 显示为数字的照片 → 看"显示信息"画面（手册印刷第 9、43 页：底部中间上行 "F 2.5 1/50"、下行 "ISO 200"）。若画面没有信息栏，按 DISP. 切换到这一画面。DISP. 循环顺序：显示信息 → 详细信息＋直方图 → 高光 → 无信息
主要检查画面 = "显示信息"画面底部的 ISO。第一份字符串的屏幕坐标 (310,428) 与这里对应，证据最强
附带记录 = 记录"详细信息＋直方图"画面左上 ISO 标签的实际显示，供后续比对。这个画面不单独作为演练成败或安全判据，也无法区分两份已修改的字符串。按第 3 节检查主画面、启动、菜单及基本拍摄；任一必要检查失败时，按第 3、4 节停止并有条件恢复
拍摄画面 = 不改，刷写后仍显示 "ISO"。拍摄画面的 ISO 来自第三份 "ISO %d"（0x2037A23E，与快门、光圈、变焦倍率同一组代码），本次没有修改，不能据此判断刷写失败
官方原版表现 = "ISO 200" 一类（刷写前自行拍照留底）
演练固件表现 = 同一照片显示 "ISX 200" 一类；其余文字与官方相同。若照片显示 "ISO-LO"，该文字未改，换一张照片
恢复官方后的表现 = 回到 "ISO 200" 一类，与刷写前照片相同
若所有画面都看不到 ISX = 可见标记验收失败。拍下各画面并停止继续实验，不要反复刷演练包。更新已结束且正常升级器仍可用时，按第 4 节刷回官方；无法启动或进不了升级器时，按第 4 节"未证明"部分处理
演练包形式 = 目录，不是 ZIP：artifacts/phase0-drill/packages/phase0-drill-isx/drill/SD_ROOT（29 个文件）
演练 SHA256SUMS 的 SHA-256 = e8ee44fded22580640b671cd047a722253133649a1127cdb759d867141aef6bf
恢复包 = artifacts/phase0-drill/packages/phase0-drill-isx/recovery-official-1.51/SD_ROOT（29 个官方原文件）；其 SHA256SUMS 的 SHA-256 = 51a4d618f4cc0871b44bbb8b2492a380bfea7924729b9717d2ef61acbab405b0
演练 ilaunch3 SHA-256 = bc1197b5323799a943b435ed206608bd20b3ae276b28f7acbc2e59f625df3f34
改动 = ilaunch3 文件 0x330D70 与 0x330D86 两处 4f→58（两份 "ISO %d" 的 O→X），以及 0x16C 校验 0x6ACDB212→0x6ACDB25A（只有末字节变化）；其余 28 个文件与官方逐字节相同
最终 29 文件差异及校验记录 = research/phase0_drill/ROOT_VERIFICATION.md；artifacts/phase0-drill/packages/phase0-drill-isx/manifest.json
```

照片文件本身不受影响：改的是机身显示文字，照片里记录的 ISO 是数值。演练期间拍的照片，刷回官方后应重新显示 `ISO`。

### 本机实际版本与调整后的顺序（2026-10-13）

版本页显示机身 `MAIN V 1.51`（CV `000035`），镜头单元 `MAIN V 1.50`（CV `000034`），触发停止条件。1.51 包内全部文件的版本字段为 `0151`、CmpVer 为 `0035`，因此装着这枚 A12 50mm 刷任何一份 1.51 包，都预期会把镜头单元升到 1.51，且现有文件无法回退到 1.50。用户同意升级后，顺序调整为：

1. **先刷官方 1.51**（`recovery-official-1.51`，第 4 节第 2 步的命令）：镜头单元升到 1.51，机身同版本重刷。顺带在本机验证官方包刷写路径。刷写过程中记录是否出现 `[Updating body firmware]`；它表示升级器会重写同版本机身，演练包才可能写入。
2. 版本页两边 `MAIN` 都是 `V 1.51` 后，再按本节刷演练包。
3. 最后按第 4 节刷回官方 1.51。

卡已在相机中格式化后，原来的 `100-1127` 已不在卡上。格式化后先拍一张测试照片，回放时底部显示 `ISO` 加数字，用它做后续对照。证据见 `captures/a12-50/2026-10-13/P0-version-page/observation.json`。

## 2. 按官方按键顺序刷写

按 MENU/OK 确认 Yes 后即开始更新。更新期间不要关机、取出电池、拔卡或拆卸模块；不要用强制断电处理等待时间。这些禁令来自[上游 README 第 115-117、163-164 行](../../sources/gxr-language-patch/README.md)。所核对的英文官方升级手册没有明确写出这条中断禁令，不能把它冒称为该 PDF 的原话。

按以下步骤操作。

1. 演练包是一个目录，不是 ZIP。只复制 `artifacts/phase0-drill/packages/phase0-drill-isx/drill/SD_ROOT` **里面**的 29 个文件到 SD 卡根目录。不要复制 `SD_ROOT` 文件夹本身、`SHA256SUMS`、`manifest.json` 或 `recovery-official-1.51` 目录，也不要放进 `DCIM`。在 Mac 终端执行（`/Volumes/卡名` 换成实际卡的挂载路径）：

   ```sh
   CARD="/Volumes/卡名"
   PKG=/Users/wu/.t3/projects/projectricoh/artifacts/phase0-drill/packages/phase0-drill-isx
   cp -X "$PKG"/drill/SD_ROOT/* "$CARD"/
   dot_clean -m "$CARD"
   (cd "$CARD" && shasum -a 256 -c "$PKG"/drill/SHA256SUMS)
   ls -A "$CARD"
   ```

   `dot_clean -m` 删除 macOS 在 FAT 卡上生成的 `._*` 附属文件。`shasum` 必须 29 行全部为 `OK`。`ls` 应看到这 29 个升级文件；macOS 自动生成的隐藏目录（`.Spotlight-V100`、`.fseventsd`、`.Trashes`）和相机建的 `DCIM` 不算升级文件，不能出现第二套升级文件。这一套命令已在 64 MB FAT32 磁盘镜像上实测：复制后 29 个 `._*` 被清除，读回 29/29 OK。
2. 安全弹出卡（`diskutil eject "$CARD"` 或拖到废纸篓）。若通过 USB 复制，确认相机关机并断开 USB，再进入更新操作。[官方手册第 2、4-5 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf#page=4)
3. 把卡装回装有 A12 50mm 的相机，确认相机关机。
4. 按住 `+` 不放，同时按住回放按钮 **2-3 秒**，直到出现更新确认画面。
5. 在确认写入前核对更新识别结果。画面如显示机身、模块或版本，必须与已记录的 A12 50mm 组合及 1.51 预期相符。确认页未显示的字段以事先拍下的版本页核对，不虚构画面上有这些信息。任何不符或无法确认的情况，执行下节的停止条件。
6. 仅在检查全部通过后，用 Fn2 选择 Yes，再按 MENU/OK 确认。
7. 等待相机完成更新并自动关机、重启。官方手册说明更新会经过传输、检查模块、检查机身及写入状态，状态顺序可能不同；重启后显示版本页。[官方手册第 5 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf#page=5)

官方第 5 页的关键原文片段是 "[+] button"、"(Playback) button (2) for 2-3 seconds."、"Use the Fn2 button to select [Yes]" 和 "the MENU button."。页面图示确认是回放键，不是数字 6 键；部分 PDF 文本提取把回放图标识别成 `6`。同一手册的格式化步骤把中间确认键称为 MENU/OK，更新步骤简称 MENU。上游 README 第 115-116 行使用 `+`、回放 2-3 秒、Fn2 选择是、MENU/OK，物理按键与顺序一致。[官方原页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf#page=5)，[上游 README](../../sources/gxr-language-patch/README.md)

### 确认写入前的停止条件

出现任一项，停止，不确认 Yes。

- 更新器不识别文件、不出现正常更新确认画面，或报出 `Incorrect rewriting file`。官方第 6 页要求核对机型与正确固件；本演练先停止查原因，不重复确认写入。[官方手册第 6 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf#page=6)
- 机身或模块版本与预先记录或 1.51 预期不同，模块不是已确认的 A12 50mm，或更新对象无法确认。
- 卡上读回核验没有 29 行全部 `OK`、卡上有第二套升级文件、复制不完整，或电量不足。

选择 No 退出的操作见[上游失败实验报告第 195-204 行](../../sources/gxr-language-patch/研究资料/报告/GXR_1.51_英文入口重定向简体中文_保底包报告.md)。该段是上游操作建议，本次没有在相机上验证 No 的退出行为。停止条件适用于写入前；写入已经开始时，不用断电或拔卡来中止。

### 官方手册的其他警告

第 3、5 页提醒格式化会丢失照片。第 4 页提醒跳过安全弹出可能导致固件复制失败。第 6 页说明格式化也会删去卡上的升级文件，并要求多个模块分别更新。恢复包应保留在电脑上的独立目录，不能只依赖一张之后可能被格式化的卡。[官方手册](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf)

## 3. 检查演练是否成功

以下项目必须逐项记录实际结果。本次研究没有替用户通过这些检查。

- 相机完成自动重启，机身与 A12 50mm 正常工作；再正常关机、开机一次，仍能启动。
- 按第 1 节的触发步骤，在"显示信息"画面看到 `ISX`，拍照记录。版本号仍是 1.51 不能单独证明演练补丁已生效。拍摄画面仍显示 `ISO` 属于预期。
- 打开拍摄菜单、设置菜单和回放界面，文字可读，没有乱码、混合字形或缺字。
- 在该机原本可用的语言之间切换，再切回原语言，菜单仍可读。记录实际语言选项；不要求 Phase 0 新增语言或解锁 11 种语言。
- 用 A12 50mm 拍摄并回放一张研究照片，检查没有明显异常。此项只检查基本使用路径，不证明全部拍摄模式都通过。

如果更新完成后还能进入正常升级器，但上述任一项失败，停止继续实验，按下一节刷回官方包。把“演练检查通过”和“本机恢复检查通过”分开记录。

## 4. 用官方 1.51 恢复及其证据边界

### 已核验：官方文件与正常更新步骤，本机官方恢复已实测（2026-10-14）

可采用的恢复方式是将未经修改的官方 1.51 全部 29 个文件放在卡根目录，按正常更新流程刷回。它必须同时满足相机仍能启动、读取卡、进入更新确认画面并完成写入的条件。

**本机已实测（2026-10-13/14）：** 先用官方包把镜头单元由 1.50 升到 1.51（机身同版本重刷），再刷入演练包、回放显示 `ISX`，最后刷回官方包、回放恢复 `ISO`。同版本重刷和官方恢复在这台机身与 A12 50mm 上均已成功，证据见 `captures/a12-50/2026-10-13/P1-official-upgrade/` 与 `captures/a12-50/2026-10-14/P0-recovery-confirmed/`。这证明的是**相机仍能启动、升级器可用**时的恢复；主程序损坏后的救援仍未证明，见下一节。

上游 README 第 20-21 行明确声称 1.51 可在 1.51 上再次更新，第 87-90 行说明刷回官方后英文入口恢复，第 99-105 行要求解锁后刷回官方，第 159-160 行仅说明特定真机已有成功反馈。它没有给出用户这台相机的恢复证据。失败资源包报告第 15 行要求用官方包恢复，第 188-189 行仍列出异常恢复与硬件救援的未知项；该报告没有记录官方恢复完成。因此不能把失败报告中的恢复建议当作一次已观察的恢复成功。[上游 README](../../sources/gxr-language-patch/README.md)，[失败实验报告](../../sources/gxr-language-patch/研究资料/报告/GXR_1.51_英文入口重定向简体中文_保底包报告.md)

这一节的范围指官方正常更新流程与文件身份，以及上游报告支持的有条件重刷方式。它不表示本机恢复已经验收，也不表示发生任意故障都能救回。[本地恢复约束，第 7-15 行](../../docs/A12_50_DEVELOPMENT.md)

满足上述条件后，按以下步骤恢复。

1. 确认先前更新已结束，能够正常关机。继续使用同一 A12 50mm，换用满电电池。
2. 使用预先准备的官方恢复卡。若重新准备卡，先备份照片并在相机中格式化，再执行下面的命令。它复制的是 `recovery-official-1.51/SD_ROOT` 里的 29 个官方文件，并用恢复清单读回核验，29 行必须全部 `OK`。不能用演练清单核验恢复卡，不要只替换 `ilaunch3`，不要混入演练文件。

   ```sh
   CARD="/Volumes/卡名"
   PKG=/Users/wu/.t3/projects/projectricoh/artifacts/phase0-drill/packages/phase0-drill-isx
   cp -X "$PKG"/recovery-official-1.51/SD_ROOT/* "$CARD"/
   dot_clean -m "$CARD"
   (cd "$CARD" && shasum -a 256 -c "$PKG"/recovery-official-1.51/SHA256SUMS)
   ls -A "$CARD"
   ```

   安全弹出并断开 USB。
3. 关机，按住 `+`，同时按住回放 2-3 秒。核对版本与对象，用 Fn2 选择 Yes，按 MENU/OK。
4. 全程保持电源、卡和模块连接，等相机完成并自动重启。同版本重刷若被拒绝，停止并记录画面，不改版本号或绕过检查。
5. 检查机身与 A12 50mm 的 `MAIN` 为 `V 1.51`，演练可见变化消失，菜单和语言切换正常，再正常关机、开机复查。只有实际完成这些检查，才记为本机恢复通过。

刷回官方程序不等于清除所有持久设置。上游完全解锁模式会写入地区设置，README 第 18、133-134 行声称恢复官方后仍保留；不能把该模式当作“刷回就完全撤销”的演练。本次 Phase 0 只改 `ilaunch3` 两处显示文字，不写入设置或地区值；差异与复核见 [ROOT_VERIFICATION.md](ROOT_VERIFICATION.md) 和 [PHASE0_DRILL_REVIEW.md](../review/PHASE0_DRILL_REVIEW.md)。刷回官方后显示是否完全复原，仍以第 5 步的真机检查为准。

### 未证明：主程序损坏后的救援

以下能力没有在用户这台 GXR 与 A12 50mm 上证明。

- 主程序错误或写到一半后，仍能通过普通卡更新恢复。
- `Boot & Monitor` 或 `Backup prog blk` 对应的维修入口可由普通用户进入，或独立于损坏的主程序运行。
- 相机不再启动、不能读取卡、不能进入更新确认，或机身与模块无法通信时，有可执行且经过验证的恢复流程。
- 更换模块、某个未公开按键组合、USB 维修命令、备用程序块或外部编程器能恢复此设备。

本次独立复查了 `ilaunch0`、`ilaunch3`、`jlaunch0`、`jlaunch3` 的维修相关字符串。它们是维修结构线索，不能证明入口、按键、写入范围或故障后的可达性。本文不提供猜测的 Monitor 救援按键。[字符串证据](../../artifacts/development/environment-and-recovery-strings.json)，[本地风险说明第 25-32 行](../../docs/A12_50_RAW_AND_RISK.md)

如果已经不能启动、读卡或进入确认画面，停止自行重刷和试探维修入口，保留包哈希、版本照片和异常过程记录，交给项目负责人或具备该设备维修能力的人评估。当前没有可承诺的用户自助救援步骤，也没有经过验证的中途写入超时阈值。

## 5. 风险低但不为零的依据

Phase 0 用一个小的 `ilaunch3` 可见变化和 28 个原样文件控制变更范围，避免同时动模块资源与持久地区设置。上游英文替换和解锁代码补丁有特定真机成功反馈，不能推导本次新补丁也安全。2026-07-30 的失败先例修改了包括 `ilaunch4` 在内的七个 `launch4` 资源文件，静态校验和刷写通过后仍出现乱码，连切换日语也没有恢复。文件校验只证明格式与字节符合要求，不能证明启动和菜单正确。修改机身主程序仍可能使正常升级入口失效；28 个文件保持官方也不证明升级器会跳过写入这些文件。这里的“低风险”是控制范围的目标，没有经过测量的失败概率。[上游 README 第 130-160 行](../../sources/gxr-language-patch/README.md)，[失败实验报告第 6-15、54-66 行](../../sources/gxr-language-patch/研究资料/报告/GXR_1.51_英文入口重定向简体中文_保底包报告.md)

## 附录：独立核验方法与结果

### A. 官方输入、手册与源码身份

- 官方 ZIP：`artifacts/downloads/gxr-151.zip`，SHA-256 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。本次验证了本地文件与任务给定身份一致，没有再次下载官方 ZIP 作网络逐字节比对。
- 官方解压目录：`artifacts/firmware/gxr-1.51`，正好 29 个普通文件；每个文件与 ZIP 对应项逐字节相同；ZIP CRC 检查通过。
- 官方英文升级手册：从指定 URL 实际下载，6 页、231693 字节、SHA-256 为 `1bd682dbbb4693726a19ba54d1814c858c52904ceaceff08a75e70299ca368cc`。用 `pdftotext -layout` 提取全文，以 `pdftoppm` 渲染并查看第 5-6 页，核对按键图标、步骤和警告。PDF 临时副本为 `/private/tmp/projectricoh-phase0-gxr-fwup-en.pdf`，正式来源仍是[官方 PDF](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf)。
- 上游 checkout：`sources/gxr-language-patch`，HEAD 为 `5a5366dd017827bc4c4e9e65a0253c4b947a78a0`，核验时工作区无修改。修改器 SHA-256 为 `f6713b28341eae15543ea09264bc123d50758917bd94f40a19152b1784f8eab4`。其他输入文件哈希见[结构化事实](flash-recovery-facts.json)。

这 29 个官方文件应全部位于卡根目录。

```text
ilaunch0 ilaunch3 ilaunch4 ilaunch8
jlaunch0 jlaunch3 jlaunch4 jlaunch8
klaunch0 klaunch3 klaunch4 klaunch8
l06firm0 l06firm3 l06firm4 l06firm5 l06firm8
l08firm0 l08firm3 l08firm4 l08firm8
nlaunch0 nlaunch3 nlaunch4 nlaunch8
qlaunch0 qlaunch3 qlaunch4 qlaunch8
```

### B. 官方 ilaunch3 头部与内部校验

实际只读结果为以下值。

```text
path = artifacts/firmware/gxr-1.51/ilaunch3
SHA-256 = da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7
file bytes = 3993340
be32(0x164) payload length = 0x003CECFC = 3992828
len(bytes[0x200:]) = 3992828
be32(0x16C) stored checksum = 0x6ACDB212
sum(b * ((i % 6) + 2) for i, b in enumerate(bytes[0x200:])) = 0x6ACDB212
stored == recomputed = True
```

索引 `i` 从载荷首字节开始为 0，权重依次循环为 2、3、4、5、6、7。修改器第 67-75 行使用 32 位取模；该官方文件的原始加权和为 `1791865362`，未溢出，所以原始和及取模后的值都等于存储值。这里验证的是官方 `ilaunch3`，演练文件还需要独立重算。

以下命令可复跑头部、29 文件哈希和原包对应关系核验。它不导入或执行修改器，也不写任何文件。

```bash
cd /Users/wu/.t3/projects/projectricoh
python3 -I - <<'PY'
from pathlib import Path
import ast
import hashlib
import struct
import zipfile

fw = Path('artifacts/firmware/gxr-1.51')
p = fw / 'ilaunch3'
b = p.read_bytes()
payload_len = struct.unpack_from('>I', b, 0x164)[0]
stored = struct.unpack_from('>I', b, 0x16C)[0]
weighted = sum(v * ((i % 6) + 2) for i, v in enumerate(b[0x200:]))
print(f'payload_length = 0x{payload_len:08X}')
print(f'stored_checksum = 0x{stored:08X}')
print(f'recomputed_checksum = 0x{weighted:08X}')
assert payload_len == len(b) - 0x200
assert stored == weighted == (weighted & 0xFFFFFFFF)

source = Path('sources/gxr-language-patch/gxr_firmware_modifier.py')
tree = ast.parse(source.read_text())
official = next(
	ast.literal_eval(node.value)
	for node in tree.body
	if isinstance(node, ast.Assign)
	and any(isinstance(t, ast.Name) and t.id == 'OFFICIAL_SHA256'
		for t in node.targets)
)
assert len(official) == 29
assert {x.name for x in fw.iterdir() if x.is_file()} == set(official)
archive = Path('artifacts/downloads/gxr-151.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == (
	'3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
)
with zipfile.ZipFile(archive) as z:
	members = [x for x in z.infolist() if not x.is_dir()]
	assert len(members) == 29
	assert {Path(x.filename).name for x in members} == set(official)
	assert z.testzip() is None
	for member in members:
		name = Path(member.filename).name
		data = (fw / name).read_bytes()
		assert z.read(member.filename) == data
		assert hashlib.sha256(data).hexdigest() == official[name]
print('official_files = 29; all_sha256_match = True; zip_matches = True')
PY
```

### C. 29 文件门禁与只替换 ilaunch3 的源码证据

以下行号均属于 `sources/gxr-language-patch/gxr_firmware_modifier.py`，以本附录记录的源码哈希为准。[查看修改器](../../sources/gxr-language-patch/gxr_firmware_modifier.py)

- 第 19-49 行定义 `OFFICIAL_SHA256`。本次用 AST 读取字面量，计数为 29；独立计算官方目录及 ZIP 的全部 29 个 SHA-256，全部匹配。
- 第 205-245 行实现输入读取。目录或 ZIP 必须找到一套完整的 29 文件；第 239-244 行遍历哈希表全部条目，任何 SHA-256 不符都报错。额外说明文件不会加入输出；此门禁并未声称拒绝输入目录中每个无关文件。
- 第 364-365 行先调用 `read_firmware`，再只把 `files["ilaunch3"]` 传给对应补丁函数。
- 第 191-201 行检查原始内部校验，在 `0x16C` 重算并写入新校验，随后核对固定的修改结果 SHA-256。
- 第 313-314 行复制已验证的文件字典，只替换键 `ilaunch3`。第 327-328 行把全部条目写到 ZIP 的 `SD_ROOT`；第 333-338 行把全部条目写到目录的 `SD_ROOT`。按正常 `main` 调用得到 29 个升级文件，只有 `ilaunch3` 取替换内容，28 个文件保持输入字节。
- 第 288-289 行的 manifest 也声明 `file_count = 29`、`modified_files = ["ilaunch3"]`。本次依据输入门禁及输出代码核验，没有仅凭这两项自报字段得出结论。

29 指 `SD_ROOT` 内升级文件数；外层 ZIP 另有 README 和 manifest，不能把整个 ZIP 的文件总数误写成 29。`write_output` 单独被任意代码调用时不会自行重验输入，本结论限定于上述经过 `main` 门禁的正常路径。

修改器只提供 `english`、`unlock` 两个模式，并验证各自固定输出哈希。它不会自动接纳任意 Phase 0 改动。本次未调用任何补丁或输出函数，没有生成包；最终 Phase 0 包的文件数、差异、长度、内部校验及哈希必须另行核验。

### D. 维修字符串与真机先例的证据等级

本次按 `artifacts/development/environment-and-recovery-strings.json` 的明文偏移重新读取四个官方文件；文件哈希、`Boot & Monitor`、`Backup prog blk`、`card version up` 和全部明文 `reboot` 候选字节均匹配。机身 `ilaunch0` 的前两个字符串位于 `0x81db3`、`0x81de9`，机身 `ilaunch3` 对应位于 `0x833f7`、`0x8342d`。这是静态字节证据，没有执行维修代码，也没有验证普通用户可进入的按键序列。

英文替换及解锁代码补丁的成功依据是上游 README 第 159-160 行所述特定真机反馈，本次没有该用户设备的型号批次、刷写日志或录像可作独立实机复核。资源失败依据是上游报告第 6-15 行的 2026-07-30 真机观察；涉及七个资源文件而非只改 `ilaunch4`。两类报告均不等于本项目相机的验收。

本次可确认的安全范围：只读核验不写相机；恢复方法限于正常升级器仍可用时的官方 1.51 全量重刷。
最大未证明项：坏主程序或中途写入后，是否仍有用户可进入的救援流程。
最应遵守的停止条件：机身或 A12 50mm 的版本、更新对象与预期不符时，立即停止，不确认写入。
