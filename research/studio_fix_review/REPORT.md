可以交复审

# studio-fix-review-r1：按复审报告修复"GXR 电脑工作室"

依据：`research/review_studio_m2/REVIEW.md`（结论"不可以给用户试用"）。改动全部在 `studio/` 和本目录；没有碰相机、真实卡（`/Volumes/RICOHDCX` 等）、网络，没有 git commit，没有启动子代理。

## 1. 结果一览

| 验收项 | 结果 |
|---|---|
| 复审探针 `probe_a`～`probe_d` | a：71 项失败 0（原 4 项失败）；b：49 项失败 0；c：4 项失败 0（原 1 项失败）；d：见下面 §3，原探针按设计无法转为通过，换成了真调前端代码的 `probe_d_fixed.py`，8 项全过 |
| 全量测试 | **356 个全部通过**（原 305；新增 51 个，改了 2 个旧测试，理由见 §4），347 秒 |
| 浏览器走查（原走查的副本） | 87 项通过，0 失败，浏览器错误记录 0（原 72 项；多出来的是新增检查，见 §5） |
| 新增走查"导入部分失败" | 34 项通过，0 失败，浏览器错误记录 0、4xx/5xx 0 |
| 临时目录 | `Scratch/sfr`（测试、探针）已删除；走查的临时目录由脚本自己删，两次都打印"临时目录已删除" |

## 2. 必须修的三项

### P0-1　导入不完整时不再说"可以安全弹出"

后端（`cards/importer.py`）：
- 一对文件里每个文件各自处理：读得出的照常导入，读不出（`unreadable`）或复制后校验不一致（`verify_failed`）的明确列出，**不登记 seen**，所以下次会重试。
- 列卡上目录时读不了的文件夹/文件也记下来（`scan_errors`），以前是悄悄漏掉。
- 进度里新增 `failed_shots`（按"张"算：一对里坏一个也算一张）、`completed_shots`。
- `_done_message`：`unreadable`、`verify_failed`、`scan_errors` 任何一个不空，就写"导入没有全部完成…请先别格式化或清空这张卡：换个读卡器或重新插拔，再点「继续导入」"，整句不含"安全弹出"。
- 上次只导进来一半的照片，这次把另一半读好了：并进**同一张**照片（`_complete_existing`），保留裁切/配方/调整，不会多出一张同名的（否则两张会共用同一个 sidecar，互相覆盖）。代价：补全后这张照片的 id 会变（id 是两个文件内容的哈希），旧 id 的缩略图缓存成了孤儿，无害。

前端：
- 文字规则单独放在不碰页面的 `web/assets/import_summary.js`，`import.js` 只调用它。有任何没读进来的文件：红色横幅、列出文件名（最多 6 个，其余"等共 N 个"）、状态栏同样提醒先别格式化；只有"完成且一个问题都没有"才说"可以安全弹出"。
- 有问题的导入不算"处理完"：关掉横幅后仍会出现「开始导入」可以重试（走查里发现我第一版漏了这点，已改）。
- 用 node 直接测这个模块（`tests/test_import_summary.py`），不用浏览器。

### P1-1　编辑记录（sidecar）坏了或被删了

- 读的接口（裁切、编辑、预览、导出）当作"没有编辑"继续，响应带 `warning`：白话，不含路径和解析错误。`_crop_for_export` 同样防护。
- 写的接口（保存裁切/编辑）：先把坏的改名留着（`<名>.gxrs.json.corrupt-<时间>`），再建一份"没有编辑"的往下写，也带 `warning`。删掉的情形（不是损坏）走同一条路。
- 兜底：`app.py` 给 `SidecarCorrupt` 装了统一处理（422 白话），再也不会 500；`render_routes` 里原来 `str(exc)` 带路径的 500 全部去掉。
- 前端：保存裁切、保存编辑时弹提示；导出结果、批量导出汇总里写明哪几张是按没有编辑导出的。
- 复审探针 a 里"sidecar 损坏"那几行原来抛异常，现在都是 200；但探针的顺序是先 PUT crop（会修好 sidecar）再测导出，所以"损坏状态下导出"这条路径我另外用 `tests/test_fix_review.py` 单独覆盖了（损坏/被删/不是 sidecar 三种 × 裁切读写、编辑读写、单张导出、批量导出，并检查响应里没有路径、`Expecting`、`Traceback`）。

