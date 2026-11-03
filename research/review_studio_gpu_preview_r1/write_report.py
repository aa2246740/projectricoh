"""Render the review from independent receipts; contains no private image bytes."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from collections import Counter

R=Path(__file__).resolve().parent
def read(name):return json.loads((R/name).read_text())
sw={x['id']:x for x in read('real-parity.json')}
metal={x['id']:x for x in read('real-parity-metal.json')}
coverage=read('coverage.json')['totals']['percent_covered']
perf=read('native-perf-summary.json')
original={}
for t in ET.parse(R/'make-check-final.xml').findall('.//testcase'):
    if t.find('skipped') is not None:original[(t.get('classname'),t.get('name'))]=t.find('skipped').get('message')
passed=set();extra=[]
for name in ['local-data-tests-fixed','local-data-contracts','local-data-remaining']:
    p=R/(name+'.xml')
    if not p.exists():continue
    nodes=ET.parse(p).findall('.//testcase');counts=Counter()
    for t in nodes:
        status='skipped' if t.find('skipped') is not None else 'failed' if t.find('failure') is not None or t.find('error') is not None else 'passed'
        counts[status]+=1
        if status=='passed':passed.add((t.get('classname'),t.get('name')))
    extra.append((name,counts))
remaining={k:v for k,v in original.items() if k not in passed}
summary={'originally_skipped':len(original),'subsequently_passed':len(original)-len(remaining),'remaining':len(remaining),'remaining_cases':[{'module':k[0],'name':k[1],'reason':v} for k,v in remaining.items()]}
(R/'supplement-final.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
cleanup=read('cleanup.json') if (R/'cleanup.json').exists() else {'complete':False}
color_rows=[]
for cid,a in metal.items():
    b=sw[cid]
    ok=a['within_1']>=.9999 and a['mean_delta_e00']<=.01
    color_rows.append(f"| {cid} | {a['w']}×{a['h']} | {a['within_1']*100:.8f}% | {a['mean_delta_e00']:.8f} | {a['max_code']} | {a['over_2_outside_edge_band']} | {'PASS' if ok else 'FAIL'} | {b['mean_delta_e00']:.8f} |")
extra_rows='\n'.join(f"| [{name}.log]({name}.log) | {c['passed']} | {c['skipped']} | {c['failed']} |" for name,c in extra)
remaining_lines='\n'.join(f"- `{k[0]}::{k[1]}`：{v}。" for k,v in remaining.items()) or '- 原先跳过的用例均已在补跑中通过。'
text=f'''不能合并
开关保持默认关闭：有 4 项 P1，涉及图库外文件读取、GPU 资源版本失效、颜色门槛失败和 Windows CI 收集失败。

## 对象与证据边界

- 工作树 `/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview`，HEAD `cd2817fb0b8cf81b1b1c3b0449245c20e4b4fcde`，分支 `feat/gpu-preview`。
- 基线是本地 `origin/main` 的 `edf01457cb8d941cda877cf6f5a1f84cd5c38324`。按三点差异审查全部 42 个文件，见 [full.diff](full.diff)。没有 fetch、commit、push、merge 或其他 Git 写操作。检查使用了工作树已有的忽略依赖和缓存，未改实现文件。
- 299 个受 Git 跟踪文件在复审前后逐个核对 SHA-256。主测试、复算与本文均对应这些冻结输入，见 [frozen-inputs.json](frozen-inputs.json)、[source-stability-before-cleanup.json](source-stability-before-cleanup.json)。未修改实现文件。
- 真实输入来自指定 DNG 清单，选取 R8051410、R8051448、R8051312、R8051691、R8051699、R8051707、R8051711 及配对 JPG，包含 50mm、MOUNT 和 Orientation=8。DAT 与标定仅从项目已有副本提取到临时应用目录。路径和哈希见 [real-inputs.json](real-inputs.json)。没有把这些输入写入公开工作树。
- 所有自建临时文件、pytest basetemp 和固定 Chromium 的临时用户目录都在 `/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r1/`。原生 in-app Browser 使用本轮 incognito 标签，没有启动系统 Chrome 用户目录。
- 开工已运行 `df -h /Volumes/Workspace`，确认 APFS、可写、UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，见 [volume.json](volume.json)。复审工作负载使用 `nice -n 10`，主测试串行，拟合子进程按测试自身生命周期启动与结束。
- 未访问 `127.0.0.1:49667`、三个受保护的机主目录、`/Volumes/RICOHDCX` 或任何真实卡。隔离工作室端口为 `49741`；TestClient 的 `49742/49743` 只用于进程内请求。没有设备、存储卡或刷机验收结论。

## 逐项判定

| 项目 | 判定 | 核实结果与证据 |
| --- | --- | --- |
| 1. 新接口安全、只读、大响应 | FAIL | 访问控制和流式返回通过；图库外符号链接可读，旧 LUT 元数据迁移会写盘，NaN 裁切返回 500。见 P1-01、P2-01、P2-05。 |
| 2. 开关关闭时零变化 | FAIL | 不创建设备、CPU 输出一致均 PASS；严格的行为零变化不成立，首次多一次 `/gpu` 请求和 DNG 解析。见 P2-04。 |
| 3. 开关打开时结果、回退、生命周期 | FAIL | 常规回退和受控请求乱序通过；相机数据和 LUT 版本变化后仍显示旧结果。缓冲覆盖还缺少显式释放。见 P1-02、P2-02。 |
| 4. 颜色与测试门槛 | FAIL | 真实输入在 SwiftShader 和 Metal 上复跑，另有全合成反例违反原门槛；非边缘最多 2 码值也不能通过。见 P1-03 和颜色章节。 |
| 5. 构建、make check、覆盖率 | PASS | 构建逐字节一致；942 passed、697 skipped、零 pytest 自动重跑；覆盖率 {coverage:.8f}%。补跑结果见下。 |
| 6. CI 工作流 | FAIL | Ubuntu 的 pnpm/Node/强制构建检查编排静态正确；Windows 新任务在收集测试时会导入 Unix 专用模块。远端工作流未运行。见 P1-04。 |
| 7. 依赖、许可、公开字节扫描 | PASS | 直接依赖和传递许可已登记；相同产物的模块图只含项目源码；lightningcss 未进入引擎；公开源码与分发包扫描通过。 |
| 8. 现有界面性能抽查 | OPEN | 原生 Metal 上取得 25 次真实输入和两次换片样本；原生自动化连接随后报错，未复现完整的 Chrome 156 连续拖动协议及冷启动基线。 |

### 1. 接口安全与只读性

| 子项 | 判定 | 证据 |
| --- | --- | --- |
| 六个接口都经过令牌、Host、Origin 检查 | PASS | `app.py` 将 `gpu_router` 挂在统一 SecurityMiddleware 内。六个端点各测无令牌、非法 Host、非法 Origin、cross-site，共 24 个拒绝用例全部符合 401/403 约定。[api-probes.json](api-probes.json)。 |
| shot_id 输入不能拼任意路径 | PASS | SQL 参数化按 id 查记录；编码斜线、`../` 和不存在 id 均为 404。URL 路径穿越未复现。 |
| 实际打开的文件必须在图库内 | FAIL | 已登记 DNG/JPG 被替换成指向图库外合成标记文件的符号链接后，两个接口均 200 返回外部字节；`Library.is_local()` 同时为 false。 |
| 当前格式数据上的六个成功请求不写盘 | PASS | 真实输入上 `/gpu`、`/raw`、`/camera-jpg`、`/bake`、`/table`、`/gpu/box` 全部 200，审计记录写入数为 0。[real-api-readonly.json](real-api-readonly.json)。 |
| 所有可达读取路径都只读 | FAIL | 将本轮合成 LUT 的 attribution_version 改成旧版本后，GET `/table` 触发 `.library.json.*.tmp` 写入及 rename。迁移发生在共用 LUT 库中。 |
| 错误码和错误体一致 | FAIL | 无 RAW、找不到照片、非法配方等沿用 404/409/422 和 JSON 错误体；但 NaN 裁切产生 500 纯文本 `Internal Server Error`，错误裁切类型还会被静默忽略。 |
| RAW/JPG 大响应按块发送 | PASS | 路由返回 Starlette FileResponse；Range 请求返回 206，16 字节内容正确。真实 DNG 18,659,168 B、JPG 4,056,805 B 均成功。这里确认的是服务端流式实现，不是任意并发下的总内存上限。 |

### 2. 关闭开关的行为与输出

[fallback-probes.json](fallback-probes.json) 记录 `flag_off` 下 adapterCalls=0、deviceCalls=0，最终显示服务器 `<img>`，状态 200。

从 `origin/main` 只读导出源码快照，在独立的基线图库与应用目录上，对同一批 14 个请求分别跑基线和 HEAD。14/14 状态、图像尺寸、解码像素 SHA-256 和业务响应头一致，见 [baseline-comparison.json](baseline-comparison.json)。未经重新编码的相机 JPG 也逐字节相同。

其余 JPEG 的字节哈希存在跨进程差异。额外定点复算证明，样本只差 ICC 创建时间的一个字节，删除 ICC APP2 段后压缩图像流逐字节相同，见 [jpeg-icc-comparison.json](jpeg-icc-comparison.json)。这不是本次开关造成的像素差异。

关闭时仍先调用 `gpuRoute()`，首次等待 `/gpu`；后端即使 enabled=false 也执行 `_raw_source()`。因此不能写成完整的“关闭时零变化”。这属于 P2-04。

### 3. 回退、方向、编辑与异步状态

| 子项 | 判定 | 证据 |
| --- | --- | --- |
| 透视、畸变 | PASS | `decide()` 对 vertical、horizontal、distortion 直接返回服务器路径；现有 17 个分支测试包括透视。[test_gpu_frontend.py](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/tests/test_gpu_frontend.py:75)。 |
| 成片边框、日期戳及默认装饰 | PASS | `applyEdit()` 先经 `resolveFinish()` 合并默认装饰，`decide()` 对成片中的 frame/stamp 回退。裁剪页只显示未裁切颜色层。源码与纯函数分支测试通过。 |
| JPG-only 近似配方 | PASS | 只有 JPG 时 recipe 路径返回 null，保留既有服务器近似管线；分支测试通过。 |
| 没有 WebGPU | PASS | 实际页面注入 navigator.gpu=undefined 后显示服务器图，200，设备创建数为 0。 |
| 着色器编译失败 | PASS | 实际设备的 shader module 注入非法 WGSL，最终服务器图 200，设备仅尝试一次。 |
| 设备丢失 | PASS | 已显示 GPU 画面后执行真实 device.destroy()，旧引擎 isLost=true，最终回到服务器图 200。上述三项见 [fallback-probes.json](fallback-probes.json)。 |
| 连续换片的过期照片请求 | PASS | 挂住 A、B 的 `/gpu`，先让 C 显示，再按 B、A 顺序释放；最终 hash、source key、画布名称均为 C。[race-probes.json](race-probes.json)。 |
| 连续换配方的过期烘焙请求 | PASS | 挂住配方 1、2 的表，先显示配方 3，再释放 2、1；实际引擎 recipe key 与配方 3 的响应 key 相同。 |
| 相机数据、LUT 版本变动 | FAIL | 实际界面通过原 API 从 g127 更新到可渲染的 g155 后仍使用旧表、旧画面；LUT 元数据变更后也未重新验证。见 P1-02。 |
| 竖拍方向 | PASS | 真实 Orientation=8 RAW 为 1424×2144、JPG 为 2848×4288；与 Python 参考尺寸和像素对拍通过。合成 Orientation=6/8 用例也运行。 |
| 编辑仍经旧 API、带 rev 保存 | PASS | 保存代码未替换，仍共用 saveQ/expected_rev。真实界面输入触发原编辑 API；本机补跑包含 edit roundtrip、rev 冲突、实时覆盖与导出用例。 |
| 导出参数与预览一致 | FAIL | 稳态时 `gpuContext()` 使用原来的 recipeForRender/adjustBody/cropDraft，14 个数值场景已有对拍；但 LUT/相机数据变更后，GPU 仍用旧资源，服务器导出使用当前版本。不能给无条件一致结论。 |
| 源纹理和 RAW 临时缓冲释放 | PASS | Metal 上上传 17 份真实尺寸源，缓存稳定为 13 份、635,035,648 B，小于 640 MiB；4 次淘汰明确 destroy，dispose 后 17/17 纹理、34/34 临时缓冲均明确销毁。当前源保留，旧非当前源被淘汰。[resource-probe.json](resource-probe.json)。 |
| 同键烘焙缓冲生命周期 | FAIL | 覆盖同一键 12 次，Map 只有 1 项，覆盖阶段旧缓冲显式 destroy=0。见 P2-02。 |
| 长时间会话的实际驱动显存不增长 | OPEN | 以上检查覆盖资源所有权和源 LRU；没有驱动级 VRAM 计数，也没有用 Map 大小推断实际显存。 |

## 颜色结果与门槛

参考图由生产 RAW、配方链、LUT 和 finish_array 在 JPEG 压缩前生成。所有计数与 ΔE00 均保留未四舍五入的原值。比的是 1:1 成片纹理，显示缩小的质量、ICC 显示管理和全尺寸 GPU 导出不在这组数值结果内。

真实照片沿用原报告的 14 组参数；显示类和 Log LUT 改用明确公式生成的 17³/65³ 合成 LUT，没有读取第三方 LUT。因此不能把此处 e/h 数值与原报告采用的另一份 LUT 逐值对照。该差别用于检验“所有受支持 LUT 都能满足门槛”的推广是否成立。

两种后端均复跑完成：固定 Chromium 的默认无头适配器实际为 Google SwiftShader；显式 Metal 启动得到 Apple metal-3、fallback=false。适配器以 JSON 字段为准，不能从脚本或文件名称推断。见 [real-parity.json](real-parity.json)、[real-parity-metal.json](real-parity-metal.json)、[real-route-metal.json](real-route-metal.json)。

| 用例 | Metal 尺寸 | Metal ≤1 码值像素比例 | Metal 平均 ΔE00 | 最大码值差 | 边缘带外 >2 的像素数 | 原门槛 | SwiftShader 平均 ΔE00 |
| --- | --- | --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(color_rows)+f'''

### 原因说明的复核

“连续 uint8 量化放大初始一档差异”的机制已复现。`c_recipe04_curve_extra` 有 7 个非边缘像素差 3–4 码值。对它们逐段复算配方/曲线、黑点、饱和度、自然饱和度、暗角：最初差 1，后续量化扩大到 3–4。把 GPU 第一段的 uint8 输出喂给 Python apply_extra，7/7 个最终异常像素均逐字节重现 GPU 的结果。[rounding-trace.json](rounding-trace.json)。

例如 `(1159,584)` 的差值依次为 1、2、3、4、4。该结果支持量化传播解释，但没有把最初翻转具体归到某个 pow/log2 指令。RAW 配方路径还涉及查表、插值与色度运算，应把原因写为中间精度和运算顺序引发的量化分叉。

24 码值的点是 `(91,1304)`，拉直 7.25°。Python 的源 y=1423.001021922912，大于阈值 1423.001，写入填充色 `[27,28,31]`；float32 的 y 和阈值均为 1423.0009765625，GPU 判为有效，写入 `[39,52,54]`。点在一像素有效区边缘带内，带外最大差为 1。[geometry-boundary-cause.json](geometry-boundary-cause.json)。这一原因说明成立。

### 原门槛和新增上限的判断

原门槛“≥99.99% 像素在 1 码值内、平均 ΔE00 ≤0.01”仍有价值，但本实现尚未普遍达到。新增的全合成、可公开复跑用例也失败：

| 全合成用例 | ≤1 码值比例 | 平均 ΔE00 | 最大差 | 判定 |
| --- | --- | --- | --- | --- |
| RAW + 合成 LUT + 调整 | 99.96065109% | 0.00221030 | 2 | FAIL，像素比例不足。 |
| JPG + 合成 LUT + 高光 | 99.95880127% | 0.01071808 | 2 | FAIL，两项均不足。 |

LUT 节点公式是 `clip([r,g,b] × [0.86,0.97,1.05],0,1)`，17³，输入全由测试脚本合成。复算脚本 [synthetic_lut_counterexample.py](synthetic_lut_counterexample.py) 按原门槛明确退出 1，见 [synthetic-lut-counterexample.json](synthetic-lut-counterexample.json) 与 [执行回执](synthetic-lut-counterexample-receipt.json)。这不是相机私有数据才能触发的问题。

“有效区域边缘一像素带外不允许超过 2 码值”不能作为当前实现的通过门槛：上述 7 个内区像素会失败，与几何有效区无关。可以保留它作为后续精度目标；当前若采用有界的替代写法，建议：

1. 每个用例保留 ≥99.99% 和平均 ΔE00 ≤0.01，两项均用未舍入计数判定。
2. 在 CPU 有效区蒙版上定义一像素边缘带，包含边界内外各一像素，随旋转、翻转和裁切同步变换；不能把整块无效区或所有裁切边缘都豁免。
3. 带外最大差暂限 4；超过 2 的像素须逐个由前向量化复算解释，并限制在冻结用例集合已知的位置与数量内。新位置、新数量或差值扩大均失败，不写成无限制的浮点误差豁免。
4. 带内超过 2 的异常还须证明 CPU/GPU 的 coverage 分类不同，且取样点处于边界数值误差范围内；记录个数和最大差。建议数量上限为 `ceil(N × 10⁻⁶)`，本例为 1/3,053,056。

这是待扩充用例后采用的门槛建议，不使目前失败的显示类 LUT 通过。修复前可让该路径回到服务器。CI 当前 10 个颜色用例只用合成 DNG、配方表、矩阵、LUT 和 JPG，此点 PASS。

## 构建和检查

`make web` 在原工作树执行，但通过配置原有的 `GXR_GPU_OUT` 把产物写到临时目录。重建和提交文件均为 36,963 B，SHA-256 都是 `1313d5b9ffd07b603f66e3bdb704f8d79701de04d8f5be6184840c502be43a97`。[make-web-byte-comparison.json](make-web-byte-comparison.json)。类型检查及 make check 内的独立临时重建也通过。

正式 make check 的 pytest 结果是 942 passed、697 skipped、3 warnings，1639 个用例，覆盖率 {coverage:.8f}%，门槛 85%。使用 `--force-reruns 0` 覆盖项目命令的自动重跑设置，见 [make-check-final.log](make-check-final.log)、[make-check-final-receipt.json](make-check-final-receipt.json)、[make-check-final.xml](make-check-final.xml)、[coverage.json](coverage.json)。数目比实现报告多，判断绑定当前合并后 HEAD。

没有把缺失夹具补入公开工作树。本地 pytest 插件只将研究输入路径重定向到现有项目目录，测试写入仍留在指定 basetemp。后续补跑如下：

| 补跑 | 通过 | 跳过 | 失败 |
| --- | --- | --- | --- |
{extra_rows}

原先 697 个跳过用例中，现已有 {len(original)-len(remaining)} 个在补跑中通过。具体覆盖包括真实 RAW 读取/方向、预览/导出、rev 冲突、相机数据与标定、DAT 127/129/131/135/137/138/150/152/153/154/155、完整 552 B 条目和相机 C 参考对拍。对应代数以补跑日志实际执行为准。这些是桌面和主机层测试，不是相机上运行证明。

仍未通过本机补跑关闭的原始跳过用例为 {len(remaining)} 个，详见 [supplement-final.json](supplement-final.json)：

{remaining_lines}

前置环境和复算脚本错误未计为产品失败，也没有丢弃原记录：首次 make check 因新隔离的 uv 缓存缺 hatchling 停在离线打包；第二次因隔离 Corepack 缓存触发下载失败停在前端检查。补齐隔离缓存后正式检查通过。第一组本机补跑的初版插件遗漏了 make_card 已绑定的默认样本路径，导致 10 个 FileNotFoundError/StopIteration；修正插件后 110 passed、1 skipped。初版日志和最终日志均保留。正式统计不包含 pytest 自动重跑。

## CI 与依赖

Ubuntu 的步骤顺序正确：固定 pnpm 10.33.2、Node 22、锁文件安装，再用 `GXR_REQUIRE_FRONTEND=1` 和 `GXR_REQUIRE_GPU_TEST=1` 强制执行构建/适配器检查。缺少 Node、前端依赖或 WebGPU 适配器会使主检查失败。Node 22 的 CI 通道安装 22 系列版本；本机实际核对使用 Node 26.7.0，跨平台构建未在远端运行。

Windows 新增的 gpu-parity 任务有确定的收集阻塞，详见 P1-04；不能断言推上去后整个工作流能跑通。macOS/Ubuntu 的实际 GitHub Actions 执行状态仍 OPEN。本轮没有推送或触发工作流。

依赖登记和安装元数据相符：Vite 8.3.5/MIT、TypeScript 7.0.2/Apache-2.0、@webgpu/types 0.1.74/BSD-3-Clause。pnpm 许可清单共 MIT、Apache-2.0、BSD-3-Clause、MPL-2.0、ISC 五类，见 [frontend-licenses.json](frontend-licenses.json)。这些是构建依赖，当前交付的引擎没有打入它们的运行时代码。

使用 Vite 的 generateBundle 记录模块图，在与 make web 相同的 frontend cwd 重建，产物仍为上述 SHA-256；模块图仅包含项目的 engine、tones、index 和 WGSL，外部 imports/dynamicImports 均为空。[bundle-module-graph.json](bundle-module-graph.json)。lightningcss 及其 MPL 文件没有进入该产物，因此本次产物没有引入 MPL 源码合并问题。声明的许可与当前 PolyForm Noncommercial 项目构建方式不冲突。

make check 中 `private_bytes.py --tracked --dist` 检查 302 个源码/打包对象并通过；秘密扫描无高置信命中，OpenAPI 与源码一致，包体扫描也通过。CI 新 GPU 测试的数据生成代码没有照片、理光 DAT/条目或第三方 LUT 文件。

## 性能抽查

只使用临时图库及原生 in-app Browser，UA 为 Chrome 152.0.7977.169 / Electron 44.10.0，适配器 Apple metal-3、fallback=false、DPR=2。主机 10 个逻辑 CPU、16 GiB 内存。输入样本期间 load average 为 29.99/20.24/17.74；整轮其他阶段曾达到 75.36/45.68/30.46，未停止或调整机主其他工作负载。

| 观察 | 样本与结果 |
| --- | --- |
| 真实控件输入 | 24 次键盘调整加一次原生指针手势，共 25 次可信 input，25 次都有对应 GPU 提交。 |
| 输入至 GPU 提交 | p50 {perf['inputToSubmitMs']['p50']:.2f} ms，p95 {perf['inputToSubmitMs']['p95']:.2f} ms。 |
| 输入至 queue.onSubmittedWorkDone | p50 {perf['inputToDoneMs']['p50']:.2f} ms，p95 {perf['inputToDoneMs']['p95']:.2f} ms，最大 {perf['inputToDoneMs']['max']:.2f} ms，包含首次样本。 |
| 输入至下一次 rAF | p50 {perf['inputToNextRafMs']['p50']:.2f} ms，p95 {perf['inputToNextRafMs']['p95']:.2f} ms。不是显示器实际呈现时刻。 |
| 空闲刷新 | 输入之前的 240 个间隔均值 {perf['raf_mean']:.3f} ms，最大 {perf['raf_max']:.2f} ms；不能据此认定持续拖动 120 Hz 不掉帧。 |
| 换片 | 两次原生点击到匹配新 source 的第一笔提交分别为 58.4 ms、21.7 ms。 |
| 网络 | 输入期间 `/render` 为 0；相邻照片 `/edit` 读取为 100。 |

原始数据和测量定义在 [native-ui-perf-r1.json](native-ui-perf-r1.json)、[native-perf-summary.json](native-perf-summary.json)、[native-ui-switch-partial.json](native-ui-switch-partial.json)、[ui_measure.js](ui_measure.js)。

抽样支持“暖路径不用服务器出图，交互反馈处于毫秒级”的有限结论。没有复现原报告四秒连续 120 Hz 拖动，也没有交替测旧版和新版或重测冷开/冷跳预算，因此不确认其完整 p95、换片分布和速度提升倍数。期间原生自动化报告 `cdpSession.send: Target page, context or browser has been closed`，后来又报告 automation host unavailable；未把控制连接失败当作产品着色器失败。固定 Chromium 的颜色对拍不作为交互性能替代。

## P1 问题与最小修正

### P1-01：新媒体端点读取图库外符号链接

[gpu_routes.py:109](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/api/gpu_routes.py:109) 和 [gpu_routes.py:119](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/api/gpu_routes.py:119) 直接把 `lib.abspath()` 的路径交给 FileResponse；该函数只拼接根目录。前提是已登记的图库文件或目录被替换为库外符号链接，并且请求者持有合法凭据。没有复现通过任意 shot_id 直接拼接路径的攻击。

两个端点都已返回库外合成标记文件的完整字节。功能开关默认关闭时端点仍可访问，因此关开关不能隔离此问题。[api-probes.json](api-probes.json)。

最小修正是为这些读取建立共用的受约束打开方式，拒绝库外/卡路径及符号链接，验证后绑定已打开的文件描述符再流式发送；不要仅增加一次 resolve/is_local 检查后又按原路径重新打开。RAW 布局解析也使用同一边界。补目录链接、文件链接、替换时序和正常大文件 Range 回归。

### P1-02：GPU 资源未随相机数据和 LUT 版本失效

[gpu_stage.js:130](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/web/assets/gpu_stage.js:130) 和 [gpu_stage.js:144](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/web/assets/gpu_stage.js:144) 只按请求 URL/cube_id 记忆资源；命中 hasBake/hasLut 后不验证版本。该模块没有处理 camdata-changed，也没有检查异步结果是否属于当前数据版本。

复现一：把已载入 LUT 的输出空间改成 vlog，服务器新 `/table` 为 422，旧模块仍返回 GPU；发送事件后不变，新模块才回退。[state-probes.json](state-probes.json)。

复现二采用完整界面和正常导入 API：显示 MOUNT 照片 R8051691，再通过 `/api/camdata/import-file` 将临时相机数据从 g127 换成 g155。服务器 ready=true，界面已识别 generation=155，仍把旧键 `e5605f58d63e727916600b2d` 传给引擎，成片纹理 SHA-256 保持原值。服务器对应的新键为 `df457d61244aa1126d4ccf7c`，表的字节哈希也已改变。强制给引擎装入新表后，纹理哈希从 `490b3681…349e68` 变成 `ee71ab30…3b5858`。测试结束恢复 g127。[camdata-ui-probe.json](camdata-ui-probe.json)、[复算脚本](camdata_ui_probe.mjs)。直接模块层的数据失效故障注入记录也保留在 state-probes 中。

最小修正是将 camdata dataVersion 和 LUT render_token/元数据版本纳入缓存身份，接入版本变化事件，并让成功、失败和预取的旧 Promise 都在完成时校验代数。清理 Map 不足以防止旧 Promise 再填回。检测到不可渲染状态时应回退并沿用现有错误提示。上述两种失效以及失效中的迟到成功/拒绝都应有回归。

### P1-03：支持的 LUT 路径不满足颜色门槛

现有 10 个合成场景覆盖不够。新增全合成取整边界用例在相同已提交 engine.js 上失败，真实输入的合成 LUT 在 SwiftShader 与 Metal 上也失败，见颜色章节。JPG 的普通调整路径逐字节一致，不能推广成所有 JPG+LUT 也一致。

最小修正是把 [synthetic_lut_counterexample.py](synthetic_lut_counterexample.py) 的等价合成场景纳入 CI，修正显示类 LUT 的计算/量化误差；修复前让这些路径回到服务器。不要直接放宽门槛以容纳当前反例。前述可解释的少量 3–4 码值传播应与此处广泛的 LUT 取整边界失败分开处理。

### P1-04：新增 Windows CI 任务无法收集测试

[ci.yml:45](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/.github/workflows/ci.yml:45) 新增 windows-latest，但 pytest 在收集前会执行 tests/conftest.py，其中导入 gxr_studio.audit。[audit.py:16](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/audit.py:16) 无条件导入 Windows CPython 不提供的 fcntl；privacy.py 和 library/lock.py 也有相同导入。

这是静态确定的入口阻塞，非 Windows 实跑结果。[windows-ci-import-blocker.json](windows-ci-import-blocker.json)。Unix 模块原先已存在于 main，新增矩阵使它变成此工作流的失败条件。

最小修正是建立不导入应用 Unix 平台层的独立合成 GPU 测试入口，同时保留适配器必须成功的断言；或先补齐应用平台层，再启用 Windows 任务。单纯更改 Chrome 参数、允许 skip 或移除 require 标志都不能修复入口。

## P2 问题与最小修正

1. `gpu/box` 没有严格解析裁切对象。字符串坐标被忽略，负宽高被裁成 1×1，NaN 触发 500；width/height 还独立允许到 20000×20000，身份蒙版本身就需要约 381 MiB，拉直会再建立大坐标数组。本轮没有实际执行超大分配。复用有限数、类型、范围验证，并将像素预算绑定实际源图尺寸；无效请求返回现有 422 JSON 风格。
2. `Engine.addBake()` 在同一键上直接 `Map.set()`，没有销毁被覆盖的 buffer；addLut 的结构相同。12 次 990,392 B 表上传生成 11,884,704 B 缓冲，Map 只有一项，dispose 只显式销毁最后一份。此处统计的是显式调用，不把它等同于 GC 后驱动仍占用的字节。最小修正是同键复用，或覆盖前 destroy 旧资源。[state-probes.json](state-probes.json)。
3. `prefetch()` 每次 route 成功都读取相邻照片 edit，25 次输入造成 100 次相邻 GET，见 [native-perf-summary.json](native-perf-summary.json)。按当前照片/相邻照片的 rev 调度一次并去重；不要在每次滑块输入上重新发请求。
4. 关闭开关仍请求 `/gpu` 并解析 DNG。使用现有启动设置传递开关状态，在进入新路径前直接返回旧预览；至少应在 gpu_info 发现 disabled 时尽早返回，避免解析 RAW。[gpu_routes.py:93](/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/src/gxr_studio/api/gpu_routes.py:93)。
5. 旧 LUT 元数据经 GET `/table` 触发磁盘迁移，违背六个端点的严格只读声明。[api-probes.json](api-probes.json) 的 legacy_lut_read_side_effect 有临时文件与 rename 记录。将迁移放到明确的导入/启动迁移阶段，或提供不持久化的读取方法；当前格式的六个成功请求无写入不覆盖这一分支。

## 可重跑入口与收尾

复跑前先核对 Workspace 卷 UUID。工作树 `.venv`、Node、pnpm 和全局固定 Playwright 运行时是前提。所有脚本只写本报告目录和指定 Scratch；不要将真实输入复制进公开仓库。

```sh
nice -n 10 /usr/bin/python3 -I -B /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_gpu_preview_r1/prepare_runtime.py
nice -n 10 /usr/bin/python3 -I -B /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_gpu_preview_r1/run_gate.py make-check-final -- make check
```

上例由脚本固定到目标工作树运行。[prepare_runtime.py](prepare_runtime.py) 恢复已安装的 Corepack 缓存并准备隔离构建后端；缺失缓存时构建后端准备需要读取软件包源。[run_gate.py](run_gate.py) 记录命令、负载、耗时与退出码，并设置 TMPDIR、basetemp、零重跑和固定 Chromium 适配脚本。[prepare_session.py](prepare_session.py) 建立隔离图库；[run_real.mjs](run_real.mjs)、[color_reference.py](color_reference.py) 负责真实对拍；[state_probes.mjs](state_probes.mjs)、[fallback_probes.mjs](fallback_probes.mjs)、[race_probes.mjs](race_probes.mjs)、[resource_probe.mjs](resource_probe.mjs) 各自复算状态、回退、乱序和资源生命周期。复跑后用 [cleanup_review.py](cleanup_review.py) 结束本轮服务并清理同一 Scratch 根目录。

收尾状态：{'已清理。隔离工作室和自建浏览器已退出，指定 Scratch 根目录已删除；保留本报告、复算脚本和不含原始照片/固件的证据。见 [cleanup.json](cleanup.json)。' if cleanup.get('complete') else '尚在收尾，正式交付前更新 cleanup.json 并删除指定 Scratch。'}
'''
(R/'REVIEW.md').write_text(text)
print('Wrote',R/'REVIEW.md','; original skipped closed',summary['subsequently_passed'],'; remaining',summary['remaining'])
