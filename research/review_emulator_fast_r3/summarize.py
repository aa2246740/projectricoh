"""Recompute review comparisons from completed raw receipts, never author totals."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RUNS = HERE / 'runs'


def read(name):
    return json.loads((RUNS / (name + '.json')).read_text())


def diff(left, right, path=''):
    if type(left) is not type(right):
        return [path + ':type']
    if isinstance(left, dict):
        rows = [path + '/' + str(k) + ':missing' for k in left.keys() ^ right.keys()]
        for k in left.keys() & right.keys():
            rows.extend(diff(left[k], right[k], path + '/' + str(k)))
        return rows
    if isinstance(left, list):
        if len(left) != len(right):
            return [path + ':length']
        return [v for i, (a, b) in enumerate(zip(left, right)) for v in diff(a, b, path + '/' + str(i))]
    return [] if left == right else [path]


def main():
    result = dict(flows={}, controls={}, snapshots={})
    for name, native, reference in (
            ('menu', 'menu-native-03', 'menu-reference-03'),
            ('release', 'release-native', 'release-reference'),
            ('recovery', 'recovery-native', 'recovery-reference'),
            ('sd-keys', 'sd-keys-native', 'sd-keys-reference')):
        a, b = read(native), read(reference)
        differences = diff(a['points'], b['points'])
        row = dict(native_status=a['status'], reference_status=b['status'],
                   checkpoints=len(a['points']), differences=differences,
                   steps=a.get('steps', max(p['steps'] for p in a['points'].values())),
                   native=a.get('native'), sources=[native + '.json', reference + '.json'])
        assert a['status'] in ('PASS', 'COMPLETE') and b['status'] in ('PASS', 'COMPLETE')
        assert not differences, (name, differences)
        result['flows'][name] = row
    a, b = read('input-segments-native'), read('input-segments-reference')
    assert a['full_state'] == b['full_state'] and a['receipt'] == b['receipt']
    result['flows']['input-segments'] = dict(steps=a['steps'], full_state_equal=True, receipt_equal=True,
                                            native=a['native'], full_state=a['full_state'])
    a, b = read('input-resume-native'), read('input-resume-reference')
    assert all(a[k]['state'] == b[k]['state'] for k in ('base', 'continued'))
    result['flows']['input-resume'] = dict(phases=a, state_equal=True)
    old = read('replay-old04')
    assert old['status'] == 'PASS' and old['counts'] == {'ACCEPTED': 1, 'REJECTED': 70}
    a = read('old04-01')['cases']['self-modifying']
    b = read('smc-reference')['cases']['self-modifying']
    assert a['state'] == b['state'] and a['detail'] == b['detail'] == [1, 127, 126, 42]
    result['historical'] = dict(counts=old['counts'], positive_state_equal=True,
                               positive_native=a['native'], positive_state=a['state']['all'],
                               nonzero_prefix=[dict(index=i, script=r['script'], args=r['args'], steps=r['steps'])
                                               for i, r in enumerate(old['rows'], 1) if any(r['steps'])])
    matrix = read('model-matrix-review')
    assert matrix['status'] == 'PASS' and len(matrix['pairs']) == 16
    assert sum(len(r['rejections']) for r in matrix['rejections']) == 64
    result['models'] = dict(combinations=16, points=sum(r['points_equal'] for r in matrix['pairs']),
                          independent_keys=len({r['snapshot_key'] for r in matrix['pairs']}), rejected_changes=64)
    result['snapshot-positive'] = read('snapshot-acceptance')['status']
    for case in ('label-long', 'label-nul', 'stop-watch-order', 'watch-stop-order'):
        a, b = read('control-' + case + '-native'), read('control-' + case + '-reference')
        result['controls'][case] = dict(native_status=a['status'], reference_status=b['status'],
                                       native_steps=a['steps'], reference_steps=b['steps'],
                                       differences=diff(a['state'], b['state']),
                                       native_kinds=[x['kind'] for x in a['flow']['rows']],
                                       reference_kinds=[x['kind'] for x in b['flow']['rows']])
    for backend in ('native', 'reference'):
        name = 'key-off-native-recipe-native' if backend == 'native' else 'key-current-reference-recipe-reference'
        x = read(name)
        result['snapshots']['recipe-' + backend] = dict(
            key=x['old_key'], keys_equal=x['keys_equal'], accepted=x['accepted'],
            before=x['target_stop_after_before'], after=x['target_stop_after_after'])
        x = read('hold-native-02' if backend == 'native' else 'hold-reference')
        result['snapshots']['ready-hold-' + backend] = dict(
            snapshot_layer='strict_r2' if backend == 'native' else 'legacy fix_r1',
            accepted=x['accepted'], actual_state_equal=x['actual_state_equal'],
            packets_before=len(x['live_controls_before']['held_ready']),
            packets_after=len(x['live_controls_after']['held_ready']),
            continuations=[dict(old_steps=r['old_steps'], restored_steps=r['restored_steps'],
                                error=r.get('error'), equal=r.get('equal'),
                                old_pc=r.get('old_state', {}).get('registers', {}).get('pc'),
                                restored_pc=r.get('restored_state', {}).get('registers', {}).get('pc'))
                           for r in x['continuations']])
    for case in ('label-long', 'label-nul', 'label-pair'):
        names = ['control-' + case + '-real-' + b for b in ('native', 'reference')]
        if all((RUNS / (n + '.json')).exists() for n in names):
            a, b = map(read, names)
            result['controls'][case + '-real'] = dict(steps=a['steps'],
                differences=diff(a['state'], b['state']), native=a['native'],
                native_status=a['status'], reference_status=b['status'])
    result['normal_flows_all_equal'] = True
    (RUNS / 'assessment-review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
