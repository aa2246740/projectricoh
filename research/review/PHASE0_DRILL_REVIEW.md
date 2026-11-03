# Phase 0 drill 对抗审查

当前交付有 1 项操作说明阻断：刷写步骤要求解压一个未交付的演练 ZIP，与已经填好的目录包身份冲突。成品没有发现错字节、额外文件或校验错误；静态审查支持两处文字改动的已识别显示路径，但不证明真机启动、同版本写入或恢复成功。

审查日期：2026-10-13。对象：GXR 机身与 GR LENS A12 50mm F2.5 MACRO 的 Phase 0 演练。固件与包全程只读，没有操作相机、SD 卡或刷写程序。临时脚本、测试输出和反汇编都在 `/tmp/projectricoh-phase0-review-7l37oe4m/`。仓库唯一交付写入是本报告。

文中三个被审查的报告、`xrefs.py` 和 `evidence/` 均位于 `research/phase0_drill/`。临时 `disassembly/` 和引用的扫描 JSON 均相对于上面的临时目录。

下面的行号属于本次读取的文件版本。三个报告的 SHA-256 为：

- `research/phase0_drill/ROOT_VERIFICATION.md`：`5e2a05cbc11c81d4bbe945545191869042c1c4b21a8122a36cd403acee466024`
- `research/phase0_drill/CHANGE_CANDIDATE.md`：`54ed217d776252821669836c95b72d4dc987f4a5463352548bd0529c26c96d6f`
- `research/phase0_drill/FLASH_AND_RECOVERY.md`：`0a9aa36e74c320de640485a8861b1a2d166e4c0d365de6c35e11307688cb9c94`

## 发现及修法

1. **阻断：实际目录包与刷写第一步的 ZIP 指引冲突。**

   证据：`FLASH_AND_RECOVERY.md:30` 指定演练目录 `artifacts/phase0-drill/packages/phase0-drill-isx/drill/SD_ROOT`；`:32` 单独指定恢复目录。`:46` 却要求“解压已核验的演练 ZIP”。独立文件清点确认当前交付是目录，包内没有演练 ZIP。实际存在的官方 `gxr-151.zip` 是另一套输入，上游修改器也采用 ZIP 输出形式，不能让用户自行猜测该解压哪一个。

   影响：用户可能复制官方恢复包、旧修改包，或把整个包目录连同两套文件复制上卡。相机的 1.51 版本页无法区分这些内容。

   修法：把第 46 行改成“打开 `artifacts/phase0-drill/packages/phase0-drill-isx/drill/SD_ROOT`，仅复制其中的 29 个升级文件到 SD 卡根目录”。明确 `SHA256SUMS`、`manifest.json` 和 `recovery-official-1.51` 不复制到演练卡；恢复时仅使用恢复 `SD_ROOT` 的 29 个文件。修正后重新通读第 1、2、4 节，核对三处路径一致。

