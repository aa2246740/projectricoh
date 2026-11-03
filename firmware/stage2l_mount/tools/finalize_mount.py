#!/usr/bin/env python3
"""Check final readback, protected inputs and manifests without touching media."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
PACKAGE = LOCAL / "package"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_sums(directory):
    listed = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest,name = line.split("  ",1)
        path = (directory / name).resolve()
        assert path.is_relative_to(directory) and name not in listed
        assert sha(path) == digest, name
        listed[name] = digest
    actual = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file() and p != directory / "SHA256SUMS"}
    assert set(listed) == actual
    return len(listed)


def main():
    volume = plistlib.loads(subprocess.check_output(["diskutil","info","-plist","/Volumes/Workspace"]))
    assert volume["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert volume["FilesystemType"] == "apfs" and volume["WritableVolume"] and volume["WritableMedia"]
    protected = json.loads((LOCAL / "protected-before.json").read_text())
    assert all(sha(ROOT / name) == digest for name,digest in protected.items())
    refs = json.loads((LOCAL / "reference-inputs-sha256.json").read_text())
    refs.update(json.loads((LOCAL / "provisional.json").read_text())["source_sha256"])
    assert all(sha(ROOT / name) == digest for name,digest in refs.items())
    evidence = json.loads((LOCAL / "build/verification.json").read_text())
    assert all(sha(ROOT / name) == digest for name,digest in evidence["inputs_sha256"].items())
    assert [x["cases"] for x in evidence["host"]] == [283,283] and evidence["abi_model_cases"] == 48
    package_sums = check_sums(PACKAGE)
    candidate, recovery = PACKAGE / "candidate/SD_ROOT", PACKAGE / "recovery-official-1.51/SD_ROOT"
    names = {p.name for p in candidate.iterdir()}
    assert len(names) == 29 and names == {p.name for p in recovery.iterdir()}
    official = ROOT / "artifacts/firmware/gxr-1.51"
    for name in names:
        assert (recovery / name).read_bytes() == (official / name).read_bytes()
        if name != "ilaunch3":
            assert (candidate / name).read_bytes() == (official / name).read_bytes()
    image = (candidate / "ilaunch3").read_bytes()
    payload = (LOCAL / "build/payload.bin").read_bytes()
    assert len(payload) == 8084 and image[0x796c:0x9900] == payload
    assert image[0x9900:0x9a00] == b"\xff" * 256
    assert struct.unpack_from(">I",image,0x16c)[0] == sum(v*(i%6+2) for i,v in enumerate(image[512:])) & 0xffffffff
    old = (ROOT / "artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/ilaunch3").read_bytes()
    changes = [(i,a,b) for i,(a,b) in enumerate(zip(old,image)) if a != b]
    listed = (LOCAL / "byte-diff-image.tsv").read_text().splitlines()[1:]
    assert len(changes) == len(listed) == 776
    assert [(int(line.split('\t')[0],16),int(line.split('\t')[1],16),int(line.split('\t')[2],16)) for line in listed] == changes
    table = (LOCAL / "DEEPTBL_mount_provisional.DAT").read_bytes()
    assert len(table) == 3600
    assert all((PACKAGE / f"runtime-data/SD_ROOT/DEEPTBL{i}.DAT").read_bytes() == table for i in (0,1))
    assert (HERE / "tools/build.py").read_bytes() == (ROOT / "firmware/stage2l_switch/tools/build.py").read_bytes()
    env = dict(os.environ,GIT_OPTIONAL_LOCKS="0")
    paths = ["firmware/stage2l_mount/local/DEEPTBL_mount_provisional.DAT",
             "firmware/stage2l_mount/local/build/payload.bin",
             "firmware/stage2l_mount/local/package/candidate/SD_ROOT/ilaunch3"]
    ignored = subprocess.check_output(["git","check-ignore","-v",*paths],cwd=ROOT,env=env,text=True)
    assert len(ignored.splitlines()) == len(paths) and all("stage2l_mount/.gitignore:1:/local/" in line for line in ignored.splitlines())
    (LOCAL / "git-check-ignore.txt").write_text(ignored)
    status = subprocess.check_output(["git","status","--short","--untracked-files=no"],cwd=ROOT,env=env,text=True)
    (LOCAL / "git-status-after.txt").write_text(status)
    final = dict(status="HOST_AND_PACKAGE_VERIFIED_NOT_ACCEPTED", protected_files_unchanged=len(protected),
                 reference_inputs_unchanged=len(refs), package_checksums_verified=package_sums,
                 candidate_firmware_files=29, unchanged_candidate_components=28, recovery_official_files=29,
                 host_cases=283,sanitizer_cases=283,abi_model_cases=48,
                 image_sha256=sha(candidate / "ilaunch3"), table_sha256=sha(LOCAL / "DEEPTBL_mount_provisional.DAT"),
                 payload_bytes=8084,strict_size_gate=False,literal_constants_only_byte_gate=False,
                 write_scope="firmware/stage2l_mount/",local_ignored=True,camera_executed=False,sd_accessed=False,
                 release_approved=False,warning="未审查，不得上卡")
    (LOCAL / "final-verification.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n")
    files = sorted(p for p in HERE.rglob("*") if p.is_file() and p != HERE / "SHA256SUMS")
    (HERE / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(HERE)}\n" for p in files))
    for name in re.findall(r"\]\(([^)]+)\)",(HERE / "REPORT.md").read_text()):
        assert (HERE / name).resolve().is_relative_to(HERE) and (HERE / name).exists(), name
    total = check_sums(HERE)
    for directory,count in ((HERE,total),(PACKAGE,package_sums)):
        checked = subprocess.run(["shasum","-a","256","-c","SHA256SUMS"],cwd=directory,
                                 capture_output=True,text=True)
        assert checked.returncode == 0 and len(checked.stdout.splitlines()) == count, checked.stderr
    print(json.dumps(dict(status=final["status"],protected=len(protected),package_sums=package_sums,
                          total_sums=total,system_shasum_verified=True,strict_size_gate=False),ensure_ascii=False))


if __name__ == "__main__":
    main()
