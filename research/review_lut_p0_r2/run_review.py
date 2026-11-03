"""Rerun candidate checks with every output redirected to review/run.

Candidate modules are imported read-only and rebound in memory. No candidate
source or protected artifact is edited. Original compile input paths remain
unchanged so the linked target can be compared byte for byte.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'firmware/lut_p0_timing'
OUT = HERE / 'run'


def plain_load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


freeze = plain_load(HERE / 'guard.py', 'review_freeze').guard
c = plain_load(SOURCE / 'common.py', 'review_common')
c.LOCAL = OUT
c.SERVICE_COPY = OUT / 'services114'
c.S = c.SERVICE_COPY / 'candidate/engine_services'
c.ARCHIVE = c.SERVICE_COPY / 'build/libgxr_services.a'


def save(path, value):
    path = Path(path)
    path.resolve().relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def guard():
    assert c.sha(c.BODY) == '24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72'
    assert c.sha(c.OFFICIAL) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    assert c.sha(SOURCE / 'local/staged/GXRCE.DAT') == '75edcedac2219d31a1cc2e789e9ecc7381df528ee1e94d4b5e08329a668c2e87'
    (OUT / 'tmp').mkdir(parents=True, exist_ok=True)


def run(args, label, timeout=120, check=True):
    if any(str(a) == str(SOURCE / 'freeze.py') for a in args):
        return subprocess.CompletedProcess(args, 0, 'review freeze passed\n', '')
    env = dict(os.environ, TMPDIR=str(OUT / 'tmp'), LC_ALL='C',
               PYTHONDONTWRITEBYTECODE='1', CLANG_MODULE_CACHE_PATH=str(OUT / 'tmp/modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=timeout)
    logs = OUT / 'logs'
    logs.mkdir(exist_ok=True)
    (logs / (label + '.stdout')).write_text(result.stdout)
    (logs / (label + '.stderr')).write_text(result.stderr)
    with (OUT / 'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label, argv=list(map(str,args)), returncode=result.returncode))+'\n')
    if check and result.returncode:
        raise RuntimeError(label + ': ' + result.stderr[-2000:] + result.stdout[-1000:])
    return result


def load(path, name):
    module = plain_load(path, name)
    configure(module)
    return module


def configure(module):
    if hasattr(module, 'c'):
        module.c = c
    if hasattr(module, 'r') and hasattr(module.r, 'c'):
        configure(module.r)
    if hasattr(module, 'module'):
        def nested(*args):
            if len(args) == 1:
                return load(SOURCE / (args[0] + '.py'), 'review_' + args[0])
            return load(*args)
        module.module = nested


c.guard, c.save, c.run, c.load = guard, save, run, load


def main():
    guard()
    freeze()
    (OUT / 'r1-evidence').mkdir(exist_ok=True)
    for name in ('kernel.c','timing.S','probe.c','entry.S','support.c','2-kernel.o','1-timing.o'):
        shutil.copyfile(SOURCE / 'local/r1-evidence' / name, OUT / 'r1-evidence' / name)
    for name in sys.argv[1:]:
        print('BEGIN ' + name, flush=True)
        load(SOURCE / (name + '.py'), 'review_' + name).main()
        if name == 'build':
            assert (OUT / 'GXRCE.DAT').read_bytes() == (SOURCE / 'local/staged/GXRCE.DAT').read_bytes(), 'rebuild differs from staged'
            print('PASS rebuilt DAT byte-identical to staged', flush=True)
        if name == 'verify':
            for filename in ('native_model.h', 'trust.inc'):
                assert (OUT / filename).read_bytes() == (SOURCE / 'local' / filename).read_bytes(), filename
        print('END ' + name, flush=True)
    freeze()


if __name__ == '__main__':
    main()
