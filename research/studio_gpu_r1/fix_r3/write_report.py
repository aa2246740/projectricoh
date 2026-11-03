"""Build the final review report only from completed, SHA-bound evidence."""

from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
from xml.etree import ElementTree

OUT = Path(__file__).resolve().parent
ROOT = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
HEAD = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
ci = json.loads((OUT / 'ci-final.json').read_text())
assert ci['headSha'] == HEAD and ci['status'] == 'completed' and ci['conclusion'] == 'success'
jobs = {job['name']: job for job in ci['jobs']}
names = ('tests (windows-latest)', 'tests (macos-latest)', 'check', 'windows-probes')
assert all(jobs[name]['conclusion'] == 'success' for name in names)
receipts = {}
for name in ['final-check'] + [
    'final-r2-' + case for case in
    ('media_root_race', 'path_delete_race', 'card_reader_retarget', 'lut_reimport_probe', 'http_boundary_extra')
] + ['final-r3-' + case for case in ('extra', 'loop', 'contracts')]:
    record = json.loads((OUT / (name + '-receipt.json')).read_text())
    assert record['head'] == HEAD and record['exit_code'] == 0 and record['source_hashes_unchanged']
    assert record['automatic_reruns'] == 0 and record['nice'] == 10
    receipts[name] = record
native_evidence = json.loads((OUT / 'windows-native-evidence.json').read_text())
assert native_evidence['head'] == HEAD
processes = native_evidence['process_relationships']
coverage = json.loads((OUT / 'coverage.json').read_text())['totals']
cases = list(ElementTree.parse(OUT / 'final-check.xml').iter('testcase'))
assert all(c.find('error') is None and c.find('failure') is None and c.find('rerun') is None for c in cases)
skipped = sum(c.find('skipped') is not None for c in cases)
passed = len(cases) - skipped
files = subprocess.check_output(['git', 'diff', '--name-only', 'f47572e', HEAD], cwd=ROOT, text=True).splitlines()
(OUT / 'changed-files.txt').write_text('\n'.join(files) + '\n', encoding='utf-8')
(OUT / 'final-source.diff').write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'f47572e', HEAD], cwd=ROOT))
tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in tracked if name and (ROOT / name).is_file()}
frozen = json.loads((OUT / 'review-inputs.json').read_text())['frozen_review_inputs']
assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == value for name, value in frozen.items())
color = [name for name in manifest if name.startswith('src/gxr_studio/engine/') or name in
         ('src/gxr_studio/lut/spaces.py', 'src/gxr_studio/lut/photo.py', 'src/gxr_studio/gpu/tables.py', 'src/gxr_studio/web/assets/gpu/engine.js')]
assert all(subprocess.check_output(['git', 'show', 'f47572e:' + name], cwd=ROOT) == (ROOT / name).read_bytes()
           for name in color)
(OUT / 'final-source-manifest.json').write_text(json.dumps({
    'head': HEAD, 'files': manifest, 'frozen_review_input_count': len(frozen),
    'color_source_files_unchanged': color,
}, indent=2) + '\n', encoding='utf-8')

def link(name):
    return jobs[name]['url']

def summary(filename):
    text = (OUT / filename).read_text(encoding='utf-8')
    matches = re.findall(r'\d+ passed(?:, \d+ skipped)?(?:, \d+ warnings?)? in [^\r\n=]+', text)
    assert matches, filename
    return matches[0].strip()

