# FRAME-GR2 与 GXR A12 50mm 的参考关系

核验日期：2026-10-12。用户给出的账号是 [Lyle-xub](https://github.com/Lyle-xub)，其中相机项目为 [FRAME-GR2](https://github.com/Lyle-xub/FRAME-GR2)。本轮只读取公开资料和电脑中的固件文件，未安装 App、执行相机固件、连接或改写相机。

## 当前可确认的来源

- main 提交固定为 `3f819a5749e5ccb1781337098da646bf77fd2c2c`，树为 `17784099a8a2d62bab94966a245c80da8eb711a3`。
- 当前公开文件树只有 `README.md`。README 的发布说明也明确未包含实现源码。已按 Git blob SHA-1 核对保存的 README 与指定树一致。
- 发布 tag 为 `v0.62.1-wn3`；当前资产包含 WN3 固件与各平台 App。tag 名称与当前 App 版本不同，研究以实际资产名称、大小和 SHA-256 固定输入。
- `FRAME-GR2-WN3-Firmware.zip` 为 9,160,352 字节；GitHub asset digest 与作者 `SHA256SUMS.txt` 对应值相同：`af2e231d9ed9a7b604b1e7f63c6dcefd984951f80eb9595421fdc2bdeccc9bcd`。这只标识公开文件，不证明安全性或 GXR 兼容性。

上述核验可用以下只读命令重跑，输出 JSON 在来源目录之外：

```sh
python3 research/frame_gr2/audit_reference.py --output artifacts/frame-gr2/reference-audit.json
```

输入元数据和指定提交 README 保存在 `sources/`；核验输出为 [reference-audit.json](../../artifacts/frame-gr2/reference-audit.json)。

## 作者声明与本项目判断

作者说明包含 16 个独立机内滤镜位置、LUT/预设导入、名称和参数管理、保存后脱离手机继续拍摄，以及 JPEG/DNG 原图导出。这与用户希望十几种可保存配方的使用目标吻合。[直接来源](https://github.com/Lyle-xub/FRAME-GR2/blob/3f819a5749e5ccb1781337098da646bf77fd2c2c/README.md)。

这些是作者的功能说明。本轮没有在 GR II 上复现；导出 DNG 原文件也不能证明自定义 LUT 的计算路径不影响 RAW，更不能证明尚未实现的 GXR 配方功能。

README 和发布包的目标是 **GR II**，要求以官方 GR II 3.00 为基线。GXR 当前研究输入是 1.51 的机身 `ilaunch3` 与 A12 50mm `jlaunch3`。GR II 的 `rg2_v003.frm`、地址、升级按键和更新步骤均不能直接用于 GXR。[发布来源](https://github.com/Lyle-xub/FRAME-GR2/releases/tag/v0.62.1-wn3)。

## 借鉴范围

- 配方采用独立列表和独立记录；按钮可以打开列表，MY 拨盘数量不限制配方容量。
- 提供有名称的预置风格，允许用户修改并保存；首版先使用 GXR 原厂 Image Settings 参数，具体颜色在 A12 50mm 实拍调校。
- 切换配方只更新颜色字段及明确纳入的白平衡字段，不加载完整 My Settings，保留曝光、对焦及 RAW 画质选择。
- 首版保持同一次拍摄的原厂 DNG 与有配方效果的 JPEG。GXR 原厂说明是这项约束的直接基础，GR II 项目不能代替 GXR 验证。

当前不能直接复用实现源代码。发布固件的容器、指令集和新增数据结构需分别核对；相同品牌或相近交互不能证明地址、函数签名、内存容量和图像处理入口相同。

## 与当前交付的关系

已下载并静态对比 WN3 与官方 GR II 3.00：两者使用双层 `UNITY FILE V1.10` 容器。`b01firm6` 逐字节相同；嵌套的 `b01firm8` 内容不同并增加 432,556 字节。GXR 两份主镜像使用另外的 16 段大端加载表。GR II 的负载尚未解包，ISA、16 槽记录格式、LUT 和 RAW 调用关系均未恢复。

因此本轮新增价值是产品设计参照和一套可重跑的容器对比；没有得到能直接用于 GXR 的补丁、算法或字段表。相同组件的运行角色和独立救援能力同样未知。详细证据及来源见 [二进制报告](binary/REPORT.md)，根代理复跑输出在 [binary-verified.json](../../artifacts/frame-gr2/binary-verified.json)。

这是新增参考研究，16 配方固件仍未实现。GXR 已完成的离线成果是专用 M32R 工具、固件分段映射、My Settings 记录外壳和完整性算法；颜色字段、独立配方菜单、可用代码空间、真实 DNG 和坏固件恢复仍待核验。

现行目标与风险见 [A12 50mm 范围](../../docs/A12_50_SCOPE.md)和 [RAW 与风险说明](../../docs/A12_50_RAW_AND_RISK.md)。
