# v3.9 / g153 文件身份

本轮只做离线构建和测试，没有操作设备或存储卡。两个包等待差量复审。本文件记录 g153 的最终身份；原 `research/body_v39/FLASH.md` 在本轮只读范围内，因此本轮更新保存在这里。

| 文件 | SHA-256 |
|---|---|
| 两包的 `ilaunch3` | `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d` |
| 发布版 `package_v39_g153/SD_ROOT/GXRCE.DAT` | `e6dab16235dd6fad870c6c6f4935a078351de10334e2145cc94e940598b7083b` |
| 测试版 `package_v39_g153_test/SD_ROOT/GXRCE.DAT` | `5afc388902c9931d55c831e5afc27684d032193c9775e77a8509e9098e65ba7b` |
| resident 的 `.resident` | `7983d6a8eb72f2ef4e58fd5f848ad05550b0b2f17c40c84a09ae43fd07fdd2ca` |

build id 为 `785706aa2323d8f1c313e37c4eab94fdd2899c2f66d40e3dda9d505f32235f81`，ABI id 为 `dd55f5b9c81d35bd9f520b9449a6c463`。

发布版含 0 条用户条目和 10 个效果；测试版含 3 条用户条目和同样的 10 个效果。每包 SD_ROOT 共 30 个文件，28 个同伴文件逐字节等于官方 ZIP。停用文件在各包的 `local/disable/GXRCE.CTL`，未放入 SD_ROOT。

两代的配套身份不同。g151 机身 `71697385bf69283ed6349f8829884e8768ff33be2869f940188b668d782e31fa` 与 g153 DAT、g153 机身与 g151 DAT，均须在执行 DAT 前拒绝。匹配组合、交叉组合及恢复模型的最终回执见本目录 REPORT.md。

机主刷机与检查步骤见 [OWNER_STEPS.md](OWNER_STEPS.md)（复审 P1-01 已按替换稿采纳，取代原 research/body_v39/FLASH.md 中引用 g151 的步骤）。当前测速探测 DAT 没有因此获得使用许可。固件恢复不需要格式化内置照片存储。
