# M32R C 交叉编译器报告

结论：GNU GCC 13.4.0 的 `m32r-elf` C 交叉编译器已在项目目录构建成功。它把当前 `recipe_core.c` 编译成 32 位大端 M32R object，但这个 object 还没有链接到 Ricoh 固件，也没有绑定相机 ABI。

核验日期为 2026-10-12。构建和验证没有执行 M32R 代码，也没有生成相机更新包。

## GCC 版本与目标支持

本轮固定使用 GNU GCC 13.4.0。来源与 SHA-512 记录在 [`SOURCE.md`](SOURCE.md)。官方源码归档的实际 SHA-512 与 GNU 校验文件一致。

校验通过的源码给出两个直接证据。

- `gcc/config.gcc` 第 292 行把 `m32r-*-linux*` 列为不支持目标。
- 同一文件第 2294 行有独立的 `m32r-*-elf*` 配置，使用 `elfos.h` 和 `newlib-stdint.h`。

因此，GCC 13.4.0 不支持 M32R Linux，但支持本项目需要的 `m32r-elf`。本轮没有根据目标名称猜测支持情况。

## 构建环境

实际环境如下。

- 主机是 macOS 27.0.1 arm64。
- 编译器是 Apple Clang 21.0.0。
- 构建工具是 GNU Make 3.81。
- 验证器使用 Python 3.14.7。
- GCC 使用系统 zlib。
- GMP 6.3.0 来自只读路径 `/opt/homebrew/opt/gmp`。
- MPFR 4.1.0 和 MPC 1.2.1 按 GCC 13.4.0 自带清单固定版本，并构建到本目录的 `prefix/deps/`。
- 目标汇编器和链接器复用已核验的 Binutils 2.43 绝对路径。

构建没有调用 Homebrew 安装命令，也没有修改 Homebrew 环境。构建没有使用 Docker、虚拟机或后台服务。

工具目录当前占 1.9 GB。主要部分是 1.0 GB 的 GCC 解包源码、703 MB 的构建目录、99 MB 的下载归档和 83 MB 的项目内 prefix。

`cc1` 运行时依赖系统 `libiconv`、系统 zlib、系统 C++ 库、`libSystem` 和 `/opt/homebrew/opt/gmp/lib/libgmp.10.dylib`。MPFR 与 MPC 静态链接进编译器。

## 构建范围与复跑

[`run_all.sh`](run_all.sh)完成以下工作。

1. 核验 GCC、MPFR 和 MPC 三个归档的固定 SHA-512。
2. 在独立目录构建并安装 MPFR 与 MPC。
3. 配置 `--target=m32r-elf` 和 `--enable-languages=c`。
4. 只运行 `all-gcc` 和项目内 `install-gcc`。
5. 编译 tiny C 和当前 recipe core，再运行结构化验证。

GCC 配置关闭 bootstrap、multilib、NLS、共享库、线程、libatomic、libgomp、libquadmath、libsanitizer、libssp 和 libstdc++。配置使用 `--without-headers`，因此没有构建 newlib、目标 libgcc 或完整 SDK。

从项目根目录复跑：

```sh
sh research/tooling_m32r_c/run_all.sh
```

脚本已连续复跑两次。两次的 `verification.json` SHA-256 都是 `0f9c9ca493c252cd953e6158522e1275e729313e5b0effb06dee8a813797efff`。两次的 `recipe_core.o` SHA-256 都是 `ee83dab8450c7a7e8146ef43b37af6b0c3062cc93e7e8d35aa535b172529a23c`。标准错误为空。

GCC 当前构建树的 `all-gcc` 检查见 [`build-gcc-final.log`](evidence/build-gcc-final.log)。项目内安装日志见 [`install-gcc.log`](evidence/install-gcc.log)。

## 工具哈希

| 工具 | SHA-256 |
| --- | --- |
| [`m32r-elf-gcc`](prefix/gcc/bin/m32r-elf-gcc) | `4864b9476b06cd488292c9937ddb92b021605e89ccd06a859f5d4146b46393de` |
| [`cc1`](prefix/gcc/libexec/gcc/m32r-elf/13.4.0/cc1) | `ce6a619fd010651d2c7f7a503f24d3e31a72b34cc9f69aca74f0143b7e8ec318` |
| 复用的 `m32r-elf-as` | `ddf6208da3b64b2b33e0032ca8c66957f8bd3c0e68aada93eaa4e75076cd7768` |
| 复用的 `m32r-elf-ld` | `d40da13ef65ca7b9bbce56550e931b9ce21432405be2481b8a6e423993f76bf0` |

