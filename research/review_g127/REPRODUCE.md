在仓库根运行。Python 固定 `/usr/bin/python3 -I -B`，使用本目录的系统写入围栏，TMPDIR 固定在实现者的 local/tmp。不要打开或复制旧 g123/g124 的 Python 源码。

H07 父层重构的 P1-02 残留：

```sh
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/native_checks.py --case h07-parent --unit 50mm
```

该命令先在 fork 副本中观察 preview 服务切点，再在原模型中观察 settings op 2 切点。两个子用例串行使用一个执行槽，结果分别保存，OBSERVED 不转成固件 PASS。可将单元换为 28mm、mount。

独立源码、最终 DAT 与 ELF 核对：

```sh
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/audit_source.py
```

不带 CRC 参数、保持原生 CRC 的原归属及重开检查：

```sh
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/g127_fix/run_existing.py --postcheck research/review_g127/crc_reopen.py research/review_g126/ownership_settings.py --generation 127 --unit 50mm
```

`crc_reopen.py` 移除底层自动安装的主机 CRC 回调，保持原生 CRC，再执行原重开断言，核对原生入口访问和主机回调次数。仅去掉 `--fast-crc` 会让底层安装主机回调，不能用参数名称代替实际回调核对。

后续补跑可为 `run_regressions.py` 指定新的带时区 UTC 截止时间。下面时间占位符需要按新的时间盒填写；已返回 0 的同一 DAT 命令会跳过。默认时间保留本轮的 2026-10-28 22:36 UTC，不会自行延长本轮。

```sh
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/run_regressions.py --deadline-utc 'YYYY-MM-DDTHH:MM:SS+00:00'
```

重新汇总已有结果：

```sh
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/summarize_regressions.py
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/summarize_history.py
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/summarize_controls.py
TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/write_review.py
```

只在所有验证进程结束、报告已经定稿后运行 `seal.py`。它核对冻结输入、措辞和文件摘要，生成以仓库根为基准的 SHA256SUMS。重跑会更新 local 记录，应重新汇总并封存，不能继续声称旧清单覆盖了全部可变输出。
