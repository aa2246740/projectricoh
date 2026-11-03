# 复跑并封存 kv2-math-r1

从仓库根按顺序运行下列命令。脚本串行调用编译器和执行器，不启动后台任务。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B research/kv2_math/audit.py --inputs-only
/usr/bin/python3 -I -B firmware/kv2_modules/math/build.py
/usr/bin/python3 -I -B research/kv2_math/capture_reference.py > research/kv2_math/local/capture.log 2>&1
/usr/bin/python3 -I -B firmware/kv2_modules/math/test_host.py > research/kv2_math/local/host.log 2>&1
/usr/bin/python3 -I -B research/kv2_math/test_sanitizers.py > research/kv2_math/local/sanitizers.log 2>&1
/usr/bin/python3 -I -B research/kv2_math/test_target.py > research/kv2_math/local/target.log 2>&1
/usr/bin/python3 -I -B research/kv2_math/audit.py
/usr/bin/python3 -I -B research/kv2_math/finalize.py
/usr/bin/python3 -I -B research/kv2_math/finalize.py --check
```

遇到非零退出码时停止后续命令。`inputs.json` 校验失败表示冻结输入不同；不要刷新该清单继续跑。

最后一条命令应输出 `PASS manifest`。`SHA256SUMS` 使用仓库根相对路径，覆盖源码、报告、结果、指定目标产物、日志、语料和冻结输入。复跑时日志时间会变化，封存命令会为本次结果重建清单。

`capture_reference.py` 按原路径调用冻结验证器，将输出目录改到本任务 `local/reference/`。它记录全部 C 核心和 C 菜单计算，并把原套件的非法 Fade 断言补为 C 入口不变检查。它不复制旧脚本源码。

`test_target.py` 用仓库后端校验目标指令字节并解码，在本目录 C 执行器中跑完整语料，再用仓库原解释后端独立复核 101 例和 185 组整数运算。该执行器只处理实际出现的指令；未支持的指令和地址直接报错。两种执行方式都执行整数辅助函数的目标指令。
