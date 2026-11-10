还差几项才能公开复现
完成计数：5/5

两份正在使用的文件都可以从官方 1.51 包加公开补丁逐字节重建。本机已经用本地 zip 跑通，没有联网下载。颜色核对和 g180 回归还不能交给一台新机器：入口脚本、参考解释器和照片登记都不在公开提交里，其中照片登记不能公开。

公开仓库是 https://github.com/aa2246740/projectricoh ，当前 `origin/main` 为 `fcb0cf2ad0b592b35bc85f08330186252f273806`。这次新增的工具和补丁都还没有提交。`.gitignore` 只加了这一行：`/research/public_rebuild_r1/cache/`。缓存里是官方包和解出来的 29 个成员，不能进仓库。

## 重建结果

官方包长度 11,277,528，SHA-256 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。成员名单用 `scripts/build_drill.py` 里的 `OFFICIAL`，29 个名字和 SHA-256。`fetch_official.py --from artifacts/downloads/gxr-151.zip` 第一次写入缓存，第二次复用缓存，两次都是 `members_ok: 29`，`downloaded: false`。

补丁格式是 `gxr-public-patch/1`。每个改动记录文件偏移、长度、被盖住的官方字节的 SHA-256，以及两种操作之一：`literal` 带上我们的新字节，或 `copy` 从官方映像的另一个偏移复制。校验不把结果字节写进补丁。算法名是 `gxr151-weighted-residue`：载荷从偏移 512 开始，按 6 个余数分别求和，再用相位 0 到 5 的权重 `(余数 + 相位) % 6 + 2` 合成一个 32 位和，写回偏移 364。相位从官方文件上唯一对上的那一档读取，这两份都是相位 0。脚本在全部改动之后重算这 4 个字节。

两份补丁的文件名故意不用固件名。根 `.gitignore` 已有 `ilaunch*` 和 `qlaunch*`，用那些名字的话补丁会被忽略。

| 补丁 | 目标 | 结果 SHA-256 | 我们的字节 | 从官方映像引用 | 校验字段 |
| --- | --- | --- | --- | --- | --- |
| `patches/body-r5.json` | ilaunch3，3,993,340 B | `37fe29f0813b9bbf9fd6319498d8921748fd34fb4f79f1f0c0572bf2dbebc729` | 7,480 | 323，22 条 copy | 重写 4 字节，相对官方有 3 字节不同 |
| `patches/xpan-28mm.json` | qlaunch3，2,505,308 B | `aed12aee9ea26f5a6839cef6a6380497a1b21342bf551f93878671e877d5d27a` | 8 | 0 | 重写 4 字节，相对官方有 2 字节不同 |

`rebuild.py --audit` 的输出 `embedded_runs` 都是 0。重建文件与 `firmware/package_v310b_g178_xpan28_r4/local/xpan-direct-r4-28mm-flash/SD_ROOT/` 里的在用文件 `cmp` 相同。工具只使用 Python 标准库，本机是 `/usr/bin/python3` 3.9.6。没有在 Linux 上跑。

qlaunch3 相对官方，除校验外有 4 处各 2 字节。三处新字节是 `0630`（1584），一处是 `0278`（632）。加上校验里实际变化的 2 字节，一共 10 字节，和先前记录的差异量一致。

ilaunch3 除校验外有 7,803 字节不同，分布在 317 段里。其中 323 字节在官方映像的其他偏移已经存在，长度 12 到 27 字节，已改成 copy，不写入补丁。其余 7,480 字节是补丁里的字面量。字面量内部还能对上官方映像的最长连续片段是 11 字节，短于这次采用的 12 字节门槛，所以留在字面量里。没有整段函数被原样搬进补丁。文件其余约 3.98 MB 不在补丁里，重建时直接来自官方包。

22 条 copy 都落在文件偏移 31087 到 39104。最长的一条是偏移 31087、长度 27，来源偏移 3896291。完整清单在 `patches/body-r5.json` 的 `op: copy` 项里，只有偏移和长度。

## 新机器上跑重活还缺什么

