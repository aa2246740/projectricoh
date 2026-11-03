#!/usr/bin/python3
"""Enforce two review Python processes, retaining one PID through exec."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    assert len(sys.argv) >= 2
    target = Path(sys.argv[1]).resolve()
    assert target.parent == HERE and target.suffix == '.py'
    active = []
    text = subprocess.check_output(['ps', '-ww', '-axo', 'pid=,ni=,args='], text=True)
    for line in text.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) != 3 or int(fields[0]) == os.getpid():
            continue
        executable = fields[2].split(None, 1)[0]
        if 'python' in Path(executable).name.lower() and 'research/review_v310_body_r1/' in fields[2]:
            active.append(dict(pid=int(fields[0]), nice=int(fields[1]), command=fields[2]))
    entry = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), pid=os.getpid(),
        nice=os.getpriority(os.PRIO_PROCESS, 0), active_before=active,
        command=[str(target), *sys.argv[2:]], allowed=len(active) < 2,
        limit=2, method='The launcher replaces itself with the target Python process')
    with (HERE / 'evidence/process-allocation.jsonl').open('a') as stream:
        stream.write(json.dumps(entry) + '\n')
    print(json.dumps(dict(process_gate='ALLOW' if entry['allowed'] else 'REFUSE',
        pid=os.getpid(), other_review_processes=len(active))), flush=True)
    if not entry['allowed']:
        raise SystemExit(2)
    os.execv('/usr/bin/python3', ['/usr/bin/python3', '-I', '-B', str(target), *sys.argv[2:]])


if __name__ == '__main__':
    main()
