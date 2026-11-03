"""Derive benchmark tables and local charts directly from the five raw pairs."""
import json
import os
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
RUNS = HERE / 'runs'
assert os.getpriority(os.PRIO_PROCESS, 0) >= 15


def stats(kind):
    raw = json.loads((RUNS / ('benchmark-' + kind + '.json')).read_text())
    assert raw['status'] == 'PASS' and len(raw['pairs']) == 5
    key = 'seconds' if kind == 'main' else 'product_seconds'
    r = dict(ratios=[p['ratio'] for p in raw['pairs']], median=raw['median_pair_ratio'], range=raw['ratio_range'])
    for b in ('reference', 'native'):
        values = [p[b][key] for p in raw['pairs']]
        r[b] = dict(median=statistics.median(values), minimum=min(values), maximum=max(values))
    return r


def svg(data, width=720, height=300, static=False):
    left, right, top, bottom = 40, width - 50, 18, height - 38
    color = lambda name, fallback: fallback if static else 'var(--' + name + ', ' + fallback + ')'
    fg, muted, border = color('foreground', '#233044'), color('muted-foreground', '#657083'), color('border', '#d7dee5')
    blue, gold = color('chart-1', '#2166ac'), color('chart-2', '#9c6500')
    y = lambda v: bottom - v / 80 * (bottom - top)
    x = lambda i: left + i / 4 * (right - left)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img" aria-label="两项各五对交替测速，实线为本轮有负载样本，虚线为原报告数值">']
    if static:
        parts.append(f'<rect width="{width}" height="{height}" fill="white"/>')
    parts.append('<g font-family="-apple-system,BlinkMacSystemFont,PingFang SC,sans-serif" font-size="12">')
    for value in (0, 20, 40, 60, 80):
        parts.append(f'<line x1="{left}" x2="{right}" y1="{y(value):.2f}" y2="{y(value):.2f}" stroke="{border}"/>')
        parts.append(f'<text x="{left-9}" y="{y(value)+4:.2f}" text-anchor="end" fill="{muted}">{value}</text>')
    for i in range(5):
        parts.append(f'<text x="{x(i):.2f}" y="{bottom+22}" text-anchor="middle" fill="{fg}">{i+1}</text>')
    parts.append(f'<text x="{left}" y="11" fill="{muted}">倍</text><text x="{right}" y="{height-2}" text-anchor="end" fill="{muted}">第几对</text>')
    for key, col, claim in (('main', blue, 65.35), ('input', gold, 45.91)):
        parts.append(f'<line x1="{left}" x2="{right}" y1="{y(claim):.2f}" y2="{y(claim):.2f}" stroke="{col}" stroke-dasharray="5 5" opacity="0.6"/>')
        parts.append(f'<text x="{right+6}" y="{y(claim)+4:.2f}" fill="{col}">{claim:.2f}</text>')
        points = ' '.join(f'{x(i):.2f},{y(v):.2f}' for i, v in enumerate(data[key]['ratios']))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{col}" stroke-width="2.5"/>')
        for i, value in enumerate(data[key]['ratios']):
            parts.append(f'<circle cx="{x(i):.2f}" cy="{y(value):.2f}" r="4" fill="{col}"><title>{key} 第 {i+1} 对：{value:.2f} 倍</title></circle>')
    return ''.join(parts) + '</g></svg>'


def main():
    data = {k: stats(k) for k in ('main', 'input')}
    (RUNS / 'benchmark-summary.json').write_text(json.dumps(data, indent=2) + '\n')
    chart = svg(data, static=True)
    (HERE / 'benchmark.svg').write_text(chart + '\n')
    document = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--font-sans:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}body{margin:0;font-family:var(--font-sans);color:var(--foreground)}p{font-size:13px;line-height:1.5;margin:8px 0}.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}.main{color:var(--chart-1)}.input{color:var(--chart-2)}.note{color:var(--muted-foreground)}#chart{height:300px;width:100%}</style></head><body>
