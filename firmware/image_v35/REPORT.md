# image v3.5 没有构建

resident v3.5 链接停在 200 字节余量上，代码末尾 `0x20054690`，门槛 `0x20054638`，超出 88 字节。没有新的 ELF，也就没有新的 ilaunch3。官方 `ilaunch3` 和 `gxr-151.zip` 没有读出来重打包。

细节和字节选项在 `firmware/resident_v35/REPORT.md`。容器 gen 116 同样没有做。

恢复方式：卡 A 的 Stage2l，挂 50mm，「+ 和回放」。

## 这一轮的包

`ilaunch3` SHA-256 `6e9ea05868b2bb56fb60de0e8506aad7b952715c061009b2acc891b45d220b20`。payload 7880 字节，root 256，窗口前余量 204。七个执行钩子还是 H01、H02、H05、H06、H07、H08、H09。`verify.py` 重建逐字节相同，14 个拒绝用例都对上，objdump 的 7 条分支也对上。

`local/package/SD_ROOT/` 里是这份 `ilaunch3`、`gxr-151.zip` 里另外 28 个官方文件（已逐字节核对），以及 gen 116 的 `GXRCE.DAT`。校验在 `local/package/SHA256SUMS`。

resident build id `9cc5359e073a3b65a223ca3af41055fd10e52b5e701db1fe08426023aea731ba`。

新场景在 `harness_scenarios/run_v35.py`，只读导入 `tools/native_harness`。六项都过：OK 然后 MENU，模式留在 1，没有进 `0x202871dc`；Fn2 然后 OK 同样；inflight 的 H07 走 `rv_close_07`，`diag_early` 是 `0x307`；发布后弄坏 UI snapshot，H07 退休且不进原生 setter；28mm 第一次 H01 在 `0x200d7fd8==0` 时不置 `RF_ATTEMPTED`，字写成 1 之后第二次发布 8 行；本开机没进过 READY 时 H07 仍进原生 setter。

宿主没有手写原生 UI，除了把 snapshot magic 异或 1 的那条负面用例。`0x200d7fd8` 由场景写成 1，因为机身现在直接读这个 BSS 字，不再调用 `0x2009359c`。

`tools/native_harness/conformance.py` 通过。`scenarios.py` 的 20 个继承场景都是 violations 0、error False。结果文件没有写进 `tools/native_harness/`，因为那个目录的 guard 只接受自己的 local，而这一轮不改那里。

刷的时候先挂 50mm。换镜头之后如果卡住，挂着那个镜头再刷一次，然后回到 50mm 再查一次。恢复仍是卡 A 的 Stage2l，「+ 和回放」。
