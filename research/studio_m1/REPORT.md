可以交复审

# studio-m1-backend-r1 报告

S1（工程骨架）和 S2（插卡导入 + 图库 + 裁切/导出接口）已做完，代码在 `studio/`。
**pytest：73 个用例全部通过**（Python 3.14.7 约 33 秒；同一份锁文件在 Python 3.12.11 上也是 73 通过）。
没有 git commit；只写了 `studio/` 和 `research/studio_m1/`。

## 测试结果

```
$ cd studio && uv run pytest -q
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 33.65s
```

| 文件 | 用例 | 内容 |
|---|---|---|
| `tests/test_import.py` | 24 | 只读卡、配对、去重、同名、日期、幂等、拔卡续传、空间不足、校验、取消、杀进程 20 次、真实样本、索引重建 |
| `tests/test_crop.py` | 17 | 比例预设像素、XPan 4288×1583、拉直、校验、拖动、旋转方向、sidecar 往返 1e-9、版本冲突 |
| `tests/test_api.py` | 13 | 接口端到端：卡、导入、日期/照片/缩略图/预览、裁切、导出、批量导出、重建、审计、并发导入 |
| `tests/test_security.py` | 19 | 令牌、Host、Origin、cookie 不能单独做写操作、只监听回环、审计钩子、真实卷禁区、离线 |

## M1 验收逐条（只列与后端有关的）

| # | 验收 | 结果 | 证据 |
|---|---|---|---|
| 1 | 只读卡：导入前后整棵卡目录内容+大小+mtime 快照相等；写卡次数 0 | 通过 | `test_card_is_never_written`：`AuditRecorder` 记到 0 次写（含被拦截的尝试），同时记到读取，证明探针有效；`test_writes_to_card_are_blocked_and_recorded` 证明真有人写时会被记录并拒绝 |
| 1 | 合成卡 20 个 shot，含 DNG+JPG、仅 JPG、仅 DNG、同名不同内容、EXIF 乱码 | 通过 | `synthetic_card.make_card`：20 个 shot（4 对真实样本 + 16 个合成，其中 1 个是同内容副本）；纯合成版是 16 个（不含真实大文件） |
| 2 | 幂等：第二次复制 0 个文件、不读文件内容 | 通过 | `test_second_import_copies_nothing_and_reads_no_card_content`：审计钩子记到 0 次对卡上文件的 `open`；`force_verify` 打开后读了全部但新增 0；重建索引后 seen 从 `import-log.jsonl` 恢复，仍然 0 复制 0 读取 |
| 3 | 中断可恢复：随机杀进程 20 次 | 通过 | `test_kill_the_process_20_times`：20 轮，每轮新图库，子进程导入中途 SIGKILL（每 4 轮再杀一次，共 ≥ 20 次真的杀到了运行中的进程——测试里断言了）；每次杀完检查库里每个媒体文件的哈希都对应卡上某个文件（无残缺）；重开后无 `.part`、无 `.tmp`；再跑一次补齐，总数、哈希全对；最后索引重建一致 |
| 3 | 拔卡 | 通过（模拟） | `test_unplug_midway_then_resume`：读到第 9 个文件后目录消失 → `interrupted`，文案含"插回卡可以继续"，库内一致；插回后只补缺的 |
| 3 | 读不出来的文件跳过、不中断其他 | 通过 | `test_unreadable_file_is_skipped_not_fatal`（整对跳过，不会只导一半；好了以后补上） |
| 3 | 复制后校验大小+哈希 | 通过 | `test_verify_failure_is_not_committed`：暂存文件被改坏 → `verify_failed`，该照片不入库 |
| 3 | 空间不足暂停并可继续 | 通过 | `test_pause_when_no_space_then_resume`（注入可用空间）、`test_enospc_while_writing_pauses`（写盘报 ENOSPC） |
| 4 | 按 EXIF 日期归档；缺 EXIF 的退回…；批次偏移写入日志；DCIM 多子目录 | 通过 | `test_dates_folders_and_fallback`、`test_batch_shift_moves_dates_and_is_logged`（23:59:59 +2 秒跨午夜；日志里有 `shift_seconds`）、`test_pairing_and_junk`（`101RICOH` 也扫） |
| 5 | 真实样本 4 对 | 通过 | `test_real_samples_four_pairs`：`stage2c-first-run` 4 对 DNG+JPG 套上 `DCIM/100RICOH` 外壳，得到 4 对，尺寸 4288×2848，哈希与源一致，无重复无遗漏 |
| 6 | XPan 4288×1583；预设像素；sidecar 往返 1e-9 | 通过 | `test_xpan_on_4288_wide_frame_is_4288x1583_and_centered`、`test_preset_pixel_sizes_landscape`、`test_sidecar_roundtrip_is_exact_to_1e9` |
| 7 | 导出：原文件哈希不变；EXIF（日期/镜头/ISO）+ sRGB ICC；尺寸 = 裁切结果 | 通过 | `test_export_flow_and_source_untouched`、`test_real_sample_xpan_export`（真实样本导出 4288×1583；macOS `sips` 能读出尺寸；拉直 4° 的尺寸等于接口返回的裁切像素） |
| 8 | 离线 | 通过 | conftest 在整个测试进程里禁止 `socket.connect`/`getaddrinfo`，每个测试结束断言联网尝试为 0 |
| 9 | 新手可用 | 未做 | 人工验收，且前端不在本任务内 |
| 10 | 1000 张合成照片记录数值 | 已记录 | `tests/perf/baseline.json`（见下）；前端首屏/滚动流畅度要等前端 |

