修改后再合并

本轮复现一项 P2：Studio 会把外层改成 156、内嵌引擎仍为 g155c 的文件认成有效 g156；该文件自己的 M32R 引擎却拒绝运行。156/155 的 bank 映射、四个正式输入的往返和正常用户条目封装都通过，但不足以排除这种错配。

审查对象为 [GXR Studio PR #29](https://github.com/aa2246740/gxr-studio/pull/29)，HEAD `1c690bbe271d6ffaf4e6cf2c575f1dcc83ac1bb5`，base `b8ab429514ea7e6793af589760fdec4e05eb128b`。从指定 worktree 读取差异，未修改它。父仓库起始 HEAD 为 `7ba9cb4a2d921cd5ad88f037c1e9693323bad05f`。

审查时间为 2026-11-03 20:09 UTC 起，限时 1.5 小时。所有审查文件、缓存和编译输出均在本目录。计算任务最多两个并行，子命令串行执行，数值库线程限制为 1。未访问卡或相机，GitHub 只读，未评论、批准或合并 PR。

## Findings

### P2-01：正确的 bank 标签不能证明引擎匹配

位置为 `src/gxr_studio/camdata/datcodec.py:109` 新增的 Profile，以及同文件 `230`、`323`、`664` 附近的解析和封装。`bank_generation` 正确地只把 156 映射为 155，但引擎仍只检查长度、入口和重定位，没有验证它属于哪个代数或链接布局。

最小反例从真实 g155c release 或 test 开始，只把外层 offset 28 的代数改为 156，再重算外层 CRC。实际只改变 5 个字节：头 CRC 的 20..23 和代数的 31。bank、引擎和其余数据都保留原值。

| 输入 | Studio parse / pack | 生产导入校验 inspect_dat | g156 主机 C gate，三个单元 | 文件内原 M32R eng_data_accept，三个单元 |
| --- | --- | --- | --- | --- |
| 原 g155c release / test | 通过 | 通过，代数 155 | 拒绝，106 | 通过，0 |
| 同一文件仅重封为外层 156 | 通过，往返逐字节相同 | 通过，代数 156 | 通过，0 | 拒绝，1 |

两份错配文件的 SHA-256 分别为 `82da08f66d18cd5e79f0e015c6918c8af09d3653828246aa35e346f80dfd5e3e` 和 `0d92cbedc7e621e63a1269958de960c945d3a3de921f291088551bcf51f3341f`。M32R 执行前逐字节确认了 ELF 的 `.engine` 与 DAT 内代码相同；原文件作为同引擎、同单元对照。这里没有用实现者的回执代替执行。

另把真正的 g156 引擎、入口、BSS 大小和重定位装入 g155c 数据，也被 Studio、inspect_dat 和 C gate 接收。release 输出长 86712 B，而换入引擎的原链接 BSS 起点为 88684；test 对应为 89620 与 90532。g155c bank 本来就与 g156 bank 相同，不能靠 bank 标签发现这种布局错配。本轮没有启动这两份混合包，不能据此声称发生了崩溃或越界。

生产的三个导入入口都经过 `api/camdata_routes.py:114` 的 `_install()`，其中直接调用 `intake.inspect_dat()`，后者已实际接收上述四个反例。正常 CRC 和重新封装相等都挡不住它们。C gate 通过也不能代替内嵌引擎的准入检查。

合并前应为 g156 绑定已登记的引擎与外层代数、入口、BSS、重定位及链接数据末端，并在 parse 和 pack 共用检查。仅登记引擎 SHA 仍挡不住第二组布局错配；锁整个 DAT SHA 又会拒绝合法的用户条目修改。需要增加“仅改外层头”和“换入真实 g156 引擎但保留旧布局”的拒绝测试，同时保留四个真实 DAT 和合法修改的通过测试。

证据在 [dat-audit.json](evidence/dat-audit.json)、[intake-audit.json](evidence/intake-audit.json)。复跑脚本为 [audit_dat.py](audit_dat.py) 和 [audit_intake.py](audit_intake.py)。

### P3-01：部分真实文件测试还有额外跳过条件

`tests/test_g156.py:39` 的 package fixture 确实现场读四个 DAT，并核对固定 SHA。文件不存在才在这里 skip；文件存在但 SHA 不同会报错，本轮已用损坏副本验证。

但“只在 DAT 缺失时跳过”不适用于整个测试文件。第 88 行的基本往返测试还依赖 `parent_format`：四个 DAT 都存在、但父仓库 `research/v39_g153/dat_format.py` 缺失时，四例全部 skip，本轮已复现。C gate 测试还会因父源码、clang 缺失或平台不是 macOS 而 skip。后者在 README 已说明。

建议把基础 parse / pack 往返与父解析器对照拆开，让已有 DAT 的基础检查照常运行。PR 的新测试没有覆盖 P2-01 的引擎错配；只改坏 bank 代数、或用正确 g156 引擎测试外层 155 / 157，都不是该反例。

## 156/155 规则与其他代数

就 bank 头而言，规则是精确的：三个 bank 都必须为 155，没有接受任意旧 bank 的分支。对四个输入分别在每个单元写入 0、127、154、156、157，并重算 bank 头及外层 CRC，共 60 例全部因 bank 代数不合格被拒绝。

其余 11 个已登记代数 127、129、131、135、137、138、150、152、153、154、155 的 `bank_generation` 都等于外层。逐代读取本机真实 DAT，并逐单元换成错误 bank 代数，33 例全部拒绝。未发现放宽其他代数。输入摘要和逐例结果在 `dat-audit.json`。

父审查 `research/review_g156_r1/REVIEW.md` 的 P2-01 所指出的两个拒绝点，本 PR 都已修正：Profile 登记了 156，parse 和 pack 共用了 156/155 映射。当前新增问题是这组标签没有绑定引擎。

## 四个真实 DAT 与写出校验

| 包 | 外层 / 三个 bank | 字节数 | parse→pack 逐字节相同 | 对应代数的 C gate，三个单元 |
| --- | --- | ---: | --- | --- |
| g156 | 156 / 155、155、155 | 88684 | 是 | 全部通过 |
| g156_test | 156 / 155、155、155 | 90532 | 是 | 全部通过 |
| g155c | 155 / 155、155、155 | 86712 | 是 | 全部通过 |
| g155c_test | 155 / 155、155、155 | 89620 | 是 | 全部通过 |

四个输入各做了三种 `replace_users()` 后封装：清空用户条目、一条非零微调、30 条用户条目，最后一种与每单元 10 个 Looks 合计达到 40 的上限。12 个输出重新 parse 成功，对应 C gate 的 36 个单元检查全部通过。

逐字节比较确认，正常用户修改只改变 GXUI 区及外层两项 CRC；三个完整 bank、引擎、重定位、描述符、行池、GXFX、R3 点表和 pin 均保持原字节。所有原厂 04 的 CRC、所有内置记录及所有 Looks 的完整 552 B 也与父解析器一致。GXUI 自身 CRC 重算正确，与三个 bank 的 CRC 绑定仍有效。C gate 实际调用原 gate、semantic 和 UI-extension parser，验证了这些输出的相机格式检查。

原样调用了父仓库 `research/g156/r2_static.py:main()`，只重定向 HERE、TMP 和允许写入目录，6 个 g156 单元检查通过，原 C 的三处代数常量差异核对也通过。另编译原 g155c C parser 作对照。随后调用原 `research/g156/r2_generation_harness.py:main()` 的 Python 后端，当前真实 g156 引擎对外层 156 接受、对 155 / 157 拒绝，18 例通过。父脚本和产品源码未修改。

生产 DAT 落盘路径也已逐一检查：import-card、import-file、import-upload 共用 `_install()`，最后由 `store.import_from_dat()` 把输入 raw 原样保存为模板；`import_from_dat_file()` 也走同一路径。当前生产源码没有调用 `replace_users()` 导出编辑后 DAT 的接口。`pack()` 是底层封装入口，已单独实跑上述修改及 C gate。

模板实际落盘和 API 导入成功的验收仍未闭合。本轮只允许在父 Git 仓库内的新目录写入，而产品隐私守卫禁止把应用数据放进任何 Git 仓库；因此相关测试被 `private_path_in_repository` 拒绝。没有绕过或修改守卫。完整覆盖这条路径需要仓库外的临时应用数据目录。不能把底层封装通过写成所有生产写入路径都已通过。

## 新测试、提交数据与本机 CI

新增测试实际执行结果为 59 通过、10 失败，未跳过。失败为 2 个模板保存用例及 8 个 file / upload 用例，原因均为上述目录边界；单独运行不需要应用落盘的部分为 57 通过。四个正式 DAT 的 SHA 校验、往返、bank 拒绝和用户修改都真实执行了。

PR 只有 9 个 UTF-8 文本文件变化。逐项查看差异，并运行 `scripts/private_bytes.py --tracked --dist`，316 个仓库及 sdist / wheel 文件全部通过。新测试提交的是路径、摘要和测试代码，没有提交 DAT、深层行或其他 Ricoh 派生载荷。跳过条件测试用的副本和失败日志位于本目录忽略的 tmp / evidence 中。

GitHub 的 [CI run 41709243741](https://github.com/aa2246740/gxr-studio/actions/runs/41709243741) 注释明确写明：

> The job was not started because recent account payments have failed or your spending limit needs to be increased.

本机为 macOS 27.0.1 arm64，Studio Python 3.14.7。执行了 `make -j1 check`，并在环境阻断后分别补跑其余命令，结果如下。

| 检查 | 结果 |
| --- | --- |
| frozen 依赖核对 | `uv sync --frozen --dry-run --offline` 审核 55 包，无需改动；未重建干净环境。 |
| ruff lint / format | 通过，187 个格式检查文件。 |
| mypy 与 mypy --platform win32 | 均通过，各 113 个源文件。 |
| 秘密扫描、Bandit、dead flags | 通过。 |
| 私有字节、分发包、AGENTS、大文件、OpenAPI | 通过。 |
| import-linter、deptry、vulture、pylint duplicate-code | 通过。 |
| 前端 TypeScript 与重建产物比较 | 通过，1 个产物逐字节相同。为保持 worktree 只读，在本目录复制前端并保留 pnpm 内部链接；13 个非依赖源文件已核对 SHA 相同。使用缓存 pnpm 10.33.2；本机 Node 26.7.0，不是 CI 的 Node 22。 |
| GPU 一致性 | 14 通过。仅替换测试浏览器启动器，使用固定 Playwright 1.61.1 / Chromium Headless Shell 1228；页面、测试输入和像素断言未改。使用单进程及进程内 GPU 参数。 |
| make dast | 25 通过。 |
| 完整 pytest 与覆盖率 | 80 通过、10 失败后按 CI 的 maxfail=10 停止；失败来自临时目录处于父 Git 仓库，85% 覆盖率门槛未完成。GPU 文件由上面的固定运行时单独验。 |

首次 make check 在隔离缓存缺少 hatchling 时停止。随后只读复制本机已有构建依赖缓存到本目录，分发包扫描已补过。前端最初也受隔离 Corepack 缓存影响；改用已有固定版本和保留链接的前端副本后补过。这些原失败日志都保留，没有据此算 PR 源码缺陷。

Windows 完整 pytest、真实 Windows 句柄与子进程、WARP / D3D12 和平台探针均未运行；win32 mypy 只能证明类型检查。本轮也没有 Ubuntu 运行时、Node 22、干净依赖安装、真实 Studio 浏览器导入、实卡或相机启动与持久化证据。此次不能把本机结果写成 CI 全绿或相机放行。

执行明细见 [checks.jsonl](evidence/checks.jsonl)、[environment.json](evidence/environment.json) 及各日志。固定 GPU 启动器为 [pinned_gpu.mjs](pinned_gpu.mjs)，测试适配器为 [pinned_gpu_plugin.py](pinned_gpu_plugin.py)。

## SHA256SUMS

四个正式 DAT 的摘要如下，路径相对父仓库。

```text
f42b81a854d86b66ee7f65ac0123153c7e54e59d6e3d2079834490771d0ce1e0  firmware/package_v310_g156/GXRCE.DAT
0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7  firmware/package_v310_g156_test/GXRCE.DAT
69fa85104fcb449e613950bb58c802b9b64464769ae524fe3f7303e06093c2ad  firmware/package_v310_g155c/GXRCE.DAT
c3017d3663e9501b43c921e3b46333b74d751eaa170781c4e1a00d90118f0335  firmware/package_v310_g155c_test/GXRCE.DAT
```

起始冻结的 5315 个输入文件末次核对均未变化，Studio HEAD 和工作树也保持原状。冻结清单在 `evidence/inputs-before.json`，复核在 `evidence/integrity.json`。本报告、脚本、关键输入及证据的校验值另列于 [SHA256SUMS](SHA256SUMS)。

从父仓库复跑格式与错配检查：

```bash
nice -n 15 sandbox-exec -f research/review_studio_g156_r1/readonly.sb \
  /usr/bin/python3 -I -B research/review_studio_g156_r1/audit_dat.py
nice -n 15 sandbox-exec -f research/review_studio_g156_r1/readonly.sb \
  /usr/bin/python3 -I -B research/review_studio_g156_r1/run_parent_generation.py
nice -n 15 sandbox-exec -f research/review_studio_g156_r1/readonly.sb \
  /Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec/.venv/bin/python -I -B \
  research/review_studio_g156_r1/audit_intake.py
```
