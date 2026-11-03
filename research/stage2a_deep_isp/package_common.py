"""Paths and local-only helpers for the Stage 2a package workflow."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FW = ROOT/'firmware/stage2a_deep_isp'
PACKAGES = ROOT/'artifacts/stage2a-packages'
VARIANTS = {'safe':'stage2a-canonical-gr-safe', 'deep':'stage2a-canonical-gr-deep-isp'}


def local(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f'Symlink is not a package input/output: {path}')
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f'Package access must stay in project: {path}')
    return path


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def read_json(path):
    return json.loads(local(path).read_text())


def save_json(path, data):
    path = local(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name,local(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def run(argv, label):
    result = subprocess.run([str(a) for a in argv],cwd=ROOT,capture_output=True,text=True)
    log = HERE/'package_logs'/f'{label}.txt'
    log.parent.mkdir(exist_ok=True)
    log.write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'{label} exited {result.returncode}; see {log}')
    return result.stdout


def protected_inputs():
    snapshot = read_json(HERE/'package_protected_inputs.json')
    for name,expected in snapshot.items():
        assert sha(local(ROOT/name).read_bytes()) == expected, f'Protected input changed: {name}'
    # These are fixed reviewed Stage 1c inputs, outside this implementation tree.
    baseline = read_json(HERE/'baseline_snapshot.json')
    for entry in baseline:
        path = Path(entry['source'])
        assert path.is_absolute() and not str(path).startswith('/Volumes/')
        assert sha(path.read_bytes()) == entry['sha256'], str(path)
    previous = read_json(HERE/'verification.json')['reviewed_stage1c_artifacts_unchanged']
    for name,expected in previous.items():
        path = Path(name)
        assert path.is_absolute() and not str(path).startswith('/Volumes/')
        assert sha(path.read_bytes()) == expected, name
    return dict(local_official_and_existing_stage1_package_files=len(snapshot),
                stage1c_original_source_files=len(baseline),stage1c_reviewed_artifacts=len(previous),
                all_hashes_unchanged=True)
