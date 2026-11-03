#!/usr/bin/env python3
"""Read-only: dump the GXUI v1 per-base, per-unit knob domains from a gen 137+ DAT."""
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dat', type=Path)
    a = ap.parse_args()
    ue = load('g139_user_entries', ROOT / 'firmware/engine_v56_g139/candidate/user_entries.py')
    gx = ue.gxui
    raw = a.dat.read_bytes()
    at, generation, users = ue.parse(raw)
    ext = raw[at:at + gx.EXT_BYTES]
    units = ('50mm', '28mm', 'MOUNT')
    out = dict(dat=str(a.dat), generation=generation, users=users, keys=gx.KEYS, groups=gx.GROUPS,
               name_rule='auto: GROUP + (* if any level else -) + 3-digit ordinal; not user text',
               domains={})
    for mi in range(3):
        for slot in range(1, 9):
            c = ext[64 + (mi * 8 + slot - 1) * gx.CONFIG_BYTES:][:gx.CONFIG_BYTES]
            visible = list(c[4:4 + c[2]])
            dom = {gx.KEYS[k]: struct.unpack_from('bbb', c, 15 + 3 * k) for k in range(11)}
            out['domains'][f'{units[mi]}/{slot:02d}'] = dict(
                visible=[gx.KEYS[v - 1] for v in visible],
                ranges={k: dict(lo=v[0], hi=v[1], default=v[2]) for k, v in dom.items()})
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
