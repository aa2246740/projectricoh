"""Compare actual review outputs. Preserve all fields except named timing fields."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local'


def read(name):
    return json.loads((OUT / name).read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def without_times(value, path='', removed=None):
    if removed is None:
        removed = []
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            child = path + '/' + key
            if key == 'seconds':
                removed.append(child)
            else:
                result[key] = without_times(item, child, removed)
        return result
    if isinstance(value, list):
        return [without_times(item, path + '/' + str(index), removed)
                for index, item in enumerate(value)]
    return value


def sector_changes(before, after):
    assert len(before) == len(after) and len(before) % 512 == 0
    rows = []
    for offset in range(0, len(before), 512):
        a, b = before[offset:offset+512], after[offset:offset+512]
        if a != b:
            rows.append({'lba': offset//512, 'before_sha256': sha(a), 'after_sha256': sha(b)})
    return rows


def main():
    state_a, state_b = [read('state-' + impl + '.json') for impl in ['step', 'batch']]
    state = {'points_equal': state_a['points'] == state_b['points'], 'points': {}}
    archived = json.loads((ROOT / 'research/emulator_batch/local/eq-step-no-card.json').read_text())
    for point, data in state_a['points'].items():
        state['points'][point] = {'equal': data == state_b['points'][point],
            'state': data['state'], 'full_snapshot': data['full_snapshot'],
            'observations': data['observations'],
            'implementation_report_state_equal': data['state'] == archived['points'][point]['state']}
    a, b = [read('g146/' + impl + '/result.json') for impl in ['step', 'batch']]
    removed_a, removed_b = [], []
    normalized_a, normalized_b = without_times(a, removed=removed_a), without_times(b, removed=removed_b)
    reference = ROOT / 'research/emulator_m2d/local/unit28-g146/final5/card.img'
    before = reference.read_bytes()
    cards = [(OUT / 'g146' / impl / 'card.img').read_bytes() for impl in ['step', 'batch']]
    changes = {impl: sector_changes(before, card) for impl, card in zip(['step', 'batch'], cards)}
    g146 = {'result_equal_except_times': normalized_a == normalized_b,
            'removed_timing_fields': {'step': removed_a, 'batch': removed_b},
            'status': {'step': a['status'], 'batch': b['status']},
            'error': a.get('error'), 'call_rows': len(a['calls']),
            'boot_steps': [r['boot']['steps'] for r in a['calls'] if 'boot' in r],
            'input_card_sha256': sha(before), 'final_card_sha256': dict(zip(['step', 'batch'], map(sha, cards))),
            'final_card_bytes_equal': cards[0] == cards[1],
            'sector_changes_equal': changes['step'] == changes['batch'],
            'sector_changes': changes,
            'scope': 'Copy of latest final5 launch, starting from identical copies of final5/card.img; stops at its existing Dat.image error.'}
    (OUT / 'g146-sector-changes.json').write_text(json.dumps(changes, indent=2) + '\n')
    a, b = [read('probes-' + impl + '.json') for impl in ['step', 'batch']]
    comparisons = {name: a['results'][name] == b['results'][name]
                   for name in a['results'] if name != 'device_windows'}
    dynamic = {impl: {'r0': data['results']['dynamic_plain_hook']['registers']['r0'],
                      'hook_calls': len(data['results']['dynamic_plain_hook']['observations']),
                      'stop': data['results']['dynamic_plain_hook']['stop'],
                      'batch_stats': data['stats']['dynamic_plain_hook']}
               for impl, data in [('step', a), ('batch', b)]}
    result = {'state': state, 'g146': g146,
              'm2b': {key: read('m2b/m2b-review.json')[key] for key in ['passed', 'total', 'status']},
              'probes': {'compared': len(comparisons), 'equal': sum(comparisons.values()),
                         'comparisons': comparisons, 'different': [k for k,v in comparisons.items() if not v],
                         'dynamic_plain_hook': dynamic,
                         'undeclared_device': {impl: data['results']['undeclared_device']
                                               for impl, data in [('step', a), ('batch', b)]},
                         'batch_only_windows': b['results']['device_windows']},
              'm2_options_equal': read('m2-options-step.json') == read('m2-options-batch.json'),
              'checkpoints': read('checkpoints.json')}
    result['verdict'] = '不可以切换' if result['probes']['different'] else '可以切换'
    (OUT / 'comparisons.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'verdict': result['verdict'], 'state_equal': state['points_equal'],
                      'g146_equal': g146['result_equal_except_times'], 'probes': result['probes']['different'],
                      'm2b': result['m2b']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
