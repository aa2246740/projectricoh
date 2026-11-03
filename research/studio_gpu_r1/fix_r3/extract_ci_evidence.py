"""Extract named Windows assertions and colour cases from the retained CI log."""

from pathlib import Path
import json
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
log = (OUT / 'ci-final-probes.log').read_text(encoding='utf-8')
assert head in log
groups = {}
for filename, count in (
    ('test_windows_io.py', 9),
    ('test_network_guard.py', 7),
    ('test_card_read_boundaries.py', 11),
):
    matches = re.findall(r'tests/' + re.escape(filename) + r'::(\S+)\s+PASSED', log)
    assert len(matches) == len(set(matches)) == count, (filename, matches)
    groups[filename] = matches
lifecycle = ('test_worker_exits_by_itself_when_the_parent_is_killed', 'test_worker_sets_the_stop_flag_when_the_parent_goes_away')
assert all(re.search(re.escape(name) + r'.{0,1000}PASSED', log, re.S) for name in lifecycle)
groups['worker_lifecycle'] = list(lifecycle)
platform_cases = ('test_prefs_default_off_then_remember_each_choice', 'test_default_settings_would_use_pictures_dir_but_tests_never_touch_it', 'test_real_volumes_are_off_limits_in_tests')
assert all(name + ' PASSED' in log for name in platform_cases)
groups['platform_boundaries'] = list(platform_cases)
assert 'test_display_lut_table_is_the_production_function_on_every_input PASSED' in log
colours = []
for line in log.splitlines():
    if '{"pixels":' in line:
        prefix, data = line.split('{"pixels":', 1)
        colours.append({'case': prefix.split()[-1], **json.loads('{"pixels":' + data)})
assert len(colours) == 13 and all(row['pass'] for row in colours)
table_hash = '0f87d0cb7e25e7b1c9cf03a5a1a852ff819d773b6de41f21bd97b3836f5df92c'
assert table_hash in log and '"blas_threads": null' in log
assert '"architecture": "swiftshader"' in log
processes = []
terminations = []
for line in log.splitlines():
    for marker, output in (('{"launcher":', processes), ('{"terminated_worker_pids":', terminations)):
        if marker in line:
            output.append(json.loads(marker + line.split(marker, 1)[1]))
assert len(processes) == len(terminations) == 1
assert processes[0]['parent'] == processes[0]['expected_parent']
assert terminations[0]['rounds'] == 20 and len(terminations[0]['terminated_worker_pids']) == 25
native = {'head': head, 'source_log': 'ci-final-probes.log', 'passed_cases': groups,
          'exact_table_inputs': 16777216, 'table_bytes': 67108864,
          'table_sha256': table_hash, 'blas_threads_environment': None,
          'process_relationships': processes[0], 'import_terminations': terminations[0]}
(OUT / 'windows-native-evidence.json').write_text(json.dumps(native, indent=2) + '\n', encoding='utf-8')
(OUT / 'gpu-colour-evidence.json').write_text(json.dumps({'head': head, 'adapter': 'SwiftShader', 'cases': colours}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'head': head, 'native_cases': {key: len(value) for key, value in groups.items()}, 'colour_cases': len(colours)}))
