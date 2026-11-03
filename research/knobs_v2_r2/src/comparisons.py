"""Retain T1 and B&W Tone algorithms as explicitly excluded comparisons."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hashlib
import json
import support as s
import knobs as k
from bridge import C, compare


def main():
    s.guard()
    modules = {m['name']:m for m in s.parse()}
    c = C(build=False)
    source = s.ROOT/'research/knobs_v2_r1/local/alternatives.json'
    alternatives = [g for g in json.loads(source.read_text()) if g['param'] in ('warmth', 'tint')]
    rows, count, payload = [], 0, bytearray()
    for g in alternatives:
        m = modules[g['unit']]
        doses = {int(a):d for a, d in g['doses'].items()}
        for level, dose in sorted(doses.items()):
            b, _ = compare(c, m['entries'][4], m['entries'][g['slot']],
                           k.request_for(g['param'], dose, wb_method=1))
            rows.append(dict(unit=g['unit'], slot=g['slot'], param=g['param'], level=level,
                             dose=dose, wb_method=1, offset=len(payload), sha256=hashlib.sha256(b).hexdigest()))
            payload.extend(b)
            count += 1
    tone_count = 0
    for unit, m in modules.items():
        for method in (0, 1):
            for level in range(-9, 10):
                dose = k.rd(level*k.Q, 9)
                b, _ = compare(c, m['entries'][4], m['entries'][3],
                               k.request_for('tone', dose, tone_method=method))
                rows.append(dict(unit=unit, slot=3, param='tone', level=level, dose=dose,
                                 tone_method=method, offset=len(payload), sha256=hashlib.sha256(b).hexdigest()))
                payload.extend(b)
                tone_count += 1
    (s.LOCAL/'comparison_entries.bin').write_bytes(payload)
    s.dump(s.LOCAL/'comparisons.json', dict(final_menu=False, source=str(source.relative_to(s.ROOT)),
           source_sha256=s.sha(source), T1_parity_cases=count, Tone_parity_cases=tone_count,
           Tone_visibility='unknown on camera; matrix chroma may be erased by 03 zero colour row', states=rows))
    print('PASS excluded comparison parity:', count, 'T1 states;', tone_count, 'Tone states')


if __name__ == '__main__':
    main()
