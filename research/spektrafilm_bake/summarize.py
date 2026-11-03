#!/usr/bin/env python3
"""Merge bake / similarity / NicePhoto JSON into local/summary.json and markdown tables (local/tables.md);
also the look descriptors and the spektrafilm-vs-fotufilm overlap comparison on the validation photos."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from bakelib import CUBES, LOCAL, PHOTOS, ROOT, apply_lut, check_paths, de00, dump, lab, load_photos, read_cube_table

FOTU = ROOT / 'research/fotufilm_bake/local'
ORDER = ['彩色负片', '反转片', '电影卷']
# spektrafilm film -> fotufilm stock id for the same (or nearest named) stock
OVERLAP = {'kodak_portra_400': 'portra400', 'kodak_gold_200': 'gold200', 'kodak_ektar_100': 'ektar100',
           'kodak_ultramax_400': 'ultramax400', 'fujifilm_c200': 'c200', 'fujifilm_pro_400h': 'pro400h',
           'fujifilm_xtra_400': 'superia400', 'fujifilm_provia_100f': 'provia100f',
           'kodak_ektachrome_100': 'ektachromee100', 'kodak_kodachrome_64': 'kodachrome64',
           'fujifilm_velvia_100': 'velvia50', 'kodak_verita_200d': 'verita200d',
           'kodak_vision3_250d': 'vision250d', 'kodak_vision3_500t': 'vision500t'}
SHORT = {'fujifilm_c200': 'C200', 'fujifilm_pro_400h': 'Pro 400H', 'fujifilm_provia_100f': 'Provia 100F',
         'fujifilm_velvia_100': 'Velvia 100', 'fujifilm_xtra_400': 'Superia X-TRA 400',
         'kodak_ektachrome_100': 'Ektachrome 100', 'kodak_ektar_100': 'Ektar 100', 'kodak_gold_200': 'Gold 200',
         'kodak_kodachrome_64': 'Kodachrome 64', 'kodak_portra_160': 'Portra 160', 'kodak_portra_400': 'Portra 400',
         'kodak_portra_800': 'Portra 800', 'kodak_portra_800_push1': 'Portra 800 +1', 'kodak_portra_800_push2': 'Portra 800 +2',
         'kodak_ultramax_400': 'UltraMax 400', 'kodak_verita_200d': 'Verita 200D', 'kodak_vision3_200t': 'Vision3 200T',
         'kodak_vision3_250d': 'Vision3 250D', 'kodak_vision3_500t': 'Vision3 500T', 'kodak_vision3_50d': 'Vision3 50D'}
PRINT = {'kodak_portra_endura': 'Portra Endura', 'fujifilm_crystal_archive_typeii': 'Crystal Archive II',
         'kodak_2383': 'Vision 2383'}


def category(r):
    return '反转片' if r['positive'] else ('电影卷' if r['use'] == 'cine' else '彩色负片')


def load(pattern):
    rows = []
    for p in sorted(LOCAL.glob(pattern)):
        rows += json.loads(p.read_text())
    return rows


def pct(v):
    return '—' if v is None else f'{100 * v:.1f}%'


def look(codes_lab, neutral_mask):
    L, a, b = codes_lab.T
    C = np.hypot(a, b)
    return {'L50': float(np.median(L)), 'L_p90_p10': float(np.percentile(L, 90) - np.percentile(L, 10)),
            'C50': float(np.median(C)), 'C90': float(np.percentile(C, 90)),
            'neutral_a': float(np.median(a[neutral_mask])), 'neutral_b': float(np.median(b[neutral_mask]))}


def fmt(e):
    return f'{e["median"]:.2f} / {e["p99"]:.2f} / {e["max"]:.2f}'


def main():
    bake = {r['film']: r for r in load('bake_*of*.json')}
    sim = {(r['film'], r['usage']): r for r in load('similarity_*of*.json')}
    rows = sorted(bake.values(), key=lambda r: (ORDER.index(category(r)) if r.get('success') else 9, r['film']))
    small, _ = load_photos()
    x = np.concatenate([small[n].reshape(-1, 3) for n in PHOTOS])[::5]
    xl = lab(x)
    neutral = np.hypot(xl[:, 1], xl[:, 2]) < 4
    out = {'input_look': look(xl, neutral)}

    # looks and pairwise distinctness (median dE00 on the validation photos) for the srgbmid and srgb cubes
    labs, looks = {}, {}
    for variant in ('srgb', 'srgbmid'):
        labs[variant] = {r['film']: lab(apply_lut(read_cube_table(CUBES / f'spektrafilm_{r["film"]}_{variant}.cube'), x))
                         for r in rows if r.get('success')}
        looks[variant] = {f: look(v, neutral) for f, v in labs[variant].items()}
    ids = list(labs['srgbmid'])
    near, D = {}, {}
    for variant in ('srgb', 'srgbmid'):
        M = np.zeros((len(ids), len(ids)))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                M[i, j] = M[j, i] = float(np.median(de00(labs[variant][ids[i]], labs[variant][ids[j]])))
        D[variant] = M.round(3).tolist()
        near[variant] = {ids[i]: sorted((M[i, j], ids[j]) for j in range(len(ids)) if j != i)[:2] for i in range(len(ids))}

    # overlap with fotufilm (srgb cubes of both, same photos)
    over = {}
    for f, g in OVERLAP.items():
        if f not in labs['srgb']:
            continue
        ft = lab(apply_lut(read_cube_table(FOTU / f'cubes/fotufilm_{g}_srgb.cube'), x))
        over[f] = {'fotufilm': g, 'look_fotufilm': look(ft, neutral),
                   'dE_vs_spk_srgb': float(np.median(de00(ft, labs['srgb'][f]))),
                   'dE_vs_spk_srgbmid': float(np.median(de00(ft, labs['srgbmid'][f])))}
    fsim = {}
    for p in sorted(FOTU.glob('similarity_*of*.json')):
        for r in json.loads(p.read_text()):
            if r.get('success'):
                fsim[(r['stock'], r['usage'])] = r

    L = ['## 胶片清单与一致性（LUT↔spektrafilm 直接渲染，ΔE00 中位 / p99 / 最大）', '',
         '| 类别 | 胶片 | 相纸 | 打乱检验 | 节点最大差 | sRGB 默认 | sRGB 中灰不提亮 | V-Log 33³ | V-Log 65³ |',
         '|---|---|---|---|---:|---:|---:|---:|---:|']
    summary = []
    for r in rows:
        if not r.get('success'):
            L.append(f'| ? | {r["film"]} | 失败：{r.get("error", "")[:80]} | | | | | | |')
            continue
        V = r['variants']
        sh = '通过' if all(v['shuffle_max_u16'] == 0 for v in V.values()) else '差 ' + str(
            max(v['shuffle_max_u16'] for v in V.values()))
        node = max(v['nodes_runtime_vs_cube_max_abs'] for v in V.values())
        pr = '直接扫描' if r['positive'] else PRINT.get(r['target_print'], r['target_print'])
        L.append(f'| {category(r)} | {SHORT[r["film"]]} | {pr} | {sh} | {node * 65535:.1f}/65535 | '
                 + ' | '.join(fmt(V[v]['lut_vs_runtime']['tetra']) for v in ('srgb', 'srgbmid', 'vlog', 'vlog65')) + ' |')
        s = {'film': r['film'], 'name': SHORT[r['film']], 'category': category(r), 'print': pr,
             'lut_vs_runtime': {v: V[v]['lut_vs_runtime'] for v in V},
             'pass': {v: V[v]['lut_vs_runtime']['tetra']['median'] < .5 and V[v]['lut_vs_runtime']['tetra']['p99'] < 2
                      for v in V},
             'full_frame': {v: V[v].get('full_frame') for v in ('srgb', 'srgbmid')},
             'look': {v: looks[v][r['film']] for v in looks},
             'nearest': {v: [(round(d, 2), SHORT[n]) for d, n in near[v][r['film']]] for v in near}}
        for usage in ('jpeg', 'jpegmid', 'scene'):
            x_ = sim.get((r['film'], usage))
            if x_ and x_.get('success'):
                t, l = x_['camera_table_safe'], x_['lut_on_04']['rgb17']
                s[usage] = {'table_syn': t['synthetic_holdout']['similarity'],
                            'table_scene': t['scene_holdout']['similarity'],
                            'lut17_syn': l['synthetic_holdout']['similarity'],
                            'lut17_scene': l['scene_holdout']['similarity'],
                            'lut33_syn': x_['lut_on_04']['rgb33']['synthetic_holdout']['similarity'],
                            'base_de': t['synthetic_holdout']['baseline_de00_median'],
                            'table_de': t['synthetic_holdout']['de00']['median'],
                            'lut17_de': l['synthetic_holdout']['de00']['median']}
        summary.append(s)

    L += ['', '## 整幅：作者默认的自动曝光、默认空间效果 与 LUT 的差别（ΔE00 中位 / p99；括号内为 8×8 低通后）', '',
          '| 胶片 | 照片 | L* 中位：输入 / sRGB 默认 LUT / 中灰不提亮 LUT / 自动曝光 | 自动曝光↔默认 LUT | 自动曝光↔中灰不提亮 LUT | 默认空间效果↔默认 LUT（低通） |',
          '|---|---|---|---:|---:|---:|']
    for s in summary:
        ff, fm = s['full_frame']['srgb'], s['full_frame']['srgbmid']
        for n in ff:
            a, b, c = ff[n], fm[n], ff[n]['spatial']
            L.append(f'| {s["name"]} | {n} | — / {a["lut_L_median"]} / {b["lut_L_median"]} / {a["autoexp_L_median"]} | '
                     f'{a["autoexp"]["raw"]["median"]:.1f} / {a["autoexp"]["raw"]["p99"]:.1f} | '
                     f'{b["autoexp"]["raw"]["median"]:.1f} / {b["autoexp"]["raw"]["p99"]:.1f} | '
                     f'{c["raw"]["median"]:.2f} / {c["raw"]["p99"]:.2f}（{c["lowpass8"]["median"]:.2f} / {c["lowpass8"]["p99"]:.2f}） |')

    L += ['', '## 相似度（全部是电脑预测）', '',
          '| 类别 | 胶片 | 用法 | 相机表（合成 / 实景） | 机内 17³（合成 / 实景） | 机内 33³ | 04→目标 | 相机表余差 | 17³ 余差 |',
          '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        for usage, label in (('jpeg', '接 04 JPEG · 默认'), ('jpegmid', '接 04 JPEG · 中灰不提亮'), ('scene', 'RAW 场景光 · V-Log 65³')):
            v = s.get(usage)
            if not v:
                continue
            first = usage == 'jpeg'
            L.append(f'| {s["category"] if first else ""} | {s["name"] if first else ""} | {label} | '
                     f'{pct(v["table_syn"])} / {pct(v["table_scene"])} | {pct(v["lut17_syn"])} / {pct(v["lut17_scene"])} | '
                     f'{pct(v["lut33_syn"])} | {v["base_de"]:.2f} | **{v["table_de"]:.2f}** | {v["lut17_de"]:.2f} |')

    L += ['', '## 观感描述（6 张验证照片，中灰不提亮版；输入本身 L50 %.1f、C50 %.1f）' % (out['input_look']['L50'], out['input_look']['C50']), '',
          '| 胶片 | L* 中位 | L* 跨度 p90−p10 | 彩度中位 / p90 | 中性色 a* / b* | 最近的两支（中位 ΔE00） |', '|---|---:|---:|---:|---:|---|']
    for s in summary:
        k = s['look']['srgbmid']
        nn = '、'.join(f'{n} {d}' for d, n in s['nearest']['srgbmid'])
        L.append(f'| {s["name"]} | {k["L50"]:.1f} | {k["L_p90_p10"]:.1f} | {k["C50"]:.1f} / {k["C90"]:.1f} | '
                 f'{k["neutral_a"]:+.1f} / {k["neutral_b"]:+.1f} | {nn} |')

    L += ['', '## 与 fotufilm 重叠的片种（两家的 sRGB LUT，同 6 张照片）', '',
          '| spektrafilm | fotufilm | 两家差（vs 默认 / vs 中灰不提亮） | L* 中位 spk 默认 / spk 中灰 / fotu | 彩度中位 spk 中灰 / fotu | 中性 b* spk 中灰 / fotu | 相机表余差 spk 默认 / spk 中灰 / fotu | 17³ spk 中灰 / fotu |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for f, o in over.items():
        s = next(s for s in summary if s['film'] == f)
        fj = fsim.get((o['fotufilm'], 'jpeg'))
        fde = fj['camera_table_safe']['synthetic_holdout']['de00']['median'] if fj else None
        f17 = fj['lut_on_04']['rgb17']['synthetic_holdout']['similarity'] if fj else None
        a, b, c = s['look']['srgb'], s['look']['srgbmid'], o['look_fotufilm']
        L.append(f'| {s["name"]} | `{o["fotufilm"]}` | {o["dE_vs_spk_srgb"]:.1f} / {o["dE_vs_spk_srgbmid"]:.1f} | '
                 f'{a["L50"]:.0f} / {b["L50"]:.0f} / {c["L50"]:.0f} | {b["C50"]:.1f} / {c["C50"]:.1f} | '
                 f'{b["neutral_b"]:+.1f} / {c["neutral_b"]:+.1f} | '
                 f'{s.get("jpeg", {}).get("table_de", float("nan")):.2f} / {s.get("jpegmid", {}).get("table_de", float("nan")):.2f} / '
                 f'{fde if fde is None else round(fde, 2)} | {pct(s.get("jpegmid", {}).get("lut17_syn"))} / {pct(f17)} |')
        o['fotufilm_table_de'] = fde
        o['fotufilm_lut17'] = f17

    np_path = LOCAL / 'nicephoto.json'
    if np_path.exists():
        npj = json.loads(np_path.read_text())
        L += ['', '## 与第三方 NicePhoto 重烘版的差别（6 张验证照片，ΔE00 中位 / p99）', '',
              '| 代号 | 胶片 | vs 我们默认 | vs 我们中灰不提亮 | vs 我们默认 + 拟合前置增益 | 拟合增益 | 中灰 0.466 输出：NicePhoto / 默认 / 中灰不提亮 | L* 中位：输入 / NicePhoto / 默认 / 中灰不提亮 |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
        for code, r in npj.items():
            ph, m, Lm = r['photos'], r['midgray_0466_out'], r['L_median_photos']
            L.append(f'| {code} | {SHORT[r["film"]]} | {ph["srgb"]["median"]:.2f} / {ph["srgb"]["p99"]:.2f} | '
                     f'{ph["srgbmid"]["median"]:.2f} / {ph["srgbmid"]["p99"]:.2f} | {ph["srgb+g"]["median"]:.2f} / {ph["srgb+g"]["p99"]:.2f} | '
                     f'{r["fitted_pregain"]:.3f}（{r["fitted_pregain_ev"]:+.2f} EV） | {m["nicephoto"]:.3f} / {m["srgb"]:.3f} / {m["srgbmid"]:.3f} | '
                     f'{Lm["input"]:.0f} / {Lm["nicephoto"]:.0f} / {Lm["srgb"]:.0f} / {Lm["srgbmid"]:.0f} |')
    path = LOCAL / 'tables.md'
    check_paths(path)
    path.write_text('\n'.join(L) + '\n')
    dump(LOCAL / 'summary.json', {'films': summary, 'overlap': over, 'ids': ids, 'pairwise_median_de00': D,
                                  'input_look': out['input_look']})
    for v in ('srgb', 'srgbmid', 'vlog', 'vlog65'):
        print(v, f'{sum(s["pass"][v] for s in summary)}/{len(summary)} pass median<0.5 & p99<2')


if __name__ == '__main__':
    main()
