验收修订 2 的后端项已复验，逐条结论在文末「验收修订 2」。本机 `make check` 487 passed，覆盖率 91.40%。无私有夹具的 `portable_check.py` 退出码 0，覆盖率 87.65%。

## 完成项

数码管撇号不再用缺字方块，也不再用一块竖的矩形。`'` 画成右上到左下的斜撇。默认格式 `'26 10 23` 的样图在 `research/studio_v2/backend/final/stamp-apostrophe.jpg`。

徕卡水印右边固定两行，都靠右缘对齐，竖线紧挨文字块左边。日期跟在光圈、快门、ISO 后面，不再因为多出第三行被丢掉。样图是 `final/leica.jpg`。其余边框和几何样图也在这个目录，源图是 `R8051219.JPG`。

`.github/workflows/error-issue.yml` 的 `gh issue create` 带有 `--repo "$GITHUB_REPOSITORY"`。

导出文件名是 `<原名>_gxr.jpg`，重名加 `-2`、`-3`。文件名里没有「电脑预测」「未校准」「近似」。这三样写进 EXIF ImageDescription，Pillow 以 UTF-8 字节写入。`_近似` 后缀已取消。中性转换仍用原来的 `_neutral`，第 3.9 节没有取消它。

JPG 近似配方的留出用色卡 `R8051148`（ISO 500），对照同一张 RAW 的配方成片。八个内置配方的平均 ΔE00 是 5.179，超过 3。各槽：01 为 2.881，02 为 6.542，03 为 12.291，04 为 3.289，05 为 4.595，06 为 5.678，07 为 3.292，08 为 2.868。`finish/approx.py` 的 `ENABLED` 为 False，`/capabilities` 的 `recipe` 返回 `none`。

## 测试命令和结果

本机 `make check` 没有通过。`ruff check` 通过。`ruff format --check` 只报 `tests/test_web_frontend.py`。排除 `tests/test_web_*.py` 之后，`ruff format --check` 通过。`mypy` 通过。`scan_secrets`、`bandit`、`dead_flags`、`check_agents_md`、`large_files`、`export_openapi.py --check`、`lint-imports`、`deptry`、`vulture`、pylint 重复代码都通过。

全量 pytest：

```bash
uv run --frozen pytest -q --durations=15 --reruns 1 --cov=gxr_studio --cov-report=term:skip-covered --cov-fail-under=85 --basetemp="$TMPDIR/pytest-full"
```

448 passed，4 failed，覆盖率 87.11%。4 个失败里，`tests/test_import_summary.py` 的两处是前端文案已经改成「已导入 14 张」和角标「电脑预测」，断言已跟上，单独再跑这一个文件 13 passed。剩下两个归前端，没有改：

- `tests/test_web_m2_smoke.py` 还在找「再点一次：全部归零」
- `tests/test_web_smoke.py` 还在找页面标题「GXR 电脑工作室」

干净克隆放在临时目录，旁边没有 `captures/`。`make check` 退出码 2，同样只卡在 `tests/test_web_frontend.py` 的 format。`make dast` 退出码 0，25 passed。临时目录峰值约 3.3 GB，克隆和 pytest 临时目录已删。

## 还开着的问题

前面说的 ruff format 和两个 web 测试已经由前端改完，本机 `make check` 不再卡在那里。简单的配方加裁剪导出仍走原来的 RAW 链，边框、时间戳、透视、畸变和四项新调整才走成片。保存时不会把扩大画布之后的裁剪框写回 sidecar，成片渲染时才会夹进有效区域。

## 复审前补丁

徕卡水印和哈苏参数行改用 Inter Regular（OFL，零是普通椭圆）。GXR 字样仍用 Atkinson Hyperlegible。来源、许可和 SHA-256 写在 `studio/src/gxr_studio/assets/SOURCES.md`。边框日期改为 `2026.10.23`。时间戳数码管仍是 `'26 10 23`，每个字符占一格，`1` 的笔画对齐到格子左缘，两组之间的空隙一样宽。重渲了 `final/leica.jpg`、`final/hasselblad.jpg`、`final/stamp-apostrophe.jpg`。

