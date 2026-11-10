#!/usr/bin/env python3
"""Rebuild one GXR image from the cached official member plus a public patch.

The rebuilt file contains the official image, so this tool only writes under
the gitignored cache or the task-local directory. With --audit it also checks
that literal replacement bytes do not contain a long exact run from the
official image. Those runs belong in copy hunks.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gxr151


def allowed_output(root, path):
    resolved = path.resolve()
    allowed = [
        (root / "research" / "public_rebuild_r1" / "cache").resolve(),
        (root / "research" / "public_rebuild_r1" / "local").resolve(),
    ]
    return any(resolved == parent or parent in resolved.parents for parent in allowed)


def audit_literals(base, patch):
    window = int(patch.get("copy_min_length") or gxr151.COPY_MIN_LENGTH)
    index = gxr151.build_window_index(base, window)
    runs = []
    for hunk in patch["hunks"]:
        if hunk["op"] != "literal":
            continue
        blob = bytes.fromhex(hunk["new_hex"])
        for blob_offset, official_offset, length in gxr151.embedded_runs(base, index, blob, window):
            runs.append({
                "hunk_offset": hunk["offset"],
                "literal_offset": blob_offset,
                "official_offset": official_offset,
                "length": length,
            })
    longest = max((item["length"] for item in runs), default=0)
    return {"window": window, "embedded_runs": len(runs), "longest_literal_match": longest, "runs": runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--audit", action="store_true", help="reject literals that still contain long official runs")
    args = parser.parse_args()
    root = gxr151.repo_root()
    cache = args.cache or (root / "research" / "public_rebuild_r1" / "cache")
    patch = gxr151.load_patch(args.patch)
    name = patch["target_name"]
    manifest = gxr151.load_member_manifest(root)
    if name not in manifest:
        raise SystemExit("patch target is not one of the 29 official members")
    if patch["base_sha256"] != manifest[name]:
        raise SystemExit("patch base is not the pinned official member")
    member = cache / "gxr-1.51" / name
    if not member.is_file():
        raise SystemExit("missing cached official member; run fetch_official.py first")
    base = member.read_bytes()
    if gxr151.sha256(base) != manifest[name]:
        raise SystemExit("cached member does not match the official manifest")
    rebuilt = gxr151.apply_patch(base, patch)
    counts = gxr151.accounting(patch)
    report = {
        "status": "ok",
        "target_name": name,
        "result_sha256": gxr151.sha256(rebuilt),
        "result_size": len(rebuilt),
        "matches_patch": True,
    }
    report.update(counts)
    if args.audit:
        findings = audit_literals(base, patch)
        report["audit_window"] = findings["window"]
        report["embedded_runs"] = findings["embedded_runs"]
        report["longest_literal_match"] = findings["longest_literal_match"]
        if findings["embedded_runs"]:
            report["status"] = "embedded-official-run"
            report["runs"] = findings["runs"]
            print(json.dumps(report, ensure_ascii=False))
            raise SystemExit(3)
    out = args.out or (cache / "rebuilt" / name)
    if not allowed_output(root, out):
        raise SystemExit("refusing to write a rebuilt image outside the gitignored cache or local directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rebuilt)
    report["out"] = str(out)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
