#!/usr/bin/env python3
"""Join camera-table estimates and in-body LUT estimates into report tables (local/tables.md, local/summary.json)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import csv
import json
from guard import HERE, ROOT, DOWNLOADS, mount_guard, install_write_fence, dump, sha

LEICA_RUN = ROOT/'research/lut_convert/local/leica-complete'
HUZI_CSV = ROOT/'research/huzi_luts/local/SUMMARY.csv'
FUJI_NAMES = {'PROVIA': 'Provia', 'Velvia': 'Velvia', 'ASTIA': 'Astia', 'CLASSIC-CHROME': 'Classic Chrome',
              'REALA-ACE': 'Reala Ace', 'PRO-Neg.Std': 'Pro Neg. Std', 'CLASSIC-Neg.': 'Classic Neg.',
              'ETERNA': 'Eterna', 'ETERNA-BB': 'Eterna 漂白', 'ACROS': 'Acros',
              'XT5-ETERNA': 'Eterna（X-T5 等四机包）', 'XT5-ETERNA-BB': 'Eterna 漂白（X-T5 等四机包）'}


def pct(v):
    return '—' if v is None else f'{100*v:.1f}%'


def table_scores(family, label, cube=None):
    """Camera-table safe/T1 synthetic holdout + scene holdout from the converter runs."""
    if family == 'fuji':
        n = {'XT5-ETERNA': '11-xt5-ETERNA', 'XT5-ETERNA-BB': '12-xt5-ETERNA-BB'}.get(label)
        if label == 'CLASSIC-Neg.':
            f = HERE/'local/fuji-classicneg-safe/results.json'
        else:
            hits = [p for p in (HERE/'local/fuji-batch').glob('*/results.json')
                    if (n and p.parent.name == n) or (not n and p.parent.name.endswith('-gfx-'+label))]
            f = hits[0] if hits else None
    elif family == 'leica':
        digest = sha(DOWNLOADS/cube)
        hits = [p for p in LEICA_RUN.glob('*/results.json') if json.loads(p.read_text())['lut']['sha256'] == digest]
        f = hits[0] if hits else None
    else:
        return None
    if not f or not f.exists():
        return None
    r = json.loads(f.read_text())
    s = r['scores']
    out = {'safe': s['safe']['synthetic_holdout']['similarity'], 'safe_scene': s['safe']['scene_holdout']['similarity'],
           'safe_de': s['safe']['synthetic_holdout']['de00']['median'],
           'base_de': s['safe']['synthetic_holdout']['baseline_de00']['median'],
           't1': s.get('t1', {}).get('synthetic_holdout', {}).get('similarity'),
           'sector_pass': s['safe'].get('sector_safety', {}).get('passes') if isinstance(s['safe'].get('sector_safety'), dict) else None,
           'source': str(f.relative_to(ROOT))}
    return out


def huzi_rows():
    rows = {}
    with HUZI_CSV.open() as f:
        for r in csv.DictReader(f):
            if r['concentration'] == '100':
                rows.setdefault(r['look'], {})[(r['basis'], r['variant'])] = float(r['similarity'])
    return rows


def main():
    mount_guard(); install_write_fence()
    ceil = [r for r in json.loads((HERE/'local/ceiling/ceiling.json').read_text()) if r.get('success')]
    huzi = huzi_rows()
    lines, summary = [], []
    lines += ['| 外观 | 相机表 safe（合成/实景） | T1 | 机内 17³（合成/实景） | 机内 33³ | YCbCr 17³ | 相机表＋残差 17³ | 04→目标 ΔE00 | 相机表余差 ΔE00 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for fam, title in (('fuji', '富士（GFX ETERNA 55 包，F-Log2 33 格）'), ('leica', '徕卡官方（L-Log）'),
                       ('huzi', '胡子（输入按 GXR 04 代理“松下标准”，100% 浓度）')):
        lines.append(f'| **{title}** | | | | | | | | |')
        for r in [c for c in ceil if c['family'] == fam]:
            lab = r['label']
            name = FUJI_NAMES.get(lab, lab)
            t = table_scores(fam, lab, r['cube'])
            c4, cr = r['lut_on_04'], r['residual_on_recipe']
            bw = r['camera_table_safe']['bw_native03']
            if fam == 'huzi':
                h = huzi.get(lab, {})
                tab = f"{pct(h.get(('gxr04', 'safe')))}（松下基底 {pct(h.get(('panasonic_s1rii', 'safe')))}）"
                t1 = pct(h.get(('gxr04', 't1')))
                base_de, tab_de = '—', '—'
            else:
                tab = f"{pct(t['safe'])} / {pct(t['safe_scene'])}" if t else pct(r['camera_table_safe']['synthetic_holdout']['similarity'])
                t1 = pct(t['t1']) if t else '—'
                base_de = f"{t['base_de']:.2f}" if t else '—'
                tab_de = f"{t['safe_de']:.2f}" if t else '—'
            resid = '不适用（黑白）' if bw else pct(cr['rgb17']['synthetic_holdout']['similarity'])
            lines.append(f"| {name}{'（黑白，走 03）' if bw else ''} | {tab} | {t1} | "
                         f"{pct(c4['rgb17']['synthetic_holdout']['similarity'])} / {pct(c4['rgb17']['scene_holdout']['similarity'])} | "
                         f"{pct(c4['rgb33']['synthetic_holdout']['similarity'])} | {pct(c4['ycc17']['synthetic_holdout']['similarity'])} | "
                         f"{resid} | {base_de} | {tab_de} |")
            summary.append({'family': fam, 'label': lab, 'camera_table': t, 'host_table_refit': r['camera_table_safe'],
                            'in_body_lut_on_04': c4, 'residual_on_recipe': None if bw else cr,
                            'huzi_table': huzi.get(lab) if fam == 'huzi' else None})
    (HERE/'local/tables.md').write_text('\n'.join(lines)+'\n')
    dump(HERE/'local/summary.json', summary)
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
