# 色调曲线：首轮静态扫描

日期：2026-10-13。只读取官方 1.51 固件，没有连接相机，也没有改写固件。

## 做了什么

用 `scan_curves.py` 在 A12 50mm 的 `jlaunch3`、`jlaunch4` 和机身的 `ilaunch3`、`ilaunch4` 中搜索单调递增表：

- u8 表：至少 256 项，跨度至少 200；
- 大端 u16 表：至少 128 项，跨度至少 1000。

```sh
python3 -I research/tone_curve/scan_curves.py artifacts/firmware/gxr-1.51/jlaunch3 artifacts/firmware/gxr-1.51/jlaunch4 --output research/tone_curve/jlaunch-candidates.json
python3 -I research/tone_curve/scan_curves.py artifacts/firmware/gxr-1.51/ilaunch3 artifacts/firmware/gxr-1.51/ilaunch4
```

## 结果

没有找到能确认的色调曲线表。

- `jlaunch3` 的 `0x1d5c00–0x1d9800` 有一组结构化的 u16 数据。它们分段从低值升到 0–4095 之间，每段长度逐渐变长，段前还有全 2、全 1 的步长数组。这更像对数或测光换算用的表，不像按输入均匀采样的整条色调曲线。用途尚未确认。
- `ilaunch3` 的 `0x35ec7c` 和 `0x35ed7c` 是两张 256 项 u8 直通表（0→255），不是色调曲线。
- 四个文件都没有整体高熵区，`jlaunch4` 只有 1 个 64 KiB 块的熵超过 7.5。目前没有看到大面积压缩数据，但这一点不能排除曲线以压缩或其他编码存放。

## 判断与下一步

曲线可能在运行时由对比度等参数计算生成，也可能以少量控制点写给图像处理硬件，或者以本次阈值扫不到的格式存放。

- 测量曲线形状：用同一次快门的 JPEG＋DNG 对比，拟合 RAW 到 JPEG 的映射。每个对比度档位拍一组，就能得到全部档位的曲线。这条路不依赖固件分析。
- 写入自定义曲线：要从 Image Settings 的对比度参数顺着代码追到它写入图像处理硬件的位置。这一步尚未开始，可行性未知。