### P1-2　只有 RAW 的照片的缩略图/大图标注

选了**"标成电脑预测（原厂标准）"**，没有改成中性预览。理由：已经导入相机数据时，只有 RAW 的照片用原厂 04 的电脑模拟，比中性转换更接近相机默认会给出的样子，用户也更容易理解；改成中性反而让导入相机数据后图库颜色变回"发灰"的状态，是退步。代价是必须处处如实标注，所以：

- 后端新增 `preview_look = {kind, label, prediction}`，`kind` 四种：
  - `camera-jpg`：配对了相机 JPG，画面就是相机拍出来的；
  - `stock04-prediction`：只有 RAW 且已导入相机数据——"电脑预测（原厂标准）"，未标定时"电脑预测（原厂标准；跨单元/跨 ISO，未标定）"；
  - `neutral`：只有 RAW 且没有相机数据——"中性转换（不是相机的颜色）"，不算预测；
  - `embedded`：RAW 半分辨率读不出来而退回的 RAW 内嵌小预览（走查里合成的假 DNG 就是这种）。
- 缩略图/预览的响应头：`X-GXR-Look`、`X-GXR-Label`（百分号编码），预测时加 `X-GXR-Prediction: 1`（探针 c 要的就是这个）。`preview_kind` 保持 `dng-preview` 不变（探针 c 里断言了它）。
- 前端：图库角标写"只有 DNG · 电脑预测 / 中性 / 内嵌小图"；大图下面的说明按种类写，只有相机 JPG 才说"照片本身（不是预测）"；按住 Space 的说明也跟着改；电脑预测时带"电脑预测"小标签。文字规则在 `web/assets/look_notes.js`，同样用 node 测。
- 真浏览器核对过：相机数据+标定导入后，图库里这张的角标是"只有 DNG · 电脑预测"，打开大图说明是"电脑预测（原厂标准…）：…不是相机拍出的 JPG"，截图 `screenshots/05c-raw-only-labelled.png`。
- 一个小设计点：退回内嵌小预览的缩略图存成单独的 `-emb` 缓存变体，且换相机数据时不清掉它；照片列表靠"导入时就生成过的 `-emb` 缩略图"认出这类照片（导入时会生成缩略图）。如果用户手动删了 `.studio/thumbs/`，在缩略图重新生成之前列表会暂时把这类照片标成预测，图片响应头始终是对的。这是已知的小缺口。

## 3. 顺手修的 P2

