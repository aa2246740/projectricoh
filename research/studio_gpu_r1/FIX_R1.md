# FIX_R1：显卡预览复审 r1 的修复

**能交复审。** 4 项 P1、5 项 P2 都改了，每项都有回归测试；新加的测试都在修复前的代码上验证过会失败。
`make check` 全部通过（lint、两遍 mypy（darwin + win32）、bandit、开关、私有字节、前端构建核对、OpenAPI 核对、import-linter、deptry、vulture、pylint 重复代码，以及测试 998 passed、697 skipped、0 rerun，覆盖率 89.32%（门槛 85%））。构建产物逐字节可复现（`scripts/check_frontend.py --require`：前端构建产物与源码一致）。
真实输入 14 组在 Metal 和 SwiftShader 上各重跑一遍，按新门槛全部通过；复审的两个全合成反例现在逐字节相同。

**本机做不到、要靠 CI 的一项：** Windows 完整测试套件没有在本机跑过（没有 Windows 机器）。本机做了能做的三件事：
mypy 按 win32 平台检查，把 Windows 那条按路径的实现在 macOS 上整套跑通，Windows 专用分支逐段读过。
CI 已改成 windows-latest 和 macos-latest 都跑完整测试套件，另加 Linux 上按路径实现的整套。推送后请看三平台结果；
Windows 上第一次真跑仍可能暴露本机看不到的问题（见第 6 节的风险点）。

工作树 `/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview`（`feat/gpu-preview`，HEAD `cd2817fb`），没有任何 git 写操作。
改动文件 37 个（修改 30、新增 7），见第 8 节。

---

## 1. 一览

