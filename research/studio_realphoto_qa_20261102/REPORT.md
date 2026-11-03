第 152 代相机配方文件进不去，10 个新风格在界面里没有名字。照片本身导入、配对、裁剪、加边、导出都走通了，同一张卡再导一次没有多出文件。

严重程度：P1 一条，P2 三条，P3 三条。

## 环境

工作室仓库 `studio/` 的提交是 `e73a7af474e137b26862f252da0a8ad58b5d3793`（e73a7af，Add a re-viewable first-run guide…）。磁盘 `/Volumes/Workspace` 是 APFS、可写，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，当时大约还剩 1.0 TiB。

单实例锁在图库目录 `.studio/studio.lock` 上，跟着 `GXR_STUDIO_LIBRARY` 走，不跟着 `GXR_STUDIO_HOME`。所以独立图库可以再开一份，没有动主人正在跑的 `127.0.0.1:49667`，也没有读 `/Volumes/RICOHDCX`。

启动命令在 `studio/` 里：

```bash
PYTHONDONTWRITEBYTECODE=1 \
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-realphoto-qa-r1/tmp \
GXR_STUDIO_VOLUMES=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-realphoto-qa-r1/volumes \
GXR_STUDIO_LIBRARY=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-realphoto-qa-r1/library \
GXR_STUDIO_EXPORT=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-realphoto-qa-r1/export \
GXR_STUDIO_HOME=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-realphoto-qa-r1/home \
GXR_STUDIO_TOKEN=qa-r1-local-only \
uv run --frozen --offline --no-sync gxr-studio --no-browser --port 0
```

没有设置 `GXR_STUDIO_SENTRY_DSN`。第一轮页面是 `http://127.0.0.1:60169/`，补测是 `http://127.0.0.1:62551/`。浏览器是仓库复审一直用的固定 Playwright 1.61.1、Chromium headless shell revision 1228，用户数据目录在上述 scratch 的 `tmp/` 里。走完后进程已退出，没有留下 `code_sign_clone` 目录。scratch 在写完这份报告后删除。

假卡是 `volumes/FAKECARD`。`DCIM/100RICOH` 里是 152 对相机原片：街拍 R8051707–R8051838 共 132 对，MOUNT 目录里的 R8051691–R8051706 共 16 对，今晚 R8051839–R8051842 共 4 对。`sheet.jpg` 和 `view/` 里那些几十 KB 的小图没有放进去。HDR 样本的相机原片 R8051627 放在 `DCIM/101RICOH`，Downloads 里已有的 `*_HDR.JPG` 只留在 scratch 里当对照，没有当照片导入。卡根是第 152 代 `GXRCE.DAT`，90384 字节。一共 153 张、306 个文件。

## 覆盖

| 流程 | 结果 | 说明 |
|---|---|---|
| 首次引导，并从卡导入第 152 代配方 | 完成 | 四步引导可以走完。导入配方被拒绝，10 个新风格没有出现。 |
| 导入假卡上的全部照片 | 完成 | 153 张全部进图库，横幅写「已导入 153 张照片」，状态栏「存储卡：可以推出」。 |
| 日期、RAW+JPEG 配对、镜头 | 部分 | 日期和配对是对的。153 张镜头字符串都是「GXR MOUNT A12」，分不出 50mm 和 MOUNT。 |
| 浏览并编辑 | 部分 | 打开了多张街拍、一张 MOUNT、一张今晚的照片。曝光、曲线、XPan 65:24、白边、时间戳、LUT 库都用过。八个内置配方是灰的，点不下去。 |
| HDR | 完成 | R8051627 导出的 JPEG 能打开，并且带增益图。另外抽了一张后台记为对不齐的街拍，导出退回普通 JPEG。 |
| 导出 JPEG | 完成 | 编辑过的 R8051707 导出为 4632×1927，sips 能打开。 |
| 再次导入同一张卡 | 完成 | 横幅「这张存储卡上的照片都已导入」，新导入 0 张，图库仍是 306 个文件。 |
| 界面用词 | 完成 | 不对的句子写在下面的发现里。 |

