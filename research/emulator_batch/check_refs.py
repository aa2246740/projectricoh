"""Print a batch run against the frozen per-step references of research/emulator_speed."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
run = json.loads(Path(sys.argv[1]).read_text())
profile = run["profile"]
candidate = {"no-card": "33004041", "card": "42572307"}[profile]
for s in run["segments"]:
    print(s["segment"], s["to"], round(s["seconds"], 1), round(s["steps_per_second"]))
snap = json.loads((ROOT / "tools/gxr_emulator/local/speed" / (profile + ".snap.json")).read_text())
print("candidate state == snapshot metadata:", run["points"][candidate]["state"] == snap["state_hash"])
if "adj" in run:
    adj = json.loads((ROOT / "research/emulator_speed/local" / (profile + "-adj-cold-debug.json")).read_text())
    print("ADJ state/observations/flow == emulator_speed cold debug:",
          run["adj"]["state"] == adj["state"], run["adj"]["observations"] == adj["observations"],
          run["adj"]["flow_hash"] == adj["flow_hash"])