| 项 | 做法 | 怎么验证 |
|---|---|---|
| P2-1 | `rebuild` 遇到坏 sidecar 先改名成 `.corrupt-<时间>` 再写新的；接口返回 `corrupt_backups` | `test_rebuild_keeps_a_copy_of_a_corrupt_sidecar`；探针 a 末尾现在能看到备份文件名 |
| P2-2 | `library/lock.py`：启动时对 `<图库>/.studio/studio.lock` 拿 flock；第二个实例打印"工作室已经开着了：请回到第一个打开的窗口…"，退出码 75，`GXR Studio.command` 据此不再多说"已停止" | 测试：同进程二次加锁被拒；**子进程持锁被 kill 后锁自动释放**；`cli.main` 的提示和退出码。没有在真终端里双击两次（用的是同样的代码路径） |
| P2-4 | README 第 2 步写明"可移除的卷"权限；`find_cards` 可收集 `PermissionError`；新增 `GET /api/cards/status`；界面在没找到卡且被系统拒绝时红色横幅明说（`state.cardAccess`），状态栏不再只写"未插入" | 测试（读卡器注入 `PermissionError`，卷根和单张卡两种）；**真浏览器**里把卷根目录 `chmod 000`，横幅和状态栏如预期，恢复后消失。没有在真 macOS 权限弹窗下验证（做不到） |
| P2-5 | 批量导出单张失败：白话 + 错误代码，不带异常原文和路径 | `test_batch_export_with_a_broken_sidecar_and_plain_failures` |
| P2-6 | `GET /api/camdata/status` 带 `project_dir`；设置里的路径框预填，并加「用工作室所在的项目文件夹」按钮 | 测试 + 真浏览器走查（点按钮填路径后导入成功） |
| P2-7 | 现状：`配方`页签已是可用的"导入调色文件→做成配方"页（LUT 任务做的），`index.html` 里**已经没有"即将推出"角标**，不用再改。我只改了两处：大图配方标签里那个禁用按钮的提示不再写内部代号"M3"（改成白话，指到「配方」页）；`相机`页签的"即将推出"保留——把配方写回相机确实还没做 | `test_recipes_tab_has_no_coming_soon_badge_but_the_camera_tab_keeps_it` |
| P2-8 | `camdata.store.swap_in`：macOS 用一次 `renamex_np(RENAME_SWAP)` 原子对调（任何时刻都有完整的一份），不支持时退回两步改名；`recover_interrupted_swaps` 在 `create_app` 启动时处理 `camera-data.old`/`calib.old`（根在就删残渣，根不在就改回去）。相机数据和标定包共用 | 测试：原子和退路两种、**在两步之间模拟被打断**再启动恢复、残渣清理、`create_app` 触发恢复。原子对调在本机（APFS）上实测可用；Linux/其他文件系统走退路，没有测 |
| P2-10 | 同时插着多张卡：横幅和状态栏提示"插着 N 张卡，一次只处理第一张"；真浏览器核对 | 走查 E；node 测文字 |
| P2-12 | 所有响应带 `Content-Security-Policy: default-src 'self'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` | `img-src` 多放行了 `blob:`（预览图是 fetch 之后用 object URL 显示的）和 `data:`（页面的 `<link rel=icon href="data:,">`）。**在真 Chrome 里整套走查一遍，浏览器错误记录为 0**（CSP 违规会记成控制台错误）；另有静态检查：没有内联脚本/样式属性/`eval`/外部地址 |

**不改的 P2：** 
- **P2-3**（令牌 cookie 不分端口）：复审自己评估风险很小（HttpOnly + SameSite=Strict）。要改就要动令牌交换流程，和这次的修复无关，且容易引入回归。
- **P2-9**（`seen` 对同名卷标的卡可能误判）：概率极低；要改需要换卡标识（卷序列号）和迁移已有的 seen 记录，应单独做。
- **P2-11**（`dest_dir` 接受任意绝对路径）：需要令牌，风险有限；限制到 `~/` 之下会挡住合法的外接硬盘导出，应由用户决定。
- **P2-13**（`.command` 没有 Homebrew 时的安装命令）：现有提示已经够用（复审 §4 也这么说）。

## 4. 测试

- 全量 356 个全部通过。新增 51 个：`tests/test_fix_review.py` 34 个、`tests/test_import_summary.py` 13 个（node）、`tests/test_render.py` 1 个 P1-2 测试（另外扩充了原来的"内嵌预览"测试）、`tests/test_import.py` 3 个。
- **改了 2 个旧测试**（`test_import.py` 的 `test_unreadable_file_is_skipped_not_fatal`、`test_verify_failure_is_not_committed`）：它们断言的是旧行为"一对里坏一个就整对丢掉"，而这正是复审 P0-1 要求去掉的（"读得出的那个照常导入"）。新断言：好的那半进图库、坏的列出、消息里没有"安全弹出"、再导一次把另一半并进同一张。
- 测试全程用临时目录，`conftest` 的 `forbid_volumes` 保证碰不到 `/Volumes` 下的真实卡。

## 5. 探针与走查：哪些改了、为什么