## 发现

| 级别 | 现象 | 怎么重现 | 预期 | 实际 | 证据 |
|---|---|---|---|---|---|
| P1 | 第 152 代配方文件无法导入，10 个新风格没有入口 | 假卡根放着这份 GXRCE.DAT。打开设置，点「从存储卡导入配方」。再到任意 RAW+JPEG 的「配方」页，看内置配方的八个名字。 | 第 152 代能导入。MANIFEST 里的 10 个名字（M9 STD、HNCS HiCon、Tri-X 400、Portra 400、Velvia 50、Kodachrome25、HNCS LowSat、Vision3 500T、instax mini、Metropolis）至少有一处能看到。 | 设置里立刻写「不支持第 152 代相机配方文件。请使用第 127 代或更新的版本。」状态仍是未导入。配方页只有原来的 8 个：GR 正片、GR 负片、高反差黑白、标准、富士 CC、富士 CN、徕卡 Chrome、徕卡 Vivid。上面 10 个名字一个都没有。提示让人去用「第 127 代或更新」，但这份文件本身就是更新的一代。 | `camdata-import.png`，`recipe-disabled.png` |
| P2 | 配方页把两件不相干的事说成了原因 | 配方文件导入失败之后，打开任意一张带 RAW+JPEG 角标的照片，看右侧「配方」。 | 说明这份配方文件的代数不被接受。照片已经是 RAW+JPEG，就不要再叫人改画质。卡上有 GXRCE.DAT，就不要说卡上没有这个文件。 | 同一块面板写着「存储卡上没有相机配方文件（GXRCE.DAT）」，下面又写「配方需要 RAW 文件」和「拍摄时将画质设为 RAW+JPEG」。八个按钮是灰的。照片顶栏的角标同时是 RAW+JPEG。 | `fail-套用内置配方.png`，`recipe-disabled.png` |
| P2 | 50mm 和 MOUNT 在这批照片里认成同一个镜头 | 导入后看图库接口里的 lens/unit，再打开街拍、MOUNT 目录里的照片和今晚的 R8051839。 | 50mm 和 MOUNT 能分开，大图上能看出这张用的是哪一个单元。 | 153 张 JPEG 的焦距都是 0，LensModel 都是空的，机身型号都是「GXR MOUNT A12」。工作室把这条型号当成镜头，unit 为空。大图顶栏只有文件名、时间和 RAW+JPEG，没有镜头。因为字符串里有 mount，配方页一律挂「未校准」。文件里前 2MB 也没有 50mm、28mm 或 GR LENS 这些字，所以不是界面把已经读到的焦距藏起来了。 | `qa-results.json` 的 byLens，`qa2-results.json` 的 bar |
| P2 | 有 23 张做不了 HDR，导出时只说不支持 | 导入结束后图库 `.studio/hdr/` 里有 130 个带增益图的 JPEG 和 23 个原因文件。打开其中一张，例如 R8051712，导出时打开 HDR。再对 R8051627 做同样的操作。 | 做不了的照片在图库里就能看出来，导出时说明是对不齐，而不是只给一句不支持。能做的那张导出文件能打开，并且带增益图。 | R8051627 导出成功，4.7 秒，4288×2848，文件里有 hdrgm 和 GainMap，sips 能打开。R8051712 也导出了一张普通 JPEG，下面多一行「这张照片不支持 HDR」，文件里没有增益图。23 张的原因文件都是 `not_aligned`，都是街拍：R8051712、R8051714–R8051718、R8051760、R8051764、R8051772、R8051778、R8051796、R8051803、R8051804、R8051806、R8051809、R8051810、R8051812、R8051813、R8051819、R8051820、R8051835、R8051837、R8051838。图库网格上看不出哪一张做不了。 | `hdr-unaligned.png`，`qa2-results.json` |
| P3 | HDR 做成了，结果里不说这是 HDR | 在 R8051627 的导出页打开 HDR 再导出。 | 结果里能看出这张带增益图。 | 成功时只写「已导出 1 张」、路径和尺寸。失败的那张反而有一句「这张照片不支持 HDR」。 | `qa2-results.json` 的 hdrSample |
| P3 | 第一次引导没有提到配方文件 | 清空应用数据后打开首页，把四步点完。 | 四步能看懂接下来要做什么。套配方还要另导入 GXRCE.DAT，引导里最好有一句。 | 四步是「插入存储卡 / 自动导入照片」「在图库里浏览、编辑 / 裁剪、曝光、边框」「用 LUT 库管理 LUT / 套用到照片」「导出 / 可选 HDR」。句子本身清楚，但走完也不会知道要先导入相机配方文件。 | `guide-1.png` |
| P3 | 「存储为我的配方」和「写入存储卡」一直是灰的 | 打开任意照片的配方页，看底部两个按钮。 | 现在做不到的动作，旁边有一句原因。 | 两个按钮都不可点。「写入存储卡」只有鼠标悬停才有「暂不支持写入存储卡」。「存储为我的配方」没有说明。 | `recipe-disabled.png` |