```bash
uv run --frozen pytest -q tests/test_finish.py --basetemp="$TMPDIR/pytest-finish" -p no:cacheprovider
```

13 passed。没有再跑全量 `make check`。

时间戳组内改回原样数码管，`1` 贴住后面的 `0`。三组之间按墨迹外缘留出一样宽的空隙。重渲了 `final/stamp-apostrophe.jpg`，`tests/test_finish.py` 仍是 13 passed。

组间改用 DSEG7 的等宽空白 `!`，排成 `'26!10!23` 交给字体，不再手调字距。`26` 和 `10` 之间比 `10` 和 `23` 之间宽大约半格，这是 `1` 只亮右侧两段的结果。重渲了 `final/stamp-apostrophe.jpg`，`tests/test_finish.py` 13 passed。

## 边框键、裁切角度、137/138 代

sidecar 里 `frame` 继续只放尺寸（`orientation` / `width` / `height`）。边框样式改存 `border`。API 字段名仍叫 `frame`。`DELETE /edit` 和 `DELETE /crop` 只清编辑，不清尺寸。已经写坏的文件（`frame` 里只有样式、没有宽高）在读裁切或编辑时从照片文件把尺寸读回来，样式挪到 `border` 再写回，不再回 422 `no_frame_size`。

`PUT /crop` 的 `angle_deg` 可以不传。不传就保持 sidecar 里的角度，显式传 0 才归零。

`/assets/*` 的响应带 `Cache-Control: no-cache`。

第 137、138 代和 135 是同一套区段尺寸。配方映射、行池、kv2 的字节相同。变的是引擎长度（135 为 60652，137 为 61016，138 为 62512），以及跟着引擎走的重定位、目录里的绝对地址、配方库头里的代数和它的 CRC。两代都按 135 的配置登记进 `datcodec.PROFILES`（最大 98304，带 kv2）。g137、g138 的 `parse` → `pack` 逐字节相同。g138 不钉哈希。文件不在本机时测试跳过，没有把 DAT 拷进 studio。

不支持的代数现在报「不支持第 N 代相机配方文件。请使用第 127 代或更新的版本。」只有 JPG 时，`/capabilities` 的 `reason` 是「配方需要 RAW 文件」。没有照片时的 LUT 预览标签从「示意图」改为「示例照片」。

本机 `make check` 退出码 0。464 passed，覆盖率 87.20%。干净克隆放在临时目录，用符号链接看到本机已有的 `firmware/`、`captures/`、`research/`，没有把这些字节拷进仓库。克隆的 `make check` 退出码 0。463 passed，1 skipped（克隆目录不叫 `studio`，项目文件夹预填那一条跳过），覆盖率 87.20%。旁边完全没有这些目录时，138 个依赖 DAT 或样本的测试会跳过，覆盖率掉到 83.63%，`make check` 会在覆盖率门槛上失败。这是夹具不在旁边，不是这批改动的失败。克隆和 pytest 临时目录已删。

## COPY 3.11

LUT 拟合结果里的 `caution` 长句删掉了。字段还在，值是空串，测试改成断言空串。这份结果不是 OpenAPI 里的模型，`docs/openapi.json` 没有这条句子，`export_openapi.py --check` 仍然一致。

没有照片时的预览标签是「示例照片」，放在 `X-GXR-Label`。没有实测场景光时 `X-GXR-Nominal-Scene` 仍是 `1`，标签同样是「示例照片」。

带上这两条之后，本机 `make check` 退出码 0。466 passed，覆盖率 87.15%。

## COPY 3.12

`POST /api/exports/{export_id}/reveal` 在访达里显示这次导出的第一张。单张导出的 `export_id` 在导出响应里。批量导出用任务的 `id`。请求体里的路径不会被采用。文件必须还在这次导出的目录里。不是 macOS 时返回 501。测试把 `subprocess.run` 换成了假的，没有打开访达。

存成我的配方时，如果当时用的输入色彩空间就是按文件名或标题猜出来的那一个，`source.input_space_guessed` 为 true。前端在这种情况下会把 `space_guessed` 传成 false，后端按文件名自己判断，不再只信这个字段。点了「不确定」时仍是 true。

