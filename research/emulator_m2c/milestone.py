"""Evaluate M2c from selected native runs, independent media checks and fixed inputs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
WRITTEN_SHA = "47bbc5ee8a4585c558ad1e5b9a9c9da604ead3c82bb6c327cd80285847d46e41"
SEED_SHA = "1dcaaea6de71feceab845d0fac6fd266871df5ab6f5606738fde680747b402cf"


def read(name):
    return json.loads((OUT / (name + ".json")).read_text())


def entry(metadata):
    return next((row for row in metadata["files"] if row["name"] == "M2CWRITE.BIN"), {})


def file_value(metadata):
    row = entry(metadata)
    return row.get("size") == 4099 and row.get("sha256") == WRITTEN_SHA \
        and bool(row.get("clusters")) and metadata["fat_copies_equal"] \
        and not metadata["unreferenced_clusters"]


def task_and_lock(case):
    names = {"open-test-file", "read-short-file", "close-read-file", "create-new-file",
             "write-new-file", "close-written-file"}
    rows = [row for row in case["calls"] if row["name"] in names]
    return bool(rows) and all(row["task"] == row["return_task"] == 8 and row["psw"] & 0x80
                              and row["semaphore47_before"] == row["semaphore47_after"] == 1
                              and row["stop"]["reason"] == "return" for row in rows)


def card_mount(run):
    medium = None
    for row in run["events"]:
        if row.get("task") != 8:
            continue
        if row["kind"] == "medium-mount":
            medium = row["args"][0]
        elif row["kind"] == "medium-mount-return":
            if medium == 1 and row.get("r0") == 0:
                return True
            medium = None
    return False


def mounted_call(case, name):
    return any(row["name"] == name and row["state_before"].get("volume", {}).get("mounted_flags", 0) & 1
               for row in case["calls"])


def error_code(case, first, second):
    return any(row["kind"] == "file-error-code" and row["args"][:2] == [first, second]
               for row in case["events"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("files", "reboot", "readback", "full", "read_error", "write_error",
                 "no_card", "cumulative", "model_checks", "guard", "final_sources"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().parent != OUT:
        raise ValueError("use a fresh M2c local result")
    selected = {key: read(getattr(args, key)) for key in
                ("files", "reboot", "readback", "full", "read_error", "write_error",
                 "no_card", "cumulative", "model_checks", "guard", "final_sources")}
    files, reboot, back = (selected[key] for key in ("files", "reboot", "readback"))
    full, read_error, write_error = (selected[key] for key in ("full", "read_error", "write_error"))
    boot = read(args.reboot.removesuffix("-restart"))
    raw = files["read"]
    back_read = back["read"]
    checks = {
        "declared_block_model": selected["model_checks"]["passed"] >= 13,
        "fresh_MAIN_restart": reboot["status"] == "passed" and boot["start_step"] == 0
                              and boot["resume"] is None
                              and (boot["steps"] == 55000000 and boot["stop"]["reason"] == "max_steps"
                                   or boot["stop"]["reason"] == "breakpoint"
                                   and boot["stop"]["pc"] == 0x2010E23C),
        "native_card_mount": card_mount(boot),
        "seed_open_read_close": files["status"] == "passed" and raw["returned"] == 3077
                                and raw["byte_equal"] and raw["sha256"] == SEED_SHA
                                and files["read_close"] == 0,
        "short_read_preserves_tail": raw["requested"] == 3204 and raw["returned"] == 3077
                                     and raw["tail_unchanged"],
        "native_create_write_close": files["written"] == 4099 and files["write_close"] == 0,
        "independent_FAT_after_write": file_value(files["medium"]),
        "same_image_bytes_at_restart": reboot["before"]["image_sha256"] == files["medium"]["image_sha256"]
                                       and reboot["checkpoint_input"] is None,
        "native_read_after_restart": back["status"] == "passed" and back["filename"] == "/ATA1/M2CWRITE.BIN"
                                     and Path(back["resume"]).name == args.reboot.removesuffix("-restart") + "-stop.pkl"
                                     and back_read["returned"] == 4099 and back_read["byte_equal"]
                                     and back_read["sha256"] == WRITTEN_SHA and back["read_close"] == 0,
        "independent_FAT_after_restart": file_value(reboot["after"]) and file_value(back["medium"]),
        "full_medium_branch": full["status"] == "passed" and full["medium"]["free_clusters"] == 0
                              and full.get("create_result", 0) < 0
                              and mounted_call(full, "create-new-file") and error_code(full, 4, 17),
        "read_error_branch": read_error["status"] == "passed" and read_error["read"]["returned"] <= 0
                             and read_error["sd_counts"].get("io-error", 0) > 0
                             and mounted_call(read_error, "read-short-file") and error_code(read_error, 223, 255),
        "write_error_branch": write_error["status"] == "passed"
                              and (write_error["written"] <= 0 or write_error["write_close"] < 0)
                              and write_error["sd_counts"].get("io-error", 0) > 0
                              and mounted_call(write_error, "write-new-file") and error_code(write_error, 67, 255),
        "no_card_branch": selected["no_card"]["status"] == "passed"
                          and selected["no_card"]["open_result"] == -1,
        "native_Task8_and_semaphore47": all(task_and_lock(selected[key]) for key in
                                           ("files", "readback", "full", "read_error", "write_error", "no_card")),
        "M2b_cumulative": selected["cumulative"]["status"] == "passed"
                          and selected["cumulative"]["passed"] == selected["cumulative"]["total"] == 22,
        "card_reaches_same_wait_state": selected["cumulative"]["card"]["same_wait_state"],
        "fixed_inputs": selected["guard"]["unchanged_initial_inputs"]
                        and selected["guard"]["changes_prefix_unchanged"] and not selected["guard"]["m2b_mismatches"],
        "current_file_entry_evidence": selected["final_sources"]["status"] == "passed",
        "GXRCE_absent": all(not any(row["name"].rsplit("/", 1)[-1].upper() == "GXRCE.DAT"
                                      for row in metadata["files"])
                            for metadata in (files["medium"], reboot["before"], reboot["after"], back["medium"])),
    }
    current_sd = hashlib.sha256((ROOT / "tools/gxr_emulator/sdcard.py").read_bytes()).hexdigest()
    cases = (files, back, read_error, write_error, boot, selected["no_card"], full)
    checks["final_SD_model_identity"] = all(case["sources"]["tools/gxr_emulator/sdcard.py"] == current_sd for case in cases) \
        and selected["model_checks"]["source_hashes"]["tools/gxr_emulator/sdcard.py"] == current_sd
    result = {"milestone": "M2c", "verdict": "达成" if all(checks.values()) else "部分",
              "checks": checks, "passed": sum(checks.values()), "total": len(checks),
              "selected": {key: getattr(args, key) for key in selected},
              "SD_model_sha256": current_sd,
              "scope": "offline original-firmware behavior under the declared device contract"}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"verdict": result["verdict"], "passed": result["passed"], "total": result["total"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
