# GXR recipe codec and apply, Stage 1c

当前实现保留 `rv1_*` API 前缀，磁盘格式升级为 v2。它支持 Color Setting1 `04`、无染色 B&W `03`、B&W TE `06`。设计依据是 [基础模式研究](../../research/bw_and_base_modes/REPORT.md)，最终包与检查见 [Stage 1c 报告](../../research/stage1c_brand_pack/REPORT.md)。

每个文件仍为 1056 字节，包含 32 字节头和 16 条 64 字节记录。所有整数显式大端编码，不写 C struct。`Rv1Recipe` 在 M32R 为 49 字节，`Rv1Bank` 为 804 字节。

| 格式 | Magic、版本 | 相机双 bank 路径 | 用途 |
| --- | --- | --- | --- |
| v1 | `GXRRV101`、1 | `/ATA1/RECIPES0.DAT`、`RECIPES1.DAT` | 已安装的 Stage 1b；只有 Setting1。 |
| v2 | `GXRRV201`、2 | `/ATA1/RECIPE20.DAT`、`RECIPE21.DAT` | Stage 1c；每槽有基础模式。 |

`rv1_encode`、`rv1_decode` 和 store 只使用 v2。`rv1_import_v1` 显式校验旧库，将占用槽映射为 Color=04，不根据名字猜黑白。新旧路径互不覆盖。未知 magic、版本或基础模式返回 `RV1_VERSION`，阻止自动保存。旧固件不会读取 v2 路径。

头部偏移 8、10、12、14 是 u16 版本、头长、记录长、槽数。16、20、24、28 是 u32 generation、payload 长度、payload CRC、header CRC。CRC-32/ISO-HDLC 分别覆盖 32..1055 和 0..27。

| 记录偏移 | 内容 |
| --- | --- |
| 0、1、2、3 | 槽号、occupied、名称长度、base_mode。 |
| 4..35 | 1..32 字节 printable ASCII 名称，零填充。 |
| 36..48，mode04 | C/S/V、五色鲜艳度、五色色相，13 个 raw 字节。 |
| 36..48，mode03 | 对比度、锐度，余下 11 字节为零。 |
| 36..48，mode06 | 对比度、锐度、鲜艳度、tone，余下 9 字节为零。 |
| 49..50 | 两个 s8 WB，范围 -8..8。 |
| 51..59 | 零保留区。 |
| 60..63 | 记录前 60 字节的 CRC。 |

空槽除槽号和 CRC 外全零。tone 原生值只允许 Red=1、Green=2、Blue=3、Purple=4、Sepia=6。无染色用 mode03，TE 不接受 tone0 或 tone5。全库校验通过后才公开解码结果。

显示档位 1..9 对应 raw `07 06 01 02 03 04 05 08 09`。五色顺序为 orange、green、blue、red、magenta。WB 应用时加9，不猜测其颜色轴名称。

`rv1_plan` 是 apply 和列表匹配共用的写入计划。Color 写 `36F/370/371/8AC..8B5`，BW 写 `645/646`，TE 写 `641/642/644/643`。最后写两轴 WB 和 selector，再请求原厂预览 `0x202D6F38(0)`。不写 RAW 格式、场景、曝光、drive 或 Setting2。预览失败保留已写完整的配方并返回 `RV1_IO`。

`Rv1SettingsPort.acquire` 必须提供当前 S 和串行所有权，不能缓存 MY recall 之前的指针。固件适配器保留原生 ADJ 活动 gate，并检查类别字节 `0x205D9A7F==0`。`cache->busy` 只阻止自身重入，不等于已经证明原厂任务间互斥。原厂拍摄、MY recall 与设置任务的完整并发验收仍需真机。

在项目根目录运行：

```sh
python3 -I firmware/recipe_v1/verify.py
```

测试包含原始 MYSET 字节、完整 bank、损坏与未来格式、交替 bank、三种模式和五种 tone、整个 4096 字节 S 对比、ASan/UBSan、M32R 编译及布局。它们不证明相机执行、JPEG 外观、DNG 写出或掉电持久化。
