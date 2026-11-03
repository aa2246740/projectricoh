"""Prove that in a g139m DAT the MOUNT recipe table equals the 50mm table except 06's T1 part.

  mount_vs_50mm.py G139M.DAT G139.DAT

For each slot 1..8 the decoded 552-byte entries (descriptor fields + all ten
rows, row CRCs recomputed) of l08firm and jlaunch are compared byte by byte.
Expected: slots 1, 2, 3, 5, 7, 8 identical; slot 06 differs only in the
mask byte (1 vs 7), the C/D rows (bytes 379..444, MOUNT stock), their CRC
(280..283) and the control halfword (445..446, 0x0002 vs 0x0000); slot 04 is
the unchanged MOUNT stock entry of g139. Also: row 14 (A14/B14) == row 5
(A5/B5) for every non-04 MOUNT slot, and 50mm/28mm entries equal g139's.
Writes research/g139m/diff/mount-vs-50mm.json. /usr/bin/python3 -I -B.
"""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decode as D  # noqa: E402


def entry(m, slot):
    return m['entries'][m['refs'][slot - 1]]


def ranges(diff):
    out = []
    for i in diff:
        if out and out[-1][1] == i - 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def main():
    new = {m['name']: m for m in D.modules(Path(sys.argv[1]).read_bytes())}
    old = {m['name']: m for m in D.modules(Path(sys.argv[2]).read_bytes())}
    fifty, mount, q = new['jlaunch'], new['l08firm'], new['qlaunch']
    result = dict(slots={}, checks={})
    ok = True
    for slot in range(1, 9):
        a, b = entry(mount, slot), entry(fifty, slot)
        diff = [i for i in range(552) if a[i] != b[i]]
        row = dict(identical=not diff, differing_byte_ranges=ranges(diff), mount_mask=a[1], fifty_mask=b[1],
                   mount_control=D.control(a), fifty_control=D.control(b))
        if slot == 4:
            row['mount_stock_unchanged_from_g139'] = a == entry(old['l08firm'], 4)
            ok &= row['mount_stock_unchanged_from_g139']
        elif slot == 6:
            allowed = {1} | set(range(280, 284)) | set(range(379, 447))
            row['only_t1_part'] = bool(diff) and set(diff) <= allowed
            row['mount_cd_is_mount_stock'] = a[379:445] == entry(mount, 4)[379:445]
            row['mount_cd_equals_g139_mount_06_cd'] = a[379:447] == entry(old['l08firm'], 6)[379:447]
            row['mount_mask_t1_bits_clear'] = not a[1] & 6 and D.control(a) == 2
            ok &= row['only_t1_part'] and row['mount_cd_is_mount_stock'] and row['mount_mask_t1_bits_clear']
        else:
            ok &= row['identical']
        if slot != 4:
            row['row14_equals_row5'] = a[456:518] == a[20:82] and a[518:551] == a[82:115]
            ok &= row['row14_equals_row5']
        result['slots'][slot] = row
    for name in ('jlaunch', 'qlaunch'):
        same = all(entry(new[name], s) == entry(old[name], s) for s in range(1, 17))
        result['checks'][f'{name}_entries_equal_g139'] = same; ok &= same
    for key in ('map', 'records', 'refs', 'ranges', 'pin', 'crc_pin'):
        same = mount[key] == old['l08firm'][key]
        result['checks'][f'l08firm_{key}_equal_g139'] = same; ok &= same
    result['checks']['l08firm_slots_9_16_alias_stock'] = all(mount['refs'][s - 1] == 4 for s in range(9, 17))
    result['checks']['qlaunch_equals_jlaunch_slots_1_8'] = all(entry(q, s) == entry(fifty, s) for s in (1, 2, 3, 5, 6, 7, 8))
    result['PASS'] = bool(ok and result['checks']['l08firm_slots_9_16_alias_stock'])
    target = HERE / 'diff/mount-vs-50mm.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(result, indent=1))
    sys.exit(0 if result['PASS'] else 1)


if __name__ == '__main__':
    main()
