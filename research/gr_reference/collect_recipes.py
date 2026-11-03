#!/usr/bin/env python3
"""Collect public numeric recipe facts only; never fetch firmware or apps."""
import argparse
import csv
import hashlib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
COLLECTIONS = {
    'GR III/IIIx': ['the-nature-collection', 'the-road-trip-collection',
                   'the-street-collection', 'california-negative-collection',
                   'film-collection', 'the-analog-collection',
                   'the-adventure-collection', 'the-bw-collection'],
    'GR/GR II': ['the-color-city-collection', 'the-color-landscape-collection',
                'the-lomo-collection', 'the-monochrome-collection'],
}
FIELDS = {'Effect': 'preset', 'Image Settings': 'image_settings', 'Saturation': 'saturation', 'Vividness': 'vividness',
          'Hue': 'hue', 'High/Low Key': 'high_low_key', 'Contrast': 'contrast',
          'Contrast (Highlight)': 'contrast_highlight', 'Contrast (Shadow)': 'contrast_shadow',
          'Sharpness': 'sharpness', 'Shading': 'shading', 'Clarity': 'clarity',
          'Toning': 'toning', 'Toning Effect': 'toning_effect', 'Color Tone': 'color_tone', 'Filter Effect': 'filter_effect',
          'HDR Tone': 'hdr_tone',
          'Grain Effect': 'grain_effect', 'Vignetting': 'vignetting',
          'Highlight Correction': 'highlight_correction', 'Shadow Correction': 'shadow_correction',
          'Peripheral Illumination Correction': 'peripheral_illumination_correction',
          'Dynamic Range Compensation': 'dynamic_range_compensation',
          'High-ISO Noise Reduction': 'high_iso_noise_reduction', 'Noise Reduction': 'noise_reduction',
          'White Balance': 'white_balance', 'WB Compensation': 'wb_compensation',
          'ISO': 'iso', 'Exposure Compensation': 'exposure_compensation'}
PATTERN = re.compile(r'(' + '|'.join(re.escape(k) for k in sorted(FIELDS, key=len, reverse=True)) + r'):\s*')
EXTRA_SLUG = 'luke-candy-color-400'
EXTRA_URL = 'https://www.lukeptaylor.com/blog/candy-color-400-ricoh-gr-iii-film-recipe'

def fetch_extra():
    raw = urllib.request.urlopen(EXTRA_URL, timeout=40).read()
    soup = BeautifulSoup(raw, 'html.parser')
    lines = [p.get_text(' ', strip=True) for p in soup.select('p')]
    lookup = {'EFFECT': 'Effect', 'SATURATION': 'Saturation', 'HUE': 'Hue',
              'HIGH/LOW KEY': 'High/Low Key', 'CONTRAST': 'Contrast',
              'CONTRAST (HIGHLIGHT)': 'Contrast (Highlight)',
              'CONTRAST (SHADOW)': 'Contrast (Shadow)', 'SHARPNESS': 'Sharpness',
              'TONING': 'Toning', 'SHADING': 'Shading', 'CLARITY': 'Clarity',
              'HIGHLIGHT CORRECTION': 'Highlight Correction',
              'SHADOW CORRECTION': 'Shadow Correction',
              'PERIPHERAL ILLUM. CORR.': 'Peripheral Illumination Correction',
              'NOISE REDUCTION': 'High-ISO Noise Reduction', 'WHITE BALANCE': 'White Balance',
              'ISO': 'ISO', 'EXPOSURE COMPENSATION': 'Exposure Compensation'}
    parts = []
    shifts = []
    source_lines = []
    for line in lines:
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key in lookup:
            parts.append(lookup[key] + ': ' + value.strip())
            source_lines.append(line)
        elif key in ('WB COMP. A/B', 'WB COMP. G/M'):
            shifts.append(value.strip())
            source_lines.append(line)
    assert len(parts) == 18, parts
    parts.append('WB Compensation: ' + ' '.join(shifts))
    return {'url': EXTRA_URL, 'resolved_url': EXTRA_URL,
            'retrieved_utc': datetime.now(timezone.utc).isoformat(),
            'html_sha256': hashlib.sha256(raw).hexdigest(), 'model': 'GR III/IIIx',
            'original_parameter_lines': source_lines,
            'recipes': [{'name': 'Candy Color 400', 'raw_parameters': ' '.join(parts)}]}

