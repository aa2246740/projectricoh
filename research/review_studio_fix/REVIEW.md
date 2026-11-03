可以给用户试用（P0-1、P1-1、P1-2 都已真正关闭；没有 P0、没有 P1。剩下 6 条 P2，都不丢照片，只有边角情形会出小毛病，试用时留意 §2 的几条就行）

# review-studio-fix-r1：GXR 电脑工作室修复复审

复审人：review 子代理（Sonnet 5.5），2026-10-30。只读复审：`studio/` 一个文件都没改（复审结束时重新算了 117 个文件的哈希，与开始时逐字节一致，清单 `reviewed_files_at_start.sha256`）。写入只在本目录。没有碰相机、真实卡、网络，没有启动子代理。

## 0. 结论一句话

上一轮的 P0（导入出错还说"可以安全弹出"）我用 10 种出错情形去撞，没有一处再说"安全弹出"；读得出的那一半照常导入，之后补全也不丢裁切。LUT 功能没有写卡的路径，上传限制和路径穿越都挡得住。我这次**新找到的问题都是 P2**：缩略图偶发 500、补全那一瞬间被杀会多出一张且丢裁切、关终端窗口时拟合子进程会再跑一会儿等（见 §2）。

## 1. 重点核对结果

### 1.1 P0-1：关闭

**探针 d 的原断言确实写死了旧逻辑。** `research/review_studio_m2/probe_d.py` 里横幅是探针自己拼的字符串 `ui = f"导入完成：…现在可以安全弹出卡了。"`，最后一句 `ok = bool(verify_failed) and "安全弹出" in ui` 不依赖前端，所以不管前端怎么改都"复现"。我拿修好的代码重跑了原件（`rerun_probe_d_original.out`）：后端消息已经变成"导入没有全部完成…请先别格式化"，但探针那一行仍然打印旧文案。所以修复报告说的"原探针无法转为通过"属实。`probe_d_fixed.py` 合理：同一场景（翻转 R0000102.JPG 的一个字节），横幅文字改成用 node 跑真正的 `web/assets/import_summary.js` 算，8 项断言（不是绿色、没有"安全弹出"、建议先别格式化、列出文件名、状态栏同样、好的 DNG 照常导入…）我重跑 8 项全过（`rerun_probe_d_fixed.out`）。

**我自己造的 10 种出错情形**（`probe_e_partial.py`，`probe_e.out`；进程内，假卡，用 node 跑真正的前端文字模块）。每种都检查：后端消息、横幅文字、横幅说明行、状态栏都不含"安全弹出"，横幅不是绿色，`canEject=false`：

| 情形 | 结果 |
|---|---|
| A 一对里 JPG 读不出（权限错误） | 好的 DNG 已导入；JPG 被列出；`failed_shots=1`；横幅红色，列出 R0000102.JPG，有「继续导入」 |
| B 一对里 DNG 读不出 | 好的 JPG 已导入；补全后合并成一张 |
| C 一对两个都读不出 | 这一对没进库，其余 14 张照常；红色 |
| D 复制后校验不一致 | 好的那半导入，坏文件不进图库、图库磁盘上没残留、staging 清空 |
| E 拔卡（读第 5 个文件时） | 状态 `interrupted`，横幅"导入被打断了…插回卡可以继续"，无 `.part` 残留；插回后继续，完成且无遗漏 |
| F 电脑空间不足 | `paused_no_space`，红色，可重试 |
| G 卡上某个子目录读不了 | `scan_errors=['DCIM/100RICOH/LOCKED/']`，红色（以前是悄悄漏掉） |
| H 读到一半 I/O 错误 / H2 短读（读出字节数不够） | 都记为"读不出"，不会有短文件进库 |
| H3 未知异常 | 状态 `failed`，不是 `done`，staging 清空 |

**补全后编辑记录**（A、B 情形的第二步，卡恢复后再导入）：
- 仍然只有一张 R0000102，总张数不增加（15→15）；
- 补全前我先给那半张照片写了裁切（XPan，角度 1.5°），补全后 sidecar 和索引里的裁切**原样还在**；sidecar 里的 `shot_id` 和另一半的 SHA 都更新了；没有多余的 sidecar；
- 再导一次是"这张卡上的照片都导入过了"，没有新增。

