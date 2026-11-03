# Stage 1c R1 审查证据

主报告为上一级 `STAGE1C_REVIEW_R1.md`。这里没有升级包或 SD 根目录材料。

- `hashes-before.json`、`hashes-after.json` 和 `hash-comparison.log` 封存原始 403 个文件，前后无变化。
- `independent_audit.py` 独立检查真实候选、官方、恢复树、ELF、payload、hooks、checksum、原厂机器码和 30 个 boot/update 窗口；不导入项目打包器。结果为 `independent-audit.json`，摘要为同名 log。JSON 的 `original_disassembly_reference_candidates` 是线性反汇编数据产生的待判读项目，不是已建立的执行边。
- `native-windows.txt` 每条证据有原厂文件、行号、VMA、file offset 和机器码；审计脚本将这些机器码与官方文件核对。
- `candidate-payload.disasm.txt`、`stage1b-payload.disasm.txt` 来自指定 GNU M32R objdump，对应两版实际 ELF。
- `adversarial_modes.c` 基于 builder 的 host stub，增加 139 个新模式 GUI/parser 与 bank 竞争用例。两份同名前缀 log 是普通和 ASan/UBSan 结果。
- 其余 log 记录本轮 codec、host、sanitizer、ABI、最终 DAT、M32R rebuild 和 packaged-output 检查。`rebuild-manifest.json` 是本轮副本重建结果，不能据其中 `LINKED_STATIC_ONLY` 推导相机验收。

运行目录为已有隔离副本 `/tmp/gxr_stage1c_review/worktree`。原输入工作树为 `/Users/wu/.t3/worktrees/projectricoh/t3-cecf5e85`，主项目参考为 `/Users/wu/.t3/projects/projectricoh`。所有 Python 使用 `python3 -I`。任何重新执行前，先用 `rg -n '/Volumes'` 检查对应脚本、测试和项目内导入/子进程依赖；发现该字符串即只读审查，不执行。不要运行全量入口或 tools/image-audit suite，它们会调用或导入命中项，详见主报告。

本轮运行的安全入口为：

```sh
python3 -I firmware/recipe_v1/verify.py
python3 -I firmware/recipe_fw/tests/test_abi.py firmware/recipe_fw/build
python3 -I research/stage1c_brand_pack/verify_libraries.py
python3 -I firmware/recipe_fw/tools/build.py --out firmware/recipe_fw/review-rebuild
python3 -I research/stage1c_brand_pack/verify_outputs.py
python3 -I /tmp/gxr_stage1c_review/independent_audit.py
```

host 与 sanitizer 直接用 clang 编译 `tests/test_host.c`、`ui.c`、`platform.c` 及 `recipe_format.c/recipe_store.c/recipe_apply.c`，定义 `RECIPE_FW_HOST`。运行参数是副本 `firmware/recipe_fw/build/RECIPE20.DAT` 与 `validation-RECIPE20.DAT`。主机 test 中的 store 写入只针对内存 stub；M32R link 未含 store。

新增 139 例的编译方式如下，先检查列出的 C/header 输入，再运行。`adversarial_modes.c` 的 include 相对 `/tmp/gxr_stage1c_review`，复跑时保留该目录结构，或通过此处 `-I` 找到副本：

```sh
clang -std=c11 -O1 -g -Wall -Wextra -Werror -DRECIPE_FW_HOST \
  -I /tmp/gxr_stage1c_review \
  -I firmware/recipe_fw \
  /tmp/gxr_stage1c_review/adversarial_modes.c \
  firmware/recipe_fw/ui.c firmware/recipe_fw/platform.c \
  firmware/recipe_v1/recipe_format.c firmware/recipe_v1/recipe_store.c \
  firmware/recipe_v1/recipe_apply.c \
  -o /tmp/gxr_stage1c_review/adversarial-modes-host
/tmp/gxr_stage1c_review/adversarial-modes-host
```

sanitizer 编译另加 `-fsanitize=address,undefined -fno-omit-frame-pointer`。上述命令全部只能在隔离副本运行。不要用它们访问、准备或更新任何已挂载介质。
