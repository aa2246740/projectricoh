"""Derive the g135 check tools from the g131 ones (copy, rename paths and generation)."""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'research/g131_merge'
DST = ROOT / 'research/g135_v37'
COPY = ['fences.py', 'host_check.py', 'host_engine.c', 'layout.py', 'adapter_layout.c', 'core_layout.c',
        'layout_bindings.py', 'target_gate.py', 'target_check.py', 'target_runner.c', 'capture_state.py',
        'product_checks.py', 'run_existing.py', 'run_stage.py', 'audit_communications.py',
        'verify_wrapper.py', 'verify_words.py']
for name in COPY:
    t = (SRC / name).read_text()
    for a, b in (('engine_v51_g131', 'engine_v53_g135'), ('package_v36_g131', 'package_v37_g135'),
                 ('g131_merge', 'g135_v37'), ('g131', 'g135'), ('G131', 'G135')):
        t = t.replace(a, b)
    t = re.sub(r'(?<![\w.])131(?![\w.])', '135', t)
    (DST / name).write_text(t)
    print(name, len(re.findall(r'\b13[15]\b', t)))
