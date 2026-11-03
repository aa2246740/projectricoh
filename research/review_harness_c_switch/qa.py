from pathlib import Path
import hashlib
import json
import re

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
SOURCE = ROOT / 'tools/speedlab/host_regression_r3'


def main():
    report = (OUT / 'REVIEW.md').read_text()
    assert report.splitlines()[0] == '修改后再采用'
    assert '补跑中' not in report and '尚未判定' not in report and '复审仍在补跑' not in report
    missing = []
    for target in re.findall(r'\]\(([^\n)]+)\)', report):
        if target.startswith('/'):
            path = Path(re.sub(r':\d+$', '', target))
            if not path.exists() and path != OUT / 'SHA256SUMS':
                missing.append(str(path))
    assert not missing, missing
    compiled = []
    for path in sorted(OUT.glob('*.py')):
        compile(path.read_text(), str(path), 'exec')
        compiled.append(path.name)
    runner_sha = hashlib.sha256((ROOT / 'research/review_g135/runner.py').read_bytes()).hexdigest()
    required = {'name', 'returncode', 'postcheck_returncode', 'seconds', 'dat_sha256', 'runner_sha256', 'observations'}
    products = list((SOURCE / 'local/measurements').glob('*/*/products'))
    products += list((OUT / 'entry/local/runs').glob('*/run/local/jobs/*'))
    wrappers = []
    for folder in products:
        for path in folder.rglob('result-*.json'):
            data = json.loads(path.read_text())
            assert required <= data.keys() and data['runner_sha256'] == runner_sha
            assert type(data['seconds']) in (int, float)
            wrappers.append(str(path.relative_to(ROOT)))
    checks = json.loads((OUT / 'evidence/check-results.json').read_text())
    comparisons = json.loads((OUT / 'comparisons/summary.json').read_text())
    cleanup = json.loads((OUT / 'evidence/cleanup.json').read_text())
    assert checks['candidate_accepted'] is False and len(checks['blocking_findings']) == 3
    assert checks['evidence_checks_complete'] and comparisons['passed'] and comparisons['groups'] == 5
    assert cleanup['remaining_review_processes'] == [] and cleanup['tmp_exists_after'] is False
    assert not Path(cleanup['tmp']).exists()
    result = {'passed': True, 'report_sha256': hashlib.sha256(report.encode()).hexdigest(),
              'missing_report_links': missing, 'compiled_review_scripts': compiled,
              'timing_wrapper_schema_checks': len(wrappers), 'timing_wrappers': wrappers,
              'timing_exclusion_scope': 'Only verified retained-runner wrapper root seconds; other acceptance fields retained',
              'blocking_findings': checks['blocking_findings'], 'real_groups': 5}
    (OUT / 'evidence/qa.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('compiled_review_scripts', 'timing_wrappers')}))


if __name__ == '__main__':
    main()