2. **重要：直接引用扫描支撑不了“所有消费者完整排除”的结论；邻接数值表存在计算寻址。**

   证据：`ROOT_VERIFICATION.md:7` 把每份字符串的“一处代码引用”写成全称结论，`:25` 又称引用证据完整。实际 `xrefs.py:28-42` 只把低位指令与此前最多 16 个 word 内的同寄存器 `seth` 配对，`:48-53` 扫描 BE32 字面值。这不能覆盖寄存器搬运、索引运算或跨过程数据流。`CHANGE_CANDIDATE.md:34` 和 `ROOT_VERIFICATION.md:60` 已承认部分限制，但首段没有保留限定。

   我重新反汇编全部 16 个 LOAD 段，并另做 `seth/or3/add3/mv/addi/add/ld` 常量和有效地址排查。直接构造仍只有 `0x2031844C → 0x2037BB6E`、`0x20319C64 → 0x2037BB84`；没有发现指向改动的 `O` 字节 `0x2037BB70/0x2037BB86` 的直接构造或 BE32 指针。相邻的逐字节复制分别止于 `0x2037BB6D` 和 `0x2037BB83`，没有越过到候选字符串。

   新增需要保留的边界是 `0x2037BB94` 数值表。四处计算访问为：

   - VMA `0x2031B9EC` / file `0x2D0BEC`：从 0 开始、受 `cmpui #15` 限制的正向遍历，读取表本身。
   - VMA `0x2031BBEC..0x2031BBF0` / file `0x2D0DEC..0x2D0DF0`：`0x2037BB94 + 4*r4 - 4`。
   - VMA `0x2031C594..0x2031C5A0` / file `0x2D1794..0x2D17A0`：对调用者传入的 `r6` 使用同一表达式；只有零值分支在该窗口内得到确认。
   - VMA `0x2031CDF4..0x2031CE00` / file `0x2D1FF4..0x2D2000`：对调用者传入的 `r5` 使用同一表达式；同样有零值分支。

   这没有证明真实相机会越界。它说明还需要参数范围证据。算术上，索引 `-3` 会落到 `0x2037BB84`，索引 `-8` 会落到 `0x2037BB70`。我检查了这些函数的 1、4、6 个已识别直接调用点，部分参数来自 `0x205E4470` 或其他函数返回值，尚未完成所有写入来源的范围证明。不能把这些假设索引写成已观察的实际消费者或已证实故障。

   修法：把结论改为“目前识别出的直接消费者用于显示；未识别出会读取补丁字节的其他间接路径，邻接数值表的索引范围尚未完全证明”。如要继续使用“引用完整”，补充数值表索引的全部来源与范围证明。证据：`/tmp/projectricoh-phase0-review-7l37oe4m/computed-census.json`；`disassembly/index-bb94-a.txt:26-39`、`index-bb94-b.txt:34-36`、`index-bb94-c.txt:25-36`、`index-bb94-d.txt:21-32`；`callers-index-b.json`、`callers-index-c.json`、`callers-index-d.json`。

3. **重要：“整条使用链无内容分支”和“两份都改必然可见”均超过证据。**

   证据：`ROOT_VERIFICATION.md:7` 声称整条使用链没有依赖文字内容的分支。实际 `evidence/19-format-literal-processing.objdump.txt:24-26` 比较字符与 `37`，即 `%`；`evidence/15-ascii-glyph-map.objdump.txt:29-37` 按字符范围选择分支，`:100-107` 根据 NUL 和长度停止。这些分支是真实存在的。对这次改动可确认的是 `O/X` 同属大写字母分支，且格式串的 `%d` 没变。

   `ROOT_VERIFICATION.md:25` 的“无论机身走哪条路径，屏幕上都会显示 ISX”也不成立。两处生成函数都会在低 ISO 标志 `0x205E42F9` 非零时，以未修改的 `ISO-LO` 覆盖输出。见 `evidence/01-iso-normal-producer.objdump.txt:47-58` 和 `04-iso-alternate-producer.objdump.txt:47-58`。此外，另一条 ISO 显示路径使用未修改的 `0x2037A23E`，file `0x32F43E`，由 `0x202E6E40` 附近代码生成；普通按键到本次两个函数的完整路径仍未证明。见 `evidence/29-iso-capture-producer-unselected.objdump.txt:25-33`。

   修法：改成“两份补丁覆盖了已识别的两个数字 ISO 文本生成函数；在数值有效、低 ISO 标志为零且该画面实际使用这两个函数时，预期显示 ISX”。保留真机可达性与字形待验收。首段改成“已观察链中，O/X 不改变格式解析和大写字母转换的分支”。

   对双处修改的判断：两份字符串使用同一格式函数、共享缓冲区和 ASCII 绘图类型，已知路径上的改动机制相同。扩大覆盖范围有依据，未发现第二处引入独有的格式或缓冲区问题。这个判断是静态、条件性的；worker 的可达性缺口和第 2 项的间接引用边界仍然存在。