**照片 id 会变，对用户的影响**（id 是两个文件内容的哈希，补全后重新算）：
- 编辑记录、裁切、缩略图都跟着带过去，用户几乎感觉不到；
- 旧 id 的缩略图缓存成了孤儿（无害，几十 KB）；
- 补全发生时，如果用户**恰好**已经勾选了这张照片或开着它的大图：大图会显示"找不到这张照片 · 回到图库"（体面）；**已勾选的选择集里还留着旧 id，批量导出会整批被拒**（`POST /api/export` 只要有一个 id 不存在就 404，其余照片也不导，见 P2-3）。补全通常发生在重新插卡后自动开始的那一刻，用户一般还没来得及选，所以影响很小。

**一处没有被修复报告提到的边角**：见 P2-1（补全那一瞬间被杀）。

### 1.2 P1-1、P1-2：关闭

- **P1-1（编辑文件坏了）**：`probe_a` 重跑 71 项 0 失败；"sidecar 损坏"那几行（GET/PUT crop、GET/PUT edit、单张导出、批量导出、缩略图、预览）现在全是 200，并且旧的损坏内容有备份（`R0000102.gxrs.json.corrupt-<时间>`）。我另外试了"格式没坏但内容怪"（`probe_h_sidecar_misc.py`）：schema 比本程序新 → PUT crop/edit 返回 409 且**文件不变**，导出仍可用，rebuild 不覆盖；裁切数字越界、adjust 越界、recipe 是数字、curve 乱写、顶层是 `[]`/`null` 都不是 500，照片文件字节全程不变。只有"手改出来的怪 JSON"仍会 500，见 P2-5。
- **P1-2（只有 RAW 的照片标注）**：`probe_c` 重跑 4 项 0 失败。我用真实 DNG（`probe_j_rawonly_brightness.py`）确认：导入相机数据 + 标定包后，只有 DNG 的照片 `preview_look = stock04-prediction`，缩略图和大图响应头带 `X-GXR-Look`、`X-GXR-Label`、`X-GXR-Prediction: 1`；画面亮度与相机 JPG 接近（平均差 1.2/255，另一张 28/255，是 04 对该张实拍 JPG 配方的差异，本来就"不是相机 JPG"）。
- **新标签用语是否处处出现、是否如实**：
  - "电脑预测（原厂标准）"/"（原厂标准；跨单元/跨 ISO，未标定）"：后端 `thumbs.look_of`、响应头、图库角标"只有 DNG · 电脑预测"、大图小标签 + 说明、Space 说明、导出文件名 `_电脑预测`/EXIF，全都有，我读了 `look_notes.js`、`gallery.js`、`preview.js` 和 `thumbs.py`；
  - "中性转换（不是相机的颜色）"：没有相机数据时的缩略图/大图/角标"只有 DNG · 中性"，走查里真浏览器核对过；
  - "内嵌小图"：读不出的 DNG（走查里的合成假文件）角标"只有 DNG · 内嵌小图"，说明写"相机自己生成的，很小，不是配方预测"；
  - 只有相机 JPG 才说"照片本身（不是预测）"。回退分支也是 JPG 文案，但 `preview_look` 对每张照片都会给，不会误落到这支。
  - **用语不统一（P2-6）**：LUT 页预览标签叫"中性预览"，导出里叫"中性预览"，图库叫"中性转换"。都是如实的，只是同一件事两个名字。

### 1.3 上一轮已修的 P2（下面表里的编号是上一轮报告里的编号）

