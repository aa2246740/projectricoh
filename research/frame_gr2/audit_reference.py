#!/usr/bin/env python3
"""Verify the saved public FRAME-GR2 source snapshot without running its code."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(source_dir):
    repo = json.loads((source_dir / "repository.json").read_text())
    commit = json.loads((source_dir / "commit-main.json").read_text())
    tree = json.loads((source_dir / "tree-main.json").read_text())
    release = json.loads((source_dir / "release-latest.json").read_text())
    readme = (source_dir / "README.md").read_bytes()
    if repo["full_name"] != "Lyle-xub/FRAME-GR2":
        raise ValueError("The snapshot belongs to another repository")
    if tree.get("truncated") or tree["sha"] != commit["commit"]["tree"]["sha"]:
        raise ValueError("The saved tree is truncated or belongs to another commit")
    readme_entry = next(item for item in tree["tree"] if item["path"] == "README.md")
    blob_hash = hashlib.sha1(b"blob " + str(len(readme)).encode() + b"\0" + readme).hexdigest()
    if readme_entry["sha"] != blob_hash:
        raise ValueError("The README does not match the saved Git tree")
    firmware = next(item for item in release["assets"] if item["name"] == "FRAME-GR2-WN3-Firmware.zip")
    sums_path = source_dir / "SHA256SUMS.txt"
    sums = dict((name.lstrip("*"), value) for value, name in
                (line.split(maxsplit=1) for line in sums_path.read_text().splitlines() if line.strip()))
    if firmware["digest"] != "sha256:" + sums[firmware["name"]]:
        raise ValueError("GitHub asset digest and the author's checksum list disagree")
    checksum_asset = next(item for item in release["assets"] if item["name"] == "SHA256SUMS.txt")
    if checksum_asset["digest"] != "sha256:" + sha256(sums_path):
        raise ValueError("The saved checksum list does not match the GitHub asset digest")
    return {
        "repository": repo["html_url"],
        "commit": commit["sha"],
        "tree_sha": tree["sha"],
        "public_files": [item["path"] for item in tree["tree"] if item["type"] == "blob"],
        "readme_git_blob_matches": True,
        "release_url": release["html_url"],
        "release_tag": release["tag_name"],
        "firmware_asset": {key: firmware[key] for key in ("name", "size", "digest", "browser_download_url")},
        "author_checksum_and_asset_digest_agree": True,
        "source_sha256": {path.name: sha256(path) for path in sorted(source_dir.iterdir()) if path.is_file()},
        "limits": [
            "Checksums identify these published files; they do not prove camera compatibility or safe flashing.",
            "README feature and RAW export claims are not independent validation of firmware processing.",
            "This audit reads only saved source metadata and does not execute apps or camera firmware."
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("research/frame_gr2/sources"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.sources.resolve() or args.sources.resolve() in args.output.resolve().parents:
        parser.error("Write the audit JSON outside the saved input directory")
    result = audit(args.sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"public_files": result["public_files"], "readme_git_blob_matches": True,
                      "author_checksum_and_asset_digest_agree": True, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
