"""Create 81 fresh job names without deleting earlier review evidence."""
import argparse
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
args = parser.parse_args()
assert re.fullmatch('[a-z0-9_-]{1,32}', args.label)
queue = json.loads((OUT / 'queue.json').read_text())
jobs = [next(job for job in queue['jobs'] if job['name'] == 'user-tool')]
for original in queue['jobs']:
    if original['kind'] != 'regression':
        continue
    job = dict(original, matrix_name=original['name'], name=original['name'] + '__' + args.label)
    assert not (OUT / 'evidence/receipts' / (job['name'] + '.json')).exists()
    assert not (OUT / 'legacy/local/jobs' / job['name']).exists()
    jobs.append(job)
assert len(jobs) == 82
path = OUT / ('repeat-' + args.label + '.json')
assert not path.exists()
path.write_text(json.dumps(dict(slots=2, jobs=jobs), indent=2) + '\n')
print(path.name)
