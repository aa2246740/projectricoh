"""Render the review from independently checked evidence, without changing Studio."""
import datetime
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
WT='/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview'
read=lambda n:json.loads((HERE/n).read_text())
summary=read('verified-summary.json');cleanup=read('cleanup.json')
assert summary['p1_count']==4 and cleanup['temporary_root_removed'] and not cleanup['changed_tracked_source_files']
metal=read('real-parity-metal.json');swift=read('real-parity-swiftshader.json')
build=read('build-byte-comparison.json')['outputs']['committed'][0]
exhaustive=read('exhaustive-lut.json');perf=read('perf-adjust-warm.json')
ci=read('ci-final.json');assert ci['headSha']=='72d9b44aa62d5133565117d533041bad9a76cdc5'
windows=next(j for j in ci['jobs'] if j['name']=='tests (windows-latest)')
assert windows['status']!='completed','A completed Windows run needs its log reviewed before this pending-CI report is used.'
ci_time=datetime.datetime.fromtimestamp((HERE/'ci-final.json').stat().st_mtime,datetime.timezone.utc).isoformat()
colour_rows=[]
for m,s in zip(metal,swift):
    assert m['id']==s['id'] and m['pass'] and s['pass']
    colour_rows.append(f"| {m['id']} | {m['over_1']}/{m['pixels']} | {m['mean_de00']:.12g} | {m['max_code']} | {s['over_1']}/{s['pixels']} | {s['mean_de00']:.12g} | {s['max_code']} | 通过 |")
