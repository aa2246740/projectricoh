# 第二阶段实现计划

第一阶段没有改 `studio/`。下面是编排者放行之后要动的后端。前端仍由另一位改 `studio/web/`；这里只写后端必须交出去的行为和文件。

原型在 `proto/`。`geometry.py` 是纠正和内接矩形，`auto_lines.py` 是自动拉直/垂直，`frames.py` 是六种边框和时间戳。效果图由 `make_sheet.py` 写到 `proto/out/`，`proto/index.html` 并排查看。素材在 `assets/`，说明在 `assets/SOURCES.md`。

## 渲染顺序

和 PRD 第 6 节同一条，预览和导出都走它，只是预览把长边限制在 1600 左右：

配方（有 RAW 才走相机链；只有 JPG 时走下面的近似 LUT 或跳过）→ 调节和曲线 → 畸变 → 垂直/水平透视 → 拉直 → 旋转 90° / 左右翻转 → 裁切 → 时间戳（画在照片内）→ 边框（加在照片外）→ sRGB JPEG。

有 RAW 时，调节仍加在线性码值上（现有 `tones.channel_gains` / `display_table`），几何在 8 位图之后做，和现在 `crop_image` 的位置一样。只有 JPG 时，调节改在线性 sRGB 上做同一套公式，不进 RAW 链。

`/api/photos/{id}/preview` 和缩略图继续表示“相机原来的样子”，不偷偷换成成片。裁切标签现在把裁切框叠在这张图上，改掉它会把框套错。成片用新的 `stage=final`。图库缩略图要另开一个变体，把成片缩小，链接带上 sidecar 的 `rev`，这样 immutable 缓存不会粘住旧图。

## 要改的文件

新增，从原型搬进去，不在运行时 import `research/`：

- `studio/src/gxr_studio/finish/geometry.py`：畸变、透视、拉直、旋转、翻转，以及固定比例的最大内接矩形。拉直正方向保持 `crop.affine_coeffs` 的顺时针。
- `studio/src/gxr_studio/finish/frame.py`：六种边框。画廊边宽 = 照片长边 × 2% / 4% / 7%。
- `studio/src/gxr_studio/finish/stamp.py`：时间戳画在照片内部。
- `studio/src/gxr_studio/finish/auto_lines.py`：numpy 霍夫，不加入 OpenCV。
- `studio/src/gxr_studio/finish/approx.py`：八个底子的显示域 LUT。JPG 上 `capabilities.recipe = "approx"`。旋钮不进表。
- `studio/src/gxr_studio/assets/`：从 `research/studio_v2/backend/assets/` 拷贝要用的那四款字体、许可证和 `logo/ricoh.png`。SVG 原件留在 research，仓库里的 PNG 是我们栅格化的。

修改：

- `render/service.py`：预览和导出共用上面的顺序。没有 DNG 时不再在调整之前抛 `NoRaw`；只有“要跑 RAW 配方链”才抛。缓存键补上 geometry、frame、stamp、近似 LUT 的 id，以及 JPEG quality。
- `render/params.py`、`render/edits.py`：读写真的 `geometry` / `frame` / `stamp`，以及 `adjust` 里的 `black_point`、`saturation`、`vibrance`、`vignette`。
- `render/tones.py`：黑点、饱和度、自然饱和度、暗角。高光/阴影的正方向先保持现在的“正值变亮”，见 `CONTRACT_REQUESTS.md`。
- `api/render_routes.py`：`PUT /edit` 接受新块；`GET/POST /render` 增加 `stage=final|uncropped`。`final` 含裁切、时间戳、边框。`uncropped` 只做颜色和纠正，给裁切标签叠框。旧的 `crop=true` 继续可用，等于在 final 之前的那一步裁切。
- 新路由，都在 `api/render_routes.py`（或同目录一个新文件，由 `app.py` 挂上）：`POST /geometry/auto`、`GET /frames`、`GET /photos/{id}/meta`、`GET/PUT /defaults/finish`、`GET /photos/{id}/capabilities`。错误仍走 `api/errors.py`。
- `library/sidecar.py`：认这些可选键；缺省就是不启用。schema 字符串先不升，避免旧程序把文件当成“太新”而只读。升 schema 要等确认没有旧构建还在写同一图库。
- `library/thumbs.py`：成片缩略图用带 `rev` 的变体。原来的 JPG 缩略图保留给“看相机原图”。
- `crop.py`：`MAX_ANGLE` 从 10 改到 45。内接检查改走 `finish/geometry.py`，透视和畸变之后的框也要收进有效区域。
- `export.py`：导出走同一条成片管线，不再只在 RAW 渲染之后套旧的 `crop_image`。
- `meta.py`：给边框和时间戳读镜头、光圈、快门、ISO、拍摄时间。缺的字段返回 null，边框不印空字。
- `docs/openapi.json`：把新路由和 sidecar 字段补上。
- `pyproject.toml` / `uv.lock`：不改。没有新依赖。

