修改后再提交

本轮发现 8 项 P1。换卡后的前端结果归属、导入证明的有效期、图库文件校验和系统文件分类仍有漏导后显示成功的路径；标定导入存在向卡写入的路径；提交内容检查和有限数校验也有缺口。两组改动目前均不放行。

复审日期：2026-11-01。对象是独立仓库 `studio/` 相对 HEAD 的全部工作区改动，包括未跟踪文件。HEAD 为 `1407830ee7c32fff892b23f2ddbfeb2bafd95b45`，共 30 个已跟踪改动和 11 个未跟踪文件。复审及运行绑定 `evidence/source_manifest.json` 中的 229 个文件摘要，而非仅绑定 HEAD。

## P1

### P1-01：旧卡任务的成功结果会套到新卡，新卡没有导入请求仍显示“都已导入”

位置：`studio/web/assets/import.js:43-46、:119-127、:260-262`；`studio/src/gxr_studio/jobs.py:29-31`。

A 卡任务已在服务端完成，页面还保留上次轮询的 `running=true`。这时换成 B 卡，`refreshCards()` 载入 B 的摘要，却因 `isImporting()` 为真跳过导入。下一次轮询取得 A 的成功结果，`tickImport()` 把当前的 B 卡 id 加入 `handled`。之后同一个 B 卡 id 不再触发发现分支，状态栏和横幅继续使用 A 的结果。

主机已证：运行未修改的 `import.js`，只替换 API 和 DOM 边界。B 卡摘要为 `shots=3、new_shots=3、verified=false`，整个请求序列中 `POST /api/import` 次数为 0，横幅却是“这张存储卡上的照片都已导入”，状态栏是“存储卡：可以推出”。证据为 `evidence/repro-frontend.json`，复现脚本为 `evidence/repro_frontend.mjs`。这是模块执行结果，未作浏览器视觉验收。

最小修正：任务及其结果必须携带来源挂载会话 id，前端按任务来源更新 `handled`，仅为同一会话显示成功。忙碌时发现的新卡须排队，或在恢复空闲时重新判断是否需要导入，不能仅在 id 刚变化时判断。补上上述轮询时序用例。

### P1-02：导入丢弃了完整挂载指纹，结束核对会复用另一挂载之前的内容证明

位置：`studio/src/gxr_studio/api/routes.py:115-118、:352-366`；`studio/src/gxr_studio/cards/coverage.py:33-37、:132-140`；`studio/src/gxr_studio/cards/importer.py:145-146、:394-414`。

接口把会话压缩成 UUID 和根目录 `(dev, ino)` 后交给导入，未保留 `f_fsid`、设备来源或可重新解析该会话的能力。导入中没有再验证完整会话。结束时只要相对路径、长度、mtime 未变，就复用 `_Run.proofs` 的旧 SHA，不再读取当前内容。

主机已证：沿用项目 `FakeProbe` 的重挂载模型，先导入 A，再于第二次导入的一张照片处理结束后，替换为同路径、同长度、同 mtime 的 B 内容，并改变 statfs 指纹。登记表随后解析旧会话会返回 404；该导入仍返回 `all_imported=true` 和“都已导入”，B 内容的 SHA 不在图库实际文件中。更换为不同根 inode 的对照用例会正确返回 `root_changed`，所以缺口是完整会话及证明归属，而非根目录检查完全无效。见 `evidence/repro-photos.json` 的 `mid_import_remount` 和 `different_root_inode`。

这个结果证明模型内的控制流缺口；本轮未验证真实 FAT 卡重挂载后 dev/ino 是否复用。独立于重挂载，文件在读后被等长改写并恢复 mtime，也会满足目前的旧证明条件。

最小修正：把完整会话核验带进导入，至少在读取边界和发布最终成功结果前重新验证；会话变化立即中断，清除该会话的证明。内容证明还须绑定实际读取的文件状态，不能仅以路径、长度和 mtime 认定读后仍未变化。

### P1-03：图库里同长度的错误内容被当成原照片，读了卡也会漏导并报“都已导入”

