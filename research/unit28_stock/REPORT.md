可以交复审

# g146 卡上记录：读写方式、模拟器最终检查、打包（第五轮收尾）

2026-10-31。本轮只在本机离线工作：没有写真实存储卡，没有访问 `/Volumes/RICOHDCX`，没有联网，没有 git 写操作，没有开子代理，同一时间最多 2 个模拟进程。临时文件在 `/Volumes/Workspace/Scratch/tmp/projectricoh/diag146-finish`，结束时删除。DAT 和它的源码没有改。上一轮报告存为 `REPORT-r4-g145.md`。给用户的上卡步骤不在本报告里，由编排者写。

## 结论

- DAT：`firmware/engine_diag_v38_g146/candidate/local/full-r1/GXRCE.DAT`，30,776 B，SHA256 `1a3ed0457540a86100bb1327b9120a05460bb9e0b6169c017e374188cc4b4abd`，搭配机身 v3.8（resident build id `79d8e2a2…`）。
- 模拟器重放脚本 `emu_g146_trace.py` 已改成 DAT 现在的调用：开机读入走 `0x200AAD38`，每条记录用新句柄从位置 0 整文件刷出，写后不读回。调用顺序与 `diag.c`、`bridges.S` 逐个对应（第 3 节）。
- 原版模拟器 `tools/gxr_emulator` 的最终运行 `final7`：PASS，21 项判定全部通过（第 5 节）。
  - 三个单元的记录位置（槽 0、1、2）共 12 条记录全部写成。每次写入只改 GXRTRACE.BIN 自己那个簇里的 2 个扇区，FAT 和根目录不变。
  - 持锁时跳过：先用原厂等待包装拿住 47，DAT 只试一次（返回 −50），没有任何文件调用，卡不变。放开后，下一条记录写成，并带着 `busy_init=1`。
  - 冷启动后第二次开机读入的 8,704 B，等于第一次开机留下的内容：既等于卡上的文件，也等于第一次开机最后的 RAM 映像。之后接着写，两半交替。
  - `decode_trace.py` 解出两次开机的全部记录。每次写完都解码一遍：刚写的那条有效，计数连续，CRC 和提交字正确，同槽另一半仍然有效。
- 任务 id：在模拟器里，**H01、H06、H07、H08 四个入口都没跑到**。依次按了 ADJ、OK、DISP、四个方向键，最后再按一次 ADJ，四个入口都没有命中。原因和 M2d 的结论一致：UI 停在状态 2，没有进入状态 56 的 ADJ 构造。所以无法在入口处比较“当时真正在跑的任务”和 `0x200D1838`。作为替代，在同一条 Task 6 原厂 UI 路径的两个点（`0x202B0B18`、`0x202AFE98`）上比较了 34 次：33 次一致；1 次发生在恢复检查点后、还没观察到任何调度时，无法判定；没有不一致（第 6 节）。DAT 没改。
- FAT32 卡：只有静态论证，没有模拟器运行。静态上 `0x200A6750` 能到达 FAT 脏区间回写 `0x200B0C6C` 和 FAT32 FSInfo 写回 `0x200B76EC`，所以在 FAT32 卡上，“只改这个文件的簇”没有被证明（第 7 节）。
- 包 `firmware/package_v38_diag146/` 已整个重做：
  - `SD_ROOT/GXRCE.DAT`：SHA256 `1a3ed0457540a86100bb1327b9120a05460bb9e0b6169c017e374188cc4b4abd`；
  - `SD_ROOT/GXRTRACE.BIN`：空白 8,704 B，nonce `38bc1137dcceaa074a2ef173de9cd101`，SHA256 `db41ec46c2428b03aa94e8d5e839376aecd3a11d2887876867c38346eadd28cd`（第 10 节）。

## 1. 读写方式和改动

记录文件 `/ATA1/GXRTRACE.BIN` 共 8,704 B：512 B 文件头（`GXRT146\0` 加 16 B nonce，在 Mac 上放好），后面是 8 条 1,024 B 记录。单元槽 k 占记录 2k 和 2k+1，即 A、B 两半；槽 0 是 jlaunch（50mm），槽 1 是 qlaunch（28mm），槽 2 是 l08firm（MOUNT），槽 3 是其他名字。DAT 只打开这个已有文件，从不新建、改名、删除或加长它。