| 编号 | 改了什么 | 证明它的测试 |
| --- | --- | --- |
| P1-01 图库外读取 | 新模块 `library/media.py`：`/raw`、`/camera-jpg` 和 RAW 布局解析共用一个受限打开函数，只认图库根下的相对路径，拒绝卡上和受保护目录、任何一级链接。打开以后只用这个 fd：发送和 TIFF 解析都不按路径重开；支持单段 Range | `test_gpu_api.py`：`test_photo_file_that_became_a_link_is_refused[raw / camera-jpg]`、`test_photo_folder_that_became_a_link_is_refused_for_bytes_and_layout`、`test_open_media_refuses_paths_outside_the_library`、`test_open_media_refuses_a_file_replaced_between_check_and_open[目录 fd / 按路径]`、`test_raw_bytes_support_ranges_and_large_files`；`test_platform_io.py::test_media_by_path_refuses_a_folder_swapped_for_a_link` |
| P1-02 资源版本 | 烘焙表的地址和键带相机数据版本（`dv=`），LUT 表的键带 render token；`camdata-changed`、`luts-changed` 让前端换代；旧代请求无论成功还是失败，回来都丢掉；表不可用时这一帧回服务器，沿用原有错误 | `test_gpu_state.py` 的 6 个场景（真的 `gpu_stage.js`，接口、fetch、引擎用替身，请求何时完成由脚本控制）：LUT 改成 vlog、相机数据 g127→g155（dv v1→v2）、迟到的成功、迟到的失败、预取去重、开关关着 |
| P1-03 颜色门槛 | 显示类 LUT 改成 8 位精确表：全部 256³ 个输入逐个交给生产 `lut.photo._apply`，着色器只查表；门槛按编排者定稿写进 `tests/gpu_gate.py`；复审反例进 CI | `test_gpu_api.py::test_display_lut_table_is_the_production_function_on_every_input`；`test_gpu_parity.py` 新增 `counter_raw_lut_adjust`、`counter_jpg_lut_highlight`、`raw_display_lut_geometry`；`test_gpu_gate.py`（门槛每条规则一个刚好通过、一个刚好失败的例子） |
| P1-04 Windows | 新平台层 `osplat`（锁、fd→真实路径、落盘、父进程存活）；`audit`、`privacy`、`library/lock` 不再导入 `fcntl`；没有 `dir_fd` 的平台用按路径的 `_PathPrivateDir`、`PathCardReader`；CI 两个平台跑完整套件 | `test_platform_io.py`（7 个）、`test_fix_review.py` 原有的锁冲突测试（同进程两个句柄、子进程持锁）、`test_a1a_review_r2.py` 两种实现各自的移走目录测试、`test_polish_p2.py` 跨平台的父进程被杀测试；`GXR_FORCE_PATH_IO=1` 整套；`mypy --platform win32` |
| P2-01 裁切框校验 | `gpu/box` 在路由里严格校验：整数宽高、有限数、`rect` 在 0..1 内、预设名已知、多余键拒绝、宽×高不超过这张照片的像素数；错误统一回 422 `{"error": "bad_box"}` | `test_box_rejects_bad_input_with_a_json_422`（23 种坏输入：NaN、Infinity、1e309、字符串、布尔、负数、超尺寸、未知键、坏预设……） |
| P2-02 显卡资源 | 同一个键再上传烘焙表 / LUT 表先销毁旧的；LUT 最多留 3 张（精确表每张 64 MB），烘焙表 24 张 | `test_gpu_frontend.py::test_engine_replaces_and_frees_resources_with_the_same_key`（用记录 create/destroy 的假设备跑真正的 `engine.js`） |
| P2-03 预取 | 按照片 + `sidecar_rev` 去重，不随滑块输入重复 | `test_prefetch_runs_once_per_photo_not_per_slider_input`（修复前：拖 25 下发了 26 次邻图编辑请求；修复后 ≤ 2） |
| P2-04 开关关着 | `/gpu` 只回 `{"enabled": false}`，不解析 DNG、不预热；`/api/settings` 带开关状态，前端开关关着时一个显卡请求都不发、不建设备 | `test_flag_off_makes_no_gpu_requests`、`test_gpu_info_off_by_default` |
| P2-05 `/table` 写盘 | LUT 库按 `persist=False` 读；旧格式的升级挪到启动时（`app._migrate_luts`） | `test_lut_table_does_not_write_and_old_records_upgrade_at_startup`（启动后已升级；运行中再出现旧记录，`/table` 前后文件字节、mtime、目录列表都不变） |

"在修复前的代码上会失败"的核对：
- 6 个状态场景放在 HEAD 的 `gpu_stage.js` 上跑：LUT 改成 vlog 后仍走显卡、相机数据换了还用 K1、旧代的成功被装进引擎、旧代的失败把新代标成服务器、预取 26 次、开关关着仍发 1 次 `/gpu`。每个都违反对应断言；
- 资源测试放在 HEAD 的 `engine.js` 上跑：同键第二次上传，旧缓冲没有销毁；
- 3 个链接替换测试把新加的真实位置核对去掉后都失败；
- 链接、图库外的接口测试对应 HEAD 的按路径 `FileResponse`，会直接把图库外的字节发出去。

---

## 2. P1-01：照片文件只读、拒绝链接和图库外

`library/media.py`：
- `open_media(lib, relpath)` 先检查路径：只接受相对路径，不能有空段、`.`、`..`、反斜杠或 NUL。图库根按 realpath 确定，再用 `Library.is_local` 核对它不在卡上，也不在受保护目录里；
- POSIX：从图库根逐级 `O_DIRECTORY|O_NOFOLLOW` 打开，最后一级 `O_NOFOLLOW|O_NONBLOCK`。任何一级是链接，打开本身就失败（ELOOP/ENOTDIR → `MediaRefused("link")`），核对和打开是同一次系统调用，没有空隙。打开以后再 fstat，必须是普通文件；
- Windows（没有 `dir_fd`）：逐级 lstat，链接和重解析点（目录联接）一律拒绝。打开后先核对 `(st_dev, st_ino)` 与 lstat 一致，再用 `GetFinalPathNameByHandleW` 核对 fd 的真实位置就是这个路径；
- `FdResponse` 拥有这个 fd：按 1 MB 块从 fd 读，结束关闭。支持单段 Range：206 加 `Content-Range`，越界回 416 和 `bytes */大小`，看不懂的 Range 发整个文件；
- RAW 布局解析（`_raw_source`）从同一个 fd 读出全部字节交给 `open_dng`，不按路径重开。被拒绝时 `raw_reason` 是 `refused:link` 之类，前端回服务器出图；
- 接口错误：拒绝回 409 `photo_file_unavailable`，文件不存在回 404 `photo_file_missing`。

