#!/usr/bin/env python3
"""Compile explicit v1 color or v2 color/BW/TE libraries; never builds firmware."""
import argparse
import json
from pathlib import Path
import struct
import zlib

PARAMETERS = (
    "contrast", "sharpness", "vividness",
    "orange_saturation", "green_saturation", "blue_saturation",
    "red_saturation", "magenta_saturation",
    "orange_hue", "green_hue", "blue_hue", "red_hue", "magenta_hue",
)
DISPLAY_TO_RAW = (7, 6, 1, 2, 3, 4, 5, 8, 9)
MODES = {"color": 4, "bw": 3, "bw_te": 6, "standard": 1}
TONES = {"sepia": 6, "red": 1, "green": 2, "blue": 3, "purple": 4}
MODE_PARAMETERS = {"color": PARAMETERS, "bw": ("contrast", "sharpness"),
                   "bw_te": ("contrast", "sharpness", "vividness", "toning_color"),
                   "standard": ()}


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in {low}..{high}")
    return value


def compile_recipes(document):
    if not isinstance(document, dict) or set(document) - {"format_version", "generation", "recipes"}:
        raise ValueError("expected format_version, generation and recipes")
    version = integer(document.get("format_version", 1), 1, 2, "format_version")
    generation = integer(document.get("generation", 1), 0, 0xffffffff, "generation")
    recipes = document.get("recipes")
    if not isinstance(recipes, list) or len(recipes) > 16:
        raise ValueError("recipes must be a list containing at most 16 entries")
    records = [bytearray(64) for _ in range(16)]
    occupied = set()
    for entry in recipes:
        keys = {"slot", "name", "parameters", "wb"}
        if version == 2: keys.add("base_mode")
        if not isinstance(entry, dict) or set(entry) != keys:
            raise ValueError(f"each v{version} recipe needs exactly {sorted(keys)}")
        mode = entry.get("base_mode", "color")
        if not isinstance(mode, str) or mode not in MODES:
            raise ValueError("base_mode must be color, bw, bw_te or standard")
        slot = integer(entry["slot"], 1, 16, "slot")
        if slot in occupied:
            raise ValueError(f"duplicate slot {slot}")
        occupied.add(slot)
        name = entry["name"]
        if not isinstance(name, str) or not 1 <= len(name) <= 32 or not name.strip():
            raise ValueError(f"slot {slot}: name must contain 1..32 printable ASCII characters")
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in name):
            raise ValueError(f"slot {slot}: name must be printable ASCII")
        parameters = entry["parameters"]
        fields = MODE_PARAMETERS[mode]
        if not isinstance(parameters, dict) or set(parameters) != set(fields):
            raise ValueError(f"slot {slot}: parameters must contain exactly {', '.join(fields)}")
        wb = entry["wb"]
        if not isinstance(wb, list) or len(wb) != 2:
            raise ValueError(f"slot {slot}: wb must be [axis0, axis1]")
        record = records[slot - 1]
        record[1:3] = bytes((1, len(name)))
        record[3] = MODES[mode] if version == 2 else 0
        record[4:4 + len(name)] = name.encode("ascii")
        for index, key in enumerate(fields):
            if key == "toning_color":
                tone = parameters[key]
                if not isinstance(tone, str) or tone not in TONES:
                    raise ValueError("toning_color must be sepia, red, green, blue or purple")
                record[36 + index] = TONES[tone]
            else:
                record[36 + index] = DISPLAY_TO_RAW[integer(parameters[key], 1, 9, key) - 1]
        record[49:51] = bytes(integer(value, -8, 8, "wb") & 0xff for value in wb)
    for slot, record in enumerate(records, 1):
        record[0] = slot
        struct.pack_into(">I", record, 60, zlib.crc32(record[:60]))
    payload = b"".join(records)
    header = struct.pack(">8s4H3I", b"GXRRV101" if version == 1 else b"GXRRV201", version, 32, 64, 16,
                         generation, 1024, zlib.crc32(payload))
    return header + struct.pack(">I", zlib.crc32(header)) + payload


def migrate_v1(blob):
    """Validate a whole legacy bank before producing explicit color v2 bytes."""
    if len(blob) != 1056 or blob[:16] != b"GXRRV101\x00\x01\x00\x20\x00\x40\x00\x10":
        raise ValueError("not a v1 bank")
    if struct.unpack_from(">I", blob, 20)[0] != 1024 or any(
            struct.unpack_from(">I", blob, offset)[0] != zlib.crc32(data)
            for offset, data in ((24, blob[32:]), (28, blob[:28]))):
        raise ValueError("v1 header/payload CRC or dimensions")
    doc = {"format_version": 2, "generation": struct.unpack_from(">I", blob, 16)[0], "recipes": []}
    for index in range(16):
        r = blob[32 + index * 64:96 + index * 64]
        if r[0] != index + 1 or r[1] not in (0, 1) or r[3] or struct.unpack_from(">I", r, 60)[0] != zlib.crc32(r[:60]):
            raise ValueError("v1 slot/CRC")
        if not r[1]:
            if any(r[2:60]): raise ValueError("v1 empty padding")
            continue
        length = r[2]
        if not 1 <= length <= 32 or any(r[4 + length:36]) or any(r[51:60]):
            raise ValueError("v1 name/padding")
        if any(v not in DISPLAY_TO_RAW for v in r[36:49]):
            raise ValueError("v1 raw value")
        doc["recipes"].append({"slot": index + 1, "name": r[4:4 + length].decode('ascii'),
                               "base_mode": "color", "parameters": dict(zip(PARAMETERS,
                                   (DISPLAY_TO_RAW.index(v) + 1 for v in r[36:49]))),
                               "wb": list(struct.unpack('bb', r[49:51]))})
    return compile_recipes(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json", type=Path, nargs="?")
    parser.add_argument("--import-v1", type=Path, help="Explicitly migrate a legacy DAT as color")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if (args.json is None) == (args.import_v1 is None):
            raise ValueError("supply JSON or --import-v1")
        blob = (migrate_v1(args.import_v1.read_bytes()) if args.import_v1 else
                compile_recipes(json.loads(args.json.read_text(encoding="utf-8"))))
        version = blob[9]
        if args.output is None:
            args.output = Path("RECIPES0.DAT" if version == 1 else "RECIPE20.DAT")
        if args.output.name in ("RECIPES0.DAT", "RECIPES1.DAT") and version != 1:
            raise ValueError("v2 requires RECIPE20.DAT / RECIPE21.DAT, never legacy bank names")
        if args.output.name in ("RECIPE20.DAT", "RECIPE21.DAT") and version != 2:
            raise ValueError("v1 requires legacy bank names")
        if not args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError("output must stay inside the Stage 2a directory")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    args.output.write_bytes(blob)
    print(json.dumps({"output": str(args.output), "bytes": len(blob),
                      "occupied": sum(blob[33 + i * 64] for i in range(16))}))


if __name__ == "__main__":
    main()
