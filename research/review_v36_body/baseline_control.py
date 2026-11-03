"""Positive control: the same real-getter replay must still expose the v3.5 P0."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, ROOT, save as original_save
source = (HERE / "adversarial.py").read_text().split('selected=sys.argv')[0]
source = source.replace('HERE / "body_binding.py"', 'ROOT / "firmware/image_v35/harness_scenarios/run_v35.py"')
exec(compile(source, str(HERE / "adversarial.py"), "exec"), globals())
def save(name, value): original_save("baseline-control-" + name, value)
run("v35_positive_control_H08", [OPEN, ONE, OK, REOPEN, ONE,
    ("negative: corrupt detached snapshot", corrupt_ui), SCROLL, MENU])
r = reports[-1]
assert "error" not in r
assert r["final"]["mode"] == 5 and r["final"]["native_visits"]["H08_native"] == 1
assert r["final"]["deep_sha256"] == r["steps"][2]["after"]["deep_sha256"]
save("adversarial.json", reports)
print("PASS positive control v3.5 still reproduces Setting2 plus unchanged 01 rows", flush=True)
