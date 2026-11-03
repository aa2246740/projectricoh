#!/usr/bin/env python3
"""Read-only inventory of the user's LUT packs (headers, grid, hashes, duplicate groups).

Reads the copies extracted under local/luts/ and the original archives; writes local/inventory.json.
Only names and header comments are kept; no table values leave local/.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hashlib
import re
from collections import defaultdict
from guard import HERE, ROOT, DOWNLOADS, mount_guard, install_write_fence, dump, sha

ARCHIVES = {'fuji': ROOT/'artifacts/downloads/fuji-luts', 'leica': ROOT/'artifacts/downloads/leica-luts/20261023-official',
            'huzi': ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'}
FUJI_NAMES = {'PROVIA': 'Provia/Standard', 'Velvia': 'Velvia/Vivid', 'ASTIA': 'Astia/Soft',
              'CLASSIC-CHROME': 'Classic Chrome', 'REALA-ACE': 'Reala Ace', 'PRO-Neg.Std': 'Pro Neg. Std',
              'CLASSIC-Neg.': 'Classic Neg.', 'ETERNA': 'Eterna/Cinema', 'ETERNA-BB': 'Eterna Bleach Bypass',
              'ACROS': 'Acros', 'WDR': 'WDR (technical, BT.709 OETF)', 'WDR-709': 'WDR (technical, BT.709 OETF)',
              'FLog-709': 'F-Log kept (technical)', 'FLog2-709': 'F-Log2 kept (technical)',
              'FLog2C-709': 'F-Log2C kept (technical)', 'FLog': 'F-Log kept (technical)',
              'FLog2': 'F-Log2 kept (technical)', 'FLog2C': 'F-Log2C kept (technical)'}


def header(path):
    info, size = [], None
    with path.open('rb') as f:
        for raw in f:
            line = raw.decode('utf-8', 'replace').strip()
            if not line:
                continue
            if re.match(r'^[-+0-9.eE]', line):
                break
            m = re.match(r'LUT_3D_SIZE\s+(\d+)', line)
            if m:
                size = int(m.group(1))
            info.append(line[:120])
    return info, size


def fuji_fields(stem):
    m = re.match(r'(?:(XE5|XT5|XH2|X100VI)_)?(FLog2C|FLog2|FLog)_(?:FGamutC?_)?to_(.+?)_(?:BT\.709_)?(\d+)grid', stem)
    if not m:
        return {}
    body, log, look, grid = m.groups()
    return {'body_pack': body or 'GFX ETERNA 55', 'input_log': {'FLog': 'F-Log', 'FLog2': 'F-Log2', 'FLog2C': 'F-Log2C'}[log],
            'input_gamut': 'F-Gamut C' if log == 'FLog2C' else 'F-Gamut', 'look_code': look,
            'look': FUJI_NAMES.get(look, look), 'grid': int(grid)}


def main():
    mount_guard(); install_write_fence()
    rows, groups = [], defaultdict(list)
    for family in ('fuji', 'leica', 'huzi'):
        for cube in sorted((DOWNLOADS/family).rglob('*.cube')):
            if '__MACOSX' in cube.parts:
                continue
            h = sha(cube)
            info, size = header(cube)
            row = {'family': family, 'file': str(cube.relative_to(DOWNLOADS)), 'sha256': h,
                   'bytes': cube.stat().st_size, 'grid': size, 'header': info}
            if family == 'fuji':
                row.update(fuji_fields(cube.stem))
            rows.append(row); groups[h].append(row['file'])
    archives = [{'family': k, 'file': p.name, 'sha256': sha(p), 'bytes': p.stat().st_size}
                for k, d in ARCHIVES.items() for p in sorted(d.iterdir()) if p.is_file() and p.suffix in ('.zip', '.cube')]
    dup = [v for v in groups.values() if len(v) > 1]
    dump(HERE/'local/inventory.json', {'cubes': rows, 'duplicate_groups': dup, 'archives': archives})
    looks = defaultdict(set)
    for r in rows:
        if r['family'] == 'fuji' and r.get('look'):
            looks[(r['body_pack'], r['input_log'])].add(r['look'])
    for k in sorted(looks):
        print(k, sorted(looks[k]))
    print('cubes', len(rows), 'duplicate groups', len(dup), 'max group', max(map(len, dup)) if dup else 0)


if __name__ == '__main__':
    main()
