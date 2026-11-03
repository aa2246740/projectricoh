"""Verify matching pairs, every required mismatched DAT, and disable routes."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'tests'))
import v39_host as H


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    layout = json.loads((HERE / 'local/body/local/resident/target-layout.json').read_text())
    offsets = layout['RvRoot']['offsets']
    rows = []
    new_package = ROOT / 'firmware/package_v39_g153/local/SD_ROOT'
    old_package = ROOT / 'firmware/package_v39_g151/local/SD_ROOT'
    cases = [
        ('new-new', 'new', new_package / 'GXRCE.DAT', 'ready'),
        ('old-old', 'old', old_package / 'GXRCE.DAT', 'ready'),
        ('new-old', 'new', old_package / 'GXRCE.DAT', 'reject'),
        ('old-new', 'old', new_package / 'GXRCE.DAT', 'reject'),
    ]
    for name, directory in (
        ('g137', 'package_v38_g137'), ('g139', 'package_v38_g139'),
        ('g150', 'package_v38_g150'), ('g152', 'package_v38_g152'),
        ('probe', 'package_v38_cpuprobe'),
    ):
        path = ROOT / 'firmware' / directory / 'local/SD_ROOT/GXRCE.DAT'
        if not path.is_file():
            path = ROOT / 'firmware' / directory / 'SD_ROOT/GXRCE.DAT'
        assert path.is_file(), path
        cases.append(('new-' + name, 'new', path, 'reject'))
    cases += [('new-ctl', 'new', new_package / 'GXRCE.DAT', 'disabled'),
              ('new-ctl-bad', 'new', new_package / 'GXRCE.DAT', 'ready'),
              ('new-no-card-IROM', 'new', ROOT / 'firmware/package_v38_g139/SD_ROOT/GXRCE.DAT', 'IROM')]
    for name, version, dat, expectation in cases:
        started = time.monotonic()
        H.PACKAGE = new_package if version == 'new' else old_package
        H.BODY = H.PACKAGE / 'ilaunch3'
        H.DAT = H.PACKAGE / 'GXRCE.DAT'
        H.BODY_SHA = sha(H.BODY)
        H.RESIDENT = (HERE / 'local/body/local/resident/build/resident.elf' if version == 'new'
                      else ROOT / 'firmware/resident_v39/local/resident/build/resident.elf')
        H.ENGINE = ROOT / ('firmware/engine_v62_g153' if version == 'new' else 'firmware/engine_v59_g151') / 'candidate/local/full-r13/engine.elf'
        H.setup()
        cam = H.Camera('50mm')
        files = cam.p.files
        files.paths['/ATA1/GXRCE.DAT'] = dat.read_bytes()
        files.paths.pop('/ATA1/GXRCE.CTL', None)
        if name in ('new-ctl', 'new-ctl-bad'):
            control = bytearray((ROOT / 'firmware/package_v39_g153/local/disable/GXRCE.CTL').read_bytes())
            if name == 'new-ctl-bad':
                control[15] ^= 1
            files.paths['/ATA1/GXRCE.CTL'] = bytes(control)
        if expectation == 'IROM':
            files.paths.pop('/ATA1/GXRCE.DAT')
            files.paths['/IROM/GXRCE0.DAT'] = dat.read_bytes()
            files.present = False
        entered = []
        cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'], lambda b: entered.append(b.get_reg('pc')) or False)
        exception = None
        try:
            cam.open_menu()
        except Exception as error:
            exception = str(error)
        state, flags = cam.h.u(H.R + 5, 1), cam.h.u(H.R + 212)
        count = cam.h.u(0x2022f5ac, 1)
        serial = cam.h.u(H.R + offsets['entry_serial'])
        if expectation == 'ready':
            assert exception is None and state == 3 and count == 8 and flags & 128, (name, exception, state, count, flags)
            assert entered and serial > 0
            block = cam.h.u(H.R + offsets['block'])
            caps = cam.h.u(block + layout['RvSession']['offsets']['capabilities'])
            assert caps & (1 << 20), (name, caps)
        else:
            assert state == 6 and count == 7 and flags & 1 and not flags & 128, (name, state, count, flags)
            assert cam.h.u(0x2022f5a8) == 0x2022d610
            if expectation in ('reject', 'IROM'):
                assert not entered and serial == 0, (name, entered, serial)
        row = dict(name=name, status='PASS', body_sha256=sha(H.BODY), dat_sha256=sha(dat),
                   generation=int.from_bytes(dat.read_bytes()[28:32], 'big'), root_state=state,
                   flags=hex(flags), rows=count, DAT_entries=len(entered), entry_serial=serial,
                   expectation=expectation, reader_exception=exception, seconds=time.monotonic()-started)
        rows.append(row)
        print(json.dumps(row), flush=True)
    (HERE / 'evidence/cross-checks.json').write_text(json.dumps(dict(status='PASS', cases=rows), indent=2) + '\n')


if __name__ == '__main__':
    main()
