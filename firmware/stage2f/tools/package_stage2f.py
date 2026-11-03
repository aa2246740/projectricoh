#!/usr/bin/env python3
"""Write the stage 2f package. Does not touch a camera or an SD card.

Stage 2f is stage 2e with only the 03 HC BW type-26 row replaced. Besides the
2e checks against official firmware, this compares the new ilaunch3 with the
stage 2e package byte for byte and fails unless the only differences are the
container checksum and the two 03 tone tables inside the payload.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
BUILD = HERE / "build"
PACKAGE = ROOT / "artifacts/stage2f-packages/stage2f"
OFFICIAL = ROOT / "artifacts/firmware/gxr-1.51/ilaunch3"
STAGE2E_ROOT = ROOT / "artifacts/stage2e-packages/stage2e"
STAGE2E = STAGE2E_ROOT / "candidate/SD_ROOT/ilaunch3"
STAGE2E_LINK = STAGE2E_ROOT / "evidence/manifest.json"
TABLES = ROOT / "research/stage2f/tables_manifest.json"
OFFICIAL_I = "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
OFFICIAL_J = "951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673"
STAGE2E_SHA = "a3e699601cd50e5a97706081962c2956ecac5f060396ed3554bd34fe1c50bb45"
STAGE2E_DAT = "9b04ab6b5fe30c2a59d2b88c3219ffca6220791e7f4c5ba1bbf11b4c2278cb38"
STAGE2E_PAYLOAD = (8060, "0x200546e8")
DATS = ("DEEPISP0.DAT", "DEEPISP1.DAT", "RECIPE20.DAT", "RECIPE21.DAT")
NAMES = ["01 Posi", "02 Nega", "03 HC BW", "04 Std", "05Chrome", "06ClsNeg", "07 PrbA", "08 PrbB"]
PAYLOAD_VMA = 0x2005276C
PAYLOAD_FILE = 0x796C
HC_TABLES = {"03 HC BW.a5": 62, "03 HC BW.b5": 33}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guard(path):
    text = str(path)
    if "RICOH" in text and "DCX" in text:
        raise SystemExit(f"refusing path {text}")


def runs(old, new):
    found = []
    index = 0
    while index < len(old):
        if old[index] == new[index]:
            index += 1
            continue
        end = index + 1
        while end < len(old) and old[end] != new[end]:
            end += 1
        found.append((index, end))
        index = end
    return found


def classify(start, end, hooks):
    if 0x16C <= start and end <= 0x170:
        return "checksum"
    for hook in hooks:
        hook_at = int(hook["file_offset"], 16)
        if hook_at <= start and end <= hook_at + hook["length"]:
            return hook["id"]
    if 0x796C <= start and end <= 0x9900:
        return "payload"
    return "unexpected"


def diff_image(previous, body, hooks):
    regions = []
    for start, end in runs(previous, body):
        points = [start, *[cut for cut in cuts_for(hooks) if start < cut < end], end]
        for piece_start, piece_end in zip(points, points[1:]):
            kind = classify(piece_start, piece_end, hooks)
            if kind == "unexpected":
                raise SystemExit(f"unexpected diff at {piece_start:#x}..{piece_end:#x}")
            regions.append({"file_offset": hex(piece_start), "end": hex(piece_end),
                            "length": piece_end - piece_start, "kind": kind})
    return regions


def cuts_for(hooks):
    cuts = [0x16C, 0x170, 0x796C, 0x9900]
    for hook in hooks:
        hook_at = int(hook["file_offset"], 16)
        cuts.extend((hook_at, hook_at + hook["length"]))
    return sorted(set(cuts))


def file_list(candidate, official_files):
    rows = []
    for name in sorted(official_files):
        same = candidate[name] == official_files[name]
        rows.append({"name": name, "status": "identical" if same else "differs",
                     "sha256": sha(candidate[name])})
    for name in DATS:
        rows.append({"name": name, "status": "added", "sha256": sha(candidate[name])})
    return rows


def versus_name(rows, name):
    return next(row["status"] for row in rows if row["name"] == name)


def hc_spans(symbols, tables):
    """VMA and file spans of the two 03 tone tables in the new link."""
    spans = {}
    for label, length in HC_TABLES.items():
        symbol = tables["table_symbols"][label]
        if symbol != {"03 HC BW.a5": "table_3_0", "03 HC BW.b5": "table_3_1"}[label]:
            raise SystemExit(f"{label} is linked as {symbol}; the 03 table is shared")
        vma = int(symbols[symbol], 16)
        spans[label] = {"symbol": symbol, "vma": vma, "vma_end": vma + length,
                        "file_offset": PAYLOAD_FILE + vma - PAYLOAD_VMA,
                        "file_end": PAYLOAD_FILE + vma - PAYLOAD_VMA + length, "length": length}
    return spans


def stage2e_diff(previous, body, hooks, spans):
    """Every changed byte versus 2e must be the checksum or inside a 03 table."""
    regions = diff_image(previous, body, hooks)
    detailed = []
    for region in regions:
        start, end = int(region["file_offset"], 16), int(region["end"], 16)
        entry = dict(region)
        if region["kind"] == "payload":
            owner = [label for label, span in spans.items()
                     if span["file_offset"] <= start and end <= span["file_end"]]
            if len(owner) != 1:
                raise SystemExit(f"payload diff {start:#x}..{end:#x} is outside the 03 tables")
            entry["kind"] = f"payload:{spans[owner[0]]['symbol']}"
            entry["table"] = owner[0]
            entry["vma"] = hex(PAYLOAD_VMA + start - PAYLOAD_FILE)
            entry["vma_end"] = hex(PAYLOAD_VMA + end - PAYLOAD_FILE)
        elif region["kind"] != "checksum":
            raise SystemExit(f"diff versus stage 2e in {region['kind']} at {start:#x}")
        detailed.append(entry)
    if not any(entry["kind"] == "checksum" for entry in detailed):
        raise SystemExit("checksum did not change versus stage 2e")
    for label in spans:
        if not any(entry.get("table") == label for entry in detailed):
            raise SystemExit(f"{label} did not change versus stage 2e")
    return detailed


def main():
    for path in (HERE, BUILD, PACKAGE, OFFICIAL, STAGE2E, ROOT / "artifacts/firmware/gxr-1.51"):
        guard(path)
    audit = load("stage2f_audit", HERE / "tools/audit_image.py")
    builder = load("stage2f_candidate", HERE / "tools/build_candidate.py")
    routing = load("stage2f_routing", HERE / "tests/test_ui_routing.py")
    audit_log = subprocess.run(
        [sys.executable, "-I", str(HERE / "tests/test_audit_image.py"), "--build", str(BUILD)],
        cwd=ROOT, text=True, capture_output=True)
    (BUILD / "image-audit-tests.txt").write_text(audit_log.stdout + audit_log.stderr)
    if audit_log.returncode != 0:
        raise SystemExit(audit_log.stdout + audit_log.stderr)
    body, report = builder.create_candidate(BUILD)
    image_audit = audit.audit(*audit.read_inputs(BUILD))
    if sha(body) != image_audit["candidate_image_sha256"]:
        raise SystemExit("candidate bytes disagree with the audit")
    (BUILD / "image_audit.json").write_text(json.dumps(image_audit, indent=2) + "\n")
    ui = routing.check(body)
    if not ui["passed"] or len(ui["cases"]) != 25:
        raise SystemExit(f"dispatcher failed: {len(ui['failures'])}")
    (BUILD / "ui_routing.json").write_text(json.dumps(ui, indent=2) + "\n")

    official = OFFICIAL.read_bytes()
    jlaunch = (ROOT / "artifacts/firmware/gxr-1.51/jlaunch3").read_bytes()
    previous = STAGE2E.read_bytes()
    if sha(official) != OFFICIAL_I or sha(jlaunch) != OFFICIAL_J or sha(previous) != STAGE2E_SHA:
        raise SystemExit("baseline firmware hash changed")
    if body[0x26F8FC:0x26F900] != b"\xd2\xc0\x20\x5e" or official[0x26F8FC:0x26F900] != body[0x26F8FC:0x26F900]:
        raise SystemExit("dispatcher bytes changed")
    if body[0x32C634:0x32C660] != official[0x32C634:0x32C660]:
        raise SystemExit("jump table changed")
    if body[0x9900:0x9A00] != b"\xff" * 256:
        raise SystemExit("probe tail is not 0xFF")
    hooks = json.loads((BUILD / "hooks.json").read_text())["hooks"]
    if body[0x1E47AC:0x1E47AD] != b"\x08":
        raise SystemExit("ADJ count is not 8")

    linked = json.loads((BUILD / "manifest.json").read_text())
    previous_link = json.loads(STAGE2E_LINK.read_text())
    tables = json.loads(TABLES.read_text())
    payload_end = int(linked["payload_end"], 16)
    if (linked["payload_bytes"], linked["payload_end"]) != STAGE2E_PAYLOAD:
        raise SystemExit(f"payload size changed: {linked['payload_bytes']} ending {linked['payload_end']}")
    if linked["symbols"] != previous_link["symbols"]:
        moved = sorted(name for name in set(linked["symbols"]) | set(previous_link["symbols"])
                       if linked["symbols"].get(name) != previous_link["symbols"].get(name))
        raise SystemExit(f"symbol layout differs from stage 2e: {moved}")
    stage2e_hooks = json.loads((STAGE2E_ROOT / "evidence/hooks.json").read_text())["hooks"]
    if [(h["id"], h["new_bytes"]) for h in hooks] != [(h["id"], h["new_bytes"]) for h in stage2e_hooks]:
        raise SystemExit("hook bytes differ from stage 2e")
    spans = hc_spans(linked["symbols"], tables)
    linked_hc = b""
    for label, span in spans.items():
        blob = body[span["file_offset"]:span["file_end"]]
        if sha(blob) != tables["table_sha256"][label]:
            raise SystemExit(f"{label} bytes in ilaunch3 differ from the tables manifest")
        linked_hc += blob
    if sha(linked_hc) != tables["hc_source"]["curve_sha256"]:
        raise SystemExit("linked 03 curve differs from the HC source curve")

    regions = diff_image(official, body, hooks)
    stage2e_regions = stage2e_diff(previous, body, hooks, spans)
    (BUILD / "diff-vs-official.json").write_text(json.dumps({
        "baseline_sha256": OFFICIAL_I,
        "candidate_sha256": sha(body),
        "changed_bytes": sum(item["length"] for item in regions),
        "regions": regions,
    }, indent=2) + "\n")
    hc_table_spans = {
        label: {"symbol": span["symbol"], "vma": hex(span["vma"]), "vma_end": hex(span["vma_end"]),
                "file_offset": hex(span["file_offset"]), "file_end": hex(span["file_end"]),
                "length": span["length"],
                "sha256": tables["table_sha256"][label],
                "stage2e_sha256": sha(previous[span["file_offset"]:span["file_end"]])}
        for label, span in spans.items()
    }
    (BUILD / "diff-vs-stage2e.json").write_text(json.dumps({
        "baseline_sha256": STAGE2E_SHA,
        "candidate_sha256": sha(body),
        "changed_bytes": sum(item["length"] for item in stage2e_regions),
        "regions": stage2e_regions,
        "hc_tables": hc_table_spans,
    }, indent=2) + "\n")

    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    files, _, payload, _ = audit.read_inputs(BUILD)
    candidate = dict(files)
    candidate["ilaunch3"] = body
    for name in DATS:
        candidate[name] = (HERE / "examples" / name).read_bytes()
        if candidate[name] != (STAGE2E_ROOT / "candidate/SD_ROOT" / name).read_bytes():
            raise SystemExit(f"{name} differs from the stage 2e package")
    if len(files) != 29 or {sha(candidate[name]) for name in DATS} != {STAGE2E_DAT}:
        raise SystemExit("component or DAT inventory mismatch")
    versus = file_list(candidate, files)
    if sum(1 for row in versus if row["status"] == "differs") != 1 or versus_name(versus, "ilaunch3") != "differs":
        raise SystemExit("official file diff is not exactly ilaunch3")
    for name, data in files.items():
        if name != "ilaunch3" and data != (STAGE2E_ROOT / "candidate/SD_ROOT" / name).read_bytes():
            raise SystemExit(f"{name} differs from the stage 2e package")

    def write_tree(root, blobs):
        root.mkdir(parents=True)
        for name, data in sorted(blobs.items()):
            guard(root / name)
            (root / name).write_bytes(data)
            if (root / name).read_bytes() != data:
                raise SystemExit(f"readback failed for {name}")

    write_tree(PACKAGE / "candidate/SD_ROOT", candidate)
    write_tree(PACKAGE / "recovery-official-1.51/SD_ROOT", files)
    evidence = PACKAGE / "evidence"
    evidence.mkdir()
    names = (
        "payload.bin", "payload.elf", "payload.map", "payload-disasm.txt", "payload-headers.txt",
        "manifest.json", "hooks.json", "verification.json", "abi-tests.json", "abi-results.txt",
        "candidate_verification.json", "host-results.txt", "sanitizers-results.txt",
        "tools-results.txt", "image-audit-tests.txt", "image_audit.json", "ui_routing.json",
        "diff-vs-official.json", "diff-vs-stage2e.json",
    )
    for name in names:
        (evidence / name).write_bytes((BUILD / name).read_bytes())
    (evidence / "tables_manifest.json").write_bytes(TABLES.read_bytes())
    (evidence / "files-vs-official.json").write_text(json.dumps(versus, indent=2) + "\n")
    readme = """# stage2f

