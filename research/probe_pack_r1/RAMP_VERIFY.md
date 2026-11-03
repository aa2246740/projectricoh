# 下一轮拍摄页已准备

沿用现有 a30675fa，共拍 8 组 RAW＋JPG。打开 [ramp.html](ramp.html)，照 [OWNER_STEPS_RAMP.md](OWNER_STEPS_RAMP.md) 一次拍完。页面、说明和自检都是新增文件，旧页及封存报告未改。

49 级灰阶由 45 个密集灰码和 4 个边界灰码组成。密集区为 118–224，相邻差 2 或 3；边界为 48、96、240、254。另保留旧页的天空蓝、肤色和绿叶。中央图板最多 640×468 CSS 像素，缩放只适配窗口，不把图板铺满大屏幕。四角各有一个独特黑白编码，标签在色面下方，中央 50% 留给取样。

灰码由午休 R8051902 的 1/15 A，以及上午六张 1/30 A 的中位值反推。按通道把三个已测灰码做单调 PCHIP 插值；上午分支按两倍曝光投影到 1/15。取两组各通道节点 16 支持区间的屏幕码并集，再向两端各留 16 个屏幕码。这里的 PCHIP 只用于估计屏幕灰码与 RAW 的关系，不是认定硬件曲线使用 PCHIP。

| 输入依据 | 通道 | 预测上升侧点数 | 预测下降侧点数 |
| --- | --- | ---: | ---: |
| 午休实测 1/15 | R | 7 | 9 |
| 午休实测 1/15 | G | 5 | 8 |
| 午休实测 1/15 | B | 5 | 8 |
| 上午投影 1/15 | R | 5 | 8 |
| 上午投影 1/15 | G | 5 | 7 |
| 上午投影 1/15 | B | 5 | 6 |

这些是拍前预测，完整输入、拟合与逐灰级结果保存在 [plan.json](local/ramp/plan.json)。目标支持区间的反解都落在历史测量的屏幕码范围内；高于 208 的预测是外推。屏幕照明环境、新页面布局、实际镜头与光圈仍会改变 RAW。尤其 f/5.6 备用值没有已知曝光基准，不能保证覆盖。机主按固定 1/15 拍完，我们再用第一张 A 的 RAW 检查；相机直方图和高光闪烁不能代替这个检查。

验证使用固定 Playwright 1.61.1、Chromium Headless Shell 1228，直接打开 file://，串行运行，nice 10。9 种窗口与状态均通过，包括 864×900、900×650、800×600、720×450、1440×900 和 390×844。普通显示与拍摄显示都检查了整组可见、无滚动、标签不压中央取样区、52 个色块色值准确及四角完整。可选全屏、空格和 Esc 也通过。

逐像素复核 468 个中央取样区，均为准确的指定 RGB；独立从截图识别 36 个角标，均成功。角标所有旋转编码的最小汉明距离为 4。真实拍摄下的透视、离焦和摩尔纹尚未验证，四角仍须完整拍进原图。

查看 [半屏普通显示截图](local/ramp/browser/864x900-normal.png) 和 [小窗口拍摄截图](local/ramp/browser/720x450-capture.png)。机器回执为 [浏览器检查](local/ramp/browser/check.json)、[像素与角标检查](local/ramp/pixels.json) 和 [相对定位坐标](local/ramp/browser/layout.json)。设计扫描在三个尺寸下均无布局缺陷；其“Wireframe look”提示来自灰阶页低彩色面积，保留测量布局。

本地重跑，先核对封存文件，再依次运行自检。在项目根目录逐条运行，等上一条退出后再运行下一条。不需联网或启动 Studio：

```sh
nice -n 10 shasum -a 256 -c research/probe_pack_r1/RAMP.SHA256SUMS
nice -n 10 shasum -a 256 -c research/probe_pack_r1/local/ramp/SHA256SUMS
nice -n 10 env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 studio/.venv/bin/python -I -B research/probe_pack_r1/ramp_plan.py
nice -n 10 node research/probe_pack_r1/verify_ramp.mjs
nice -n 10 env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 studio/.venv/bin/python -I -B research/probe_pack_r1/ramp_pixels.py
```

`ramp_plan.py` 需要现有 NumPy／SciPy，`ramp_pixels.py` 另需 Pillow，复用已有环境。`verify_ramp.mjs` 是页面自检入口，只用全局固定无头运行时；版本不符会停止。它会正常关闭浏览器，删除自己在指定 Scratch 下创建的 profile。重跑会更新 local 回执，尤其随机临时目录名会改变；重跑后封存回执的哈希需重新生成。

全部原有文件的保全清单及本轮输入哈希放在 local/ramp。校验清单为 [RAMP.SHA256SUMS](RAMP.SHA256SUMS)，其中也包含 local 证据清单的哈希。临时目录清理与原有文件核对见 [closure.json](local/ramp/closure.json)。
