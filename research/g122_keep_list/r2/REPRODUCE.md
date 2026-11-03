# r2 通信记录复核器

入口为 `research/g122_keep_list/audit_records.py`，同内容副本为 `research/g122_keep_list/r2/audit_records.py`。只依赖 Python 标准库，不导入某代构建脚本。所有输入和输出路径均可显式指定，输出记录实际 DAT SHA 和 generation。

先核对候选，再离线复核已有记录；本轮 gen 122 回归队列已经停止，不再运行剩余测试。

```sh
shasum -a 256 firmware/package_v36_g122/SD_ROOT/GXRCE.DAT
/usr/bin/python3 -I -B research/g122_keep_list/r2/check_auditor.py
/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py \
  --dat firmware/package_v36_g122/SD_ROOT/GXRCE.DAT \
  --records research/g122_keep_list/native/matrix-50mm.json \
            research/g122_keep_list/native/matrix-28mm.json \
            research/g122_keep_list/native/matrix-mount.json \
  --output research/g122_keep_list/r2/matrix-record-safety.json
```

复核所有已有完整日志及哨兵行内地址：

```sh
/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py \
  --dat firmware/package_v36_g122/SD_ROOT/GXRCE.DAT \
  --records research/g122_keep_list/native research/g122_keep_list/field \
            research/g122_keep_list/open-counts-122-50mm.json \
            research/g122_keep_list/open-counts-122-28mm.json \
            research/g122_keep_list/open-counts-122-mount.json \
            research/g122_keep_list/machine-gates.json \
  --sentinel-records research/g122_keep_list/open-counts-122-50mm.json \
                     research/g122_keep_list/open-counts-122-28mm.json \
                     research/g122_keep_list/open-counts-122-mount.json \
  --output research/g122_keep_list/r2/record-safety.json
```

复用到其他 generation 时，将 `--dat`、`--records`、`--output` 换成获准的实际路径。`--records` 接受多个 JSON 文件或目录，目录递归读取 JSON；不要把只有故障摘要的记录当作完整通信流。单元顺序为 50mm、28mm、mount，支持本项目相同的 DAT/GXMP 布局。不同 DAT SHA 的记录列入 excluded_other_dat，不计入当前候选。

`--sentinel-records` 是可选的 gen 122 二十次调用样本检查；下一代取消该路径时应省略。范围与相邻字节保留通过不证明未读字节未变化，不关闭 P1-01/P1-02。

实际命令 receipts、日志和已完成产物均由 REPORT.md 索引；三个确认命令的耗时是观察上界。更新证据后，最后重新生成报告与仓库根基准清单。

```sh
/usr/bin/python3 -I -B research/g122_keep_list/r2/refresh_evidence.py
/usr/bin/python3 -I -B research/g122_keep_list/r2/write_report.py
/usr/bin/python3 -I -B research/g122_keep_list/r2/seal.py
```
