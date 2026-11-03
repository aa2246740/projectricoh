"""Collect completed native cases and bind their evidence to local inputs."""
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, ROOT, save, sha, verify_pins

NAMES = ('ready-at-entry', 'ready-before-H01', 'ready-after-H01', 'ready-after-open',
         'link-after-open', 'both-after-open', 'not-ready-before-exit', 'late-ready-Fn2')


def run():
    verify_pins()
    rows, covered = [], Counter()
    for name in NAMES:
        path = OUT/'native'/ (name+'.json')
        case = json.loads(path.read_text())
        assert case['status'] == 'PASS'
        assert not case['ui_fields_assigned_by_research_script']
        assert case['native_getter_fixed_result_removed']
        assert all(value == 0 for value in case['file_observations'].values())
        assert case['publication_writers']
        if name in ('ready-after-open', 'link-after-open', 'both-after-open', 'not-ready-before-exit'):
            exits = [s for s in case['steps'] if s['label'] == 'native ADJ exit through event table']
            assert len(exits) == (2 if name == 'not-ready-before-exit' else 1)
            for step in exits:
                result = step['result']
                assert result['source_state'] == 56 and result['key'] == '0x2b'
                assert [c['entry'] for c in result['callbacks']] == ['0x202c2abc', '0x202b76ec']
        for event in case['publication_writers']:
            assert event['origin'] == 'cpu'
            expected = '0x200935de' if event['address'] == '0x200d7fd8' else '0x2006387c'
            assert event['writer_pc'] == expected
        for step in case['steps']:
            state = step['after']
            if state['root']['state'] == 0:
                assert state['engine_calls'] == 0 and state['root']['block'] == 0
                assert not state['root']['flags'] & 32
                assert state['file_calls'] == state['rpc_calls'] == 0
                assert state['names'] == '0x2022d610'
        drawings = []
        for event in case['hooks']:
            if event['hook'] == 1:
                drawings.append([])
            elif event['hook'] == 5 and drawings:
                drawings[-1].append(event['rows'])
        assert all(group and len(set(group)) == 1 for group in drawings)
        first = case['steps'][0]['after']
        last = case['steps'][-1]['after']
        covered.update({k: int(v) for k, v in last['hooks'].items()})
        rows.append(dict(name=name, first_rows=first['rows'], final_rows=last['rows'],
                         final_loads=last['loads'], final_engine_calls=last['engine_calls'],
                         hook_counts=last['hooks'], publication_writes=len(case['publication_writers']),
                         first_draw_rows=[group[0] for group in drawings],
                         evidence=str(path.relative_to(OUT)), sha256=sha(path.read_bytes())))
    assert set(covered) == set(map(str, (1, 2, 5, 6, 7, 8, 9)))
    sources = [
        'firmware/engine_v38_b36/integration_native.py',
        'firmware/engine_v38_b36/native_binding.py',
        'tools/native_harness/harness.py',
        'tools/native_harness/image_loader.py',
        'tools/native_harness/python_backend.py',
        'tools/native_harness/backend_api.py',
        'tools/native_harness/product_execute.py',
        'tools/native_harness/field_replay.py',
        'research/emulator_feasibility_r1/prototype/boot_probe.py',
    ]
    save('harness-provenance.json', [dict(path=p, sha256=sha((ROOT/p).read_bytes())) for p in sources])
    result = dict(status='PASS', native_cases=len(rows), cases=rows,
                  hooks_covered=dict(covered), real_native_getter=True,
                  native_readiness_writers=True, normal_UI_state_assigned=False,
                  exits_follow_native_event_table=True,
                  product_DAT_built=False, generation120_executed=False,
                  camera_or_card_used=False, network_used=False,
                  model_boundaries=['settings and font inputs', 'allocator', 'unit transport and RPC',
                                    'file open/read/close', 'graphics and system services', 'CRC equivalent calculation'])
    save('acceptance.json', result)
    print(json.dumps(dict(status='PASS', native_cases=len(rows), hooks=dict(covered))))


if __name__ == '__main__':
    run()
