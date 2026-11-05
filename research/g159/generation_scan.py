"""Inspect the real GXRCE001 DAT header and stream source declarations with rg."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true", help="Retain completed binary scan; recheck source coverage")
    parser.add_argument("--backup-tag", default="initial-stdin")
    args = parser.parse_args()
    assert args.backup_tag and all(c.isascii() and (c.isalnum() or c in '-_') for c in args.backup_tag)
    C.setup()
    C.gate("correct-DAT-magic-generation-scan")
    destination = C.LOCAL / "generation-scan.json"
    if args.source_only:
        previous = json.loads(destination.read_text())
        historical = C.LOCAL / ("generation-scan-" + args.backup_tag + ".json")
        assert not historical.exists(), "Keep prior generation scan evidence"
        historical.write_bytes(destination.read_bytes())
        paths = [None] * previous['binary_paths_examined']
        headers = previous['DAT_headers']
    else:
        assert not destination.exists(), "Keep prior generation scan evidence"
    excludes = ["-g", "!.git", "-g", "!.venv", "-g", "!node_modules", "-g", "!__pycache__",
                "-g", "!research/g159/**", "-g", "!firmware/engine_v71_g159/**",
                "-g", "!firmware/package_v310_g159*/**"]
    query = ["rg", "--files", "--hidden", "--no-ignore", *excludes, "-g", "*.DAT", "-g", "*.dat", "-g", "*.bin"]
    if not args.source_only:
        paths = subprocess.check_output(query, cwd=C.ROOT, text=True).splitlines()
        headers = []
    failures = []
    for i, name in enumerate([] if args.source_only else paths):
        path = C.ROOT / name
        with path.open("rb") as source:
            header = source.read(256)
        if len(header) == 256 and header[:8] == b"GXRCE001":
            headers.append(dict(path=name, generation=int.from_bytes(header[28:32], "big"),
                                bytes=path.stat().st_size))
        if (i + 1) % 10000 == 0:
            print("BINARY_HEADERS", i + 1, "DAT", len(headers), flush=True)
    for profile in ("test", "release"):
        path = str(C.baseline_dat(profile).relative_to(C.ROOT))
        assert any(row["path"] == path and row["generation"] == 158 for row in headers), "Positive DAT scan control"
    assert any("lutprobe" in row["path"] for row in headers), "Probe coverage control"
    pattern = (r"(?:build_number|generation|GENERATION|ENG_GEN|build)"
               r"[^\n,;]{0,32}\b(?:159|0[xX]9[fF])\b|\bg159\b|\bv71_g159\b")
    query = ["rg", "-n", "--hidden", "--no-ignore",
             "-g", "*.json", "-g", "MANIFEST", "-g", "*.py", "-g", "*.c", "-g", "*.h",
             "-g", "*.md", "-g", "*.txt", "-g", "*.toml", "-g", "*.yml", *excludes, pattern, "."]
    process = subprocess.run(query, cwd=C.ROOT, text=True, capture_output=True, stdin=subprocess.DEVNULL)
    assert process.returncode in (0, 1), process.stderr
    (C.LOCAL / "generation-source-matches.txt").write_text(process.stdout)
    matches = []
    for line in process.stdout.splitlines():
        name, number, text = line.split(":", 2)
        matches.append(dict(path=str(Path(name)), line=int(number), text=text[:1000]))
        if (Path(name).name == "MANIFEST" or Path(name).suffix == ".json") and re.search(
                r'"(?:generation|build_number)"\s*:\s*159\b', text):
            failures.append(name)
    assert any(x['path'].endswith('research/lunch_g157_r1/REPORT_R2.md') for x in matches), 'Positive source scan control'
    prior_host_probe = C.ROOT / 'research/exif_recipe_tag_r1/local/format_probe.py'
    prior_result = prior_host_probe.with_name('format-results.json')
    sealed = prior_host_probe.with_name('SHA256SUMS').read_text()
    assert C.sha(prior_host_probe.read_bytes()) + '  ' + str(prior_host_probe.relative_to(C.ROOT)) in sealed
    assert C.sha(prior_result.read_bytes()) + '  ' + str(prior_result.relative_to(C.ROOT)) in sealed
    assert json.loads(prior_result.read_text())['status'] == 'PASS'
    fixture_uses = [row for row in matches if row['path'] == str(prior_host_probe.relative_to(C.ROOT))
                    and re.search(r't\.generation\s*=\s*159\b', row['text'])]
    assert fixture_uses, 'Positive prior-probe generation control'
    binary_status = "PASS" if not failures and not any(x["generation"] == 159 for x in headers) else "FAIL_GENERATION_IN_USE"
    result = dict(status="BLOCKED_PRIOR_HOST_PROBE_FIXTURE" if binary_status == 'PASS' else binary_status,
                  DAT_scan_status=binary_status, host_probe_generation159_uses=fixture_uses,
                  host_probe_sha256=C.sha(prior_host_probe.read_bytes()),
                  host_probe_result_sha256=C.sha(prior_result.read_bytes()),
                  host_probe_scope='Host EXIF serialization fixtures, not a DAT or a camera probe image. Owner forbids reuse by any probe.',
                  actual_DAT_magic="GXRCE001", positive_controls="Both g158 delivered DATs and lutprobe DATs are present",
                  binary_paths_examined=len(paths), DAT_headers=headers, generation159_manifests=failures,
                  generation159_packages=[r for r in headers if r["generation"] == 159],
                  source_mentions=matches, no_size_cutoff_for_source_scan=True,
                  source_scan_command=query, source_positive_control='Known future g159 candidate report must match', DAT_created=False)
    C.save(destination, result)
    print(json.dumps(dict(status=result["status"], binary_paths=len(paths), DAT_headers=len(headers),
                          source_matches=len(matches), generation159_DATs=len(result["generation159_packages"]))))


if __name__ == "__main__":
    main()