| 项 | 我的核对 | 结果 |
|---|---|---|
| 上轮 P2-2 启动锁 | 真起 `gxr-studio`：第二个实例打印"工作室已经开着了：请回到第一个打开的窗口…"，**退出码 75**；通过符号链接路径启动第二个也被挡；`kill -9` 第一个后第三个能正常起（锁随进程消失）。`.command` 对 75 不再多说"已停止"。 | 关闭。小提醒：`LibraryLock` 把任何 `OSError` 都当成"已经开着"，万一图库放在不支持 `flock` 的网络盘上会误报，这条对本地盘无影响 |
| 上轮 P2-8 原子切换 / `.old` 恢复 | 读了 `swap_in`（macOS 用 `renamex_np(RENAME_SWAP)`，不行就退回两步）和 `recover_interrupted_swaps`；测试里有"两步之间被打断→启动恢复""残渣清理""create_app 触发恢复"，我的全量测试里全过 | 关闭（原子路径只在 APFS 上实测，退路由测试覆盖） |
| 上轮 P2-12 CSP | 响应头有 `default-src 'self'; img-src 'self' blob: data:; object-src 'none'; …`；前端只用 `el.style.x=`（CSP 允许），没有内联脚本/样式属性；真 Chrome 里两份走查 + CSP 违规算控制台错误，**0 条** | 关闭 |
| 上轮 P2-4 读 `/Volumes` 的 PermissionError | `probe_h`：把卷根目录 `chmod 000`，`/api/cards` 返回 200 空列表（不是 500），`/api/cards/status` 明说"电脑不让工作室读取外接的存储卡。请打开「系统设置→隐私与安全性→文件和文件夹」…"；恢复后提示消失。走查 A 在真浏览器里也核对了红色横幅。没法在真 macOS 弹窗下验证 | 关闭 |
| 上轮 P2-1 / 5 / 6 / 10 | 上轮 P2-1：探针 a 末尾"旧的损坏内容有备份"= `.corrupt-20261030-…`；上轮 P2-10 多卡提示走查 E 通过；上轮 P2-5、上轮 P2-6 靠测试 + 走查（走查里点"用工作室所在的项目文件夹"导入成功） | 关闭 |
| 没修的 3、9、11、13 | 理由（风险小/要迁移/要用户决定）我认同，不挡试用 | 保留 |

### 1.4 LUT 功能的数据安全与服务安全（上一轮没看到）

我读了 `lut/service.py`、`lut/worker.py`、`lut/cube.py`、`api/lut_routes.py`，另外写了 `probe_g_lut_api.py`（73 项全过，`probe_g.out`）和 `probe_f_lut_orphan.py`（真起服务，`probe_f.out`）：

- **写卡路径：没有。** LUT 代码里没有任何碰卡的调用；`save_recipe` 只写 `home/my_recipes/*.json`，配方里写明 `camera_write: not_supported_yet`，界面也写"写回相机卡的功能还没做好"。我的探针里全程卡目录的哈希/大小/mtime 一字未动，所有写入都落在 `home/`、`lib/` 下。
- **上传限制：** 65 MB 请求体 → 422 `cube_too_big`（边读边拒，不整个收完）；空体、非 UTF-8、尺寸 99999999 / 130、行数不够 / 多出、NaN、inf、引号没闭合的 TITLE、1D 65537、DOMAIN 反了、二进制垃圾、20 万行假 cube 全部 422，没有一个 500。`LUT_3D_SIZE` 上限 129，数据行数有上限，内存可控。
- **路径穿越：** `X-GXR-Filename` 只取 `Path(...).name` 且只用于回显，磁盘上的文件名是内容的 SHA-256（`luts/<64 位十六进制>.cube`）；我试了 `../../../../etc/passwd`、`%2e%2e%2f`、含 NUL、绝对路径、5000 字符，回显都不含路径。`cube_id`、`job_id`、`rid` 都用严格的十六进制正则，`..`、`%2e%2e`、大写、63 位、`photo=../../etc/passwd` 全部 404/4xx。`max_edge`、`which`、`space`、色域、范围越界参数都是 4xx 不是 500。
- **令牌/来源：** 无令牌被拒，只带 cookie 没有 Origin 的 POST 403，错误 Origin 403。
- **拟合子进程能不能取消、会不会残留：**
  - 取消：`cancel` 先 SIGTERM 再 3 秒后 SIGKILL，并写 `cancelled`；已有测试 `test_cancel_kills_the_worker_and_allows_a_new_fit`，全量测试里通过。
  - 服务被 SIGTERM / SIGINT（Ctrl-C）结束：子进程一并结束，0 残留（真起服务测的）。
  - **服务被 SIGHUP（直接关掉终端窗口）或 SIGKILL：子进程会变成孤儿继续跑**（`start_new_session=True`，不会收到 SIGHUP；也没有"父进程没了就退出"的检测）。我的小样本拟合约 20 秒后自己结束；真实照片的拟合会更久，期间占 CPU，不会无限残留，只写它自己的任务目录。README 恰好写着"关掉窗口，工作室就停了"，所以这是用户会碰到的路径。见 P2-4。

### 1.5 回归

