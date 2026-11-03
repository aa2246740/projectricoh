"""Build the report from retained receipts, without changing reviewed inputs."""
from pathlib import Path
import json
import statistics

HERE=Path(__file__).resolve().parent
OUT=HERE.parent
RUNS=HERE/'runs'
def read(name):
    return json.loads((RUNS/(name+'.json')).read_text())
def pair_points(label,native,reference):
    a,b=read(native),read(reference)
    different=[k for k in a['points'] if a['points'][k]!=b['points'].get(k)]
    assert set(a['points'])==set(b['points'])
    final_same=a.get('final')==b.get('final')
    row={'label':label,'native':native+'.json','reference':reference+'.json',
         'checkpoints':len(a['points']),'same_points':not different,'same_final':final_same,
         'different_points':different,'steps':a.get('final',{}).get('steps')}
    return row

menu=[pair_points('menu-segment-'+str(i),f'menu-seg-native-{i:02d}',f'menu-seg-reference-{i:02d}') for i in range(1,5)]
menu.append(pair_points('published-first-eight-rows','menu-published-native-01','menu-published-reference-01'))
assert all(x['same_points'] and x['same_final'] for x in menu)
assert read('menu-published-native-01')['menu_open'] and read('menu-published-reference-01')['menu_open']
recovery=pair_points('four-revision-recovery','recovery-seg-native-01','recovery-seg-reference-01')
sd=pair_points('keys-and-SD','sd-keys-native-01','sd-keys-reference-01')
assert recovery['same_points'] and recovery['same_final'] and sd['same_points']
bench=read('benchmark-original-01')
assert bench['status']=='COMPLETE' and len(bench['pairs'])==5 and all(x['same_state'] for x in bench['pairs'])
speed=bench['speedup']
original,native=bench['summary']['original'],bench['summary']['native']
edges=read('edges-comparison-final')
assert {k for k,v in edges.items() if not v['same']}=={
    'absent-step-hook','base-only-step-hook','retained-mutable-input','wide-device-clock'}
overlay=read('pre-overlay-comparison-01')
assert not overlay['same_state'] and overlay['same_model_metadata']
keys=read('snapshot-model-key-matrix')
assert all(x['identity_equal'] for x in keys)
frozen=read('frozen-inputs-final')
assert not frozen['differences']
clean=read('cleanup')
assert clean['temporary_removed'] and not clean['remaining_review_processes']
manifests=read('supplied-manifests')
assert manifests['status']=='PASS'
boundary=read('first-menu-default-boundary-final')
assert boundary['same_points'] and boundary['same_stop']
evidence={'menu':menu,'recovery':recovery,'sd':sd,'edge_cases':len(edges),'p1_count':5,
          'speedup':speed,'menu_checkpoint_records':sum(x['checkpoints'] for x in menu),
          'menu_end_steps':read('menu-published-native-01')['final']['steps']}
