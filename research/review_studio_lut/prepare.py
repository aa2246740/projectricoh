"""Copy only the existing offline build dependencies into the review temporary directory."""
import hashlib
import json
import shutil
from pathlib import Path

OUT=Path(__file__).resolve().parent
TMP=Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-lut")
SRC=Path("/Users/wu/.cache/uv")

def prepare():
    target=TMP/"uv"
    entries=[]
    for name in ("hatchling","packaging","pathspec","pluggy","tomlkit","trove-classifiers"):
        source=SRC/"wheels-v5/pypi"/name
        if not source.is_dir():raise SystemExit("Missing offline build cache: "+name)
        for item in source.iterdir():
            dst=target/item.relative_to(SRC)
            dst.parent.mkdir(parents=True,exist_ok=True)
            if item.is_symlink():
                real=item.resolve()
                archive=target/real.relative_to(SRC)
                if not archive.exists():shutil.copytree(real,archive,symlinks=False)
                if not dst.exists():dst.symlink_to(archive)
            elif item.is_file():shutil.copy2(item,dst)
        p=SRC/"simple-v17/pypi"/(name+".rkyv")
        dst=target/p.relative_to(SRC)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dst)
        entries.append({"package":name,"simple_sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    (TMP/"bin").mkdir(parents=True,exist_ok=True)
    uv=TMP/"bin/uv"
    uv.write_text('#!/bin/sh\nif [ "$*" = "run --frozen lint-imports" ]; then\n    exec /opt/homebrew/bin/uv "$@" --cache-dir "$REVIEW_TMP/import-linter"\nfi\nexec /opt/homebrew/bin/uv "$@"\n')
    uv.chmod(0o755)
    files=[p for p in target.rglob("*") if p.is_file() and not p.is_symlink()]
    receipt={"source":str(SRC),"destination":str(target),"packages":entries,"file_count":len(files),
             "bytes":sum(p.stat().st_size for p in files),
             "all_links_internal":all(p.resolve().is_relative_to(target) for p in target.rglob("*") if p.is_symlink())}
    (OUT/"offline_build_cache.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print("Prepared six existing offline build dependency caches.")

if __name__=="__main__":prepare()
