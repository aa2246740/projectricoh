"""Run the changed DAT path and the relevant API/frontend regressions without reruns."""
import contextlib
import json
import os
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import environment

fixture, output = environment('targeted-tests')
os.environ['PYTEST_ADDOPTS'] = '--force-reruns 0'
os.environ['COVERAGE_FILE'] = str(fixture/'.coverage')
tests = ['tests/test_dat_card_identity.py', 'tests/test_card_read_boundaries.py',
         'tests/test_camdata_api.py', 'tests/test_camdata.py', 'tests/test_gpu_api.py',
         'tests/test_gpu_frontend.py', 'tests/test_gpu_state.py', 'tests/test_gpu_gate.py',
         'tests/test_clone_coverage.py::test_intake_pack_scan_and_api']
import pytest

start = time.monotonic()
arguments = ['-q', '-s', '--force-reruns', '0', '--basetemp', str(fixture/'pytest'),
             '--junitxml', str(output/'tests.xml'), *tests]
with (output/'pytest.log').open('w') as stdout, (output/'pytest-stderr.log').open('w') as stderr, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
    code = pytest.main(arguments)
suites = ET.parse(output/'tests.xml').getroot()
receipt = {'exit': int(code), 'seconds': time.monotonic()-start, 'nice': os.getpriority(os.PRIO_PROCESS, 0),
           'arguments': arguments, 'reruns': 0,
           'testsuites': [dict(s.attrib) for s in suites.iter('testsuite')]}
(output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
raise SystemExit(int(code))
