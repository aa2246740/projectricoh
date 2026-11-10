"""Shared helpers for the public GXR 1.51 rebuild tools.

Patches store offsets, lengths, the SHA-256 of the official bytes they
replace, and either our replacement bytes or a copy from another offset in
the official image. They do not store the official bytes themselves.
A run of 12 or more bytes that already occurs in the official image is a
copy operation. Shorter matches stay in literals.
"""

import ast
import hashlib
import json
import zlib
from pathlib import Path


FORMAT = "gxr-public-patch/1"
HEADER = 0x200
CHECKSUM_FIELD = 0x16C
CHECKSUM_ALGORITHM = "gxr151-weighted-residue"
COPY_MIN_LENGTH = 12
ZIP_SHA256 = "3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898"
ZIP_BYTES = 11277528
ZIP_URL = "https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/exe/gxr-151.zip"


def repo_root():
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "scripts" / "build_drill.py").is_file() and (candidate / ".git").exists():
            return candidate
    raise SystemExit("gxr151.py must live inside the projectricoh checkout")


def sha256(data):
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(data).hexdigest()
    digest = hashlib.sha256()
    with Path(data).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_member_manifest(root=None):
    """The 29-member list pinned in scripts/build_drill.py."""
    path = (root or repo_root()) / "scripts" / "build_drill.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "OFFICIAL" for target in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict) or len(value) != 29:
                raise SystemExit("scripts/build_drill.py OFFICIAL is not the 29-member list")
            if any(not isinstance(name, str) or not isinstance(digest, str) or len(digest) != 64
                   for name, digest in value.items()):
                raise SystemExit("official manifest entries must be name and SHA-256 strings")
            return dict(value)
    raise SystemExit("scripts/build_drill.py has no OFFICIAL manifest")


def weighted_checksum(payload, phase):
    """Observed GXR 1.51 payload checksum. phase is 0..5 and comes from the base file."""
    sums = [sum(payload[residue::6]) for residue in range(6)]
    return sum(total * ((residue + phase) % 6 + 2) for residue, total in enumerate(sums)) & 0xFFFFFFFF


def stored_checksum(data):
    return int.from_bytes(data[CHECKSUM_FIELD:CHECKSUM_FIELD + 4], "big")


def checksum_phase(data):
    payload = data[HEADER:]
    stored = stored_checksum(data)
    phases = [phase for phase in range(6) if weighted_checksum(payload, phase) == stored]
    if len(phases) != 1:
        raise ValueError("checksum phase is not unique: %s" % (phases,))
    return phases[0]


def write_checksum(image, phase):
    value = weighted_checksum(image[HEADER:], phase)
    image[CHECKSUM_FIELD:CHECKSUM_FIELD + 4] = value.to_bytes(4, "big")
    return value


def load_patch(path):
    patch = json.loads(Path(path).read_text(encoding="utf-8"))
    if patch.get("format") != FORMAT:
        raise ValueError("unsupported patch format")
    if patch.get("checksum", {}).get("algorithm") != CHECKSUM_ALGORITHM:
        raise ValueError("unsupported checksum algorithm")
    hunks = patch.get("hunks")
    if not isinstance(hunks, list) or not hunks:
        raise ValueError("patch has no hunks")
    return patch


def _hunk_span(hunk):
    offset = hunk["offset"]
    length = hunk["length"]
    if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or length <= 0:
        raise ValueError("hunk offset and length must be positive integers")
    return offset, offset + length