位置：`studio/src/gxr_studio/library/store.py:239-251`；`studio/src/gxr_studio/cards/importer.py:580-585`。

`sha_in_library()` 按索引中的旧 SHA 查找后，只检查目标文件当前的长度。图库文件在外部被等长替换、损坏或改写，旧 SHA 不再描述磁盘内容，但函数仍返回真。默认关闭 UUID 信任并不能阻止这条路径，因为卡上的内容虽被重新哈希，图库端仍使用旧索引作证明。

主机已证：导入一张 6000 B 合成照片，把图库文件替换成另一份 6000 B 内容，再导入原卡。结果是 `copied_files=0、all_imported=true` 和“都已导入”。原照片 SHA 为 `7a8a811fed6b76472057c97e62043a72e3b4c2f1b74e6fb49c986db017cad268`，图库实际文件 SHA 为 `4c54eccd601297aad367dadc92be10c434caf5461b6fa7f793d62fad8c346dfe`；独立读取图库文件确认原内容不存在。见 `evidence/repro-photos.json` 的 `same_size_library_replacement`。

最小修正：成功证明必须核对图库当前普通文件的内容，或使用能可靠发现外部变化、变化后强制重算 SHA 的文件校验记录。照片和视频应共用这一规则；发现不一致时重新保存卡上原件，同时保留外部修改的文件，不能继续相信旧索引。

### P1-04：系统文件规则只看名字，把可解码照片排除后仍报全部导入

位置：`studio/src/gxr_studio/cards/discovery.py:253-263、:358-360`；`studio/tests/test_a1a_photos.py:238-285`。

规则把任何 `._*` 文件，以及名字属于 `MAC_SYSTEM_DIRS` 的目录内所有文件，直接归为系统文件。它不核对 AppleDouble 等实际格式，也不保守保留媒体文件。`scan_card()` 跳过这些路径，严格核对又把它们从未导入列表排除，两边共同遗漏。

主机已证：在 DCIM 下放入三个由 Pillow 生成并成功解码的真实 JPEG 格式合成图像，路径分别为 `100RICOH/._R0090001.JPG`、`100RICOH/.Spotlight-V100/R0090002.JPG` 和 `.Trashes/501/R0090003.JPG`。三者均进入 `system_files`，没有复制到图库，第二次导入仍返回“都已导入”。见 `evidence/repro-photos.json` 的 `system_rule_real_photos`。现有测试还明确断言忽略 `.Trashes` 内的 JPG，因此“仅覆盖 macOS 名字”的测试不能证明没有忽略照片。

最小修正：对 `._*` 校验元数据格式；DCIM 内出现可识别的照片或视频时保留为需处理项目，不能仅因目录名就给出全部导入证明。如果产品要排除废纸篓内的媒体，成功提示须明确其范围，并在照片保护状态中列出这些文件。

### P1-05：产品的标定写入没有使用目录 fd 守卫，检查后换向可写进受保护卡

位置：`studio/src/gxr_studio/camdata/calib.py:79-83、:105-116`；`camdata/store.py:65、:86-105、:129-137`；`api/camdata_routes.py:223-229`；`privacy.py:109-152`，后三个路径均在 `studio/src/gxr_studio/` 下。

`privacy.private_write()` 提供了不跟随链接的目录 fd 写入，但相机数据和标定入口仍直接用路径执行 `mkdir/open/np.savez/copyfile/replace`。API 里的禁止卷根检查只在开始时执行一次，底层再次检查又未传入这些禁止目录。路径在检查后换向，写入会跟随新链接。现有审计按路径字符串判断，未把后来增加的这个别名对应到原卡根。

主机已证：使用全合成 stock、NPZ 和 JSON，通过一次包含卡根/卷根的真实预检查，再于底层真实检查成功返回后，把应用数据目录换成指向受保护假卡的链接。未替换任何写入函数，`calib.import_calibration()` 成功返回，并实际在假卡创建 `calib/ctx_200.npz`、`calib/ring_model_200.json`、`calib/manifest.json`。卡上原照片未变，但“零写卡”门槛已不满足。见 `evidence/repro-privacy.json` 的 `calibration_alias_race`。