测试要点：
- 文件换成链接：两个接口都回 409，响应里没有图库外的字节；
- 照片所在目录换成链接（目录外放了同名文件）：`/raw`、`/camera-jpg` 都 409，`/gpu` 的布局为空、原因是 `refused:link`；
- 核对和打开之间被替换：
  - 按目录 fd：最后一级打开时被换成链接，`O_NOFOLLOW` 直接失败；
  - 按路径：打开时被换，身份核对失败；
  - 中间一级被换成目录链接：真实位置核对失败；
- 大文件和 Range：
  - 约 5 MB 的文件跨好几个块，整文件逐字节相同；
  - 跨块的中间段、`bytes=-10`、`bytes=N-`、越界、`bytes=-0` 都对；
  - 改的是图库里的副本，卡上文件不动。

## 3. P1-02：GPU 资源跟着数据版本走

`web/assets/gpu_stage.js`：
- 烘焙表地址带 `dv=<相机数据版本>`，键里也带。相机数据从 g127 换到 g155 后键变了，引擎里旧的那张不会被命中；
- LUT 表的键是服务器给的 `<cube_id 前 16 位>-<render token>`，空间版本一变键就变；
- 代数：收到 `camdata-changed`、`luts-changed`（`lut_library.js`、`lut.js` 改空间或删 LUT 后发出）时代数加一，所有挂着的请求（成功、失败、预取）回来先核对代数，不对就丢掉；
- LUT 表还没到（显示类精确表第一次计算约 4 秒）或取表失败（422 等）：这一帧回服务器出图，沿用服务器原来的错误，表到了再切回显卡。

`tests/test_gpu_state.py` + `tests/support/gpu_stage_state.mjs`：每个场景一个 node 进程，加载真的 `gpu_stage.js` 和 `state.js`；接口、fetch、引擎用替身，请求挂起后什么时候完成由脚本决定，不靠时间间隔。复审给的两条复现都在里面：
- LUT 输出改成 vlog：第一次表在算 → server；表到 → gpu；`luts-changed` 后重新取表，422 → server，再路由一次仍是 server，旧表不再使用；
- 相机数据 g127 → g155：换代前用 K1；`camdata-changed` 后以 `dv=v2` 重新取表 → K2；
- 迟到的成功：v1 的表挂着时换代，v1 随后成功：没有装进引擎；最终用 K2；
- 迟到的失败：v1 随后失败：新代没有被标成失败，最终用 K2 走显卡。

## 4. P1-03：显示类 LUT 和颜色门槛

**根因**：原实现在着色器里对 17³ 表做三线性插值，再按输入空间解码、编码。浮点运算顺序与 numpy 不同，在取整边界上会翻 1 码值；陡的 LUT 再放大。复审的反例在 RAW 和 JPG 上都触发了。

**修正**：显示类 LUT 的输入就是 8 位底图，可以穷举。`gpu/tables.display_lut_u8` 把全部 256³ 个 8 位 RGB 分 8 块（每块 32 个 B 平面），两个线程交给生产函数 `lut.photo._apply`，结果存 RGBA8（64 MB）。
着色器用 `textureLoad` 取整数坐标，不插值，所以与 Python 对整张图套 LUT 逐像素相同，取整平局也一样。一维表、任何输出空间（包括 V-Log）、色域都在 `_apply` 里，所以显示类 LUT 不再因为这些退回服务器。

