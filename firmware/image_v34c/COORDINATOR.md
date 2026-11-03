# 最终刷机前核对审计输出

本目录只交付未审查候选，不得上卡。`AUDIT_PASS_UNREVIEWED` 证明映像与指定输入、字节白名单和更新容器规则相符。它不批准刷机，也不证明常驻层在相机运行。

## 用最终输入重跑审计

在仓库根目录运行审计，命令必须退出 0。三个常驻层输入必须对应同一份最终主机测试记录。更换输入后，先用未使用的新目录构建，再审计和运行故障注入。打包器拒绝覆盖已有目录。

当前包已生成，不要对现有 `local/candidate-v3` 再执行构建。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B firmware/image_v3/audit.py \
  --package firmware/image_v3/local/candidate-v3 \
  --official artifacts/firmware/gxr-1.51/ilaunch3 \
  --elf firmware/resident_v3/local/resident/build/resident.elf \
  --hooks firmware/resident_v3/local/hooks.json \
  --patch-manifest firmware/resident_v3/local/patch-manifest.json \
  --verbose
```

需要复建时，使用以下尚未占用的目录。若目录已存在，换一个新名称。

```bash
/usr/bin/python3 -I -B firmware/image_v3/build.py \
  --official artifacts/firmware/gxr-1.51/ilaunch3 \
  --elf firmware/resident_v3/local/resident/build/resident.elf \
  --hooks firmware/resident_v3/local/hooks.json \
  --patch-manifest firmware/resident_v3/local/patch-manifest.json \
  --output firmware/image_v3/local/candidate-next
```

## 人工核对这些行

1. 核对首行必须为 `AUDIT_PASS_UNREVIEWED 未审查候选，不得上卡`。任何 `AUDIT_REJECT` 或非零退出码都停止交接。
2. 把 `IMAGE_SHA256=` 与独立审查批准的最终摘要、manifest 和包内实际文件核对。当前为 `104637a935c66e4087d8ab2884a17f308840e11bf27a91652596df1a8871dbe9`。摘要变化必须重新审查。
3. 核对 `OFFICIAL_SHA256=da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` 和 `STAGE2L_SHA256=efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`。这两个参考摘要固定。
4. 把 `INPUT_ELF_SHA256=`、`HOOKS_SHA256=` 和 `PATCH_MANIFEST_SHA256=` 与最终常驻层测试记录核对。当前依次为 `0845f7c4b50d04fe0e5c9393ce32bd4b6c37b044afba18a0225909c98e8c405c`、`d7bc77611826f2ab413be190e24e62b2fbd1d6474b980abf1cadcd1f2d59ab38`、`e90d82e7206f45e390ee558caf2b6984da79e03787527f26706a59ebb1ea6414`。三份输入在包内均有冻结副本。
5. 核对 `PAYLOAD_PASS code=7532 root=256 margin=552 normalized_PT_LOAD_bytes=7544`。与最终链接 map 核对总占用 7788 B。7544 B 文件加载字节包含 7532 B payload 和 12 B pins。
6. 核对 `ELF_METADATA_PREFIX_EXCLUDED=148 root_NOBITS_FF=244`。148 B 文件头前缀不能写入窗口之前。只规范化包内 `resident.load.elf` 的代码 PT_LOAD，原 ELF 保留在 `resident.source.elf`。
7. 核对 `HOOKS_PASS enabled=9 BRA24=7 stock_data_unchanged=2 disabled_unchanged=28 execution_overwrite_bytes=36`。逐行把 H01、H02、H05、H06、H07、H08、H09 的 `BRA24->rv_hook_NN@...` 与最终 map 对齐。H01、H05 各覆盖 8 B，其余五点各 4 B。H03/H04 必须为 `STOCK_DATA_ORIGINAL`，H10–H37 全部必须为 `DISABLED_ORIGINAL`，包含 H15。
8. 核对 `OUTSIDE_DIFF_PASS unexpected=0 allowed=window+7_code_points+checksum_0x16c_0x170`。窗口外只允许七处执行覆盖和 `[0x16c, 0x170)` 的头部校验变化。
9. 核对 `CONTAINER_PASS checksum=0x6a834f7b phase=0 segments=16 components=29 header_other_changes=0`。checksum 随候选改变，phase、段数和头部其它字节规则固定。其它 28 个组件保持官方各自的校验 phase。16 个描述符没有独立段校验字段。
10. 核对 `RECOVERY_PASS identical_official_files=29` 和 `PACKAGE_SUMS_PASS files=67 camera_executed=false sd_accessed=false`。恢复目录逐字节等于官方，不能据此推断任意坏 MAIN 都能恢复。

## 核对故障验证和最终文件清单

阅读 `local/verification-v3.stdout.log` 及 `local/verification-v3/verification.json`。当前结果必须为：

```text
VERIFICATION_PASS deterministic_files=68 rejections=14/14 objdump_branches=7 protected_unchanged=3000
deleted-H15-valid-checksum: E_DISABLED_HOOK
```

需重跑验证时，选择未使用的新目录：

```bash
/usr/bin/python3 -I -B firmware/image_v3/verify.py \
  --package firmware/image_v3/local/candidate-v3 \
  --elf firmware/resident_v3/local/resident/build/resident.elf \
  --hooks firmware/resident_v3/local/hooks.json \
  --patch-manifest firmware/resident_v3/local/patch-manifest.json \
  --output firmware/image_v3/local/verification-next
```

在各清单所在目录核对摘要。所有项目必须显示 `OK`。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/image_v3
shasum -a 256 -c SHA256SUMS
cd local/candidate-v3
shasum -a 256 -c SHA256SUMS
shasum -a 256 candidate/SD_ROOT/ilaunch3 recovery-official-1.51/SD_ROOT/ilaunch3
```

包结构沿用 image_v2，新增 `evidence/patch-manifest.source.json`。候选与恢复目录各含 29 个组件，包内清单覆盖 67 个文件，连同清单自身共 68 个文件。旧 Stage2l 的六个表文件和 v3 引擎容器不属于本包。协调者须另行整合并验收引擎容器与相机运行；本清单不授权上卡或刷机。