text='''不能合并
开关默认值建议：保持 `gpu_preview=false`。当前有 4 项已复现的 P1；关闭开关不能屏蔽直接文件接口或 Windows 平台 I/O 分支，不能据此放行合并。

## 首轮 9 项复核

| 首轮编号 | 判定 | 独立核实与证据 |
| --- | --- | --- |
| P1-01，图库外链接读取 | 未关闭 | 原来的文件链接和中间目录链接均被拒绝；图库根目录在校验后被替换时，`/raw` 返回外部字节、Range 返回 206，`/gpu` 还解析了外部 DNG。见 [旧脚本结果](api-probes.json)、[新 API 反例](http-boundary-extra.json)、[两种打开实现对照](media-root-race.json)。 |
| P1-02，资源不随数据/LUT 版本失效 | 未关闭 | g127→g155、普通 LUT 修改、旧成功/失败迟到均通过；删除并重导入相同 LUT 后版本号复用，仍命中旧色彩空间的表。见 [实际相机数据切换](camdata-ui-probe.json)、[实际 LUT 生命周期](lut-ui-lifecycle.json)、[预取跨代模型](prefetch-generation.json)、[删除重导入反例](lut-reimport-probe.json)。 |
| P1-03，显示类 LUT 颜色门槛 | 本轮冻结用例通过 | Metal、SwiftShader 各 14 组真实输入及 2 个首轮全合成反例通过；两个目标的 256³ 全输入与生产函数逐值相同。见 [Metal](real-parity-metal.json)、[SwiftShader](real-parity-swiftshader.json)、[穷举](exhaustive-lut.json)。版本复用造成的错表另计 P1-02。 |
| P1-04，Windows 收集失败 | 静态阻塞已修；Windows 完整运行待 CI | Unix 专有导入已收进平台分支，darwin/win32 mypy 均通过。工作流在 Windows/macOS 跑完整套件；macOS 实跑通过，Windows 尚未结束，不能写成 Windows 验收通过。见 [修复差异](repair.diff)、[make check](make-check.log)、[CI 原始状态](ci-final.json)。新平台边界问题另列下表。 |
| P2-01，box 校验 | 已修 | 原 NaN 和非法裁切均返回 JSON 422；严格整数、未知键、像素预算、几何/裁切异常的测试也实际运行。见 [首轮脚本复跑](api-probes.json)、[完整测试回执](make-check-receipt.json)。 |
| P2-02，同键资源覆盖 | 已修 | 同键添加 12 次，覆盖时明确销毁 11 份旧缓冲/纹理；dispose 后全部销毁。LUT 上限 3、烘焙表上限 24。见 [真实 Metal 分配记录](table-resource-probe.json)、[首轮脚本复跑](state-probes.json)。 |
| P2-03，预取重复请求 | 已修 | 25 次实际界面暖路径输入没有额外邻图 edit GET；受控预取跨代的旧成功、旧失败均未装入旧烘焙表。见 [界面/网络记录](perf-adjust-warm.json)、[预取模型](prefetch-generation.json)。 |
| P2-04，关闭仍请求 /gpu、解析 DNG | 渲染路径已修 | 实际页面 `/gpu` 请求、adapter/device 创建均为 0；关闭分支的 RAW 布局和烘焙预热调用均为 0；14 组基线渲染对照通过，响应范围和 ICC 差异见后文。见 [回退](fallback-probes.json)、[解析调用计数](flag-off-api-probe.json)、[基线对照](baseline-comparison.json)。 |
| P2-05，GET /table 写盘 | 已修 | 原旧 attribution_version 反例的写记录为 0；真实隔离数据上的六个接口全部 200、写记录为 0。见 [旧格式复跑](api-probes.json)、[六接口审计](real-api-readonly.json)。 |

## 新发现

| 编号 | 级别 | 结果与最小修正方向 |
| --- | --- | --- |
| R2-P1-01，按路径删除越界 | P1 | `_PathPrivateDir.remove()` 在最后检查后按完整路径 unlink。中间目录替换成链接后，外部文件被删除且没有异常；Unix 对照没有删除外部文件。删除应绑定已核对的对象/父目录句柄，不能只在按名删除前重复检查。见 [复现](path-delete-race.json)。 |
| R2-P1-02，严格扫描目录句柄被重定向 | P1 | `PathCardReader` 的伪句柄仅保存路径。fstat 之后替换中间目录，严格扫描读取了外部字节、把外部 JPG 列为照片，仍报 complete=true、errors=[]。应保存并验证目录身份，读取绑定实际打开的文件句柄；无法保证时拒绝扫描。见 [复现与 Unix 对照](card-reader-retarget.json)。 |
| R2-P2-01，Range 数字解析泄漏 fd | P2 | 5,000 位起始偏移触发 int 转换异常。12 次请求均为 500，fd 从 7 增至 19。应有界解析 Range，并在 Response 构造失败时关闭已取得的 fd。见 [实际 API 计数](http-boundary-extra.json)。 |

## 阻塞项的触发点和修正建议

### P1-01 仍可从图库外读文件

[`library/media.py:51`]('''+WT+'''/src/gxr_studio/library/media.py:51) 对子路径使用 `O_NOFOLLOW`，但根目录的第一次 open 没有该标志，也没有核对已打开根目录的真实位置。`open_media()` 的 `is_local(root)` 是此前的一次路径检查。

本轮在该检查之后、真正打开根目录之前，将临时图库根目录挪开并放入指向临时外部目录的链接。`/raw` 返回 200 和外部标记字节；`/camera-jpg` 的 `bytes=0-6` 返回 206 和 `OUTSIDE`；清空布局缓存后，`/gpu` 返回外部合成 DNG 的 16 位、96×64 布局，原文件是 12 位、120×80。路径版在同一根目录替换反例中拒绝读取。

最小修正是把根目录也纳入不跟随链接的目录句柄遍历，并对实际打开的目录/文件执行位置约束；不能继续在检查后按根路径重开。增加根目录及其祖先目录替换、Range 和布局解析的共同反例。[脚本](http_boundary_extra.py)、[结果](http-boundary-extra.json)。

### P1-02 删除重导入后命中旧 LUT 表

[`api/gpu_routes.py:201`]('''+WT+'''/src/gxr_studio/api/gpu_routes.py:201) 按 `(cube_id, render_token)` 缓存表；`LutLibrary.render_token()` 只绑定 cube_id 和记录 version，而新导入记录的 version 会重新从 1 开始。

通过正式 API 依次上传合成 LUT、设为 sRGB、请求表、删除、重传相同字节、改设 Rec.709。两次记录均为 version=2，得到完全相同的 key、ETag 和表 SHA-256。输入 `[64,128,192]` 的当前生产函数应输出 `[42,112,194]`，GPU 表仍输出旧值 `[55,124,202]`。这会使预览与当前服务器出图/导出不一致。

最小修正是在同一个读取快照内，以实际颜色规范或不复用的实例版本生成 token，同时用于服务器与客户端缓存。只清前端 Map 不足以修复服务器的旧表命中。增加删除、重导入、再次修改色彩空间的往返用例。[脚本](lut_reimport_probe.py)、[结果](lut-reimport-probe.json)。

### R2-P1-01 新的删除实现没有保持 Unix 边界

[`privacy.py:548`]('''+WT+'''/src/gxr_studio/privacy.py:548) 先解析路径、lstat，随后在第 570 行按完整路径 unlink。复现在最后一次 unlink 前替换 `home/a/b`；路径版删除了外部 `victim.txt`，原目录中的文件反而保留，整个操作未报错。Unix 目录 fd 对照删除的是原目录内文件，外部文件保留。

该问题在 Windows 选择的 `_PathPrivateDir` 实际代码上复现，宿主是 macOS，使用目录链接模拟重定向；这不是 Windows 实机锁或目录联接验收。反例说明当前 Python 路径算法缺少对象绑定，增加一次 lstat 仍会留下同类间隔。[脚本](path_delete_race.py)、[结果](path-delete-race.json)。

### R2-P1-02 新的严格扫描使用可变路径代替目录句柄

[`cards/discovery.py:135`]('''+WT+'''/src/gxr_studio/cards/discovery.py:135) 将路径存入 `_dirs`，后续 listdir/stat/read_head 都重新解释该路径。复现在严格扫描完成该目录的 fstat 后、listdir 前替换 `DCIM/100RICOH`。路径版读出外部合成字节前缀，并把 `DCIM/100RICOH/OUTSIDE.JPG` 作为照片返回；Unix 对照只返回 `OWN.JPG`。

这是生产严格扫描的 `_is_system` 分支自行读取外部 `.DS_Store` 所得的字节前缀，探针只记录调用，不添加额外读取。初版附加读取的记录另保留为 [helper 记录](card-reader-retarget-helper.json)，不作为生产扫描读取的依据。

这也是在 macOS 执行 Windows 选用的实际路径类所得的逻辑反例，没有接触真实卡，也没有把模拟链接称为 Windows junction 实测。最小修正是为伪句柄保存身份并保持后续操作绑定，读完路径上的最后一级 lstat 不能证明父目录仍是原目录。[脚本](card_reader_retarget.py)、[结果](card-reader-retarget.json)。

### R2-P2-01 Response 构造失败没有释放 fd

[`library/media.py:122`]('''+WT+'''/src/gxr_studio/library/media.py:122) 直接把任意长度的数字传给 int；异常发生在 `FdResponse.__init__`，尚未进入带 finally 关闭 fd 的 `__call__`。既要修 Range 解析，也要让构造失败时的 fd 所有权有明确释放路径。[脚本](http_boundary_extra.py)、[结果](http-boundary-extra.json)。

## 颜色门槛与精确表

参考图由生产 RAW、配方链、LUT 和 `finish_array` 在 JPEG 压缩前生成；比较的是 GPU 1:1 成片纹理。Metal 实际适配器是 `apple/metal-3`、fallback=false，SwiftShader 是 `google/swiftshader`、fallback=true。均使用固定 Playwright 1.61.1 / Chromium Headless Shell 1228。见 [Metal 路由](real-route-metal.json)、[SwiftShader 路由](real-route-swiftshader.json)。

每个用例按 `over_1 × 10000 <= N` 和未舍入的平均 ΔE00 判定。带外最大差不超过 4；带外 >2 的点必须位于首轮冻结集合且由实际 GPU 第一段输出前向复算解释；带内 >2 个数不超过 `ceil(N×10⁻⁶)`。下表均值仅缩短显示，判定使用 JSON 的原始值。

| 用例 | Metal >1 像素/N | Metal 平均 ΔE00 | 最大差 | SwiftShader >1 像素/N | SwiftShader 平均 ΔE00 | 最大差 | 门槛 |
| --- | --- | --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(colour_rows)+'''

