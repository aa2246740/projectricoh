"""Write the final verdict only after the current PR checks and cleanup are verified."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ci = json.loads((OUT/'ci-verification.json').read_text())
summary = json.loads((OUT/'verification-summary.json').read_text())
assert ci['head'] == summary['head'] == '652847c0ea570ba4bc1e5e635055e3a1543ec996'
assert ci['attempt'] == 1 and ci['push']['conclusion'] == 'success'
assert not Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r5').exists()
assert json.loads((OUT/'reproductions/independent-selfcheck/receipt.json').read_text())['temporary_root_removed']
text = '''可以合并

| 核实项目 | 判定 | 独立证据 |
| --- | --- | --- |
| r4 P1-01，DAT 读取丢失卡根身份 | 已关闭 | 原普通根替换与三种根变化均复跑，全部返回 409，内容读取次数为 0，expect 为变化前的 dev/ino。[原触发点结果](cases/r4-dat-variants/dat-root-variants.json)、[普通根反例](cases/r4-dat-root/card-root-dat.json)、[全新副本复验](reproductions/independent-selfcheck/receipt.json)。 |
| 显式 card_id 与自动单卡选择 | 通过 | 独立新增 49 项，覆盖显式首张/末张、空对象、无请求体、空 card_id，以及两张卡中仅一张含 DAT。身份变化在内容打开前拒绝；已绑定根句柄的对照仍读取原字节。[49 项结果](cases/independent-dat/dat-identity.json)。 |
| 其他卡内容读取调用 | 无遗漏 | 三处生产 open_rb 均传 root 和 expect。DAT 取所选会话指纹；照片暂存与哈希在扫描前固定根身份；严格扫描的文件头读取使用已核对的目录句柄。[调用清单与上层传递](card-read-call-sites.json)。 |
| r2 反例 | 通过 | 五组边界反例、原合成 RAW/JPG 颜色反例和全输入 LUT 检查均通过。[逐项回执](verification-summary.json)、[r2 颜色](cases/r2-colour/synthetic-lut-counterexample-swiftshader.json)、[穷举](cases/r2-exhaustive/exhaustive-lut.json)。 |
| r3 反例 | 通过 | 普通照片父目录变化、响应 fd、私有目录失败清理、事件循环与 Windows 声明检查均通过。Windows 原生运行另核对同 SHA 的实际 CI。[边界](cases/r3-extra/extra-boundaries.json)、[事件循环](cases/r3-loop/windows-loop-guard.json)、[声明模型](cases/r3-contracts/windows-contracts.json)、[Windows 日志](pr-windows.log)。 |
| r4 反例与补充检查 | 通过 | DAT、18 项读卡补充、边界与声明、两份历史运行库入口各五种模式均通过。历轮行为复跑合计 29 项，另保留一项旧子类接口观察。[汇总](verification-summary.json)、[18 项读卡检查](cases/r4-card-extra/additional-card-cases.json)。 |
| 开关默认关闭 | 通过 | API 默认返回 enabled=false，不解析 DNG、不预热表；真实前端模块在关闭时不发 GPU 请求、不创建引擎。[定向测试日志](cases/targeted-tests/pytest.log)、[JUnit](cases/targeted-tests/tests.xml)。 |
| 显卡预览颜色 | 本轮未变，所测用例通过 | 85 个显卡与颜色相关跟踪文件同 r4 逐字节相同。两份全输入入口均零差异；两份原 RAW/JPG 反例均逐像素相同；现有 13 组渲染与适配器检查共 14 项通过，最大差异 1 码值，均满足原门槛。[源码哈希](colour-source-stability.json)、[当前颜色结果](cases/current-colour/colour-results.json)。 |
| 本机定向回归 | 通过 | 125 passed、54 skipped、0 重跑，包含新增 8 项 DAT 回归、旧 intake 失败用例、卡读取与 GPU API、前端分支和状态检查。[回执](cases/targeted-tests/receipt.json)。 |
| PR 上 652847c 的三平台 CI | 全部通过 | pull_request 与 push 两条运行的 Windows、macOS、Linux 均 success，均为首次 attempt。PR Windows 与 macOS 各核对 1,739 个不同用例，新增 DAT 8 项与颜色 14 项均通过。[最终 gh pr checks](pr-checks-final.log)、[逐项核对](ci-verification.json)、[最终 PR 元数据](pr-metadata-final.json)。 |
| windows-probes 首次超时 | P2，不阻塞合并 | 30 秒未收到页面完成结果，随后清理目录出现 WinError 32；首因及占用日志的进程 PID 未记录。一次重跑通过不能确定首因。正式颜色测试覆盖同一初始化路径的成功运行，未覆盖这次超时清理失败。[首错](debug-windows-probes-first.log)、[重跑](debug-windows-probes-final.log)、[分析](windows-timeout-analysis.json)。 |
| 冻结输入与清理 | 通过 | 312 个跟踪文件和 755 个既有审查输入哈希未变，工作树状态未变。3 次固定浏览器启动均正常关闭；任务临时目录及 profile 已删除，交付入口再次自验后也删除了新副本。[稳定性](source-stability.json)、[清理](cleanup.json)、[入口自验](reproductions/independent-selfcheck/receipt.json)、[SHA256SUMS](SHA256SUMS)。 |

审查对象是 [PR #16](https://github.com/aa2246740/gxr-studio/pull/16) 的 `652847c0ea570ba4bc1e5e635055e3a1543ec996`，分支 feat/gpu-preview。相对 r4 的 fb6bacc 仅一个提交、四个文件，97 行增加、5 行删除。两处生产改动分别保留自动选择分支的 session，并将所选会话的 root_dev/root_ino 作为必需关键字参数传入 DAT 读取。其余改动为八项回归和旧调用的签名调整。实现者说明只作为线索，本报告采用本轮冻结源码、独立复跑和 GitHub 原始日志。

本轮 P1 0 项，P2 1 项。

| 编号 | 级别 | 位置与影响 | 最小修正建议与关闭条件 |
| --- | --- | --- | --- |
| P2-01，Windows 探针超时后的诊断与清理不完整 | P2 | [gpu_support.py:148](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/tests/gpu_support.py:148) 只终止并等待初始浏览器进程。[windows_probe.py:59](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/scripts/windows_probe.py:59) 随后删除临时目录，首次日志实际出现文件占用错误。日志没有给出占用者 PID，不能直接认定它是浏览器子进程；现有测试也没有验证这个失败路径。它影响测试诊断与清理可靠性。 | 后续为本次浏览器建立可关闭的 Windows Job Object，等待本次启动的进程结束后再删除目录；保存页面加载、适配器请求和设备创建阶段的日志。补 Windows 超时清理用例，要求保留最初错误、无本次浏览器残留、无文件占用错误，并保持正常 14 项颜色检查通过。 |

P1-01 的原触发点保留在 [adaptation.diff](cases/r4-dat-variants/adaptation.diff)。原脚本断言的是旧失败行为，本轮只将关闭预期改为 409 与零读取。目录变化仍由独立短进程真实执行，读取仍调用生产 CardReader.open_rb 和 _read_limited；观察函数不替换返回字节。原报告及原反例文件均未改动。

新增检查采用七种选卡方式和七种目录或文件状态，共 49 项。普通根替换、根链接、上级目录链接、上级普通目录替换及 DAT 文件链接共 35 项，均返回 409、成功打开内容次数为 0、读取次数为 0。七项不变对照与七项“根句柄已打开后再换路径”的对照均只读取原字节。合成 DAT 格式无效，所以这十四项在后续格式校验返回 422，符合对照预期。

历轮复跑均保留输入哈希和适配差异。r3 原样旧子类因不接受 root 关键字得到 TypeError，记录在 [旧接口观察](cases/r3-original-interface/legacy-interface.json)；传递当前参数的适配版保留原变化时点并验证拒绝读取。Windows 声明检查在本机是模型验证。两份历史运行库入口的本机复跑使用当前 macOS 依赖，不作为 Windows 旧轮子的再次 A/B 结论；Windows 行为采用同 SHA 的原生 CI 日志。

颜色穷举对每组全部 16,777,216 个 RGB 输入逐字节比较生产 _apply，且检查 alpha=255。两组表的 SHA-256 分别为 `2b6d9dcc34c2b274bcecce3cfd7973ef4978809582c66f0434041c4add564b05` 和 `1f56de3f354563b084473fe44887d8a5bf452b6075c9c0b4ea7fd7049b70bce0`，r2 与 r4 入口结果一致。软件显卡使用固定 Playwright 1.61.1、Chromium Headless Shell 1228，读取提交的 engine.js 与原 harness。夹具生成、浏览器执行、像素比较分步运行，输入字节与用例清单在比较前再次核对；这使执行保持最多两个进程。三个浏览器回执分别见 [r2](cases/r2-colour/browser-receipt.json)、[r4](cases/r4-colour/browser-receipt.json)、[当前用例](cases/current-colour/browser-receipt.json)。

| CI 运行 | Windows 完整测试 | macOS 完整测试 | Linux check | windows-probes |
| --- | --- | --- | --- | --- |
| [PR 41601025374](https://github.com/aa2246740/gxr-studio/actions/runs/41601025374) | success，1,036 passed、703 skipped | success，1,033 passed、706 skipped | success，1,029 passed、710 skipped；DAST 另 25 passed | 按分支条件跳过 |
| [push 41601018252](https://github.com/aa2246740/gxr-studio/actions/runs/41601018252) | success，1,036 passed、703 skipped | success | success | 按分支条件跳过 |
| [调试 41595529400 首轮](https://github.com/aa2246740/gxr-studio/actions/runs/41595529400/attempts/1) | success，1,036 passed、703 skipped | success | success | failure，30 秒超时，清理报错 |
| [同一调试运行第二次 attempt](https://github.com/aa2246740/gxr-studio/actions/runs/41595529400/attempts/2) | 沿用首轮成功结果 | 沿用首轮成功结果 | 沿用首轮成功结果 | success，重跑一次 |

正式 PR 和 push 的完整任务均未自动重跑，security-report 也通过，最终 mergeStateStatus 为 CLEAN。调试运行第二次 attempt 虽给其余四项分配了新的 job ID，但它们的开始、结束和步骤时间沿用首轮；只有 windows-probes 有新的执行时间。这与只重跑一次短任务相符。

那次 30 秒未结束的首因尚未定位，不能判定为单纯的环境偶发。短探针的 cases=[]，只创建引擎；正式 14 项颜色检查调用同一 run_engine，默认上限为 180 秒，PR 首次运行全部通过。重跑探针记录了 SwiftShader，首轮与重跑的 Chrome 版本字符串同为 156.0.8078.80。现有记录未定位第一次停在浏览器启动、页面加载还是设备创建，因此也没有证据把它认定为生产渲染或颜色错误。已经证实的缺口是失败诊断和临时目录清理，按 P2 后续处理，合并结论不依赖把这次失败解释成已解决。

可用下面的入口在全新跟踪文件副本独立复跑 DAT 三种根变化。它核对卷 UUID、HEAD 与冻结哈希，只写本审查目录的新 reproductions 子目录及指定 Scratch 根，结束时删除临时副本。更换 run-name 可再次运行；case 也可选 independent-dat、r4-dat-root、r4-card-extra。[脚本](reproduce.py)已实际自验。

```bash
/usr/bin/nice -n 10 /Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/.venv/bin/python -I -B \\
  /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_gpu_preview_r5/reproduce.py \\
  --case r4-dat-variants --run-name dat-root-check
```

本轮未运行 macOS Metal 与 Windows D3D12 硬件路径、其他 Python 版本、真实读卡器与 FAT32 存储卡、相机设备。缺少实拍或标定夹具的跳过项未计为通过。未访问机主 Studio、机主图库、导出、应用数据目录或真实卡；未改工作树、执行 Git 写操作、推送、评论 PR 或启动子代理。本机行为复跑均使用 nice 10，各项检查串行运行，临时文件和浏览器 profile 均限于指定 Scratch 根。

[SHA256SUMS](SHA256SUMS)覆盖本报告、冻结清单、脚本、适配差异、原始 CI 日志与回执。可在本目录执行以下命令逐项核对。

```bash
/usr/bin/shasum -a 256 -c SHA256SUMS
```

可以合并；P1 0 项；PR 上 652847c 的 Windows、macOS、Linux CI 均通过；任务临时文件与浏览器 profile 已清理。
'''
(OUT/'REVIEW.md').write_text(text)
print(str(OUT/'REVIEW.md'))
