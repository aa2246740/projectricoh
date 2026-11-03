"""Scoped storage, frozen source inputs, commands and ELF inspection."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
UPSTREAM = LOCAL / 'upstream'
COMMANDS = []


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    if not path.resolve().is_relative_to(LOCAL.resolve()):
        raise ValueError('evidence must remain in task local/')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def preflight():
    info = plistlib.loads(subprocess.check_output(
        ['diskutil', 'info', '-plist', '/Volumes/Workspace'], timeout=10))
    assert info['MountPoint'] == '/Volumes/Workspace'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume'] and info['WritableMedia']
    assert os.access('/Volumes/Workspace', os.W_OK)
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/probes_int')
    assert not LOCAL.is_symlink() and not (LOCAL / 'tmp').is_symlink()
    ignored = subprocess.check_output(
        ['git', 'check-ignore', '-v', 'firmware/probes_int/local/check'], cwd=ROOT, text=True)
    assert 'firmware/probes_int/.gitignore:1:/local/' in ignored
    for item in json.loads((LOCAL / 'inputs.json').read_text()):
        assert sha(HERE / item['snapshot']) == item['sha256'], item['snapshot']
    save(LOCAL / 'ignore.json', {'check_ignore': ignored})
    return {k: info[k] for k in ('MountPoint', 'VolumeUUID', 'FilesystemType', 'WritableVolume')}


def run(args, label, timeout=25, check=True):
    env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C', PYTHONDONTWRITEBYTECODE='1',
               CLANG_MODULE_CACHE_PATH=str(LOCAL / 'tmp/modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    log = LOCAL / 'logs' / (label + '.log')
    log.parent.mkdir(exist_ok=True)
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env, text=True,
                            capture_output=True, timeout=timeout)
    log.write_text(result.stdout + result.stderr)
    COMMANDS.append(dict(argv=[str(a) for a in args], returncode=result.returncode,
                         log=str(log.relative_to(HERE))))
    save(LOCAL / 'commands.json', COMMANDS)
    if result.returncode:
        failures = LOCAL / 'failures'
        failures.mkdir(exist_ok=True)
        digest = hashlib.sha256((result.stdout + result.stderr).encode()).hexdigest()[:12]
        (failures / (label + '-' + digest + '.log')).write_text(result.stdout + result.stderr)
        if check:
            raise RuntimeError(f'{label}: exit {result.returncode}: {(result.stdout + result.stderr)[-1800:]}')
    return result


Elf = module(UPSTREAM / 'stage2l_switch/tools/build.py', 'pi_frozen_elf').Elf
