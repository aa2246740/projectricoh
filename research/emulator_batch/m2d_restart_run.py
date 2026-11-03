"""Copy of research/emulator_m2d/restart_run.py for tools/gxr_emulator_batch; changes are marked BATCH-COPY."""
"""Start official MAIN with a verified copy of a completed file-case medium."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator_batch"))
from input_run import run
from storage_run import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--budget", type=int, default=40000000)
    args = parser.parse_args()
    if not all(value.replace("-", "").isalnum() for value in (args.name, args.case)):
        raise ValueError("use simple local evidence names")
    case_path = OUT / (args.case+".json")
    case = json.loads(case_path.read_text())
    source = OUT / (args.case+"-medium.img")
    target = OUT / (args.name+"-medium.img")
    input_path = OUT / (args.name+"-input.json")
    if target.exists() or input_path.exists() or (OUT / (args.name+".json")).exists():
        raise ValueError("use a fresh restart name")
    source_sha = sha(source)
    if case["status"] != "passed" or source_sha != case["medium"]["image_sha256"]:
        raise ValueError("completed file-case medium identity differs")
    shutil.copyfile(source, target)
    record = {"source_case": args.case, "source_case_sha256": sha(case_path),
              "source_medium_sha256": source_sha, "restart_medium_sha256": sha(target),
              "checkpoint_input": None, "driver_sha256": sha(Path(__file__))}
    if record["restart_medium_sha256"] != source_sha:
        raise ValueError("restart medium copy differs")
    input_path.write_text(json.dumps(record, indent=2)+"\n")
    values = SimpleNamespace(name=args.name, resume=None, card=target, budget=args.budget,
                             segment=None, stop_at=[0x2010E23C], stop_task=8,
                             stop_after=[], watch=[])
    run(values)


if __name__ == "__main__":
    main()