每次同步（`trace_sync`：init 一次，之后每次进菜单一次，每次开机最多写 24 次）：

1. **取锁只试一次**：调用 `0x2005E360(47, 0)`。
   - 返回 −50（计数为 0，不排队）：跳过本次，计 `busy_init` 或 `busy_menu`；
   - 返回其他非 0 值：计 `poll_error`，同样跳过；
   - 只有返回 0 才往下做，做完释放一次 `0x0500D4FC`。
2. **开机读入**：在本次开机第一次取到锁时做。
   - 新开一个句柄：parse `0x200A531C` → lookup `0x200A65F8`（mode 2）→ attach `0x200AB4F0`。
   - 置 mode 2，用 `0x200AAD38(fd, 0, 簇字节数)` 一次读进句柄自己的单簇缓冲。`0x200AAD38` 就是缓冲读 API `0x200A449C` 在自己的等待和释放之间调用的内部函数，g145 run2 已证明它在原厂 FAT 代码上可靠。它不读第二个参数：反汇编 `0x200AAD38..0x200AB028` 里，r5 只在后续调用前被重新赋值。
   - 返回的有效字节数必须正好是 8,704，否则判为长度不对，本次开机不再写。簇不大于 8,704 B 时也拒绝。
   - 然后关闭（release `0x200A6750`）。
   - 读入后核对文件头和 nonce，再用 `rec_valid` 逐条检查 8 条记录。会话号取全文件最大值加 1；本槽先写不含最新有效记录的那一半。
3. **每条记录**：
   - 记录先写进 RAM 映像里本槽当前那一半；
   - 再新开一个句柄，把整个 8,704 B 映像放进句柄的簇缓冲，文件末尾以后到簇末清零；
   - 置 mode 1、位置 8,704，从位置 0 刷出：`0x200AB02C(fd, 8704, 8704 % 簇)`，不 seek；然后关闭；
   - 刷出成功就切到另一半，`written` 加 1；失败计 `write_fail`，`last_failed_seq` 记下序号，下一次仍写同一半。
4. **写后不在相机里读回**。完整性由电脑上的 `decode_trace.py` 判断：CRC32 覆盖记录前 1,016 B，提交字为 `CMIT` ^ 会话 ^ 序号。
5. H01、H06、H07、H08 入口读内核当前任务字 `0x200D1838`，把最后一次的任务 id 和次数、第一次的任务 id 记在记录的备用字里（`hook_task`、`hook_first`）。

和上一版重放（同为 g146）相比，改了两处：

- 开机读入不再用 `0x200ADAD0`。它是直接读 API `0x200A4880` 的内部函数，旧版先 seek 再用它分段读，在模拟器里读回的数据不对。`final2`、`final3`、`final4` 三次运行里，每次写后读回都判为不同（`verify-diff`），第二次开机读入的内容也和第一次留下的不同（`research/emulator_m2d/local/unit28-g146/final2…4/result.json`）。
- 不再 seek：seek 到记录位置后再刷出，原厂报错 236，见第 8 节。

`firmware/engine_diag_v38_g146/STATUS.txt` 的读写描述已按上面更新。原文还写着 lseek、read 和“七个文件内部函数”，现改为六个，与 `bridges.S` 一致。

## 2. 去掉了什么，以及为什么两半交替仍然有保护

去掉的是相机里的“写后读回”和“读回不同”计数。计数位置还留在记录格式里（`trace146.COUNTS` 的 `seek_fail`、`read_fail`、`verify_diff`），DAT 不再增加它们，始终为 0。

改成整文件重写以后，两半交替仍然起保护作用：

