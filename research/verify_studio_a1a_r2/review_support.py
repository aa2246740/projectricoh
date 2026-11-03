"""独立复测使用的合成数据和收据，不复制被审测试的实现。"""

import hashlib
import io
import json
import os
from pathlib import Path
import struct
from datetime import datetime

import numpy as np
from PIL import Image

from gxr_studio.cards import discovery, session
from gxr_studio.cards.importer import ImportOptions

OUT = Path(__file__).resolve().parent
BASE = OUT.parent.parent
REPO = BASE / "studio"
TEMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-a1a-r2")
FIXED_TIME = int(datetime(2026, 10, 31, 12).timestamp() * 1e9)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(name, values):
    with (OUT / "observations.jsonl").open("a") as fh:
        fh.write(json.dumps({"run": os.environ.get("REVIEW_RUN_NAME"), "case": name, **values}, ensure_ascii=False, default=str) + "\n")


def jpeg_bytes(colour=(31, 110, 210)):
    image = Image.new("RGB", (48, 32), colour)
    data = io.BytesIO()
    image.save(data, format="JPEG", quality=94)
    return data.getvalue()


def media_bytes(kind):
    if kind == "jpg":
        return jpeg_bytes()
    if kind == "dng":
        return dng_bytes()
    return b"RIFF" + struct.pack("<I", 4100) + b"AVI " + bytes(range(256)) * 16


def card_at(area, kinds=("jpg",), count=1):
    root = area / "volumes" / "CARD"
    directory = root / "DCIM" / "100RICOH"
    directory.mkdir(parents=True)
    for index in range(count):
        for kind in kinds:
            path = directory / f"R{index + 1:07d}.{kind.upper()}"
            data = media_bytes(kind)
            if kind == "jpg" and index:
                data = jpeg_bytes((31 + index, 110, 210))
            path.write_bytes(data)
            os.utime(path, ns=(FIXED_TIME, FIXED_TIME))
    return discovery.Card(root, "CARD")


def tree(root):
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        st = path.lstat()
        if path.is_symlink():
            result[str(path.relative_to(root))] = {"link": os.readlink(path)}
        elif path.is_file():
            result[str(path.relative_to(root))] = {
                "sha256": digest(path.read_bytes()), "size": st.st_size,
                "mtime_ns": st.st_mtime_ns, "ctime_ns": st.st_ctime_ns,
            }
        else:
            result[str(path.relative_to(root))] = {"directory": True}
    return result


def options(**kwargs):
    return ImportOptions(min_free_bytes=0, make_thumbs=False, fsync=True, chunk=96, **kwargs)


class ModelProbe(session.VolumeProbe):
    def __init__(self):
        self.number = 1
        self.device = "local-model-a"
        self.available = True

    def fingerprint(self, path):
        if not self.available:
            return None
        try:
            st = Path(path).lstat()
        except OSError:
            return None
        return session.Fingerprint(path, st.st_dev, st.st_ino, (self.number, 0), self.device)

    def volume_uuid(self, path):
        return "2A6AC8E1-5B29-4F44-8549-2FF1D0766F4B"


def attached(card):
    probe = ModelProbe()
    registry = session.SessionRegistry(probe=probe)
    mount = registry.attach(card)
    from gxr_studio.api.routes import identity_of
    return probe, registry, mount, identity_of(mount)


def dng_bytes(overrides=None, absent=()):
    width, height = 12, 10
    pixels = (np.arange(width * height, dtype=np.uint16) * 23 + 64).reshape(height, width)
    tags = {
        254: (4, [0]), 256: (4, [width]), 257: (4, [height]), 258: (3, [16]),
        259: (3, [1]), 262: (3, [32803]), 273: (4, [0]), 274: (3, [1]),
        277: (3, [1]), 278: (4, [height]), 279: (4, [pixels.nbytes]),
        33421: (3, [2, 2]), 33422: (1, [0, 1, 1, 2]),
        50706: (1, [1, 4, 0, 0]), 50710: (1, [0, 1, 2]), 50711: (3, [1]),
        50713: (3, [1, 1]), 50714: (3, [0]), 50717: (4, [4095]),
        50719: (4, [0, 0]), 50720: (4, [width, height]),
        50721: (10, [(1 if i % 4 == 0 else 0, 1) for i in range(9)]),
        50728: (5, [(1, 1), (1, 1), (1, 1)]), 50778: (3, [21]),
        50736: (5, [(0, 100), (0, 100), (0, 0), (0, 0)]),
    }
    tags.update(overrides or {})
    for tag in absent:
        tags.pop(tag, None)
    formats = {1: "B", 3: "H", 4: "I", 5: "II", 10: "ii", 11: "f", 12: "d"}

    def encode(typ, values):
        flat = [part for value in values for part in value] if typ in (5, 10) else values
        return struct.pack("<" + formats[typ] * len(values), *flat)

    offset = 8 + 2 + 12 * len(tags) + 4
    lengths = [len(encode(typ, values)) for typ, values in tags.values()]
    tags[273] = (4, [offset + sum(n + n % 2 for n in lengths if n > 4)])
    entries, extra = [], bytearray()
    for tag, (typ, values) in sorted(tags.items()):
        data = encode(typ, values)
        if len(data) <= 4:
            field = data.ljust(4, b"\0")
        else:
            field = struct.pack("<I", offset + len(extra))
            extra.extend(data)
            if len(data) % 2:
                extra.append(0)
        entries.append(struct.pack("<HHI", tag, typ, len(values)) + field)
    return b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", len(tags)) + b"".join(entries) + b"\0" * 4 + extra + pixels.astype("<u2").tobytes()