- **全量测试：356 个全部通过，331.95 秒**（`pytest_full.out`）。
- **走查（允许 3 个进程：node + 服务 + Chrome，我始终没超过）：**
  - 部分失败走查：**34 项通过 / 0 失败**，浏览器错误 0，4xx/5xx 0。
  - 原走查（修复版副本）：我跑了两次。**第 2 次 87 项通过 / 0 失败**，浏览器错误 0，4xx/5xx 只有 4 条预期的"还没标定时渲染 409"。**第 1 次 77 通过 / 10 失败**：起因是"点开照片后马上点『配方』标签，点在旧页面上"（脚本日志 `tabs=裁切:true,配方:false`），后面"从卡导入"那几项都是连锁失败——这就是修复报告说的脚本时序问题。但那一次**同时记到一条真实的 500**（`/api/photos/<id>/thumb`），我顺藤摸瓜查到根因，见 P2-2。
- **上一轮探针重跑**：a 71 项 0 失败；b 49 项 0 失败；c 4 项 0 失败；d_fixed 8 项 0 失败。

## 2. 问题清单

### P0

无。

### P1

无。

### P2

**P2-1　补全那一瞬间进程被杀，会多出一张同名照片，并丢掉裁切**
- 现象：一对里一半先导入（比如 JPG 读不出，DNG 已进库），用户给 DNG 半张做了裁切；重新插卡继续导入时，`_complete_existing` 先把新来的 JPG `os.replace` 到位，**之后**才写 sidecar 和换索引。如果恰好在两步之间被杀（或 `replace_shot` 抛错），下次导入发现目标位置已有文件，`_complete_existing` 返回 False，落到"新建一张照片"的路径，结果是：同一个 sidecar 路径被**覆盖**（裁切丢了），图库里同时有"只有 DNG"和"只有 JPG"两张同名照片。照片文件本身一个字节都没丢。
- 复现：`probe_e_partial.py` 的情形 I（在 `Library.replace_shot` 上注入失败后重启再导入）：`FAIL I: 中途被杀再来一次后只有一张 R0000102`、`FAIL I: 裁切没有丢`。
- 影响：需要"先有半张 + 用户已编辑 + 补全那几毫秒被杀"三个条件同时成立，很少见；后果是一张重复照片和一条丢失的裁切，用户重新裁一下即可。
- 建议：先写 sidecar 再 `os.replace`，或在发现目标已有同内容文件时识别为"补全残留"继续合并，而不是新建。

**P2-2　导入相机数据 / 标定包时，浏览器正在取缩略图，会偶发 500（缩略图裂图）**
- 现象：导入相机数据或标定包会 `purge_variants` 删掉只有 DNG 的缩略图缓存；`_image` 里 `ensure()` 返回缓存路径之后、`FileResponse` 真正读文件之前，文件被删，就抛 `File at path … does not exist`，返回 500。该张缩略图在页面上显示成破图，刷新后正常。没有数据损坏。
- 复现：`probe_i_thumb_race.py`（3 个线程取缩略图、1 个线程循环 `purge_variants`，25 秒）：`{'ok': 499, '500': 41}`，约 8%。真浏览器里原走查第 1 次运行遇到过一次（id `6ec17dfcb59baa1a`，就是这个探针里的同一张真实 DNG）。
- 建议：`_image` 里捕获这类错误后再 `ensure` 一次，或先把文件字节读进内存再返回。

**P2-3　补全后照片 id 变了，已勾选的照片再批量导出会整批被拒**
- 现象：`POST /api/export` 里只要 `ids` 有一个不存在就整批 404（`_shot_or_404` 在列表推导里先全部检查），界面提示只有"找不到这张照片"，用户不知道是哪张、也不知道要重选。同样的情形也会发生在用户勾选后又在别处删掉/重建照片。
- 复现：`probe_h_sidecar_misc.py` 末尾："批量导出含失效 id → 404"。
- 建议：批量导出里不存在的 id 记为那一张失败（和单张出错一样），其余照常导出；或前端在 `library-changed` 后清理选择集里已经不存在的 id。

**P2-4　关掉终端窗口（SIGHUP）或强杀服务时，拟合子进程变孤儿继续跑**
- 复现：`probe_f_lut_orphan.py`（`probe_f.out`）：term、int 两种 0 残留；hup、kill9 各留下 1 个子进程（PPID=1），约 20 秒后自己结束（真实照片会更久）。
- 影响：只占一会儿 CPU，会写它自己的任务目录，不碰照片和卡。
- 建议：子进程定期检查父进程是否还在（`os.getppid()==1` 就退出），或不要 `start_new_session`，或在服务里处理 SIGHUP。

