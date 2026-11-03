"""Run the complete host-only calibration and acceptance in serial."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import subprocess
import support as s


def main():
    s.guard()
    import prepare
    prepare.main()
    for name in ('calibrate', 'cap_evidence', 'export_tables', 'comparisons', 'domain_parity', 'verify', 'previews'):
        command = ['/usr/bin/python3', '-I', '-B', str(s.HERE/'src'/f'{name}.py')]
        with (s.LOCAL/f'{name}.log').open('w') as log:
            cp = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        print(name, 'exit', cp.returncode, flush=True)
        if cp.returncode:
            raise SystemExit(cp.returncode)
    subprocess.run(['/usr/bin/python3', '-I', '-B', str(s.HERE/'src/finalize.py')], check=True)


if __name__ == '__main__':
    main()