4. **重要：卡上核验缺少可执行方法；“看不到 ISX 不算危险”是无证据的安全判断。**

   证据：`FLASH_AND_RECOVERY.md:16,31-35,62` 要求数量和哈希匹配，但 `:47` 只要求“核对 29 个文件已复制完整”，没有说明如何从卡上读回 29 个文件核验。`:29` 又把“所有画面都看不到 ISX”写成“不算危险”。文件数相同、版本同为 1.51、更新器校验通过，都无法证明用户选中了本次演练包；上游资源失败实验已经出现“校验通过、能够启动、菜单乱码”，见 `sources/gxr-language-patch/研究资料/报告/GXR_1.51_英文入口重定向简体中文_保底包报告.md:8-15`。

   修法：在安全弹出之前，明确要求从卡上读回核验。当前工作目录设为实际 SD 卡根目录后，用电脑上已核验的演练清单执行下面的只读命令，29 项都必须为 `OK`：

   ```sh
   shasum -a 256 -c /Users/wu/.t3/projects/projectricoh/artifacts/phase0-drill/packages/phase0-drill-isx/drill/SHA256SUMS
   ```

   恢复卡使用 `recovery-official-1.51/SHA256SUMS`，不能用演练清单。检查 29 个升级文件名完整且没有另一套升级文件；相机产生的照片目录不算升级文件。以上是说明的修法，本次没有读取或操作任何 SD 卡。

   把第 29 行改为“可见标记验收失败，记录画面并停止继续实验。只有先前更新已经结束且正常升级器仍可用时，按第 4 节恢复；无法启动或无法进入升级器时，按第 4 节未证明的救援边界处理”。不要凭缺少标记判定安全，也不要因此反复刷演练包。

5. **一般：恢复章节标题和未交付措辞混合了不同证据状态。**

   证据：`FLASH_AND_RECOVERY.md:5` 仍称本文待补全，`:100` 称具体补丁尚未交付；`:16,21,30-35` 则已填入最终成品。`:75` 仍引用“占位内容补全后”的步骤。`:84` 使用 `PROVEN` 标题，但 `:86-90` 正确承认同版本恢复没有在本机实测。

   同版本支持来自 `sources/gxr-language-patch/README.md:20-21,87-90,159-160` 的作者说明与特定真机反馈。资源失败报告 `:184-189` 把同版本更新和异常恢复列为当时未验证项。两者是不同时间和不同实验的证据，不能合并为本机恢复实证。

   修法：删除已经失效的待补全、尚未交付和占位措辞；把标题写成“已核验官方文件与正常更新步骤；本机同版本恢复待测”。保留现有的无法启动救援缺口和同版本拒绝时停止的规则。`CHANGE_CANDIDATE.md` 的单处候选范围可保留为研究记录，明确实际成品以两处 `spec.json` 为准。

6. **建议：把验证脚本的输出路径做成显式参数，方便以后保持审查只读。**

   证据：`scripts/verify_build_drill.py:12` 固定 `OUT` 为仓库内 `artifacts/phase0-drill/builder-verification.json`，`:132-133` 会创建目录并写结果。直接执行用户给定命令会写该文件，导入同目录构建器还可能生成 Python 缓存。

   修法：增加显式结果输出路径或不落盘模式。本次未改脚本。将两个脚本原样复制到 `/tmp/projectricoh-phase0-review-7l37oe4m/scripts/`，官方输入和 CSV 通过只读使用的符号链接引用原文件，在临时工作区实际执行：

   ```sh
   TMPDIR=/tmp python3 -I scripts/verify_build_drill.py
   ```

   原样脚本的 SHA-256 与仓库一致。输出是 `{"status": "passed", "refusals": 10, "write_checks": 4}`。结果文件只写到临时工作区。

## 独立完成的检查