def fetch_one(item):
    model, slug = item
    url = 'https://ricohrecipes.com/' + slug + '/'
    request = urllib.request.Request(url, headers={'User-Agent': 'GXR-reference-research/1.0'})
    with urllib.request.urlopen(request, timeout=40) as response:
        raw = response.read()
        resolved = response.url
    soup = BeautifulSoup(raw, 'html.parser')
    content = soup.select_one('.entry-content')
    if content is None:
        raise ValueError('Missing entry-content: ' + url)
    name = None
    rows = []
    for p in content.find_all('p'):
        value = p.get_text(' ', strip=True).replace('\xa0', ' ')
        if re.search(r'Recipe\s*:', value) and not value.startswith('Effect:'):
            name = re.sub(r'\s+Recipe\s*:.*$', '', value).strip()
        if not value.startswith('Effect:'):
            continue
        if not name:
            raise ValueError('Recipe has no title: ' + url)
        matches = list(PATTERN.finditer(value))
        row = {'name': name, 'source_url': url, 'model': model, 'collection': slug}
        for i, match in enumerate(matches):
            end = matches[i+1].start() if i+1 < len(matches) else len(value)
            row[FIELDS[match.group(1)]] = value[match.end():end].strip()
        if 'white_balance' not in row:
            raise ValueError('Incomplete recipe: ' + name)
        row['raw_parameters'] = value
        row['notes'] = 'Public parameter block; blank means not stated or not applicable, never assumed zero.'
        rows.append(row)
    if not rows:
        raise ValueError('No recipes: ' + url)
    evidence = {'url': url, 'resolved_url': resolved, 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                'html_sha256': hashlib.sha256(raw).hexdigest(), 'model': model,
                'recipes': [{k: v for k, v in r.items() if k in ('name', 'raw_parameters')} for r in rows]}
    return slug, rows, evidence

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true', help='Rebuild CSV from saved parameter facts')
    args = parser.parse_args()
    source_dir = ROOT / 'sources'
    source_dir.mkdir(parents=True, exist_ok=True)
    items = [(m, s) for m, slugs in COLLECTIONS.items() for s in slugs]
    rows = []
    if not args.offline:
        extra = fetch_extra()
        (source_dir / (EXTRA_SLUG + '.json')).write_text(json.dumps(extra, ensure_ascii=False, indent=2) + '\n')
    if args.offline:
        for model, slug in items:
            saved = json.loads((source_dir / (slug + '.json')).read_text())
            for recipe in saved['recipes']:
                value = recipe['raw_parameters']
                matches = list(PATTERN.finditer(value))
                row = {'name': recipe['name'], 'source_url': saved['url'], 'model': model, 'collection': slug}
                for i, match in enumerate(matches):
                    end = matches[i+1].start() if i+1 < len(matches) else len(value)
                    row[FIELDS[match.group(1)]] = value[match.end():end].strip()
                row['raw_parameters'] = value
                row['notes'] = 'Public parameter block; blank means not stated or not applicable, never assumed zero.'
                rows.append(row)
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for slug, collected, evidence in pool.map(fetch_one, items):
                (source_dir / (slug + '.json')).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
                rows.extend(collected)
                print(slug, len(collected))
    extra = json.loads((source_dir / (EXTRA_SLUG + '.json')).read_text())
    for recipe in extra['recipes']:
        value = recipe['raw_parameters']
        matches = list(PATTERN.finditer(value))
        row = {'name': recipe['name'], 'source_url': extra['url'], 'model': extra['model'], 'collection': EXTRA_SLUG}
        for i, match in enumerate(matches):
            end = matches[i+1].start() if i+1 < len(matches) else len(value)
            row[FIELDS[match.group(1)]] = value[match.end():end].strip()
        row['raw_parameters'] = value
        row['notes'] = 'Labels normalized from uppercase webpage; exact source lines in sources/luke-candy-color-400.json. N/A preserved.'
        rows.append(row)
    for row in rows:
        ab = re.search(r'([AB]):\s*(\d+)', row.get('wb_compensation', ''))
        gm = re.search(r'([GM]):\s*(\d+)', row.get('wb_compensation', ''))
        kelvin = re.search(r'(\d+)K', row.get('white_balance', ''))
        row['wb_ab_signed'] = str(int(ab[2]) * (1 if ab[1] == 'A' else -1)) if ab else ''
        row['wb_gm_signed'] = str(int(gm[2]) * (1 if gm[1] == 'G' else -1)) if gm else ''
        row['wb_kelvin'] = kelvin[1] if kelvin else ''
    keys = ['name', 'source_url', 'model', 'collection'] + list(FIELDS.values()) + ['wb_ab_signed', 'wb_gm_signed', 'wb_kelvin', 'notes', 'raw_parameters']
    with (ROOT / 'recipes.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    assert len(rows) >= 50, len(rows)
    assert len({(r['model'], r['name']) for r in rows}) == len(rows)
    print('Total public recipes:', len(rows))

if __name__ == '__main__':
    main()
