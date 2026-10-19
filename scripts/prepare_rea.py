#!/usr/bin/env python3
"""Verify and unpack REA; prepare native-only dependencies without another Playwright."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=Path("artifacts/downloads/rea-npm-metadata.json"))
    parser.add_argument("--archive", type=Path, default=Path("artifacts/downloads/rea-agents-6.4.0.tgz"))
    parser.add_argument("--root", type=Path, default=Path("tools/rea"))
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text())
    content = args.archive.read_bytes()
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(content).digest()).decode()
    if metadata["name"] != "rea-agents" or metadata["version"] != "6.4.0" or integrity != metadata["dist"]["integrity"]:
        raise ValueError("REA package identity or registry integrity mismatch")
    package = args.root / "package"
    if not package.exists():
        with tarfile.open(args.archive) as archive:
            for member in archive.getmembers():
                if not member.name.startswith("package/") or member.issym() or member.islnk():
                    raise ValueError(f"Unexpected archive member: {member.name}")
            archive.extractall(args.root, filter="data")
    # Keep the vendor manifest unchanged. Only the separate dependency manifest is reduced.
    vendor = json.loads((package / "package.json").read_text())
    dependencies = dict(vendor["dependencies"])
    excluded = {name: dependencies.pop(name) for name in ["playwright-core"]}
    deps = args.root / "deps"
    deps.mkdir(parents=True, exist_ok=True)
    (deps / "package.json").write_text(json.dumps({
        "name": "projectricoh-rea-native-dependencies", "version": "0.0.0", "private": True,
        "description": "Project-scoped REA dependencies. Browser commands are unsupported.",
        "dependencies": dependencies,
    }, indent=2) + "\n")
    link = package / "node_modules"
    target = Path("../deps/node_modules")
    if link.is_symlink() and link.readlink() != target:
        raise ValueError("REA node_modules points to an unexpected location")
    if not link.exists() and not link.is_symlink():
        link.symlink_to(target, target_is_directory=True)
    manifest = {
        "name": vendor["name"], "version": vendor["version"],
        "tarball": metadata["dist"]["tarball"], "registry_integrity_verified": True,
        "registry_git_head": metadata.get("gitHead"),
        "archive_sha256": hashlib.sha256(content).hexdigest(), "archive_sha512_sri": integrity,
        "vendor_package_json_sha256": hashlib.sha256((package / "package.json").read_bytes()).hexdigest(),
        "installation_scope": "project-local native/static CLI; not a full upstream setup",
        "excluded_dependencies": excluded,
        "browser_commands": "disabled by missing dependency; use the user's pinned/native browser policy",
        "agent_config_written": False, "upstream_install_scripts_run": False,
    }
    Path("artifacts/rea").mkdir(parents=True, exist_ok=True)
    Path("artifacts/rea/install-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
