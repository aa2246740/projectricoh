#!/usr/bin/env python3
"""Check actual unpublished Git blobs without staging or contacting a remote.

Run with nice -n 15 python3 -I -B. Detailed findings stay under local/r2/.
The original audit_sync.py rules remain in use. Matches report locations only.
An optional local official firmware directory enables byte fingerprint checks.
Passing this scanner does not establish ownership or hardware compatibility.
"""

import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/git_sync/local/r2"
spec = importlib.util.spec_from_file_location("public_sync_rules", Path(__file__).with_name("audit_sync.py"))
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)
START = "7ba9cb4a"
ACTIVE = ("firmware/", "research/g162/", "research/v310b/",
          "research/card_library_gate_r1/", "research/review_lutprobe_r2/")
EXTRA = {
    "dat_magic_text": re.compile(r"GXRCE001"),
    "local_reference": re.compile(r"(?:^|[\s/'\"(])local/"),
    "gps_reference": re.compile(r"GPS|geotag|latitude|longitude", re.I),
    "firmware_word_context": re.compile(
        r"(?i)(?:原字节|重放原|copied from|original bytes|expected bytes).*?(?<![\w])[0-9a-f]{8}(?![\w])"),
    "listing_without_colon": re.compile(
        r"(?i)^\s*(?:0x)?[0-9a-f]{8}\s+(?:[0-9a-f]{4,8}\s+)+.*\b(?:ldi|ld|st|add|sub|cmp|bne|beq|bra|jmp|jl|seth|or3|mv)\b"),
    "gps_coordinate_literal": re.compile(
        r"(?i)(?:GPSLatitude|GPSLongitude|gps_latitude|gps_longitude)[\"']?\s*[:=]\s*[-+]?\d+(?:\.\d+)?"),
}
BYTE_MAGIC = b"GXRCE001"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def literal_bytes(body, suffix):
    """Return Python byte and fromhex literals, not computed firmware output."""
    if suffix != ".py":
        return []
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return []
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, bytes) and len(node.value) >= 8:
            result.append((node.lineno, node.value, "byte_literal"))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == "fromhex" and len(node.args) == 1
              and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            try:
                data = bytes.fromhex(node.args[0].value)
            except ValueError:
                continue
            if len(data) >= 8:
                result.append((node.lineno, data, "fromhex"))
    return result


def official_inputs(directory):
    if directory is None:
        return [], []
    source = ROOT / "scripts/build_drill.py"
    assignment = next(n for n in ast.parse(source.read_text()).body
                      if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "OFFICIAL" for t in n.targets))
    expected = ast.literal_eval(assignment.value)
    images, identities = [], []
    for name, digest in sorted(expected.items()):
        data = (directory / name).read_bytes()
        if sha(data) != digest:
            raise ValueError("official fingerprint input mismatch: " + name)
        images.append(data)
        identities.append({"name": name, "sha256": digest, "size": len(data)})
    return images, identities