带上这两条之后，本机 `make check` 退出码 0。473 passed，覆盖率 87.21%。

## 验收修订 2

文案对照表在 `research/studio_v2/backend/COPY_DIFF_backend.tsv`，116 行，列是文件:行、旧、新、依据。行号是改写当时的位置；`routes.py` 后来又加了导出模型，那一文件的行号会偏十几行。

给前端的接口：

- `GET /api/photos/{id}/render?stage=original&size=preview|full|thumb` 有相机 JPG 就给相机 JPG，只有 RAW 才给 04 标准。不套编辑，也不套默认装饰。
- sidecar 没有 `border` / `stamp` 才继承默认装饰。`frame.style="none"` 和 `stamp.enabled=false` 是明确关掉。复原要写这两个值，写 `null` 会重新继承。
- 导出响应的 `render_label` 是 `prediction`、`approx`、`original`。给人看的字在 `render_text`。`render` 仍是原来的机器 id。OpenAPI 模型是 `ExportFile`。
- 错误和降分辨率的成功响应都可以带 `detail`，给「详细信息」折叠区。

| 编号 | 结论 | 证据 |
| --- | --- | --- |
| V2-01 | 已修 | `acceptance.json` 的 `jpg_effect_export`。曝光 +1.5 的导出相对未编辑导出平均差 59.86，预览和导出平均差 0.27。RAW+JPG 零编辑的预览和导出都是 4288×2848，`focused.json` 的 `plain_raw_preview_export.mean_de00` 是 0.23。 |
| V2-02 | 已修 | `raw_resolution`：不加边框 4288×2848，加白边后画布 4632×3192，四边各约 172 像素，照片本体仍是传感器尺寸。 |
| V2-03 | 已修 | `geometry`：向左旋转后 uncropped 和 `crop.frame` 都是 480×640，1:1 是 480×480。垂直是 720×488，畸变是 544×440，frame 与 uncropped 一致。收进有效区域时先按比例取整数。1:1 宽高相等。4:5、3:2、XPan 65:24 与精确比例的偏差不超过 1 像素。 |
| V2-04 | 已修 | 拉直、垂直、畸变都会把框写回 sidecar。成片四角不是 #1b1c1f。拉直的角是 `[30,72,94]`、`[149,30,110]`、`[49,168,86]` 这一组。 |
| V2-05 | 已修（后端） | `stage=original` 已存在。前端已接按住空格。 |
| V2-06 | 已修 | `auto-level-lines.json`：建议的 `vertical` 是整数，原样 PUT 返回 200。水平线图的绝对纠正是 0（原图本身是平的，不再把已经拉过的画面上的残余角当绝对值）。再请求一次结果不变。没有线条时 `confident` 为 false，文字是「未检测到明显的水平线」。 |
| V2-07 | 已修 | `chinese_text`：上海和北京的时间戳、拍立得文字都不再逐像素相同。缺字时按 PingFang、冬青黑体、华文黑体回退，不把中文字体放进仓库。都没有时 `message` 是「无法显示中文。请改用英文或数字。」 |
| V2-08 | 已修（后端） | 缺键才继承。`style=none` / `stamp.enabled=false` 不继承。前端复原已改成写这两个值。 |
| V2-09 | 已修 | `pristine_defaults`：rev=0 的照片套上默认白边后缩略图变了，`Cache-Control` 是 `private, no-cache`。列表 URL 在默认装饰版本不是 0 时带 `d=`。 |
| V2-10 | 已修 | `long_edge` 请求 512，加白边后的最终尺寸是 512×353，没有超出。 |
| V2-11 | 已修 | 加白边导出的 EXIF 有 270、271、272、274、305、306、34665。 |
| V2-12 | 已修 | 24 个 W 会缩小后画进画面。`focused.json` 里的 `text_width` 745.875 是脚本用未缩小的字号量出来的，不是画上去的宽度。合成测试检查了墨迹落在画面内。 |
| V2-13 | 已修 | `date_override=2026-99-99` 保存返回 422，不会留下坏状态。`format=tiff` 返回 422。 |
| V2-14 | 已修 | `reveal_security`：同目录符号链接和目录外链接都是 404。注入的 path 仍只打开登记的那张。核对 inode、大小和修改时间。 |
| V2-15 | 已修（预览） | `focused.json` 的 `loopback_latency`：preview 中位 0.376 秒。full 中位 1.479 秒，五次里有一次 1.85 秒。full 现在是 4288×2848，不再是半尺寸。有效矩形先缩到长边 240。 |
| V2-16 | 已修（前端） | 样式卡片已由前端修好。后端没有改 `web/`。 |
| V2-17 | 已修 | 116 处都改过，表在 `COPY_DIFF_backend.tsv`。 |
| V2-18 | 已修 | `render_label` 为 `prediction` / `approx` / `original`，显示文字在 `render_text`。`docs/openapi.json` 的 `ExportFile` 写了这个取值，`acceptance.json` 的 `openapi.identical` 为 true。 |
| V2-19 | 已修 | 水平正方向现在比较左右两侧的有效高度。近似开关测试改名为 `test_approx_switch_stays_off`，只断言开关，不把色卡留出说成这次重算。自动建议、预览导出和全尺寸在 `tests/test_portable_finish.py`。 |
| V2-20 | 已修 | `portable_check.py` 退出码 0。349 passed，138 skipped，覆盖率 87.65%，旁边没有 firmware、captures、research。门槛仍是 85%。 |

