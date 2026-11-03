"""Run focused host and static checks between retained target jobs."""
from pathlib import Path
import argparse
import contextlib
import io
import json
import os
import runpy
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g135_v37'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--next-index', type=int, required=True)
    parser.add_argument('--stage', choices=('host', 'target', 'gate'), default='host')
    options = parser.parse_args()
    def timed_out(number, frame):
        raise TimeoutError('stage time limit')
    signal.signal(signal.SIGALRM, timed_out)
    steps = [(name, name + '.py', []) for name in
             ('target_gate', 'host_check', 'layout', 'layout_bindings', 'check_delta')]
    if options.stage == 'target':
        steps = [('target_check-' + str(index), 'target_check.py', [
            '--state', str(WORK / 'local/checks/review_g126' / ('target-state-' + unit)),
            '--unit', str(index)]) for index, unit in enumerate(('50mm', '28mm', 'mount'))]
    if options.stage == 'gate':
        steps = [('target_gate', 'target_gate.py', [])]
    for name, filename, arguments in steps:
        started = time.monotonic()
        stream = io.StringIO()
        script = WORK / filename
        sys.argv = [str(script)] + arguments
        status = 0
        signal.alarm(7200)
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                runpy.run_path(str(script), run_name='__main__')
        except BaseException as error:
            status = 1
            (WORK / 'local' / ('stage-error-' + name + '.json')).write_text(json.dumps(dict(
                error=type(error).__name__, message=str(error)), indent=2) + '\n')
        finally:
            signal.alarm(0)
        result = dict(name=name, returncode=status, seconds=round(time.monotonic() - started, 3),
                      counts=dict(output_lines=len(stream.getvalue().splitlines())))
        with (WORK / 'evidence/stage-runs.jsonl').open('a') as output:
            output.write(json.dumps(result) + '\n')
        print(json.dumps(dict(name=name, returncode=status, counts=result['counts'])), flush=True)
        if status:
            raise SystemExit(status)
    if options.next_index >= len(json.loads(options.queue.read_text())):
        return
    os.execv('/usr/bin/python3', ['/usr/bin/python3', '-I', '-B', str(WORK / 'run_existing.py'),
        '--queue', str(options.queue.resolve()), '--job-index', str(options.next_index)])

if __name__ == '__main__':
    main()
