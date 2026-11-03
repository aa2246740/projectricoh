#!/usr/bin/env python3
"""In-memory check that the A entry is a legal g139 user record on all three units; no file is written."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import entries as E
from fit_user import V1

MANIFEST = Path(__file__).resolve().parent / 'user_entry_GR-BB.txt'


def main():
    ue = rt.module('bleach_g139_user_entries', rt.ROOT / 'firmware/engine_v56_g139/candidate/user_entries.py')
    raw = E.DAT.read_bytes()
    assert rt.sha(E.DAT) == E.DAT_SHA
    users = ue.gxui.read_manifest(MANIFEST.read_text())
    out = ue.replace(raw, users)          # bytes only; nothing is written
    _, generation, parsed = ue.parse(out)
    v1 = rt.read('user/v1_base02.json')['full']['levels']
    assert users[0]['base'] == 2 and users[0]['levels'][:4] == [v1['Cont'], v1['High'], v1['Shad'], v1['Satu']]
    assert not any(users[0]['levels'][4:])
    # Same knob request and derived entry on every unit; 28mm equals 50mm when the base keeps its own matrix.
    mods, data = E.parse(), E.table()
    derived = []
    for unit in range(3):
        req = E.request(data, unit, 2, {c: v1[V1[c]] for c in V1})
        derived.append(E.apply(mods[unit]['entries'][4], mods[unit]['entries'][2], req))
    result = dict(manifest=MANIFEST.name, generation=generation, record=parsed, name=parsed[0]['name'],
        changed_bytes=sum(a != b for a, b in zip(raw, out)), dat_sha256=E.DAT_SHA,
        derived_entry_sha256={E.UNITS[u]: rt.hashlib.sha256(derived[u]).hexdigest() for u in range(3)},
        derived_28mm_equals_50mm=derived[0] == derived[1], file_written=False)
    rt.dump('user/entry_check.json', result)
    print(result['name'], result['changed_bytes'], result['derived_28mm_equals_50mm'], flush=True)


if __name__ == '__main__':
    main()
