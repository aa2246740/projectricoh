from pathlib import Path
import hashlib
import json
import os
import subprocess
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')
NORMAL = ROOT / 'tools/speedlab/harness_release/local/ccore/build.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = OUT / 'switch'
    base.mkdir(exist_ok=False)
    records = []

    def run(label, source='release', selection=None, manifest=None, expected_error=None):
        env = dict(os.environ, TMPDIR=str(TMP))
        for key in list(env):
            if key.startswith('GXR_HARNESS_') or key == 'GXR_CCORE_BUILD_MANIFEST':
                env.pop(key)
        if selection is not None:
            env['GXR_HARNESS_BACKEND'] = selection
        if manifest is not None:
            env['GXR_CCORE_BUILD_MANIFEST'] = str(manifest)
        command = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'fence.sb'),
                   '/usr/bin/python3', '-I', '-B', str(OUT / 'probe.py'),
                   '--source', source, '--output', str(base / label)]
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=1800)
        (base / (label + '.stdout')).write_bytes(result.stdout)
        (base / (label + '.stderr')).write_bytes(result.stderr)
        passed = ((result.returncode == 0) if expected_error is None else
                  (result.returncode != 0 and expected_error.encode() in result.stderr))
        row = {'case': label, 'passed': passed, 'returncode': result.returncode,
               'wall_seconds': time.monotonic() - started, 'command': command,
               'selection': selection, 'manifest': str(manifest) if manifest else None,
               'expected_error': expected_error}
        records.append(row)
        print(json.dumps(row), flush=True)

    absent = TMP / 'missing-build.json'
    run('original-default', source='original')
    run('release-default')
    run('release-python', selection='python')
    run('default-with-missing-manifest', manifest=absent)
    run('explicit-python-with-missing-manifest', selection='python', manifest=absent)
    run('explicit-c', selection='c')
    run('missing-manifest', selection='c', manifest=absent, expected_error='C core is not built')
    build = json.loads(NORMAL.read_text())
    for label, changes, message in [
        ('missing-library', {'library': str(TMP / 'absent-library.so')}, 'FileNotFoundError'),
        ('wrong-abi', {'python': build['python'] + ' changed'}, 'C core Python ABI or host architecture differs'),
        ('wrong-library-hash', {'sha256': '0' * 64}, 'C core library identity differs'),
        ('wrong-source-hash', {'sources': {str(ROOT / 'tools/speedlab/harness_release/python_backend.py'): '0' * 64}}, 'C core source identity changed'),
    ]:
        altered = dict(build, **changes)
        manifest = TMP / (label + '.json')
        manifest.write_text(json.dumps(altered, indent=2) + '\n')
        run(label, selection='c', manifest=manifest, expected_error=message)
    code = ROOT / 'tools/speedlab/harness_release/ccore/core.c'
    original = code.read_text()
    needle = 'PyModule_AddIntConstant(module,"API_VERSION",5)'
    assert original.count(needle) == 1
    version_source = TMP / 'version4-core.c'
    version_source.write_text(original.replace(needle, 'PyModule_AddIntConstant(module,"API_VERSION",4)'))
    library = TMP / Path(build['library']).name
    command = [str(version_source) if item == str(code) else item for item in build['command']]
    command[-1] = str(library)
    command[1:1] = ['-I', str(code.parent)]
    compiled = subprocess.run(command, cwd=ROOT, env=dict(os.environ, TMPDIR=str(TMP)), capture_output=True, timeout=3600)
    (base / 'version4-build.log').write_bytes(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise RuntimeError('Version control library did not build')
    altered = dict(build, library=str(library), sha256=sha(library), command=command)
    altered['sources'] = dict(build['sources'], **{str(version_source): sha(version_source)})
    manifest = TMP / 'version4-build.json'
    manifest.write_text(json.dumps(altered, indent=2) + '\n')
    (base / 'version4-build.json').write_text(json.dumps(altered, indent=2) + '\n')
    run('wrong-api', selection='c', manifest=manifest, expected_error='C core API differs')
    samples = ['original-default', 'release-default', 'release-python', 'default-with-missing-manifest', 'explicit-python-with-missing-manifest', 'explicit-c']
    expected = (base / 'original-default/acceptance.json').read_bytes()
    byte_equality = {name: (base / name / 'acceptance.json').read_bytes() == expected for name in samples}
    core_not_loaded = {name: not json.loads((base / name / 'metadata.json').read_text())['native_loaded'] for name in samples[:-1]}
    result = {'passed': all(row['passed'] for row in records) and all(byte_equality.values()) and all(core_not_loaded.values()),
              'checks': records, 'acceptance_byte_equality': byte_equality, 'default_native_not_loaded': core_not_loaded}
    (base / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