同一脚本的目录 fd 移动对照中，`private_write()` 通过 `F_GETPATH=50` 正确拒绝，假仓库没有 blob。问题在产品入口没有接上这条写入路径。现有 PR02 换向测试只调用辅助函数，没有覆盖真实标定写入。

最小修正：让相机数据、标定及目录替换共用经验证的目录能力，传递完整禁止目录集合，后续创建、复制及替换均相对持有的目录 fd 执行。在真实产品入口补齐检查后换向的用例，断言假卡零新增、零写入。

### P1-06：pre-commit 检查工作文件而非暂存区 blob，现有测试抓不到完全关闭暂存检查

位置：`studio/scripts/private_bytes.py:164-172、:188-189、:213-216`；`studio/tests/test_a1a_privacy.py:215-233`。

`git diff --cached` 在这里仅提供路径，后续 `p.read_bytes()` 读取工作区当前内容。若暂存区保存了受限内容，工作文件已改回普通文本，检查通过；工作文件被移走时，还会被 `is_file()` 直接过滤。提交读取的仍是暂存区原 blob。

静态已证该数据来源错误。主机小检查在不写 Git 索引的前提下提供暂存路径列表，确认检查实际采用普通工作文件，且会排除工作文件已消失的条目。未执行 `git add` 或 `git commit`。

测试变异另有主机证据：仅在独立副本把 `staged_files()` 改成恒返空列表，整份 `test_a1a_privacy.py` 仍为 `16 passed`。PR03 用例把 `staged_files` 整个替换掉，因此未检验真正的暂存读取逻辑。见 `evidence/mutation-staged.patch`、`evidence/mutation-staged.log` 和 `evidence/repro-privacy.json`。

最小修正：按暂存区对象 id 读取 blob 字节，例如使用只读 `git cat-file`，不以工作文件存在性或工作文件内容代替。测试必须覆盖暂存区与工作区内容不同，以及暂存文件在工作区已不存在的情况。

### P1-07：内容检查对换行编码和超过归档深度的内容直接放行

位置：`studio/scripts/private_bytes.py:53-57、:92-105、:156-161`。

hex/base64 只识别单段连续不少于 512 字符的串。标准 76 列 base64 或 64 列 hex 即使包含完整文件，也不会进入解码检查。归档达到深度上限后直接停止扫描，不报告未检查内容。

主机已证：同一个带 `GXRCE001` 头的 2048 B 全合成输入，原文件和单行 base64 退出 1；按 76 列换行的完整 base64、按 64 列换行的完整 hex、五层压缩 ZIP 都退出 0 且 `hits=[]`。脚本先独立反解，确认两个换行编码仍完整等于原输入。四层 ZIP 的对照退出 1。见 `evidence/repro-privacy.json`。

最小修正：识别完整的常见换行编码块并在总量限制内解码；无法检查的归档深度、成员尺寸或展开量应使检查失败，并说明哪个成员未检查，不能当作无命中通过。将这些用例加入提交和分发两条路径。

### P1-08：零分母容忍范围扩到了渲染字段，仍可静默降级或产生 NaN 像素码值

位置：`studio/src/gxr_studio/lut/scene.py:65-68`；`raw/dng.py:80、:133-146、:229-233`；`lut/colorimetry.py:182-183`，后两个路径均在 `studio/src/gxr_studio/` 下。

`mat()` 把存在但含 NaN 的矩阵当成缺失。`CameraCalibration1` 含零分母时，下游会换用单位矩阵；`ForwardMatrix1` 同样会被忽略，未拒绝这个渲染输入。另一个入口是未列入 `_check_finite()` 的 `lin_table`：TIFF 类型不符合预期时，零分母值可直接进入线性化计算。

主机已证：有正常 ColorMatrix 的合成 DNG，分别放入零分母的 CameraCalibration1 和 ForwardMatrix1，`scene_colour()` 均成功返回并产生有限 XYZ，没有报错。把合成 LinearizationTable 的 TIFF 类型改为 RATIONAL 并填零分母后，`open_dng()` 也成功，`half_res_codes()` 的 48 个值全部非有限。后一个用例是畸形 TIFF 类型输入，并非本轮观察到的真机文件。见 `evidence/repro-mount.json`。

