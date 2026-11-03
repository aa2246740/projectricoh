GRMod 的速度来自「电脑程序改 GR 的 ARM 固件、一个公开版本只交一件已经上机核对过的事」；2026-11-01 能对上公开源码的最新标签是 0.8.6，0.8.7 发布说明里的新固件支持还没有出现在这个标签的树里。我们能马上用的是交付说明、写文件读回和拟合门槛，不能搬它的 ARM 补丁，也不能把它的 GPL 代码并进工作室。

2026-11-01 读取。只使用 GitHub 网页和 API 的文本（`api.github.com`、`raw.githubusercontent.com`）。没有下载或运行它的 exe、zip、dmg 或固件，没有访问相机或存储卡，没有 git 写操作，没有开子代理。仓库内只新增本目录。

本仓库 2026-10-27 的 [gr4_repos_review_r1](../gr4_repos_review_r1/REPORT.md) 已经读过它在提交 `8b4ca5e`（即标签 v0.8.5）上的颜色模型。本文不重复那次拟合公式，只补发布节奏、交付方式和 0.8.5 之后公开树上的增量。

没有单独标注的句子，来自下面「来源」里的 API 或原文。标了「推断」的句子是本文的判断。

## 1. 仓库快照

[Maxwooow/Ricoh-GRMod](https://github.com/Maxwooow/Ricoh-GRMod) 创建于 2026-10-08。API 在 2026-11-01 返回：默认分支 `main`，语言 TypeScript，星标 234，fork 23，开放 issue 计数 7（这个计数含开放的 pull request），仓库约 4341 KB。简介原文：给 Ricoh GR IV 系列的非官方改装工具，把 `.xmp` / `.cube` 导入影像控制，并加入自定义宽高比和关机画面。

`main` 的树 SHA 是 `1f4216e4b80d737a3e670c0b6169398f57598b5e`。这次提交的说明是「0.8.6: hue sectors for GR IV's added slots」，作者时间 2026-10-27T23:21:58Z。该树上 `package.json` 的 `version` 是 `0.8.6`，`license` 是 `GPL-2.0-only`。递归树共 474 项，其中文件 419 个：TypeScript 173、Go 83、Python 73、JSON 17、C 14，其余为测试夹具、文档和界面资源。顶层是 `core/`、`ui/`、`shell/`、`tools/`、`docs/`、`examples/`、`third_party/`。

公开提交 196 个，时间从 2026-10-07 到 2026-10-27。按 API 返回的 GitHub 登录名计数：`claude` 160，`Fapitao` 19，`Maxwooow` 6，`Mrjie7205` 4，`sjclijie` 2，另有 4 个提交的作者名是 `GR Mod`、1 个是 `Mathias`。发布由 `Maxwooow` 创建。推断：提交登录名只能说明 Git 身份，不能说明每一行代码的执笔人。

GitHub Actions 工作流数量是 0。树里没有 `.github/`。

## 2. 它做了什么

程序是电脑上的一个窗口。用户打开理光官方固件（或由程序从理光网站下载并核对 SHA-256），在界面里选效果，程序生成一份新固件写到存储卡，相机用自己的固件更新入口刷入。仓库不附带理光固件。README 写明支持的官方版本，在这份公开树上是 GR IV / HDF / Monochrome 的 1.11、GR III / HDF 的 2.10、GR IIIx / HDF 的 1.60；同一段写明 GR III 2.20 和 GR IIIx 1.70 是另一个程序，这份树不支持。

结构，来自 README：

- `core/`：与操作系统无关的 TypeScript。固件容器、补丁、自检、宽高比、`.xmp` / `.cube` 转换、定长 JPEG、早期关机画面脚本。
- `ui/`：Vite + React。只通过 `ui/src/host.ts` 访问本机能力。
- `shell/`：Go。Windows 用 WebView2，macOS 和 Linux 用本机已安装的 Chromium 系浏览器开一个应用窗口，再加一个只监听本机的 HTTP API，用来列存储卡、读写文件、下载官方固件和自更新。
- `tools/`：不进成品的检查程序。用 Unicorn 跑相机固件里的函数，用 Capstone 做反汇编。`tools/gr3x/native_probe.py` 的文件头写明这是函数级 ARM 探针，不是整机模拟器。

公开的 GitHub Release 有 13 个。标签还有 `v0.6.0` 和 `v0.7.1`，不在这 13 个 Release 里。0.8.3 和 0.8.4 没有标签，功能写进了 0.8.5 的说明。下表的「说明里的变化」摘自各 Release 正文；下载数是 API 的 `download_count`，只计安装包，不计 `update.json`（那是程序启动时拉取的清单，不是用户数）。

| 发布 | 发布时间 | 安装包下载数 | 说明里的变化 |
| --- | --- | --- | --- |
| [0.3.3](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.3.3) | 2026-10-08 | exe 4 | 第一份公开包，仅 Windows。把 `.xmp` / `.cube` 导入 Cinema Yellow / Green，最多 8 个额外宽高比，最多 9 张关机画面（靠卡上脚本轮换），工厂菜单入口，在线下载官方 1.11，第一次打开有引导。说明写明刷修改固件不可逆。宽高比移植自 gr-custom-tool。 |
| [0.6.1](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.6.1) | 2026-10-08 | exe 83，dmg 63 | 1.12 桥接固件：给刷不进官方 1.11 的机器先抬版本号。桥接文件由官方 1.11 现场生成并核对 SHA-256。 |
| [0.7.0](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.7.0) | 2026-10-12 | exe 113，dmg 102 | 导入预设时加上曲线之后的第二矩阵。9 个预设的平均 ΔE2000 全部下降，正文给了对照表（例如 Provia 100F 1.32 → 0.43）。新增最多 6 个影像控制槽位，各有名称、图标和一组参数。说明写这些项在 GR IV HDF 上用测试固件 022–034 逐项核对。 |
| [0.7.2](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.7.2) | 2026-10-14 | exe 72，dmg 36 | 光晕按 CineStill 800T 的样片收成固定效果，相机里选关 / 弱 / 强。启动时检查更新，核对签名后替换并重启。更新后第一次打开显示这次的说明。正文同时收入 0.7.1 的修复：RAW 显像里选新增槽位会死机、参数全是 −4。 |
| [0.7.3](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.7.3) | 2026-10-14 | exe 116，dmg 67，zip 22 | 光晕按每个槽位自己的高光起算。把白色压暗的预设以前几乎看不到光晕。需要重新写固件才生效。 |
| [0.7.4](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.7.4) | 2026-10-16 | exe 29，zip 14 | 写回原厂固件前弹出红色提示，要求先在相机里恢复出厂设置。默认焦点在「取消」。每个新增槽位都带光晕，软件里不再单独开关。 |
| [0.7.5](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.7.5) | 2026-10-17 | exe 17，zip 9 | 只修一件事：输入宽高比时中间态（例如先打出「5」）会让界面卡住。 |
| [0.8.0](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.8.0) | 2026-10-17 | exe 146，zip 85 | 最多 8 张关机画面写进固件，在相机「结束画面」里按名字选择，拔卡后仍在。去掉卡上轮换脚本和「开启工厂菜单」。 |
| [0.8.1](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.8.1) | 2026-10-21 | exe 40，zip 27 | 理光当天发布 GR IV 1.20。说明要求先不要升级相机，因为升上去不能退回，也刷不进当时的 GR Mod。在线下载同时列出「暂不支持」的 1.20 和仍可下载的 1.11。 |
| [0.8.2](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.8.2) | 2026-10-23 | exe 72，zip 43 | 光晕在相机里改成关 / 开，Fn 子菜单调弱 / 中 / 强和红 / 白。新增槽位从 6 个增到 20 个。自定义比例只能横构图，因为竖构图取景两侧会留旧画面。开机、关机、调用 U1–U3 时，固件不认识的风格、比例或 ADJ 项改回原厂值，避免从功能更多的固件刷回功能更少的固件后死机。 |
| [0.8.5](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.8.5) | 2026-10-26 | exe 242，zip 318 | GR III / HDF 与 GR IIIx / HDF 并进同一个程序（官方 2.10 / 1.60）。GR III 侧可加宽高比、最多 20 条胶片、ADJ 柔焦、时间戳、结束画面、菜单排序和隐藏。GR IV 增加直闪：固定功率，按对焦距离和闪光指数算曝光。说明同时收入 0.8.4：菜单可拖动排序和隐藏，时间戳可以带风格名，拟合多采样中性色和色域边角。并写明当时不要把相机升到 1.20 / 2.20 / 1.70。 |
| [0.8.6](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.8.6) | 2026-10-30 | exe 59，zip 67 | GR IV 新增槽位的预设除整体拟合外，再按 12 个色相区拟合一次，只有整体明显更接近且灰阶和肤色基本不变差才采用。说明写模型测试里被采用的预设平均色差大约降低三分之一，并在 GR IV 上用测试固件 064 核对。修直闪子菜单退回后 MENU 无响应。更新说明窗口列出代码贡献者。 |
| [0.8.7](https://github.com/Maxwooow/Ricoh-GRMod/releases/tag/v0.8.7) | 2026-10-31 | exe 76，zip 74 | 说明写：GR IV 1.20、GR III 2.20、GR IIIx 1.70 和 GR IV Monochrome 1.10 都能用全部功能；去掉桥接固件；在线更新不再分版本线；GR IV 1.20 上柔焦打开时光晕也生效（测试固件 065）。并写明相机升到这些新版本后不能降级。 |

0.8.6 与 0.8.7 两个标签的 API 都指向同一次提交 `1f4216e4`。该提交的 README 仍写 2.20 / 1.70 不受支持，更新器会拒绝 0.9 及以上（那条线当时留给不能降级的 1.20）。两个安装包的体积不同：0.8.6 的 exe 是 10,911,744 字节，0.8.7 的 exe 是 12,029,952 字节，mac zip 分别是 9,771,672 和 10,419,090 字节。推断：2026-11-01 的公开源码树描述的是 0.8.6；0.8.7 说明里的新固件支持没有落在这个标签上。本文没有打开二进制，不能描述 0.8.7 安装包里的代码。

0.3.3 到 0.8.7 之间，提交说明里还出现过、但没有单独 Release 的版本：0.2.x 宽高比，0.3.x 回放放大修复和在线下载，0.4.x 用清晰度表做柔焦，0.5.x 把柔焦挪到 ADJ 且不再搬动 ADJ 表，0.6.0 把日期戳和单色风格放进界面，0.7.1 修复 RAW 显像，0.7.6 调整关机画面菜单，0.8.3 日期戳跟随拍摄方向，0.8.4 日期戳带风格名、菜单排序和拟合采样。这些后来被写进后续 Release 的正文。

同一时期的 issue 和 pull request 共 19 个（API `state=all`）。和功能直接相关的有：

- [#1](https://github.com/Maxwooow/Ricoh-GRMod/issues/1) 柔焦关不掉，已关闭。
- [#2](https://github.com/Maxwooow/Ricoh-GRMod/issues/2) 建议在曲线后加 3×3，并给出 GR III 上的地址、格式和一组 ΔE。已关闭。0.7.0 的第二矩阵是三天后的发布。
- [#3](https://github.com/Maxwooow/Ricoh-GRMod/pull/3) GR IIIx HDF 1.60，已合并方向的贡献，作者 Mrjie7205。
- [#4](https://github.com/Maxwooow/Ricoh-GRMod/pull/4) Linux 桌面构建，已合并。
- [#6](https://github.com/Maxwooow/Ricoh-GRMod/pull/6)、[#7](https://github.com/Maxwooow/Ricoh-GRMod/pull/7) 菜单排序和拟合采样，已关闭。
- [#9](https://github.com/Maxwooow/Ricoh-GRMod/pull/9) 日期戳带风格名。API 状态仍是 open。0.8.5 的说明把这个点子记为已做，并在 0.8.6 的贡献者名单里写了 sjclijie。推断：点子进了他们自己的提交，这个 pull request 本身没有合并。
- [#14](https://github.com/Maxwooow/Ricoh-GRMod/issues/14) 希望在 GR III 上做「胶卷」：锁定风格和宽高比，拍 36 张，日期旁印张数。已关闭。正文是在问现有钩子能不能复用，不是一份已完成的补丁。
- [#19](https://github.com/Maxwooow/Ricoh-GRMod/issues/19) 用户已经升到 GR III 2.20，询问是否不受支持。已关闭。0.8.7 的说明在次日声称支持 2.20。
- [#20](https://github.com/Maxwooow/Ricoh-GRMod/issues/20) 2026-10-31 仍开放，0 条评论。用户写自己用的是 0.8.7、相机固件 1.10，65:24 把原始 RAW 也裁了。README 对 GR III 的表述是自定义比例保留完整 RAW。两处文字同时成立于公开页面上。推断：完整 RAW 这个承诺至少有一份未关闭的相反报告，不能当成已经证毕的行为。

## 3. 它为什么快

从 2026-10-07 的第一次提交到 2026-10-31 的 0.8.7，公开日历是 24 天，13 个 Release。10 月 8 日一天里，提交说明从 0.3.0 走到 0.6.0（回放修复、引导、柔焦的三代做法、日期戳、单色风格）。10 月 23 日有 47 个提交，主要是 GR III 的第 7、8 轮和直闪。

范围切得很小。0.7.5 的正文只有一个界面卡死。0.8.1 不声称支持新固件，只保证旧的 1.11 还能下载。0.8.6 修一个 MENU 返回，外加一条已经在测试固件 064 上核对过的拟合规则。提交说明里反复出现「test 036」「测试固件 064」这种编号。推断：上机是按编号的构建在推进，公开版本只捡已经核对过的那一刀，所以版本号走得快，每一刀的表面范围不大。

测试分层，README 和工具文件头写得很明确：

- `npm -w core test` 跑 Vitest。配置里单测超时 600 秒。字节级测试需要官方固件放在 `core/testdata/private/`，仓库不附带这份文件。
- `core/test/gr4-unchanged.test.ts` 把「GR IV 输出与上一版一致」钉死。`core/test/combinations.test.ts` 对功能组合做自检，并要求和早前的测试固件 017 逐字节相同。
- `tools/*/` 用 Unicorn 执行构建结果里的原函数（菜单构造、设置保护、日期戳绘制、直闪曝光）。主 README 写 `tools/directflash/check.py` 用一份 Python 规则对照二十万级以上的情形。
- 原生模块用 clang 或 `ziglang` 编成位置无关的 Cortex-A9 代码，再嵌进 TypeScript。换两个链接地址，字节必须相同。
- `cd shell && go test ./...` 覆盖写卡、更新清单和理光下载页解析。
- 没有 GitHub Actions。推断：速度不来自云端 CI，来自本机可以反复跑的函数级探针，加上作者自己的相机。

工具链是现成的。宽高比编译器是 [DoYitNow/gr-custom-tool](https://github.com/DoYitNow/gr-custom-tool) 的移植，`third_party/gr-custom-tool/NOTICE.md` 按文件列出了来源。单色风格声明沿用 [GR4-MonoUnlock](https://github.com/lemonadesaltbagel/GR4-MonoUnlock) 的方法、不包含其代码。色相区参数化声明来自 LUTSmith，经 pull request #8 / #15 进入。关机画面的研究基础写的是 radium-wang 的公开分析。直闪声明是在官方 1.11 里自己找到的，不使用 GR4-GF2Unlock 或 GR III 的代码。推断：第一周能交出宽高比，是因为 GR IV 的容器、裁切和模拟器已经有公开实现，他们做的是移植、自检和壳。

交付也按「用户当天能装」来切。Windows 是单个 exe。macOS 是 zip，说明里每次都写：解压、拖进「应用程序」、第一次被系统拦住时到「隐私与安全性」点「仍要打开」。每个 Release 附安装包 SHA-256。0.7.2 起程序自己拉 `update.json` 和 Ed25519 签名，体积和 SHA-256 都要对上才替换。0.8.5 的提交说明写过：本来要叫 0.9.0，改叫 0.8.5，因为旧程序只会自动安装 0.9 以下的版本。0.8.7 的说明又解释了为什么不叫 0.9.0。推断：版本号在给他们的自动更新通道让路，这是发布工程，不是功能数量。

文档分两层。给用户的是 Release 正文（先中文，后英文）和应用内引导（`ui/src/tour.tsx`：第一次不能跳过总览，每页第一次打开有自己的步骤，帮助按钮可以重看）。给改代码的人是 43 KB 的 README，按地址和测试固件编号写每个机制。`docs/` 里是 GR III 的上机步骤和验证记录，不是第二份用户手册。

社区侧，19 个 issue / pull request 里，能接上已有机制的建议进了后续版本（第二矩阵、菜单排序、Linux 构建、IIIx 移植）。胶卷模式停在「现有钩子够不够」的讨论，没有变成一个版本。推断：他们收的是已经有落点的补丁和点子，不把每个愿望都排进下一版。

下面这些是平台差，搬不过来：

- GR 的主固件跑在 ARM Cortex-A9 上，可以用 clang / zig 编位置无关代码，用 Unicorn 跑原函数。GXR 机身是 Renesas M32R，镜头单元里另有图像处理器。他们的补丁地址、容器（README 里的 `fwdc248b.bin` 分帧和 `A55A5AA5`）和 JPEG 编码钩子对不上我们的机身或单元。
- 他们改的是相机整份官方固件，相机自己的更新程序负责写入，并且新版本号会挡住降级。我们的用户指南写的是按住 `+` 和回放键更新，屏幕版本号仍显示 1.51，恢复路径是备用卡或官方 1.51。两套写入和回退不是同一个机制。
- 他们的颜色资源是 GR 的矩阵、三条曲线和 12 扇区多轴块。GXR 配方走的是镜头单元里的表。0.8.5 那份颜色模型已经在 r1 里读过，不能当成 GXR 的表。
- 第一周的速度建立在 gr-custom-tool、MonoUnlock、LUTSmith 和已有固件分析之上。GXR 没有同等公开的「裁切编译器 + 模拟器」可以移植。

推断：值得学的是切片、上机编号、写卡读回和说明文案。不值得学的是「24 天 13 个固件版本」这个表面数字，那个数字依赖 ARM 工具链和已经公开的 GR 研究。

## 4. 可以借鉴的具体东西

### 4.1 用户体验和交付

**每个公开包一份中文说明，并带 SHA-256。** 他们的 Release 先写用户能看见的变化，再写「要重新写固件才生效」或「不要升级相机」，最后是系统要求和两个哈希。我们的 [用户指南](../../docs/GXR_RECIPES_GUIDE.md) 已经用「你会看到 / 按」写操作，但安装包名称、版本、官方固件从哪拿、更新画面长什么样，仍写着「待确认」。用法：以后每份给用户的卡包，在包内放一页说明，只写这一版核对过的行为，哈希用我们已有的 SHA-256 习惯。工作量小，就是写字和冻结文件。风险低。没在相机上见过的界面不要写进「你会看到」。

**版本号在界面上，点开是历次说明。** 他们的引导把版本号当成一步（`tour.tsx` 的 `version`），0.7.2 起点版本号能看每版正文。我们工作室的 `pyproject.toml` 版本是 `0.1.0`，`studio/CHANGELOG.md` 只有两条本地提交说明；指南不显示包版本。用法：工作室页脚写出版本，旁边放一份人话的变更，和卡包说明用同一个版本号。工作量小。风险低。

**安装包是一个文件，说明里重复第一次打开怎么放行。** Windows 单 exe，macOS 是 zip 加拖进「应用程序」，每次 Release 都重复「仍要打开」。我们工作室是双击 `GXR Studio.command`，README 已经写了右键打开和「可移除的卷」。用法：若以后把工作室收成一个给别人下载的包，沿用这段「第一次会被系统拦住」的固定短句，并给这个包做哈希。工作量中等，因为现在没有这种下载包。风险低。在没有安装包之前，不要先做自更新。

**写存储卡先写临时文件，读回再比对哈希。** `shell/README.md` 写明：写到同目录临时文件，刷到介质，改名覆盖，再读回；读回与收到的内容不一致就失败，旧文件保持不动。失败时临时文件删除。我们工作室 README 写明不往相机的卡上写任何东西。指南第 5.3 节仍要用户在终端生成 `GXRCE.DAT`，再自己备份、覆盖、关机再开。用法：工作室只在电脑上生成新的 `GXRCE.DAT`，页面上按顺序写出备份、复制、关机再开；若以后增加写卡，写路径采用他们的临时文件和读回。工作量中等，生成器 `firmware/engine_v46_ui/user_entries.py` 已经在指南里。风险：自动写卡会碰到我们自己的「不改卡」约定，所以这一步先停在电脑上的文件。推断：先消除终端，比先获得写卡权限划算。

**不可逆操作默认是取消。** 0.7.4 写回原厂前用红按钮，回车不会确认。0.8.7 的说明对更高版本固件加了黄字：刷入后不能降级。我们的恢复步骤写在指南 6.2，没有这样一个默认取消的确认。用法：任何会刷机身或覆盖 `GXRCE.DAT` 的界面，主按钮是取消，确认钮写明「我已备份 / 我知道要恢复出厂」。工作量小。风险低。

**第一次使用的引导钉在真实控件上，帮助按钮可重看。** `tour.tsx` 用 `data-tour` 照亮控件；控件不在页面上就跳过该步。我们的指南是一篇长文，工作室 README 是三步。用法：工作室用同样的方式把「插卡、导入、裁切、配方」做成可重看的四步，不要新写一套与界面脱节的手册。工作量中等。风险低。

**设置不兼容时改回已知值，而不是留一个旧固件不认识的编号。** 0.8.2 的设置保护：不认识的风格回到标准，不认识的比例回到 3:2，没有柔焦功能的 ADJ 槽把柔焦关掉。说明写这是为了避免刷回更少功能的固件后死机。我们的指南写过：用其它镜头刷过之后，50mm 曾经开不了机；关机后配方回到 04，微调不保留。用法：卡包标明适用的机身版本和镜头单元；换包或恢复官方前，说明里写清哪些相机设置会留下。若机身侧能在开机时把不认识的配方编号改回 04，就和他们的保护是同一类。工作量：说明是小；机身侧改编号要进现有的开机恢复设计，是中到大。风险：说明本身低；改开机路径属于刷机。

### 4.2 功能点子

**关机后仍停在上次的配方，微调还在。** 他们把新增槽位的参数放进相机会保存的设置，关机和 U1–U3 都能留。我们的指南 3.4 写明：关机再开回到 04 标准，调过的数值不保留，相机不记得上次的配方。用法：这是用户每天会碰到的差距。落点在机身开机恢复，不在工作室。工作量大，因为要改刷进机身的程序并上机。风险是刷机。推断：在这件事做完之前，工作室和指南都应该继续写明「关机即回 04」，避免用户按 GR 的习惯来预期。

**拟合更复杂的模型时，灰阶和肤色变差就不用。** 0.8.6 的色相区规则写在 README 的 `huePasses`：整体至少接近 2%，灰、近中性和肤色最多差一点点，才保留 12 扇区；`.xmp` 用拟合留出的三分之一颜色再查一次。说明称测试固件 064 上相机与模型差 0.5–0.8 ΔE00。用法：给我们现有的 LUT 拟合加同一条采用规则，并分开记录拟合误差和实拍误差。r1 已经要求把浮点、量化和实拍分开。工作量小到中，改工作室里的拟合和报告。风险低，只影响电脑上的候选，不改相机。不要把他们的 12 扇区 Q10 块写成 GXR 的表。

**光晕、柔焦、日期戳、65:24。** 光晕是 JPEG 编码前的一块位置无关 C（`tools/halation/halation.c`），红或白，强度三档，取景不显示，不改 RAW。柔焦经过三代：先改清晰度表，再占 ADJ 上一个原厂不用的功能号，取景同样不走这步。日期戳钩在 JPEG 编码上，七段橙字，可跟拍摄方向，可带风格名。65:24 是裁切列表，JPEG 变窄；README 写 GR III 保留完整 RAW，issue #20 对 0.8.7 提出相反报告。我们这边，日期戳、65:24 裁切和暗角已经在工作室里；机内宽幅有单独研究。机内柔焦若只是打开镜头单元已有的场景效果，比新写一块全画幅光晕更接近他们 0.4 的做法。工作量：工作室已有的保持现状；机内调用已有场景效果是中等；在 M32R 上新写全画幅光晕是大，而且他们自己写了取景不显示。风险：机内效果都要刷机或改单元。推断：光晕不该排在「关机记住配方」前面。

**菜单排序、隐藏，以及 20 个槽。** 排序在 GR IV 上是一张 20 字节的表，隐藏是把可见性跳转指到已有的「返回 0」桩，不增加菜单容量。20 个槽则是把风格表、名字、图标和参数存储都加长。我们的指南是 8 个配方加一行 MyRec。本仓库 [trend_ideas](../trend_ideas/REPORT.md) 记录过 DAT 自绘列表必须正好 8 行。用法：隐藏和排序要等列表长度不再被钉死之后再做。MyRec 已经是「卡上多条目、相机里查看」的路径，先把生成从终端里拿出来。工作量：生成器界面是中等；加长机内列表是大。风险：在 8 行约束还在时改行数，会碰到现有菜单。

**直闪。** 0.8.5 起 GR IV 的闪光模式多一项固定功率，用闪光指数、距离、背景压暗和快门上限一起算。设置在相机菜单里，不在电脑上。GXR 有内置闪光灯，曝光和同步速度不是这套地址。用法：只把「固定功率直闪」留在点子列表里，等我们自己的闪光参数研究有落点再做。工作量大。风险是刷机，而且他们的 C 模块不能编译进 M32R。

**预设改了以后，该槽位的微调回到中性，其它槽位不动。** 0.8.2 的指纹是这件事。我们的微调关机即失，所以现在没有「旧微调配上新预设」的问题。等微调能保存之后，再加指纹。工作量小，但是依附于上一件「能保存」。风险低。

### 4.3 工程做法

**公开版本只含一件用户能核对的变化，说明里写测试编号。** 他们用测试固件编号把「模型算过」和「相机见过」分开。0.7.3 写明必须重新写入才生效。用法：我们每份卡包的说明只列这次上机见过的行为；没见过的留在研究记录，不写进「你会看到」。工作量小。风险低。

**旧功能的输出用字节级测试钉住。** `gr4-unchanged` 和测试固件 017 的逐字节比较，使 GR III 的开发不会悄悄改掉 GR IV 的产物。用法：我们已有的包读回和场景测试继续担任这个角色；每加一个机身功能，留一份「其它功能组合的包哈希不变」的检查。工作量中等，接在现有测试上。风险低。

**上机前先跑原函数，并写明探针不是整机。** 他们的 Unicorn 脚本只覆盖菜单、设置字节和一块图像模块，文件头声明不模拟传感器、DMA 和开机。用法：我们继续用现有的宿主重放和本机探针做这一层，在报告里写清没覆盖开机和镜头单元。不能把 `tools/gr3x/*.py` 拿来跑 GXR。工作量是我们自己的探针，不是移植。风险：把函数级通过说成上机通过。他们的 issue #20 就是这种落差的例子。

**自动更新按固件能否降级分成通道。** 0.8.5 改版本号，是为了不让仍用 1.11 的用户自动装上只认 1.20 的程序。用法：如果我们以后发工作室安装包，更新通道要和机身包版本绑在一起，不能只看工作室版本号更大。工作量大，现在没有安装包。风险：通道分错会让用户生成一台相机不认识的卡包。

**issue 模板和 CI 不必向他们看齐。** 他们没有 Actions，也没有 issue 模板。工作室的 `CONTRIBUTING.md` 已经指向 `.github/ISSUE_TEMPLATE/` 和 `make check`。推断：我们缺的是面向用户的发布切片，不是再补一套他们没有的模板。

## 5. 能不能直接复用代码或数据

整仓许可以仓库为准，不是以 GitHub 侧栏的简称为准。

- [LICENSE](https://github.com/Maxwooow/Ricoh-GRMod/blob/1f4216e4b80d737a3e670c0b6169398f57598b5e/LICENSE) 是 GNU GPL 第 2 版正文。API 的检测结果是 `GPL-2.0`。
- README「Licence」和根目录、`core`、`ui` 的 `package.json` 都写 `GPL-2.0-only`：只此版本，不包含「或任何更高版本」。README 写明：交给别人的构建必须附上同一许可下的完整源码。
- 抽查到 SPDX 头的文件包括 `core/src/color/hue.ts`、`tools/halation/gen.py`、`tools/aspect/verify_file.py`、`tools/looks/looks_check.py`。`core/src/color/fit.ts` 和 `core/src/fw/container.ts` 开头没有 SPDX 行，项目级声明仍覆盖它们。
- `third_party/gr-custom-tool/NOTICE.md` 写明宽高比相关文件是 DoYitNow 作品的修改版，Copyright (C) 2026 DoYitNow，同样是 GPL-2.0-only，并按 GPL 第 2 版第 2 条 (a) 列出了改动。
- 明确不在代码许可内的：`ui/src/assets/preview.jpg`（README 写是 DPReview 样张，获 DPReview 许可，457,517 字节），以及理光固件（不在仓库里，下载即接受理光自己的协议）。
- `examples/gr3x/T6/README.md` 写 t3mujinpack 的 LUT 是 MIT，但 CUBE 和 PNG 没有放进仓库，只留了许可文本和下载脚本。CineStill 文件写明个人下载许可不等于可以再分发，所以没有打包。目录里实际有的 `Demo-Cool.cube` 和 `Demo-Warm.cube` 各 743 字节。本文没有把它们复制出来。

因此：

- 可以把他们的代码收进一个单独的 GPL-2.0-only 程序，保留版权声明、许可文本和修改记录，再分发时附上完整对应源码。
- 不能把 `fit.ts`、`hue.ts`、`halation.c`、宽高比编译器或 shell 的源码抄进工作室。工作室的 `pyproject.toml` 没有 `license` 字段，README 也没有把工作室标成 GPL-2.0-only。GPL-2.0-only 的派生作品不能混进一个未按同一许可发布的程序。推断：即使只抄拟合里的几十行，也会把工作室拖进「整个结合作品都要按 GPL-2.0-only 提供源码」。本文不建议为了这个拟合去改工作室的许可。
- 预览样张不能用。官方固件不能经由他们的发布再分发；他们自己也没有附带。
- 电脑端工具是有的，而且就是这个仓库的主体：导入 `.xmp` / `.cube`、拟合矩阵和曲线、预览、写卡、自更新。它不是一个可以单独抽出来、许可上干净的小库。预览和写卡都绑在 GR 的固件容器上。对我们工作室能用的是规则（灰阶和肤色门槛、读回哈希、说明文案），不是这套 TypeScript。

0.8.6 相对 r1 已读的 0.8.5，公开树上新增的颜色相关代码是 `core/src/color/hue.ts` 和 `hue-fit.ts` 这条色相区拟合。它仍是 GR 的 12 扇区、每个扇区 5 份 Q10 矩阵。GXR 的 24 扇区色相环不是这个数据结构。

## 6. 最值得马上做的 5 件事

按收益除以工作量排。都不要去移植他们的固件补丁。

1. **给下一份用户卡包写死版本页。** 包名、适用机身和镜头、SHA-256、这次在相机上见过的行为、刷完要关机再开、怎样退回官方 1.51。把指南里仍标「待确认」的安装画面留在研究记录，直到有人看见。收益高，因为现在的指南已经在被用户跟着做。工作量小。风险低。

2. **在工作室里生成 MyRec 的 `GXRCE.DAT`，不写存储卡。** 页面收清单，调用已有的 `user_entries.py`，输出到用户选的电脑目录，并按顺序显示：先备份卡上的原文件，再复制，再关机再开。收益高，指南 5.3 现在要求会用终端。工作量中等。风险低，只要不打破「工作室不写卡」。

3. **拟合候选增加灰阶和肤色门槛。** 更复杂的曲线或矩阵只有在整体更接近、灰阶和肤色不明显变差时才采用，报告里分开写拟合误差和实拍误差。收益高，能少做出一组只在高饱和色块上好看的配方。工作量小到中。风险低。实现用我们自己的代码。

4. **刷机或覆盖配方文件的确认，默认焦点放在取消。** 确认钮写明后果：不认识的设置、50mm 与其它镜头单元、电量。包上标明它对应哪一版机身。收益是少一次开不了机。工作量小，如果确认只做在说明和现有写卡脚本的提示里；做成图形按钮是中等。风险低。

5. **工作室里用四步可重看的引导，并在配方页写明关机回到 04。** 引导只覆盖已经能用的导入、裁切、配方和导出。关机不记住配方这件事继续写在引导里，直到机身恢复做完。收益是用户不再靠一篇长指南猜哪些已经能用。工作量中等。风险低。机身侧「记住上次的配方」收益也高，但工作量是一次刷机开发，不放进这五件。

先不做的：光晕模块、20 个机内槽、直闪公式、签名自更新、把他们的源码并进工作室。这些要么平台对不上，要么工作量集中在还没产品化的机身路径上。

## 7. 来源

API 读取时间 2026-11-01。树和提交以 `1f4216e4b80d737a3e670c0b6169398f57598b5e` 为准。

- 仓库：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod> ，页面 <https://github.com/Maxwooow/Ricoh-GRMod>
- 许可检测：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/license>
- Release 列表：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/releases?per_page=100> ，页面 <https://github.com/Maxwooow/Ricoh-GRMod/releases>
- 标签：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/tags?per_page=100>
- 提交：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/commits?per_page=100> 与 `page=2`
- 树：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/git/trees/main?recursive=1>
- 工作流：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/actions/workflows> （`total_count` 为 0）
- 贡献者：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/contributors?per_page=100>
- issue 与 pull request：<https://api.github.com/repos/Maxwooow/Ricoh-GRMod/issues?state=all&per_page=100>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/README.md>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/package.json>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/LICENSE>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/third_party/gr-custom-tool/NOTICE.md>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/shell/README.md>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/shell/go.mod>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/core/package.json>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/ui/package.json>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/ui/src/host.ts>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/ui/src/tour.tsx>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/core/src/color/fit.ts>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/core/src/color/hue.ts>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/core/src/fw/container.ts>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/core/vitest.config.ts>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/tools/aspect/verify_file.py>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/tools/halation/gen.py>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/tools/looks/looks_check.py>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/tools/gr3x/native_probe.py>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/tools/gr3x/disasm.py>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/docs/GR3X_HDF.md>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/examples/gr3x/T6/README.md>
- 原文：<https://raw.githubusercontent.com/Maxwooow/Ricoh-GRMod/1f4216e4b80d737a3e670c0b6169398f57598b5e/examples/gr3x/T6/LICENSE-t3mujinpack.txt>
- 各 Release 页面即上表链接。0.8.7 与 0.8.6 的标签对象都指向 `1f4216e4b80d737a3e670c0b6169398f57598b5e`。

本仓库对照读过：`README.md`、`docs/GXR_RECIPES_GUIDE.md`、`studio/README.md`、`studio/pyproject.toml`、`studio/CHANGELOG.md`、`studio/CONTRIBUTING.md`、`research/gr4_repos_review_r1/REPORT.md`、`research/trend_ideas/REPORT.md`。
