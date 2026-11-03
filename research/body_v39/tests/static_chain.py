#!/usr/bin/python3 -I
"""Bounded static check: do any replaced hook words lie on the firmware-update path?

For each replaced word (H01/H02/H05-H10/H40) the script finds the enclosing
function (start = first word after the previous 'jmp lr', padding skipped; if
that start has no caller or pointer it steps back to the previous 'jmp lr', up to
6 times), then walks callers upwards through direct calls ('seth/or3 ... jl' and
24-bit 'bl') and exact big-endian 32-bit pointers, to depth 10. It reports
whether any update-path function appears among the ancestors, and where each
search ended (no caller found, or a pointer table, i.e. an indirect call).

It reads the image given with --image (the bytes outside the resident window are
the official ones for v3.9; see build_image.py's image-diff-exact). Call sites
inside the resident window are ignored (they are the resident itself).
This is a bounded static argument (heuristic function starts, no computed
targets); the decisive evidence is the emulator run (recovery_path.py).

  /usr/bin/python3 -I -B research/body_v39/tests/static_chain.py --image <ilaunch3> --out <json>
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

HOOKS = {'H01': 0x2028709C, 'H02': 0x202870A8, 'H05': 0x201FEBE4, 'H06': 0x202BE24C, 'H07': 0x202871D8,
         'H08': 0x202BB968, 'H09': 0x2017098C, 'H10': 0x202B120C, 'H40/H41': 0x2015F9D8}
UPDATE_PATH = {0x2005C1D8: 'common init loop', 0x2005CE08: 'start-up continuation', 0x2005C538: 'boot scan',
               0x2005CCE4: 'mode table loop', 0x2036E9AC: 'update init', 0x2036E34C: 'update handler',
               0x2036D4E8: 'update UI', 0x2036CAD8: 'update UI inner', 0x2036C9E4: 'confirmation stage',
               0x20069160: 'event wait', 0x200690B0: 'event wait (inner)', 0x20069018: 'event receive'}
WINDOW = (0x2005276C, 0x20054800)


class Image:
    def __init__(self, path):
        self.raw = Path(path).read_bytes()
        rows = [struct.unpack_from('>5I', self.raw, 0x20 + 20 * i) for i in range(16)]
        self.rows = [(src + 0x200, va, size) for src, va, size, _, _ in rows if size]

    def half(self, a):
        for off, va, size in self.rows:
            if va <= a < va + size - 1:
                return int.from_bytes(self.raw[off + a - va:off + a - va + 2], 'big')
        return None

    def words(self):
        for off, va, size in self.rows:
            for i in range(0, size - 3, 2):
                yield va + i, int.from_bytes(self.raw[off + i:off + i + 4], 'big')


def call_index(img):
    """target -> list of call/pointer sites."""
    sites = {}
    pending = {}                                      # register -> (hi, site) from seth
    for a, w in img.words():
        if WINDOW[0] <= a < WINDOW[1]:
            continue
        if (w >> 24) == 0xFE:                         # bl disp24 (word aligned)
            if a % 4 == 0:
                d = w & 0xFFFFFF
                d -= (1 << 24) if d & 0x800000 else 0
                sites.setdefault((a & ~3) + 4 * d, []).append(('bl', a))
        if (w & 0xF0FF0000) == 0xD0C00000 and a % 4 == 0:       # seth rX,#hi
            pending[(w >> 24) & 15] = (w & 0xFFFF, a)
        elif (w & 0xF0F00000) == 0x80E00000 and a % 4 == 0:     # or3 rX,rY,#lo
            dst, srcr = (w >> 24) & 15, (w >> 16) & 15
            if dst == srcr and dst in pending and a - pending[dst][1] <= 16:
                target = pending[dst][0] << 16 | (w & 0xFFFF)
                for k in range(0, 24, 2):                       # jl rX within a few halfwords
                    h = img.half(a + 4 + k)
                    if h == (0x1EC0 | dst):
                        sites.setdefault(target, []).append(('jl', a))
                        break
        if a % 4 == 0 and 0x20000000 <= w < 0x20800000:
            sites.setdefault(w, []).append(('pointer', a))
    return sites


def function_start(img, a, sites, tries=6):
    candidates = []
    p = a
    for _ in range(tries):
        while p > 0 and img.half(p) not in (0x1FCE, None):
            p -= 2
        if img.half(p) is None:
            break
        start = p + 2
        while img.half(start) in (0xF000, 0x7000):
            start += 2
        start = (start + 3) & ~3 if start % 4 else start
        candidates.append(start)
        if start in sites:
            return start, candidates
        p -= 2
    return (candidates[0] if candidates else None), candidates


def ancestors(img, sites, start, depth=10):
    seen, frontier, ends = {start: 0}, [start], []
    while frontier:
        f = frontier.pop()
        d = seen[f]
        callers = sites.get(f, [])
        if not callers:
            ends.append(dict(function=hex(f), end='no direct caller or pointer found'))
            continue
        for kind, site in callers:
            if kind == 'pointer':
                ends.append(dict(function=hex(f), end='pointer at ' + hex(site) + ' (indirect call)'))
                continue
            parent, _ = function_start(img, site, sites)
            if parent is None or parent in seen or d + 1 > depth:
                continue
            seen[parent] = d + 1
            frontier.append(parent)
    return seen, ends


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    img = Image(args.image)
    sites = call_index(img)
    result = dict(image=args.image, image_sha256=hashlib.sha256(img.raw).hexdigest(),
                  method=__doc__.split('\n\n')[1].replace('\n', ' '), hooks={})
    for name, a in HOOKS.items():
        start, tried = function_start(img, a, sites)
        seen, ends = ancestors(img, sites, start)
        hit = {hex(f): UPDATE_PATH[f] for f in seen if f in UPDATE_PATH}
        result['hooks'][name] = dict(word=hex(a), function_start=hex(start), start_candidates=[hex(c) for c in tried],
                                     ancestor_functions=len(seen), update_path_ancestors=hit,
                                     search_ends=ends[:20], ancestors=[hex(f) for f in sorted(seen)][:80])
    result['update_path_reached_from_any_hook'] = any(h['update_path_ancestors'] for h in result['hooks'].values())
    Path(args.out).write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({n: (h['function_start'], h['ancestor_functions'], h['update_path_ancestors'],
                          len(h['search_ends'])) for n, h in result['hooks'].items()}))


if __name__ == '__main__':
    main()