设置里的图库路径会在文件夹名中间断开，例如 `studio-realphoto-qa-` 下一行才是 `r1/library`。不影响使用。日期没有问题：侧栏是 2026-11-02 共 4 张（今晚的四对）、2026-11-01 共 148 张（132 张街拍加 16 张 MOUNT）、2026-10-31 共 1 张（HDR 样本），加起来 153。主网格默认标题是「全部照片」，日期要点左边的按钮才筛选。153 张全部带 RAW+JPEG 角标，没有只剩一半的。

套 LUT 时角标变成「电脑预测」和「未校准」。当时相机配方文件并没有导入成功，这个「电脑预测」容易让人以为内置配方已经在起作用。LUT 本身是后加进库里的 Portra 400，不是相机里的那个 Portra 效果。

## 用时

导入从页面打开、状态还是「正在导入 0/0」算起，到「可以推出」并且 153 张缩略图都在，大约 24 秒。任务结果是复制了 306 个文件、3,504,116,452 字节，没有读失败的文件。

再次导入同一张卡用了 7.4 秒。`imported_shots` 是 0，`duplicate_shots` 是 153，`copied_files` 是 0。图库里的 JPEG/DNG 仍是 306 个，没有 `modified-` 或带短哈希的重名文件。

出图是渲染请求回到 200 的时间。R8051773 是 379ms，R8051838 是 247ms，都是还没改过的街拍。已经裁过、加过白边和时间戳的 R8051707 是 1795ms。同一张上继续改：曝光到预览停下来 712ms，曲线 822ms，白边 967ms，时间戳 1172ms。XPan 65:24 点下去之后，裁剪页仍显示未裁切的 4288×2848；离开裁剪、加上白边之后成片变成 4632×1927，导出文件是同一尺寸。

把 LUT 库里的 Portra 400 套到 R8051770 上，成片停下来用了 8.6 秒。导出编辑过的 R8051707 用了 1.9 秒，文件 2.1 MB，sips 打开为 JPEG。导出 R8051627 的 HDR 用了 4.7 秒。导出对不齐的 R8051712 用了 1.8 秒，得到的是没有增益图的普通 JPEG。

## 这次没测到

八个内置配方没有真正套到 RAW 上。按钮是灰的，强制点下去画面和文字都不变。颜色标定也没导，因为界面要求先有相机配方文件。

10 个新风格除了「没有出现」之外，没有别的界面可以点。配方页里能看到的「Portra 400」是这次亲手导入的 LUT 文件名，不是相机配方文件里的那一条。

这 153 张 JPEG 自己没有焦距和镜头型号，工作室也就没有第二处可显示的 50mm 字样。真卡、主人的图库和 `127.0.0.1:49667` 按约定没有碰。