- `c_recipe04_curve_extra` 两种适配器各有 7 个带外 >2 的点，位置、数量和差值上限均与首轮各自的冻结集合一致。实际读回配方/曲线第一段，再交给生产 `apply_extra`，7/7 个最终异常像素逐字节吻合；没有用“存在某种 ±1 偏移”代替实际输入。见 [Metal 分段复算](rounding-trace-metal.json)、[SwiftShader 分段复算](rounding-trace-swiftshader.json)。
- `m_uncropped_straighten` 的唯一 24 码值点是 `(x=91,y=1304)`，位于有效区边缘带内，1 ≤ ceil(3,053,056×10⁻⁶)=4。float64 源 y 为 1423.001021922912，阈值为 1423.001；float32 重算后二者都是 1423.0009765625。带外最大差为 1。见 [本轮重算](geometry-boundary-cause.json)。
- 首轮两个全合成反例在两个适配器上均为 over_1=0、平均 ΔE00=0、最大差=0。见 [Metal](synthetic-lut-counterexample-metal.json)、[SwiftShader](synthetic-lut-counterexample-swiftshader.json)。
- 另用首轮分块 ΔE 参考脚本独立复算，所有像素计数和均值与本轮门槛结果一致。见 [数值交叉核对](verified-summary.json)、[独立 Metal 统计](independent-parity-metal.json)、[独立 SwiftShader 统计](independent-parity-swiftshader.json)。边缘带放行使用本轮严格蒙版，不使用首轮脚本的额外画面边缘统计。

