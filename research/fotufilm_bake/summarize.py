#!/usr/bin/env python3
"""Merge bake/similarity/auto-levels JSON into local/summary.json and markdown tables (local/tables.md)."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from common import CAPTURES, CUBES, LOCAL, apply_lut, de00, dump, lab, read_cube_table, check_paths

ORDER = ['黑白', '反转片', '彩色负片', '电影卷', '拍立得', '红外/特殊']


def category(r):
    sid = r['id']
    if r['monochrome']:
        return '黑白'
    if sid in ('aerochrome1443', 'infraredcolor', 'aerocolor2460') or sid.startswith('lomochrome'):
        return '红外/特殊'
    if r['reflection_print']:
        return '拍立得'
    if r['reversal']:
        return '反转片'
    if r['format'] == 'super35' or sid.startswith('cinestill'):
        return '电影卷'
    return '彩色负片'


def load(pattern):
    rows = []
    for p in sorted(LOCAL.glob(pattern)):
        rows += json.loads(p.read_text())
    return rows


def pct(v):
    return '—' if v is None else f'{100 * v:.1f}%'


def main():
    bake = {r['id']: r for r in load('bake_*of*.json')}
    sim = {}
    for r in load('similarity_*of*.json'):
        sim[(r['stock'], r['usage'])] = r
    auto = {r['id']: r for r in load('autolevels*.json')}
    rows = sorted(bake.values(), key=lambda r: (ORDER.index(category(r)) if r.get('success') else 9, r['id']))

    # pairwise distinctness on the validation photos (median dE00 between the baked sRGB LUT outputs)
    from bake import PHOTOS, load_photos
    small, _ = load_photos('sum.u16')
    flat = np.concatenate([small[n].reshape(-1, 3) for n in PHOTOS])[::7]
    labs = {r['id']: lab(apply_lut(read_cube_table(CUBES / r['cubes']['srgb']), flat))
            for r in rows if r.get('success')}
    ids = list(labs)
    D = np.zeros((len(ids), len(ids)))
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            D[i, j] = D[j, i] = float(np.median(de00(labs[ids[i]], labs[ids[j]])))
    near = {ids[i]: sorted(((D[i, j], ids[j]) for j in range(len(ids)) if j != i))[:2] for i in range(len(ids))}

    lines = ['## 胶片清单与一致性', '',
             '| 类别 | id | 名称 | 介质 | 逐点检验 | LUT↔引擎 sRGB 中位 / p99 / 最大 | P3 中位 / p99 | 8 位输出 中位 / p99 | 整幅↔逐点 中位 / p99 | 整幅低通↔LUT 中位 / p99 | 超出 sRGB 的节点 |',
             '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    summary = []
    for r in rows:
        if not r.get('success'):
            lines.append(f'| ? | {r["id"]} | {r.get("name")} | — | 失败：{r.get("error", "")[:80]} | | | | | | |')
            continue
        e, p, b8 = (r['lut_vs_engine'][k] for k in ('srgb_tetra', 'p3_tetra', 'srgb_tetra_8bit_out'))
        ff = r['full_frame']
        fw = max(ff.values(), key=lambda v: v['full_vs_pointwise']['p99'])['full_vs_pointwise']
        lp = max(ff.values(), key=lambda v: v['lowpass8_full_vs_lut']['p99'])['lowpass8_full_vs_lut']
        pw = '通过' if r['pointwise_max_u16'] == 0 else f'差 {r["pointwise_max_u16"]:.0f}/65535'
        lines.append(f'| {category(r)} | `{r["id"]}` | {r["name"]} | {r["medium"]} | {pw} | '
                     f'{e["median"]:.2f} / {e["p99"]:.2f} / {e["max"]:.2f} | {p["median"]:.2f} / {p["p99"]:.2f} | '
                     f'{b8["median"]:.2f} / {b8["p99"]:.2f} | {fw["median"]:.2f} / {fw["p99"]:.2f} | '
                     f'{lp["median"]:.2f} / {lp["p99"]:.2f} | {100 * r["grid_out_of_srgb_share"]:.1f}% |')
        s = {'id': r['id'], 'name': r['name'], 'category': category(r), 'medium': r['medium'],
             'lut_vs_engine_srgb': e, 'lut_vs_engine_p3': p, 'full_vs_pointwise_worst': fw,
             'lowpass_full_vs_lut_worst': lp, 'pass': e['median'] < .5 and e['p99'] < 2,
             'nearest': [(round(d, 2), n) for d, n in near.get(r['id'], [])]}
        for usage in ('jpeg', 'scene'):
            x = sim.get((r['id'], usage))
            if x and x.get('success'):
                t, l = x['camera_table_safe'], x['lut_on_04']['rgb17']
                s[usage] = {'table_syn': t['synthetic_holdout']['similarity'],
                            'table_scene': t['scene_holdout']['similarity'],
                            'lut17_syn': l['synthetic_holdout']['similarity'],
                            'lut17_scene': l['scene_holdout']['similarity'],
                            'lut33_syn': x['lut_on_04']['rgb33']['synthetic_holdout']['similarity'],
                            'base_de': t['synthetic_holdout']['baseline_de00_median'],
                            'table_de': t['synthetic_holdout']['de00']['median'],
                            'lut17_de': l['synthetic_holdout']['de00']['median'], 'bw': t['bw_native03']}
        if r['id'] in auto:
            s['autolevels'] = auto[r['id']]
        summary.append(s)

    lines += ['', '## 相似度（全部是电脑预测）', '',
              '| 类别 | id | 用法 | 相机表（合成 / 实景） | 机内 17³（合成 / 实景） | 机内 33³ | 04→目标 ΔE00 | 相机表余差 | 17³ 余差 | 最近的另一支（中位 ΔE00） |',
              '|---|---|---|---:|---:|---:|---:|---:|---:|---|']
    for s in summary:
        for usage, label in (('jpeg', '接 04 JPEG'), ('scene', '场景光')):
            x = s.get(usage)
            if not x:
                continue
            nn = '、'.join(f'{n} {d}' for d, n in s['nearest']) if usage == 'jpeg' else ''
            lines.append(f'| {s["category"] if usage == "jpeg" else ""} | {"`" + s["id"] + "`" if usage == "jpeg" else ""} | {label} | '
                         f'{pct(x["table_syn"])} / {pct(x["table_scene"])} | {pct(x["lut17_syn"])} / {pct(x["lut17_scene"])} | '
                         f'{pct(x["lut33_syn"])} | {x["base_de"]:.2f} | **{x["table_de"]:.2f}** | {x["lut17_de"]:.2f} | {nn} |')
    if auto:
        lines += ['', '## 屏幕介质的 Auto Levels（应用默认）与固定烘焙相差多少', '',
                  '| id | 照片 | Auto Levels ↔ 烘焙 LUT 中位 / p99 |', '|---|---|---:|']
        for sid, a in sorted(auto.items()):
            for n, v in a['photos'].items():
                lines.append(f'| `{sid}` | {n} | {v["median"]:.2f} / {v["p99"]:.2f} |')
    out = LOCAL / 'tables.md'
    check_paths(out)
    out.write_text('\n'.join(lines) + '\n')
    dump(LOCAL / 'summary.json', {'stocks': summary, 'ids': ids, 'pairwise_median_de00': D.round(3).tolist()})
    ok = sum(s['pass'] for s in summary)
    print(f'{ok}/{len(summary)} pass median<0.5 & p99<2; tables -> {out}')


if __name__ == '__main__':
    main()
