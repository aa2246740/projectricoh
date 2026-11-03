# probe_mcm_r1

本目录交付 BASE 与 CPU/L17 的只读候选，不包含 C120、C004、C100、C040 写探针。真实模式切换、休眠使参考失效的路径尚未闭合，因此未通过完整上机规格。结论、证据与剩余工作在 [REPORT.md](../../research/probe_mcm_r1/REPORT.md)。

唯一构建、验证和封包入口如下，均从仓库根目录运行：

```sh
/usr/bin/python3 -I -B firmware/probe_mcm_r1/build_probe.py
/usr/bin/python3 -I -B firmware/probe_mcm_r1/verify_probe.py --rebuild-compare
/usr/bin/python3 -I -B firmware/probe_mcm_r1/finalize_probe.py
/usr/bin/python3 -I -B firmware/probe_mcm_r1/finalize_probe.py --check-only
```

最终卡包在 `local/package/`，只含探针 DAT、换卡步骤、中文指南与校验清单。不向卡上复制其它文件。

从 engine_v38_b36 复制的旧 product、package117、build、native_harness 等文件保留作为来源参考；它们不是本候选的执行入口。正式验证调用仓库 `tools/native_harness` 并把缓存、日志全部重定向到本目录 local/。

脚本在写入前核对外置 APFS 卷 UUID、冻结 v3.6 机身和 trust；允许写入的范围仅为本目录与 `research/probe_mcm_r1/`。没有相机、存储卡、T 或机身固件写入动作。
