# 最终刷机前核对审计输出

本目录只交付未审查候选，不得上卡。`AUDIT_PASS_UNREVIEWED` 证明映像与指定输入、字节白名单和更新容器规则相符。它不批准刷机，也不证明常驻层在相机运行。

## 用最终输入重跑审计

在仓库根目录运行，命令必须退出 0。`--elf` 和 `--hooks` 指向最终主机测试对应的常驻层输入。常驻层变更后重新构建新目录，再重跑审计和故障注入。不要覆盖旧包。

```bash
python3 -I -B firmware/image_v2/build.py \
  --official artifacts/firmware/gxr-1.51/ilaunch3 \
  --elf firmware/resident_slim/local/build/resident.elf \
  --hooks firmware/resident_slim/local/hooks.json \
  --output firmware/image_v2/local/candidate-final

python3 -I -B firmware/image_v2/audit.py \
  --package firmware/image_v2/local/candidate-final \
  --official artifacts/firmware/gxr-1.51/ilaunch3 \
  --elf firmware/resident_slim/local/build/resident.elf \
  --hooks firmware/resident_slim/local/hooks.json \
  --report firmware/image_v2/local/audit-final.json \
  --verbose
```

## 人工核对这些行

1. 核对首行必须为 `AUDIT_PASS_UNREVIEWED 未审查候选，不得上卡`。任何 `AUDIT_REJECT` 或非零退出码都停止交接。
2. 把 `IMAGE_SHA256=` 与独立审查批准的最终机身摘要、该包 manifest 和包内 `ilaunch3` 的实际摘要核对。当前候选为 `20aaeec12f221295b914d31a5978202de036a3dff241dc9e22fadb852bd1abad`。新版 ELF 允许产生新摘要，旧批准不自动覆盖新包。
3. 核对 `OFFICIAL_SHA256=da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` 和 `STAGE2L_SHA256=efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`。它们是固定参考，不能随候选变化。
4. 把 `INPUT_ELF_SHA256=`、`HOOKS_SHA256=` 与最终常驻层测试记录核对。当前分别为 `36e65caf5136d65cab35154a950665b9abb61f0afbb2cece75b36273c211dafd`、`abfebeeb29a9c8697702a5262b9e5dba24955888c6d7f52d2e0e0b60352f8f0e`。测试次数本身不能绑定这些输入。
5. 核对 `PAYLOAD_PASS` 的 code、root、margin 与最终链接 map。当前为 `code=7784 root=256 margin=300 normalized_PT_LOAD_bytes=7796`。后续代码只能使用剩余窗口，root 固定为 256 B。规范化 ELF 的 7796 B 是 7784 B 代码加 12 B pins。
6. 核对 `ELF_METADATA_PREFIX_EXCLUDED=148 root_NOBITS_FF=244`。本次原始 ELF 首段包含文件头，前缀位于窗口之前，不能写入机身。只修改包内 `resident.load.elf` 的代码 PT_LOAD 描述符，原 ELF 留在 `resident.source.elf`。若新版 ELF 无此前缀，这行应为 0，人工确认差异。
7. 核对 `HOOKS_PASS enabled=26 BRA24=24 stock_data_unchanged=2 disabled_unchanged=11`。逐行核对 `--verbose` 输出的 24 个 `HOOK ... BRA24->rv_hook_NN@...`，把 VA、符号和最终 map 对上。H03/H04 必须为 `STOCK_DATA_ORIGINAL`。H24、H26–H30、H33–H37 必须为 `DISABLED_ORIGINAL`。只看总数不够。
8. 核对 `OUTSIDE_DIFF_PASS unexpected=0 allowed=window+24_code_points+checksum_0x16c_0x170`。这是完整文件比较，允许头部校验字段变化。不能把“仅窗口和 hook 点”理解为头部校验字段也不变。
9. 核对 `CONTAINER_PASS ... phase=0 segments=16 components=29 header_other_changes=0`。本次 checksum 为 `0x6a7fcd4d`。checksum 随候选变化；phase、段数、组件数和其它头部字节规则保持。16 段的加权贡献与空隙贡献在审计 JSON 中相加得到此值，容器没有独立的段校验字段。
10. 核对 `RECOVERY_PASS identical_official_files=29` 和 `PACKAGE_SUMS_PASS files=66 camera_executed=false sd_accessed=false`。恢复文件已逐字节比较，但坏 MAIN 后能否进入更新流程仍取决于实际故障。

## 核对最终文件清单

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/image_v2/local/candidate-final
shasum -a 256 -c SHA256SUMS
shasum -a 256 candidate/SD_ROOT/ilaunch3 recovery-official-1.51/SD_ROOT/ilaunch3
```

本包保持 Stage2l 的 `candidate/SD_ROOT`、`recovery-official-1.51/SD_ROOT`、`evidence`、`manifest.json`、`README.txt` 和 `SHA256SUMS` 目录结构。candidate 有 29 个更新文件。旧 Stage2l 的 6 个配方表不属于本次输入，未随包复制。新 engine、IROM 容器及相机端接纳由协调者单独集成与验收。
