"""Dispatch one bounded verification job; use a fresh --name for every run."""
from pathlib import Path
import runpy
import sys

HERE=Path(__file__).resolve().parent
COMMANDS={'cold':'cold.py','native':'native_from_cold.py','unit':'unit_checks.py',
          'c120-static':'c120_static.py','c120-unit':'mount_c120_native.py'}


def main():
    if len(sys.argv)<2 or sys.argv[1] not in COMMANDS:
        raise SystemExit('usage: verify.py {'+'|'.join(COMMANDS)+'} [job options]')
    command=sys.argv.pop(1)
    runpy.run_path(str(HERE/'local'/COMMANDS[command]),run_name='__main__')


if __name__=='__main__':main()