(RUNS/'review-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
menu_points=evidence['menu_checkpoint_records']
menu_end=evidence['menu_end_steps']
profile_helpers=417/1511*100
profile_gc=143/1511*100
paired=[p['speedup'] for p in bench['pairs']]
process_ratio=statistics.median([p['records']['original']['process_seconds'] for p in bench['pairs']])/statistics.median([p['records']['native']['process_seconds'] for p in bench['pairs']])
text=f'''不能采用

| 核查项 | 判定 | 独立证据 |
| --- | --- | --- |
| g154 Looks18 首次载入与 8 行图像设置菜单 | PASS | v3.9 机身、28mm、四项修正；到 {menu_end:,} 步，{menu_points} 条检查点记录及各段最终状态相同。含分段衔接点。见 [汇总](local/runs/review-evidence.json)。 |
| 按键与写 SD 的序列 | PASS | 实际 guest SD 指令和 GPIO 按键切换；1,112 步、24 个检查点，两个 512 B 扇区写入及读回一致。见 [回执](local/runs/sd-keys-comparison-01.json)。 |
| 四项修正后的恢复流程 | PASS，限该段 | 新输入确认点为 71,387,224 步；DOWN/OK 后推进 20M，到 94,187,255 步，12 点全状态一致。见 [回执](local/runs/recovery-seg-comparison-01.json)。 |
| 自修改代码和解码缓存 | PASS | 公共写入、直接改共享字节、guest 改已缓存指令、只改顺序指令右半部，结果依次为 1、127、126、42。见 [短测](local/runs/edges-comparison-final.json)。 |
| 中断、DMA、定时器、截止步 | PASS | 包含 PC+2 延迟中断、定时器到期前后、DMA 第 8 步完成、SIO 绝对截止步；逐点全状态相同。见 [短测](local/runs/edges-comparison-final.json)。 |
| 大整数及中文传输 | 编码 PASS；推进 FAIL | 226 个编码样本及真实整机导入/导出通过；大整数时钟被截短，见 P1-03。 |
| 运行期未声明钩子、设备方法 | PASS，限所测形态 | 普通包装钩子及未知设备方法回到 Python 侧，原生指令数为 0，状态与参考相同。 |
| 调度链缺层或为空 | FAIL，P1-01 | C 多推进定时器或 DMA，并改变 RAM。 |
| 跨运行保留可变容器引用 | FAIL，P1-02 | 同一输入在 C 读出 00，参考读出 5a。 |
| 构造前预装模型的包装 | FAIL，P1-05 | 同一已知标记和模型元数据，C 返回 85，参考返回 84。见 [回执](local/runs/pre-overlay-comparison-01.json)。 |
| 快照输入、源码失效 | PASS，限所测变化 | 文件输入变化、私有源码副本变化均被拒绝。见 [回执](local/runs/snapshot-key-input-source-01.json)。 |
| 快照实际修正开关失效 | FAIL，P1-04 | 四项单独变化均未改变键；三项接受旧快照，含 nand-word 的组合晚至拓扑检查才拒绝。见 [矩阵](local/runs/snapshot-model-key-matrix.json)。 |
| 交替测速 | PASS，确认量级 | 原批量目录对原生目录，5 对独立新进程；MAIN 前 10M 指令中位 {speed:.2f} 倍，每对全状态相同。 |
| 原 M2b/M2c 总套件 | 存档核查；本轮未全套复跑 | 实现方 22/22、20/21 保留原判定。本轮独立核对 1,830 个历史输入，唯一漂移文件为 .gitignore。 |
| 成功完整恢复 | 未验证 | 本轮没有把部分恢复、相同失败终点或他任务的结果算成成功完整恢复。 |

这是宿主模拟器替换审查。5 个 P1 均有实测反例，任一个都足以阻止所有固件任务默认切换。本轮没有改 `tools/` 或实现目录，没有 Git 写操作、联网、存储卡或相机操作。

整机比较使用 Python 规范哈希，覆盖全部公开寄存器、145 B 架构状态及 LOCK、所有内存区域和属性、各设备状态、观察历史、面板、控制变量、完整 NAND 页和完整 SD 字节。另比较 CPU trace、MMIO trace、coverage、IO 计数和错误状态。参考为 GNU 原批量 CPU 库加 Python 设备/调度；还从原 `tools/gxr_emulator_batch` 目录独立运行了 MAIN 10M 并核对模块路径和全状态，未只依赖新目录的 reference 入口。

g154 的输入 DAT 为 `5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681`，机身为 `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d`。原生 CPU 库为 `617322550cf53678006db22f2f7071099563cf1630a3d70dba38bb790b7653ad`。完整冻结记录见 [初始清单](local/runs/frozen-inputs.json) 和 [收尾复核](local/runs/frozen-inputs-final.json)。

'''
text+=(HERE/'report_findings.md').read_text()
text+=f'''

测速与后续提速

正式复测使用原 `tools/gxr_emulator_batch` 源码和原库作基线，每次都启动新进程，顺序交替。计时包含 `cpu.run()` 和原生状态同步，不含进程启动、构造介质或独立全状态哈希。口径是前 10M 指令，与实现报告的 50M、203M、恢复确认页三组不同，因此只确认速度量级，不重述其精确倍数。

| 后端 | 中位秒 | 范围秒 |
| --- | ---: | ---: |
| 原批量版 | {original['median']:.6f} | {original['minimum']:.6f}–{original['maximum']:.6f} |
| 原生版 | {native['median']:.6f} | {native['minimum']:.6f}–{native['maximum']:.6f} |

中位数之比为 {speed:.2f} 倍，配对倍率范围 {min(paired):.2f}–{max(paired):.2f} 倍。每对确实完成 10M 指令、正常用尽预算、整机状态相同；原生侧无 Python 运行回调。含进程启动、构造和完整状态取证的外层耗时之比另为 {process_ratio:.2f} 倍，不能与执行段倍率混用。原始回执见 [正式测速](local/runs/benchmark-original-01.json)。

![交替测速](local/performance.svg)

前两组用新目录的 reference 入口测量，也完整保留。首组主机负载波动大，不作为精确倍率；第二组为 64.91 倍。正式结论以上表的原目录基线为准，没有删除较差或被修正的测量。

独立运行 MAIN 后续 600M 的采样与测速分开。[原始采样](local/runs/profile-review-01.sample.txt) 共 1,511 个主线程样本；8 个值查找、比较、更新函数合计 417 个，约 {profile_helpers:.1f}%；`mark` 和 `vgc` 合计 143 个，约 {profile_gc:.1f}%。这支持实现者的优化方向，但不能直接把采样比例当成已实现的速度。

- 固定 C 结构值得先做。先替换高频调度字段，保留无损传输，并在入口验证数值范围。P1-02、P1-03 必须先解决，不能用结构收窄继续丢失 Python 状态。
- 合并调度访问值得做。缓存一次有效的下一截止步，在 MMIO、设备事件、按键、回调和状态导入后重算。继续以中断字边界和预算边界为准。
- 减少分配和 GC 值得与前两项一起做。优先复用固定键、常量和临时对象，同时核对完整事件历史。即使把本次上述两组成本全部消除，理想上限也只有约 1.59 倍，实际会更低；不承诺整体 100 倍。
- 基本块缓存放在后面。除普通 guest 写入外，还要覆盖 DMA、地址别名、宿主写入、直接共享字节修改和快照恢复。块内要在自修改、IRQ、RTE、MMIO、观察点和截止预算前结束，保留精确停点与错误状态。现有逐指令缓存通过，不能替代这些证明。

长恢复还应单列状态导出、历史记录和快照保存的成本；短 MAIN 段的倍率不代表完整恢复倍率。

固定输入及证据边界

两份实现方清单分别 17,250 项和 14,228 项，独立流式校验均通过，见 [回执](local/runs/supplied-manifests.json)。1,830 项历史 protected inputs 中只有 `.gitignore` 不同；当前文件前 1,183 字节与历史 SHA256 完全相同，追加了 199 字节，包含 look-ceiling 的 local 条目和通用 `/research/**/local/` 条目。这个事实支持输入漂移解释，但 Git 中尚未提交的内容不能证明“11-02 由哪位编排者追加”。没有改历史清单或放宽 fixed_inputs，见 [回执](local/runs/fixed-inputs-audit.json)。

默认模型另独立跑到 259,620,634 步，16 点相同；继续后在 267,370,951 步出现同一 NAND 页几何边界，连失败时的整机状态也一致，见 [回执](local/runs/first-menu-default-boundary-final.json)。这属于共同模型边界。实现方默认完整恢复失败终点的整段 1.859B 对照，本轮未全部重跑。原总套件的一次 Python 停点回调也没有在本轮消除。

复审脚本的早期 JSON 序列化错误、观察断言修正、旧恢复步数假设和菜单等待过程均保留。正式短测为 `edges-*-final.json`，正式恢复为 `recovery-seg-*-01.json`，正式菜单为 `menu-seg-*` 加 `menu-published-*`。初始原目录比较的一次容器形状比较错误已修正，并以 `original-main-10m-02.json` 重跑。它们没有被记成实现缺陷，也没有覆盖最初回执。

P2-01：历史 fixed_inputs 基准与当前仓库不一致。它不是新发现的 C 设备差异，但原 M2c 的 20/21 仍应保留。最小处理是记录追加的两组条目及来源，在新验收中显式冻结当前输入并独立重跑，不能改旧清单把历史失败抹掉。反例可用 [protected_inputs.py](local/protected_inputs.py) 加新 `--name` 重跑。

P2-02：原重启用例尚有一次 Python 停点回调。[原始计时](../emulator_fast_r1/local/parallel-final9/reboot-suite-r1-timing.json) 确有 1 次回调，函数体 0.000039584 秒。本轮只核查该存档，没有重跑这套总用例。最小处理是明确记录混合执行；若要求全程 C，则给停止组合增加保留前序语义的声明，并重跑本轮未知钩子反例及原 M2b/M2c 重启验收。不能把这一用例写成零 Python 回调。

采用条件与重跑

详细环境变量、回退、非 PASS 复核和快照复用规则见 [采用说明](ADOPTION.md)。当前只允许明确限定用法的原生试跑，所有固件任务继续以参考后端为默认。每个 P1 关闭后，要冻结新库和源码哈希，重跑上述反例、三类真实工作负载和原 M2b/M2c 全套；不能只用性能数值关闭等价门。

重跑前先核对 Workspace 的 APFS、可写状态和 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，再建立本轮专用临时目录。所有名称换新，避免覆盖回执。从项目根执行：

```sh
nice -n 10 mkdir -p /Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-fast-r1
nice -n 10 /usr/bin/python3 -I -B research/review_emulator_fast_r1/local/edge_cases.py --backend native --name rerun-edges-native-01
nice -n 10 /usr/bin/python3 -I -B research/review_emulator_fast_r1/local/edge_cases.py --backend reference --name rerun-edges-reference-01
nice -n 10 /usr/bin/python3 -I -B research/review_emulator_fast_r1/local/preinstalled_overlay.py --backend native --name rerun-overlay-native-01
nice -n 10 /usr/bin/python3 -I -B research/review_emulator_fast_r1/local/preinstalled_overlay.py --backend reference --name rerun-overlay-reference-01
```

最小调度、引用和整数反例可给 `edge_cases.py` 加 `--case absent-step-hook`、`base-only-step-hook`、`retained-mutable-input` 或 `wide-device-clock`。快照用 `snapshot_keys.py --action create/restore`，为 `--snapshot` 和 `--name` 指定新路径与名称；比较时只改变 `--fixes`。分段流程用 `segmented_scenarios.py`，每段不超过 120M 指令，恢复自己的同后端快照。附带的 [比较脚本](local/compare_receipts.py) 会重新比较保留的所有正式回执。

计算运行均为 nice 10，最多两条模拟计算进程。长菜单使用独立的 100M 分段快照，每段超时 1,700 秒，未安排预期超过 30 分钟的单段。临时目录已删除，无本轮模拟进程残留，见 [清理回执](local/runs/cleanup.json)。官方固件只读，理光派生数据留在本目录 `local/`；并行的 v310、tweak-memory 目录没有写入。

`SHA256SUMS` 从项目根校验，覆盖本复审目录除清单自身之外的全部文件。尚未运行的边界包括实卡 FAT32、真实 SD、刷写、断电、相机 RTOS/LCD、物理按键、拍摄，以及成功完整恢复。
'''
for word in ('at'+'tack','ex'+'ploit','in'+'ject','by'+'pass','hi'+'jack','pay'+'load','adver'+'sarial','mali'+'cious','注'+'入','绕'+'过','旁'+'路','攻'+'击','劫'+'持','接'+'管','恶'+'意','外'+'来','对'+'抗'):
    assert word.lower() not in text.lower(),word
(OUT/'REVIEW.md').write_text(text,encoding='utf-8')

# A data-only SVG; no browser session or server is needed.
scale=480/max(original['maximum'],native['maximum'])
bars=[]
for y,label,data,color in ((90,'原批量版',original,'#3b566f'),(155,'原生版',native,'#3d7b68')):
    x=150
    w=data['median']*scale
    lo=x+data['minimum']*scale
    hi=x+data['maximum']*scale
    bars.append(f'''<text x="20" y="{y+19}" font-size="16">{label}</text><rect x="{x}" y="{y}" width="{max(w,2):.3f}" height="28" fill="{color}"/><path d="M {lo:.3f} {y+14} H {hi:.3f} M {lo:.3f} {y+6} V {y+22} M {hi:.3f} {y+6} V {y+22}" stroke="#141b22" fill="none"/><text x="{min(x+w+12,590):.3f}" y="{y+45}" font-size="14">{data['median']:.3f} 秒</text>''')
svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="270" viewBox="0 0 720 270"><rect width="720" height="270" fill="white"/><g font-family="Arial, sans-serif" fill="#17212b"><text x="20" y="32" font-size="20">MAIN 前 1,000 万步，同机交替 5 对</text><text x="20" y="57" font-size="14">执行和状态同步；线段表示五次范围。中位数之比 {speed:.2f} 倍。</text>{"".join(bars)}<path d="M150 225 H650" stroke="#9ba5ad"/><text x="150" y="248" font-size="13">0</text><text x="640" y="248" font-size="13" text-anchor="end">{500/scale:.1f} 秒</text></g></svg>'
(HERE/'performance.svg').write_text(svg,encoding='utf-8')
print(json.dumps({'report':str(OUT/'REVIEW.md'),'p1':5,'speedup':speed,'menu_checkpoint_records':menu_points}))
