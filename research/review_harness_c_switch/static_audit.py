from pathlib import Path
import hashlib
import json
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
SOURCE = ROOT / 'tools/speedlab/host_regression_r3'
REFERENCE = ROOT / 'tools/native_harness'
CANDIDATE = ROOT / 'tools/speedlab/harness_release'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sums = {}
    for path in sorted(CANDIDATE.glob('*.py')):
        other = REFERENCE / path.name
        if other.is_file():
            sums[path.name] = {'reference_sha256': sha(other), 'candidate_sha256': sha(path),
                               'equal': other.read_bytes() == path.read_bytes()}
    prefix_equal = (CANDIDATE / 'python_backend.py').read_bytes().startswith((REFERENCE / 'python_backend.py').read_bytes())
    stats = {}
    loads = []
    priorities = set()
    instructions = 0
    for file in sorted((SOURCE / 'local/measurements/c').glob('*/measurement.json')):
        data = json.loads(file.read_text())
        if data['job'] == 'user-tool':
            continue
        for key, value in data['native_stats'].items():
            stats[key] = stats.get(key, 0) + value
        for record in data['processes']:
            priorities.add(record['nice'])
    for file in sorted((SOURCE / 'local/measurements').glob('*/*/measurement.json')):
        data = json.loads(file.read_text())
        if data['job'] != 'user-tool':
            loads.extend([data['load_start'][0], data['load_end'][0]])
    selected = {}
    for path in [CANDIDATE / 'local/ccore/build.json',
                 ROOT / 'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT',
                 ROOT / 'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT',
                 REFERENCE / 'python_backend.py', CANDIDATE / 'python_backend.py']:
        selected[str(path.relative_to(ROOT))] = sha(path)
    result = {'python_source_prefix_exact': prefix_equal, 'python_files': sums,
              'stored_c_native_stats': stats, 'stored_worker_priorities': sorted(priorities),
              'stored_sampled_load_range': [min(loads), max(loads)], 'selected_input_hashes': selected}
    (OUT / 'evidence/static-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'python_files'}))


if __name__ == '__main__':
    main()
