#!/usr/bin/env python3
"""Inventory public-sync candidates without staging, deleting, or using the network.

Run with /usr/bin/python3 -I -B. Findings contain rule names and line numbers,
never matched secret values. A human must review content findings before staging.
"""

import argparse
import ast
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "research/git_sync/local"
LIMIT = 5_000_000
BASE = "ae01c96c97be1d6edfa82d22e3109891dd906d5b"
APPROVED_PNG = re.compile(r"research/chart_v2/pages/0[0-6]_(?:white|chart)\.png\Z")
GENERATED = {
    "candidate", "baseline", "variants", "options", "containers", "acceptance",
    "decode", "disasm", "disassembly", "native", "native-static", "native_harness",
    "codegen", "rebuild", "build", "host", "runs", "run", "image", "isolated",
    "history", "evidence", "command-logs", "commands", "logs", "previous_delta",
    "diff-decode", "sections", "segments", "prefix", "install", "downloads",
    "node_modules", ".venv", "venv", "__pycache__", ".git",
}
BINARY = {
    ".dat", ".bin", ".elf", ".dng", ".jpg", ".jpeg", ".raw", ".o", ".a",
    ".dylib", ".so", ".exe", ".dll", ".pyc", ".zip", ".gz", ".xz", ".z",
    ".tar", ".img", ".dmg", ".pdf", ".png", ".webp", ".tif", ".tiff",
}
TEXT = {
    ".py", ".c", ".h", ".ld", ".s", ".inc", ".sh", ".md", ".tsv", ".html",
    ".mjs", ".js", ".json", ".txt", ".csv", ".yml", ".yaml", ".toml", ".ini",
    ".cfg", ".patch", ".diff", ".asm", ".dis", ".disasm", ".jsonl", ".xml",
}
CONTENT = {
    "deep_tables_reference": re.compile(r"deep_tables|deep_probe\.h", re.I),
    "ricoh_table_language": re.compile(
        r"stock.{0,35}(?:table|curve|recipe|matrix|bytes)|"
        r"(?:table|curve|matrix).{0,35}(?:extracted|dumped|stock)|"
        r"原厂.{0,15}(?:字节|矩阵|曲线|表)|提取.{0,15}(?:参数|曲线|矩阵|表)|"
        r"fitted.{0,30}(?:parameter|coeff)|拟合.{0,15}(?:参数|系数)", re.I),
    "hex_byte_sequence": re.compile(r"(?:0x[0-9a-f]{2}\s*,\s*){8,}|"
                                    r"(?:\\x[0-9a-f]{2}){8,}", re.I),
    "hex_string": re.compile(r"(?:fromhex|unhexlify)\s*\(\s*['\"][0-9a-f\s]{16,}", re.I),
    "numeric_array": re.compile(r"(?<![\w.])(?:[-+]?\d{1,12}(?:\.\d{1,16})?(?:[eE][-+]?\d{1,3})?\s*,\s*){16,}"),
    "listing": re.compile(r"^\s*(?:0x)?[0-9a-f]{6,16}\s*:\s*(?:[0-9a-f]{2,8}\s+){1,}", re.I | re.M),
    "generated_assembly": re.compile(r"\.(?:file\s+\d|loc\s+\d|ident\s)|^\s*\.L(?:FB|FE|VL|BE|BB)\d", re.M),
    "embedded_byte_dump": re.compile(r"(?:before|original|stock|expected|old|bytes|hex)[\w\"'\s]{0,120}[:=]\s*"
                                     r"(?:bytes\.fromhex\()?\s*['\"][0-9a-f]{16,}['\"]", re.I),
}
SECRETS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "service_token": re.compile(r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16})\b"),
    "credential_url": re.compile(r"https?://[^\s/@:]+:[^\s/@]{6,}@", re.I),
    "credential_assignment": re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd)"
        r"\s*[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_+/.=-]{12,}[\"']"),
}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def path_reason(path, size, mode):
    p = Path(path)
    parts = p.parts
    low = path.lower()
    if stat.S_ISLNK(mode):
        return "unsure", "符号链接，未沿链接读取"
    if stat.S_ISDIR(mode):
        return "keep-local", "独立嵌套仓库或目录，不作为主仓子模块提交"
    if size > LIMIT:
        return "keep-local", "文件超过 5 MB"
    if parts[0] in {"artifacts", "captures", "sources", "tools", "Scratch", "scratch"}:
        return "keep-local", "仓库约定的本地资料或输出目录"
    if "local" in parts or any(s.lower().startswith("local_") for s in parts):
        return "keep-local", "local 目录中的本地数据"
    if "SD_ROOT" in parts or re.match(r"(?:i|j|k|n|q)launch|l0.*firm", p.name, re.I):
        return "keep-local", "原厂固件文件或打包卡目录"
    if p.name in {"deep_tables.c", "deep_probe.h"}:
        return "keep-local", "Ricoh 提取的表或探针数据"
    if p.suffix.lower() in BINARY:
        if APPROVED_PNG.fullmatch(path):
            return "review", "自编纯色测试图，需核对来源和哈希"
        return "keep-local", "二进制、照片、归档或生成图片"
    if parts[0] == "firmware" and len(parts) > 1 and parts[1].startswith("package_"):
        return "keep-local", "固件卡包目录，保留整个交付包在本机"
    if any(s in GENERATED or s.startswith(("build-", "previous-", "evidence_")) for s in parts[:-1]):
        return "keep-local", "生成、复制验证或工具链输出目录"
    if any(s in p.name.lower() for s in ("disasm", "disassembly", "decompil")) or p.suffix.lower() in {".dis", ".disasm", ".asm"}:
        return "keep-local", "反汇编或反编译清单"
    if p.suffix.lower() in {".log", ".stdout", ".stderr", ".su", ".map", ".lock"}:
        return "keep-local", "可重建运行日志、映射或锁文件"
    if p.suffix.lower() in TEXT or p.name in {"Makefile", ".gitignore", "SHA256SUMS"}:
        return "review", "文本候选，待内容和来源审核"
    return "unsure", "格式或来源未确认"


