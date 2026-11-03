#!/usr/bin/python3
"""Compare recovery_path.py runs: milestone sequences (label, step, task, path, r0, r4)
must be identical; hook and resident execution must be absent.
  /usr/bin/python3 -I -B research/body_v39/tests/recovery_compare.py <out.json> <label> <label> ...
"""
import json
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent.parent / 'evidence'


def key(row):
    return tuple(row.get(k) for k in ('label', 'step', 'task', 'path', 'r0', 'r4'))


def main():
    out, labels = sys.argv[1], sys.argv[2:]
    runs = {l: json.loads((EVIDENCE / f'recovery-{l}.json').read_text()) for l in labels}
    base = labels[0]
    result = dict(labels=labels, runs={})
    for label, run in runs.items():
        seq = [key(r) for r in run['milestones'] if r['label'] != 'input-read' or True]
        result['runs'][label] = dict(image_sha256=run['image_sha256'], stop=run['stop'], steps=run['steps'],
                                     milestones=len(seq), hooks_or_resident_executed=run['hooks_or_resident_executed'],
                                     pc_in_resident_window=len(run['pc_in_resident_window']),
                                     nand_commands=run.get('nand_commands'),
                                     identical_to_first=seq == [key(r) for r in runs[base]['milestones']],
                                     files_opened=[r['path'] for r in run['milestones'] if r['label'] == 'file-open'])
    result['all_identical'] = all(r['identical_to_first'] for r in result['runs'].values())
    result['no_hook_or_resident'] = all(not r['hooks_or_resident_executed'] and not r['pc_in_resident_window']
                                        for r in result['runs'].values())
    (EVIDENCE / out).write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(dict(all_identical=result['all_identical'], no_hook_or_resident=result['no_hook_or_resident'],
                          steps={l: r['steps'] for l, r in result['runs'].items()})))


if __name__ == '__main__':
    main()