实现里的“every input”测试实际抽查 20,004 个输入。本轮另外对两个目标分别穷举全部 16,777,216 个 RGB 输入，并与生产 `_apply` 逐值比较：一个是首轮反例 LUT，另一个含 1D shaper、Rec.709、legal range、色域覆盖和 V-Log 输出；两者均为零差异、alpha 全为 255。见 [独立穷举脚本](exhaustive_lut.py)、[结果](exhaustive-lut.json)。

实际界面在表被有意延迟交付时先显示已成功解码的服务器 blob 图，再切换到 GPU。旧代成功和 503 失败在新代表已经显示后释放，均未安装旧表，也未改变当前表。g127→g155 的实际界面结果与强制获取的新烘焙表一致。见 [LUT 生命周期](lut-ui-lifecycle.json)、[相机数据切换](camdata-ui-probe.json)。预取迟到测试使用实际 gpu_stage/state 模块和受控传输/GPU 替身，属于模型证据，见 [记录](prefetch-generation.json)。
'''
text+=f'''
每张精确表为 67,108,864 B，即 64 MiB。服务器缓存最多两张，共 128 MiB 表字节；GPU 最多三张，共 192 MiB 的请求纹理分配。同键覆盖、淘汰和 dispose 的显式销毁均已核对。旧版本资源不会在事件发生时立即全部销毁，而是受这些上限约束；P1-02 证明了版本标识复用时旧表仍会被命中。见 [资源记录](table-resource-probe.json)、[源图 LRU](resource-probe.json)。没有把分配请求或 Map 大小当作驱动实际显存读数。

两个穷举目标的冷算表耗时分别为 {exhaustive[0]['generation_seconds']:.3f} s、{exhaustive[1]['generation_seconds']:.3f} s，穷举校验进程的最高 RSS 为 {max(r['peak_rss_bytes_darwin'] for r in exhaustive)} B，约 {max(r['peak_rss_bytes_darwin'] for r in exhaustive)/(1<<20):.2f} MiB。这包含导入、算表与校验，不是 Studio 总内存。真实 Metal 显示类用例从路由到 GPU 接手约 7.0 s，含其它资源等待。

## Windows、跨平台和 CI

`osplat` 的 Windows 分支使用第 0 字节的 `msvcrt.locking`；Unix 使用 flock。完整套件包含同进程两个句柄冲突、不同进程的锁冲突、杀进程后重新获取、两个进程并发整体替换文件。上述关键测试没有新增 Windows skip。macOS 默认实现和强制路径实现均实际跑完，但后者仍调用宿主的 Unix 锁，不能替代 Windows msvcrt 证据。