def findings(text, rules):
    result = {}
    for name, pattern in rules.items():
        count, lines = 0, set()
        # Bound long generated lines. Their presence is separately a content flag.
        for line_number, line in enumerate(text.splitlines(), 1):
            if rules is CONTENT and len(line) > 4096:
                result.setdefault("long_generated_line", {"count": 0, "lines": []})
                if name == next(iter(rules)):
                    result["long_generated_line"]["count"] += 1
                    if len(result["long_generated_line"]["lines"]) < 80:
                        result["long_generated_line"]["lines"].append(line_number)
                line = line[:4096]
            for match in pattern.finditer(line):
                count += 1
                if len(lines) < 80:
                    lines.add(line_number)
        if count:
            result[name] = {"count": count, "lines": sorted(lines)}
    return result


def source_findings(path, body):
    result = {}
    if Path(path).suffix.lower() not in {".py", ".c", ".h", ".inc", ".s", ".md", ".html", ".js", ".mjs"}:
        return result
    for match in re.finditer(r'''["']([0-9a-fA-F]{8,})["']''', body):
        value = match.group(1)
        if not value.isdigit() and len(value) not in {40, 64, 128}:
            result.setdefault("quoted_hex", []).append(body.count("\n", 0, match.start()) + 1)
    for name, pattern in (
        ("spaced_byte_dump", r"(?i)(?:\b[0-9a-f]{2}[ \t]+){8,}[0-9a-f]{2}\b"),
        ("numeric_initializer", r"\{\s*(?:0x[0-9a-fA-F]{1,8}|[-+]?\d+(?:\.\d+)?)\s*,(?:[\s\dxa-fA-FeE+.,-]){24,}\}"),
    ):
        lines = [body.count("\n", 0, m.start()) + 1 for m in re.finditer(pattern, body)]
        if lines:
            result[name] = lines[:100]
    if Path(path).suffix == ".py":
        try:
            tree = ast.parse(body)
        except SyntaxError:
            result["syntax_unconfirmed"] = [1]
        else:
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, bytes) and len(node.value) >= 8:
                    result.setdefault("byte_literal", []).append(node.lineno)
                if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) >= 16 and all(
                    isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) for n in node.elts
                ):
                    result.setdefault("numeric_literal_array", []).append(node.lineno)
    return result


