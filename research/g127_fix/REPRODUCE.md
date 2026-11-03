# gen 127 复现

在仓库根运行，全部 Python 固定为 `/usr/bin/python3 -I -B`。系统围栏仅允许三个交付目录写入，并禁止网络。下列命令直接加载原脚本；不复制其源码。

```sh
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/g127_fix/local/write-fence.sb /usr/bin/python3 -I -B research/g127_fix/build_candidate.py
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/g127_fix/local/write-fence.sb /usr/bin/python3 -I -B research/g127_fix/run_existing.py --postcheck research/g127_fix/ownership_reopen.py research/review_g126/ownership_settings.py --generation 127 --unit 50mm
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/g127_fix/local/write-fence.sb /usr/bin/python3 -I -B research/g127_fix/run_existing.py research/review_g126/cold_reentry.py --generation 127 --unit 50mm
/usr/bin/python3 -I -B research/g127_fix/check_delta.py
/usr/bin/python3 -I -B research/g127_fix/audit_communications.py
shasum -a 256 -c research/g127_fix/SHA256SUMS
```

归属及 cold_reentry 命令分别将单元换为 `28mm`、`mount`。原始运行记录在 `local/release127`。全量回归及旧代接口适配的实际命令保留在 `commands.jsonl`，超时和未完成项见 `evidence/acceptance.json`。复跑会产生新记录，需重新生成清单。

常规回归的 `--fast-crc` 仅使用现有 CRC 主机叶函数。gen 122 的 `--reference-expectations` 使用旧脚本的正确基线期望，实际模型绑定 gen 127 DAT；保留原 OBSERVED 标记。原有断言保持启用。
