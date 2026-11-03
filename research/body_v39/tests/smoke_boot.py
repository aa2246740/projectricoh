"""Smoke: boot the v3.9 body + gen 149 DAT on one unit, open the list once.

  /usr/bin/python3 -I -B research/body_v39/tests/smoke_boot.py <unit>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v39_host as H

R = 0x20054700


def main():
    unit = sys.argv[1]
    start = time.monotonic()
    H.setup()
    cam = H.Camera(unit)
    state = cam.h.u(R + 5, 1)
    opened = cam.open_menu()
    after = dict(root_state=cam.h.u(R + 5, 1), flags=hex(cam.h.u(R + 212)), check_failure=cam.h.u(R + 152),
                 rows=cam.h.u(0x2022f5ac, 1), names=hex(cam.h.u(0x2022f5a8)))
    block = cam.h.u(R + 56)
    caps = cam.h.u(block + 340) if block else None
    print(json.dumps(dict(unit=unit, state_after_boot=state, opened=str(opened)[:300], after=after,
                          capabilities=hex(caps) if caps is not None else None,
                          frame=cam.state() if after['rows'] == 8 else None,
                          seconds=round(time.monotonic() - start, 1)), default=str))


if __name__ == '__main__':
    main()
