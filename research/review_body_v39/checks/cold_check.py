#!/usr/bin/python3 -I
"""Compare three cold MAIN executions with explicit output and batch counts."""
from pathlib import Path
import importlib.util
import json
import os
import sys
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_model as B

source = B.ROOT / 'research/body_v39/tests/emu_boot.py'
text = source.read_text()
prior = "Path('/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39')"
assert text.count(prior) == 1
text = text.replace(prior, 'Path(' + repr(os.environ['REVIEW_TEMP']) + ')')
module = types.ModuleType('emu_boot')
module.__file__ = str(source)
sys.modules['emu_boot'] = module
exec(compile(text, str(source), 'exec'), module.__dict__)
import storage_run
storage_run.OUT = Path(os.environ['REVIEW_TEMP']) / 'whole-body'
spec = importlib.util.spec_from_file_location('review_cold_comparison', source.with_name('emu_diff.py'))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
comparison.HERE = HERE
comparison.main()
result = json.loads((B.OUT / 'emu-diff.json').read_text())
assert all(result['observations_equal'].values())
assert all(len(set(row['state'].values())) == 1 for row in result['phases'])
assert result['root_page_v39'][:488] == 'ff' * 244
assert len(B.INSTANCES) == 3
assert all(cpu.batch_stats.get('batch-steps', 0) > 0 for cpu in B.INSTANCES)
print(json.dumps({'status': 'PASS', 'observations': result['observation_counts'],
                  'batch_stats': [dict(cpu.batch_stats) for cpu in B.INSTANCES]}))
