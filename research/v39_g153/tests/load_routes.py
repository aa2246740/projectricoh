"""Load-route cases on the host model (real v3.9 ilaunch3 + resident + DAT code).

Scenarios (one fresh boot each; the card/IROM files are set after boot and
before the first H01, which is the only load point):
  ctl        package DAT on the card + firmware/package_v39_g153/local/disable/GXRCE.CTL
             -> the DAT's bootstrap refuses, the session is disabled for this boot,
                the stock 7-row list stays
  ctl-bad    same with a control file whose CRC is wrong -> normal load (negative control)
  no-card    no card DAT; IROM holds only the v3.8 g139 DAT -> rejected by identity, stock list
  old-dat    v3.8 g139 DAT on the card (body-dat-pair) -> rejected, stock list
  release    the package's own DAT on the card -> READY, our 8-row list
  card-dat   the DAT named by V39_CARD_DAT replaces the card DAT -> rejected, stock list
             (cross combinations: old/new body x old/new DAT; output name gets V39_LABEL)

The package (body + DAT) comes from v39_host's V39_PACKAGE / V39_RESIDENT / V39_ENGINE /
V39_BODY_SHA, so the same scenarios run on the c0 body and on the g151 body.

  /usr/bin/python3 -I -B research/body_v39/tests/load_routes.py <unit> <scenario>
"""
import hashlib
import json
import os
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v39_host as H

R = 0x20054700
G139 = H.ROOT / 'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT'
CTL = H.ROOT / 'firmware/package_v39_g153/local/disable/GXRCE.CTL'


def main():
    unit, scenario = sys.argv[1], sys.argv[2]
    start = time.monotonic()
    H.setup()
    cam = H.Camera(unit)
    files = cam.p.files
    before_keys = sorted(files.paths)
    if scenario == 'ctl':
        files.paths['/ATA1/GXRCE.CTL'] = CTL.read_bytes()
    elif scenario == 'ctl-bad':
        raw = bytearray(CTL.read_bytes()); raw[15] ^= 1
        assert zlib.crc32(bytes(raw[:12])) != int.from_bytes(raw[12:], 'big')
        files.paths['/ATA1/GXRCE.CTL'] = bytes(raw)
    elif scenario == 'no-card':
        files.paths.pop('/ATA1/GXRCE.DAT', None)
        files.paths['/IROM/GXRCE0.DAT'] = G139.read_bytes()
        files.present = False
    elif scenario == 'old-dat':
        files.paths['/ATA1/GXRCE.DAT'] = G139.read_bytes()
    elif scenario == 'card-dat':
        card = Path(os.environ['V39_CARD_DAT'])
        card = card if card.is_absolute() else H.ROOT / card
        files.paths['/ATA1/GXRCE.DAT'] = card.read_bytes()
    else:
        assert scenario == 'release'
    try:
        opened = cam.open_menu()
    except Exception as exc:                       # stock list: the harness's own-list reader may refuse
        opened = 'exception: ' + str(exc)[:200]
    state, flags = cam.h.u(R + 5, 1), cam.h.u(R + 212)
    rows, names = cam.h.u(0x2022f5ac, 1), cam.h.u(0x2022f5a8)
    result = dict(unit=unit, scenario=scenario, root_state=state, flags=hex(flags), check_failure=cam.h.u(R + 152),
                  rows=rows, names=hex(names), files_opened=files.log[-8:], files_before=before_keys,
                  opened=str(opened)[:300], seconds=round(time.monotonic() - start, 1),
                  body_sha256=H.BODY_SHA, package=str(H.PACKAGE.relative_to(H.ROOT)))
    if scenario == 'card-dat':
        raw = files.paths['/ATA1/GXRCE.DAT']
        result.update(card_dat=os.environ['V39_CARD_DAT'], card_dat_sha256=hashlib.sha256(raw).hexdigest(),
                      card_dat_generation=int.from_bytes(raw[28:32], 'big'))
    if scenario == 'release' or scenario == 'ctl-bad':
        assert state == 3 and rows == 8, result
    else:
        assert state == 6 and rows == 7 and names == 0x2022d610, result
        assert flags & 1 and not flags & 128, result          # RF_STOP set, never published
    label = os.environ.get('V39_LABEL', '')
    out = HERE.parent / 'evidence' / (os.environ.get('V39_EVIDENCE_DIR', '')) / f'load-{scenario}{label}-{unit}.json'
    out.write_text(json.dumps(result, indent=1, default=str) + '\n')
    print(json.dumps(result, default=str))


if __name__ == '__main__':
    main()