- **其他字节写回原值**：刷出的是 RAM 映像。映像来自本次开机读入的卡上内容，之后只改本槽当前那一半。所以每次刷出时，目标半以外的 7,680 B 都和卡上已有内容逐字节相同。模拟器里每次写入，文件内变化的字节都落在目标那 1,024 B 里（第 5 节 `only_target_half`）；按扇区看，每次只变 2 个扇区。
- **写断只坏目标半**：刷出中途断了，没写完的部分只可能在目标半里。目标半的 CRC 或提交字对不上，解码器判它无效（rejected）。同槽另一半是上一条完整记录，字节没变，仍然有效。主机验收的 `cuts` 组在 5 个切点上验证过这一点（`local/accept146-cuts.json`）。
- **失败不切半**：刷出返回失败时，`trace_half` 不翻转，下一条记录仍写同一半；RAM 映像里另一半仍是卡上那条完整记录。所以不会出现两半都坏的情形。`allwritefail`、`partial`、`closefail` 组验证了这一点。
- **为什么可以不读回**：读回只能在本次开机里发现问题，改变不了卡上已写的内容；而且读回用的 `0x200ADAD0` 在模拟器里本身就不可靠。决定证据是否可信的，是下一次开机的读入（已证明可靠的 `0x200AAD38`）和电脑上的解码，两者都只认 CRC 和提交字都对的记录。代价是：最后一条记录没写好时，相机自己不知道；但电脑解码时能看出来，不会把它当成有效。

## 3. 重放与 DAT 源码的对应

重放在 `emu_g146_trace.py` 里，由宿主在 Task 8 发起原生调用。传参方式和 `bridges.S` 的 `NATIVE` 宏一致：C 的 r0..r3 依次传给原生的 r4..r7。

| DAT（`diag.c`、`bridges.S`） | 原生地址与参数 | 重放（`emu_g146_trace.py`） |
|---|---|---|
| `trace_sync` 第 606 行 `dg_lock_try()`（`bridges.S:67`，r4=47，r5=0） | `0x2005E360(47, 0)` | `Run.take()` 第 283 行，由 `Dat.sync()`（第 437 行）调用 |
| −50 → `busy_init`／`busy_menu`；其他非 0 → `poll_error`；直接返回 | — | `Dat.sync()` 同样计数并直接返回，不释放 |
| `fs_open` 第 483 行：打开计数 ≥2 时返回 −2 | 读 `0x204C8668` | `Run.fs_open()` 第 289 行 |
| 第 487 行 `dg_fs_parse(trace_path)` | `0x200A531C(path)` | 第 293 行 |
| 第 488 行 `dg_fs_lookup(FS_TABLE, 2)`，只有 −1 算失败 | `0x200A65F8(0x204C866C, 2)` | 第 294 行 |
| 第 491 行 `dg_fs_attach(fd, e+4, e+2)`，−1 时 `dg_fs_release(fd)` | `0x200AB4F0`；失败时 `0x200A6750` | 第 298–299 行 |
| 打开计数 +1，`e+8=0`，mode 半字清 0 | 写 `0x204C8668` 和句柄项 | 第 301–303 行 |
| `trace_load` 第 544 行：簇 ≤8,704 B 或缓冲越界 → `size_fail`，本次开机不再写 | 读 `e+2`、`e+4` | `Dat.load()` 第 481 行 |
| 置 mode 2；第 550 行 `dg_fs_fill(fd, 0, size)`；`e+12=got`；−1 → `load_read_fail`（下次再试）；不等于 8,704 → `size_fail`（不再写） | `0x200AAD38(fd, 0, 簇)` | 第 491 行起 |
| 拷出 8,704 B，`e+8=8704`；查文件头、nonce；`rec_valid`（第 526 行）；定会话号和写哪一半 | — | `Dat.load()`、`Dat.rec_valid()`（第 529 行） |
| `fs_close` 第 497 行：`e+8=0`，mode 清 0，打开计数 −1，第 501 行 `dg_fs_release(fd)` | `0x200A6750(fd)` | `Run.fs_close()` 第 306 行 |
| 第二次 `fs_open`（新句柄，位置 0） | 同上三个调用 | 同上 |
| `trace_write` 第 586 行：记录写进映像。`fs_write_all` 第 513 行：拷进簇缓冲，簇尾清零，mode 1，`e+8=8704`；第 520 行 `dg_fs_flush(fd, 8704, 8704 % 簇)`；`e+8=0` | `0x200AB02C(fd, 8704, 8704)` | `Dat.write()` 第 538 行，`Run.fs_write()` 第 315 行 |
| 成功 → `written` 加 1，切半；失败 → `write_fail`，记 `last_failed_seq` | — | `Dat.write()` |
| `fs_close` | `0x200A6750(fd)` | `Run.fs_close()` |
| 第 625 行 `dg_lock_release()` | `0x0500D4FC` | `Run.give()` 第 286 行 |

