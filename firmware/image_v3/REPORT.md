# image-v3 打包与独立审计报告

v3 候选已生成，完整 `--verbose` 审计通过。9 个启用点包含 7 处 BRA24 执行覆盖，共 36 B；H03/H04 保留原厂数据，H10–H37 共 28 点逐点确认保持官方字节。13 个既有故障案例及新增 H15 案例全部被拒绝。候选仍为“未审查候选，不得上卡”。

候选文件为 [local/candidate-v3/candidate/SD_ROOT/ilaunch3](local/candidate-v3/candidate/SD_ROOT/ilaunch3)，长度 3,993,340 B。

```text
IMAGE_SHA256=104637a935c66e4087d8ab2884a17f308840e11bf27a91652596df1a8871dbe9
```

本次只写入 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/image_v3/`。`image_v2`、`resident_v3`、官方固件和 Stage2l 参考均只读；3000 个受保护文件在任务开始、验证前后和报告前的 SHA-256 一致。未启动子代理，未安装包，未构建常驻层，未接触相机、任何存储卡或刷机流程，未 commit 或 push。全部派生映像、ELF、恢复副本和原始日志保存在 `local/`。

## 适配内容与错误根因

从 image_v2 复制 `build.py`、`audit.py`、`verify.py`、`policy.json`、`.gitignore` 和交接文档起步。原错误已用 v3 ELF 和原 v2 policy 复现，见 [local/v2-reproduction.log](local/v2-reproduction.log)：

```text
BUILD_REJECT hook symbol is not inside resident code
```

根因是 v2 policy 仍把 H10 等已删除点列为启用点，并要求 ELF 提供对应 `rv_hook_NN` 符号。v3 的 `hooks.json` 已明确关闭这些点，ELF 也没有相应桩；问题不在 v3 携带无效的启用符号。

当前适配如下：

- `policy.json` 只调整启用集合及关闭点的目标符号。37 个点的 ID、地址、长度、类型，以及官方 29 文件摘要、Stage2l 摘要、窗口和 root 规则均与 v2 相同。新 policy SHA-256 为 `1cc1664145b0a3d1bafac553bb418d6cf1b7068a77f2cbba42b40813c9a919fb`。
- 打包器和审计器都新增必填 `--patch-manifest`，独立核对 hooks 与 patch manifest 的 37 行顺序、启用布尔值、地址、长度、类型和官方原字节。manifest 的 Stage2l 参考字节也与参考映像核对，状态必须为 `constrained_link=true`、`installable=false`。
- 打包器只为七个启用执行点解析目标符号，并从 ELF 生成 BRA24。生成结果必须与 patch manifest 的最终替换字一致。关闭点及 H03/H04 的清单替换字必须等于官方值；实际映像从官方原件起步，只写窗口、七处执行点和头部校验。
- 审计器仍不导入或调用打包器。它重新解析实际映像、ELF、hooks 和 patch manifest，逐点核对 37 处，再比较完整文件的其它字节。包内冻结三份输入，新增 `evidence/patch-manifest.source.json`，并验证输入、manifest、证据文件和完整包清单。
- `verify.py` 保留 v2 的 13 个案例及其指定拒绝码，新增 H15 篡改案例，复建并比较全部包文件，还调用既有 M32R objdump 解码七处实际跳转。

ELF 结构、分段映射、范围与对齐、未定义符号和重定位拒绝、官方身份、FF 窗口、NOBITS、规范化 ELF、容器、其它组件、恢复包、目录成员、符号链接和 SHA256SUMS 检查均保留。新增清单校验没有代替这些检查。完整源差异见 [local/source-diff.patch](local/source-diff.patch)。

## 输入身份与窗口

| 输入 | 仓库相对路径 | SHA-256 |
| --- | --- | --- |
| 官方机身 | `artifacts/firmware/gxr-1.51/ilaunch3` | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| Stage2l 参考 | `artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/ilaunch3` | `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7` |
| v3 ELF | `firmware/resident_v3/local/resident/build/resident.elf` | `0845f7c4b50d04fe0e5c9393ce32bd4b6c37b044afba18a0225909c98e8c405c` |
| v3 hooks | `firmware/resident_v3/local/hooks.json` | `d7bc77611826f2ab413be190e24e62b2fbd1d6474b980abf1cadcd1f2d59ab38` |
| v3 最终替换字清单 | `firmware/resident_v3/local/patch-manifest.json` | `e90d82e7206f45e390ee558caf2b6984da79e03787527f26706a59ebb1ea6414` |

固定窗口为 VA `[0x2005276c, 0x20054800)`，文件偏移 `[0x796c, 0x9a00)`，共 8340 B。官方窗口全为 FF。7532 B payload 与 256 B root 合计占用 7788 B，余量 552 B。payload 结束于 `0x200544d8`，root 起于 `0x20054700`。

原 ELF 首个 PT_LOAD 包含位于窗口之前的 148 B ELF 头和程序头，打包器排除这个严格限定的前缀。包内原始 ELF 保留不变，只规范化 `resident.load.elf` 的首个程序头。独立审计确认规范化 ELF 的全部 7544 B 文件加载字节都与映像相同，包括 7532 B payload 和 12 B pins。244 B root NOBITS 和 552 B 空隙保持官方 FF。

## 七处执行覆盖与关闭点

下表来自实际候选的独立解码，objdump 得到相同目标。

| 点位 | VA | 文件偏移 | 覆盖 B | ELF 符号 | 跳转目标 |
| --- | --- | --- | --- | --- | --- |
| H01 | `0x2028709c` | `0x23c29c` | 8 | `rv_hook_01` | `0x20052a60` |
| H02 | `0x202870a8` | `0x23c2a8` | 4 | `rv_hook_02` | `0x20052a84` |
| H05 | `0x201febe4` | `0x1b3de4` | 8 | `rv_hook_05` | `0x20052aa4` |
| H06 | `0x202be24c` | `0x27344c` | 4 | `rv_hook_06` | `0x20052ac8` |
| H07 | `0x202871d8` | `0x23c3d8` | 4 | `rv_hook_07` | `0x20052ae8` |
| H08 | `0x202bb968` | `0x270b68` | 4 | `rv_hook_08` | `0x20052b08` |
| H09 | `0x2017098c` | `0x125b8c` | 4 | `rv_hook_09` | `0x20052b28` |

H03 与 H04 分别检查 4 B 和 1 B 原厂数据，不生成执行补丁。H10–H37 的 28 处都以 `DISABLED_ORIGINAL` 单独列入 verbose 日志；不因符号已删除而跳过官方字节核对。

完整映像共 7261 个字节与官方不同，其中窗口 7222 B、七处执行覆盖 36 B、头部校验字段 3 B。窗口外的全部差异仅在上述七处和 `[0x16c, 0x170)`；没有其它字节变化。

## 容器与恢复包

机身 checksum 为 `0x6a834f7b`，唯一匹配 phase 为 0。审计器按每个字节独立重算权重，并另算十六段与空隙贡献：

```text
checksum = sum(image[512 + i] * (i % 6 + 2)) mod 2^32
16 段贡献 = 0x69f7f660
7957 B 空隙和尾部贡献 = 0x008b591b
合计 = 0x6a834f7b
```

头部只有校验字段允许变化，16 个段描述符及其它头部字节全部保持官方值；描述符没有独立段校验字段。全部 29 个候选组件的长度和唯一校验 phase 均通过，phase 集合为 0、2、4。除 `ilaunch3` 外的 28 个组件逐字节等于官方。

`recovery-official-1.51/SD_ROOT/` 的全部 29 个文件与官方及 Stage2l 恢复副本逐字节一致。包内 SHA256SUMS 覆盖 67 个文件，连同清单自身共 68 个文件。第二次构建的 68 个文件全部逐字节一致。旧 Stage2l 六个表文件和 resident_v3 的引擎容器未混入本包。

## 完整审计输出

以下汇总行取自 [local/audit-v3.stdout.log](local/audit-v3.stdout.log)。该日志还包含全部 37 个点位的 verbose 行；机器可读结果在 [local/audit-v3.json](local/audit-v3.json)。

```text
AUDIT_PASS_UNREVIEWED 未审查候选，不得上卡
IMAGE_SHA256=104637a935c66e4087d8ab2884a17f308840e11bf27a91652596df1a8871dbe9
OFFICIAL_SHA256=da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7
STAGE2L_SHA256=efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7
INPUT_ELF_SHA256=0845f7c4b50d04fe0e5c9393ce32bd4b6c37b044afba18a0225909c98e8c405c HOOKS_SHA256=d7bc77611826f2ab413be190e24e62b2fbd1d6474b980abf1cadcd1f2d59ab38
PATCH_MANIFEST_SHA256=e90d82e7206f45e390ee558caf2b6984da79e03787527f26706a59ebb1ea6414
PAYLOAD_PASS code=7532 root=256 margin=552 normalized_PT_LOAD_bytes=7544
ELF_METADATA_PREFIX_EXCLUDED=148 root_NOBITS_FF=244
HOOKS_PASS enabled=9 BRA24=7 stock_data_unchanged=2 disabled_unchanged=28 execution_overwrite_bytes=36
OUTSIDE_DIFF_PASS unexpected=0 allowed=window+7_code_points+checksum_0x16c_0x170
CONTAINER_PASS checksum=0x6a834f7b phase=0 segments=16 components=29 header_other_changes=0
RECOVERY_PASS identical_official_files=29
PACKAGE_SUMS_PASS files=67 camera_executed=false sd_accessed=false
```

## 14 个故障案例全部拒绝

全部审计退出码为 1，实际拒绝码与预期相同。原始包副本、修改位置、摘要、命令、审计 JSON 和 stdout、stderr 均保留在 `local/verification-v3/<case>/`；总记录为 [local/verification-v3/verification.json](local/verification-v3/verification.json)。

| 序号 | 注入 | 预期 | 实际 |
| --- | --- | --- | --- |
| 1 | 窗口和 hook 外改一字节，并修复校验 | `E_OUTSIDE_DIFF` | `E_OUTSIDE_DIFF`，退出 1 |
| 2 | H01 跳转目标错误，并修复校验 | `E_HOOK_TARGET` | `E_HOOK_TARGET`，退出 1 |
| 3 | 头部容器校验值错误 | `E_CHECKSUM` | `E_CHECKSUM`，退出 1 |
| 4 | ELF 声明的 payload 超出窗口 | `E_PAYLOAD_RANGE` | `E_PAYLOAD_RANGE`，退出 1 |
| 5 | 恢复包 ilaunch3 改一字节 | `E_RECOVERY` | `E_RECOVERY`，退出 1 |
| 6 | 未启用 H24 改写，并修复校验 | `E_DISABLED_HOOK` | `E_DISABLED_HOOK`，退出 1 |
| 7 | H03 原厂数据改写，并修复校验 | `E_STOCK_DATA` | `E_STOCK_DATA`，退出 1 |
| 8 | 代码与 ELF 不同，并修复校验 | `E_PAYLOAD_BYTES` | `E_PAYLOAD_BYTES`，退出 1 |
| 9 | 552 B 空隙出现非 FF，并修复校验 | `E_PAYLOAD_BYTES` | `E_PAYLOAD_BYTES`，退出 1 |
| 10 | hooks 原字节声明错误 | `E_HOOK_ORIGINAL` | `E_HOOK_ORIGINAL`，退出 1 |
| 11 | 头部段描述符改写 | `E_HEADER` | `E_HEADER`，退出 1 |
| 12 | 规范化 ELF 改写 | `E_ELF_NORMALIZATION` | `E_ELF_NORMALIZATION`，退出 1 |
| 13 | 包内 SHA256SUMS 错误 | `E_SUMS` | `E_SUMS`，退出 1 |
| 14 | 新增：已删除 H15 改写，并修复校验 | `E_DISABLED_HOOK` | `E_DISABLED_HOOK`，退出 1 |

七个名称以 `valid-checksum` 结尾的案例都修复了容器校验、manifest 中的机身摘要和包内 SHA256SUMS。新增 H15 案例在文件偏移 `0xa274` 改一字节后，仍收到 `AUDIT_REJECT E_DISABLED_HOOK: H15 disabled point changed`。ELF 越界案例还确认打包器拒绝，且未创建输出目录。

```text
VERIFICATION_PASS deterministic_files=68 rejections=14/14 objdump_branches=7 protected_unchanged=3000
```

objdump 使用既有 `research/tooling_m32r/prefix/bin/m32r-elf-objdump`，SHA-256 为 `8d3712c11cac0ffc63b790148c49a916f25d96fceabbb3c1daa125cf4904368a`。七处解码日志与命令保存在 `local/verification-v3/objdump/`。

## 复跑命令与交接

本次构建命令如下；现有目录已封存，复跑时把输出换成新目录。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B firmware/image_v3/build.py \
  --official artifacts/firmware/gxr-1.51/ilaunch3 \
  --elf firmware/resident_v3/local/resident/build/resident.elf \
  --hooks firmware/resident_v3/local/hooks.json \
  --patch-manifest firmware/resident_v3/local/patch-manifest.json \
  --output firmware/image_v3/local/candidate-v3

/usr/bin/python3 -I -B firmware/image_v3/audit.py \
  --package firmware/image_v3/local/candidate-v3 \
  --official artifacts/firmware/gxr-1.51/ilaunch3 \
  --elf firmware/resident_v3/local/resident/build/resident.elf \
  --hooks firmware/resident_v3/local/hooks.json \
  --patch-manifest firmware/resident_v3/local/patch-manifest.json \
  --verbose

/usr/bin/python3 -I -B firmware/image_v3/verify.py \
  --package firmware/image_v3/local/candidate-v3 \
  --elf firmware/resident_v3/local/resident/build/resident.elf \
  --hooks firmware/resident_v3/local/hooks.json \
  --patch-manifest firmware/resident_v3/local/patch-manifest.json \
  --output firmware/image_v3/local/verification-next
```

