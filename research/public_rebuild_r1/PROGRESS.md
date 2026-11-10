# 公开复现准备

完成计数：5/5

已完成：五项都做完。`fetch_official.py --from` 用本地 zip 核对了 29 个成员，第二次运行复用缓存，没有下载。`patches/body-r5.json` 和 `patches/xpan-28mm.json` 经 `rebuild.py --audit` 重建后，与在用的 ilaunch3（`37fe29f0…`）和 qlaunch3（`aed12aee…`）逐字节相同。字面量里没有 12 字节以上的官方片段。颜色核对和 g180 回归的缺口写在 REPORT.md。`.gitignore` 只加了 `/research/public_rebuild_r1/cache/`。

当前步骤：没有进行中的计算。

下一步：机主决定是否提交补丁和 REPORT.md。`tools/public/` 仍被 `/tools/` 忽略，提交工具前要单独加例外。不要提交 `cache/` 和 `local/`。颜色核对还要先有一套不含照片登记的期望值。

怎么续跑：从仓库根执行下面三条。期望 SHA 和 `embedded_runs: 0` 见 REPORT.md 的作业说明。

```sh
nice -n 15 /usr/bin/python3 -I -B tools/public/fetch_official.py --from artifacts/downloads/gxr-151.zip
nice -n 15 /usr/bin/python3 -I -B tools/public/rebuild.py --patch research/public_rebuild_r1/patches/body-r5.json --audit --out research/public_rebuild_r1/local/rebuilt/body-r5
nice -n 15 /usr/bin/python3 -I -B tools/public/rebuild.py --patch research/public_rebuild_r1/patches/xpan-28mm.json --audit --out research/public_rebuild_r1/local/rebuilt/xpan-28mm
```