每次同步实际发生的调用顺序都被记录下来，并逐个与 DAT 的调用形状比较（`final7/result.json` 的 `outcomes[].calls`，判定项 `call_order`）：

- 本次开机第一次取到锁：`poll-47, parse, lookup, attach, fill, release, parse, lookup, attach, flush, release, signal-47`；
- 之后每次：`poll-47, parse, lookup, attach, flush, release, signal-47`；
- 锁被占时：只有 `poll-47`。

记录头、计数、CRC 和提交字按 DAT 的规则生成；其余内容是合成的（菜单字只填序号和 `K`），因为模拟器里跑的不是 DAT 本身。

旧的 `probe`、`variants` 两种模式保留下来，只用来复现 `probe1`、`probe2`、`variants1` 三次历史运行。脚本开头已注明它们不是 DAT 的调用。

## 4. 主机验收与静态检查（沿用，本轮未重跑）

| 检查 | 结果 | 证据 |
|---|---|---|
| `run_accept146.py`，27 组，三个单元 | 全过，单组最长 51.6 秒（`28mm-refuse`） | `local/unit28-r5/acc-final/summary.json`、`local/unit28-r5/acc-final.log`、各组 `local/accept146-*.json`（其中记录的 DAT 即 `1a3ed045…`） |
| `lock_proof146.py` | 通过；4 个变异（busy 判断反转、去掉 busy 判断、错误判断反转、去掉释放）都被查出 | `static-diag146.json` 的 `lock_proof` |
| `static_check.py 146` | 通过：引擎里没有 seek、直接读、直接写的调用地址，也没有信号量 47 的等待入口；唯一的路径字符串是 `/ATA1/GXRTRACE.BIN` | `static-diag146.json` |
| 静态调用图（本轮新跑）：DAT 用到的六个文件内部函数 | 共到达 94 个函数，都到不了 47 的等待和释放，也到不了原始信号量包装 | `local/diag146-finish/cg-dat146.json` |

## 5. 模拟器最终检查（`final7`）

运行目录 `research/emulator_m2d/local/unit28-g146/final7/`（`result.json`、`card.img`、`GXRTRACE-final.bin`），日志 `research/unit28_stock/local/diag146-finish/emu-final7.log`。

- 工具：`tools/gxr_emulator`（原版，未改）。
- 机身和单元：官方 1.51 `ilaunch3`，合成 jlaunch 单元。
- 卡：64 MiB FAT16 虚拟卡，每簇 32 扇区（16 KiB）。GXRTRACE.BIN 按普通电脑的方式放在根目录第 1 项、簇 3。
- 耗时 1,504（两次冷启动分别约 746 秒和 648 秒） 秒。超时给到 7,200 秒，是 g145 参照（约 2,215 秒）的 3 倍以上。

