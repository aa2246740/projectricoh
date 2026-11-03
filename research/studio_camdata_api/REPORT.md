可以交复审

# studio-camdata-api-r1：导入相机数据与标定包的后端接口

完整测试 **244 个全部通过**（原来的 206 个 + 新增 38 个，`studio/.venv/bin/python -m pytest -q`，167 秒）。没有改 `studio/web/`，没有改 engine 的算法，没碰相机和真实的卡（测试进程禁止访问 /Volumes 下的真实卷），没联网，没 commit，没启动子代理。

## 1. 新接口（`studio/src/gxr_studio/api/camdata_routes.py`，逻辑在 `camdata/intake.py`）

| 接口 | 作用 |
|---|---|
| `GET /api/camdata/status` | `ready`；相机数据状态/来源（卡的卷标或"文件"、文件名、大小、SHA-256、代数、导入时间）；三个单元各自的槽位 1–8 与原厂 04 是否齐全；标定状态与来源；插着的卡里哪张有 GXRCE.DAT；`next`（下一步要做什么）与 `data_version` |
| `POST /api/camdata/import-card` `{card_id?}` | 从插着的卡上**只读**取出 GXRCE.DAT，校验后提取到应用数据目录 |
| `POST /api/camdata/import-file` `{path}` | 从本地 GXRCE.DAT（或装着它的文件夹）导入 |
| `POST /api/calibration/import` `{path}` | 从本地文件夹导入标定包；要先有相机数据 |

**校验（写任何东西之前做完）**：魔数、代数（127/129/131/135 以外拒绝）、两层 CRC、钉子、`pack(parse(b)) == b`、三个单元的原厂 04 CRC、长度上限（96 KB）。不过就返回中文说明，应用数据目录原封不动（测试逐文件比对哈希）。
**错误码**：`no_card` / `dat_not_found`（404）、`multiple_cards`（409，带候选）、`card_not_found`、`card_read_failed`（409）、`generation_unsupported` / `dat_invalid`（422，消息里写明第几代、支持哪些）、`bad_path` / `file_not_found` / `file_unreadable`；标定：`camera_data_missing`（409）、`calibration_pack_invalid` / `calibration_stock_mismatch`（422）、`folder_not_found`（404）。
内容与已导入的完全相同时什么都不做（`unchanged: true`，不重写、不清缓存）。

**对卡只读**：只经过 `CardReader`（`scandir` / `open_rb`），在每个卷的最外层找 `GXRCE.DAT`（不分大小写，没有 DCIM 的刷机卡也能找到）；被发现的卡登记进审计钩子，之后任何写入都会被拒绝。测试里：审计记录器看到的卡上写入 0 次；导入前后卡目录的文件树（大小、mtime、SHA）完全相同；`open_rb` 只被调用过一次、对象正是 GXRCE.DAT；应用自己的 `/api/audit` 新增的写入全部落在应用数据目录。副作用：测试里要模拟"换了卡上的文件"，得先 `audit.unprotect`，说明保护确实生效。

**标定包**：两种来源。
1. 标定包文件夹：`calib-pack.json`（schema `gxr-studio/calib-pack/1`，正好 ISO 200、1600 两套，每个文件的 SHA-256 与大小）+ 数据文件。文件名只能是普通文件名（挡 `../`）；先逐个核 SHA-256 并复制到 `calib-intake.tmp`，再从这份副本导入（核对与导入读的是同一份字节），结束后删除临时目录。`intake.write_pack` 能把 `{iso: (npz, ring)}` 整理成这种文件夹（测试用它造包）。
2. 开发机：`path` 指向仓库根或 `research/`（用 `calib.dev_sources`），返回 `kind: "dev"`。**README 里写明：这只是开发阶段的办法，别的用户以后需要另外拿到标定包，怎么制作和分发还没决定。**
两种都用包里的 `stock` 核对已导入相机数据里 jlaunch 的原厂 04，不一致拒绝（并且旧的标定包保持不变，失败留下的 `calib.new` 半成品会清掉）。

## 2. 缓存失效