### 1000 张合成照片的后端数字（单次实测，M 系列 Mac；不是基准承诺）

合成 1600×1067 噪声 JPG，导入含缩略图生成：全部导入 8.4 秒（8.4 ms/张）；`/api/dates` p50 6.3 ms；首屏 60 张列表 p50 2.9 ms；
1000 张全量列表 p50 41 ms；60 张缩略图冷启动 421 ms、热 47 ms；1600 px 预览冷生成 16 ms；索引重建 1000 张 1.1 秒。
真实 4 MB 的 4288×2848 JPG 会比这慢（解码），没有量。

## S1 清单

- `pyproject.toml` + `uv.lock`（`uv lock` 生成，带哈希；`.python-version` = 3.14）。
- **锁文件与 `requirements.pin.txt` 逐项核对：14 项（12 运行时 + pytest、httpx）版本全部一致，无差异。**
  锁文件里另有 11 个传递依赖，pin 清单没列：annotated-doc 0.0.5、annotated-types 0.8.0、certifi 2026.10.23、colorama 0.4.6、httpcore 1.0.9、idna 3.20、iniconfig 2.3.1、packaging 26.3、pluggy 1.7.0、pygments 2.21.0、typing-inspection 0.4.4（均为 fastapi/pydantic/httpx/pytest 的依赖）。pin 清单里"明确不要"的包（rawpy、python-multipart、piexif、opencv、watchfiles）都不在锁里。
- 只监听本机：`cli.py` 自己绑 `127.0.0.1` 的 socket（端口随机）交给 uvicorn；实测 `lsof` 只看到 `127.0.0.1:<端口>`；令牌（HttpOnly + SameSite=Strict cookie、`X-GXR-Token`、`Bearer`）、Host 白名单（含端口，挡 DNS 重绑定）、Origin 校验；没有 Origin 的写操作必须用头部令牌（cookie 单独不行）。
- 审计钩子 `audit.py`：记录 `open`（写模式）、rename/remove/mkdir/utime/chmod/copyfile/rmtree/sqlite3.connect 等写事件的路径；可把目录登记为"受保护"——发现卡时卡根目录自动登记，任何写入记录后抛 `PermissionError`；应用自带一个记录器，`GET /api/audit` 可看。
- 测试夹具生成器 `devtools/synthetic_card.py`（也有命令行，前端任务可以拿它造假卡）。

## 与设计文档不一致/需要您留意的地方

