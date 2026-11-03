# 重新取得并核验本轮固件数据

工作目录固定为 `/Users/wu/.t3/projects/projectricoh`。解析器只依赖 Python 标准库；用 `python3 -I` 运行。它们不会运行固件或下载的第三方源码，也不需要安装解包工具。

## 1. 核验现存取件

如果 `/tmp/gxr_gr_firmware/` 的原始下载与解包内容还在，直接运行：

```sh
python3 -I research/gr_firmware/tools/verify.py
```

预期为 `status: PASS`，12 个 ZIP、8 对现代压缩包 / 载荷校验和、330 个现代数据块及 4 个旧式 bank。该结果不包含相机执行或图像匹配。

## 2. 从官方 URL 重新取件

`fetch.py firmware` 为每个 `model-version` 创建新的空目录。目录已存在时它会拒绝复用。不要把现有不明文件混入取件目录；现有数据先用上一节核验。本节用于目标取件目录尚不存在的情形。

下载请求清单含精确 URL。下载会分别记录实际字节数、SHA-256、最终 URL 和 HTTP 状态；错误会保留在 manifest 中，不能当成功包继续解析。

```sh
python3 -I research/gr_firmware/tools/fetch.py firmware research/gr_firmware/sources/download_requests.json research/gr_firmware/sources/latest_download_manifest.json
python3 -I research/gr_firmware/tools/fetch.py firmware research/gr_firmware/sources/historical_download_requests.json research/gr_firmware/historical_download_manifest.json
python3 -I research/gr_firmware/tools/fetch.py firmware research/gr_firmware/sources/additional_download_requests.json research/gr_firmware/sources/additional_download_manifest.json
```

网络需要宿主正常授权。本轮沙箱网络代理无法连接，取件通过正常网络权限执行，未换用其他浏览器或相机接口。脚本不关闭 TLS 校验。

## 3. 重建静态研究数据

以下命令写入本研究目录及 `/tmp/gxr_gr_firmware/`，不会更改原项目的固件、脚本或其他研究结果。

```sh
python3 -I research/gr_firmware/tools/unpack.py research/gr_firmware/sources/latest_download_manifest.json --output research/gr_firmware/data/unpack_manifest.json
python3 -I research/gr_firmware/tools/unpack.py research/gr_firmware/historical_download_manifest.json --output research/gr_firmware/data/historical_unpack_manifest.json
python3 -I research/gr_firmware/tools/unpack.py research/gr_firmware/sources/additional_download_manifest.json --output research/gr_firmware/data/additional_unpack_manifest.json
python3 -I research/gr_firmware/tools/filesystems.py research/gr_firmware/data/unpack_manifest.json --output research/gr_firmware/data/filesystem_manifest.json
python3 -I research/gr_firmware/tools/mine_tables.py
python3 -I research/gr_firmware/tools/legacy_sibling.py
python3 -I research/gr_firmware/tools/scan_secondary.py
python3 -I research/gr_firmware/tools/assess.py
python3 -I research/gr_firmware/tools/finalize.py
python3 -I research/gr_firmware/tools/verify.py
```

`legacy_sibling.py` 只读已有的 `artifacts/firmware/gxr-1.51/jlaunch3`。`assess.py` 只读已有的 `research/color_calibration/reference_analysis.json`。前者用于同形数据与原始 GXR 哈希核对，后者用于色卡测量核对。没有运行这些位置下的任何既有脚本。

## 4. 重新取得格式文档

格式文档及第三方源码只作为文本保存在 `/tmp/gxr_gr_firmware/docs/`。它们不参与解析器的运行时导入。各 `sources/*doc_requests.json` 及对应 manifest 记录 URL 和本轮文本哈希。

```sh
python3 -I research/gr_firmware/tools/fetch.py docs research/gr_firmware/sources/doc_requests.json research/gr_firmware/sources/doc_manifest.json
python3 -I research/gr_firmware/tools/fetch.py docs research/gr_firmware/sources/mode_doc_requests.json research/gr_firmware/sources/mode_doc_manifest.json
python3 -I research/gr_firmware/tools/fetch.py docs research/gr_firmware/sources/layout_doc_requests.json research/gr_firmware/sources/layout_doc_manifest.json
```

在线文档会变化。已有缓存只读返回其大小和哈希；重新下载后的内容应与保留的 manifest 比较。曾返回 404 或 429 的文档请求也留有记录，不能将它们视为已读取的文档。

`scan_secondary.py` 的结果只表示形状候选。`gxr_33node_projection.*` 只表示数值格式投影。两者均不构成已恢复模式或可刷写固件。