- `RenderService.replace_data(action)`：在渲染服务的锁里执行替换，`_refresh` 看不到"换到一半"的状态；之后 `invalidate()` 清空烘焙与渲染结果缓存（解码后的码值图与相机数据无关，保留）。
- 渲染键本来就含相机数据和标定清单的 SHA（S6），所以即使缓存没清，旧结果也不会命中；测试里：换成第 135 代后同一参数的渲染 `X-GXR-Cache: miss`，`X-GXR-Render-Key` 不同。
- 没有 JPG 的照片的缩略图/预览：缓存变体名现在含相机数据 + 标定清单的哈希（`thumb_variant`），导入后旧文件由 `thumbs.purge_variants` 删除（JPG 的缩略图不动）；**照片列表里这类照片的 `thumb_url`/`preview_url` 带上 `?v=<data_version>`**。这是必要的：图片响应是 `immutable` 一年缓存，URL 不变浏览器永远用旧图。有 JPG 的照片链接不变（测试断言）。前端导入后重新取一次 `/api/photos` 即可。
- 测试（用样本 DNG 去掉 JPG）走了完整过程：无数据（渲染 409 `camera_data_missing`、缩略图为中性预览）→ 导入相机数据（链接变、仍 409 `calibration_missing`）→ 导入标定包（缩略图变成 04 电脑模拟、`-n` 文件被删）→ 换成第 135 代（渲染重画、链接再变）。

## 3. 为了做对而多改的几处（均在允许的目录内）

- `camdata/store.py`：`import_from_dat` 多一个可选 `origin`，写进 manifest 的 `source.origin`（卡的卷标，或 `{"kind":"file"}`；**不记本地路径**，测试断言）。
- `camdata/calib.py`：新增 `StockMismatch(CalibError)`、`stock_fingerprint`；标定清单多写 `camera_stock_sha256`、`imported_at`、可选 `origin`。
- `render/service.py`：`invalidate` / `replace_data` / `data_version`；标定清单里有 `camera_stock_sha256` 时，与当前相机数据的原厂 04 不符就把标定状态标成 `invalid`（"请重新导入标定包"），不静默继续预测——否则用户换一份原厂 04 不同的 DAT，预测会悄悄变。老清单没有这个字段则跳过检查。
- `library/thumbs.py`：`purge_variants`。`api/routes.py`：`photo_json` 的 `data_version`。`app.py`：注册路由、`camdata_lock`。
- 渲染算法、engine 没动。

## 4. 没有做 / 需要知道的

1. **没有最终用户的标定办法**：开发阶段靠研究目录；`write_pack` 只是把现有数据整理成包的格式，包的制作与分发由你决定。包里含 `stock`/`d0`/`d1`（理光派生），分发有版权问题，我没有碰。
2. **原厂 04 不同的 DAT 无法在测试里真造出来**（条目 CRC 被登记值钉死）；这条检查用 monkeypatch 登记值测了拒绝路径，"标定与相机数据 04 不一致"的状态用改标定清单里的指纹测了。
3. 28mm / MOUNT 的 DAT 只能用本机四代固件包里的 DAT 测，没有真卡。真实卡（RICOHDCX）按约束没有碰，接口对真卡的行为只由合成卡验证。
4. 扫卡每次 `GET /api/camdata/status` 都会列一遍各卷最外层（只 `scandir`）；前端不要高频轮询。
5. `import-file` 接受任何本地绝对路径（只读、有大小上限、不是 DAT 就拒绝）；服务只听 127.0.0.1 且要令牌。
6. 导入成功后缩略图缓存里只有 DNG-only 的变体会被删；`.studio/thumbs/` 其余内容不动。

## 5. 文件

- 新增：`studio/src/gxr_studio/camdata/intake.py`、`studio/src/gxr_studio/api/camdata_routes.py`、`studio/tests/test_camdata_api.py`、`research/studio_camdata_api/{REPORT.md,SHA256SUMS}`。
- 修改：`studio/src/gxr_studio/{app.py,api/routes.py,camdata/store.py,camdata/calib.py,render/service.py,library/thumbs.py}`、`studio/README.md`（新增"第一次使用：导入相机数据和标定包"、接口表、目录说明）。
- 仓库里没有新增理光字节：测试里的 DAT 现场从本机固件打包目录读取，写到临时目录；原有的"代码/测试/报告里没有理光行"扫描测试通过。
- 复现：在 `studio/` 下 `.venv/bin/python -m pytest -q`（全部）；`.venv/bin/python -m pytest tests/test_camdata_api.py -q`（新增 38 个，约 5 秒）。
