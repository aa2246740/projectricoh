"""Fn rotation on the host model with the host-only variant DAT
(firmware/engine_v59_g151/variants/fn-test: fn_next=0x22, fn_prev=0x21).

Run with V39_PACKAGE=research/body_v39/local/fntest-package
         V39_ENGINE=firmware/engine_v59_g151/variants/fn-test
  /usr/bin/python3 -I -B research/body_v39/tests/dat_rotate.py <unit>

Flow: H10 at state 5 (fixture: view word 5 for that call only) turns the Fn
code into ADJ 0x2B and arms one rotation; the next H01 offers the neighbouring
recipe without applying it; OK on the offered row applies it (stock OK path,
not rerouted). A rotation older than three DAT entries is dropped. Fn codes at
state 56 pass through unchanged.
"""
import json
import os
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v39_host as H
from dat_body import Site, R

OUT = HERE.parent / 'evidence' / os.environ.get('V39_EVIDENCE_DIR', '')


def at_state5(cam, site, code):
    view = cam.h.u(0x205D9C00)
    site.put(0x205D9C00, (5).to_bytes(4, 'big'))
    try:
        return site.h10(code)
    finally:
        site.put(0x205D9C00, view.to_bytes(4, 'big'))


def main():
    unit = sys.argv[1]
    start = time.monotonic()
    assert 'fntest' in str(H.PACKAGE) and 'fn-test' in str(H.ENGINE)
    H.setup()
    cam = H.Camera(unit)
    st = cam.open_menu() and cam.state()
    site = Site(cam)
    report = dict(unit=unit, dat_sha256=H.sha(H.DAT), engine_elf_sha256=H.sha(H.ENGINE), steps=[])
    first = cam.state()
    report['initial'] = dict(slot=first['slot'], cur=first['cur'])
    # Fn at state 56 is not ours to change
    assert site.h10(0x22) == 0x22 and site.h10(0x21) == 0x21
    for code, want in ((0x22, 1), (0x21, -1)):
        before = cam.state()['slot']
        assert at_state5(cam, site, code) == 0x2B
        cam.open_menu()
        offered = cam.state()
        target = before % 8 + 1 if want > 0 else (before + 6) % 8 + 1
        assert offered['cur'] == target - 1 and offered['slot'] == before, (offered, target)
        assert site.h10(0x23) == 0x23                      # OK on the offered row is not rerouted
        applied = cam.press('OK')
        assert applied['slot'] == target, applied
        report['steps'].append(dict(code=hex(code), slot_before=before, offered_row=offered['cur'],
                                    slot_after_ok=applied['slot']))
    # stale rotation: more than three DAT entries between the Fn press and H01
    before = cam.state()['slot']
    assert at_state5(cam, site, 0x22) == 0x2B
    saved = bytes(cam.h.b.read(0x20610000, 144))
    for _ in range(4):
        site.call(0x2017098C, 0x20170990, {'r5': 0x20610000})      # four more DAT entries (H09)
    site.put(0x20610000, saved)
    cam.open_menu()
    late = cam.state()
    assert late['slot'] == before and late['cur'] == before - 1, late
    report['stale_rotation'] = dict(slot=late['slot'], cur=late['cur'], offered=False)
    report['seconds'] = round(time.monotonic() - start, 1)
    OUT.mkdir(exist_ok=True)
    (OUT / f'dat-rotate-{unit}.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