不改 `engine/` 和 `lut/spaces.py`。这两处要和 `PROVENANCE.json` 逐字节一致。

`studio/web/` 不在这次的写入范围。前端要改的点已经记在 `DIAG.md`：大图在非裁切标签时用 `stage=final`，裁切标签用 `stage=uncropped` 再叠框；只有 JPG 时按 `capabilities` 把配方旋钮置灰或标“近似”。

## sidecar：`crop.angle_deg` 和 `geometry.straighten`

两个键是同一个角度。

- 读：有 `geometry.straighten` 就用它；否则用 `crop.angle_deg`；都没有就是 0。
- 两者都在、差超过 0.05°：以 `geometry.straighten` 为准，下次保存时把 `angle_deg` 改成同一个数。不拒绝打开这张照片。
- 写：只要拉直不是 0，或者以前已经有其中任何一个键，就两个都写。范围 −45..+45，步长在界面是 0.1，存储用浮点。
- 旧的 ±10° 文件不用迁移脚本。读的时候就能用。
- `rotate90`、`flip`、透视、畸变只写在 `geometry` 里。旧文件没有这些键，就当作 0 和 false。

## 接口

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| PUT | `/api/photos/{id}/edit` | 原有 `recipe` / `adjust` / `curve` 不变。多出来的 `geometry`、`frame`、`stamp` 和四个新调整键，出现才改，`null` 表示清掉这一块。仍要 `expected_rev`。 |
| GET | `/api/photos/{id}/render?stage=final` | 成片。`stage=uncropped` 给裁切标签。默认 `final`，避免再有人拿到一张没裁的图当成结果。 |
| POST | `/api/photos/{id}/geometry/auto` | `{"straighten": x, "vertical": y, "confident": bool}`。没把握时两个数都是 0、`confident` 为 false。水平透视不猜。 |
| GET | `/api/frames` | 六种样式、默认底色和粗细、每种能调的项。 |
| GET | `/api/photos/{id}/meta` | 镜头、光圈、快门、ISO、拍摄时间。没有就是 null。没有 EXIF 时间时再给文件时间，并带 `date_source`。 |
| GET/PUT | `/api/defaults/finish` | 新照片和批量导出用的默认边框、时间戳。存在应用数据目录，不写进某一张 sidecar。 |
| GET | `/api/photos/{id}/capabilities` | `raw`，以及 `recipe` 为 `full` / `approx` / `none`。`approx` 的 `reason` 用“近似（这张没有 RAW）”。八个底子的表还没烤好、或者留出测试不过线时，返回 `none`，`reason` 写“这张只有 JPG，配方需要 RAW（DNG）。拍的时候把画质设成 RAW+JPEG”。 |

只有 JPG、又在请求里点了不在近似表里的旋钮：422，不悄悄画成标准。

## 测试

加在 `studio/tests/`，不降低现有 398 个测试和覆盖率 85% 的线。

- 有 DNG 的夹具上，八个配方相对标准的平均 ΔE00 ≥ 2，黑白色度接近 0。调整两端的方向用和 `DIAG.md` 同一套判断。
- 只有 JPG 的夹具：曝光 +2 必须改变像素；配方底子要么走近似并在头里标明，要么 `capabilities.recipe=none` 且渲染不报 500。
- 几何：旋转、透视、畸变之后，内接矩形的每个像素都有效；再高 2 像素的同比例矩形放不进去。旧的 `angle_deg=8` 仍能读，写回时 `geometry.straighten` 同时是 8。
- 边框：3:2、1:1、65:24 的画廊白边，边宽 / 成片长边的差在 0.4 个百分点以内。时间戳落在照片矩形内，边框在照片外。
- 自动：合成的已知倾斜能回到 1° 和大约 10 个滑块刻度以内；没有线的图 `confident=false`。
- 缓存：改 `rev` 或 quality 后不能命中上一张的 ETag。缩略图链接带 `rev`。
- `mypy --strict` 给新模块写全注解。`engine/` 的 provenance 测试继续通过。

## 风险

- 另一位正在给 `studio/src` 和 `studio/tests` 补类型。第二阶段开始前要以他交回来的树为准，避免两边改同一段 `render/service.py`。
- 成片预览比现在多几次重采样。半分辨率配方本身是 146 ms，几何和边框应该还在 1.5 秒里；全分辨率导出要单独看，不能在请求线程里做。
- 近似 LUT 只在两张同一天的 ISO 800 上量过。第二阶段要用色卡和另一档 ISO 再留出一次，不过线就改回 `none`，不要把 2 ΔE 写进发布说明。
- 高光正方向和苹果相册相反。没收到合同改动之前保持现状，避免界面和导出各拧一次。
- 字体和标志进 `studio/` 之后体积要留在 3 MB 以内，许可证文件跟着走。CI 机器上用 Pillow 读这些 TTF，不调用系统的 `rsvg-convert`。