- 代价：第一次计算在本机约 4 秒（2 线程），按 (cube_id, render token) 缓存最近两张；同一张同时只算一次。显卡上每张 64 MB，最多留 3 张；
- Log 类输入仍然下发 3D 表在着色器里算（输入是浮点，无法穷举），实测与 Python 最大差 1 码值；
- `test_display_lut_table_is_the_production_function_on_every_input`：用复审的反例节点、加一维表、输出 vlog，抽 20,004 个输入（含黑、白、纯红），与 `_apply` 逐个相等。

**门槛**（`tests/gpu_gate.py`，CI 和本机真实用例共用）：

1. 每个用例 ≤1 码值的像素 ≥ 99.99%、平均 ΔE00 ≤ 0.01。都用未舍入的整数计数判（`超过 1 码值的像素数 × 10⁴ ≤ N`）；
2. 边缘带：在 CPU 有效区蒙版（`warp_valid`，裁到成片框）上取边界内外各一像素（8 邻接），随拉直、旋转、翻转、裁切一起变换；画面四周和裁切边不算，没有拉直时边缘带为空；
3. 带外：最大差 ≤ 4。>2 码值的像素只能出现在冻结位置上，差值不超过冻结值，并且要由前向量化复算逐字节重现。新位置、更多像素、更大的差都失败；
4. 带内 >2 码值的像素 ≤ ceil(N × 10⁻⁶)；
5. 显示类 LUT 的用例不允许冻结豁免。

前向量化复算的做法：把 Python 第一段（配方 + 曲线，`chroma_u8` 的 uint8 输出）在该像素上每通道偏 −1/0/+1（27 种），交给生产 `finish_array` 走完黑点、饱和度、自然饱和度、暗角。有一种逐字节等于显卡结果，就算解释了。它只用于没有几何变换的配方路径，那里是逐像素运算，位置不变。

CI 的合成用例冻结列表全部为空。本机真实用例的冻结列表**直接取复审 r1 的独立测量**：
- 来源：`real-parity-metal.json` / `real-parity.json` 中 >2 码值且不在边缘带的像素，按适配器分开；
- 不从本次结果里取；
- 脚本会核对复审记录的样例数等于它报告的总数。

`test_gpu_gate.py` 覆盖每条规则：边缘带随旋转翻转裁切变换、恰好 0.01% 过 / 多一个不过、未冻结位置、差值变大、新位置、复算解释不了、带外 5、显示类 LUT 带冻结、带内恰好 ceil(N×10⁻⁶) 过 / 多一个不过。

### CI 合成对拍（SwiftShader，13 个颜色用例 + 适配器检查）

| 用例 | ≤1 码值 | 平均 ΔE00 | 最大差 |
| --- | --- | --- | --- |
| raw12_tone | 100% | 0 | 0 |
| raw16_o6_curve_extra | 100% | 0.00000404 | 1 |
| raw_o8_display_lut | 100% | 0.00001036 | 1 |
| raw_log_lut | 100% | 0.00001016 | 1 |
| jpg_o6_adjust / jpg_rec709_lut_curve / jpg_untouched | 100% | 0 | 0 |
| raw_geometry_ratio | 100% | 0.00001468 | 1 |
| raw_free_crop | 100% | 0.00000914 | 1 |
| raw_uncropped_straighten（边缘带 1,180 像素） | 100% | 0.00001847 | 1 |
| **counter_raw_lut_adjust**（复审反例） | 100% | 0 | **0** |
| **counter_jpg_lut_highlight**（复审反例） | 100% | 0 | **0** |
| raw_display_lut_geometry（显示类 LUT + 拉直 + 旋转 + 翻转） | 100% | 0.00003529 | 1 |

