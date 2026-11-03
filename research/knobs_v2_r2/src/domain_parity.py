"""Check the expanded core dose domain, independently of calibrated UI levels."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hashlib
import random
import support as s
import knobs as k
from bridge import C, compare


def main():
    s.guard()
    modules = s.parse()
    c = C(build=False)
    records, payload = [], bytearray()
    rng = random.Random(0x6b327232)

    def check(m, slot, request, kind):
        b, stats = compare(c, m['entries'][4], m['entries'][slot], request)
        records.append(dict(unit=m['name'], slot=slot, kind=kind, amount=request.amount,
                            doses=list(request.doses), wb_method=request.wb_method, tone_method=request.tone_method,
                            offset=len(payload), sha256=hashlib.sha256(b).hexdigest(), stats=stats))
        payload.extend(b)

    for m in modules:
        for slot in range(1, 9):
            for i, limit in enumerate(k.MAX_DOSES):
                for dose in ((limit,) if i == 3 else (-limit, limit)):
                    ds = [0]*10
                    ds[i] = dose
                    check(m, slot, k.Request(100, tuple(ds)), 'single-domain-end')
    for n in range(2048):
        m, slot = modules[n % 3], 1+rng.randrange(8)
        ds = [rng.randint(-limit, limit) for limit in k.MAX_DOSES]
        ds[3] = rng.randint(0, 4096)
        check(m, slot, k.Request(rng.randint(0, 150), tuple(ds), rng.randrange(2), rng.randrange(2)), 'mixed-domain')
    (s.LOCAL/'domain_parity.bin').write_bytes(payload)
    s.dump(s.LOCAL/'domain_parity.json', dict(status='PASS', cases=len(records), boundary_cases=456,
           seeded_mixed_cases=2048, seed=0x6b327232,
           source_sha256={str(p.relative_to(s.ROOT)):s.sha(p) for p in
                          (s.HERE/'src/knobs.c', s.HERE/'src/knobs.h', s.HERE/'src/knobs.py',
                           s.HERE/'src/bridge.py', s.HERE/'src/domain_parity.py')}, records=records))
    print('PASS C/Python expanded-domain parity:', len(records), 'cases, every byte and counter equal')


if __name__ == '__main__':
    main()