def scan_blob(path, oid, mode, data, official=()):
    p = Path(path)
    row = {"path": path, "oid": oid, "sha256": sha(data), "size": len(data), "errors": []}
    parts = set(p.parts[:-1])
    if mode not in {"100644", "100755"}:
        row["errors"].append("non_regular_git_entry")
    if p.parts[0] in {"captures", "artifacts", "sources"} or "local" in parts or any(s.startswith("local_") for s in parts):
        row["errors"].append("private_path")
    if p.suffix.lower() in rules.BINARY and not rules.APPROVED_PNG.fullmatch(path):
        row["errors"].append("binary_or_media_extension")
    if re.fullmatch(r"(?:[ijknq]launch\d+|l\d+firm\d+)", p.name, re.I):
        row["errors"].append("official_firmware_filename")
    if p.name in {"deep_tables.c", "deep_probe.h"} or p.suffix.lower() in {".asm", ".dis", ".disasm"}:
        row["errors"].append("extracted_data_or_listing")
    if len(data) > rules.LIMIT:
        row["errors"].append("larger_than_5MB")
    if data.startswith(BYTE_MAGIC):
        row["errors"].append("dat_header")
    if rules.APPROVED_PNG.fullmatch(path):
        row["approved_chart_png"] = True
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            row["errors"].append("invalid_chart_png")
        return row
    if data.startswith((b"\xff\xd8\xff", b"\x89PNG", b"II*\0", b"MM\0*", b"\x7fELF")):
        row["errors"].append("media_or_executable_signature")
    try:
        body = data.decode("utf-8")
    except UnicodeDecodeError:
        row["errors"].append("non_UTF8_blob")
        return row
    if "\0" in body:
        row["errors"].append("NUL_in_text")
    row["content"] = rules.findings(body, rules.CONTENT)
    row["source"] = rules.source_findings(path, body)
    row["references"] = rules.findings(body, EXTRA)
    table_lines, byte_table = [], False
    for number, line in enumerate(body.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            byte_table = False
        elif "原字节" in line or "original bytes" in line.lower():
            byte_table = True
        elif byte_table and re.search(r"(?<![\w])[0-9a-fA-F]{8}(?![\w])", line):
            table_lines.append(number)
    if table_lines:
        row["references"]["original_byte_table"] = {"count": len(table_lines), "lines": table_lines}
    row["secrets"] = rules.findings(body, rules.SECRETS)
    if row["secrets"]:
        row["errors"].append("secret_pattern")
    if row["references"].get("gps_coordinate_literal"):
        row["errors"].append("literal_GPS_coordinate")
    matches = []
    for line, value, kind in literal_bytes(body, p.suffix.lower()):
        # Plain names, format markers and filler are not firmware instruction samples.
        if len(set(value)) < 4 or (kind == "byte_literal" and all(32 <= b < 127 for b in value)):
            continue
        if any(value in image for image in official):
            matches.append({"line": line, "bytes": len(value), "kind": kind})
    if matches:
        row["official_literal_matches"] = matches
    if official:
        header_hits = 0
        for image in official:
            # Check nonuniform header/payload samples. Full-file hash and format checks are separate.
            samples = [image[o:o + 32] for o in (0, 0x100, 0x200, 0x400)]
            if any(len(x) == 32 and len(set(x)) >= 8 and x in data for x in samples):
                header_hits += 1
        if header_hits:
            row["errors"].append("official_raw_fingerprint")
    return row


def object_entries(ref, base, history):
    refs = [ref]
    if history:
        if ref == "index":
            raise ValueError("history mode requires a commit ref")
        refs = git("rev-list", "--reverse", base + ".." + ref).decode().splitlines()
    selected = {}
    for commit in refs:
        if commit == "index":
            paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0")
            entries = git("ls-files", "--stage", "-z")
        else:
            paths = git("diff", "--name-only", "--diff-filter=ACMR", "-z", base, commit).split(b"\0")
            entries = git("ls-tree", "-r", "-z", commit)
        wanted = {os.fsdecode(p) for p in paths if p}
        for item in entries.split(b"\0"):
            if not item:
                continue
            fields, name = item.split(b"\t", 1)
            path = os.fsdecode(name)
            if path not in wanted:
                continue
            fields = fields.decode().split()
            mode, oid = fields[0], fields[1 if commit == "index" else 2]
            selected[path, oid] = mode
    return selected


def verify(args):
    images, identities = official_inputs(args.official_dir)
    entries = object_entries(args.ref, args.base, args.history)
    payload = "".join(oid + "\n" for path, oid in entries).encode()
    batch = subprocess.run(["git", "-C", str(ROOT), "cat-file", "--batch"], input=payload,
                           capture_output=True, check=True).stdout
    rows, offset = [], 0
    for (path, oid), mode in entries.items():
        end = batch.index(b"\n", offset)
        _, kind, length = batch[offset:end].split()
        length = int(length)
        data = batch[end + 1:end + 1 + length]
        offset = end + 2 + length
        if kind != b"blob":
            raise ValueError("expected blob: " + path)
        rows.append(scan_blob(path, oid, mode, data, images))
    summary = {
        "base": git("rev-parse", args.base).decode().strip(),
        "ref": args.ref if args.ref == "index" else git("rev-parse", args.ref).decode().strip(),
        "history": args.history, "path_versions": len(rows),
        "unique_paths": len({r["path"] for r in rows}),
        "hard_error_versions": sum(bool(r["errors"]) for r in rows),
        "official_literal_match_versions": sum(bool(r.get("official_literal_matches")) for r in rows),
        "firmware_word_context_versions": sum(bool(r.get("references", {}).get("firmware_word_context")) for r in rows),
        "original_byte_table_versions": sum(bool(r.get("references", {}).get("original_byte_table")) for r in rows),
        "listing_versions": sum(bool(r.get("references", {}).get("listing_without_colon")) for r in rows),
        "content_flag_versions": sum(bool(r.get("content") or r.get("source")) for r in rows),
        "reference_versions": {k: sum(bool(r.get("references", {}).get(k)) for r in rows) for k in EXTRA},
        "approved_chart_png_versions": sum(bool(r.get("approved_chart_png")) for r in rows),
        "max_blob_bytes": max((r["size"] for r in rows), default=0),
        "official_inputs": identities,
        "limits": "Pattern and local-byte checks require source review. Header fingerprints are sampled. No hardware or legal acceptance.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    tag = args.tag or ("history" if args.history else args.ref.replace("/", "_"))
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", tag):
        raise ValueError("invalid tag")
    (OUT / (tag + "-blobs.json")).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    (OUT / (tag + "-summary.json")).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"official_inputs", "limits"}}, ensure_ascii=False))
    return bool(summary["hard_error_versions"] or summary["official_literal_match_versions"]
                or summary["firmware_word_context_versions"] or summary["original_byte_table_versions"]
                or summary["listing_versions"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--base", default="origin/main", help="local ref only; no fetch")
    parser.add_argument("--history", action="store_true", help="inspect each unpublished path version, including superseded ones")
    parser.add_argument("--official-dir", type=Path)
    parser.add_argument("--tag")
    raise SystemExit(verify(parser.parse_args()))