Host-verified candidate. The camera has not been flashed.

Stage 2e with one change: the 03 HC BW type-26 tone row is the GR IV
high-contrast B&W candidate instead of GXR native row 20. Everything else,
including 07 PrbA and 08 PrbB, is byte-identical to stage 2e.

Eight rows: 01 Posi, 02 Nega, 03 HC BW, 04 Std, 05Chrome, 06ClsNeg, 07 PrbA, 08 PrbB.
Slots 9..16 are empty. The ADJ count byte is 0x08. Category 0 and 4 still apply;
every other category conflicts.

candidate/SD_ROOT has the 29 firmware files plus DEEPISP0.DAT, DEEPISP1.DAT, RECIPE20.DAT and RECIPE21.DAT.
The four DATs are byte-identical to stage 2e.
recovery-official-1.51/SD_ROOT has the 29 official 1.51 files.
jlaunch3 is byte-identical to official.

Check the tree with `shasum -a 256 -c SHA256SUMS` from this directory.
"""
    (PACKAGE / "README.md").write_text(readme)
    verification = json.loads((BUILD / "verification.json").read_text())
    audit_cases = int(re.search(r"Ran (\d+) tests", audit_log.stdout + audit_log.stderr)[1])
    manifest = {
        "schema": "stage2f-v1",
        "package": "stage2f",
        "status": "HOST_VERIFIED_CAMERA_NOT_RUN",
        "camera_executed": False,
        "sd_accessed": False,
        "change_vs_stage2e": "03 HC BW type-26 row only (GR IV candidate replaces native row 20)",
        "candidate_ilaunch3_sha256": sha(body),
        "official_ilaunch3_sha256": sha(official),
        "official_jlaunch3_sha256": sha(jlaunch),
        "stage2e_ilaunch3_sha256": sha(previous),
        "stage2e_ilaunch3_unchanged": sha(previous) == STAGE2E_SHA,
        "official_inputs_unchanged": True,
        "jlaunch3_byte_identical_to_official": candidate["jlaunch3"] == jlaunch,
        "other_components_equal_official": 28,
        "recovery_files_equal_official": 29,
        "checksum": image_audit["checksum"],
        "checksum_phase": 0,
        "payload": {
            "bytes": len(payload),
            "sha256": sha(payload),
            "base": "0x2005276c",
            "end": hex(payload_end),
            "probe_tail": "0x20054700..0x20054800",
            "probe_tail_is_ff": True,
            "free_bytes_before_probe": 0x20054700 - payload_end,
            "size_equal_stage2e": True,
            "symbols_equal_stage2e": True,
        },
        "hc_curve_sha256": tables["hc_source"]["curve_sha256"],
        "hc_source": {key: tables["hc_source"][key] for key in ("path", "key", "json_sha256")},
        "hc_tables": hc_table_spans,
        "dat_sha256": {name: sha(candidate[name]) for name in DATS},
        "dat_equal_stage2e": True,
        "names": NAMES,
        "adj_count": 8,
        "deep_slots": [1, 2, 3, 5, 6, 7, 8],
        "files_vs_official": versus,
        "diff_vs_official": regions,
        "diff_vs_stage2e": stage2e_regions,
        "tests": {
            "host_cases": verification["host"][0]["cases"],
            "sanitizer_cases": verification["host"][1]["cases"],
            "abi_model_cases": verification["abi_model_cases"],
            "tool_cases": verification["tool_cases"],
            "image_audit_cases": audit_cases,
            "dispatcher_cases": len(ui["cases"]),
            "dispatcher_passed": True,
            "protected_update_windows": report["protected_update_windows_count"],
            "rejections": [item["case"] for item in verification["rejections"]],
        },
    }
    (PACKAGE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    manifest["files_sha256"] = {
        str(path.relative_to(PACKAGE)): sha(path.read_bytes())
        for path in sorted(PACKAGE.rglob("*")) if path.is_file() and path.name != "manifest.json"
    }
    (PACKAGE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    sums = "".join(
        f"{sha(path.read_bytes())}  {path.relative_to(PACKAGE)}\n"
        for path in sorted(PACKAGE.rglob("*")) if path.is_file() and path.name != "SHA256SUMS")
    (PACKAGE / "SHA256SUMS").write_text(sums)
    checked = subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=PACKAGE, text=True, capture_output=True)
    if checked.returncode != 0:
        raise SystemExit(checked.stdout + checked.stderr)
    (HERE / "hooks.json").write_bytes((BUILD / "hooks.json").read_bytes())
    print(json.dumps({
        "candidate": sha(body),
        "checksum": image_audit["checksum"],
        "payload_bytes": len(payload),
        "payload_end": hex(payload_end),
        "free_before_probe": 0x20054700 - payload_end,
        "regions_vs_official": [(item["kind"], item["length"]) for item in regions],
        "regions_vs_stage2e": [(item["kind"], item["file_offset"], item["end"]) for item in stage2e_regions],
        "hc_curve_sha256": tables["hc_source"]["curve_sha256"],
        "dispatcher": len(ui["cases"]),
        "windows": report["protected_update_windows_count"],
        "shasum": "ok",
    }))


if __name__ == "__main__":
    main()