def apply_patch(base, patch):
    """Return the rebuilt image. Reads copy sources from the untouched base."""
    if sha256(base) != patch["base_sha256"]:
        raise ValueError("base image SHA-256 does not match the patch")
    if len(base) != patch["result_size"]:
        raise ValueError("base size does not match the patch")
    phase = checksum_phase(base)
    declared = patch["checksum"].get("phase")
    if declared != phase:
        raise ValueError("checksum phase does not match the base image")
    if patch["checksum"].get("field_offset") != CHECKSUM_FIELD:
        raise ValueError("checksum field offset is not 0x16c")
    if patch["checksum"].get("payload_offset") != HEADER:
        raise ValueError("checksum payload offset is not 0x200")
    image = bytearray(base)
    covered = []
    for hunk in patch["hunks"]:
        start, end = _hunk_span(hunk)
        if end > len(base):
            raise ValueError("hunk extends past the image")
        if start < CHECKSUM_FIELD + 4 and end > CHECKSUM_FIELD:
            raise ValueError("hunk overlaps the checksum field; the script recomputes it")
        if any(start < previous_end and previous_start < end for previous_start, previous_end in covered):
            raise ValueError("hunks overlap")
        covered.append((start, end))
        destination = bytes(base[start:end])
        if sha256(destination) != hunk["base_sha256"]:
            raise ValueError("bytes at offset %d do not match base_sha256" % start)
        op = hunk["op"]
        if op == "literal":
            replacement = bytes.fromhex(hunk["new_hex"])
            if len(replacement) != end - start:
                raise ValueError("literal length does not match new_hex")
            image[start:end] = replacement
        elif op == "copy":
            source = hunk["from_offset"]
            if not isinstance(source, int) or source < 0 or source + (end - start) > len(base):
                raise ValueError("copy source is outside the base image")
            copied = bytes(base[source:source + (end - start)])
            if sha256(copied) != hunk["source_sha256"]:
                raise ValueError("copy source SHA-256 does not match")
            image[start:end] = copied
        else:
            raise ValueError("unknown hunk op")
    write_checksum(image, phase)
    if checksum_phase(image) != phase:
        raise ValueError("recomputed checksum does not verify")
    rebuilt = bytes(image)
    if sha256(rebuilt) != patch["result_sha256"]:
        raise ValueError("rebuilt SHA-256 does not match the patch")
    return rebuilt


def accounting(patch):
    literal = 0
    copied = 0
    for hunk in patch["hunks"]:
        if hunk["op"] == "literal":
            literal += hunk["length"]
        elif hunk["op"] == "copy":
            copied += hunk["length"]
        else:
            raise ValueError("unknown hunk op")
    stored = patch.get("accounting") or {}
    result = {
        "literal_bytes": literal,
        "copy_bytes": copied,
        "checksum_recomputed_bytes": 4,
        "hunks": len(patch["hunks"]),
    }
    for key in ("literal_bytes", "copy_bytes", "checksum_recomputed_bytes", "hunks"):
        if key in stored and stored[key] != result[key]:
            raise ValueError("patch accounting does not match its hunks")
    return result


def window_signature(blob):
    first = zlib.crc32(blob) & 0xFFFFFFFF
    second = zlib.crc32(blob[:1], zlib.crc32(blob[1:])) & 0xFFFFFFFF
    return first | (second << 32)


def build_window_index(official, window):
    """First offset of each 64-bit window signature.

    Identical windows are interchangeable for an exact copy. A later copy step
    continues from the next unmatched byte, so the first matching run is enough.
    """
    index = {}
    view = memoryview(official)
    for offset in range(len(official) - window + 1):
        key = window_signature(view[offset:offset + window])
        if key not in index:
            index[key] = offset
    return index


def _candidates(index, key):
    found = index.get(key)
    if found is None:
        return ()
    if isinstance(found, int):
        return (found,)
    return found


def embedded_runs(official, index, blob, window):
    """Maximal exact runs of at least `window` bytes that also occur in official.

    Returns (blob_offset, official_offset, length) and does not return the bytes.
    """
    runs = []
    index_pos = 0
    limit = len(blob)
    while index_pos + window <= limit:
        key = window_signature(blob[index_pos:index_pos + window])
        best_at = None
        best_len = 0
        for source in _candidates(index, key):
            if official[source:source + window] != blob[index_pos:index_pos + window]:
                continue
            length = window
            while (index_pos + length < limit and source + length < len(official)
                   and official[source + length] == blob[index_pos + length]):
                length += 1
            if length > best_len:
                best_len = length
                best_at = source
        if best_at is None:
            index_pos += 1
            continue
        runs.append((index_pos, best_at, best_len))
        index_pos += best_len
    return runs


def _longest_short(official, blob):
    """Longest exact piece of a short blob that also occurs in official."""
    limit = len(blob)
    for size in range(limit, 0, -1):
        for start in range(0, limit - size + 1):
            if official.find(blob[start:start + size]) != -1:
                return size
    return 0