（`raw_o8_display_lut`、`raw_display_lut_geometry` 的 1 码值来自 LUT 之前的配方链，不是 LUT 本身。）

## 5. 真实输入 14 组：Metal 和 SwiftShader

复用复审 r1 的隔离做法（`fix_r1/session.py`）：
- 7 张真实 GXR DNG + JPG 的副本，g127 夹具 DAT 和标定；
- 显示类和 Log LUT 都是公式生成的合成 LUT（17³ `clip(rgb×[0.86,0.97,1.05])`；65³ `clip((x−0.1)×1.6)`），没有用第三方 LUT；
- 端口 49751，临时目录在 scratch 下；
- 浏览器里调用工作室真正的 `gpu_stage.route()`（`fix_r1/route_cases.js`），读回成片纹理；
- 参考图由生产 RAW、配方链、LUT、`finish_array` 在 JPEG 压缩前算出（`fix_r1/color_reference.py`），按 `gpu_gate.evaluate` 判定。

适配器以页面报告的 JSON 为准：Metal 跑出 `apple/metal-3`，SwiftShader 跑出 `google/swiftshader`。14 组在两个适配器上都走显卡（`real-route-*.json`）。

| 用例 | 尺寸 | Metal ≤1 码值 | Metal 平均 ΔE00 | Metal 最大差 | SwiftShader ≤1 码值 | SwiftShader 平均 ΔE00 | SwiftShader 最大差 | 新门槛 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a_recipe01 | 2144×1424 | 100.00000000% | 0.00001040 | 1 | 100.00000000% | 0.00000967 | 1 | PASS |
| b_recipe02_tone | 2144×1424 | 100.00000000% | 0.00002773 | 1 | 100.00000000% | 0.00002298 | 1 | PASS |
| c_recipe04_curve_extra | 2144×1424 | 99.99918115% | 0.00001916 | 4 | 99.99921390% | 0.00001739 | 4 | PASS（带外 7 个 >2，全部在冻结位置并由复算解释） |
| d_mount_knobs | 2144×1424 | 99.99980348% | 0.00001367 | 2 | 99.99977072% | 0.00001120 | 2 | PASS |
| **e_display_lut** | 2144×1424 | **99.99977072%** | **0.00000735** | 2 | **99.99980348%** | **0.00000802** | 2 | PASS（复审时 Metal 99.80494953% / 0.01799379，FAIL） |
| f_log_lut | 2144×1424 | 100.00000000% | 0.00001997 | 1 | 100.00000000% | 0.00003058 | 1 | PASS |
| g_jpg_adjust | 4288×2848 | 100% | 0 | 0 | 100% | 0 | 0 | PASS |
| **h_jpg_lut** | 4288×2848 | 100% | **0** | **0** | 100% | **0** | **0** | PASS（复审时 Metal 平均 0.08118636，FAIL） |
| i_portrait_recipe | 1424×2144 | 100.00000000% | 0.00001701 | 1 | 100.00000000% | 0.00001524 | 1 | PASS |
| j_portrait_jpg | 2848×4288 | 100% | 0 | 0 | 100% | 0 | 0 | PASS |
| k_straighten_crop | 1608×1139 | 100.00000000% | 0.00023211 | 1 | 100.00000000% | 0.00016789 | 1 | PASS |
| l_rotate_flip_ratio | 1282×1923 | 100.00000000% | 0.00034656 | 1 | 100.00000000% | 0.00026841 | 1 | PASS |
| m_uncropped_straighten | 2144×1424 | 99.99996725% | 0.00043109 | 24 | 99.99996725% | 0.00037521 | 24 | PASS（24 码值那 1 个像素在边缘带内，上限 ceil(N×10⁻⁶) = 4；带外最大差 1） |
| n_jpg_untouched | 4288×2848 | 100% | 0 | 0 | 100% | 0 | 0 | PASS |

