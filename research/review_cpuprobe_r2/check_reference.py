"""Check reference cells, lengths and numerical conversion against saved rows."""
from pathlib import Path
import importlib.util
import json
import re
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_scope as rs
rs.enable()
SOURCE = rs.ROOT / 'research/cpu_speed_probe'


def main():
    started = time.monotonic()
    pages = json.loads((SOURCE / 'reference/pages.json').read_text())
    full = json.loads((SOURCE / 'local/accept-full-50mm.json').read_text())
    samples = json.loads((SOURCE / 'local/accept-pages-50mm.json').read_text())
    dat = rs.digest(rs.ROOT / 'firmware/package_v38_cpuprobe/SD_ROOT/GXRCE.DAT')
    assert full['dat'] == samples['dat'] == dat
    assert full['status'] == samples['status'] == 'PASS'
    old_source = SOURCE / 'local/old-src/probe-reviewed.c'
    patch_path = SOURCE / 'review-fix-probe.patch'
    current_source = rs.ROOT / 'firmware/engine_cpuprobe_v38/candidate/containers/product/probe.c'
    old_lines = old_source.read_text().splitlines(keepends=True)
    patch_lines = patch_path.read_text().splitlines(keepends=True)
    result_lines, old_at, patch_at = [], 0, 2
    while patch_at < len(patch_lines):
        header = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', patch_lines[patch_at])
        assert header, patch_lines[patch_at]
        stop = int(header[1]) - 1
        result_lines.extend(old_lines[old_at:stop])
        old_at = stop
        patch_at += 1
        while patch_at < len(patch_lines) and not patch_lines[patch_at].startswith('@@'):
            line = patch_lines[patch_at]
            if line[0] in ' -':
                assert old_lines[old_at] == line[1:]
                old_at += 1
            if line[0] in ' +':
                result_lines.append(line[1:])
            patch_at += 1
    result_lines.extend(old_lines[old_at:])
    assert ''.join(result_lines).encode() == current_source.read_bytes()
    results = []
    for page in pages:
        svg = SOURCE / 'reference' / page['file']
        root = ET.fromstring(svg.read_text())
        cells = {}
        for item in root.iter('{http://www.w3.org/2000/svg}text'):
            x, y = item.get('x'), item.get('y')
            if x is not None and y is not None:
                cells[(int(x), int(y))] = item.text or ''
        decoded = [''.join(cells.get((48 + 28 * c, 54 + 28 * row), ' ') for c in range(8)) for row in range(8)]
        assert len(page['rows']) == 8 and all(len(text) <= 8 for text in page['rows'])
        assert decoded == [text.ljust(8) for text in page['rows']], (page['file'], decoded)
        results.append(dict(file=str(svg.relative_to(rs.ROOT)), sha256=rs.digest(svg), rows=page['rows']))
    names = {p['file']: p['rows'] for p in pages}
    for index, test in enumerate(full['tests']):
        assert names['%02d-%s.svg' % (index + 6, test['name'])] == test['rows']
        sm, lm = sorted(test['s'])[1], sorted(test['l'])[1]
        exponent = test['e']
        units = (1 << (exponent + 2)) - (1 << exponent)
        assert units == 3 * (1 << exponent)
        assert 32 <= sm <= 63 and 128 <= lm <= 255, test
        assert test['rows'][0][4:7] == 'E%02d' % exponent
    rs.save(HERE / 'reference-result.json', dict(status='PASS', dat_sha256=dat, pages=results,
        patch_applies_exactly=True, patch_sha256=rs.digest(patch_path),
        old_source_sha256=rs.digest(old_source), current_source_sha256=rs.digest(current_source),
        scope='SVG character cells compared with pages.json and saved final-DAT model rows; formulas checked independently',
        seconds=round(time.monotonic() - started, 3)))
    print('REFERENCE_PASS', len(results))


if __name__ == '__main__':
    main()