rows = '\n'.join(
    '| [' + name + '](' + link(name) + ') | success | ' + summary(filename) + ' |'
    for name, filename in (
        ('tests (windows-latest)', 'ci-final-windows.log'),
        ('tests (macos-latest)', 'ci-final-macos.log'),
        ('check', 'ci-final-check.log'),
    )
)
changed = '\n'.join('- `' + name + '`。' for name in files)
report = f'''可以交复审

对象：PR #16 第三轮问题；交接基线 `f47572e6ac524400b79f6bebf986be368525e0a6`，最终本地提交 `{HEAD}`。工作树仍在 `feat/gpu-preview`，仅推送 `ci/win-fix-r3`。没有更新 PR 分支、main、仓库设置或 PR 评论。

同一最终 SHA 的完整 CI

| 任务 | 结果 | 完整套件记录 |
| --- | --- | --- |
{rows}

[Windows 短任务]({link('windows-probes')}) 也通过，包含独立 I/O、事件循环、双工作线程矩阵和逆矩阵、64 MiB 精确表，以及原生句柄、盘符根读取、读卡边界、离线守卫、A1a r2/r3、恢复、启动脚本和 GPU API 用例。[原生断言清单](fix_r3/windows-native-evidence.json)逐项保存 9 个句柄与盘符根、7 个网络守卫、11 个读卡边界通过记录；[显卡颜色清单](fix_r3/gpu-colour-evidence.json)保存 13 组完整比较结果。短任务上限 15 分钟，用 `-x -vv` 保留首错，并在数值计算之前检查父进程终止与 worker 退出；完整任务没有省略测试文件，用 `-vv --maxfail=10` 保留首批异常，最终运行执行到套件末尾。完整任务均设零自动重跑。[运行元数据](fix_r3/ci-final.json) 与逐任务日志绑定同一 headSha。

P1-01：Windows 数值计算运行库

独立入口不导入 GXR 平台句柄层，也不分配完整 LUT：两个线程各做 256 次 65536×3 矩阵乘法，NumPy 2.4.3 所带 OpenBLAS 0.3.31.dev 仍在 120 秒上限停住；逆矩阵入口通过。旧轮子设置 `OPENBLAS_NUM_THREADS=1` 的对照通过。见[旧运行库分离试验](https://github.com/aa2246740/gxr-studio/actions/runs/41558033437/job/125661593199)及 [ci-matrix-probes.log](fix_r3/ci-matrix-probes.log)。

同一 Windows runner 中只换为 NumPy 2.5.4 / OpenBLAS 0.3.34.106.0，使用默认 BLAS 设置，双工作线程和完整表均通过。旧轮子的成功对照与新轮子的 67108864 字节表 SHA-256 都是 `0f87d0cb7e25e7b1c9cf03a5a1a852ff819d773b6de41f21bd97b3836f5df92c`。见[运行库 A/B](https://github.com/aa2246740/gxr-studio/actions/runs/41559002510/job/125664785485)、[原始配置和表哈希](fix_r3/ci-runtime-update-probes.log)。

因此只在 Windows 锁定 NumPy 2.5.4，其他平台继续 2.4.3。保留两个 LUT 工作线程，没有更换颜色算法。2.5.4 的[官方发布时间](fix_r3/numpy-release.json)为 2026-10-10，满足仓库七天规则。最终 Windows 短任务和完整任务均使用默认 BLAS 设置通过。历史访问违规没有原生 C 栈，本轮独立复现的是同一矩阵路径停住；证据定位到旧 Windows 数值运行库组合，没有确定具体原生指令。

颜色用例现在对全部 16777216 个 RGB 输入逐字节比较精确表与生产 `_apply`，包括 1D shaper、3D LUT 和 V-Log 输出空间。原来的样本比较已扩大为全量比较。{len(color)} 个引擎、颜色函数、表实现及引擎产物文件与基线逐字节相同，详见[源码清单](fix_r3/final-source-manifest.json)。默认开关仍为 false；关闭时不预热、不打开照片的现有测试通过。

P1-02：普通导入和哈希读取

旧 `open_rb` 先解析照片父目录，逐级打开时起点已经落在链接指向的位置。现在要求显式卡根，先以不跟随链接的方式打开卡根并核对 dev/ino，再按卡内相对路径逐级打开目录和文件。拒绝父级分量和卡根以下任何链接，不再解析照片父目录。导入与覆盖核对在扫描前保存卡根身份，普通暂存、已知文件哈希和核对哈希都传递该身份。DAT 读取也改用卡根入口。

Windows 盘符根目录没有末级名称，原卡根入口会把它作为空分量拒绝。现在文件系统根直接使用平台层的根句柄入口，随后继续核对身份和逐级打开。新增 Windows 原生用例比较盘符根 dev/ino，并从该句柄逐级读取 pytest 临时目录内的全部 256 种字节及控制字节。没有读取盘根中的其他文件。

`test_card_read_boundaries.py` 实际执行暂存和哈希：父目录原本是链接、扫描后被换成链接都拒绝，卡根替换也拒绝，暂存目录为空，目录外读取审计为空；另以全部 256 种字节、CRLF、0x1a 和 NUL 确认二进制内容完整。Windows 原生与 macOS 完整套件均通过。[r3 原读取反例复跑](fix_r3/extra-boundaries.json)记录 `swapped=true`、`staged_content=null`、`CardReadError`。

P2-01：离线守卫与事件循环

仅识别 CPython socketpair 退回函数的代码对象、事件循环 self-pipe 创建函数、该次客户端 socket 对象及监听 socket 的本机地址。普通本地 TCP、外部 TCP、直接调用退回 socketpair 和 DNS 仍拒绝。事件循环不会留下网络记录；每个测试开始和结束都清空记录。子 pytest 的真实两用例检查确认：前一个测试的联网记录导致该测试报错，后一个测试仍正常通过。Windows Proactor 原生入口与强制退回路径均通过。

FIX_R2 四项 Windows 遗留

| 项目 | 最终 Windows 原生证据 |
| --- | --- |
| `rename_at` 的 RootDirectory | 父目录改名并放入链接后，Ex 与强制 classic 两条分支都只替换已打开目录里的目标；目录外目标保留。 |
| `_delete_open` 的退回 | 文件、目录各强制 Ex 不支持，classic 使用同一对象句柄；只删除原对象，目录外内容保留。 |
| `listdir_fd` 的偏移 | 700 个长 Unicode 与非 BMP 名称跨多个 64 KiB 缓冲区，两次完整枚举集合和数量相同，验证偏移与 Restart。 |
| `lstat_at` 的 dev/ino | 相对句柄结果与原生路径 stat/lstat 比较文件、目录和链接身份；另建立真实目录联接并确认拒绝读取、只删除链接本身。 |

这些是 [tests/test_windows_io.py 的实际 Windows 运行]({link('windows-probes')})，不再以宿主模型代替原生结果。原 r3 Windows 布局和控制流模型仍通过，证据层级单独保留在 [windows-contracts.json](fix_r3/windows-contracts.json)。

完整 Windows 套件揭示的其他问题

- Windows `st_ctime` 是创建时间，写完恢复 mtime 后旧内容证明仍可能被复用。新增按已打开句柄读取 FILE_BASIC_INFO.ChangeTime 的状态接口，内容核对、扫描状态和图库证明统一使用；保留 birthtime 和 dev/ino。原生测试验证结构大小 40、ChangeTime 偏移 24，以及恢复 mtime 后 ChangeTime 仍变化。原 r2 的持续修改和证明失效用例通过。
- NTSTATUS 的目录类型错误会被 Win32 转成拒绝访问，媒体接口因此选错错误分支。平台层保留 EISDIR/ENOTDIR 与原始 NTSTATUS；实际目录读取测试通过。
- 测试文本读写和 Node 输出显式使用 UTF-8，私有字节扫描与引擎文件清单统一用 `/`。二进制参数只缩短测试 ID，保留全部归档内容与断言；{len(cases)} 个用例的最长 ID 为 243 字符。
- Windows 在子文件仍打开时拒绝目录移动。旧 r3 写入反例现在核实系统拒绝确实发生在改名处、源目录仍在、目录外没有文件，以及原文件和短写字节状态；若移动成功，继续原来的清空字节和错误内容断言。macOS 的实际移动路径仍通过，未跳过该组用例。
- 导出失败用例原来写死 `/proc/...`，在 Windows 会先得到路径不完整的错误。改为隔离临时目录中的普通文件加子路径，使各平台都实际触发建目录失败，并核对原文件字节保留。
- Git 在 Windows 默认将源文件转成 CRLF，导致锁定引擎的原始字节哈希不符；`.gitattributes` 固定文本检出为 LF，保留原哈希断言。校准、相机数据和 LUT 任务的 JSON 读写显式使用 UTF-8，修复系统代码页导致的校准不可用。
- 父进程终止用例在 Windows 88% 处停在 `stdout.readline()`，旧启动器创建下一层 Python 时未显式传递标准句柄；Windows 默认关闭普通句柄继承，PID 未进入测试管道。现在显式传递 stdout/stderr，子进程 stdin 指向空设备；PID 等待限 30 秒，另存启动 PID 与 stderr，失败时也回收父子进程和管道。最终 Windows 进程记录是启动器 {processes['launcher']}、实际父 Python {processes['parent']}、worker {processes['worker']}，worker 的 `getppid()` 为 {processes['reported_parent']}；生产传入的父 PID 是 {processes['expected_parent']}。Windows 虚拟环境启动器使 `Popen.pid` 和 `getppid()` 都不能直接代表本用例要终止的 Python 父进程。用例改为按生产 `GXR_STUDIO_PARENT_PID` 协议传入实际父 PID，记录启动器、实际父进程、worker 和 `getppid()`，强杀实际父进程后要求 worker 自行退出。导入终止用例也在就绪消息中报告 `os.getpid()`，对实际进程发出终止，保留 20 轮、25 次终止与恢复并记录全部 PID。独立存活检查声明 64 位 HANDLE 的完整 ctypes 签名。短任务先实际运行两个父进程生命周期用例及 25 次导入终止，完整套件仍保留这些用例。
- Windows 不使用 POSIX 的 `0600` 位表达访问控制。偏好文件用例在 POSIX 继续检查 `0600`，在 Windows 读取原生 DACL 与文件所有者 SID，要求所有者是当前用户或 Administrators，允许项只含当前用户、所有者、SYSTEM 和 Administrators；原偏好值、原子替换和临时文件断言均保留。
- 测试隔离同时设置 Windows 的 USERPROFILE、HOMEDRIVE、HOMEPATH、APPDATA 和 LOCALAPPDATA，使 `Path.home()` 与默认应用目录都指向测试目录。卷守卫的基路径也先转为同一平台的绝对路径，修复 Windows 事件路径带盘符而守卫仍使用 `/Volumes` 字符串的差异；真实 listdir/open 的拒绝断言全部保留，stat 用实际测试目录作正向控制。
- 启动脚本的语法测试原来在 Windows 调用 PATH 中的 WSL 占位 `bash.exe`，未安装发行版时直接失败。Windows 改为显式使用 Git for Windows 自带 Bash，保留同一脚本的语法、执行权限和参数传递断言，增加 30 秒上限；短任务和完整套件都执行这项测试。
- Windows Chrome 的 WebGPU 初始化需要先向 ANGLE 取得 D3D11 设备。测试让 ANGLE 使用系统 WARP 软件设备，再由 Dawn 选择 SwiftShader；快速入口要求适配器明确报告 SwiftShader，随后完整运行 13 组颜色对照。初始化失败时保留 stderr 与内部日志。生产引擎和着色器没有改动。
- 终止恢复用例等待实际提交或核对阶段后再终止子进程，取代固定等待；保留 20 轮与 25 次实际终止。Range 用例直接追踪 13 个生产媒体 fd 的 dev/ino 并要求全部释放；独立复审脚本的全进程 fd 核对仍保留，结果 7→7。

最终本机及复审复跑

本机 `make check`：{passed} passed、{skipped} skipped、0 自动重跑，覆盖率 {coverage['percent_covered']:.8f}%（{coverage['covered_lines']}/{coverage['num_statements']} 条，排除 {coverage['excluded_lines']} 条）。[回执](fix_r3/final-check-receipt.json)、[JUnit](fix_r3/final-check.xml)、[coverage.json](fix_r3/coverage.json)均保留。nice 10、串行，源码前后哈希相同。本机覆盖率的排除项含 Windows 专用分支，其运行证据见 Windows 原生任务。中间主动终止的检查和失败 CI 单独保留，不计入最终通过证据。

| 复审脚本 | 最终结果 |
| --- | --- |
| r2 media_root_race | 替换发生，读取拒绝，无目录外字节。 |
| r2 path_delete_race | 替换发生，原对象删除，目录外文件保留。 |
| r2 card_reader_retarget | 列目录与读开头绑定原句柄，只读自己文件。 |
| r2 lut_reimport_probe | key、ETag、表随颜色规范改变，生产函数对照相同。 |
| r2 http_boundary_extra | 根和中间链接拒绝；超长 Range 12 次 200，fd 7→7。 |
| r3 extra_boundaries | 新的普通导入读取拒绝；响应、写入、改名、同步异常的 fd 与临时文件检查通过。 |
| r3 windows_loop_guard | 实际事件循环建立成功，联网记录始终为空。 |
| r3 windows_contracts | 布局和宿主控制流模型通过；Windows 原生结果见上表。 |

八个 `final-r2-*` / `final-r3-*` 回执都绑定 `{HEAD}`，源码哈希稳定。原始复审输入 {len(frozen)} 个文件哈希未变。脚本所需接口和预期结果调整均有原始哈希及 `.diff`，没有修改冻结输入。

改动文件（相对交接 SHA，共 {len(files)} 个）

{changed}

交付与边界

[SHA256SUMS](fix_r3/SHA256SUMS)覆盖报告、进度、最终源码清单、补丁、CI 日志、回执和复跑证据。任务临时目录、pytest 临时文件及浏览器 profile 的最终清理见 [cleanup.json](fix_r3/cleanup.json)。本机浏览器使用固定 Playwright 1.61.1 / Chromium Headless Shell 1228，并正常关闭。未访问真实存储卡、机主 Studio、真实图库或导出目录；公开提交只含代码、合成数据与依赖锁。

本轮证明宿主行为、Windows 原生文件系统 API 和 CI 软件显卡颜色路径。Windows D3D12 硬件显卡、真实 Windows 读卡器与 FAT32 卡、OneDrive 实际部署、掉电落盘、相机和固件设备层均未运行。

门槛结论：可以交复审。最终本地 SHA `{HEAD}`；`ci/win-fix-r3` 的 Windows tests、macOS tests、check 均 success，Windows 短任务也 success。清理结果以附带实际回执为准；调试分支保留给机主核对后删除。
'''
(OUT.parent / 'FIX_R3.md').write_text(report, encoding='utf-8')
(OUT / 'verification-summary.json').write_text(json.dumps({
    'head': HEAD, 'gate': '可以交复审', 'ci_run': ci['url'],
    'jobs': {name: {'result': jobs[name]['conclusion'], 'url': jobs[name]['url']} for name in names},
    'local': {'passed': passed, 'skipped': skipped, 'automatic_reruns': 0, 'coverage': coverage},
    'review_replays': {name: value['exit_code'] for name, value in receipts.items() if name != 'final-check'},
    'frozen_inputs_unchanged': len(frozen), 'changed_files': len(files),
    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(OUT.parent / 'FIX_R3.md')
