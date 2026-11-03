#!/usr/bin/python3 -I -B
"""Compare update-path runs of length-word images (produced with a Scratch copy
of research/body_v39/tests/recovery_path.py, outputs redirected to Scratch)
against the frozen official run research/body_v39/evidence/recovery-yes-official.json.

Milestone key = (label, step, task, path, r0, r4), same as recovery_compare.py.
Rows labelled 'hook-word C-...' are candidate v4 hook sites added only to the
second run; they are reported separately and excluded from the comparison.

  recovery_er_compare.py <run.json> [<run.json> ...]   -> JSON on stdout
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL = ROOT / 'research/body_v39/evidence/recovery-yes-official.json'


def key(row):
    return tuple(row.get(k) for k in ('label', 'step', 'task', 'path', 'r0', 'r4'))


def main():
    base = json.loads(OFFICIAL.read_text())
    base_seq = [key(r) for r in base['milestones']]
    out = dict(official=dict(image_sha256=base['image_sha256'], steps=base['steps'], stop=base['stop'],
                             milestones=len(base_seq), nand_commands=base.get('nand_commands')), runs={})
    for name in sys.argv[1:]:
        run = json.loads(Path(name).read_text())
        seq = [key(r) for r in run['milestones']]
        first_diff = next((i for i, (a, b) in enumerate(zip(seq, base_seq)) if a != b), None)
        if first_diff is None and len(seq) != len(base_seq):
            first_diff = min(len(seq), len(base_seq))
        old = [h for h in run['hooks_or_resident_executed'] if not h.startswith('hook-word C-')]
        cand = {k: v for k, v in run['counts'].items() if k.startswith('hook-word C-')}
        first_cand = {}
        for r in run.get('hook_rows', []):
            if r['label'].startswith('hook-word C-') and r['label'] not in first_cand:
                first_cand[r['label']] = dict(step=r['step'], task=r['task'], lr=r['lr'])
        out['runs'][run['label']] = dict(
            image_sha256=run['image_sha256'], steps=run['steps'], stop=run['stop'],
            confirm_step=run['confirm_phase'].get('confirm_step'), milestones=len(seq),
            identical_to_official=seq == base_seq, first_difference=first_diff,
            nand_commands_equal=run.get('nand_commands') == base.get('nand_commands'),
            existing_hook_words_or_resident_executed=old,
            pc_in_resident_window=len(run['pc_in_resident_window']),
            candidate_site_hits=cand, candidate_first_hit=first_cand,
            files_opened=[r['path'] for r in run['milestones'] if r['label'] == 'file-open'][:12])
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