<div class="legend"><span class="main">MAIN · 逐对中位 MEDMAIN 倍</span><span class="input">输入驱动 · 逐对中位 MEDINPUT 倍</span></div>
<div id="chart"></div><p class="note">每项五对，reference/native 交替；每次实跑 50M 步并核对完整终态。虚线为原报告的 65.35 / 45.91 倍。</p><p class="note">本轮主机有负载，不能确认空闲条件下的精确倍率。MAIN 只计执行；输入驱动含构造和原有检查点保存，扣除额外审计导出。</p>
<script>const data=DATA;function draw(){const host=document.getElementById('chart');const w=Math.max(320,host.clientWidth),h=300,l=40,r=w-50,t=18,b=h-38;const x=i=>l+i/4*(r-l),y=v=>b-v/80*(b-t);let s=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="100%" height="300" role="img" aria-label="两项各五对交替测速"><g font-size="12" font-family="inherit">`;for(const v of [0,20,40,60,80])s+=`<line x1="${l}" x2="${r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--border)"/><text x="${l-9}" y="${y(v)+4}" text-anchor="end" fill="var(--muted-foreground)">${v}</text>`;for(let i=0;i<5;i++)s+=`<text x="${x(i)}" y="${b+22}" text-anchor="middle" fill="var(--foreground)">${i+1}</text>`;s+=`<text x="${l}" y="11" fill="var(--muted-foreground)">倍</text><text x="${r}" y="${h-2}" text-anchor="end" fill="var(--muted-foreground)">第几对</text>`;for(const [key,color,claim]of[['main','var(--chart-1)',65.35],['input','var(--chart-2)',45.91]]){s+=`<line x1="${l}" x2="${r}" y1="${y(claim)}" y2="${y(claim)}" stroke="${color}" stroke-dasharray="5 5" opacity=".6"/><text x="${r+6}" y="${y(claim)+4}" fill="${color}">${claim.toFixed(2)}</text><polyline points="${data[key].ratios.map((v,i)=>`${x(i)},${y(v)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="2.5"/>`;data[key].ratios.forEach((v,i)=>s+=`<circle cx="${x(i)}" cy="${y(v)}" r="4" fill="${color}"><title>${key} 第 ${i+1} 对：${v.toFixed(2)} 倍</title></circle>`)}host.innerHTML=s+'</g></svg>'}new ResizeObserver(draw).observe(document.getElementById('chart'));draw();</script></body></html>'''
    document = document.replace('MEDMAIN', f"{data['main']['median']:.2f}").replace('MEDINPUT', f"{data['input']['median']:.2f}").replace('DATA', json.dumps(data))
    for name, fallback in (('foreground', '#233044'), ('muted-foreground', '#657083'),
                           ('border', '#d7dee5'), ('chart-1', '#2166ac'), ('chart-2', '#9c6500')):
        document = document.replace('var(--' + name + ')', 'var(--' + name + ',' + fallback + ')')
    (HERE / 'benchmark.html').write_text(document + '\n')
    lines = []
    for key, label in (('main', 'MAIN，执行段'), ('input', 'input_run / native_input_run，完整驱动')):
        a, b = data[key]['reference'], data[key]['native']
        lines.append(f"| {label} | {a['median']:.3f}（{a['minimum']:.3f}–{a['maximum']:.3f}） | {b['median']:.3f}（{b['minimum']:.3f}–{b['maximum']:.3f}） | {data[key]['median']:.2f}（{data[key]['range'][0]:.2f}–{data[key]['range'][1]:.2f}） |")
    text = '''本轮确认所测流程有明显提速，没有确认空闲机器上的精确 65.35 倍和 45.91 倍。正式计时每项五对新进程，固定 reference/native 顺序；两项共 20 次运行都实际完成 50M 步，配对完整状态及输入驱动业务回执均相同，原生侧全部为 C 指令，零 Python 总线/HLE 回调。

| 流程与口径 | 参考中位秒（范围） | 原生中位秒（范围） | 逐对倍率中位（范围） |
| --- | ---: | ---: | ---: |
ROWS

倍率是每对“参考秒÷原生秒”后取中位，不是表中两个独立中位秒相除。MAIN 包含 cpu.run 及状态同步，构造和独立哈希在计时外；输入驱动包含构造、执行、原有 CPU 检查点保存，扣除额外审计导出，不含模块导入。两边均 fast+batch，四项修正全关、unit-off、nice 15，实际参考库及每次负载/CPU 秒保留在回执中。这里没有用快照恢复、拒绝或未完成预算代替计算。

![五对交替测速](benchmark.svg)

正式样本见 [MAIN](runs/benchmark-main.json)、[输入驱动](runs/benchmark-input.json) 和 [计时口径](benchmark-intent.md)。原报告仅三对，且负载剧烈变化；本轮开始前仍有虚拟机重计算，启动前独立采样约 13% CPU 空闲，未取得可验证的空闲条件。数据支持提速量级，不能支持固定机器倍率承诺。精确复现需等其他重计算结束后，按相同口径再交替至少五对。

另一次 200M 指令采样未计入测速，主线程落在 gxr_machine_run 和设备值查找/更新函数中。输入驱动的独立 profile 还看到 native_machine.run 与原有 storage_run.save 两个主要阶段；额外审计导出和其状态哈希没有混入正式计时。见 [MAIN 采样](runs/profile-native.sample.txt)、[输入驱动 profile](runs/profile-input-functions.json) 和 [空闲条件采样](runs/benchmark-queue-quiet-preflight.log)。

```sh
R3=research/review_emulator_fast_r3
nice -n 15 /usr/bin/python3 -I -B "$R3/benchmark.py" --kind main --pairs 5 --label main_new
nice -n 15 /usr/bin/python3 -I -B "$R3/benchmark.py" --kind input --pairs 5 --label input_new
```'''.replace('ROWS', '\n'.join(lines))
    report = HERE / 'REVIEW.md'
    old = report.read_text()
    report.write_text(old.replace('测速结果待本轮五对交替计时结束后写入。', text))
    print(json.dumps(dict(main=data['main']['median'], input=data['input']['median'], chart=str(HERE / 'benchmark.html'))))


if __name__ == '__main__':
    main()
