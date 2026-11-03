# GXR v3.2 只读加载诊断

准备的两个数据文件都在本任务 `local/`。DIAG 不安装 IROM、不改名、不写配方或设置；它会暂时分配内存并显示诊断列表。

1. 关机取卡，在电脑上把本任务的 `local/GXRCE.DAT` 和 `local/GXRCF.DAT` 放到卡根目录，保留这两个准确文件名。前者是 DIAG，后者是原 full 产品的逐字节副本。原来的 DEEPTBL、DEEPISP、RECIPE 文件保留即可。
2. 把已经审查批准的 v3.2 `ilaunch3` 放到卡根目录。来源是仓库 `firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3`，SHA-256 为 `05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c`。按住“+”与播放键开机，沿用你验证有效的刷机方法。
3. 刷完后明确关机，再装好 50mm 并开机。使用之前能进入配方菜单的拍摄模式。这次开机第一次打开 ADJ 的 Image Settings。
4. 拍全 `D00` 至 `D0F` 共 16 行。屏幕放不下时上下滚动，分几张拍，保留相邻画面的重叠行。所有行都只是诊断文字，选择它们不会应用配方。
5. 发回照片。如果仍显示原厂 7 项，也拍下并注明“DIAG 没出现”。不要把没改名当成失败，DIAG 本来就让两个文件保持原名。

恢复时，删掉卡上的 `GXRCE.DAT` 和 `GXRCF.DAT`，换回你刚验证正常的 Stage2l `ilaunch3`，同样按住“+”与播放键刷回。保留已有 v6 表和 RECIPE 数据；无需处理 IROM。

如已抄出照片里的 16 行文字，可以在仓库根目录解码：

```sh
python3 -I -B firmware/v32_load_diag/decode.py /绝对路径/屏幕文字.txt
```

必须抄齐全部行，脚本会核对屏幕 CRC，拒绝缺行或文字错误。`D0B` 还保存当前单元两个 IROM 微调文件的原始 open 返回值，用来核对本次发现的 `-1` / `-2` 差异。

这五步用于一次开机收集证据。若 DIAG 的列表也不能发布，仅靠照片不能保证在五分钟内分清常驻入口、加载分配和 UI 准入三个分支；详见 `REPORT.md` 的限制。