以下通过项限定于电脑文件与静态代码，不代表真机验收。

- **包完整性通过。** 对官方、演练、恢复三套目录分别清点，均为 29 个普通文件，没有多余、缺失或链接文件。官方 29 文件逐个匹配上游固定 SHA-256 表，并与原始 `gxr-151.zip` 每个成员逐字节相同。ZIP CRC 检查通过，ZIP SHA-256 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。两份 `SHA256SUMS` 的 29 个条目全部正确，manifest 内每个文件的哈希也匹配实际文件。证据与重跑命令：`python3 -I /tmp/projectricoh-phase0-review-7l37oe4m/package_audit.py`，结果 `/tmp/projectricoh-phase0-review-7l37oe4m/package-audit.json`。

- **精确差异通过。** 仅演练 `ilaunch3` 与官方不同，零基文件偏移只有 `0x16F:12→5a`、`0x330D70:4f→58`、`0x330D86:4f→58`。文件长度 `0x3CEEFC`；be32@`0x164` 为 `0x3CECFC`。独立逐字节重算 payload 加权和，官方为 `0x6ACDB212`，演练为 `0x6ACDB25A`。文件头除 checksum 外完全一致；版本 `[0x12,0x18)` 为 `01 51 00 00 00 35`，16 个段表记录、长度和其他头字段未变。直接从官方头部重读段记录，与 CSV 逐项匹配。两处 7 字节窗口、原 NUL 和 `%d` 都正确。演练 `ilaunch3` SHA-256 为 `bc1197b5323799a943b435ed206608bd20b3ae276b28f7acbc2e59f625df3f34`。

- **构建器复现通过。** 原样复测得到 english `e543f5866bbc99ad4697c6dddb931c5a0fa0526fed34c421541ae32fb7f0c785`、unlock `1a383ab94db6bcc4b00583ca3d61339b7f39917aeaf8ec3be9c8809b222c9439`。另在原 checkout 执行 `python3 -I scripts/build_drill.py firmware/phase0_drill/spec.json`，没有传 `--output`，只在内存核验 spec；所得哈希与成品一致，没有重建或覆盖包。上游真机反馈支持容器处理先例，不证明这个新字符串补丁在当前机身通过。

- **已识别显示链通过，有上述覆盖边界。** 重新提取并反汇编全部 16 个 LOAD 段，现有 32 个证据窗口的原始字节 SHA-256 和指令逐条匹配。例如实际命令为 `research/tooling_m32r/prefix/bin/m32r-elf-objdump -D -b binary -m m32r -EB --adjust-vma=0x20319c00 /tmp/projectricoh-phase0-review-7l37oe4m/disassembly/01-iso-normal-producer.objdump.bin`。记录在 `/tmp/projectricoh-phase0-review-7l37oe4m/disassembly/existing-evidence-checked.json`，重跑工具 `/tmp/projectricoh-phase0-review-7l37oe4m/dump_and_compare.py`。字符串扫描扩展到 `[0x2037B900,0x2037BC00)`，缓冲区扩展到 `[0x20234BA0,0x20234C10)`，描述扩展到 `[0x20233AD0,0x20233B48)`。另做寄存器常量传播和有效地址排查，结果保存为 `computed-census.json`；它是候选清点，不能替代全程序控制流证明。 再对全部 29 个官方文件扫描本次字符串起点、O 字节和 `0x20234BD0..0x20234BD9` 的 BE32 指针及短窗口地址构造，其他 28 个文件没有确认的直接命中。`l06firm3:0xAA6EC` 的候选经反汇编排除：`0xAA6E8` 已重新 `seth r1,#0x2013`，实际目标为 `0x2013BB70`。证据 `all29-target-census.json` 和 `disassembly/l06-false-seth-pair.txt`；这仍不排除外部文件里的任意间接寻址。

