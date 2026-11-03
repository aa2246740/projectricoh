"""Render only the cohort with independently recorded shooting order."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
c.guard(30)


def main():
    rows = json.loads((c.HERE / 'inference_results.json').read_text())
    rows = [r for r in rows if r['group'] == 'street-g137']
    assert len(rows) == 8
    counts = {(a, b): 0 for a in range(1, 9) for b in range(1, 9)}
    for row in rows:
        counts[int(row['truth']), int(row['best'])] += 1
    assert sum(v for (a, b), v in counts.items() if a == b) == 7
    assert counts[8, 7] == 1
    parts = ['<text x="242" y="16" text-anchor="middle">预测配方</text>',
             '<text x="4" y="183">真值</text>']
    for i in range(1, 9):
        parts.append(f'<text x="{100+(i-1)*40}" y="39" text-anchor="middle">{i:02d}</text>')
        parts.append(f'<text x="67" y="{68+(i-1)*34}" text-anchor="end">{i:02d}</text>')
    for (a, b), count in counts.items():
        x, y = 82 + (b-1)*40, 48 + (a-1)*34
        fill = 'var(--chart-1, #377d9e)' if count and a == b else 'var(--warning, #b36b25)' if count else 'var(--secondary, #eceff1)'
        color = 'var(--primary-foreground, white)' if count else 'var(--muted-foreground, #66727a)'
        parts.append(f'<rect x="{x}" y="{y}" width="36" height="30" rx="3" fill="{fill}"/>'
                     f'<text x="{x+18}" y="{y+20}" fill="{color}" text-anchor="middle">{count}</text>')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 410 326" role="img" '
           'aria-label="八张顺序标签照片的混淆表，01至07各命中一张，08被选为07" '
           'style="width:100%;height:326px;max-width:410px;font:13px sans-serif;fill:var(--foreground, #22313a)">'
           + ''.join(parts) + '</svg>')
    html = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>body{margin:0;font:14px var(--font-sans,sans-serif);color:var(--foreground)}'
            'figure{margin:0}p{margin:0 0 10px;line-height:1.55}'
            'figcaption{color:var(--muted-foreground);font-size:13px;line-height:1.55}</style>'
            '<figure><p>有拍摄顺序记录的 RAW＋JPG：7/8 与记录一致。</p>' + svg +
            '<figcaption>实际 08 → 预测 07 的一张保留为待确认。样本来自同一 MOUNT 街景；'
            '未混入历史模型参与定标的 52 张照片。</figcaption></figure></html>')
    (c.HERE / 'confusion_street.svg').write_text(svg + '\n')
    (c.HERE / 'confusion_street.html').write_text(html + '\n')
    c.dump('visual_data.json', dict(cohort='street-g137', n=8, correct=7,
           matrix=[[counts[a, b] for b in range(1, 9)] for a in range(1, 9)],
           source_sha256=c.sha(c.HERE / 'inference_results.json')))
    c.finish('visual')


if __name__ == '__main__':
    main()
