可以合并

这次 g156 修复关闭了 r1 的 P2-01 和 P3-01，未发现新的阻塞项。四份原反例在要求的四条路径上均被拒绝，四个真实 DAT 仍逐字节往返，合法 g156 用户条目修改通过父 C gate。完整 `make check` 在本轮只读边界下未通过，Windows 运行时未测，不能把这个结论写成 CI 全绿或相机验收通过。

对象为 [GXR Studio PR #29](https://github.com/aa2246740/gxr-studio/pull/29)，HEAD `6a50c77a8ba04c45ada308a1cbc28074a79116fb`，前次 HEAD `1c690bbe271d6ffaf4e6cf2c575f1dcc83ac1bb5`。本次只审这两个提交之间的差异，共四个文件。GitHub 读回的 PR HEAD 与指定 worktree 相同。父仓库 HEAD 为 `7ba9cb4a2d921cd5ad88f037c1e9693323bad05f`。

2026-11-03 21:01 UTC 开始，限时一小时。检查任务串行，`make -j1`，数值库线程限制为 1，未启动子代理。源 worktree 只读，审查脚本、缓存、反例、构建产物和报告仅写入 `research/review_studio_g156_r2/`。未访问真实卡、相机或用户图库；GitHub 仅查询，未评论、批准或合并。

## 发现

### P2-01 已关闭：外层 156 现在绑定引擎和链接布局

`src/gxr_studio/camdata/datcodec.py:226` 的 `_check_engine_binding()` 比较引擎 SHA-256、入口、BSS 大小、完整且有序的重定位表，以及 DAT 数据末端。`parse()` 在第 471 行检查实际文件长度，`pack()` 在第 720 行检查重建后的长度。`intake.inspect_dat()` 继续调用真实 `parse()`，三个导入入口继续共用 `api/camdata_routes.py:114` 的 `_install()`。

登记值已用父仓库两个实际 ELF 独立核对：`.engine` 与 DAT 引擎逐字节相等，ELF 入口及 `ig_bootstrap` 符号等于 DAT 入口，`.bss` 地址等于 DAT 长度，`.bss` 大小和 `reloc.bin` 也一致。

| 引擎 | 入口 | BSS 字节数 | 完整重定位表 | 链接数据末端 |
| --- | ---: | ---: | --- | ---: |
| g156 release | 61984 | 9284 | `((65840, 56136),)` | 88684 |
| g156 test | 64892 | 9296 | `((68748, 59044),)` | 90532 |

r1 的 `audit_dat.py`、`audit_intake.py` 以字节完全相同的副本重跑，仅因脚本所在目录不同而把输出写到本目录。两者均在第一份外层改标文件处退出，原因分别是 `DatError("156 引擎或链接布局未登记")` 和包装后的 `IntakeError`。旧脚本预期接受反例，因此退出码 1 正是预期改变，不能写成旧脚本整轮通过。

随后用 [audit_delta.py](audit_delta.py) 重建四份反例，逐项核对 SHA 与 r1 的保存结果相同，再跑完整拒绝矩阵。

| 反例 | parse | pack | inspect_dat | `_install()` | HTTP 上传 |
| --- | --- | --- | --- | --- | --- |
| g155c release，仅改外层 156 | 拒绝 | 拒绝 | 422 / dat_invalid | 422 / dat_invalid | 422 / dat_invalid |
| g155c test，仅改外层 156 | 拒绝 | 拒绝 | 422 / dat_invalid | 422 / dat_invalid | 422 / dat_invalid |
| g156 release 引擎放进 g155c 布局 | 拒绝 | 拒绝 | 422 / dat_invalid | 422 / dat_invalid | 422 / dat_invalid |
| g156 test 引擎放进 g155c test 布局 | 拒绝 | 拒绝 | 422 / dat_invalid | 422 / dat_invalid | 422 / dat_invalid |

四份文件也都重新通过了旧 codec 的 parse / pack，排除了反例构造本身损坏。仅改外层的两份仍恰好只变 5 个字节。

路由检查调用未改动的 `_guard_home()`、`inspect_dat()`、`_install()` 和上传处理函数。测试上下文把目标指向一个不存在的仓库外路径，该路径只被检查，从未创建；存储替换次数为 0。FastAPI 使用进程内 TestClient，没有启动服务，也没有替换校验或隐私守卫。这证明实际拒绝分支在写入前生效，但没有验证已有模板的真实落盘与替换。

### P3-01 已关闭：基本往返不再依赖父解析器

`tests/test_g156.py:170` 的基本往返测试现在只依赖对应 DAT。第 185 行的父解析器对照独立。

在本目录准备四个 SHA 正确的 DAT、刻意不提供父解析器，执行两组测试，结果为基础往返 4 通过、父解析器对照 4 跳过。没有修改或临时隐藏父仓库原文件。见 [parent-parser-absent.log](evidence/parent-parser-absent.log)。

## 邻近变体与正常输入

除原四份反例外，对 release / test 各做 13 份变体，共 26 份：引擎首、中、末字节分别翻转且保持长度；入口与 BSS 各增减 4；修改重定位目标、同时修改目标与映像、删掉重定位，以及换成另一条仍满足映像绑定的等长重定位表；DAT 数据末端增减 4。30 份文件在上表五条路径上全部被拒绝。

等长重定位用例保持引擎 SHA、入口、BSS 和 DAT 长度不变，旧 parser 确实接受。长度正负 4 的用例保持引擎及登记的引擎元数据不变，重新生成尺寸和 CRC 都合法的零 Looks GXFX 区，旧 parser 也能规范往返。新版均报引擎或链接布局未登记，未把一般 CRC 错误当作布局绑定的证据。逐例输入摘要、错误原因和路径结果见 [delta-audit.json](evidence/delta-audit.json)。

四个原始 DAT 的 parse → pack 均逐字节相同，`inspect_dat()` 均通过。

| 包 | 字节数 | 外层代数 | 三个 bank 代数 | 往返 |
| --- | ---: | ---: | --- | --- |
| g156 | 88684 | 156 | 155、155、155 | 相同 |
| g156_test | 90532 | 156 | 155、155、155 | 相同 |
| g155c | 86712 | 155 | 155、155、155 | 相同 |
| g155c_test | 89620 | 155 | 155、155、155 | 相同 |

两个真实 g156 各替换为 0、1、30 个用户条目。六组输出重新解析和 `inspect_dat()` 均通过，父仓库原 g156 C gate 的三个单元均返回 0，共 18 个编辑输出检查。原始两个 g156 的 6 个单元检查也通过。C 库从 `engine_v68_g156/candidate/containers/product` 的原源码现场编译，未改代数常量或判断条件。

正常修改只改变 GXUI 区及外层 CRC；引擎、重定位、bank、钉子、内置记录和其余区段保持原字节。这里没有锁整个 DAT SHA。父 C gate 是 macOS 上的主机格式检查，本轮没有执行相机上的 M32R 引擎或启动相机。

对其余 11 个已登记代数 127、129、131、135、137、138、150、152、153、154、155，分别读取真实 DAT，比较旧、新 Profile、逐字节往返、清空和增加用户条目的封装结果，全部相同。再逐单元改坏 bank 代数，共 33 例，新旧都拒绝。本轮未发现其他代数的行为变化；新增绑定函数对非 156 直接返回。

## 新测试与本地检查

新增拒绝用例共 26 个，其中 parse、pack、inspect 三组各 4 个，metadata 10 个，安装回归 4 个。用未修改的新测试、仅在内存中换回 `1c690bbe` 的 codec，前 22 个全部因没有抛出预期异常而失败；换回当前 codec 后 22 个全部通过。没有改测试断言。对照适配器为 [old_codec_plugin.py](old_codec_plugin.py)。

四个安装回归用例在本轮都停在合法模板导入的准备阶段，原因是临时应用数据目录位于父 Git 仓库，产品报 `private_path_in_repository`。因此本轮不能独立确认“26 个原测试都先红后绿”，能确认的是上述 22 个，以及独立脚本对四份反例的真实路由拒绝。保留旧模板的完整安装流程仍需仓库外可写的临时应用数据目录；本轮没有绕过守卫。

| 检查 | 本轮结果 |
| --- | --- |
| `uv sync --frozen --dry-run --offline` | 审核 55 包，无需改动。复用现有环境，未验证全新安装。 |
| `make -j1 check` | 实际运行，退出 2。ruff、format、两种平台的 mypy、安全扫描、dead flags、私有字节与分发包扫描、AGENTS、大文件、OpenAPI 已通过；Vite 写 worktree 的 `frontend/node_modules/.vite-temp/` 被只读沙箱拒绝。 |
| 前端补验 | 只在本目录复制 frontend，核对 13 个非依赖源文件 SHA 相同，再调用原检查器。TypeScript 检查通过，重建的 1 个产物与提交文件逐字节相同。本机 Node 26.7.0，不是 CI 的 Node 22。 |
| make 后续静态检查 | import-linter、deptry、vulture、pylint duplicate-code 均通过。 |
| `tests/test_g156.py` | 93 通过、14 失败、0 跳过。14 项均受仓库内应用数据目录限制，包括 4 个安装回归、2 个模板保存及 8 个文件或上传成功用例。 |
| `make -j1 dast` | 25 通过。 |
| 全套 pytest 与覆盖率 | 104 通过、20 失败后按本轮 maxfail=20 停止。失败来自仓库内临时目录触发隐私守卫，部分用例因此没有进入原先预期的分支。85% 全套覆盖率门槛未完成。 |

检查命令和退出码见 [checks.jsonl](evidence/checks.jsonl)，原失败日志均保留。本轮 pytest 设置 `--force-reruns 0`，并排除未变化的 `tests/test_gpu_parity.py`，没有启动系统 Chrome。WebGPU 的 14 个像素对照用例本轮未运行。没有把 PR 描述中的 1816 通过、92.54% 覆盖率当成本轮证据。

## CI 与未覆盖边界

当前 head 的 [CI run 41717489416](https://github.com/aa2246740/gxr-studio/actions/runs/41717489416) 中，check 和 Windows 完整测试的检查注释均明确写道：

> The job was not started because recent account payments have failed or your spending limit needs to be increased.

GitHub 连接器没有读取 check-run 注释的工具，因此用只读 `gh api` 补取了当前 head 的注释，分别保存在 [github-check-annotations.json](evidence/github-check-annotations.json) 和 [github-windows-annotations.json](evidence/github-windows-annotations.json)。读取时 macOS job 仍排队，windows-probes 被工作流条件跳过。

Windows 完整 pytest、真实 Windows 句柄与子进程、WARP / D3D12、平台探针均未运行；`mypy --platform win32` 只证明类型检查。Ubuntu 运行时、CI 的 Node 22、干净环境安装、本轮 WebGPU、真实 Studio UI 导入、模板成功落盘与保留旧数据的整条流程也未覆盖。GitHub 仓库不带 DAT，工作流也未提供父仓库材料，恢复计费后普通独立 checkout 的真实 DAT 与父 C gate 测试仍会因材料缺失而跳过。

## SHA256SUMS

四个真实 DAT 的 SHA-256 如下，路径相对父仓库。

```text
f42b81a854d86b66ee7f65ac0123153c7e54e59d6e3d2079834490771d0ce1e0  firmware/package_v310_g156/GXRCE.DAT
0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7  firmware/package_v310_g156_test/GXRCE.DAT
69fa85104fcb449e613950bb58c802b9b64464769ae524fe3f7303e06093c2ad  firmware/package_v310_g155c/GXRCE.DAT
c3017d3663e9501b43c921e3b46333b74d751eaa170781c4e1a00d90118f0335  firmware/package_v310_g155c_test/GXRCE.DAT
```

与 r1 相同的四份反例如下。

```text
82da08f66d18cd5e79f0e015c6918c8af09d3653828246aa35e346f80dfd5e3e  g155c-only-outer156.dat
0d92cbedc7e621e63a1269958de960c945d3a3de921f291088551bcf51f3341f  g155c_test-only-outer156.dat
8763d05bee4707ebe9c3236599f68563c519e44e6a111ff53f8d28e1f7884856  g155c-with-real-g156-engine.dat
5a4c46ae452091932322b7acd4a651e45e3ef6648c981a478ba3a463d0237ee7  g155c_test-with-real-g156-engine.dat
```

反例原文件保存在本目录忽略的 `tmp/counterexamples/`。完整清单在 [SHA256SUMS](SHA256SUMS)，覆盖报告、脚本、日志、关键源文件、ELF、C 库、输入及全部反例。起始冻结清单为 [inputs-before.json](evidence/inputs-before.json)，末次核对结果为 [integrity.json](evidence/integrity.json)。

从父仓库复跑主矩阵及校验清单：

```bash
/usr/bin/python3 -I -B research/review_studio_g156_r2/run_checks.py delta
cd research/review_studio_g156_r2
/usr/bin/shasum -a 256 -c SHA256SUMS
```
