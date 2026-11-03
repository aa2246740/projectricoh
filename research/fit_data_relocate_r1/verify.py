"""Verify the relocation without running fits, rebuilding packages, or writing Git state."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / 'evidence'
FIT_DATA = ROOT / 'artifacts/downloads/vlog-alchemy-eval-20261102'
NAMES = ('all_fit_parameters.json', 'lumix_fit_parameters.json', 'look_fits.json')
EXPECTED = (
    'be5d1d91a1bc1cdb20fd96ad250637a4536879a6fba1d9e8a992b5decedcba1a',
    '69d5d90c13972f6b731a589d375b33a2511f331fb5a71fe46c2196c98bb6e392',
    '5b9caf280091ab14c78c0067eb953404a5029850c9c09395aac3ea2b0510f17d',
)
DAT_SHA = '5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681'
SCOPES = ('research/vlog_alchemy_eval', 'research/g154_looks_r1',
          'firmware/engine_v65_g154_looks', 'research/look_ceiling_r1')


def sha(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def run(argv, cwd=ROOT, valid=(0,), timeout=600):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                            env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'), timeout=timeout)
    if result.returncode not in valid:
        raise RuntimeError(f'{argv[0]} exited {result.returncode}: {result.stderr}')
    return result


def git(*args, **kwargs):
    return run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', *args], **kwargs)


def save(name, value):
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def seal_receipts():
    paths = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'
                   and p.name != '.DS_Store' and '__pycache__' not in p.parts)
    (HERE / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + str(p.relative_to(ROOT)) + '\n' for p in paths))
    return len(paths)


def support_module():
    spec = importlib.util.spec_from_file_location('relocation_support', ROOT / SCOPES[0] / 'support.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def routing_child(fixture):
    support = support_module()
    support.FIT_DATA = fixture / 'private'
    support.SCRATCH = fixture / 'scratch'
    support.setup()
    for name in NAMES:
        support.dump(name, {'relocation_fixture': True})
        assert json.loads(support.result_path(name).read_text()) == {'relocation_fixture': True}
        old = support.HERE / name
        assert not old.exists()
        try:
            old.open('w')
        except PermissionError:
            pass
        else:
            raise AssertionError('Legacy research write was not blocked: ' + name)
        assert not old.exists()
    print(json.dumps(dict(private_writes=3, legacy_writes_blocked=3)))


def expression(relative, variable):
    tree = ast.parse((ROOT / relative).read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets))
    return compile(ast.Expression(node.value), relative, 'eval')


def check_routes():
    support = support_module()
    namespace = dict(json=json, result_path=support.result_path, fresh=False)
    counts = {}
    for relative, variable, key, expected in (
        (SCOPES[0] + '/fit_candidates.py', 'result', 'fits', 27),
        (SCOPES[0] + '/fit_candidates.py', 'parameters', 'parameters', 17),
        (SCOPES[0] + '/verify_build.py', 'params', 'parameters', 4),
    ):
        value = eval(expression(relative, variable), namespace)
        assert len(value) == expected
        assert value == json.loads(support.result_path('look_fits.json' if key == 'fits' else
            'lumix_fit_parameters.json' if variable == 'params' else 'all_fit_parameters.json').read_text())[key]
        counts[variable] = len(value)
    tree = ast.parse((ROOT / SCOPES[0] / 'report.py').read_text())
    reader = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'read')
    exec(compile(ast.Module(body=[reader], type_ignores=[]), 'report.py', 'exec'), namespace)
    assert len(namespace['read']('look_fits.json')['fits']) == 27
    with tempfile.TemporaryDirectory(prefix='.relocation-check-', dir=FIT_DATA) as temporary:
        fixture = Path(temporary)
        result = run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--routing-child', str(fixture)])
        counts.update(json.loads(result.stdout))
        baseline = fixture / 'baseline'
        baseline.mkdir()
        tree = ast.parse((ROOT / SCOPES[0] / 'freeze_studio.py').read_text())
        copy = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == 'copyfile')
        after = expression(SCOPES[0] + '/compare_repeat.py', 'after')
        for name in NAMES:
            env = dict(namespace, name=name, shutil=shutil, baseline=baseline)
            eval(compile(ast.Expression(copy), 'freeze_studio.py', 'eval'), env)
            assert sha(baseline / name) == sha(support.result_path(name))
            assert eval(after, env) == json.loads((baseline / name).read_text())
        counts['snapshot_reads'] = counts['repeat_reads'] = 3
    return counts


def check_public_payloads():
    parameters = json.loads((FIT_DATA / NAMES[0]).read_text())['parameters']
    curves = sorted({tuple(bytes.fromhex(row['curve_hex'])) for row in parameters})
    arrays = [r'\[\s*' + r'\s*,\s*'.join(str(n) for n in curve) + r'\s*,?\s*\]' for curve in curves]
    tokens = r'curve_hex|matrix_hex|colour_hex|curve_values'
    command = ['rg', '-l', '--hidden', '--threads', '1', '--multiline', '--no-ignore-dot',
               '--no-ignore-global', '--glob', '!**/.git/**', '-e', tokens]
    for pattern in arrays:
        command += ['-e', pattern]
    found = run([*command, 'research', 'studio'], valid=(0, 1))
    candidates = set(found.stdout.splitlines())
    # Explicitly include tracked files even when a later ignore rule matches them.
    cached = git('ls-files', '--cached', '--ignored', '--exclude-standard', '-z', '--', 'research', 'studio')
    paths = [p for p in cached.stdout.split('\0') if (ROOT / p).is_file() and not (ROOT / p).is_symlink()]
    for start in range(0, len(paths), 256):
        extra = run([*command, '--', *paths[start:start+256]], valid=(0, 1))
        candidates.update(extra.stdout.splitlines())
    literal = re.compile(r'''["'](?:curve_hex|matrix_hex|colour_hex)["']\s*:\s*["'][0-9a-fA-F]{2,}["']|["']curve_values["']\s*:\s*\[\s*\d''')
    quantized = [re.compile(pattern) for pattern in arrays]
    hits = []
    for name in sorted(candidates):
        text = (ROOT / name).read_text(errors='replace')
        if literal.search(text) or any(pattern.search(text) for pattern in quantized):
            ignored = git('check-ignore', '--', name, valid=(0, 1)).returncode == 0
            hits.append(dict(path=name, ignored=ignored))
    (EVIDENCE / 'grep-candidates.txt').write_text('\n'.join(sorted(candidates)) + '\n')
    result = dict(scopes=['research', 'studio'], candidate_files=sorted(candidates),
                  tracked_ignored_files_scanned=len(paths), quantized_curve_signatures=len(curves),
                  literal_payload_hits=hits, nonignored_payload_hits=[h for h in hits if not h['ignored']],
                  studio_payload_hits=[h for h in hits if h['path'].startswith('studio/')],
                  grep_exit_code=found.returncode,
                  method='rg filenames only, then check literal hex values and exact 33-value fitted arrays in memory; never save payload values')
    save('payload-scan.json', result)
    assert not result['nonignored_payload_hits'] and not result['studio_payload_hits'], hits
    return result


def main():
    before = json.loads((EVIDENCE / 'before.json').read_text())
    volume = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert volume['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['FilesystemType'] == 'apfs' and volume['WritableVolume']
    (EVIDENCE / 'df.txt').write_text(run(['df', '-h', '/Volumes/Workspace']).stdout)
    files = []
    for name, expected in zip(NAMES, EXPECTED):
        old = ROOT / SCOPES[0] / name
        new = FIT_DATA / name
        assert not old.exists() and sha(new) == expected
        assert git('check-ignore', '-v', '--', str(new.relative_to(ROOT))).returncode == 0
        assert git('check-ignore', '--', str(old.relative_to(ROOT)), valid=(0, 1)).returncode == 1
        assert not git('ls-files', '--', str(new.relative_to(ROOT)), str(old.relative_to(ROOT))).stdout
        files.append(dict(path=str(new.relative_to(ROOT)), bytes=new.stat().st_size, sha256=expected))
    ignore = (ROOT / '.gitignore').read_text().splitlines()
    assert '/research/look_ceiling_r1/local/' in ignore
    assert all('/' + SCOPES[0] + '/' + name not in ignore for name in NAMES)
    old_references = run(['rg', '-n', '--hidden', '--no-ignore', '-F',
        *[arg for name in NAMES for arg in ('-e', SCOPES[0] + '/' + name)], *SCOPES], valid=(0, 1))
    assert old_references.returncode == 1, old_references.stdout
    (EVIDENCE / 'old-reference-scan.txt').write_text('No old-path references in the four requested scopes. rg exit 1.\n')
    routes = check_routes()
    manifests = []
    for relative, cwd, label in (
        ('research/vlog_alchemy_eval/SHA256SUMS', ROOT, 'vlog'),
        ('research/g154_looks_r1/SHA256SUMS', ROOT, 'g154'),
        ('SHA256SUMS', FIT_DATA, 'private-data'),
        ('firmware/package_v39_g154_looks18_test/SHA256SUMS', ROOT, 'package'),
    ):
        checked = run(['shasum', '-a', '256', '-c', relative], cwd=cwd)
        (EVIDENCE / ('shasum-' + label + '.txt')).write_text(checked.stdout + checked.stderr)
        manifests.append(dict(manifest=str((cwd / relative).relative_to(ROOT)), exit_code=0,
                              verified=sum(line.endswith(': OK') for line in checked.stdout.splitlines())))
    protected = {}
    for key in ('protected_package', 'protected_studio_source'):
        protected[key] = [p for p, row in before[key].items() if not (ROOT / p).is_file() or sha(ROOT / p) != row['sha256']]
    assert not protected['protected_package'], protected
    index = before['git_index']
    assert index is None or sha(index['path']) == index['sha256']
    dat = ROOT / 'firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT'
    assert sha(dat) == DAT_SHA
    for base in (ROOT / SCOPES[0], HERE):
        for p in base.glob('*.py'):
            ast.parse(p.read_text(), filename=str(p))
    for p in (ROOT / SCOPES[1] / 'report.py', ROOT / SCOPES[3] / 'prepare.py'):
        ast.parse(p.read_text(), filename=str(p))
    payloads = check_public_payloads()
    for scope, cwd in (('root', ROOT), ('studio', ROOT / 'studio')):
        status = git('status', '--porcelain', '--ignored', cwd=cwd)
        (EVIDENCE / ('git-status-' + scope + '.txt')).write_text(status.stdout)
    status = git('status', '--porcelain', '--ignored', '--untracked-files=all', '--',
                 *[str((FIT_DATA / name).relative_to(ROOT)) for name in NAMES])
    (EVIDENCE / 'git-status-private-data.txt').write_text(status.stdout)
    assert len(status.stdout.splitlines()) == 3 and all(line.startswith('!! ') for line in status.stdout.splitlines())
    assert index is None or sha(index['path']) == index['sha256']
    result = dict(status='PASS', files=files, routing=routes, manifests=manifests,
                  dat_sha256=sha(dat), package_files_unchanged=len(before['protected_package']),
                  protected_changes=protected, git_index_unchanged=True,
                  old_path_references_in_requested_scopes=0,
                  nonignored_payload_hits=payloads['nonignored_payload_hits'], studio_payload_hits=payloads['studio_payload_hits'])
    save('verification.json', result)
    seal_receipts()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--routing-child':
        routing_child(Path(sys.argv[2]))
    else:
        main()
