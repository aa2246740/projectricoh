# Mutate the decoded grain stub in a copy of payload-disasm.txt and check the
# ABI model rejects each mutant. Scratch is inside the gitignored build.
# Inputs are only read from the real build.
import shutil, subprocess, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
BUILD = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "build"
WORK = BUILD / "abi-mutations"
WORK.mkdir(parents=True, exist_ok=True)
results = []
TEST = HERE / "tests/test_abi.py"
original = (BUILD / "payload-disasm.txt").read_text()
MUTANTS = [
    ("20053ff8:\t26 7f 27 7f \tpush r6 -> push r7", "20053ff8:\t26 7f 27 7f \tpush r6 -> nop", "r7 not saved"),
    ("20054024:\t28 ef 27 ef \tpop r8 -> pop r7", "20054024:\t28 ef 27 ef \tpop r7 -> pop r8", "r7/r8 restored swapped"),
    ("20054014:\t20 ef 10 a0 \tpop r0 -> mvtc r0,psw", "20054014:\t20 ef 10 a0 \tpop r0 -> nop", "PSW not restored"),
    ("20054008:\t2e 7f 10 90 \tpush lr -> mvfc r0,psw", "20054008:\t2e 7f 10 90 \tpush lr -> mv r0,r0", "PSW not saved"),
    ("20054034:\t20 ef 2e 7f \tpop r0 -> push lr", "20054034:\t20 ef 2e 7f \tpop r0 -> nop", "replayed push lr missing"),
    ("20054034:\t20 ef 2e 7f \tpop r0 -> push lr", "20054034:\t20 ef 2e 7f \tpop r0 -> push r0", "replays push r0"),
    ("2005403c:\tff 04 72 55 \tbra 20170990 <native_2f02_resume>", "2005403c:\tff 04 72 55 \tbra 20170994 <x>", "resumes at 0x20170994"),
    ("2005400c:\t20 7f 10 85 \tpush r0 -> mv r0,r5", "2005400c:\t20 7f 10 85 \tpush r0 -> mv r0,r4", "passes r4 as the block"),
    ("20054038:\t70 00 f0 00 \tnop || nop", "20054038:\t70 00 f0 00 \tbeqz r0,20170990", "conditional exit added"),
    ("20054018:\t2e ef 2d ef \tpop lr -> pop fp", "20054018:\t2e ef 2d ef \tpop lr -> nop", "fp not restored"),
    ("20054030:\t22 ef 21 ef \tpop r2 -> pop r1", "20054030:\t22 ef 21 ef \tpop r2 -> pop r2", "r1 restored into r2"),
]
for i, (old, new, label) in enumerate(MUTANTS):
    if original.count(old) != 1:
        raise ValueError(f"{label}: PATTERN COUNT {original.count(old)}")
    d = WORK / str(i)
    if d.exists(): shutil.rmtree(d)
    d.mkdir()
    shutil.copy(BUILD / "manifest.json", d / "manifest.json"); shutil.copy(BUILD / "hooks.json", d / "hooks.json")
    (d / "payload-disasm.txt").write_text(original.replace(old, new))
    r = subprocess.run([sys.executable, "-I", str(TEST), str(d)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0, f"{label} survived"
    results.append({"case": label, "killed": True})
    tail = (r.stderr.strip().splitlines() or ["?"])[-1][:100]
    print(f"{i:2d} {label}: {'SURVIVED' if r.returncode == 0 else 'killed: ' + tail}")
    shutil.rmtree(d)
d = WORK / "base"; d.mkdir(exist_ok=True)
shutil.copy(BUILD / "manifest.json", d / "manifest.json"); shutil.copy(BUILD / "hooks.json", d / "hooks.json"); (d / "payload-disasm.txt").write_text(original)
r = subprocess.run([sys.executable, "-I", str(TEST), str(d)], capture_output=True, text=True, cwd=ROOT)
print("unmutated copy:", "passes" if r.returncode == 0 else "FAILS " + r.stderr[-200:]); shutil.rmtree(d)

assert r.returncode == 0, r.stderr
(BUILD / "abi-mutations.json").write_text(json.dumps({"baseline_passed": True, "cases": len(results), "all_killed": True, "results": results}, indent=2)+"\n")