使用系统 `/usr/bin/python3 -I -B`，实际解释器为 `/Applications/Xcode.app/Contents/Developer/usr/bin/python3`，版本 3.9.6。未安装 Python 包。卷预检已确认 APFS、挂载点、可写属性和 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，原始结果在 `local/volume-preflight.plist`。

`.gitignore` 第 1 行为 `/local/`。派生写入前及交付前均用 `git check-ignore -v` 确认规则，记录在 `local/git-check-ignore.log` 和 `local/git-check-ignore-final.log`。受保护文件的首尾清单在 `local/protected-before.json`、`local/protected-after.json`；验证器另存了一组前后清单。任务开始与结束的 Git 状态相同，当时均已包含本任务新建的 image_v3 条目。

[COORDINATOR.md](COORDINATOR.md) 沿用 image_v2 的格式，给出最终输入绑定、逐点输出、checksum、恢复包和摘要的人工核对要求。目录根 [SHA256SUMS](SHA256SUMS) 覆盖源码、报告、交接文档及全部 local 证据，候选包内另有完整清单；清单不包含自身。

本报告证明离线打包、字节边界、容器与恢复副本一致性，不证明常驻层在相机运行，也不证明坏 MAIN 后仍能进入更新流程。候选未获独立审查批准，仍不得上卡。
