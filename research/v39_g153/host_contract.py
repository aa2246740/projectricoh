"""Run all twelve existing v3.9 host contracts against the g153 sources."""
from pathlib import Path
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ENGINE = ROOT / 'firmware/engine_v62_g153'


def main():
    tmp = Path(os.environ['TMPDIR']) / 'contract'
    tmp.mkdir()
    sources = [ROOT / 'research/body_v39/tests/host_v39.c']
    sources += [ENGINE / 'resident' / (name + '.c') for name in ('resident', 'shared', 'hooks', 'loader', 'validate_envelope.inc')]
    sources += [ENGINE / 'candidate/engine_services' / (name + '.c') for name in ('services', 'api', 'native_seed')]
    command = ['/usr/bin/clang', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Wno-unused-function',
               '-Wno-unused-parameter', '-D_FORTIFY_SOURCE=0', '-U__OPTIMIZE__',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-DRV_HOST',
               '-I'+str(ENGINE / 'resident'), '-I'+str(ENGINE / 'candidate/engine_services'),
               *map(str, sources), '-o', str(tmp / 'host_v39')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    (HERE / 'evidence/host-contract-build.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    rows = []
    for name in ('caps', 'handshake', 'disabled', 'epochs', 'h09', 'h10', 'image', 'restore', 'lane', 'check', 'header', 'discard'):
        result = subprocess.run([str(tmp / 'host_v39'), name], text=True, capture_output=True, timeout=600,
            env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                     UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
        assert not result.returncode, (name, result.stdout, result.stderr)
        rows += [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    (HERE / 'evidence/host-contract.json').write_text(json.dumps(dict(status='PASS', groups=12, rows=rows), indent=2) + '\n')
    print(json.dumps(dict(status='PASS', groups=12, observations=len(rows))))


if __name__ == '__main__':
    main()
