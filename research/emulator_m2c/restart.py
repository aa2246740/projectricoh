"""Start MAIN afresh on the exact image accepted by the native file check."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from fat_image import inspect


def file_entry(metadata):
    return next(row for row in metadata["files"] if row["name"] == "M2CWRITE.BIN")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=Path, required=True)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--stop-at", type=lambda value: int(value, 0))
    args = parser.parse_args()
    card = args.card.resolve()
    if not card.is_file() or not card.is_relative_to(OUT):
        raise ValueError("restart requires an ignored M2c image")
    if not args.name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("use a simple restart name")
    target = OUT / (args.name + "-restart.json")
    before_copy = OUT / (args.name + "-before.img")
    if target.exists() or before_copy.exists() or (OUT / (args.name + ".json")).exists():
        raise ValueError("use a fresh restart name")
    accepted = json.loads(args.files.read_text())
    before = inspect(card)
    if accepted["status"] != "passed" or accepted.get("written") != 4099 \
            or accepted.get("write_close") != 0 \
            or before["image_sha256"] != accepted["medium"]["image_sha256"]:
        raise RuntimeError("restart input differs from the accepted native write")
    expected = file_entry(before)
    shutil.copyfile(card, before_copy)
    if hashlib.sha256(before_copy.read_bytes()).hexdigest() != before["image_sha256"]:
        raise RuntimeError("sealed pre-start image differs")
    command = ["/usr/bin/python3", "-I", "-B", "tools/gxr_emulator/storage_run.py",
               "--name", args.name, "--card", str(card), "--budget", "55000000"]
    if args.stop_at is not None:
        command += ["--stop-at", hex(args.stop_at), "--task", "8"]
    record = {"command": command, "card": str(card.relative_to(ROOT)),
              "source_files_check": str(args.files), "before": before,
              "before_copy": str(before_copy.relative_to(ROOT)), "checkpoint_input": None,
              "stop_cutpoint": args.stop_at}
    (OUT / (args.name + "-command.json")).write_text(json.dumps(record, indent=2) + "\n")
    with (OUT / (args.name + ".stdout")).open("wb") as stdout, \
            (OUT / (args.name + ".stderr")).open("wb") as stderr:
        process = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                 env={**os.environ, "TMPDIR": str(OUT)})
    run = json.loads((OUT / (args.name + ".json")).read_text())
    after = inspect(card)
    record.update({"returncode": process.returncode, "after": after,
                   "start_step": run["start_step"], "resume": run["resume"],
                   "stop": run["stop"], "file_unchanged": file_entry(after)["sha256"] == expected["sha256"]
                   and file_entry(after)["size"] == expected["size"]})
    stopped = run["stop"]["reason"] == "max_steps" and run["steps"] == 55000000 \
        if args.stop_at is None else run["stop"]["reason"] == "breakpoint" and run["stop"]["pc"] == args.stop_at
    passed = process.returncode == 0 and run["start_step"] == 0 and run["resume"] is None and stopped \
             and record["file_unchanged"] and after["fat_copies_equal"] and not after["unreferenced_clusters"]
    record["status"] = "passed" if passed else "incomplete"
    target.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"status": record["status"], "output": str(target)}))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
