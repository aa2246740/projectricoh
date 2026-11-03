"""Run only still-skipped cases whose local data can be redirected safely."""
import json
from pathlib import Path
import pytest

report=Path(__file__).resolve().parent
data=json.loads((report/'supplement-coverage.json').read_text())
names=[row['module'].replace('.','/')+'.py::'+row['name'] for row in data['remaining_cases'] if row['module'] not in {'tests.test_fix_review','tests.test_raw'}]
(report/'remaining-targets.json').write_text(json.dumps(names,indent=2)+'\n')
raise SystemExit(pytest.main(['-p','local_fixtures','-q','--durations=10',*names]))
