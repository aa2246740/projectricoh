# 主线引擎的逐字节重建

`firmware/mainline/` 里的公开源码，加上本机的几份私有输入，可以逐字节重建日常引擎 `GXRCE.DAT`。当前日常版是代数 256，`59f4e5343baaa2cb97db223e4118375394e7aeaf2a79a79e0427b9f9f8df2251`，91,292 B，profile `merged-r1-fold-a-hf10-oz-256`。

只有公开仓库还不够。下面列出的私有输入不在 Git 里，外部开发者需要自己准备同等的东西。本页不是刷机说明，修改后的固件可能让相机无法启动。

## 本机输入

| 输入 | 用途 | 位置 |
| --- | --- | --- |
| 官方 GXR 1.51 ZIP | `prepare_local.py` 只读其中的 MAIN 映像 `ilaunch3`，先核对 SHA-256 `da1980e9…`，再生成 `l2n_orig_private.h` | 默认 `<私有根>/artifacts/downloads/gxr-151.zip`，可用 `--official-zip` 指定 |
| 私有根 `GXR_PRIVATE_ROOT` | 项目的私有 checkout。默认取本仓库所在 Git 的主 checkout（`git rev-parse --git-common-dir` 的上一级）；干净导出没有 `.git`，必须指定 | 环境变量或 `--private-root` |
| M32R 工具链 | `m32r-elf-gcc`、`m32r-elf-ld`、`m32r-elf-objdump` | 私有根下 `research/tooling_m32r_c/prefix`、`research/tooling_m32r_asm/prefix`、`research/tooling_m32r/prefix` |
| ELF 读取器和服务编译参数 | `build.py` 运行时加载 | 私有根下 `firmware/stage2l_switch/tools/build.py`、`firmware/resident_v37/resident/build.py` |
| profile 覆盖层 | 5 个测试和打包文件，以及从该 profile 的 `eng_core.c` 抽出的私有常数 | 私有根下 `research/boot_copyright_g188_r2/local/engine`（`--profile g188-r2`） |
| DAT 头模板 | g178 DAT 的前 256 B | 私有根下 `research/build_g178_r1/local/model/GXRCE.DAT` |
| 机器负载闸门 | 编译前检查空闲核和内存 | 私有根下 `tools/loadgate.py`（公开） |
| 期望哈希 | `--verify` 读取 | 私有根下 `docs/DAILY.md` |

`build.py` 和 `fold_main.py` 可以在构建前核对工作卷：设环境变量 `GXR_WORKSPACE_GUARD=<挂载点>=<卷 UUID>`，或在私有根写 `local/workspace_guard.json`，内容是 `{"mount": "<挂载点>", "volume_uuid": "<卷 UUID>"}`。卷不对、不是 APFS 或不可写就拒绝构建。两样都没设时不检查，输出里 `workspace_guard` 是 `unconfigured`。这项检查不影响产物。

## 步骤

```sh
cd firmware/mainline
export GXR_PRIVATE_ROOT=<私有 checkout>
/usr/bin/python3 -I -B prepare_local.py --profile g188-r2 --official-zip <官方 ZIP>
/usr/bin/python3 -I -B build.py --profile merged-r1-fold-a-hf10-oz-256 --verify
```

成功时最后一段 JSON 是 `"verified": true`，`dat_sha256` 等于上面的哈希。输出在 `local/build/<profile>/`，整个 `local/` 都不进 Git。用 `--profile g188-r2` 准备的覆盖层，当前源码能逐字节得到当年记录 DAT 的 profile 有：`g188-r2`（188）、`g188-r3` 到 `xpan-d123-r2-nodiag`（214–221）、`merged-r1d-fold-a` 到 `merged-r1-fold-a-hf10`（240–250），以及 `merged-r1-fold-a-hf10-oz`（253）、`merged-r1-fold-a-hf10-oz-row`（254）、`merged-r1-fold-a-hf10-oz-hfu`（255）、`merged-r1-fold-a-hf10-oz-256`（256）。`daily`（185）、`feat-hf*`（223–234）、`merged-r1d` 和 `merged-r1`（237、238）在当前源码上得不到当年的 DAT。要重建它们需要当时的源码，例如本地标签 `daily-20261112-g185`；公开分支不带这些标签。`--verify-against <文件>` 可以和任意已有 DAT 比较。

## L2N 表里的 `L2N_ORIG_<VA>_<N>`

`l2n_fold_tables.inc.c`、`l2n_zoom_tables.inc.c`、`l2n_r2v2_tables.inc.c` 记录要在机身 MAIN 代码里改写的位置。每行的旧字节是原厂映像里的原字节，在公开源码里只写成名字 `L2N_ORIG_<VA>_<N>`，意思是官方 MAIN 映像在装载地址 VA 处的 N 个字节。新字节里如果有 8 B 以上的一段与原厂映像相同（保留或搬移的原指令），也写成这种名字。其余字面量是项目自己汇编的新字节。

`prepare_local.py` 从官方 ZIP 读出这些字节，写进 `local/engine/candidate/containers/product/l2n_orig_private.h`，构建时由覆盖层复制到源码旁边。若 `engine/` 下任何受跟踪的文本文件又直接写出一段 8 B 以上、原厂文件里也有的字节，脚本会报出文件和行号并停止。`0xNN`、带 `u`/`U`/`L` 后缀的写法、16 和 32 位字（两种字节序）、`\xNN`、汇编 `.byte`/`.short`/`.word`、连续十六进制串、Python 的 bytes 和 `bytes.fromhex` 都算，中间隔注释或换行也算一段。用 ZIP 时比对全部 29 个原厂文件，只给 `--official-main` 时只比对 MAIN 映像。新增或重新生成 L2N 表时，旧字节一律写成 `L2N_ORIG_` 名字。
