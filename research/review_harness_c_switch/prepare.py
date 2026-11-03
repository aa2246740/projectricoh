from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')
SOURCE = ROOT / 'tools/speedlab/host_regression_r3'
DEST = OUT / 'entry'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    DEST.mkdir(exist_ok=False)
    (DEST / 'local').mkdir()
    rows = []
    names = ['run.py', 'run_regressions.py', 'support.py', 'gate_adapter.py',
             'audit_changes.py', 'compare_products.py', 'queue.json',
             *['run/' + name for name in ['legacy_call.py', 'fixture.py',
                'users_gxui.py', 'backend_select.py', 'backend_launch.py']],
             *['cases/' + name for name in ['scope_guard.py', 'independent_cases.py',
                'extended_cases.py', 'new_cases.py', 'trace_cases.py', 'mro_cases.py']]]
    for name in names:
        source = SOURCE / name
        original = source.read_text()
        text = original
        if name == 'support.py':
            text = text.replace('ROOT=Path(__file__).resolve().parents[3]', 'ROOT=Path(' + repr(str(ROOT)) + ')')
            text = text.replace("ROOT/'tools/speedlab'", 'Path(' + repr(str(OUT)) + ')')
        if name == 'run_regressions.py':
            text = text.replace('ROOT = OUT.parents[2]', 'ROOT = Path(' + repr(str(ROOT)) + ')')
        text = text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/speed-hillclimb', str(TMP))
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        if target.suffix == '.py':
            compile(text, str(target), 'exec')
        rows.append({'source': str(source.relative_to(ROOT)), 'target': str(target.relative_to(ROOT)),
                     'source_sha256': sha(original.encode()), 'copy_sha256': sha(text.encode()),
                     'diff': ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                         fromfile=str(source), tofile=str(target)))})
    sandbox = '''(version 1)
(allow default)
(deny network*)
(deny file-write*)
(deny file-read* (regex #"^/Volumes/(?!Workspace(?:/|$))") (regex #"^/dev/r?disk"))
(allow file-write* (subpath "OUTPUT") (subpath "TEMP") (literal "/dev/null"))
(allow file-read-metadata (literal "/dev/disk7s1"))
'''.replace('OUTPUT', str(OUT)).replace('TEMP', str(TMP))
    (OUT / 'fence.sb').write_text(sandbox)
    (DEST / 'offline.sb').write_text(sandbox)
    queue = json.loads((ROOT / 'research/g150/queue-reg.json').read_text())['jobs']
    chosen = ['group126-mount-locked', 'group124+126-28mm-transitions',
              'group124+126-28mm-values', 'group126-mount-nested', 'group126-28mm-half']
    jobs = [next(j for j in queue if j['name'] == name) for name in chosen]
    (OUT / 'selected-queue.json').write_text(json.dumps({'jobs': jobs}, indent=2) + '\n')
    (OUT / 'evidence/copied-entry.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps({'copied': len(rows), 'jobs': chosen}))


if __name__ == '__main__':
    main()
