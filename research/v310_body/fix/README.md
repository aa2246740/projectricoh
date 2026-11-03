当前结论为有缺陷。入口为 ../REPORT.md；本目录不授权实体刷写。

先在仓库根运行以下只读检查，确认 UUID 为 14BE04EB-AF49-497E-B36A-B078B2F7C5E8、APFS、可写后再建立指定 TMP。不得使用存储卡路径；各次复跑都用新用例名。

```sh
df -h /Volumes/Workspace
diskutil info /Volumes/Workspace
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1
mkdir -p "$TMPDIR"
```

build.py 与 package.py 只生成 g155b 新引擎和新包；不会重建 resident 或机身。源码差异见 evidence/engine-source-differences.json。完整记录、release、身份门及两个阻塞项的独立汇总为 evidence/repair-final-tests.json 和 recovery-final-comparison.json。

纯函数的 Python 复核示例，使用实际冷启动输入，不需要恢复设备：

```sh
GXR_HARNESS_BACKEND=python nice -n 10 /usr/bin/python3 -I -B research/v310_body/fix/launch.py --name recheck-gate-python --timeout 7200 -- research/v310_body/fix/proof_gate.py --input research/v310_body/fix/local/valid-mount-builtin-r5-gate-input.z --name recheck-gate-python
```

恢复读取负返回的原始保存分支可用 proof_branch.py、local/recovery-restore-v39-read-trace-read-stop.pkl.z 和 --stop 0x2008d28c 分别跑 C/Python。它只复核三条分支指令，不能用来声称完整恢复通过。

首次菜单的设备重放示例：

```sh
nice -n 10 /usr/bin/python3 -I -B research/v310_body/fix/rehydrate_medium.py --snapshot research/v310_body/fix/local/valid-mount-look-r5-session.pkl.z
GXR_EMULATOR_BATCH=1 GXR_HARNESS_BACKEND=c nice -n 10 /usr/bin/python3 -I -B research/v310_body/fix/launch.py --name recheck-first-menu --timeout 7200 -- research/v310_body/fix/continue_run.py --source valid-mount-look-r5 --name recheck-first-menu
```

rehydrate_medium.py 按快照记录的 SHA 复制 local/media 中的精确介质到原 TMP 路径；保留原 FAT 和快照，不设置任何原生值。media-retention.json 记录 5 份去重介质及原路径。恢复快照续跑使用 recovery_read_trace.py，它会复制保存介质；基础 recovery_run.py 的 --resume 未适配原生运行后 FAT 状态，不直接用于该续跑。全新 MAIN 恢复则仍由 recovery_run.py 运行，参数以两份 restore-*-word-process.json 为准，使用新名称。

launch.py 统一限制本任务最多三个测试进程，并保存命令、超时、nice、日志与返回码。辅助队列只做事件等待。退出码 0 不等于验收完成：首次菜单仍为 OPEN，H52 独立检查返回 1，官方恢复的负返回保护也会返回 1。

最终清单只用本目录 seal.py --final 生成。它核对冻结输入、两包 28 个官方伴随文件和中性用语，删除指定 TMP，并逐项读回 SHA256SUMS。不要运行上一轮 ../seal.py，它会改原 g155 包的 MANIFEST。复跑后也须封存新证据并清理 TMP，不能沿用旧清理收据。