| 检查（`checks` 字段） | 结果 | 内容 |
|---|---|---|
| `holder_observed`、`busy_skipped` | 通过 | Task 8 先用原厂等待包装 `0x0500D4E4` 拿住 47（计数 1 → 0）。DAT 的 init 同步只调用一次 `0x2005E360(47,0)`，返回 −50；调用表里只有 `poll-47`；卡镜像逐字节不变，计数仍为 0。持有者释放后计数回到 1。 |
| `busy_carried` | 通过 | 放开后第一条记录（槽 0 第 1 条）写成，解码出 `busy_init=1`、`syncs=2`。 |
| `locks`、`call_order` | 通过 | 13 次同步，每次只试一次 47，超时 0。取到锁的 12 次各释放一次，DAT 调用里没有 47 的等待；调用顺序与第 3 节的形状完全一致。调用期间 FAT 代码只等待了 SD 驱动的信号量 24、25（原厂设备等待，超时参数 3000、4096）。 |
| `all_written`、`fill_8704` | 通过 | 12 条记录全部写成：开机 1 里，槽 0 三条菜单记录，槽 1、槽 2 各一条 init 加两条菜单；开机 2 里，槽 0 一条 init 加两条菜单。4 次读入都返回 8,704。 |
| `only_own_cluster`、`fat_root_unchanged` | 通过 | 每次写入只变 2 个扇区，都是 GXRTRACE.BIN 簇 3 里的文件数据。从开机 1 挂载完到最后，整张镜像只有簇 3 变了：两份 FAT 和根目录（包括本文件的 32 B 目录项）没有一个字节变化，第二次开机的挂载也是零变化。 |
| `boot1_mount_native_only` | 通过 | 第一次开机时、DAT 还没调用之前，原厂在空卡上新建了 `DCIM`（根目录第 2 项、簇 4–5，两份 FAT 各改 2 项），和 g145 run2 一样。本文件的目录项和簇不受影响。 |
| `file_equals_ram`、`only_target_half` | 通过 | 每次写完，卡上文件都等于 RAM 映像；文件内变化的字节只在目标那 1,024 B 里，卡上该记录的 SHA256 等于刚生成的记录。 |
| `decoded_each_write`、`other_half_kept` | 通过 | 每次写完都用 `decode_trace.decode()` 解卡上的文件：刚写的记录有效，会话、序号和 16 个计数都与 DAT 模型一致；同槽另一半如果之前写过，仍然有效。 |
| `halves_alternate` | 通过 | 槽 0：开机 1 依次 A、B、A，开机 2 依次 B、A、B；槽 1、槽 2：A、B、A。 |
| `boot2_readback`、`boot2_continues` | 通过 | 冷启动后读入的 8,704 B 等于开机 1 结束时卡上的文件，也等于开机 1 最后的 RAM 映像。新会话号为 4，第一条写到 B 半；写完后槽 0 的最新记录是会话 4 序号 1，上一条完整记录是 A 半的会话 1 序号 3（含 3 次菜单）。 |
| `counters_continuous` | 通过 | 每个会话的序号都是 1、2、3；每条记录的 `written` 等于序号减 1，`syncs` 连续递增。 |
| `boot1_decode`、`final_decode`、`entry` | 通过 | 开机 1 结束时，文件里有会话 1（50mm）、2（28mm）、3（MOUNT）共 6 条有效记录。最后的文件里有会话 2、3、4，三个槽都判为 `evidence`；会话 1 的两半已被会话 4 依次覆盖，这是两半交替的设计结果。最终目录里只有一个 GXRTRACE.BIN。 |

这里的“三个单元”是三个记录位置。模拟器只有合成 jlaunch 单元：槽 1、槽 2 是在同一次开机里，各用一个新的 DAT 会话（各自重新读入）写的，不是真接了 28mm 或 MOUNT。和单元有关的 DAT 行为由主机验收的三个单元覆盖（第 4 节）。同一次开机里连续三个会话时，文件系统缓存一直保留，这比每个会话都冷启动更严格；冷启动后的读入由开机 2 单独证明。

前一次运行 `final6`（`research/emulator_m2d/local/unit28-g146/final6/`）的 12 次写入、读入和解码结果与 `final7` 相同，两次运行每个原生调用的步数逐一相同，12 条记录在卡上的 SHA256 也逐一相同；但 `final6` 的状态是 FAIL。原因是判定写错了：它要求“开机 1 挂载前后”的差异也为零，而原厂首次开机在空卡上建 DCIM 是正常的原生行为，发生在 DAT 的任何调用之前。`final7` 把这部分单独列出并逐项核对（`boot1_mount_native_only`）；DAT 调用造成的变化，按“每次同步”和“挂载后到结束”两种范围检查。

## 6. 任务 id：H01、H06、H07、H08

脚本 `emu_g146_hooks.py`，运行目录 `research/emulator_m2d/local/unit28-g146/hooks2/`。`hooks1` 是同样的运行，只保存了前 12 条命中记录。

