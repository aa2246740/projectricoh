from pathlib import Path
import hashlib
import json
import os
import subprocess
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')
ENTRY = OUT / 'entry'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    normal = json.loads((ROOT / 'tools/speedlab/harness_release/local/ccore/build.json').read_text())
    results = []
    for label, flag, script in [
        ('audit-hit-omitted', 'GXR_TEST_DROP_AUDIT_HIT', [ENTRY / 'gate_adapter.py', 'audit']),
        ('method-guard-omitted', 'GXR_TEST_SKIP_METHOD_GUARD', [ENTRY / 'cases/new_cases.py']),
    ]:
        folder = ENTRY / 'local/gates/mutations' / label
        folder.mkdir(parents=True, exist_ok=False)
        library = folder / Path(normal['library']).name
        command = list(normal['command'])
        command.insert(1, '-D' + flag + '=1')
        command[-1] = str(library)
        started = time.monotonic()
        built = subprocess.run(command, cwd=ROOT, env=dict(os.environ, TMPDIR=str(TMP)), capture_output=True, timeout=3600)
        (folder / 'build.log').write_bytes(built.stdout + built.stderr)
        if built.returncode:
            raise RuntimeError('Control library failed to build')
        record = dict(normal, library=str(library), sha256=sha(library), command=command)
        manifest = folder / 'build.json'
        manifest.write_text(json.dumps(record, indent=2) + '\n')
        env = dict(os.environ, TMPDIR=str(TMP), GXR_HARNESS_BACKEND='c', GXR_HARNESS_UI_AUDIT='1',
                   GXR_CCORE_BUILD_MANIFEST=str(manifest), GXR_GATE_OUTPUT=str(folder),
                   GXR_REVIEW_FIX_OUTPUT=str(folder / 'cases'))
        command = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'fence.sb'),
                   '/usr/bin/python3', '-I', '-B', *map(str, script)]
        with (folder / 'run.log').open('wb') as stream:
            run = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
        if label == 'audit-hit-omitted':
            summary = json.loads((folder / 'round2/audit-checks/summary.json').read_text())
            detected = run.returncode != 0 and summary['passed'] is False
            mismatch_count = sum(not row['passed'] for row in summary['checks'])
        else:
            summary = json.loads((folder / 'cases/local/new-summary.json').read_text())
            detected = summary['mismatches'] == 2
            mismatch_count = summary['mismatches']
        result = {'case': label, 'detected': detected, 'mismatches': mismatch_count,
                  'returncode': run.returncode, 'library_sha256': record['sha256'],
                  'wall_seconds': time.monotonic() - started, 'command': command}
        results.append(result)
        print(json.dumps(result), flush=True)
    (OUT / 'evidence/mutations.json').write_text(json.dumps({'passed': all(r['detected'] for r in results), 'checks': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()