- **探针 a、b、c 一个字没改**，只是把输出存到本目录（`probe_*.out`）。
- **探针 d 无法"转为通过"**：它里面"界面横幅"那一行是探针自己用 Python 抄的旧 `import.js` 逻辑，字符串写死了"现在可以安全弹出卡了"，最后一句 `ok = bool(verify_failed) and "安全弹出" in ui` 在任何前端下都成立。原件没动（`probe_d.out` 是它的输出，仍然"复现"，这是它的设计）。我写了 `probe_d_fixed.py`：同样的场景，但横幅文字改用 node 跑真正的 `import_summary.js` 算，并断言：不是绿色、没有"安全弹出"、建议先别格式化、列出 `R0000102.JPG`、状态栏同样、好的 DNG 照常导入。8 项全过。
- **浏览器走查**：`research/studio_integration/` 里的原件、截图和结果**没有动**。本目录 `browser_walkthrough_integration.mjs` 是副本，相对原件只改了 3 处，都是因为界面本来就该变：①"只有 DNG"角标现在带后缀，按前缀找；②设置里的路径框现在预填，所以先清空验证"请先填写"，再点新按钮代替手敲；③新增检查（CSP 头、只有 RAW 的角标/大图说明如实标注、让 R8051145 变成可解码的"只有 RAW"样本）。另外把几个点标签的动作改成等页面画完、点不中重试——**走查脚本里有时序问题**（刚换照片就点标签栏，偶尔点在旧页面上），最后两次完整运行都是全过，但这是时序问题，不是应用问题。
- **新增走查** `browser_walkthrough_partial_import.mjs`：A 卷根目录读不了；B 插卡且一对里的 JPG 读不出来（`chmod 000`）；C 关掉横幅仍能重试；D JPG 恢复后继续导入，补全而不是多出一张，这时才说可以弹出；E 再插第二张卡。进程数：node + 服务 + Chrome = 3，其余时间 ≤2。

## 6. 没做到 / 限制

- 没有在真 macOS 的"可移除的卷"权限弹窗下验证 P2-4（用 `PermissionError` 注入和 `chmod 000` 模拟）。
- 没有在真终端里双击两次 `.command` 验证 P2-2（用同一份代码路径的单元测试代替，含子进程）。
- 没有测 28mm / MOUNT 的真实 DNG（和复审时一样没有样本）。
- 补全一半的照片会改变它的 id（见 P0-1）；`.studio/thumbs` 被手动删除后列表对"读不出的 RAW"的标注有短暂不准（见 P1-2）。
- 我没有改复审没提到的东西，LUT 模块（`studio/src/gxr_studio/lut/`）一行没动。
- 机器上另有一个不是我启动的 Chrome（`--remote-debugging-port=9334`，配置目录 `/tmp/gxrm2/…`，是别的任务的），我没有碰它。

## 7. 改动的文件（`studio/` 下）

源码：`cards/discovery.py`、`cards/importer.py`、`library/store.py`、`library/sidecar.py`、`library/edits.py`、`library/thumbs.py`、`library/lock.py`（新）、`render/edits.py`、`render/service.py`、`api/routes.py`、`api/render_routes.py`、`api/camdata_routes.py`、`app.py`、`cli.py`、`security.py`、`camdata/store.py`、`camdata/calib.py`、`GXR Studio.command`、`README.md`。
前端：`web/assets/import.js`、`import_summary.js`（新）、`look_notes.js`（新）、`gallery.js`、`preview.js`、`viewer.js`、`camdata.js`、`crop.js`、`export.js`、`recipes.js`、`state.js`、`app.css`。
测试：`tests/test_fix_review.py`（新）、`tests/test_import_summary.py`（新）、`tests/test_import.py`、`tests/test_render.py`。
所有改过的文件的哈希在 `SHA256SUMS`。

## 8. 复现

```bash
cd <仓库根>/studio && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q --basetemp=<临时目录>/pt     # 356 个，约 6 分钟
cd <仓库根>
studio/.venv/bin/python -I research/review_studio_m2/probe_a.py <临时目录>/a
studio/.venv/bin/python -I research/review_studio_m2/probe_b.py <临时目录>/b $PWD
studio/.venv/bin/python -I research/review_studio_m2/probe_c.py <临时目录>/c $PWD
studio/.venv/bin/python -I research/studio_fix_review/probe_d_fixed.py <临时目录>/d $PWD
node research/studio_fix_review/browser_walkthrough_integration.mjs        # 需要 Google Chrome 和本机的固件包 DAT
node research/studio_fix_review/browser_walkthrough_partial_import.mjs
```
