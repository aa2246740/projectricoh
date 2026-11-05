"""Exercise the real import validation boundary without writing application data."""
from pathlib import Path
from dataclasses import asdict, replace
import hashlib
import json
import struct

from gxr_studio.camdata import datcodec as dc
from gxr_studio.camdata.intake import IntakeError, inspect_dat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def seal(data):
    output = bytearray(data)
    struct.pack_into('>I',output,24,dc.crc(output[256:]))
    struct.pack_into('>I',output,20,0)
    struct.pack_into('>I',output,20,dc.crc(output[:256]))
    return bytes(output)


def main():
    assert Path(dc.__file__).resolve() == Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec/src/gxr_studio/camdata/datcodec.py')
    rows = []
    for package in ('g156','g156_test','g155c','g155c_test'):
        raw = (ROOT/f'firmware/package_v310_{package}/GXRCE.DAT').read_bytes()
        rows.append(dict(case=package,accepted=asdict(inspect_dat(raw))))
        for kind, offset in (('header_crc',40),('body_crc',5000)):
            damaged = bytearray(raw); damaged[offset] ^= 1
            try:
                inspect_dat(bytes(damaged))
            except IntakeError as error:
                assert error.status == 422 and error.code == 'dat_invalid'
                rows.append(dict(case=package+'-'+kind,rejected=error.code))
            else:
                raise AssertionError('CRC corruption accepted')
        if not package.startswith('g155c'):
            continue
        changed = bytearray(raw)
        struct.pack_into('>I',changed,28,156)
        changed = seal(changed)
        info = inspect_dat(changed)
        assert info.generation == 156
        rows.append(dict(case=package+'-only-header156',accepted=asdict(info),
                         embedded_engine_still_g155c=True))
        dat = dc.parse(raw)
        name = 'g156_test' if package.endswith('_test') else 'g156'
        new_raw = (ROOT/f'firmware/package_v310_{name}/GXRCE.DAT').read_bytes()
        new_dat = dc.parse(new_raw)
        hybrid = dc.pack(replace(dat,generation=156,engine=new_dat.engine,
                                relocations=new_dat.relocations,entry=new_dat.entry,bss=new_dat.bss))
        rows.append(dict(case=package+'-with-g156-engine',accepted=asdict(inspect_dat(hybrid)),
                         engine_linked_bss_start=len(new_raw),output_bss_start=len(hybrid)))
    result = dict(layer='Unmodified camdata.intake.inspect_dat; no API/storage writes',rows=rows)
    (HERE/'evidence/intake-audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(cases=len(rows),malformed_mixed_accepted=4,crc_corruption_rejected=8)))


if __name__ == '__main__':
    main()