工作流的 Windows/macOS jobs 执行无测试选择器的完整 pytest，并配置 Node 22 与 `GXR_REQUIRE_GPU_TEST=1`；Ubuntu 另跑 `make check` 和强制路径完整套件。修复轮新增的平台跳过仅是 Windows 没有 SIGHUP 的对应测试，没有对 GPU/锁测试新增跳过。见 [冻结的修复差异](repair.diff)。

截至 {ci_time}，对应 HEAD 的实际结果如下。原始命令输出见 [gh pr checks](pr-checks-final.txt)、[gh run view](ci-final.json)。

| Job | 实跑状态 | 证据 |
| --- | --- | --- |
| Ubuntu check | 通过 | [GitHub job](https://github.com/aa2246740/gxr-studio/actions/runs/41423530671/job/125204531390)。 |
| macos-latest 全套 | 通过，997 passed、698 skipped | [下载的 job 日志](ci-macos-job.log)、[GitHub job](https://github.com/aa2246740/gxr-studio/actions/runs/41423530671/job/125204531179)。额外跳过一项本机 Workspace 卷检查，runner 没有该卷。 |
| Ubuntu path-io 全套 | 通过，993 passed、702 skipped | [下载的 job 日志](ci-pathio-job.log)、[GitHub job](https://github.com/aa2246740/gxr-studio/actions/runs/41423530671/job/125204531491)。额外跳过为 macOS 字体、原子对调、ImageIO 和本机卷检查。 |
| windows-latest 全套 | 仍在运行，待 CI | [GitHub job](https://github.com/aa2246740/gxr-studio/actions/runs/41423530671/job/125204531472)。另一同 HEAD 的 run 也仍在运行，见 [PR checks](pr-checks-final.txt)。 |
| security-report | 通过 | [GitHub job](https://github.com/aa2246740/gxr-studio/actions/runs/41423530671/job/125204531578)。 |

因此只能关闭原来的静态收集阻塞，不能确认 Windows 锁语义和完整运行已经验收；Windows 硬件 D3D12 路径也未运行。两个新增平台 P1 已有直接逻辑反例，不因完整套件通过而放行。

## 回归、构建与公开字节

从 `edf01457cb8d941cda877cf6f5a1f84cd5c38324` 只读导出源码，为基线和 HEAD 各建独立图库及应用目录，使用不同进程。14/14 个真实输入渲染请求的状态、尺寸、像素 SHA-256 和业务响应头一致；相机原 JPG 的响应字节相同。其余 13 个重新编码 JPEG 的原始字节有 ICC 创建时间差异，变化只在 ICC 日期时间字段，移除该 ICC 段后压缩流全部逐字节相同。见 [夹具隔离](baseline-fixtures.json)、[完整对照](baseline-comparison.json)。

关闭开关时实际页面 `/gpu` 请求为 0，RAW 布局解析和预热调用为 0，不创建设备。这个“零变化”结论限于既有渲染路径；`/api/settings` 按设计新增 `gpu_preview:false`，不声称整个站点的所有 HTTP 字节与基线相同。

`make check` 零自动重跑，998 passed、697 skipped，覆盖率 {summary['coverage_percent']:.10f}%，门槛 85%；强制路径全套也是 998 passed、697 skipped。两者均为 1,695 个用例，0 failure、0 error。697 个本地跳过项没有在本轮补齐为整套私有数据回归；真实 GPU 验收使用另行隔离的 7 对照片和 DAT/标定副本。见 [make check](make-check.log)、[JUnit](make-check.xml)、[覆盖率](coverage.json)、[强制路径日志](path-io-full.log)、[强制路径 JUnit](path-io-full.xml)。

`make web`、同 frontend cwd 的独立模块图构建和提交的 engine.js 全部逐字节相同，均为 {build['bytes']} B：

```text
SHA-256 {build['sha256']}
```

见 [字节核对](build-byte-comparison.json)、[独立模块图](bundle-module-graph.json)、[保留的重建产物](rebuilt-engine.js)。模块图仅含 8 个项目源码/WGSL 模块，imports 和 dynamicImports 均为空。

项目的 private_bytes --tracked --dist 检查通过，独立扫描又检查 306 个跟踪文件及 wheel/sdist 等共 762 个源码/成员对象。未发现照片、相机 DAT/标定原始字节或第三方 LUT；唯一 PNG 是基线已有的 RICOH 字标，已目视核对，且与 edf0145 字节相同。见 [项目检查日志](make-check.log)、[独立清单](public-bytes-independent.json)。本轮没有新增依赖，许可登记未变。

## 性能抽查

固定无头 Metal、真实隔离照片、25 次可信键盘“曝光”输入，25/25 都对应实际 GPU 提交，渲染接口请求 0、失败响应 0、额外邻图 edit GET 0。暖路径输入到提交的 p50 为 {perf['inputToSubmitMs']['p50']:.3f} ms，p95 为 {perf['inputToSubmitMs']['p95']:.3f} ms，最大 {perf['inputToSubmitMs']['max']:.3f} ms。见 [完整样本与网络](perf-adjust-warm.json)、[回执](perf-adjust-warm-receipt.json)。

首轮原生页面的对应数为 p50 1.8 ms、p95 8.2 ms；本轮使用固定 Headless Shell 149，首轮性能样本为桌面 Chrome 152，采样方式及系统负载不同，不能据 p50 的差值认定性能回归。这里只做一次暖路径抽查，不给连续拖动吞吐结论。初次未充分暖机的 523.4 ms 样本、配方旋钮样本及工具前置失败均保留，见 [执行说明](harness-notes.json)，没有混入暖路径统计。

## 复跑、输入冻结与清理

对象为分支 feat/gpu-preview 的 `72d9b44aa62d5133565117d533041bad9a76cdc5`，基线为上述 edf0145；PR 的 head/base 与此一致，见 [PR 状态](pr-state.json)。306 个跟踪实现文件前后哈希一致，工作树状态不变，见 [开工冻结](frozen-inputs.json)、[最终核对](source-stability.json)、[汇总断言](verified-summary.json)。没有 Git 写操作、PR 评论或子代理。

4 项 P1 和 Range 反例都只需要合成文件，可用下列入口在新的指定 Scratch 根目录重跑，结果写进 Scratch/repro-evidence，不改交付目录。入口要求该 Scratch 根不存在，并复核卷 UUID。退出码表示探针执行成功，具体是否仍有缺陷看输出 JSON，不能把退出 0 当成修复通过。

```bash
nice -n 10 {WT}/.venv/bin/python -I -B {HERE}/reproduce_blockers.py
```

颜色和界面脚本也已保留；其真实输入来源及哈希见 [真实输入清单](real-inputs.json)、[相机数据副本清单](camdata-inputs.json)。仅这些清单、统计和哈希进入本交付目录，真实原图、DAT/标定与读回像素均留在临时目录并已删除。

有一处执行边界偏离：make check 的 import-linter 更新了工作树里两份既有的忽略缓存。它们是源码依赖图，不含本轮真实输入；未改实现文件，但不符合“所有临时输出都在指定 Scratch”这一要求。具体文件、哈希、时间和保留原因见 [缓存偏离记录](cache-boundary-deviation.json)。没有原始缓存字节可供可靠恢复，因此没有擅自删除或假称还原。其它前置/工具错误和修正见 [执行说明](harness-notes.json)。

计算工作串行执行；Studio 与浏览器阶段使用两个工作负载，测试子进程按测试生命周期结束，均继承 nice=10。没有 sleep 轮询，最长单次为 14 分 24 秒的隔离 Studio 会话，单次计算检查均低于 30 分钟。指定临时目录已删除，共 {cleanup['removed_regular_files']} 个普通文件、{cleanup['removed_bytes']} B；本轮浏览器已正常退出，隔离端口 49761 无监听，本轮运行进程剩余为 0。机主的 49667、三个受保护数据目录以及真实卡均未访问。见 [清理回执](cleanup.json)、[已删除私有临时文件的哈希](private-temp-artifact-hashes.json)。

本目录全部交付文件的 SHA-256 见 [SHA256SUMS](SHA256SUMS)。

不能合并；建议开关默认关闭；已确认 P1 共 4 项；指定临时目录已清理，既有缓存更新偏离已记录并保留。
'''
(HERE/'REVIEW.md').write_text(text,encoding='utf-8')
print('Wrote REVIEW.md with 4 P1 findings and pending Windows CI')