- 起点：从 M2d 最后的 UI 检查点 `record-cold-final-r11-stop.pkl` 恢复（核对 SHA，虚拟卡复制到运行目录）。
- 按键：依次按 ADJ、OK、DISP、上、下、左、右、ADJ。每个键按下 30 万步，松开 150 万到 300 万步。
- 断点：v3.8 的四个钩子位置 H01 `0x2028709C`、H06 `0x202BE24C`、H07 `0x202871D8`、H08 `0x202BB968`（`firmware/resident_v38/local/resident/hooks.json`；这些位置的原字节与 1.51 相同）。

| 入口 | 命中 | 说明 |
|---|---:|---|
| H01 menu_open | 0 | 没跑到。UI 一直是状态 2，表 `0x203761C8`；ADJ 的事件 43、72 没有分派到构造函数。M2d 报告的结论：状态 56 的表里 event 1 才指向 `0x202BA5C8`，而模拟器没有进入状态 56 |
| H06 panel_open | 0 | 没跑到（菜单没打开） |
| H07 event | 0 | 没跑到（菜单没打开） |
| H08 apply_step | 0 | 没跑到（菜单没打开） |

所以无法在入口处比较“当时真正在跑的任务”和 `0x200D1838`。

替代检查：在同一条 Task 6 原厂 UI 路径的两个点上，每次命中都把 `0x200D1838` 和独立来源比较，共 34 次。两个点是 `0x202B0B18`（UI 取事件）和 `0x202AFE98`（键映射）。独立来源有三个：

- 内核调度器最后一次切换的目标：`0x0500C92C` 处的 r9，调度器在这里从任务表 `0x200D2174` 装入该任务的 SPU；
- 命中时的 SPU 离哪个任务调度时的 SPU 最近；
- PSW.SM 必须为 1，即在任务栈上，不在中断栈上。

结果 33 次一致：都是 Task 6，SPU 与 Task 6 调度时的 SPU 相差 60–204 B。另有 1 次是恢复检查点后的第一次命中，那时还没观察到任何调度，判为无法判定，不算不一致。没有不一致。

这只说明在 Task 6 的普通 UI 代码里，`0x200D1838` 读出的是当时在跑的任务；它不能代替钩子入口本身的比较。`research/reentry_reachability/REPORT.md:198` 的提醒仍然适用：中断期间，这个字仍指被打断的任务。DAT 的 `note_task` 只记这个字，不记 PSW。H01、H06、H07、H08 入口的任务 id 只能等上机记录。DAT 没改。

## 7. FAT32 卡：只有静态论证

本轮所有模拟器运行都用 64 MiB FAT16 虚拟卡（`tools/gxr_emulator/fat_image.py` 只造这一种）。真实的 SD/SDHC 卡多半是 FAT32，**没有 FAT32 的模拟器运行**。静态上能说的：

- 文件内容：按 `diag.c` 的说明和 FAT16 运行的结果，`0x200AAD38` 读、`0x200AB02C` 写的都是句柄当前位置所在的那个簇。DAT 拒绝簇不大于 8,704 B 的卷，所以整个文件总在一个簇里。文件不加长，不需要分配簇。
- 卷元数据：`0x200A6750`（关闭时调用的 release）静态上能到达 `0x200B0C6C`（检查 FAT 脏区间并回写）和 `0x200B76EC`（FAT32 FSInfo：核对签名后写回空闲簇数和下一空闲提示，见 `research/user_storage_r2/REPORT.md` 第 7 节）。本轮调用图见 `local/diag146-finish/cg-dat146.json`。在 FAT16 卡上，模拟器证明了 FAT 和根目录没变；在 FAT32 卡上，FSInfo 扇区会不会被重写一次（值应当不变）没有验证。相机自己每次关闭文件也走这个函数，DAT 没有为它设任何特殊状态。
- 目录项：本文件的长度和首簇都不变。FAT16 运行中，release 没有改动任何目录字节。FAT32 目录项里首簇的高 16 位（偏移 20）没有单独验证。
- 簇大小：FAT32 的 SDHC 卡常见 32 KiB 簇，满足“大于 8,704 B”。如果簇不大于 8,704 B，DAT 计 `size_fail`，本次开机不写。

## 8. 为什么只能从位置 0 整文件刷出