- **格式和字形没有发现 X 特有的异常分支。** `0x200BBC7C` 经 `0x200BE43C` 将普通字符交给复制回调 `0x200BF958`，后者调用 `0x200BBF80`，其指令行为是按长度复制字节。字符解码 `0x200BF998 → 0x200BFA00` 在 `0x200BFA48..0x200BFA4C` 以 `128` 为多字节处理分界，`O/X` 都走单字节分支。改动位于 `%` 前，普通字节解析路径相同。ASCII 字形函数 `0x201D3190` 将 `0x41..0x5A` 按 `byte-42` 转换，`O→0x25`、`X→0x2E`，都在该范围内。实际字形和像素宽度没有运行时证据。

- **共享缓冲区和 +16 字段已检查。** 直接构造 `0x20234BD0` 的 4 处都属于两个生成函数的格式化写入，没有发现将其直接传给比较函数的调用。BE32 指针位于 `0x20233AF4`，两个显示描述 `0x20233AF8/0x20233B10` 通过该单元取文本。两个描述的 `+16` 指向 `0x20234BD9`；初始 `+20` 为 0。泛型消费者 `0x201E9684..0x201E9690` 实际执行“读 +16 指针、加 +20、读一个字节、写入目标描述 +14”，不能省略为无消费者。证据 `evidence/14-osd-ascii-normalize.objdump.txt:26-29`，原始 `0x20234BD9` 为 `03`。ISO 数值有效范围 1–9999，最大 `ISX 9999\0` 是 9 字节，仅占 `0x20234BD0..0x20234BD8`；这次替换没有扩大写入到 `0x20234BD9`。未证明所有未知别名访问，不能称全程序无比较。

- **比较函数与相邻复制已排查。** 按指令行为识别 strcmp 型 `0x200BC194`、strncmp 型 `0x200BC2EC` 和 memcpy 型 `0x200BBF80`，原固件没有可依赖的函数符号名。原始地址构造扫描分别找到 236、160、119 个候选，没有 BE32 函数指针；常量参数排查未找到把本次字符串或 `0x20234BD0..0x20234BD9` 直接传给前两个函数的调用。复制函数在格式回调中用于输出普通字符。相邻模块名使用 strcpy 型 `0x200BC220`，相邻编号缓冲区 `0x20234BDA` 使用 strncpy 型 `0x200BC318`，与 ISO 输出区分开。六个邻近半字跳转表经范围检查，没有落到补丁区域；四个 `0x2037BB94` 数值表访问的证明边界见第 2 项。未发现跨字符串 NUL 遍历至补丁的已识别路径。

- **额外完整性检查未发现独立第二算法，保留静态边界。** 独立复核 `ilaunch0` 原始头，payload file `0x200` 对应 VMA `0x27E00000`，整文件反汇编基址为 `0x27DFFE00`。file `0x36318` / VMA `0x27E36118` 明确执行余数 6、加 2、乘字节、累加的已知 weighted checksum。更新 wrapper file `0x3AE68` / VMA `0x27E3AC68` 在 `0x27E3ACF0..0x27E3AD08` 调用同一 helper，并比较累计结果。调用点 VMA `0x27E3B0AC` 对应 file `0x3B2AC`；失败出口 VMA `0x27E3B0C8..0x27E3B0D0` 对应 file `0x3B2C8..0x3B2D0`，引用 file `0x82143` 的 checksum 错误文本。另一个内存校验入口 `0x27E36308..0x27E36320` 也调用同一 helper 并读 `+0x16C`。已观察的两个校验入口使用同一加权和算法。检查了四个 body/module 主程序与 monitor 的校验及版本字符串，没有识别出独立段 CRC、密码签名或另一内容校验算法；ROM、硬件、未识别分支与算法仍未排除。段表五字段也没有 CRC 字段。上游 english 的真机成功反馈降低“任意内容改动都会被全局签名拒绝”的可能性，不能排除只针对其他段的检查。

