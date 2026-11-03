# 改动清单（studio，基于 cb23e70，未提交）

## 新增

- `studio/src/gxr_studio/hdr/__init__.py`（10 行）
- `studio/src/gxr_studio/hdr/container.py`（234 行）
- `studio/src/gxr_studio/hdr/gain.py`（321 行）
- `studio/src/gxr_studio/hdr/derived.py`（152 行）
- `studio/src/gxr_studio/finish/hdr_export.py`（143 行）
- `studio/tests/test_hdr.py`（544 行）
- `studio/tests/hdr_support.py`（280 行）
- `studio/tests/support/check_imageio.swift`（127 行）

## 修改

- `studio/docs/architecture.md`（+3 −0）
- `studio/docs/feature-flags.md`（+1 −0）
- `studio/docs/openapi.json`（+32 −0）
- `studio/docs/privacy.md`（+2 −0）
- `studio/pyproject.toml`（+2 −0）
- `studio/src/gxr_studio/api/routes.py`（+25 −1）
- `studio/src/gxr_studio/app.py`（+1 −0）
- `studio/src/gxr_studio/export.py`（+2 −0）
- `studio/src/gxr_studio/finish/compose.py`（+10 −0）
- `studio/src/gxr_studio/finish/geometry.py`（+33 −14）
- `studio/src/gxr_studio/finish/serve.py`（+20 −2）
- `studio/src/gxr_studio/flags.py`（+6 −0）
- `studio/src/gxr_studio/library/location.py`（+1 −0）
- `studio/src/gxr_studio/library/store.py`（+1 −1）
- `studio/web/assets/export.js`（+35 −1）

## 各处做了什么

- `hdr/container.py`：从原型移植 JPEG 段结构、XMP（hdrgm + Container）、ISO 21496-1、MPF 和 `assemble`。段扫描能跳过渐进式扫描之间的段；JPEG 坏了抛 `ContainerError`。
- `hdr/gain.py`：RAW 亮度（工作室的 `raw.half_res_codes`）、对齐、对齐门槛（相关系数 ≥ 0.5、平移 ≤ 2%、4×4 分块）、曲线拟合、增益计算、`hdr_from_camera_jpeg`。
- `hdr/derived.py`：`.studio/hdr/<前两位>/<id>-v1.jpg|.json`；`Library.check_write` 加 `privacy.PrivateDir` 写入；后台任务 `run_pending`。
- `finish/hdr_export.py`：`HdrTrack`，RAW 亮度层跟着几何、裁剪、日期戳、边框走；`finish` 在导出的 JPEG 上算增益并封装。
- `finish/geometry.py`：抽出 `_straighten_coords`（RGB 和数据层共用），新增 `warp_float`。
- `finish/compose.py`：`finish_array` 增加可选参数 `track`，每个几何步骤后面跟一行。
- `finish/serve.py`：`render_stage(track=…)`，底图一定下来就 `track.begin`；`export_finish(hdr=…)` 写 EXIF 之后封装。
- `export.py`：`ExportResult` 加 `hdr` 和 `hdr_reason`。
- `api/routes.py`：`ExportRequest.hdr`；`ExportFile.hdr` 和 `hdr_note`（含 `HDR_NOTES` 文案）；导入任务结束后调用 `start_hdr_job`；照片 JSON 加 `hdr` 状态。
- `app.py`：`Context.hdr_lock`。
- `flags.py`、`docs/feature-flags.md`：新开关 `hdr_on_import`（默认开）。
- `library/location.py`：启动核对加 `.studio/hdr`。`library/store.py` 只改了说明。
- `pyproject.toml`：import-linter 的两条约束加上 `gxr_studio.hdr`。
- `docs/architecture.md`、`docs/privacy.md`：HDR 派生文件的位置和写入方式。`docs/openapi.json` 由 `make openapi` 重新生成。
- `web/assets/export.js`：导出面板的"HDR"开关、置灰原因、单张和批量结果里的说明。
- `tests/hdr_support.py`：合成的 RAW+JPG、独立写的文件检查、ImageIO 对照。`tests/support/check_imageio.swift` 是原型原样，只改了第一行注释。
