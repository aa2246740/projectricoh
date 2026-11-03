#!/usr/bin/python3
"""Check design arithmetic, fixed read addresses, screen contracts and hashes.

This checks documents/specification only; it is not a firmware acceptance test.
"""
from pathlib import Path
import hashlib
import json
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    d = json.loads((HERE / 'design_spec.json').read_text())
    v = json.loads((ROOT / 'research/body_v4_storage/validation/diagnostic_spec.json').read_text())
    fields = d['fields']
    assert len(fields) == len({f['name'] for f in fields}) == 82
    actual = {f['name']: [f['address'], f['read_bytes']] for f in fields if f['source'] == 'V10'}
    assert actual == v['fields'] and len(actual) == 42
    layout = json.loads((ROOT / 'firmware/resident_v36/local/resident/target-layout.json').read_text())
    root_fields = layout['RvRoot']['fields']
    root_names = {'root_state_word': 'version', 'root_diag_early_reserved': 'diag_early'}
    for f in fields:
        if f['name'].startswith('root_'):
            n = root_names.get(f['name'], f['name'][5:])
            if n.endswith('_epoch'):
                n = 'epoch'
                i = ['boot', 'heap', 'link', 'unit', 'sd', 'irom', 'view', 's', 'mode', 'seg', 'power', 'io'].index(f['name'][5:-6])
                expected = 0x20054700 + root_fields[n]['offset'] + 4 * i
            else:
                expected = 0x20054700 + root_fields[n]['offset']
            assert int(f['address'], 16) == expected, f
    body = (ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3').read_bytes()
    assert hashlib.sha256(body).hexdigest() == d['body_sha256']
    spans = []
    for i in range(16):
        src, va, size, bss, bn = struct.unpack_from('>5I', body, 32 + 20 * i)
        spans.extend([(va, va + size), (bss, bss + bn)])
    for f in fields:
        a, w = int(f['address'], 16), f['read_bytes']
        assert w in [1, 2, 4] and a % w == 0 and a < 0x80000000
        assert any(lo <= a and a + w <= hi for lo, hi in spans), f
        assert f['record_offset'] == 48 + 4 * fields.index(f)
    assert 48 + 4 * len(fields) == d['record']['crc_offset'] == 376
    assert d['record']['seq_end_offset'] + 4 == d['record']['bytes'] == 384
    assert d['record']['valid_bits'] >= len(fields)
    m = d['memory']
    assert m['hook_records'] * m['record_bytes'] + m['snapshot_count'] * m['snapshot_bytes'] + m['metadata_bytes'] == m['lease_bytes'] == 65536
    ss = d['snapshots']
    assert sum(x['bytes'] for x in ss['regions']) == ss['raw_bytes'] == 2472
    assert ss['header_bytes'] + ss['raw_bytes'] == 2600
    assert ss['record_offset'] == 2688 >= ss['header_bytes'] + ss['raw_bytes']
    assert ss['record_offset'] + ss['pinned_record_bytes'] == ss['frame_bytes'] == 3072
    for x in ss['regions']:
        a, w = int(x['address'], 16), x['bytes']
        assert any(lo <= a and a + w <= hi for lo, hi in spans), x
    p = d['conditional_periodic']
    assert (p['slow_records'] + p['fast_records']) * 384 == 49152
    assert 600 * 20 * 384 == p['full_10min_20hz_bytes'] == 4608000
    assert p['slow_records'] * p['slow_period_assumed_s'] == 640
    assert p['fast_records'] * p['fast_period_assumed_s'] == 3.2
    e = d['conditional_export']
    assert len(e['paths']) == len(set(e['paths'])) == 2
    assert e['handles'] == 1 and not e['enabled']
    assert all(e['bank_bytes'] % q == 0 for q in e['q_allowed'])
    assert e['bank_bytes'] >= 2 * max(e['q_allowed'])
    assert e['bank_bytes'] >= 4096 + 65536 + 512
    values = {f['name']: 2 ** (8 * f['read_bytes']) - 1 for f in fields}
    values.update(seq=0xffffffff, quality='INVALID', phase=255, records=0xffffffff,
                  gap_ticks=0xffffffff, wraps=0xffffffff, bad=65535, snapshot_crc=0xffffffff)
    screens = {}
    for name, rows in d['views'].items():
        assert len(rows) == 8, (name, len(rows))
        rendered = [s.format(**values) for s in rows]
        assert max(map(len, rendered)) <= 31, (name, rendered)
        assert all(s.isascii() for s in rendered)
        screens[name] = dict(rows=8, max_columns=max(map(len, rendered)), example=rendered)
    assert sum(d['user_script_seconds']) == 570 <= 600
    assert d['default_file_calls'] == d['default_RPC8_calls'] == 0 and not d['default_new_task']
    # Every design-document relative link must resolve; no network resolution.
    links = []
    for pth in HERE.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', pth.read_text()):
            if '://' in target or target.startswith('#'):
                continue
            path = target.split('#')[0]
            assert (pth.parent / path).exists(), (pth.name, target)
            links.append(target)
    frozen_paths = set()
    for filename in ['inputs-before.json', 'inputs-late.json']:
        frozen = json.loads((HERE / filename).read_text())
        frozen_paths.update(frozen)
        for path, info in frozen.items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == info['sha256'], path
    checksum_file = HERE / 'SHA256SUMS'
    hashes = 0
    if checksum_file.exists():
        for line in checksum_file.read_text().splitlines():
            digest, name = line.split('  ', 1)
            path = ROOT / name
            path.resolve().relative_to(HERE)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
            hashes += 1
        members = {line.split('  ', 1)[1] for line in checksum_file.read_text().splitlines()}
        expected = {str(pth.relative_to(ROOT)) for pth in HERE.rglob('*') if pth.is_file() and pth != checksum_file}
        assert members == expected, (members ^ expected)
    result = dict(status='PASS_DESIGN_CHECKS', v10_fields=42, total_fields=82,
                  record_bytes=384, lease_bytes=65536, snapshot_header_and_raw_bytes=2600,
                  pinned_record_offset=2688, snapshot_frame_bytes=3072,
                  default_views=screens, script_seconds=570, valid_relative_links=len(links),
                  frozen_input_files=len(frozen_paths), firmware_implementation='NOT_RUN',
                  target_scheduler='NOT_RUN', LCD='NOT_RUN', camera='NOT_RUN', file_export='DISABLED')
    # Write once before sealing; normal verification is read-only and also checks
    # the sealed result file, avoiding a circular digest dependency.
    if '--write-result' in sys.argv:
        assert not checksum_file.exists(), 'Do not rewrite sealed evidence'
        (HERE / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict({k: val for k, val in result.items() if k != 'default_views'}, checksum_entries_checked=hashes), ensure_ascii=False))


if __name__ == '__main__':
    main()