- **c 的 7 个像素**：Metal 是 (y,x) = (91,210)、(557,667)、(561,1839)、(584,1159)=4、(648,819)、(649,1655)、(776,531)。SwiftShader 是 (512,2046)、(557,667)、(561,1839)、(584,1159)=4、(621,1983)、(649,1655)、(766,1005)。两边各自与复审的独立测量完全一致，27 种偏移复算 7/7 逐字节重现。这条路径本轮没有改：配方链里的中间精度和运算顺序让第一段偶尔差 1 码值，后面几步 uint8 取整把它放大到 3–4。
- **e 剩下的 1–2 码值**：来自 LUT 之前的配方链（与 a–d 同一来源）。LUT 本身逐像素相同，h（相机 JPG + 同一张 LUT）就是逐字节相同。
- **m 的 24 码值**：复审已查明是几何有效区判定的 float32 边界（Python y=1423.001021…，阈值 1423.001；float32 两者都是 1423.0009765625），点在边缘带内。
- 原始结果：`fix_r1/real-parity-metal.json`、`fix_r1/real-parity-swiftshader.json`、`fix_r1/real-route-*.json`、`fix_r1/real-inputs.json`（输入文件的 SHA-256 清单）。

## 6. P1-04：Windows

**改动**
- `osplat`（新）：POSIX 和 Windows 的差别都收在这里：
  - 文件锁：`flock` / `msvcrt.locking` 锁第一个字节，进程退出系统自动放；
  - fd → 真实路径：`F_GETPATH` / `/proc/self/fd` / `GetFinalPathNameByHandleW`；
  - 完整落盘：`F_FULLFSYNC` / `fsync`；
  - 父进程还在不在：POSIX 看 `getppid` 是否变了；Windows 拿住父进程句柄，看它结束没有。
- `audit`、`privacy`、`library/lock`、`cards/session`、`cli`（SIGHUP 只在有的平台注册）不再直接用 POSIX 专有的东西。
- `PrivateDir`、`CardReader` 在没有 `dir_fd` 的平台上构造成按路径的实现（`_PathPrivateDir`、`PathCardReader`），接口和错误语义与按 fd 的实现相同：
  - 逐级 lstat 拒绝链接和重解析点；
  - 读：打开后核对身份和真实位置；
  - 写：排他创建，每写一块前后都核对路径仍指向这个文件、文件的真实位置没变；
  - 父目录在操作途中被移走，按 `private_path_changed` 报（与按 fd 的实现拿着已移走目录的 fd 一样）。
- `GXR_FORCE_PATH_IO=1` 让 POSIX 也走按路径的实现，测试用它在 macOS/Linux 上跑 Windows 那条路的逻辑。

**本轮额外找到并修好的 Windows 问题**（都有测试）：
- 中间一级目录在 lstat 和打开之间换成目录联接：原来的身份核对拦不住，因为 lstat 自己也会跟着中间那级走。加了按 fd 的真实位置核对：读、写、照片打开三处，`test_platform_io` 的 3 个测试去掉这个核对就失败；
- LUT 拟合子进程靠 `getppid` 判断服务还在不在。Windows 不过继，父进程没了 `getppid` 也不变，子进程会一直跑。改为父进程句柄；测试改成跨平台：POSIX 父进程是 `/bin/sh`，Windows 是一个 Python，强杀后子进程 15 秒内自己退出；
- `tests/hdr_support.py` 在导入时调用 `os.uname()`，Windows 上收集就会失败。改用 `osplat.HOST_IS_DARWIN`；
- 测试里查进程是否还在原来用 `os.kill(pid, 0)`；在 Windows 上这会 TerminateProcess，改为查退出码。

**本机能做的验证**
- `mypy`（darwin）和 `mypy --platform win32` 都通过。`make type` 两个都跑，Windows 分支的类型错误在 macOS 上就能发现；
- `GXR_FORCE_PATH_IO=1` 整套测试：998 passed、697 skipped，与默认实现的数目相同（8 分 16 秒）；
- 平台层测试（`test_platform_io.py`）两种模式都通过：同进程两个句柄的锁冲突与释放、两个进程同时整体替换同一个文件（最后是其中一份完整内容，不留临时文件）、fd 真实路径与落盘。

