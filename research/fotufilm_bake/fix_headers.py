#!/usr/bin/env python3
"""Rewrite only the comment header of each baked cube to the exact notice wording
(Copyright 2026 MUAStudio Inc.); verifies the LUT rows are byte-identical before replacing."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CUBES, LOCAL, check_paths, dump, sha

OLD = 'Film profile data (c) MUAStudio, CC BY-SA 4.0. Rendered with Fotufilm (https://fotufilm.com).'
NEW = ['Film profile: Fotufilm (https://fotufilm.com), Copyright 2026 MUAStudio Inc., CC BY-SA 4.0.',
       'Changes: rendered by the fotufilm CLI on an identity grid with the settings above and stored as a',
       '33^3 table; nothing else in the profile was altered.']


def main():
    log = []
    for p in sorted(CUBES.glob('fotufilm_*.cube')):
        text = p.read_text()
        if OLD not in text:
            continue
        head, body = [], []
        for line in text.splitlines():
            (head if line.startswith('#') else body).append(line)
        new_head = []
        for line in head:
            new_head += [f'# {n}' for n in NEW] if line == f'# {OLD}' else [line]
        new = '\n'.join(new_head + body) + '\n'
        assert [l for l in new.splitlines() if not l.startswith('#')] == body
        before = sha(p)
        check_paths(p)
        p.write_text(new)
        log.append({'file': p.name, 'sha256_before': before, 'sha256_after': sha(p)})
    dump(LOCAL / 'header_fix.json', log)
    print(len(log), 'headers rewritten')


if __name__ == '__main__':
    main()