`variants1`（`research/emulator_m2d/local/unit28-g146/variants1/result.json`，历史运行，用旧重放的 `variants` 模式）每次重新打开文件，做不同的前置步骤，再刷出 1,024 B：

| 前置步骤 | 刷出结果 | 原厂错误 |
|---|---|---|
| 打开后直接刷出（位置 0） | 1,024 | 无 |
| seek 到 0 再刷出 | 1,024 | 无 |
| seek 到 3,584 再刷出 | −1 | 236 |
| seek 到末尾，再 seek 到 3,584，再刷出 | −1 | 236 |
| 读 512 B，seek 到 3,584，再刷出 | −1 | 236 |
| 读 512 B（旧读法），不 seek，直接刷出 | −1 | 236 |

所以 DAT 只用“新句柄、位置 0、整文件”这一种已证明可行的形状。

## 9. 官方 1.51 与 v3.8 的文件路径代码；文件和复跑

模拟器里跑的是官方 1.51 `ilaunch3`（`da1980e9…`）。上一轮（`REPORT-r4-g145.md` 第 8.1 节）逐字节比较过：v3.8 与官方的差别只有文件头校验字、resident 窗口 `0x2005276C..0x20054800` 和 7 个钩子位置；文件 API（`0x200A3000..0x200BC000`）、SD 驱动和信号量 47 包装全部相同。本轮用到的 `0x2005E360`、`0x0500D4E4`、`0x0500D4FC` 和六个文件内部函数都在相同的范围里。

本轮新建或修改的文件：

- `research/unit28_stock/emu_g146_trace.py`（改了 `Dat`、`final()`；新增 `native_mount()`、`lock_ok()`、`Writes`）；
- `research/unit28_stock/emu_g146_hooks.py`（新）；
- `research/unit28_stock/REPORT.md`（本文件）；
- `research/unit28_stock/SHA256SUMS`（重写，只覆盖本轮文件）；
- `research/unit28_stock/local/unit28-r5/`（从 Scratch 复制来的证据）和 `local/diag146-finish/`（本轮日志和调用图）；
- `research/emulator_m2d/local/unit28-g146/` 下新建的运行目录 `hooks1`、`hooks2`、`final6`、`final7`；
- `firmware/package_v38_diag146/`（整个重做）；
- `firmware/engine_diag_v38_g146/STATUS.txt`（读写描述）。

复跑（运行名必须是新的目录名）：

```sh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diag146-finish
/usr/bin/python3 -I -B research/unit28_stock/emu_g146_trace.py final final8        # 约 25 分钟，两次冷启动
/usr/bin/python3 -I -B research/unit28_stock/wait_done.py research/emulator_m2d/local/unit28-g146/final8 590
/usr/bin/python3 -I -B research/unit28_stock/emu_g146_hooks.py hooks3              # 约 6 分钟
/usr/bin/python3 -I -B research/unit28_stock/decode_trace.py research/emulator_m2d/local/unit28-g146/final7/GXRTRACE-final.bin --nonce a0a1a2a3a4a5a6a7a8a9aaabacadaeaf
```

## 10. 包

`firmware/package_v38_diag146/` 已整个替换。旧的 `SD_ROOT/GXRCE.DAT`（30,628 B，`d955ca2e…`，旧读法）和旧 `GXRTRACE.BIN`（`58bc868f…`）已删除。

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `SD_ROOT/GXRCE.DAT` | 30,776 B | `1a3ed0457540a86100bb1327b9120a05460bb9e0b6169c017e374188cc4b4abd` |
| `SD_ROOT/GXRTRACE.BIN` | 8,704 B | `db41ec46c2428b03aa94e8d5e839376aecd3a11d2887876867c38346eadd28cd` |

`GXRTRACE.BIN` 用 `decode_trace.py --new` 生成（即 `trace146.blank()`）：文件头 `GXRT146\0`，偏移 16..31 是 nonce `38bc1137dcceaa074a2ef173de9cd101`，其余全为 0。解码时加 `--nonce 38bc1137dcceaa074a2ef173de9cd101`。清单在 `firmware/package_v38_diag146/SHA256SUMS`。机身必须已经是 v3.8，`ilaunch3` 不在包里。`SD_ROOT/` 被 `.gitignore` 忽略。