本机 `make check` 在把 1200 像素以内的几何画布改成按实际 warp 计算之前通过：487 passed，0 failed，覆盖率 91.40%，约 380 秒。那次改动之后跑过 `tests/test_finish.py`、`tests/test_portable_finish.py`（17 passed）和上面的 acceptance。

`portable_check.py` 65.55 秒，`private_siblings_present` 为 false。

acceptance、focused、auto_check 都是退出码 0。临时服务在 127.0.0.1:64915，不是 49667，跑完已停。没有做 git 写操作，没有碰 `~/Pictures/GXR Studio`。

缺相机配方时的提示改为「无法生成电脑预测。请先导入相机配方文件。」对照表里这一行已改。固定比例收进有效区域时先取整数倍再缩小，1:1 宽高相等。本机 `make check` 488 passed，覆盖率 91.09%。

## 验收修订 3

后端这一轮是 R2-02、R2-03、R2-04、R2-05 的响应头、R2-07、R2-08、R2-10。没有改 `web/`。

| 编号 | 结论 | 证据 |
| --- | --- | --- |
| R2-02 | 已修 | 零编辑 JPG 进入 `write_with_exif` 时先按 EXIF 转正，再写 Orientation=1。不对称竖拍测试里，存成 80×48、方向 6 的图导出后是 48×80，方向标记是 1，红块落在转正后的位置。 |
| R2-03 | 已修 | 长边超过 1200 时，画布按真实边缘和 1.5 像素留量计算，不再把 360 像素试算的留量放大。`geometry_r2.py` 10 组画布全部与实际 warp 一致。1600×1200 垂直 +80 是 1794×1217，畸变 +70 是 1352×1098。保存框内无效像素都是 0。 |
| R2-04 | 已修 | 自定义文字仍最多 24 字。日期和时间不再被这 24 字截掉，拼完再按宽度缩小。`text_r2.py` 四种日期格式、开或关时间，24 个字母都还在。带时间的一行是 `2026.10.31 14:05 ABCDEFGHIJKLMNOPQRSTUVWX`。 |
| R2-05 | 已修（后端） | `X-GXR-Label` 只放 `prediction`、`approx`、`original`。每次成片响应都带 `X-GXR-Calibrated`，值是 0 或 1。显示文字留给前端。没有阶段参数的预览头也改成 `prediction`，不再把「电脑预测」放进这个头。 |
| R2-07 | 已修 | 界面点不到的非法参数，主句统一为「请求无效。请刷新页面后重试。」，原来的说明放进 `detail`。品质超出 30 到 100 是界面能触发的，主句改为「无法生成预览。品质要在 30 到 100 之间。」 |
| R2-08 | 已修 | 测试夹具是从 Noto Sans CJK SC 裁出的「上海北京」，5580 字节，OFL 在 `tests/fixtures/NotoSansSC-OFL.txt`，`assets/SOURCES.md` 有登记。可移植测试注入这份字体。产品仍只找系统字体。macOS 上另有系统字体测试。把系统字体候选清空后再跑可移植测试，1 passed。 |
| R2-10 | 已修 | 保存时的几何计算移出图库锁，提交前核对版本号。有效区域只算蒙版，不生成全尺寸 RGB。`lock_trace_r2.py` 里，fitted_crop 还在跑时预览的 `get_shot` 等待是 0.00008 秒。预览 0.588 秒出图，保存 200。 |