**P2-5　手改出来的编辑文件（格式对、字段类型错）仍会 500**
- 复现：`probe_h_sidecar_misc.py`：`crop` 写成字符串或缺字段 → `GET /crop` 500；`rev` 写成字符串 → GET/PUT crop、GET/PUT edit 全部 500。程序自己写的 sidecar 不会出现；只有用户手工编辑 JSON 才会。照片文件不受影响。
- 建议：把 sidecar 读出来的内容做一次类型检查，不合格就当"坏了"走已有的改名备份流程。

**P2-6　"中性转换"和"中性预览"两个叫法并存**
- 图库/大图叫"中性转换（不是相机的颜色）"，LUT 预览和导出文件的标签叫"中性预览"。意思一样，都如实。建议统一一个词，免得新手以为是两件事。

## 3. 没做到 / 限制

- 没有在真 macOS 的"可移除的卷"权限弹窗下验证 上轮 P2-4；用 `chmod 000` 和 `PermissionError` 注入代替。
- 原子目录对调只在本机 APFS 上实测；其它文件系统走退路，靠测试覆盖。
- 没有在真终端里双击两次 `.command`；用的是同一份代码路径（`gxr-studio` 直接启动两次）。
- 没有测 28mm / MOUNT 的真实 DNG（没有样本）。
- 05c 截图里大图是黑的：我另外用同一张真实 DNG（R8051145）在进程内取预览，亮度正常（平均 128/255），所以那是截图时图片还没载入，不是应用问题。
- 走查第 1 次的 10 项失败是脚本时序造成的，第 2 次全过；我没有为此改走查脚本。
- 没有读 `studio/` 以外的代码，没有联网，没有碰相机和真实卡（所有目录都在 `Scratch/rv_sfix/`，结束时已删除；Chrome、服务、拟合子进程都已确认退出，机器上没有我留下的进程）。

## 4. 复现方式

```bash
cd <仓库根>
# 全量测试（356 个，约 5.5 分钟）
cd studio && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<临时目录>/pt
cd ..
# 上一轮探针重跑
studio/.venv/bin/python -I research/review_studio_m2/probe_a.py <临时目录>/a
studio/.venv/bin/python -I research/review_studio_m2/probe_b.py <临时目录>/b $PWD
studio/.venv/bin/python -I research/review_studio_m2/probe_c.py <临时目录>/c $PWD
studio/.venv/bin/python -I research/studio_fix_review/probe_d_fixed.py <临时目录>/d $PWD
# 本轮新探针（都在 research/review_studio_fix/）
studio/.venv/bin/python -I research/review_studio_fix/probe_e_partial.py <临时目录>/e $PWD        # 部分失败 10 种情形 + 补全 + 被杀（P2-1 = 最后 2 项 FAIL）
studio/.venv/bin/python -I research/review_studio_fix/probe_f_lut_orphan.py <临时目录>/f $PWD     # 拟合子进程残留（P2-4）
studio/.venv/bin/python -I research/review_studio_fix/probe_g_lut_api.py <临时目录>/g             # LUT 接口安全 73 项
studio/.venv/bin/python -I research/review_studio_fix/probe_h_sidecar_misc.py <临时目录>/h        # 怪的 sidecar、失效 id、卷根权限（P2-3、P2-5）
studio/.venv/bin/python -I research/review_studio_fix/probe_i_thumb_race.py <临时目录>/i $PWD    # 缩略图 500（P2-2）
studio/.venv/bin/python -I research/review_studio_fix/probe_j_rawonly_brightness.py <临时目录>/j $PWD [R8051145]   # 只有 RAW 的标注和亮度
# 走查（需要 Chrome、node；脚本在本目录，截图/结果也写在本目录；TMPDIR 指到临时目录）
node research/review_studio_fix/browser_walkthrough_partial_import.mjs
node research/review_studio_fix/browser_walkthrough_integration.mjs     # 我只加了把服务日志写到 server_integration.log
```

探针 e、h 的"FAIL"行就是上面对应的 P2（e：`I:` 两项；h：crop 是字符串/缺字段、rev 是字符串）；其余都是 PASS。输出文件：`probe_e.out`、`probe_f.out`、`probe_g.out`、`probe_h.out`、`probe_i.out`、`probe_j*.out`、`rerun_probe_*.out`、`pytest_full.out`、`walkthrough_*`、`screenshots/`。