下面说的「公开提交」指 `fcb0cf2`。工作区里还有大量未提交文件；没进提交的，一台只克隆 GitHub 的机器看不到。

已在公开提交里：

- `scripts/build_drill.py` 的 29 个成员 SHA-256，以及同一套加权校验。
- `tools/loadgate.py`。
- `research/tooling_m32r/SOURCE.md` 和 `run_all.sh`。Binutils 2.43 的地址和 SHA-256 在 SOURCE.md：`https://ftp.gnu.org/gnu/binutils/binutils-2.43.tar.xz`，`b53606f443ac8f01d1d5fc9c39497f2af322d99e14cea5c0b4b124d630379365`。
- `research/tooling_m32r_asm/run_all.sh`。它用上面解开的源码构建 `m32r-elf-as`、`m32r-elf-ld` 和 `m32r-elf-objcopy`。
- `research/tooling_m32r_c/` 的 `SOURCE.md`、`run_all.sh`、`REPORT.md`、`tiny-core.c`、`verify_compiler.py`。GCC 13.4.0、MPFR 4.1.0、MPC 1.2.1 的地址和 SHA-512 在 SOURCE.md。
- `firmware/recipe_core/` 有 9 个已跟踪文件。编译器自检会编译其中的 `recipe_core.c` 和 `tiny-core.c`。

m32r 工具在新机器上这样装。三个前缀、源码树和下载目录都已被忽略，只提交构建脚本。

1. 在 `research/tooling_m32r` 跑 `run_all.sh` 直到它把 `prefix/bin/m32r-elf-objdump` 复制出来。脚本最后会调用被忽略的 `analyze_segments.py`，新克隆上这一步会失败；失败点若在复制 objdump 之后，二进制已经可以用，不要为了这一步去补反汇编。macOS 使用脚本里的 `--with-system-zlib`。确认 `m32r-elf-objdump --version` 打印 GNU Binutils 2.43。
2. 源码解开之后跑 `research/tooling_m32r_asm/run_all.sh`，直到三个二进制复制进 `prefix/bin/`。脚本最后调用的 `verify_toolchain.py` 不在公开提交里，同样不要为了它去跑固件。
3. 把 GCC、MPFR、MPC 三个归档放到 `research/tooling_m32r_c/downloads/` 并核对 SOURCE.md 的 SHA-512。脚本自己不下载。本机 GMP 用 `/opt/homebrew/opt/gmp`，脚本要求这个路径。Linux 改为系统 GMP，并把 `run_all.sh` 里的 `--with-gmp` 指到那份安装。然后跑 `research/tooling_m32r_c/run_all.sh`。它需要上一步的汇编器和链接器。

可从官方包加补丁重建：

- r5 机身 ilaunch3，补丁 `research/public_rebuild_r1/patches/body-r5.json`。
- 28mm XPan qlaunch3，补丁 `research/public_rebuild_r1/patches/xpan-28mm.json`。

这两份补丁此刻只在本工作区。公开提交里还没有。

只在本机、不能公开：

- `research/fit_v4_r2/local/registry/all_full_registry.json` 的 69 条记录，以及每条 `record_file` 指向的 552 字节记录。`build_g181_r1/local/colours.py` 用它们做三支镜头各 23 条的期望值。这是从照片拟合出来的逐条数据，不能进仓库。要让颜色核对在新机器上跑，需要另做一组不来自这些照片的输入，只公开期望摘要。现有这 69 条不能改成可公开材料。
- `research/tooling_m32r/disasm/` 和参考解释器写在 `tools/native_harness_c/local/decode/` 的解码文本。解释器运行时调用本机 objdump 生成，结果留在本地。不要把这些文本提交。
- 官方包、29 个成员、以及 `rebuild.py` 写出的映像。它们在 `research/public_rebuild_r1/cache/` 和 `local/rebuilt/`，两处都已被忽略。

本机有、公开提交里还没有的我们自己的代码，审查后可以提交，但现在一台新克隆用不了：