## 交复审前自查

按 `research/pitfalls/CHECKLIST.md`：

| 类 | 证据位置 |
|---|---|
| 3 归属与重入 | 记录 I/O 只在 `trace_sync` 里，而且是 `done()` → `trace_menu()`、`ig_init` → `trace_init()` 的最后一步，之后直接 `finish()`；文件调用返回后不再写任何 UI 原生字段（`diag.c` 第 600–626、658–683、697–710 行）。文件调用只写文件系统自己的打开计数和句柄项，并且只在持有 47 时写。`note_task` 只读内核字、只写自己的记录。三单元的 refuse、retire、ingress-I 组都通过（`local/accept146-28mm-refuse.json`、`-28mm-retire.json`、`-ingress-I.json`） |
| 4 夹具预置和替身 | 本轮验收里每处原生状态预置都有明确用途：attach 模型写簇扇区数和缓冲地址（`accept_diag146.py:273-274`）、读入模型拷文件内容（333）、`name-*` 组改单元名（404）、part 注入（448）、`28mm-retire` 触发退役（511、517）、`ingress-I` 清请求（618）；没有手工预置 `0x2022F71C`（全文 grep 无结果）。两个内核替身从 `accept_diag38.py:119-124` 沿用，不在 `tools/native_harness/STUBS.md` 里：① `0x0500C6EC` 上下文检查固定返回 0（任务上下文），所以 `0x2005E360` 总会走到内核服务 124，主机测不到返回 −25（非任务上下文）这条路；DAT 遇到它按 `poll_error` 跳过本次。② `0x0500C574` 取任务 id 固定写 6；DAT 的 `note_task` 不调用它，而是直接读 `0x200D1838`（主机里读到 0xFFFF），所以它不影响记录里的任务 id，只影响调用它的原生代码。另外，主机验收里 47 的试取和释放、六个文件内部函数，都是验收自带的卡模型（`accept_diag146.py` 的 `install_card`），不是原厂代码；它们的原厂行为由模拟器 `final7` 覆盖（第 5 节） |
| 5 原厂时机和隐藏分支 | 读入用到的句柄字段（`e+2` 簇扇区数、`e+4` 缓冲）由 attach `0x200AB4F0` 写入，DAT 在 attach 之后才读（`diag.c:491`、`547`）；模拟器里 attach 后的句柄项是 `00000020 204cbab0…`（`probe1/result.json` 的 `entry_after_open`）。seek 后刷出报 236 这个隐藏分支见第 8 节，首次开机原厂建 DCIM 见第 5 节。临时“未就绪”只跳过本次：`notready` 组 3 次打开都是 root_state 0，不加载、不写；`boots` 顺序组里它后面的 50mm 开机照常写出会话 2（`local/unit28-r5/acc-final/summary.json`） |
| 9 打不开不等于不存在 | DAT 从不 create、rename、delete（`static-diag146.json` 的路径和桥列表）。打开返回 −1 只计 `open_fail`，不写、不锁存：`nofile` 组 3 次同步，各试一次锁、各释放一次，0 次写入，每次都重新尝试（`local/accept146-nofile.json` 的 `lock`、`writes`） |
| 12 返回值和锁结果 | 取锁只试一次、超时 0；−50 和其他非 0 分开计数；只有返回 0 才做文件操作，且只释放一次（`lock_proof146.py` 的 4 个变异全被查出，见 `static-diag146.json`；模拟器 13 次同步的 `locks` 判定，见第 5 节）。fill 返回 −1 或长度不对、flush 返回 −1、close 返回 −1 都检查并计数（`allwritefail`、`closefail`、`short`、`badheader` 组）。每次开机最多写 24 次（`TR_WRITES`）；读入只有一次 fill，没有循环 |
| 14 只测 50mm | 主机验收 50mm、28mm、MOUNT 三个单元都跑了，另有三个单元写同一文件的顺序组（`local/unit28-r5/acc-final/summary.json`）。模拟器只有合成 jlaunch，28mm、MOUNT 只是数据位置（第 5 节）。三个单元都还没上过机 |
