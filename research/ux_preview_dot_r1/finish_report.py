"""Fill the report only after exact-artifact native evidence and packaging pass."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/'artifacts.py'),'--package'],cwd=ROOT,check=True)
    subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/'summarize.py')],cwd=ROOT,check=True)
    costs=json.loads((HERE/'local/artifacts/costs.json').read_text())
    rows=costs['transitions']
    lo_rpc=min(r['rpc_calls'][0] for r in rows);hi_rpc=max(r['rpc_calls'][1] for r in rows)
    lo_bytes=min(r['unit_write_bytes'][0] for r in rows);hi_bytes=max(r['unit_write_bytes'][1] for r in rows)
    lo_ins=min(r['instructions'][0] for r in rows);hi_ins=max(r['instructions'][1] for r in rows)
    lo_cycles=min(r['base_cycle_model'][0] for r in rows);hi_cycles=max(r['base_cycle_model'][1] for r in rows)
    lo_ms=min(r['cpu_ms_conditional'][0] for r in rows);hi_ms=max(r['cpu_ms_conditional'][1] for r in rows)
    threshold=min(r['rtt_ms_to_reach_500'] for r in rows)
    p=HERE/'REPORT.md';text=p.read_text()
    lines=text.splitlines()
    assert lines[0].startswith('# gen 118')
    lines[2]=(f'两项 UX 已在三个单元的 native harness 路径验证：移动即预览，ADJ/OK/半按离开保留所见；'
        f'黄点采用允许的次选，最终重画与高亮重合，未彻底去掉。只改配方包，resident 不变。'
        f'每格实计 {lo_rpc}–{hi_rpc} 次 RPC、{lo_bytes}–{hi_bytes} B 单元写入，'
        f'CPU 条件估计 {lo_ms:.1f}–{hi_ms:.1f} ms，另加真实 RPC 和显示等待。'
        f'遗留风险：持续断链仍可留下混合行，须重启；H08 前的旧标记中间绘制和实机时延未验收。'
        f'这是离线候选，未达到“任何故障都不混合”的完整验收。')
    text='\n'.join(lines)+'\n'
    text=text.replace('最终复查应为全部未变','最终复查全部未变')
    text=text.replace('待最终结果写入。','最终同一 SHA 的三个单元完整矩阵均通过。')
    text=text.replace('待封存','PASS')
    text=text.replace('待最终计数封存。',f'独立计量三个单元共 {sum(u["measured_moves"] for u in costs["units"])} 次导航，覆盖 {len(rows)} 种相邻转移，每单元每种重复两次；另有功能矩阵的 {sum(u["functional_fast_moves"] for u in costs["units"])} 次连续滚动。'
        f'每步非 NOP 指令为 {lo_ins:,}–{hi_ins:,}，基础周期为 {lo_cycles:,}–{hi_cycles:,}。')
    table=(HERE/'local/artifacts/cost-table.md').read_text().strip()
    block='<!-- MEASURED_COSTS_BEGIN -->\n'+table+'\n<!-- MEASURED_COSTS_END -->'
    if '<!-- MEASURED_COSTS_BEGIN -->' in text:
        text=re.sub(r'<!-- MEASURED_COSTS_BEGIN -->[\s\S]*?<!-- MEASURED_COSTS_END -->',lambda _:block,text)
    else:text=text.replace('\n周期模型沿用 ', '\n'+block+'\n\n周期模型沿用 ',1)
    text=text.replace('如果最慢步约 227 个 RPC，平均 RTT 超过约 2 ms',
                      f'按上述 CPU 情景、忽略显示等待，平均 RPC 耗时达到约 {threshold:.2f} ms')
    fault=costs['faults']
    failure_cost=(f'补偿属于异常慢路径，本次记录为 {min(f["rpc_calls"] for f in fault)}–'
        f'{max(f["rpc_calls"] for f in fault)} 次 RPC、'
        f'{min(f["write_bytes"] for f in fault)}–{max(f["write_bytes"] for f in fault)} B W 尝试；'
        f'包含强制全行写入及逐 word 读回，不能套用正常滚动延迟。'
        f'完整计数见 [costs.json](local/artifacts/costs.json)。')
    if failure_cost not in text:text=text.replace('\n## 7. 构建、复核与卡包','\n'+failure_cost+'\n\n## 7. 构建、复核与卡包')
    evidence='额外边界复核：曾给 04 保存 contrast +1 后，双故障退回纯 04，再按 ADJ 不新增 RPC/refresh，仍为纯 04；[结果](local/runs/fallback-fn2-50mm.json)。'
    if evidence not in text:text=text.replace('\n明确取消键：', '\n'+evidence+'\n\n明确取消键：')
    text=text.replace('卡包目标 `firmware/package_v36_g118/SD_ROOT`：','卡包已生成于 `firmware/package_v36_g118/SD_ROOT`：')
    assert costs['dat_sha256'] in text and '待最终' not in text and '待封存' not in text
    p.write_text(text)
    print('PASS final Chinese report: exact SHA, 3-unit matrix, real counts, stated persistent-outage limit')

if __name__=='__main__':main()
