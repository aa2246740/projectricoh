"""Sequential 16 model pairs and 64 stale-model restore rejections."""
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def invoke(name, args):
    env = dict(os.environ, GXR_STRICT_REFERENCE_ORACLE='legacy')
    run = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'review.py'), 'recipe',
                          'model_matrix', *args], cwd=ROOT, capture_output=True, text=True,
                         timeout=240, env=env)
    (HERE / 'runs' / (name + '.log')).write_text(run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError((name, run.returncode, run.stderr[-1500:]))
    row = json.loads(run.stdout.strip().splitlines()[-1])
    (HERE / 'runs' / (name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
    return row


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    result = dict(pairs=[], rejections=[])
    target = HERE / 'runs/model-matrix-review.json'; assert not target.exists()
    for mask in range(16):
        pair = {b: invoke('matrix-' + str(mask) + '-' + b,
                         ['--child', '--mask', str(mask), '--backend', b]) for b in ('reference', 'native')}
        assert pair['reference']['points'] == pair['native']['points'], mask
        result['pairs'].append(dict(mask=mask, points_equal=len(pair['native']['points']),
                                    native=pair['native']['native'], snapshot_key=pair['native']['snapshot']['key']))
        target.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(dict(mask=mask, equal=True)), flush=True)
    assert len({r['snapshot_key'] for r in result['pairs']}) == 16
    for mask in range(16):
        row = invoke('matrix-reject-' + str(mask), ['--reject', '--mask', str(mask)])
        result['rejections'].append(row)
        target.write_text(json.dumps(result, indent=2) + '\n')
    result['status'] = 'PASS'
    target.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
