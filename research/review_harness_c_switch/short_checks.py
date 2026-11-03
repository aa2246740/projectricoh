from pathlib import Path
import json
import os
import resource
import subprocess
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
ENTRY = OUT / 'entry'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')


def main():
    folder = OUT / 'short'
    folder.mkdir(exist_ok=False)
    records = []
    commands = [(name, [ENTRY / 'cases' / (name + '.py')]) for name in
                ['independent_cases', 'extended_cases', 'new_cases', 'trace_cases', 'mro_cases']]
    commands += [('differential', [ENTRY / 'gate_adapter.py', 'differential', '--folder', 'differential', '--repeats', '64']),
                 ('audit-boundaries', [ENTRY / 'gate_adapter.py', 'audit']),
                 ('audit-changes', [ENTRY / 'audit_changes.py']),
                 ('error-equivalence', [OUT / 'error_equivalence.py'])]
    for name, args in commands:
        env = dict(os.environ, TMPDIR=str(TMP), GXR_HARNESS_BACKEND='c',
                   GXR_HARNESS_UI_AUDIT='1',
                   GXR_CCORE_BUILD_MANIFEST=str(ROOT / 'tools/speedlab/harness_release/local/ccore/build.json'))
        for key in ['GXR_REVIEW_FIX_OUTPUT', 'GXR_GATE_OUTPUT']:
            env.pop(key, None)
        command = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'fence.sb'),
                   '/usr/bin/python3', '-I', '-B', *map(str, args)]
        start = time.monotonic()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        with (folder / (name + '.log')).open('wb') as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=3600)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record = {'case': name, 'returncode': result.returncode,
                  'wall_seconds': time.monotonic() - start,
                  'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                  'command': command}
        records.append(record)
        (folder / 'progress.json').write_text(json.dumps(records, indent=2) + '\n')
        print(json.dumps(record), flush=True)
    (folder / 'complete.json').write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
