#!/usr/bin/env python3
"""Check the official Ricoh GXR 1.51 package and unpack it into the gitignored cache.

A cache that already matches the pinned length and SHA-256 is reused. Pass
--from to use a local zip with no network. Pass --download to fetch the
pinned URL when the cache is empty. This tool prints hashes and sizes only.
"""

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gxr151


def cache_paths(root, cache):
    cache = cache or (root / "research" / "public_rebuild_r1" / "cache")
    return cache, cache / "gxr-151.zip", cache / "gxr-1.51"


def zip_matches(path):
    if not path.is_file():
        return False
    if path.stat().st_size != gxr151.ZIP_BYTES:
        return False
    return gxr151.sha256(path) == gxr151.ZIP_SHA256


def copy_verified(source, destination):
    if not zip_matches(source):
        raise SystemExit("local zip length or SHA-256 does not match the pinned GXR 1.51 package")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.resolve() == source.resolve():
        return
    if zip_matches(destination):
        return
    temporary = destination.with_suffix(".zip.partial")
    shutil.copyfile(source, temporary)
    if not zip_matches(temporary):
        temporary.unlink()
        raise SystemExit("copied zip failed verification")
    temporary.replace(destination)


def download_zip(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".zip.partial")
    request = urllib.request.Request(gxr151.ZIP_URL, headers={"User-Agent": "projectricoh-fetch-official"})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    if not zip_matches(temporary):
        temporary.unlink()
        raise SystemExit("downloaded zip length or SHA-256 does not match the pin")
    temporary.replace(destination)


def member_names(archive, manifest):
    chosen = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = Path(info.filename).name
        if name not in manifest:
            continue
        if name in chosen:
            raise SystemExit("zip has more than one %s" % name)
        if info.file_size > 32 * 1024 * 1024:
            raise SystemExit("unexpected member size: %s" % name)
        chosen[name] = info.filename
    missing = sorted(set(manifest) - set(chosen))
    if missing:
        raise SystemExit("zip is missing official members: %s" % ", ".join(missing))
    return chosen


def extract_members(zip_path, member_dir, manifest):
    member_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        names = member_names(archive, manifest)
        for name, zip_name in sorted(names.items()):
            destination = member_dir / name
            if destination.is_file() and gxr151.sha256(destination) == manifest[name]:
                continue
            payload = archive.read(zip_name)
            if gxr151.sha256(payload) != manifest[name]:
                raise SystemExit("member SHA-256 mismatch: %s" % name)
            temporary = destination.with_suffix(destination.suffix + ".partial")
            temporary.write_bytes(payload)
            temporary.replace(destination)
    wrong = [name for name, digest in sorted(manifest.items())
             if gxr151.sha256(member_dir / name) != digest]
    if wrong:
        raise SystemExit("cached members do not match the manifest: %s" % ", ".join(wrong))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="source", type=Path, help="local zip; do not use the network")
    parser.add_argument("--download", action="store_true", help="fetch the pinned URL when the cache is empty")
    parser.add_argument("--cache", type=Path, help="gitignored cache directory")
    args = parser.parse_args()
    root = gxr151.repo_root()
    cache, zip_path, member_dir = cache_paths(root, args.cache)
    manifest = gxr151.load_member_manifest(root)
    reused = zip_matches(zip_path)
    downloaded = False
    if args.source:
        copy_verified(args.source, zip_path)
        origin = "local"
    elif reused:
        origin = "cache"
    elif args.download:
        download_zip(zip_path)
        downloaded = True
        origin = "download"
    else:
        raise SystemExit("no verified cache; pass --from <zip> or --download")
    if not zip_matches(zip_path):
        raise SystemExit("cache zip failed verification")
    extract_members(zip_path, member_dir, manifest)
    print(json.dumps({
        "status": "ok",
        "source": origin,
        "downloaded": downloaded,
        "reused_zip": reused,
        "zip_bytes": gxr151.ZIP_BYTES,
        "zip_sha256": gxr151.ZIP_SHA256,
        "members": len(manifest),
        "members_ok": len(manifest),
        "cache": str(cache),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
