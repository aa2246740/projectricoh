"""Route every generated file into this independent delta-review directory."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "research/review_v35_body"
BUILDER = ROOT / "firmware/image_v36/local/review"

def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

protected = {}
for rel in ("firmware/resident_v35", "firmware/image_v35", "firmware/resident_v36",
            "firmware/image_v36", "tools/native_harness", "research/review_v35_body",
            "firmware/engine_v37", "artifacts/firmware/gxr-1.51"):
    for p in (ROOT / rel).rglob("*"):
        if p.is_file():
            protected[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
p = ROOT / "artifacts/downloads/gxr-151.zip"
protected[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
save("protected-before.json", protected)

changes = []
def copy(source, name, replacements=()):
    before = source.read_text()
    after = before
    for a, b in replacements:
        assert a in after, (name, a)
        after = after.replace(a, b)
    (HERE / name).write_text(after)
    changes.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                   fromfile=str(source.relative_to(ROOT)), tofile="review_v36_body/" + name))

copy(OLD / "review_common.py", "review_common.py", [
    ('import json\n', 'import json\nimport os\n'),
    ('python_backend.CACHE = HERE / "decode"', 'python_backend.CACHE = HERE / "decode" / str(os.getpid())')])
copy(ROOT / "firmware/image_v36/harness_scenarios/run_v35.py", "body_binding.py", [
    ('ROOT = Path(__file__).resolve().parents[3]', 'ROOT = Path(__file__).resolve().parents[2]')])
copy(OLD / "adversarial.py", "adversarial.py", [
    ('ROOT / "firmware/image_v35/harness_scenarios/run_v35.py"', 'HERE / "body_binding.py"')])
for name in ("h08_retire.py", "h08_first_fault.py", "reachability.py", "ownership.py", "h06_fault.py"):
    copy(BUILDER / name, name)
copy(OLD / "scroll_both.py", "scroll_both.py", [
    ('assert rec["final"]["mode"]==5 and rec["final"]["root"]["state"]==6',
     'assert rec["final"]["mode"]==1 and rec["final"]["root"]["state"]==6\nassert rec["final"]["native_visits"]["H08_native"]==0\nassert rec["final"]["deep_sha256"]==rec["positive_final"]["deep_sha256"]'),
    ('PASS both keys and wraps; COUNTEREXAMPLE on up key too',
     'PASS both keys and wraps; up-key fault also skips H08 and preserves 01')])
copy(OLD / "file_edge.py", "file_edge.py", [
    ('self.contents=contents if contents is not None else {"/IROM/GXRCE0.DAT":bytes(product.dat)}',
     'assert product.files.dat[256:]==product.dat[256:]\n        self.contents=contents if contents is not None else {"/IROM/GXRCE0.DAT":bytes(product.files.dat)}')])
for name in ("p2_gates.py", "extra_scenarios.py", "deep_bytes.py",
             "power02.py", "h07_balance.py", "menu_native.py", "run_checks.py"):
    copy(OLD / name, name)
copy(ROOT / "firmware/image_v36/run_v36_checks.py", "run_v36_checks.py", [
    ("HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];REVIEW=HERE/'local/review'",
     "HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];REVIEW=HERE")])
copy(OLD / "structural.py", "structural.py", [
    ('firmware/image_v35', 'firmware/image_v36'),
    ('"6e9ea05868b2bb56fb60de0e8506aad7b952715c061009b2acc891b45d220b20"', '"50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008"'),
    ('firmware/image_v34c', 'firmware/image_v35'),
    ('"24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72"', '"6e9ea05868b2bb56fb60de0e8506aad7b952715c061009b2acc891b45d220b20"'),
    ('Elf(HERE/"resident/build/resident.elf")', 'Elf(ROOT/"firmware/resident_v36/local/resident/build/resident.elf")'),
    ('"v34c"', '"v35"'), ('("v35",body)', '("v36",body)'),
    ('body.bytes_at(0x20054634,204)', 'body.bytes_at(0x20054638,200)'),
    ('b"\\xff"*204', 'b"\\xff"*200'),
    ('firmware/resident_v35', 'firmware/resident_v36')])
(HERE / "script-routing.diff").write_text("".join(changes))
save("prepare.json", dict(protected_files=len(protected), scope=str(HERE), copied_scripts=19))
print("Prepared isolated review; protected files", len(protected))
