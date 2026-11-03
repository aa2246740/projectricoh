本轮使用 Mac 上已有的离线 Python 环境，没有安装依赖。所有 Python 入口均使用 `python3 -I -B`，子进程沿用同一个解释器。

| 项目 | 本轮版本 |
|---|---|
| Python | 3.14.7 |
| NumPy | 2.4.3 |
| SciPy | 1.17.1 |
| Pillow | 12.2.0 |
| imagecodecs | 2026.5.10 |

矩阵与优化使用单线程数值库设置。复现时需要已有这些依赖的 `python3`；系统 `/usr/bin/python3` 未带 NumPy，不是本轮解释器。

完整固定流程已复跑。对真实 GR IV 照片的验证，全部阶段的整页留出输出与首次输出逐项相同。比较记录在 `local/repeat_consistency.json`。实际 CLI 输入与输出归档检查在 `local/renderer_verification.json`；它是电脑预测渲染检查，不代表相机验收。
