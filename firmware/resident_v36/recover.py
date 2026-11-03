"""Rerun the interrupted delivery from source, retaining separate recovery logs."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local/recovery'
PYTHON = '/usr/bin/python3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(label, script, *args):
    command = [PYTHON, '-I', '-B', str(ROOT / script), *map(str, args)]
    env = dict(os.environ, TMPDIR=str(OUT / 'tmp'), PYTHONDONTWRITEBYTECODE='1',
               GIT_OPTIONAL_LOCKS='0')
    (OUT / 'tmp').mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (OUT / (label + '.log')).write_text(result.stdout + result.stderr)
    with (OUT / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(label=label, argv=command, returncode=result.returncode)) + '\n')
    print(label, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
    if result.returncode:
        print((result.stdout + result.stderr)[-5000:], flush=True)
        raise SystemExit(result.returncode)


def initial():
    assert not (OUT / 'initial.json').exists(), 'Never replace the recovery baseline'
    spec = importlib.util.spec_from_file_location('freeze', HERE / 'prepare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.guard()
    files = {}
    package = ROOT / 'firmware/image_v33/local/package'
    for path in sorted(package.rglob('*')):
        if path.is_file():
            files[str(path.relative_to(ROOT))] = sha(path)
    inputs = ROOT / 'research/bw03_standard_mode'
    frozen = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs.rglob('*'))
              if path.is_file() and path.name != 'decisions.tsv' and '__pycache__' not in path.parts}
    save('initial.json', dict(previous_package=files, additional_frozen=frozen,
         resident_elf=sha(HERE / 'local/resident/build/resident.elf'),
         full_r8=sha(HERE / 'acceptance/local/full-r8/GXRCE.DAT')))
    print('Recovery baseline saved; original inventory already checked: 24645 files', flush=True)


def resident():
    run('resident-build', 'firmware/resident_v34c/build.py')
    run('resident-verify', 'firmware/resident_v34c/verify.py')
    run('entry-machine', 'firmware/resident_v34c/entry_machine.py')


def r8():
    for phase in ('prepare', 'compile', 'static', 'legacy', 'historical', 'behavior', 'faults',
                  'additional', 'reviewer', 'boundary', 'policy', 'upgrade', 'first-frame', 'actual-upgrade','actual-pair'):
        run('r8-' + phase, 'firmware/resident_v34c/acceptance/run.py', phase)
    run('stack-r8', 'firmware/resident_v34c/stack_r8.py')


def image(final=False):
    common = ['--elf', HERE / 'local/resident/build/resident.elf',
              '--hooks', HERE / 'local/hooks.json',
              '--patch-manifest', HERE / 'local/resident/patch-manifest.json']
    package = ROOT / ('firmware/image_v33/local/reproduced-final-v33' if final else 'firmware/image_v33/local/reproduced-v33')
    label='final-' if final else ''
    official = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
    run(label+'image-build', 'firmware/image_v33/build.py', '--official', official,
        *common, '--output', package)
    run(label+'image-audit', 'firmware/image_v33/audit.py', '--package', package,
        '--official', official, *common, '--verbose')
    run(label+'image-verify', 'firmware/image_v33/verify.py', '--package', package,
        *common, '--output', ROOT / ('firmware/image_v33/local/verification-final' if final else 'firmware/image_v33/local/verification-reproduced'))
    initial = json.loads((OUT / 'initial.json').read_text())
    actual = sha(package / 'candidate/SD_ROOT/ilaunch3')
    if not final:
        assert actual == initial['previous_package']['firmware/image_v33/local/package/SD_ROOT/ilaunch3']
        assert actual == 'b0473d003badf0713ae50d8d474023578d64d589574a768b8c975e7b802ab950'
    save(label+'image-reproduction.json', dict(status='PASS', sha256=actual, staged_equal=not final))


def r9(start='prepare'):
    phases=('prepare','compile','static','legacy','historical','behavior','faults','additional',
            'reviewer','boundary','policy','upgrade','first-frame','actual-upgrade','actual-pair','power','migration')
    assert start in phases
    for phase in phases[phases.index(start):]:
        run('r9-'+phase,'firmware/resident_v34c/acceptance/run_r9.py',phase)


def check():
    initial = json.loads((OUT / 'initial.json').read_text())
    for group in ('previous_package', 'additional_frozen'):
        for name, digest in initial[group].items():
            assert sha(ROOT / name) == digest, 'STOP_PROTECTED_INPUT_CHANGED: ' + name
    spec = importlib.util.spec_from_file_location('freeze', HERE / 'prepare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    count = module.check()
    save('protected-check.json', dict(status='PASS', original_inputs=count,
        additional_inputs=len(initial['additional_frozen']),
        earlier_package_files=len(initial['previous_package'])))
    print('PASS protected inputs and earlier full-r8 package', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('initial', 'resident', 'r8', 'r9', 'image', 'image-final', 'check'))
    parser.add_argument('--from-phase')
    args=parser.parse_args()
    if args.phase=='r9':r9(args.from_phase or 'prepare')
    elif args.phase=='image-final':image(True)
    else:globals()[args.phase]()