最小修正：区分“标签不存在”和“标签存在但非法”，渲染使用的标签若存在且非有限须明确拒绝；检查 LinearizationTable 的类型和有限性。为可容忍的 LensInfo、未知 EXIF 显示字段保留单独规则。

## P2

### P2-01：图库文件被截断后，重复导入不能修复，界面却持续建议重试

位置：`studio/src/gxr_studio/library/store.py:199-205`；`studio/src/gxr_studio/cards/importer.py:629-633`；`studio/tests/test_a1a_photos.py:390-393`。

长度不符时新的覆盖检查正确阻止成功提示，但旧 `sha_present()` 仍只检查路径存在。导入重新复制并校验好原件后，又把它当成重复内容丢弃。主机复现中，6000 B 图库文件被截为 1 B，重试后仍为 1 B，`copied_files=0`。它如实提示一个文件未导入，因此此项按 P2；“重试即可恢复”的使用路径未闭合。见 `evidence/repro-photos.json` 的 `truncated_library_file`。

最小修正：合并 P1-03 的有效文件判定，不能因索引和路径还在就丢弃正确的暂存原件；加上重试后实际文件字节恢复的断言。现有 PH05 的长度分支明确接受了重试后仍未导入的结果。

## 检查结果和覆盖范围

最终在未修改源码和测试的副本中完整执行 `make check`，退出码为 0。结果为 `606 passed、3 warnings`，耗时 386.88 秒；覆盖率为 91.70%，9716 条语句中 806 条未覆盖，超过仓库的 85% 门槛。606 个通过与实现者自述一致；覆盖率与自述 91.67% 相差 0.03 个百分点，不写成完全相同。lint、format、strict mypy、安全检查、导入分层、依赖、重复代码、OpenAPI 及私有字节检查均通过。离线 sdist/wheel 构建完成，内容检查输出 `private bytes: checked 232 files`。完整日志见 `evidence/make-check.log`。通过套件不能关闭上面的独立反例。

pre-commit 的调用已接入：原仓库 `core.hooksPath=.githooks`，钩子权限为 0755，`.githooks/pre-commit:9` 执行 `scripts/private_bytes.py --staged`；`Makefile:29` 的 `--tracked --dist` 在完整运行日志中实际执行。本轮没有执行 Git 提交。当前源文件和构建输出未观察到误报，短魔数字面量的允许用例也通过；漏检见 P1-06、P1-07。

两次完整运行之间只改了审阅沙箱和隔离环境，没有修改冻结的产品源码或测试。前一次结果为 `603 passed、3 failed、3 rerun`，覆盖率 91.18%，失败原因是审阅沙箱禁止了逐级打开 `/Volumes` 和本机随机端口绑定，详见 `evidence/make-check-isolation-failure.log`。修正后先定点复验这三个测试，`3 passed`，再重跑完整检查。更早的隔离缓存缺少构建依赖索引及构建后端依赖等失败保留在 `evidence/` 的环境日志里，没有重标为产品通过。

测试质量抽查结果如下。

| 检查 | 实际结果及证明范围 |
|---|---|
| ID01、ID02、ID03、ID08 | 核对了同挂载名且同元数据不同内容、UUID 缺失/重复、会话碰撞、非法 id、参数数组与超时的实现及断言。普通的两卡先后导入漏洞已有覆盖，不能覆盖 P1-01 的前端时序或 P1-02 的导入中换挂载。 |
| DC02、PH01、PH02、PH05 | 检查了根/DCIM/子目录/stat 的 EACCES、EIO、ENXIO 注入，真实权限位、文件移走、读取计数、长度不符及信任条件。PH01 变异对照中，故意让 UUID seen 绕过关闭的信任开关，测试在“每个文件正好读一次”断言失败。 |
| PR02、PR03 | PR02 的辅助函数测试没有覆盖真实写入入口；PR03 没有覆盖实际暂存 blob。完全关闭暂存枚举后 16 个隐私测试仍通过。详见 P1-05、P1-06。 |
| 前端 | `import_summary.js` 对缺少 coverage、扫描失败、uncovered 和 not_importable 的纯函数路径有检查；实际 `import.js` 的任务与卡会话归属缺少检查，独立模块复现确认失败。 |
| MOUNT DNG | LensInfo 零分母、EXIF 的未知值、未知光圈不显示为 f/0、元数据 API、RAW-only 导出保留 EXIF 的路径已检查。白平衡、AnalogBalance、BaselineExposure 的现有拒绝路径有效，剩余缺口见 P1-08。 |

