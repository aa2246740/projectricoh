#!/usr/bin/env python3
"""Reproduce all analyses from local inputs; downloads are a separate optional step."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    original = json.loads((HERE / 'protected_inputs_before.json').read_text())
    for name, expected in original.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, f'Input snapshot changed: {name}'
    logs = []
    for name in ['fetch_references.py', 'firmware_trace.py', 'analyze_capture.py',
                 'reference_analysis.py', 'project_targets.py', 'write_report.py', 'verify.py']:
        # The fetcher is cache-only when the checked-in reference files exist.
        # Refuse an implicit download in this offline entrypoint.
        if name == 'fetch_references.py':
            for manifest_name in ['reference_manifest.json', 'darktable_source_manifest.json']:
                for record in json.loads((HERE / manifest_name).read_text()):
                    p = HERE / record['local']
                    assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == record['sha256'], p
        result = subprocess.run([sys.executable, '-I', str(HERE / name)], cwd=ROOT,
                                capture_output=True, text=True)
        logs.append(f'$ python3 -I research/color_calibration/{name}\n{result.stdout}{result.stderr}')
        print(result.stdout, end='', flush=True)
        if result.returncode:
            (HERE / 'reproduction_log.txt').write_text('\n'.join(logs))
            print(result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode)
    (HERE / 'reproduction_log.txt').write_text('\n'.join(logs))


if __name__ == '__main__':
    main()
