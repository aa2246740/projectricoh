# 复跑本次抽查

在仓库根目录执行。先核对工作卷身份，再创建任务临时目录。只写本审查目录和指定 Scratch。测试串行执行，全部使用 `nice -n 10`。

`runtime_spots.py` 预加载 `tools/native_harness_c/python_backend.py`，设置 `GXR_HARNESS_BACKEND=c`。保留宿主脚本的产品路径，只把临时输出改到本次 Scratch。C 库按现有 manifest 检查来源、库摘要和 Python ABI，实际接口为 API 5。

使用一个未用过的 `--run-tag`，结果保存到 `research/review_g153/reruns/<tag>/`。同名回执不会覆盖。下面给出三个入口示例。

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-g153-r1 \
nice -n 10 sandbox-exec -f research/review_g153/offline.sb \
/usr/bin/python3 -I -B research/review_g153/checks/runtime_spots.py \
cross-exit --unit mount --slot 4 --side c --timeout 3600 --run-tag r2

TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-g153-r1 \
nice -n 10 sandbox-exec -f research/review_g153/offline.sb \
/usr/bin/python3 -I -B research/review_g153/checks/runtime_spots.py \
busy --unit mount --transition effect-other-base --timing race-at-s \
--exit half --side c --timeout 3600 --run-tag r2

TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-g153-r1 \
nice -n 10 sandbox-exec -f research/review_g153/offline.sb \
/usr/bin/python3 -I -B research/review_g153/checks/runtime_spots.py \
looks --unit 28mm --side c --timeout 3600 --run-tag r2
```

把 `--side c` 改为 `--side python` 可确认非 PASS 结果。本次十三种选择共十六条 C 作业全部 PASS，没有需要 Python 确认的产品结果。三条 BUSY 另在 `reruns/backend-audit/` 保存了补充后端计数和 UI 来源审计的复跑。准备脚本的错误另存于 `results/preparation-notes.json`。

本次完整选择如下。每一行是独立进程，按顺序执行即可。

| case | 参数 |
|---|---|
| cross-exit | `--unit mount --slot 4` |
| cross-exit | `--unit mount --slot 8` |
| cross-exit | `--unit 50mm --slot 4` |
| cross-exit | `--unit 50mm --slot 8` |
| busy | `--unit 50mm --transition builtin-effect --timing held --exit ok` |
| busy | `--unit mount --transition effect-other-base --timing race-at-s --exit half` |
| busy | `--unit 50mm --transition effect-builtin --timing transient --exit half` |
| looks | `--unit 50mm` |
| looks | `--unit 28mm` |
| looks | `--unit mount` |
| identity | `--version g153` |
| identity | `--version g151` |
| identity | `--version v38` |

静态入口为 `checks/static_delta.py`、`checks/port_and_recovery.py`、`checks/memory_check.py`。`static_delta.py --finish` 检查局部冻结输入是否改变。机身身份门直接调用原 `identity_compare.py` 的 `compare()`，避开其写死的输出目录限制。

`checks/recovery_spot.py` 执行原机身恢复脚本的冷启动到确认页。两处适配只涉及临时介质目录检查和介质路径序列化。虚拟介质全部位于任务 Scratch。确认后的五亿步三组结果使用原回执，另由 `port_and_recovery.py` 独立核对。

运行前先创建 Scratch。完成并确认没有运行中的检查进程后，删除这个任务的 Scratch。`results/runner-source/` 按 SHA 保存本次执行的三份原生抽查入口文本。当前入口增加了复跑标签和 BUSY 的后端统计，产品判定条件相同。