本机 `make check` 496 passed，覆盖率 91.20%。`portable_check.py` 退出码 0：358 passed，138 skipped，覆盖率 87.74%，62.1 秒，`private_siblings_present` 为 false。门槛仍是 85%。没有做 git 写操作，没有碰 `~/Pictures/GXR Studio`，也没有用 49667。

## 验收修订 4

后端这一轮是 R3-01、R3-02、R3-03，以及 V2-19 里还拦不住这两处的测试。没有改 `web/`，也没有改仓库里的 Makefile。`lint-imports --cache-dir` 和 `pylint --persistent=n` 只加在 Scratch 的 Makefile 副本上。

| 编号 | 结论 | 证据 |
| --- | --- | --- |
| R3-01 | 已修 | 指定长边时，`_decode` 先按这份 JPEG 自己的 EXIF 把像素转正，再缩放、重新编码。原始尺寸仍走 `write_with_exif`，转正后写 Orientation=1。两边都不再把横放的存储像素直接缩小。`matrix_r3.py` 的 `sized_orientation`：JPG 和 RAW+JPG，原始尺寸都是 480×640，长边 512 是 384×512，2048 和 4096 不放大、仍是 480×640，方向标记都是 1，8 组 `match` 都是 true。`failures` 为空。 |
| R3-02 | 已修 | 字号可以收到 1 像素，边距按短边的 3.5% 缩放，宽和高都放得下才停。`stamp_r3.py` 六组字形边界 `overflow` 都是 false。192×256 的中文缩略图字号是 5，右界 185。`stamp_http_r3.py` 里两段同样 24 字、只差后缀的中文，图库缩略图、样式缩略图、预览、导出的像素都不相同。 |
| R3-03 | 已修 | 预览 quality=29，导出 quality=0、101，long_edge=63、30001，主句都是「请求无效。请刷新页面后重试。」。范围在 `detail`：预览是「品质要在 30 到 100 之间。」，导出品质是「品质要在 1 到 100 之间。」，长边是「长边要在 64 到 30000 之间。」。`api_contract_r3.py` 39 项里不合规 0。继承和明确关闭仍然分开：继承 692×532，明确关闭后改默认值仍是 640×480，撤销关闭后是 640×544。 |
| V2-19 | 已修 | `test_stamp_keeps_date_time_and_all_24_characters` 检查完整字形框是否在 192×256、256×192、480×640 里面。`test_sized_export_keeps_portrait_orientation` 走真实导出接口，覆盖 JPG 与 RAW+JPG、原始尺寸和长边 512、2048、4096，并核对红块重心与 EXIF 转正后的位置。`test_thumbnail_preview_and_export_keep_the_stamp_suffix` 用两段等长、后缀不同的中文比较缩略图、预览和导出。 |

本机 `make check` 退出码 0：497 passed，覆盖率 91.54%，366.42 秒，检查期间源码哈希没变。`portable_check.py` 退出码 0：359 passed，138 skipped，覆盖率 88.04%，63.32 秒，`private_siblings_present` 为 false。门槛仍是 85%。证据写在 `/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3/evidence/`，没有改 Sol 原来的 `r3-evidence`。矩阵开跑前，临时库里补了第 137、138 代相机配方文件和开发机校准数据，否则 RAW 预测会停在缺配方。没有重跑界面脚本。没有做 git 写操作，没有碰 `~/Pictures/GXR Studio`，临时服务端口是 63596，用完已停。
