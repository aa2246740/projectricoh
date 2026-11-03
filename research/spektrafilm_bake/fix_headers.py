#!/usr/bin/env python3
"""Rewrite only our attribution lines in already-exported cubes to bake.ATTRIBUTION (the author's suggested
'Derived from spektrafilm' wording); checks the LUT rows stay byte-identical and logs hashes before/after."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bakelib import CUBES, LOCAL, check_paths, dump, sha
from bake import ATTRIBUTION

OLD_FIRST = '# Attribution: film and print profiles and the LUT exporter by Andrea Volpato, spektrafilm,'
OLD_LAST = '# Not endorsed by Andrea Volpato or by the film manufacturer; film names only identify the simulated stock.'


def main():
    log = []
    for p in sorted(CUBES.glob('spektrafilm_*.cube')):
        lines = p.read_text().splitlines()
        if OLD_FIRST not in lines:
            continue
        i, j = lines.index(OLD_FIRST), lines.index(OLD_LAST)
        new = lines[:i] + ['# ' + l for l in ATTRIBUTION] + lines[j + 1:]
        assert [l for l in new if not l.startswith('#')] == [l for l in lines if not l.startswith('#')]
        before = sha(p)
        check_paths(p)
        p.write_text('\n'.join(new) + '\n')
        log.append({'file': p.name, 'sha256_before': before, 'sha256_after': sha(p)})
    dump(LOCAL / 'header_fix.json', log)
    print(len(log), 'headers rewritten')


if __name__ == '__main__':
    main()
