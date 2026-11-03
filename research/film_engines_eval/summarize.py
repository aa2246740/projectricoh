#!/usr/bin/env python3
"""Collect engines.json runs into local/summary.json and local/tables.md (no new computation)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
from guard import HERE, mount_guard, install_write_fence, dump, output_path

RUNS = ('local/engines-user', 'local/engines-hf', 'local/engines-forum')


def pct(v):
    return '—' if v is None else f'{100*v:.1f}%'


def main():
    mount_guard(); install_write_fence()
    rows = []
    for run in RUNS:
        p = HERE/run/'engines.json'
        if p.exists():
            rows += json.loads(p.read_text())
    out, lines = [], ['| 族 | 外观 | 相机表 safe 合成/实景 | 机内 17³ 合成/实景 | 机内 33³ | YCbCr 17³ | 相机表+残差 17³ | 04→目标 ΔE00 | 相机表余差 ΔE00 | 机内17³余差 ΔE00 |',
                      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        if not r.get('success'):
            lines.append(f"| {r['family']} | {r['label']} | 失败：{r.get('error','')} |||||||| ")
            continue
        t, l, res = r['camera_table_safe'], r['lut_on_04'], r['residual_on_recipe']['rgb17']
        d = {'family': r['family'], 'label': r['label'], 'sha256': r['sha256'], 'spaces': r['spaces'],
             'table_syn': t['synthetic_holdout']['similarity'], 'table_scene': t['scene_holdout']['similarity'],
             'lut17_syn': l['rgb17']['synthetic_holdout']['similarity'],
             'lut17_scene': l['rgb17']['scene_holdout']['similarity'],
             'lut33_syn': l['rgb33']['synthetic_holdout']['similarity'],
             'ycc17_syn': l['ycc17']['synthetic_holdout']['similarity'],
             'resid17_syn': res['synthetic_holdout']['similarity'],
             'base_de00': t['synthetic_holdout'].get('baseline_de00_median',
                                                     l['rgb17']['synthetic_holdout']['baseline_de00_median']),
             'table_de00': t['synthetic_holdout']['de00']['median'],
             'lut17_de00': l['rgb17']['synthetic_holdout']['de00']['median'],
             'bw_native03': t['bw_native03'], 'solver_success': t['solver_success']}
        out.append(d)
        lines.append(f"| {d['family']} | {d['label']} | {pct(d['table_syn'])} / {pct(d['table_scene'])} | "
                     f"{pct(d['lut17_syn'])} / {pct(d['lut17_scene'])} | {pct(d['lut33_syn'])} | {pct(d['ycc17_syn'])} | "
                     f"{pct(d['resid17_syn'])} | {d['base_de00']:.2f} | {d['table_de00']:.2f} | {d['lut17_de00']:.2f} |")
    dump(HERE/'local/summary.json', out)
    t = output_path(HERE/'local/tables.md')
    t.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
