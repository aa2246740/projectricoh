from pathlib import Path
import importlib.util
import json
import os
import sys
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
HERE = OUT / 'busy-diagnostic'
HERE.mkdir(exist_ok=False)
os.environ.update(GXR_HARNESS_BACKEND='c', GXR_HARNESS_UI_AUDIT='1',
                  GXR_HOST_METRICS_DIR=str(HERE / 'metrics'), REVIEW_JOB='busy-settings-exit',
                  G139_PACKAGE='firmware/package_v38_g139', G139_ENGINE='firmware/engine_v56_g139',
                  TMPDIR='/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch/busy-diagnostic')
Path(os.environ['TMPDIR']).mkdir()
sys.path.insert(0, str(OUT / 'busy/c'))
from backend_select import install
install()
spec = importlib.util.spec_from_file_location('busy_diagnostic_case', OUT / 'busy/c/independent_checks.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
H = module.H
H.LOCAL = HERE / 'model'
H.setup()
started = time.monotonic()
cam, detail = module.busy_settings_exit('50mm')
python_file = next((OUT / 'busy/python/tests/local').rglob('50mm-busy-settings-exit.json'))
c_file = next((OUT / 'busy/c/tests/local').rglob('50mm-busy-settings-exit.json'))
python = json.loads(python_file.read_text())
candidate = json.loads(c_file.read_text())
reference_detail = dict(python['detail'])
reference_detail.pop('native_UI_audit')
result = {'scope': 'Original case function assertions and return detail; reporter module assertion is not executed in this diagnostic',
          'function_detail_equal': reference_detail == detail,
          'main_rpc_logs_equal': python['rpc_log'] == candidate['rpc_log'],
          'main_file_logs_equal': python['file_log'] == candidate['file_log'],
          'rpc_records': len(python['rpc_log']), 'file_records': len(python['file_log']),
          'reporter_status': {'python': python['status'], 'c': candidate['status']},
          'c_class_module': type(cam.h.b).__module__,
          'c_packets': cam.h.b.total_steps, 'native_stats': cam.h.b.native_stats,
          'wall_seconds': time.monotonic() - started, 'c_detail': detail}
(HERE / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: value for key, value in result.items() if key != 'c_detail'}), flush=True)