def scan():
    initial = json.loads((LOCAL / "initial-paths.json").read_text())
    overrides_path = LOCAL / "decisions.json"
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    output, reviews, secret_hits = [], [], []
    for number, item in enumerate(initial, 1):
        if number % 1000 == 0:
            print("inventoried", number, flush=True)
        path = item["path"].rstrip("/")
        target = ROOT / path
        try:
            st = target.lstat()
        except FileNotFoundError:
            output.append({**item, "classification": "unsure", "reason": "清单后文件已不存在", "size": 0})
            continue
        decision, reason = path_reason(path, st.st_size, st.st_mode)
        row = {**item, "path": path, "size": st.st_size, "classification": decision, "reason": reason}
        if decision in {"review", "unsure"} and stat.S_ISREG(st.st_mode) and st.st_size <= LIMIT:
            data = target.read_bytes()
            row["sha256"] = hashlib.sha256(data).hexdigest()
            try:
                body = data.decode("utf-8")
            except UnicodeDecodeError:
                row.update(classification="unsure", reason="非 UTF-8 文本，需人工确认格式和来源")
            else:
                row["content_findings"] = findings(body, CONTENT)
                row["secret_findings"] = findings(body, SECRETS)
                if row["secret_findings"]:
                    secret_hits.append(row)
        if path in overrides:
            override = overrides[path]
            if override.get("sha256") and row.get("sha256") != override["sha256"]:
                row.update(classification="unsure", reason="人工审核后内容变化，需重审")
            else:
                row.update(classification=override["classification"], reason=override["reason"])
        if row["classification"] in {"review", "unsure"}:
            reviews.append(row)
        output.append(row)
    (LOCAL / "inventory.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in output))
    (LOCAL / "review.json").write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + "\n")
    (LOCAL / "secret-findings.json").write_text(json.dumps(secret_hits, ensure_ascii=False, indent=2) + "\n")
    counts = collections.Counter(x["classification"] for x in output)
    print(json.dumps({"count": len(output), "classifications": counts, "secret_candidate_files": len(secret_hits)}, ensure_ascii=False))
    print("Review and complete inventory are under research/git_sync/local/.")


def verify(ref, base):
    """Read actual Git blobs. This does not trust the worktree or the stage list."""
    if ref == "index":
        paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0")
    else:
        paths = git("diff", "--name-only", "--diff-filter=ACMR", "-z", base, ref).split(b"\0")
    # One batch reads the actual Git objects, without thousands of child processes.
    entries = {}
    raw_entries = git("ls-files", "--stage", "-z") if ref == "index" else git("ls-tree", "-r", "-z", ref)
    for entry in raw_entries.split(b"\0"):
        if not entry:
            continue
        fields, raw_path = entry.split(b"\t", 1)
        fields = fields.split()
        entries[os.fsdecode(raw_path)] = (fields[0], fields[1] if ref == "index" else fields[2])
    selected = [os.fsdecode(p) for p in paths if p]
    payload = b"".join(entries[path][1] + b"\n" for path in selected)
    batch = subprocess.run(["git", "-C", str(ROOT), "cat-file", "--batch"], input=payload,
                           capture_output=True, check=True).stdout
    result, offset = [], 0
    for path in selected:
        end = batch.index(b"\n", offset)
        oid, kind, raw_size = batch[offset:end].split()
        size = int(raw_size)
        data = batch[end + 1:end + 1 + size]
        offset = end + size + 2
        if kind != b"blob" or entries[path][0] not in {b"100644", b"100755"}:
            raise ValueError("non-regular Git entry: " + path)
        decision, reason = path_reason(path, len(data), stat.S_IFREG)
        row = {"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if decision == "keep-local":
            row["path_error"] = reason
        if APPROVED_PNG.fullmatch(path):
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                row["format_error"] = "not a PNG"
            result.append(row)
            continue
        if path == "decisions.tsv":
            row["path_error"] = "完整新增记录含原厂参数或字节，本轮禁止暂存"
        try:
            body = data.decode("utf-8")
        except UnicodeDecodeError:
            row["format_error"] = "non-UTF-8"
        else:
            row["content_findings"] = findings(body, CONTENT)
            row["source_findings"] = source_findings(path, body)
            row["secret_findings"] = findings(body, SECRETS)
        result.append(row)
    dest = LOCAL / ("verify-" + ref.replace("/", "_") + ".json")
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    errors = sum(bool(x.get("path_error") or x.get("format_error") or x.get("secret_findings")) for x in result)
    print(json.dumps({"ref": ref, "files": len(result), "hard_errors": errors,
                      "content_flagged_files": sum(bool(x.get("content_findings") or x.get("source_findings")) for x in result)}))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["scan", "verify"])
    parser.add_argument("--ref", default="index")
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    if args.command == "scan":
        scan()
    else:
        verify(args.ref, args.base)
