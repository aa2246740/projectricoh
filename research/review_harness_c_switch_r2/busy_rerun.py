from pathlib import Path
import difflib
import hashlib
import json
import os
import resource
import subprocess
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_harness_c_switch_r2')
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2')


def main():
    base = OUT / 'busy'
    base.mkdir(exist_ok=False)
    records, copies = [], []
    for side in ['python', 'c']:
        folder = base / side
        (folder / 'tests').mkdir(parents=True)
        for name in ('input_trace.py','input_trace_strict.py'):
            (folder/name).write_text((OUT/'entry/run'/name).read_text())
        for source, relative, replacements in [
            (ROOT / 'research/review_g139/independent_checks.py', 'independent_checks.py',
             [('ROOT = HERE.parents[1]', 'ROOT = Path(' + repr(str(ROOT)) + ')')]),
            (ROOT / 'research/review_g139/tests/g139_host.py', 'tests/g139_host.py',
             [('ROOT = Path(__file__).resolve().parents[3]', 'ROOT = Path(' + repr(str(ROOT)) + ')')]),
            (ROOT / 'research/review_g139/tests/g139_check.py', 'tests/g139_check.py', []),
            (OUT / 'entry/run/backend_select.py', 'backend_select.py',
             [('ROOT = Path(__file__).resolve().parents[4]', 'ROOT = Path(' + repr(str(ROOT)) + ')'),
              ("ROOT / 'tools/speedlab/host_regression_r4/run/local/decode'", 'Path(' + repr(str(folder / 'decode')) + ')')]),
        ]:
            original = source.read_text()
            text = original.replace("from input_trace import InputTrace", "from input_trace_strict import InputTrace")
            for before, after in replacements:
                assert text.count(before) == 1
                text = text.replace(before, after)
            target = folder / relative
            target.write_text(text)
            compile(text, str(target), 'exec')
            copies.append({'source': str(source.relative_to(ROOT)), 'copy': str(target.relative_to(ROOT)),
                           'source_sha256': hashlib.sha256(original.encode()).hexdigest(),
                           'copy_sha256': hashlib.sha256(text.encode()).hexdigest(),
                           'diff': ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True)))})
        launcher = folder / 'launch.py'
        launcher.write_text('''from pathlib import Path
import json,runpy,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from backend_select import install
install()
import python_backend as backend
(HERE/'metadata.json').write_text(json.dumps({'class_module':backend.PythonBackend.__module__,'class_name':backend.PythonBackend.__name__,'source':backend.__file__})+'\\n')
sys.argv=[str(HERE/'independent_checks.py'),'busy-settings-exit','--unit','50mm']
runpy.run_path(sys.argv[0],run_name='__main__')
''')
        env = dict(os.environ, TMPDIR=str(TMP / ('busy-' + side)),
                   GXR_HARNESS_BACKEND=side, GXR_HARNESS_UI_AUDIT='1',
                   GXR_HOST_METRICS_DIR=str(folder / 'metrics'), REVIEW_JOB='busy-settings-exit',
                   G139_PACKAGE='firmware/package_v38_g139', G139_ENGINE='firmware/engine_v56_g139')
        env.pop('GXR_CCORE_BUILD_MANIFEST', None)
        env['GXR_INPUT_RECEIPT_DIR']=str(folder/'inputs')
        env['GXR_INPUT_EXCLUDE_WORK']=str(folder/'local')
        Path(env['TMPDIR']).mkdir(parents=True)
        command = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'fence.sb'),
                   '/usr/bin/python3', '-I', '-B', str(launcher)]
        started = time.monotonic()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        print(json.dumps({'event': 'start', 'side': side, 'command': command}), flush=True)
        with (folder / 'raw.log').open('wb') as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=10800)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record = {'side': side, 'command': command, 'returncode': result.returncode,
                  'wall_seconds': time.monotonic() - started,
                  'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                  'timeout_seconds': 10800, 'load_end': os.getloadavg()}
        records.append(record)
        (base / 'progress.json').write_text(json.dumps(records, indent=2) + '\n')
        print(json.dumps(record), flush=True)
    (base / 'complete.json').write_text(json.dumps(records, indent=2) + '\n')
    (OUT / 'evidence/copied-busy.json').write_text(json.dumps(copies, indent=2) + '\n')


if __name__ == '__main__':
    main()