独立反例还检查了三个正常/拒绝对照。

- 同主名 DNG、JPG 和 AVI 分别保存，独立读取确认三份内容都在图库；重建后为一张照片和一个视频，导入期间记录的卡写入为零。
- DCIM 内的链接列入 `not_importable`，未给出全部导入证明；不同根 inode 的换卡返回 `root_changed`。
- 用目录 fd 创建绝对路径长 1381 字符的媒体文件。严格扫描能看到它，按路径读取失败后结果不完整，明确提示未导入，没有误报全部导入。

这些是主机、源码及合成文件系统结果。没有访问真实存储卡、用户工作室实例或用户图库，没有验证真卡 UUID/设备节点复用，也没有相机或物理卡验收。AVI 行为按本轮要求原样导入；旧设计 PH03 中把 AVI 归为不会导入的描述应随实现同步更新。

## 隔离、输入和清理

写入前核实 `/Volumes/Workspace` 是可写 APFS 卷，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，并读取盘根 `AGENTS.md`。

原 `studio/` 仅读取。临时副本、变异副本、依赖副本、uv 缓存、TMPDIR、pytest basetemp 和所有合成卡均在 `/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-a1a/` 内。副本中的 `.git` 是文件复制所得，没有执行 Git 写命令，没有使用 worktree。复用依赖时仅在临时副本中改写虚拟环境启动脚本和 editable 路径，所有 `uv` 调用离线；构建后端及其依赖从本机缓存复制到隔离缓存和构建环境，没有下载。

本机现有 `captures/`、`research/` 和 `firmware/` 仅作为沙箱内测试的外部只读夹具映射；目录 fd 和写入白名单限制写入到上述临时根，无法写回这些输入。复审产物保留日志、脚本和摘要，不保存真实 DAT、原始表或照片字节。私有字节反例全部现场生成。

进程级 sandbox 禁止对外及本机的出站连接，仅允许测试启动器在 localhost 绑定/监听随机端口；未向任何服务发连接。真实图库、导出和应用数据路径被禁止读取，临时根外禁止写入。没有访问或重启 `127.0.0.1:49667`，没有访问存储卡，没有联网或启动子代理。未同时运行两个 pytest 批次；只有两个不产生子测试进程的小反例曾并行。执行偏差：原有 `tests/test_polish_p2.py:155` 的父进程退出用例会短暂同时存在 pytest、辅助父进程及 worker，共 3 个 Python 进程。编排时漏算了这条内部派生，因此按全部辅助进程计数的“最多 2 个测试进程”限制未满足，不能作为已满足的隔离项。此偏差不改变源码反例的 P1 判断。

最终回执见 `evidence/receipt.json`。229 个源文件内容/模式、HEAD、Git status 以及原仓库的 HEAD/index/config 摘要均与开始时一致。临时副本、变异副本、假卡、pytest 目录、依赖和缓存已全部删除，并确认指定临时根不再存在。

复现脚本的断言确认的是本轮观察到的结果，其中包括错误的放行结果；修复后应把这些场景改写成预期拒绝或正确保存内容的回归测试。脚本只接受指定临时根内的副本/运行目录，不能直接拿原工作区作为运行目标。

`SHA256SUMS` 同时记录报告、证据及 229 个冻结仓库输入，路径相对 Projectricoh 主目录。清单不包含自身。复核命令：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
shasum -a 256 -c research/review_studio_a1a/SHA256SUMS
```
