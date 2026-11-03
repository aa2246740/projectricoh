"""Run review commands with temporary files and every log inside this folder."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CAND = OUT / 'isolated/candidate'
LOG = OUT / 'command-logs'
LOG.mkdir(exist_ok=True)
env = dict(os.environ, TMPDIR=str(CAND / 'local/tmp'), LC_ALL='C',
           PYTHONDONTWRITEBYTECODE='1', CLANG_MODULE_CACHE_PATH=str(CAND / 'local/tmp/modules'),
           ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
           GIT_OPTIONAL_LOCKS='0')


def run(name, args, timeout=1800):
    start = time.monotonic()
    p = subprocess.run([str(x) for x in args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    (LOG / (name + '.stdout')).write_text(p.stdout)
    (LOG / (name + '.stderr')).write_text(p.stderr)
    row = dict(name=name, argv=[str(x) for x in args], returncode=p.returncode,
               seconds=round(time.monotonic() - start, 3))
    with (OUT / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(row) + '\n')
    print(name, 'exit', p.returncode, p.stdout[-14000:], p.stderr[-4000:], flush=True)
    return p.returncode


def main():
    phase = sys.argv[1]
    if phase == 'build':
        result = run('build117', ['/usr/bin/python3', '-I', '-B', CAND / 'build117.py'])
        if not result:
            produced = CAND / 'local/full-r13/GXRCE.DAT'
            staged = ROOT / 'firmware/package_v35_g117/SD_ROOT/GXRCE.DAT'
            assert produced.read_bytes() == staged.read_bytes()
            print('PASS byte-identical independent rebuild')
    elif phase == 'compile':
        result = run('host-compile', ['/usr/bin/python3', '-I', '-B', CAND / 'verify_v34c.py', 'compile'])
    elif phase == 'host':
        result = run('host-stages', ['/usr/bin/python3', '-I', '-B', OUT / 'run_host117.py'])
    elif phase == 'native':
        result = 0
        for label, path in [('conformance', OUT / 'native_harness/conformance.py'),
                            ('native-scenarios', OUT / 'native_harness/scenarios.py'),
                            ('native-gen117', OUT / 'run_v35_g117.py')]:
            result |= run(label, ['/usr/bin/python3', '-I', '-B', path])
    else:
        raise SystemExit('unknown phase')
    raise SystemExit(result)


if __name__ == '__main__':
    main()