GCC 的 `-dumpmachine` 实际输出是 `m32r-elf`。GCC 的 `-print-prog-name=as` 和 `-print-prog-name=ld` 返回项目内 Binutils 的绝对路径。完整记录见 [`verification.json`](evidence/verification.json)和 [`gcc-version.txt`](evidence/gcc-version.txt)。

## Tiny C 正向验证

[`tiny-core.c`](tiny-core.c)只定义 `u8` 与 `u32`，不包含宿主头文件。编译参数包括：

```text
-std=c11 -Os -ffreestanding -fno-builtin -fno-stack-protector
-fno-common -fno-pic -m32r -Wall -Wextra -Werror
```

实际结果如下。

- object 是 `ELF 32-bit MSB relocatable, Renesas M32R`。
- ELF 机器号是 88。
- `__M32R__` 与 `__BIG_ENDIAN__` 预定义宏存在。
- `.text` 是 112 字节。
- 未定义符号数量是 0。
- 两个函数的 GCC 静态栈框架都是 0 字节。

输出在 [`tiny-core.o`](../../artifacts/recipe-core/m32r/tiny-core.o)、[`tiny-core.disasm.txt`](../../artifacts/recipe-core/m32r/tiny-core.disasm.txt)和 [`tiny-core.su`](../../artifacts/recipe-core/m32r/tiny-core.su)。

## 当前 recipe core 编译结果

验证器只读以下输入，并记录各文件 SHA-256。

- `firmware/recipe_core/recipe_core.c`
- `firmware/recipe_core/recipe_core.h`
- `firmware/recipe_core/recipe_storage.h`

本轮编译的 `recipe_core.c` SHA-256 是 `a728036dbbcc71f8d6367607b764a267ed23e979b3b73b38477f9ee448c9955f`。编译使用与 tiny C 相同的 freestanding 选项，并增加只读头文件目录。

实际 object 结果如下。

| 项目 | 实际值 |
| --- | --- |
| 文件 | [`recipe_core.o`](../../artifacts/recipe-core/m32r/recipe_core.o) |
| 类型 | 32 位大端 M32R relocatable ELF |
| SHA-256 | `ee83dab8450c7a7e8146ef43b37af6b0c3062cc93e7e8d35aa535b172529a23c` |
| `.text` | 1,220 字节 |
| `.rodata` | 8 字节 |
| 未定义符号 | 0 |
| 重定位 | 2 个 `R_M32R_24_RELA`，都指向 `.rodata` |

三个公开函数都出现在符号表中。反汇编见 [`recipe_core.disasm.txt`](../../artifacts/recipe-core/m32r/recipe_core.disasm.txt)。符号和节表见 [`recipe_core.symbols.txt`](../../artifacts/recipe-core/m32r/recipe_core.symbols.txt)与 [`recipe_core.headers.txt`](../../artifacts/recipe-core/m32r/recipe_core.headers.txt)。

GCC 报告的每函数静态栈框架如下。

| 函数 | 字节 |
| --- | ---: |
| `copy_recipe` | 0 |
| `crc32_iso_hdlc.constprop` | 0 |
| `decode_record` | 64 |
| `recipe_read` | 136 |
| `recipe_save` | 144 |
| `recipe_delete` | 84 |

原始输出见 [`recipe_core.su`](../../artifacts/recipe-core/m32r/recipe_core.su)。这些数字只包含各函数的静态栈框架，不包含回调、嵌套调用和中断上下文的总栈需求。

## 仍需绑定的边界

- [`recipe_core.text.bin`](../../artifacts/recipe-core/m32r/recipe_core.text.bin)只包含 object 的 `.text`。它没有包含 `.rodata`，也没有应用两个重定位，不能作为已链接 payload。
- GCC 生成代码遵循 GCC 13.4.0 的 M32R ABI。项目还没有证明该 ABI 与 Ricoh 固件的参数传递、保存寄存器、栈对齐和中断约定一致。
- `recipe_core.o` 没有未定义符号，只说明当前 C 单元没有直接外部符号依赖。三个存储操作仍通过函数指针回调进入相机适配层。
- 当前 object 没有固件运行地址、链接脚本或入口跳板。它没有集成进 `ilaunch3` 或 `jlaunch3`。
- 本轮没有执行 object，没有修改固件，也没有生成 SD 卡更新包。

主代理可以独立运行 [`verify_compiler.py`](verify_compiler.py)。验证器会重新编译两个 C 单元，并检查目标名、预定义宏、ELF 类别、端序、机器号、节大小、未定义符号、栈用量和产物哈希。
