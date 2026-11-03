"""After real retire restores seven rows, H06 must retain its native continuation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, save as original_save
exec(compile((HERE / "adversarial.py").read_text().split('selected=sys.argv')[0], str(HERE / "adversarial.py"), "exec"), globals())
def save(name, value): original_save("native7-h06-" + name, value)
POINTS[0x202be250] = "H06_native"
run("native_H06_after_retire", [OPEN, ONE, OK, REOPEN,
    ("negative: corrupt snapshot", corrupt_ui), SCROLL, REOPEN, FN2])
r = reports[-1]
save("adversarial.json", reports)
assert "error" not in r
assert r["final"]["ui"]["rows"] == 7
assert r["final"]["native_visits"]["H06_native"] > 0
assert r["steps"][-1]["result"]["ok"]
print("PASS seven-row H06 native continuation allowed after genuine retire", flush=True)