- `tools/public/` 整目录被根 `.gitignore` 的 `/tools/` 挡住。要公开这套重建，得先给这个目录加例外。这次按约定只改了缓存那一行，没有改这条。
- `research/build_g181_r1/`、`research/build_g178_r1/`、`research/review_g180_r1/` 都不在 `fcb0cf2` 里。颜色入口 `colours.py`、g180 的 `review.py` 和各阶段脚本又在各自的 `local/` 下，`local/` 被忽略。目录根上的 `REPRODUCE.md`、`REVIEW.md` 是说明文字，可以以后提交；带固件地址的本地脚本不能原样提交。
- 参考解释器 `tools/native_harness_c/python_backend.py` 被 `/tools/` 忽略。它在导入时加载 `research/emulator_feasibility_r1/prototype/boot_probe.py`，而整个 `prototype/` 被忽略。颜色脚本在设置后端之前就导入它，实际走的是纯 Python 类；解码仍要调用 objdump。公开这条路径之前，只审这一个 CPU 模型文件，不要把整个 prototype 目录放开。
- `research/room_g175_r1/harness/um_session.py` 和 `um_common.py` 未跟踪。g178 的 `session.py` 会加载它们，再加载 `research/body_r5_r3/local/integration.py`。
- `research/body_r5_r3/local/common.py` 的 `setup()` 要求本机工作盘的 APFS 卷 UUID 与机主登记的值一致，并拒绝写出该任务目录之外的路径。新机器会在这里停住。卷检查留在机主这台电脑的入口里，给云端的入口不要调用它。
- g180 的 `review.py rebuild` 会编译引擎，入口是未跟踪的 `research/body_r5_r2/local/build.py`，产物和现成的 `GXRCE.DAT`、库、resident ELF 都在各任务的 `local/`。`deep_tables.c` 继续保持忽略。我们自己的引擎源码可以另审之后提交，这次没有做那次拆分。

所以现在能交给另一台机器的，只有「下载官方包、打这两份补丁、对 SHA」。颜色核对和 g180 回归还差上面这些文件和一道不依赖照片的期望值。

## 给云端 agent 的作业说明

把下面这段原样转过去。作业只做重建，不要做颜色核对，也不要做 g180 回归。

```text
仓库：https://github.com/aa2246740/projectricoh
公开提交：fcb0cf2ad0b592b35bc85f08330186252f273806
这次的工具和补丁还没进这个提交。使用机主给出的工作副本，里面要有 tools/public/ 和 research/public_rebuild_r1/patches/。不要 commit，不要 push。

用系统的 python3，命令是 python3 -I -B。不要装依赖。

取官方包。有缓存就不要再下。
python3 -I -B tools/public/fetch_official.py --download

期望 JSON 里：status 为 ok，downloaded 第一次为 true、已有缓存时为 false，zip_bytes 为 11277528，zip_sha256 为 3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898，members_ok 为 29。

若这台机器不能上网，改用已经核过的本地包：
python3 -I -B tools/public/fetch_official.py --from <本地 gxr-151.zip>
长度和 SHA-256 必须与上面相同，否则停。

重建并审查字面量：
python3 -I -B tools/public/rebuild.py --patch research/public_rebuild_r1/patches/body-r5.json --audit --out research/public_rebuild_r1/local/rebuilt/body-r5
python3 -I -B tools/public/rebuild.py --patch research/public_rebuild_r1/patches/xpan-28mm.json --audit --out research/public_rebuild_r1/local/rebuilt/xpan-28mm

期望：
body-r5 的 result_sha256 为 37fe29f0813b9bbf9fd6319498d8921748fd34fb4f79f1f0c0572bf2dbebc729，result_size 为 3993340，literal_bytes 为 7480，copy_bytes 为 323，embedded_runs 为 0。
xpan-28mm 的 result_sha256 为 aed12aee9ea26f5a6839cef6a6380497a1b21342bf551f93878671e877d5d27a，result_size 为 2505308，literal_bytes 为 8，copy_bytes 为 0，embedded_runs 为 0。

回报这三条 JSON（fetch 一条，rebuild 两条）。不要附上重建出的文件，不要附上官方包，不要粘贴补丁里的 new_hex。embedded_runs 不是 0，或 SHA 对不上，就停并原文贴出 JSON。
```
