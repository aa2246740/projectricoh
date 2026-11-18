<img src="assets/icon.svg" width="64" height="64" alt="">

# projectRicoh

Ricoh GXR 的固件扩展研究：在相机里加色彩配方，以及 XPan 和半格画幅。本仓库公开项目自编的源码、研究方法和文字结论。官方固件、从原厂映像取出的字节、照片、构建产物和刷机包都不在这里，需要自己从理光官网下载官方 1.51 包并在本机生成。

本仓库不是刷机包，也不提供刷机、移植或故障支持。修改过的固件可能让相机无法启动。

## 从哪里读起

- [新单元适配指南](docs/ADAPTING_A_NEW_UNIT.md)：想把方法用到 P10 等其他单元，先读这份。
- [路线图](docs/ROADMAP.md)、[首轮结论与实现路线](docs/RESEARCH.md)、[研究协议](docs/RESEARCH_PROTOCOL.md)。
- [现场事实](docs/FIELD_FACTS.md)：在相机上观察到的事实。每条都写了边界，多数只在 A12 单元上测过。
- [配方指南](docs/GXR_RECIPES_GUIDE.md)、[RAW 约束与刷写风险](docs/A12_50_RAW_AND_RISK.md)。
- [主线引擎的逐字节重建](firmware/mainline/REPRODUCE.md)：`firmware/mainline/` 是当前日常引擎的源码，加上本机生成的私有输入可以逐字节重建日常版 DAT。

## 公开范围

公开树按允许清单生成，只放主线源码、给外人看的文档和一部分研究报告。历史实验目录、内部看板、决策日志、工具链、模拟器和本地数据不公开。研究报告里指向 `local/`、`evidence/` 或其他未公开目录的链接是本机证据，在这里打不开。

## 许可

本仓库的代码和文档按 [MIT 许可](LICENSE) 发布。

本仓库不含第三方配方数据。项目里部分胶片配方改编自 spektrafilm（Andrea Volpato）和 Fotufilm（MUAStudio Inc.）的胶片档案（CC BY-SA 4.0）；这些改编数据不在本仓库里，若以后公开，会按 CC BY-SA 4.0 单独署名、以同样许可发布。

Ricoh、GXR 及文中提到的胶片、相机和软件名称是各自所有者的商标。本项目与这些公司无关，也没有得到它们的认可。

Created in [T3 Code](https://t3.codes).