**CI**（`.github/workflows/ci.yml`）
- `check`（ubuntu）：`make check`，要求前端核对和显卡适配器（不变）；
- `tests`（windows-latest、macos-latest）：完整测试套件，装 Node 22 让前端测试真跑，`GXR_REQUIRE_GPU_TEST=1`；
- `path-io`（ubuntu）：`GXR_FORCE_PATH_IO=1` 完整测试套件；
- `security-report`（不变）。

**新增的平台跳过**只有一个：`test_studio_shuts_down_cleanly_on_sighup` 在没有 `signal.SIGHUP` 的平台跳过（Windows 关控制台不是信号）。其余跳过都是原有的环境条件（本机没有夹具 DAT、研究目录、macOS 系统字体等），没有为了 Windows 新加跳过。适配器必须成功的断言保留。

**风险点，要看 Windows CI 或实机**
- 本机没跑过的 Windows 文件语义：打开中的文件不能改名或删除、`os.replace` 遇到对方正在替换时可能报拒绝访问。并发替换测试允许这种 `PermissionError`，但要求至少一次成功、最后一份完整、不留临时文件；
- 无权限子目录的测试（`chmod 0`）在 Windows 上挡不住读取，会按原有的"权限位挡不住读取"条件跳过；
- 按路径实现剩一个窗口：中间一级在 lstat 和排他创建之间被换成目录联接时，别处可能留下一个 0 字节文件。写第一个字节之前就会拦下并清空；
- 这次没动、Windows 上本来就不可用的功能：
  - 「在访达中显示」：501，只在 macOS 上可用；
  - 读卡器卷枚举：`default_volumes_roots` 在 Windows 返回空，原注释写着留到 M3 之后；
- WebGPU 在 Windows 上走 D3D12 的硬件路径，要在实机确认（CI 只有 SwiftShader / WARP 一类的软件适配器）。

## 7. P2

- **P2-01**：`BoxRequest` 改为 `extra="forbid"`，宽高是严格整数 1..20000，在路由里 `model_validate`，错误统一成 `{"error": "bad_box", ...}`。`crop.rect` 要求 4 个有限数（布尔不算）、落在 0..1、宽高为正；`crop.preset` 只认已知名字；宽×高不超过这张照片的像素数（RAW 全尺寸和记录尺寸里大的那个）。几何参数沿用 `parse_geometry` 的严格解析。OpenAPI 里仍有完整的请求体结构（`openapi_extra`）。
- **P2-02**：`addBake`、`addLut` 同键先 `destroy` 旧资源。烘焙表最多 24 张；LUT 表最多 3 张，按最久没用的先销毁。`dispose` 销毁全部。
- **P2-03**：预取按 `照片 id + sidecar_rev` 记一次，同一组不再请求邻图的编辑记录和显卡信息。
- **P2-04**：开关关着时 `/gpu` 只回 `{"enabled": false}`，不打开 DNG、不预热烘焙表。`/api/settings` 加了 `gpu_preview`，前端 `flagOn()` 为假时 `route()` 直接回 `server`，不建 WebGPU 设备，不发 `/gpu`。
- **P2-05**：`LutLibrary._read(..., persist=False)` 在内存里升级旧记录但不写回。`get / render_token / target / load` 都有 `persist` 参数，`/table` 用 `persist=False`。旧格式升级在启动时做（`app._migrate_luts`，失败只记日志）。

## 8. 改动文件

gxr-studio 工作树，30 个修改、7 个新增：

