"""Seal or verify the explicitly stopped P1 handoff; never stage firmware."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGE = ROOT / 'firmware/image_v34'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def output_files(directory):
    files = sorted(p for p in directory.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    assert all(not p.is_symlink() and p.resolve().is_relative_to(directory.resolve()) for p in files)
    return files


def checks():
    for directory in (HERE, IMAGE):
        assert (directory / '.gitignore').read_text() == '/local/\n'
        report = (directory / 'REPORT.md').read_text()
        for target in re.findall(r'\]\(([^)]+)\)', report):
            if '://' not in target:
                assert (directory / target.split('#')[0]).exists(), target
    budget = json.loads((HERE / 'local/budget.json').read_text())
    assert budget['status'] == 'STOPPED_P1_SIZE'
    assert budget['window_bytes'] == 8340 and budget['root_bytes'] == 256
    assert budget['required_margin_bytes'] == 200 and budget['payload_max_bytes'] == 7884
    assert (budget['payload_bytes'], budget['margin_bytes'], budget['needed_to_recover_bytes']) == (8976, -892, 1092)
    assert not any(budget[k] for k in ('body_image_built', 'container_full_r10_built', 'SD_ROOT_staged', 'product_acceptance', 'camera_acceptance'))
    for label in ('p1-final-os', 'p1-final-oz', 'p1-final-lto', 'p1-final-small'):
        out = HERE / 'local/resident' / label
        info = json.loads((out / 'size.json').read_text())
        assert not info['constrained_link'] and info['margin_bytes'] < 200
        assert not (out / 'resident.elf').exists(), 'failed-link ELF must not be delivered'
        mapping = (out / 'resident.map').read_text()
        amount = int(re.search(r'^\.payload\s+0x[0-9a-f]+\s+(0x[0-9a-f]+)', mapping, re.M)[1], 16)
        assert amount == info['payload_bytes']
    # The final source snapshots, not a stale earlier candidate, define the stop.
    for label in ('p1-final-oz', 'p1-final-lto', 'p1-final-small'):
        out = HERE / 'local/resident' / label
        frozen = json.loads((out / 'source-inputs.json').read_text())
        for name, digest in frozen.items():
            assert sha(HERE / name) == digest, 'source changed after measurement: ' + name
        assert (out / 'source/driver.py').read_bytes() == (HERE / 'build.py').read_bytes()
    result = json.loads((HERE / 'local/p1-checks/results.json').read_text())
    assert result['status'] == 'PASS_P1_LOCAL_CHECKS_ONLY'
    assert (result['host_cases'], result['host_assertions'], result['h40_stub_vectors'], result['irq_psw_vectors']) == (117, 10966, 524, 65536)
    assert not result['full_resident_link_passed'] and not result['continuous_native_replay']
    for rel, digest in (
        ('local/p1-checks/isolated-h40-proof.elf', result['isolated_proof_elf_sha256']),
        ('local/p1-checks/p1-host', result['host_executable_sha256']),
    ):
        assert sha(HERE / rel) == digest
    for name, digest in result['templates'].items():
        assert sha(HERE / 'local/controls' / name) == digest
    for rel, info in json.loads((HERE / 'local/baseline-identity.json').read_text()).items():
        assert sha(ROOT / rel) == info['sha256']
    assert not (IMAGE / 'local/package/SD_ROOT').exists()
    assert not list(IMAGE.rglob('ilaunch3')) and not list(IMAGE.rglob('GXRCE.DAT'))
    staged = json.loads((IMAGE / 'local/STAGING_BLOCKED.json').read_text())
    assert staged['status'] == 'STOPPED_P1_SIZE' and not staged['SD_ROOT_staged']
    return dict(status='SEALED_STOPPED_P1_SIZE', resident_margin_bytes=-892,
                required_recovery_bytes=1092, local_host_cases=117,
                h40_isolated_vectors=524, irq_vectors=65536,
                product_acceptance=False, camera_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('finalize', 'verify'))
    args = parser.parse_args()
    prepare = load(HERE / 'prepare.py', 'v34_protected_check')
    count = prepare.check()
    frozen = json.loads((HERE / 'local/inputs-before.json').read_text())
    added = []
    for rel in prepare.SCOPES:
        base = ROOT / rel
        for p in (base.rglob('*') if base.is_dir() else [base]):
            if p.is_file() and not p.is_symlink() and p.name != 'decisions.tsv' and '__pycache__' not in p.parts:
                if str(p.relative_to(ROOT)) not in frozen:
                    added.append(str(p.relative_to(ROOT)))
    assert not added, 'STOP_PROTECTED_INPUT_ADDED: ' + repr(added)
    result = checks()
    result['protected_inputs_unchanged'] = count
    if args.mode == 'finalize':
        (HERE / 'local/delivery.json').write_text(json.dumps(result, indent=2) + '\n')
        for directory in (HERE, IMAGE):
            (directory / 'SHA256SUMS').write_text(''.join(
                f'{sha(p)}  {p.relative_to(directory)}\n' for p in output_files(directory)))
    counts = {}
    for directory in (HERE, IMAGE):
        lines = (directory / 'SHA256SUMS').read_text().splitlines()
        expected = {}
        for line in lines:
            digest, name = line.split('  ', 1)
            p = directory / name
            assert p.resolve().is_relative_to(directory.resolve()) and sha(p) == digest, name
            assert name not in expected
            expected[name] = digest
        assert set(expected) == {str(p.relative_to(directory)) for p in output_files(directory)}
        counts[directory.name] = len(expected)
    print(json.dumps(dict(**result, checksum_files=counts,
        resident_SHA256SUMS_sha256=sha(HERE / 'SHA256SUMS'),
        image_SHA256SUMS_sha256=sha(IMAGE / 'SHA256SUMS'))))


if __name__ == '__main__':
    main()
