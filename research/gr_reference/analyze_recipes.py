#!/usr/bin/env python3
"""Reproduce sample statistics and explicitly conditional capability coverage."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALIASES = {'Std': 'Standard', 'BW Monotone': 'Monotone', 'Black & White': 'Monotone'}
NATIVE_BASES = {'Standard', 'Vivid', 'Monotone', 'B&W (TE)'}
META = {'name', 'source_url', 'model', 'collection', 'notes', 'raw_parameters', 'image_settings'}
NEUTRAL = {'', '0', 'Off', 'N/A'}

def normalized(value):
    value = value.strip()
    if re.fullmatch(r'[+-]?\s*\d+', value):
        return str(int(value.replace(' ', '')))
    return value

def preset(row):
    value = row['image_settings'] if row['preset'] == 'Off' else row['preset']
    return ALIASES.get(value, value)

def requirements(row):
    # Each stated active control is one request. Zero/off settings do not inflate coverage.
    result = {'base_native' if preset(row) in NATIVE_BASES else 'base_fit',
              'wb_mode', 'wb_ab', 'wb_gm', 'noise_reduction'}
    if row['saturation'] or row['vividness']:
        if normalized(row['saturation'] or row['vividness']) not in NEUTRAL:
            result.add('saturation')
    for key in ['hue', 'contrast', 'sharpness', 'high_low_key', 'contrast_highlight',
                'contrast_shadow', 'clarity', 'toning', 'color_tone', 'filter_effect',
                'grain_effect', 'highlight_correction', 'shadow_correction',
                'peripheral_illumination_correction', 'dynamic_range_compensation', 'toning_effect']:
        if normalized(row[key]) not in NEUTRAL:
            result.add(key)
    if normalized(row['shading']) not in NEUTRAL or normalized(row['vignetting']) not in NEUTRAL:
        result.add('shading')
    return result

def main():
    rows = list(csv.DictReader((ROOT / 'recipes.csv').open()))
    assert len(rows) >= 50
    assert len({(r['model'], r['name']) for r in rows}) == len(rows)
    for row in rows:
        assert row['source_url'].startswith('https://')
        assert row['wb_ab_signed'] and row['wb_gm_signed']
        for key in ['saturation', 'high_low_key', 'contrast_highlight', 'contrast_shadow', 'shading', 'clarity']:
            if row['model'] == 'GR III/IIIx' and row[key]:
                assert -4 <= int(normalized(row[key])) <= 4, (row['name'], key)
    stats = {}
    md = ['# 配方样本统计', '', '由 `analyze_recipes.py` 从 `recipes.csv` 生成。数值是样本频率，不是全球使用率。', '']
    for model in ['ALL', 'GR/GR II', 'GR III/IIIx']:
        subset = rows if model == 'ALL' else [r for r in rows if r['model'] == model]
        frequency = Counter(preset(r) for r in subset)
        if model in ('ALL', 'GR III/IIIx'):
            for value in ['Standard', 'Vivid', 'Positive Film', 'Negative Film', 'Monotone',
                          'Soft Monotone', 'Hard Monotone', 'Hi-Contrast B&W', 'Bleach Bypass',
                          'Retro', 'HDR Tone', 'Cross Process']:
                frequency.setdefault(value, 0)
        data = {'n': len(subset), 'presets': dict(frequency.most_common()), 'parameters': {}}
        md += ['## ' + model, '', '| 底片预设 | 条数 | 占比 |', '|---|---:|---:|']
        md += [f'| {p} | {n} | {n/len(subset):.1%} |' for p, n in frequency.most_common()]
        md += ['', '| 参数 | 写明条数 / 样本数 | 非零或非 Off 条数 | 观察范围 | 常用值（次数） |', '|---|---:|---:|---|---|']
        for key in rows[0]:
            if key in META or key == 'preset':
                continue
            values = [normalized(r[key]) for r in subset if r[key]]
            counts = Counter(values)
            ints = [int(v) for v in values if re.fullmatch(r'[+-]?\d+', v)]
            active = sum(v not in NEUTRAL for v in values)
            observed = ('无样本值' if not values else f'{min(ints)} 至 {max(ints)}'
                        if len(ints) == len(values) else '分类值见频次 JSON')
            mode = ', '.join(f'{v} ({n})' for v, n in counts.most_common(5))
            data['parameters'][key] = {'stated': len(values), 'active': active, 'frequency': dict(counts),
                                        'min': min(ints) if ints else None, 'max': max(ints) if ints else None}
            md.append(f'| {key} | {len(values)}/{len(subset)} | {active} | {observed} | {mode} |')
        stats[model] = data
        md.append('')
    v1 = {'base_native', 'wb_mode', 'wb_ab', 'wb_gm', 'saturation', 'hue', 'contrast', 'sharpness',
          'toning_effect', 'noise_reduction'}
    curve = {'high_low_key', 'contrast_highlight', 'contrast_shadow', 'shading'}
    color = {'base_fit', 'toning', 'color_tone', 'filter_effect'}
    dynamic = {'highlight_correction', 'shadow_correction', 'peripheral_illumination_correction',
               'dynamic_range_compensation'}
    profiles = {'v1': v1, 'v2_curve_shading': v1 | curve,
                'v2_color': v1 | curve | color | dynamic,
                'v2': v1 | curve | color | dynamic | {'clarity'},
                'v2_texture': v1 | curve | color | dynamic | {'clarity', 'grain_effect'}}
    all_requirements = [(r, requirements(r)) for r in rows]
    coverage = {'method': 'Optimistic structural planning proxy; existing axes may only approximate values. '
                          'v2_color assumes measured base-profile fitting, WB calibration and dynamic-range '
                          'approximations succeed. It is not measured JPEG equivalence.', 'profiles': {},
                'demand': dict(Counter(k for r, req in all_requirements for k in sorted(req)).most_common())}
    csv_rows = []
    for name, supported in profiles.items():
        demand = sum(len(req) for r, req in all_requirements)
        covered = sum(len(req & supported) for r, req in all_requirements)
        complete = [r['name'] for r, req in all_requirements if req <= supported]
        coverage['profiles'][name] = {'supported': sorted(supported), 'request_covered': covered,
                                      'request_total': demand, 'request_fraction': covered/demand,
                                      'whole_recipe_candidates': len(complete), 'whole_recipe_fraction': len(complete)/len(rows),
                                      'whole_recipe_names': complete}
    for r, req in all_requirements:
        item = {'name': r['name'], 'model': r['model'], 'source_url': r['source_url'], 'preset': preset(r)}
        for name, supported in profiles.items():
            item[name + '_missing'] = ';'.join(sorted(req - supported))
        csv_rows.append(item)
    with (ROOT / 'coverage.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0])); w.writeheader(); w.writerows(csv_rows)
    (ROOT / 'statistics.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2)+'\n')
    (ROOT / 'STATISTICS.md').write_text('\n'.join(md)+'\n')
    (ROOT / 'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2)+'\n')
    for name, v in coverage['profiles'].items():
        print(name, f"{v['request_covered']}/{v['request_total']}={v['request_fraction']:.1%}",
              f"whole candidates {v['whole_recipe_candidates']}/{len(rows)}={v['whole_recipe_fraction']:.1%}")
    print('Demand:', coverage['demand'])

if __name__ == '__main__':
    main()
