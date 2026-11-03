# GXR A12 50mm 原厂 DNG 结构

日期：2026-10-13。样本：`captures/a12-50/2026-10-13/photos/A1-setting1/R8051129.DNG`（18,648,931 字节，SHA-256 `2c70631698dd659943bf14f9138a47060ae1a6bd72a6e43238314174f4183e46`），机身 1.51、A12 50mm，Image Settings = Setting1，RAW 3:2 F。只读解析，工具为本目录的 `inspect_dng.py`，完整输出见 [R8051129-structure.json](R8051129-structure.json)。

```sh
python3 -I research/dng_structure/inspect_dng.py captures/a12-50/2026-10-13/photos/A1-setting1/R8051129.DNG
```

## 布局

| 区域 | 文件偏移 | 大小 | 内容 |
|---|---|---|---|
| TIFF 头＋IFD0 | `0x0–0x1CA` | — | 小端；IFD0 37 项，紧接其后就是数据区，没有空余项位 |
| IFD0 数据、SubIFD、ExifIFD | `0x1CA–0x740` | — | 字符串、矩阵、两个 SubIFD、Exif |
| MakerNote | `0x740` | 22,880 B | `Ricoh\0\0\0`＋大端 IFD；含 `Rev0151` 和 `[Ricoh Camera Info]` |
| UserComment | `0x60A0` | 264 B | `ASCII` 前缀＋空格 |
| 缩略图 | `0x61A8` | 57,600 B | 160×120 未压缩 RGB |
| **空闲填充** | `0x142A8–0x18000` | **15,704 B** | 344 B 的 `00`，随后 15,360 B 全为 `FF`；没有任何标签引用 |
| RAW | `0x18000` | 18,477,072 B | 4304×2862，12 位，未压缩 CFA（RGGB），固定从 `0x18000` 开始 |
| 未引用区 | `0x11B7010` | 4,080 B | 非零残留数据，没有标签引用 |
| 预览 | `0x11B8000` | 69,475 B | 640×480 JPEG |

## 关键标签

- `DNGVersion` 1.0.0.0；`UniqueCameraModel` = `RICOH GR LENS A12 50mm F2.5 MACRO`。
- 有 `ColorMatrix1/2`（标定光源 17、21）、`AsShotNeutral`、`BaselineExposure` 0.3、`BaselineSharpness` 1.33、`LensInfo` 33mm f/2.5。
- 没有 `XMP`（700）、`ProfileName`、`ProfileToneCurve`、`ProfileLookTable`、`ForwardMatrix`、`OpcodeList`。
- `ImageDescription`（64 B）、`Copyright`（70 B）、`UserComment`（264 B）是预留的定长空白字段。
- Exif 只写了 `Sharpness`=0，没有 `Contrast`、`Saturation`；Image Settings 是否记录在 MakerNote 中尚未解析。

## 对"DNG 带配方"的意义

RAW 固定从 `0x18000` 开始，前面有 15.7 KB 空闲填充。在填充区写入一个新的 IFD0（原 37 项＋XMP 标签）和一个 XMP 数据包，再把文件头第 4 字节的 IFD0 指针改过去，就能嵌入 Lightroom/ACR 的调整参数（`crs:` 命名空间），**原始数据和其他偏移都不用动**。一个包含饱和度、对比度、HSL、曲线、暗角、颗粒的 XMP 通常只有几 KB。

两种落地方式：

1. 相机固件在写 DNG 时直接写入：要改 50mm 模块的 DNG 写入代码，风险属于模块改动。
2. 相机只记录配方编号或名称（例如写进已有的定长空白字段），电脑上用一个小工具按编号补写 XMP 或生成 `.xmp` 旁注文件：相机端改动更小。这些字段由机身还是模块填写，尚未确认。

## 未知

- MakerNote 中是否已记录 Image Settings 与 13 个色彩参数。
- 这些空白字段的来源（机身下发还是模块生成）。
- Lightroom/ACR 对相机原生 DNG 中嵌入 `crs:` 设置的实际读取行为，需要用生成的样本实测。