| 类别 | 文件 |
| --- | --- |
| 新增 | `src/gxr_studio/osplat.py`、`src/gxr_studio/library/media.py`、`tests/gpu_gate.py`、`tests/test_gpu_gate.py`、`tests/test_gpu_state.py`、`tests/support/gpu_stage_state.mjs`、`tests/test_platform_io.py` |
| 后端 | `api/gpu_routes.py`、`api/routes.py`（设置带开关）、`app.py`（启动时升级 LUT 库）、`gpu/tables.py`（精确表）、`lut/library.py`（`persist`）、`lut/worker.py`（父进程存活）、`privacy.py`（按路径实现）、`audit.py`、`library/lock.py`、`cards/discovery.py`（`PathCardReader`）、`cards/session.py`、`camdata/store.py`、`cli.py` |
| 前端 | `frontend/src/engine.ts`、`frontend/src/shaders/common.wgsl`、构建产物 `web/assets/gpu/engine.js`、`web/assets/gpu_stage.js`、`web/assets/lut.js`、`web/assets/lut_library.js` |
| 测试 | `tests/test_gpu_api.py`、`tests/test_gpu_frontend.py`、`tests/test_gpu_parity.py`、`tests/test_a1a_review_r2.py`、`tests/test_polish_p2.py`、`tests/hdr_support.py` |
| 工程和文档 | `.github/workflows/ci.yml`、`Makefile`（`make type` 加 win32）、`docs/architecture.md`、`docs/feature-flags.md`、`docs/openapi.json` |

研究目录（本仓库，不进 gxr-studio）：`research/studio_gpu_r1/FIX_R1.md`、`research/studio_gpu_r1/fix_r1/`：
- `session.py`、`route_cases.js`、`run_real.mjs`、`color_reference.py`：真实输入复跑，改自复审 r1 的脚本；
- `synthetic_lut_counterexample.py`：复审脚本原样复跑，只换临时目录；
- 结果：`real-parity-*.json`、`real-route-*.json`、`real-inputs.json`、`synthetic-lut-counterexample.json`；
- 日志：`make-check-final.log`、`pathio-final.log`（按路径的整套）、`ci-parity-swiftshader.log`（CI 合成对拍逐例统计）、`ref-metal.log`、`ref-swiftshader.log`。

## 9. 复审合成反例

复审 r1 的 `synthetic_lut_counterexample.py` 原样复跑（`fix_r1/synthetic_lut_counterexample.py`，只把临时目录和结果位置换成 FIX_R1 的），SwiftShader，退出码 0：

| 全合成用例 | 复审时 ≤1 码值 / 平均 ΔE00 / 最大差 | 现在 |
| --- | --- | --- |
| RAW + 合成 LUT + 调整 | 99.96065109% / 0.00221030 / 2（FAIL） | 100% / 0 / 0，逐字节相同 |
| JPG + 合成 LUT + 高光 | 99.95880127% / 0.01071808 / 2（FAIL） | 100% / 0 / 0，逐字节相同 |

同样两组也进了 CI（`counter_raw_lut_adjust`、`counter_jpg_lut_highlight`），结果相同。

## 10. 进程、耗时和清理

- 计算进程最多 2 个，都用 `nice -n 10`；真实输入复跑时是隔离工作室加浏览器，算参考图之前先停了工作室。机器负载 8–17（别的任务）；
- 单次最长：`make check` 约 8 分钟（测试 7 分 27 秒），按路径的整套 8 分 16 秒，真实输入复跑每个适配器读回约 1.5 分钟、参考图约 1.5 分钟。没有超过 30 分钟的运行；
- 临时文件和 Chrome 用户目录都在 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r1/`，结束时已删除；隔离工作室（49751）已停，Chrome 已关；
- 工作树里的 `__pycache__`、`.pytest_cache` 已删除；
- 没碰机主的工作室（49667 和三个目录），没碰卡，没开子代理，没用 sleep 轮询。公开仓库里没有照片、理光数据或第三方 LUT：真实 DNG 只在 scratch 的临时图库里，合成 LUT 由公式生成。
