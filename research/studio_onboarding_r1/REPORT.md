可以复审

首次打开会显示四步引导。跳过或走到「完成」之后，`onboarding_dismissed` 写成 true，下次不再自动打开。点窗口的 ✕ 不算跳过，下次仍会打开。顶栏「帮助」和设置里的「打开」都可以再看一遍。`?` 仍直接打开快捷键表。

配方页标题下固定一行，不随页面重画消失。导出面板的 HDR 第一次为关。用户勾上或取消后，选择写入 `export_hdr`，下次导出沿用。选中的照片都没有 RAW 时开关置灰，显示「HDR 需要 RAW 文件」，不会把记住的值改掉。

两项都在应用数据目录的 `prefs.json`。读不到或目录还不存在时用默认值，不建文件。写入走 `lut.library.durable_write`，也就是 `PrivateDir` 的原子替换。指向别处的符号链接不会被跟着读写。目录落在 Git 工作区里时拒绝写入。

## 新文案

第二步说明用了「裁剪」，没有用「裁切」，也去掉了「等」。术语表规定编辑动作用裁剪。

| 位置 | 文字 |
| --- | --- |
| 顶栏按钮 | 帮助 |
| 帮助菜单 | 帮助；快捷键；引导 |
| 引导标题 | 引导 |
| 第 1 步 | 插入存储卡；自动导入照片 |
| 第 2 步 | 在图库里浏览、编辑；裁剪、曝光、边框 |
| 第 3 步 | 用 LUT 库管理 LUT；套用到照片 |
| 第 4 步 | 导出；可选 HDR |
| 引导按钮 | 跳过；上一步；下一步；完成 |
| 设置 | 引导；打开 |
| 配方页 | 相机关机再开后，按 ADJ 再按 OK 套用上次的配方 |

HDR 开关和没有 RAW 时的说明沿用原来的「HDR」「HDR 需要 RAW 文件」。

## 检查

`make check` 退出码 0。pytest 949 passed，覆盖率 92.60%，门槛 85%。`prefs.py` 和 `prefs_routes.py` 都是 100%。命令行仍带 Makefile 里的 `--reruns 1`，同时用了 `--force-reruns 0`，失败项不会再跑一次。输出里没有 RERUN，949 个都是第一次通过。耗时 686.72 秒。界面测试用 Node 自带能力，没有 macOS 专用接口。

没有提交。临时目录 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-onboarding` 已删除。

## 改动

哈希在同目录的 `SHA256SUMS`，路径相对项目根。

- `studio/src/gxr_studio/prefs.py`：读写 `prefs.json`
- `studio/src/gxr_studio/api/prefs_routes.py`：`GET` / `PUT /api/prefs`
- `studio/src/gxr_studio/app.py`：挂上这个路由
- `studio/web/assets/onboarding.js`：四步引导、帮助菜单、设置里的入口
- `studio/web/assets/app.js`：启动时读取偏好，帮助按钮打开菜单
- `studio/web/assets/state.js`：`prefs`
- `studio/web/index.html`：帮助按钮
- `studio/web/assets/export.js`：记住 HDR
- `studio/web/assets/lut.js`：配方页固定提示
- `studio/docs/architecture.md`、`studio/docs/privacy.md`、`studio/docs/openapi.json`
- `studio/tests/test_prefs.py`
- `studio/tests/test_onboarding_ui.py`
- `studio/tests/support/ui_scene.mjs`
