# 复核 gen 129 聚焦检查

在仓库根运行。所有命令串行执行，Python 固定为 `/usr/bin/python3 -I -B`。写入围栏只允许本任务的三个目录，并拒绝网络。

先核对封存文件，再从交付源码重建。

```sh
shasum -a 256 -c research/g129_knobs/SHA256SUMS
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B firmware/engine_v49_knobs/candidate/build129.py
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/package.py
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/host_check.py
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/layout.py
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/retained.py research/review_g126/layout_only.py
```

以下命令使用 50mm。依次将单元换为 `28mm` 和 `mount`，目标计算命令的 `--unit` 分别改为 `1` 和 `2`。遇到非零返回码时，先判断是检查入口适配还是产物行为失败，不继续后续验收。

```sh
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/retained.py --postcheck research/g129_knobs/product_after_owner.py research/review_g126/ownership_settings.py --generation 129 --unit 50mm
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/target_check.py --state research/g129_knobs/local/release129/review_g126/target-state-50mm-0 --unit 0
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/retained.py research/review_g126/cold_reentry.py --generation 129 --unit 50mm
```

`retained.py` 只按路径载入旧脚本，在运行时绑定 generation、DAT、源码树和输出目录。没有复制历史复审脚本。重开检查中原有的 `settings_pending` 字节偏移单独换为目标编译器生成的新偏移，原断言保留。

`product_after_owner.py` 在归属恢复成功的同一会话中继续菜单和 T 专项，保留已经验证的原生启动条件。菜单专项使用模型已有的 CRC 主机叶函数；计算路径的批量目标检查执行实际 CRC 指令。

`target_check.py` 用 `tools/native_harness` 的只读解码器核对最终指令字节，并让本任务的 C 执行器执行这些 M32R 指令。每个单元执行全部菜单点，原解释后端再独立核对样本。数学计算、展开、CRC 和整数 ABI 辅助函数均使用目标指令。

完成三个单元后，核对编译码、通信流和封存文件。

```sh
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/audit_codegen.py
/usr/bin/sandbox-exec -f research/g129_knobs/write-fence.sb /usr/bin/python3 -I -B research/g129_knobs/audit_communications.py
/usr/bin/python3 -I -B research/g129_knobs/finalize.py
shasum -a 256 -c research/g129_knobs/SHA256SUMS
```

`prepare.py` 和 `integrate.py` 记录首次复制与接线步骤，只用于空的交付目录。已有源码的常规复核从 `build129.py` 开始。重跑会更新本任务日志和结果，旧的 SHA 清单随之失效；只有所有检查都绑定重建后的 DAT，才重新封存。