1. **缺 EXIF 日期的归档：文档互相矛盾。** 任务说"回退到文件时间"，ARCHITECTURE §4.1/验收 4 与 UX 流程 B 说"进未知日期、文件时间只作提示"。我按任务的说法做了默认（`undated_policy="mtime"`，并在索引/日志里标 `date_source=mtime`，界面可据此提示"日期是猜的"），另一种做法 `unknown_folder` 也实现并有测试。需要您定哪个当默认。
2. **没有做**：SSE 进度（用 `GET /api/jobs/{id}` 轮询代替）；批量导出的"继续导出"清单（中断后重做会生成 `-2`、`-3`，不会覆盖）；安全弹出卡（M1 后端清单里没有）；强制全量校验在 UI 里的开关（接口 `force_verify` 有）。
3. **只有 RAW 的照片不能导出**（接口返回 409 `no_jpg_source`），按任务"导出用 JPG 源"；缩略图/预览用 DNG 内嵌的 JPEG 预览（真实样本是 640×424，不是 IFD0 的 160×120，已核实）。裁切框对只有 DNG 的照片可以设（尺寸取 DNG 的 DefaultCropSize）。
4. **合成 DNG 是 160×120 的 TIFF，不含 CFA**，只用来测配对、日期、缩略图。真实 DNG 只有那 4 个 50mm 样本；28mm/MOUNT 的 DNG 没有，`unit` 只是按镜头名里的"NNmm"粗略解析，没有核实。
5. **已知局限**：
   - `seen` 的卡标识是卷标的哈希；两张同卷标的卡若同一相对路径、同一大小、同一秒时间戳，会被误判为"见过"（概率极低；`force_verify` 可纠正）。去重本身靠内容哈希，不受影响。
   - 一对文件里只有一个是重复（另一个是新的）时，只把新的那个导成独立的一张（不会补进已有的那张）。
   - 裁切框校验允许角点超出原画面 1 像素以内（界面取整用），导出时可能出现 1 像素的黑边。
   - 导出的 EXIF 去掉了 MakerNote（它的内部偏移搬不走），其余 EXIF 保留；方向改为 1。
   - "空间不足"用注入的可用空间和模拟 ENOSPC 测试，没有用真的小容量卷；"拔卡"用读取器模拟，不是真实硬件。
   - 没有给 `/api/photos` 做游标分页（`limit/offset` 即可）。
6. **sidecar 比文档多了一块** `import`（卡标识、日期来源、批次偏移、文件大小、入库时间），好让索引能完全按目录重建；文档里的 `source/frame/crop` 照做，未知键（M2 以后的 recipe/adjust/curve）原样保留，读到更新的 schema 只读。

## 安全与卡的情况（请注意）

- 测试和运行**没有读写任何真实的卡**。`tests/conftest.py` 在测试进程里禁止读写、列出 `/Volumes` 下除 `Workspace`、`Macintosh HD` 以外的任何卷，`test_real_volumes_are_off_limits_in_tests` 证明连 `/Volumes/RICOHDCX` 都会被拦下；真实的默认图库、导出目录、应用数据目录同样被保护，HOME 换成临时目录。
- 一次例外要如实交代：开工前我在探索环境时执行过一次 `ls /Volumes` 和 `df -h /Volumes/Workspace`（那时还没有任何测试代码）。当时列出的卷是 AppleContainerData、Macintosh HD、Recovery、Workspace，**没有 `RICOHDCX`**，所以没有触及用户的卡内容。
- 唯一联网：`uv lock` 解析依赖，以及在 Python 3.12 上复验时下载 numpy/scipy 轮子（都是 pin 清单里的包）。没有访问其他网络资源。
- 没有碰相机；没有启动子代理；同时最多 2 个进程（pytest + 杀进程测试里的 1 个子进程）。
- 我另外用真实的 `gxr-studio` 命令在 `/tmp` 的假卡上起了一次服务做冒烟（无令牌 401、错 Host 403、能导入、只监听 127.0.0.1），之后已停掉并删除。

## 交接给前端任务

- 启动方式见 `studio/README.md`；`GXR_STUDIO_VOLUMES` 指向 `synthetic_card` 造的目录就能在没有真卡的情况下做界面。
- 正式前端放 `studio/web/`：有 `index.html` 时 `/` 返回它，`web/assets/` 挂在 `/assets`。所有 `fetch` 要带 cookie（同源默认就带）。
- 接口清单和裁切约定（正角度 = 顺时针、`rect` 在旋转后的画布上、`flip` 把预设转 90°）见 README。