- **同版本和 A12 的新增内容风险没有发现。** 演练与恢复的 `jlaunch0/jlaunch3/jlaunch4/jlaunch8` 都与官方逐字节一致，机身程序的模块选择、版本和格式字段也未变。官方升级手册确实包含模块检查与模块写入步骤，因此不能声称 A12 一定跳过写入。模块主程序在 file `0x136E44/0x136E69/0x136E8D` 有 `SysUnit_FileVersionCheck()` 文本，不能仅凭文本证明同版本写入策略。没有找到这两个显示字节给模块引入官方同版本重刷之外的内容改动风险；实际同版本接受、模块写入是否跳过、恢复成功均留待本机记录。[官方 1.51 页面](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/) 明确列出 body 与 A12 50mm 均为 1.51，按连接的模块识别适用文件。

- **按键与成功判据已对照官方原页。** 通过 web 读取 [官方升级 PDF](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf)，并按本地原 PDF 的实际渲染查看第 1、5 页。原 PDF SHA-256 为 `1bd682dbbb4693726a19ba54d1814c858c52904ceaceff08a75e70299ca368cc`。关机后按住 `[-]` 加回放超过 1 秒查看版本；关机后按住 `[+]` 加回放 2–3 秒进入更新，用 Fn2 选择 Yes，再按 MENU，均与 runbook 的物理按键顺序一致。手册确有更新后自动关机重启步骤。另重新渲染 `research/recipes/sources/GXR_E.pdf` 的 PDF 第 21、55 页，确认照片回放含数字 ISO，DISP. 四种画面循环。推荐把原 runbook 的选照片说明进一步具体化为“官方固件下先拍一张固定数字 ISO 200 的测试照片，再用同一照片、同一信息画面比较”。`ISO-LO` 已被 runbook 明确排除；拍摄界面的 AUTO 和另一条 ISO 生成路径不作为标记判据。

## 复核命令与未验证范围

以下命令可重读这些证据。固件只读，反汇编命令输出到标准输出；独立脚本的文件输出限于本次临时目录。

```sh
research/tooling_m32r/prefix/bin/m32r-elf-objdump -D -b binary -m m32r -EB --adjust-vma=0x27dffe00 --start-address=0x27e36118 --stop-address=0x27e3613c artifacts/firmware/gxr-1.51/ilaunch0
research/tooling_m32r/prefix/bin/m32r-elf-objdump -D -b binary -m m32r -EB --adjust-vma=0x27dffe00 --start-address=0x27e3ac68 --stop-address=0x27e3ad28 artifacts/firmware/gxr-1.51/ilaunch0
python3 -I research/phase0_drill/xrefs.py 0x2037B900 0x2037BC00
python3 -I research/phase0_drill/xrefs.py 0x20234BA0 0x20234C10
python3 -I /tmp/projectricoh-phase0-review-7l37oe4m/scan_constants.py
```

REA 的 `inspect_firmware_regions` 返回 `capability_unavailable`，原文为 `This integration requires Linux and an absolute REA_BINWALK_COMMAND path to the caller-supplied tool`。本机没有用该工具完成固件签名扫描，没有安装其他引擎；以上结论来自原始字节、仓库 M32R objdump 和本次独立脚本。

审查前后对 `artifacts/firmware/` 与 `artifacts/phase0-drill/packages/` 共 90 个文件重新清点并计算 SHA-256，文件清单与内容均未变。7 个被审查的源码、spec 和文档哈希也未变。证据为临时目录的 `protected-before.json`、`protected-after.json` 与 `reviewed-source-sha256.json`。

本机待验证项是 build → flash → boot → visible change → reflash official 1.51 的实际闭环。坏主程序后正常更新器是否可达、备用块或 Monitor 是否能救援，仍没有本机证据。第 1 项修正后，也只能消除说明中的选包歧义。

BLOCKING: 刷写第一步要求未交付的演练 ZIP，与实际目录包冲突，必须先修正选包指引。

