"""Run the original checks with output paths confined to this review."""
from pathlib import Path
import hashlib
import importlib.abc
import importlib.util
import json
import os
import sys
import time
import traceback

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/verify_g152'
SOURCE = ROOT / 'research/looks_g152'
WORK = OUT / 'runtime'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/verify-g152')
MODULES = {
    'native_support', 'dat_format', 'format_checks', 'math_reference',
    'equivalence', 'control_parity', 'apply_checks', 'lock_checks',
    'unverified_checks', 'native_reject', 'ui_checks', 'identity_checks',
    'regressions', 't0_checks', 't0_late_checks', 'knob_checks',
}
REBINDS = []


class ReviewLoader(importlib.abc.Loader):
    def __init__(self, path):
        self.path = path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        original = self.path.read_text()
        text = original.replace("HERE=Path(__file__).resolve().parent", f"HERE=Path({str(WORK)!r})")
        text = text.replace('ROOT=HERE.parents[1]', f'ROOT=Path({str(ROOT)!r})')
        text = text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/g152', str(TMP))
        for name in ('legacy/', 'layout.json', 'host_equivalence.c'):
            text = text.replace("HERE/'" + name, "Path(" + repr(str(SOURCE)) + ")/'" + name)
        REBINDS.append(dict(source=str(self.path.relative_to(ROOT)),
                            source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                            executed_sha256=hashlib.sha256(text.encode()).hexdigest()))
        module.__file__ = str(self.path)
        exec(compile(text, str(self.path), 'exec'), module.__dict__)


class ReviewFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in MODULES:
            source = SOURCE / (fullname + '.py')
            return importlib.util.spec_from_loader(fullname, ReviewLoader(source), origin=str(source))
        return None


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    name = sys.argv[1]
    arguments = sys.argv[2:]
    assert name in MODULES or name == 'independent_cases'
    job = name + '-' + str(os.getpid())
    (WORK / 'evidence').mkdir(parents=True, exist_ok=True)
    (WORK / 'local/variants').mkdir(parents=True, exist_ok=True)
    (OUT / 'runs').mkdir(exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1', REVIEW_JOB=job,
                      CLANG_MODULE_CACHE_PATH=str(TMP / 'clang-cache'))
    sys.dont_write_bytecode = True
    sys.meta_path.insert(0, ReviewFinder())
    sys.path.insert(0, str(OUT))
    sys.argv = [str(SOURCE / (name + '.py')), *arguments]
    result = dict(module=name, args=arguments, started_ns=time.time_ns(), nice=os.getpriority(os.PRIO_PROCESS, 0),
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if name=='independent_cases':
        result['case_source_sha256']=hashlib.sha256((OUT/'independent_cases.py').read_bytes()).hexdigest()
    tick = time.monotonic()
    try:
        module = __import__(name)
        module.main()
        result['status'] = 'PASS'
    except BaseException:
        result.update(status='FAIL', error=traceback.format_exc())
        raise
    finally:
        result.update(seconds=time.monotonic()-tick, ended_ns=time.time_ns(), source_rebinds=REBINDS)
        (OUT / 'runs' / (job + '.json')).write_text(json.dumps(result, indent=2)+'\n')
        print('REVIEW_RUN', json.dumps({k:v for k,v in result.items() if k != 'source_rebinds'}), flush=True)


if __name__ == '__main__':
    main()
