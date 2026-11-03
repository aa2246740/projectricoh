"""Verify the exported C table through real menu calls and an independent meter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import support as s
s.dependencies()
import collections
import csv
import ctypes as ct
import hashlib
import itertools
import json
import random
import subprocess
import time
import numpy as np
import knobs as k
import menu
from bridge import C, CRequest, CStats, compare
from checks import inspect, changed
from model_adapter import Model, masks


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def compile_c(sources, output, sanitize=False):
    cmd = ['/usr/bin/clang', '-std=c99', '-O1' if sanitize else '-O2', '-Wall', '-Wextra', '-Werror',
           '-pedantic', '-fno-modules', '-fno-implicit-modules']
    if sanitize:
        cmd += ['-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    elif str(output).endswith('.dylib'):
        cmd += ['-dynamiclib']
    cmd += [str(s.HERE / 'src' / name) for name in sources] + ['-o', str(output)]
    cp = subprocess.run(cmd, text=True, capture_output=True)
    (s.LOCAL / (output.name + '.build.log')).write_text(' '.join(cmd) + '\n' + cp.stdout + cp.stderr)
    cp.check_returncode()


class CMenu:
    def __init__(self, build=True):
        path = s.LOCAL / 'menu.dylib'
        if build:
            compile_c(('knobs.c', 'menu.c'), path)
        self.lib = ct.CDLL(str(path))
        self.lib.kv2_apply.argtypes = [ct.c_int, ct.c_int, ct.POINTER(ct.c_int16), ct.c_int,
                                      ct.c_void_p, ct.c_void_p, ct.c_void_p, ct.POINTER(CStats)]
        self.lib.kv2_apply.restype = ct.c_int
        self.lib.kv2_request.argtypes = [ct.c_int, ct.c_int, ct.POINTER(ct.c_int16), ct.c_int, ct.POINTER(CRequest)]
        self.lib.kv2_request.restype = ct.c_int

    def apply(self, unit, slot, levels, stock, base):
        out = (ct.c_uint8 * 552)()
        stats = CStats()
        a = (ct.c_int16 * len(levels))(*levels)
        rc = self.lib.kv2_apply(unit, slot, a, len(levels), stock, base, out, ct.byref(stats))
        if rc:
            raise ValueError('C menu returned ' + str(rc))
        return bytes(out), {n: getattr(stats, n) for n, _ in stats._fields_}


def table_roundtrip(data):
    binary = s.LOCAL / 'dump_tables'
    compile_c(('dump_tables.c',), binary)
    actual = json.loads(subprocess.check_output([str(binary)], text=True))
    s.dump(s.LOCAL / 'header_roundtrip.json', actual)
    assert actual == data, 'compiled C header differs from JSON'
    assert len(data['recipes']) == 24 and len(data['items']) == 201
    return 'PASS compiled header == JSON'


def sanitized(modules):
    fixture = s.LOCAL / 'test_inputs.bin'
    fixture.write_bytes(b''.join(m['entries'][4] + m['entries'][slot] for m in modules for slot in range(1, 9)))
    binary = s.LOCAL / 'test_sanitized'
    compile_c(('knobs.c', 'menu.c', 'test_sanitized.c'), binary, sanitize=True)
    run = subprocess.run([str(binary), str(fixture)], text=True, capture_output=True)
    (s.LOCAL / 'sanitize.log').write_text(run.stdout + run.stderr)
    run.check_returncode()
    return run.stdout.strip()


def invalid_menu(cm, data, modules):
    count = 0
    for recipe in data['recipes']:
        unit, slot = recipe['unit'], recipe['slot']
        items = data['items'][recipe['first_item']:recipe['first_item'] + recipe['item_count']]
        defaults = [a['default_level'] for a in items]
        attempts = [(-1, slot, defaults), (unit, 9, defaults), (unit, slot, defaults[:-1])]
        for i, item in enumerate(items):
            for bad in (item['min_level'] - 1, item['max_level'] + 1):
                levels = defaults.copy()
                levels[i] = bad
                attempts.append((unit, slot, levels))
            if item['control'] == 0:
                levels = defaults.copy()
                levels[i] = 1
                attempts.append((unit, slot, levels))
        for u, sl, levels in attempts:
            a = (ct.c_int16 * len(levels))(*levels)
            out = (ct.c_uint8 * 552)(*([0xa5] * 552))
            stats = CStats(*([0x12345678] * 7))
            before_stats = bytes(stats)
            stock, base = modules[unit]['entries'][4], modules[unit]['entries'][slot]
            assert cm.lib.kv2_apply(u, sl, a, len(levels), stock, base, out, ct.byref(stats)) == -1
            assert bytes(out) == bytes([0xa5] * 552) and bytes(stats) == before_stats
            try:
                menu.request(data, u, sl, levels)
            except ValueError:
                pass
            else:
                raise AssertionError('Python accepted invalid menu level')
            count += 1
    return count


def main():
    s.guard()
    s.verify_inputs()
    start = time.monotonic()
    modules, model, c = s.parse(), Model(), C(build=False)
    cm, data = CMenu(), menu.load()
    header = table_roundtrip(data)
    import test_goldens
    fixtures = test_goldens.run(c)
    binary = (s.LOCAL / 'variants.bin').read_bytes()
    variants = json.loads((s.LOCAL / 'variants.json').read_text())
    saved = {(v['unit'], v['slot'], v['param'], v['level']): v for v in variants}
    adjacent, curves, limits, events, row_changes = [], [], [], [], []
    parity = default_checks = combo_states = 0
    combinations, interaction = [], []
    rng = random.Random(0x6b327232)
    for recipe in data['recipes']:
        unit, slot = recipe['unit'], recipe['slot']
        m = modules[unit]
        stock, base = m['entries'][4], m['entries'][slot]
        items = data['items'][recipe['first_item']:recipe['first_item'] + recipe['item_count']]
        defaults = [a['default_level'] for a in items]
        with np.load(s.LOCAL / f'chart-{m["name"]}-{slot:02d}.npz', allow_pickle=False) as z:
            x = z['x'].copy()
        cache = {}

        def apply(levels, dense=False):
            nonlocal parity
            key = tuple(levels)
            if key not in cache:
                rq = menu.request(data, unit, slot, levels)
                py, ps = k.apply(stock, base, rq)
                cc, cs = cm.apply(unit, slot, levels, stock, base)
                assert py == cc and ps == cs, 'C/Python menu mismatch'
                parity += 1
                info = inspect(cc, dense)
                assert not info['errors'], (m['name'], slot, levels, info['errors'])
                cache[key] = (cc, model.lab(model.predict(cc, x, quantize=True)), cs, info)
            return cache[key]

        assert apply(defaults, True)[0] == base
        for amount in (0, 25, 100, 150):
            b, _ = compare(c, stock, base, k.Request(amount))
            if amount in (0, 100):
                assert b == (stock if amount == 0 else base)
                default_checks += 1
            parity += 1
        names = [data['controls'][item['control']]['name'] for item in items]
        assert names == (['contrast', 'highlight', 'shadow', 'fade', 'filter'] if slot == 3 else
                         [p for p in ('amount', 'contrast', 'highlight', 'shadow', 'fade', 'saturation', 'warmth', 'tint', 'split')
                          if not (slot == 4 and p == 'amount')])
        for i, item in enumerate(items):
            param, previous = names[i], None
            unique_entries = set()
            region = masks(model, base, x, param, chart=True)
            assert all(int(z.sum()) >= 16 for z in region)
            if param == 'fade':
                assert [p['level'] for p in item['points']] == list(range(10))
            if param == 'amount':
                assert item['points'][0]['level'] == 0 and item['points'][-1]['level'] == 150
                assert any(p['level'] == 100 for p in item['points'])
            for point in item['points']:
                levels = defaults.copy()
                levels[i] = point['level']
                b, lab, stats, info = apply(levels, True)
                assert b not in unique_entries, 'duplicate states in one menu item'
                unique_entries.add(b)
                key = m['name'], slot, param, point['level']
                v = saved[key]
                assert b == binary[v['offset']:v['offset']+552]
                assert hashlib.sha256(b).hexdigest() == v['sha256']
                tag = dict(unit=m['name'], slot=slot, param=param, level=point['level'])
                for q in info['curves']:
                    curves.append(dict(**tag, **q))
                for q in info['limits']:
                    limits.append(dict(**tag, **q))
                if any(stats.values()):
                    events.append(dict(**tag, **stats))
                if previous is not None:
                    level, aa, la = previous
                    de = model.de(la, lab)
                    med = [float(np.median(de[z])) for z in region]
                    adjacent.append(dict(unit=m['name'], slot=slot, param=param, from_level=level,
                                         to_level=point['level'], min_median_de00=min(med),
                                         region_medians=json.dumps(med), region_counts=json.dumps([int(z.sum()) for z in region]),
                                         byte_dead=aa == b, visible=min(med) >= 1.0 and aa != b))
                    change = changed(aa, b)
                    row_changes.append(dict(unit=m['name'], slot=slot, param=param, from_level=level,
                                            to_level=point['level'], changed_entry_bytes=change['changed_entry_bytes'],
                                            changed_row_bytes=change['changed_row_bytes'],
                                            rows=','.join(z['row'] for z in change['rows'])))
                previous = (point['level'], b, lab)
        # Each unordered pair is rendered at all four final endpoints. Check
        # the last adjacent step in both directions under each fixed endpoint.
        for i, j in itertools.combinations(range(len(items)), 2):
            for pi in (items[i]['points'][0], items[i]['points'][-1]):
                for pj in (items[j]['points'][0], items[j]['points'][-1]):
                    levels = defaults.copy()
                    levels[i], levels[j] = pi['level'], pj['level']
                    b, lab, stats, info = apply(levels)
                    combo_states += 1
                    combinations.append(dict(unit=m['name'], slot=slot, a=names[i], a_level=pi['level'],
                                             b=names[j], b_level=pj['level'], entry_sha256=hashlib.sha256(b).hexdigest(),
                                             curve_jump_bound=info['max_12bit_lsb_jump_bound'], limit_count=len(info['limits']), **stats))
                    for moving, fixed in ((i, j), (j, i)):
                        points = items[moving]['points']
                        side = 0 if levels[moving] == points[0]['level'] else -1
                        neighbor = points[1 if side == 0 else -2]['level']
                        before = levels.copy()
                        before[moving] = neighbor
                        aa, la, _, _ = apply(before)
                        de = model.de(la, lab)
                        regions = masks(model, base, x, names[moving], chart=True)
                        med = [float(np.median(de[z])) for z in regions]
                        interaction.append(dict(unit=m['name'], slot=slot, param=names[moving],
                                                context=names[fixed], context_level=levels[fixed],
                                                from_level=neighbor, to_level=levels[moving],
                                                min_median_de00=min(med), byte_dead=aa == b,
                                                visible=min(med) >= 1.0 and aa != b))
        for _ in range(64):
            apply([rng.choice(item['points'])['level'] for item in items])
        print('verified', m['name'], f'{slot:02d}', 'parity', parity, 'combos', combo_states,
              f'{time.monotonic()-start:.1f}s', flush=True)
    failures = [r for r in adjacent if not r['visible']]
    write_csv(s.LOCAL / 'adjacent.csv', adjacent)
    write_csv(s.LOCAL / 'interaction_adjacent.csv', interaction)
    write_csv(s.LOCAL / 'combinations.csv', combinations)
    write_csv(s.LOCAL / 'curve_checks.csv', curves)
    write_csv(s.LOCAL / 'coefficient_limits.csv', limits)
    write_csv(s.LOCAL / 'limit_events.csv', events)
    write_csv(s.LOCAL / 'row_changes.csv', row_changes)
    invalid = invalid_menu(cm, data, modules)
    san = sanitized(modules)
    summary = dict(status='PASS' if not failures else 'FAIL', header_JSON=header,
                   parity_cases=parity+fixtures, mathematical_fixtures=fixtures,
                   individual_states=len(variants), adjacent_pairs=len(adjacent),
                   below_threshold=len(failures), byte_dead=sum(r['byte_dead'] for r in adjacent),
                   minimum_de00=min(r['min_median_de00'] for r in adjacent),
                   defaults_and_endpoints=default_checks, invalid_menu_cases=invalid,
                   extreme_combinations=combo_states, extreme_adjacent_pairs=len(interaction),
                   extreme_below_threshold=sum(not r['visible'] for r in interaction),
                   extreme_byte_dead=sum(r['byte_dead'] for r in interaction),
                   max_curve_jump_bound=max(r['curve_jump_bound'] for r in combinations),
                   limit_records=len(limits), limit_event_states=len(events), sanitizer=san,
                   source_sha256={str(p.relative_to(s.ROOT)):s.sha(p) for p in sorted((s.HERE/'src').glob('*')) if p.is_file()},
                   elapsed_seconds=time.monotonic()-start)
    s.dump(s.LOCAL / 'verification.json', summary)
    s.dump(s.LOCAL / 'verification_failures.json', failures)
    s.dump(s.LOCAL / 'model_inputs_verification.json', model.provenance())
    s.verify_inputs()
    print(json.dumps({key: value for key, value in summary.items() if key != 'source_sha256'}, ensure_ascii=False), flush=True)
    if failures:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
