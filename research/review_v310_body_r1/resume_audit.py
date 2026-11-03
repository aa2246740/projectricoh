#!/usr/bin/python3
"""Record the restart boundary and verify the original frozen inputs."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    target = HERE / 'evidence/resume-preflight.json'
    assert not target.exists()
    before = json.loads((HERE / 'evidence/inputs-before.json').read_text())
    changed = []
    for name, item in before['files'].items():
        path = ROOT / name
        h = hashlib.sha256()
        if not path.is_file():
            changed.append(name)
            continue
        with path.open('rb') as stream:
            for part in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                h.update(part)
        if h.hexdigest() != item['sha256']:
            changed.append(name)
    inventory = []
    for path in sorted((HERE / 'evidence').glob('*.json')):
        if path.name == 'inputs-before.json':
            continue
        data = json.loads(path.read_text())
        inventory.append(dict(name=path.name, bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            status=data.get('status'), backend=data.get('backend'),
            steps=data.get('steps')))
    ps = subprocess.check_output(['ps', '-axo', 'pid,ppid,ni,etime,%cpu,command'], text=True)
    active = [line for line in ps.splitlines() if 'research/review_v310_body_r1/' in line]
    result = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        continuation_started_utc='2026-11-03T03:29:01+00:00',
        deadline_utc='2026-11-03T05:59:01+00:00',
        original_input_count=len(before['files']), changed=changed,
        status='PASS' if not changed else 'INPUT_CHANGED',
        initial_ps_observation='No review or emulator process remained before launching new work',
        active_at_receipt=active, inventory=inventory,
        excluded_runs=['official-tail-native', 'v310-tail-native',
                       'official-tail-reference', 'v310-tail-reference',
                       'official-tail-batch', 'v310-tail-batch'],
        rerun_rule='Only terminal complete receipts are retained; interrupted attempts are excluded and their required work is rerun on the original batch backend',
        redundant_fresh_check='release-mount-resumed-batch repeats the completed pre-restart release check',
        fast_backend_results_used_for_verdict=False)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], input_count=len(before['files']), changed=changed)))
    assert not changed


if __name__ == '__main__':
    main()
