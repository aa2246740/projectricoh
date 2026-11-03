"""Repeatable compile/link-only compiler comparison. No image or DAT output.

Each profile retains its ELF, map, command return codes, and byte account under
local/r2-sweep. All obligations and budget reservations in build.py remain.
Run from repository root with /usr/bin/python3 -I -B.
"""
from pathlib import Path
import importlib.util
import json

HERE = Path(__file__).resolve().parent
PROFILES = {
    'os': [],
    'os-no-inline-once': ['-fno-inline-functions-called-once'],
    'os-no-inline': ['-fno-inline'],
    'oz': ['-Oz'],
    'oz-no-inline-once': ['-Oz', '-fno-inline-functions-called-once'],
}


def main():
    rows = []
    for name, extra in PROFILES.items():
        spec = importlib.util.spec_from_file_location('rv4_sweep_' + name, HERE / 'build.py')
        b = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(b)
        b.LOCAL = HERE / 'local/r2-sweep' / name
        b.REPORT = b.ROOT / 'research/body_v4_w0/local/r2-sweep' / name
        b.LOCAL.mkdir(parents=True, exist_ok=True)
        b.REPORT.mkdir(parents=True, exist_ok=True)
        b.commands = []
        b.FLAGS = [*b.FLAGS, *extra]
        b.main()
        result = json.loads((b.REPORT / 'size.json').read_text())
        rows.append(dict(profile=name, extra=extra, payload_bytes=result['payload_bytes'],
                         margin_after_reserve=result['margin_after_reserve'],
                         strict_link_returncode=result['strict_link_returncode'],
                         safety_reservations_unchanged=True,
                         evidence=str((b.REPORT / 'size.json').relative_to(b.ROOT))))
    output = b.ROOT / 'research/body_v4_w0/compiler-sweep.json'
    b.write(output, rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
