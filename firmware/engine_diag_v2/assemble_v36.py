"""Gate the mechanical rebind, then assemble the exact card root from genuine ZIP."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local/integration"
PACKAGE = ROOT / "firmware/package_v36_g117"
sha = lambda b: hashlib.sha256(b).hexdigest()
u32 = lambda b, o: int.from_bytes(b[o:o+4], "big")


def crc32(data):
    value = 0xffffffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xedb88320 if value & 1 else 0)
    return value ^ 0xffffffff


def main():
    old = (ROOT / "firmware/package_v35_g117/SD_ROOT/GXRCE.DAT").read_bytes()
    new = (HERE / "candidate/local/full-r13/GXRCE.DAT").read_bytes()
    assert sha(old) == "4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a"
    assert len(old) == len(new) == 55500 and u32(new, 28) == 117
    trust = json.loads((ROOT / "firmware/resident_v36/local/resident/trust.json").read_text())
    assert new[80:112].hex() == trust["resident_build_id"]
    assert new[212:228].hex() == trust["resident_abi_id"]
    differences = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    assert differences and all(20 <= i < 24 or 80 <= i < 112 for i in differences), "STOP_NON_BINDING_BYTES_CHANGED"
    ranges = []
    for i in differences:
        if ranges and ranges[-1][1] == i:
            ranges[-1][1] += 1
        else:
            ranges.append([i, i+1])
    header = bytearray(new[:256]); header[20:24] = bytes(4)
    header_crc = crc32(header)
    assert header_crc == u32(new, 20)
    assert crc32(new[256:]) == u32(new, 24)
    assert old[256:] == new[256:]
    result = dict(status="PASS", old_sha256=sha(old), sha256=sha(new), size=len(new), generation=u32(new, 28),
                  header_crc32=f"{header_crc:08x}", image_data_crc32=f"{u32(new,24):08x}",
                  resident_build_id=new[80:112].hex(), abi=new[212:228].hex(),
                  image_data_identical=True, engine_relocations_recipes_identical=True,
                  differing_bytes=len(differences), ranges=[dict(start=a, end_exclusive=b, bytes=b-a,
                    old_hex=old[a:b].hex(), new_hex=new[a:b].hex()) for a,b in ranges])
    (OUT / "rebind-diff.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2), flush=True)
    assert not PACKAGE.exists(), "package already exists"
    sd = PACKAGE / "SD_ROOT"; sd.mkdir(parents=True)
    archive = ROOT / "artifacts/downloads/gxr-151.zip"
    assert sha(archive.read_bytes()) == "3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898"
    rows = []
    with zipfile.ZipFile(archive) as z:
        entries = [x for x in z.infolist() if not x.is_dir() and not x.filename.startswith("__MACOSX/")]
        assert len(entries) == 29, [x.filename for x in entries]
        for entry in entries:
            name = Path(entry.filename).name
            if name == "ilaunch3":
                continue
            data = z.read(entry)
            extracted = ROOT / "artifacts/firmware/gxr-1.51" / name
            assert extracted.read_bytes() == data, name
            (sd / name).write_bytes(data)
            assert (sd / name).read_bytes() == z.read(entry)
            rows.append(dict(name=name, bytes=len(data), sha256=sha(data), zip_member=entry.filename, zip_equal=True))
    assert len(rows) == 28
    body = ROOT / "firmware/image_v36/local/package/SD_ROOT/ilaunch3"
    assert sha(body.read_bytes()) == "50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008"
    shutil.copyfile(body, sd / "ilaunch3")
    (sd / "GXRCE.DAT").write_bytes(new)
    files = sorted(sd.iterdir())
    assert len(files) == 30 and all(x.is_file() for x in files)
    assert not any(x.name.startswith(("DEEPTBL", "DEEPISP", "GXRBX")) or x.name in ("GXRCE.CTL", "GXRCE.OK") for x in files)
    card = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in files)
    (PACKAGE / "CARD_SHA256SUMS").write_text(card)
    (OUT / "official-zip-verification.json").write_text(json.dumps(rows, indent=2)+"\n")
    (OUT / "package-inventory.json").write_text(json.dumps(dict(files=30, official=28,
        card_sha256sums_sha256=sha(card.encode()), card=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in files]),indent=2)+"\n")
    print("PASS package files=30 official_zip_equal=28 CARD_SHA256SUMS_sha256="+sha(card.encode()), flush=True)


if __name__ == "__main__":
    main()
