#!/usr/bin/env python3
"""Generate the phase-1 four-recipe bank and ISP rows.

Ricoh-derived bytes are written only to deep_tables.c, which stays gitignored.
Tracked JSON keeps hashes, lengths and the one endpoint adjustment.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
RESEARCH = ROOT / "research/stage2d_phase1"
CURVES = ROOT / "research/phase1_curves/curves.json"
FIT = ROOT / "research/phase1_curves/local/firmware_and_fit.json"
JLAUNCH = ROOT / "artifacts/firmware/gxr-1.51/jlaunch3"
JLAUNCH_SHA = "951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673"
SECTION3_BASE = 0x200F2000
SECTION3_FILE = 0xA7200
TARGETS = ((0x2012F504, 62), (0x2012FFFC, 33), (0x2012C5D4, 96))
ROW20 = (0x2012F8A6, 0x201301EB)

COLOR_FIELDS = (
    "contrast", "sharpness", "vividness",
    "orange_saturation", "green_saturation", "blue_saturation",
    "red_saturation", "magenta_saturation",
    "orange_hue", "green_hue", "blue_hue", "red_hue", "magenta_hue",
)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def load_make():
    spec = importlib.util.spec_from_file_location("phase1_make", HERE / "tools/make_recipes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_image(image, va, count):
    segments = [struct.unpack_from(">5I", image, 32 + i * 20) for i in range(16)]
    hits = [src + 512 + va - base for src, base, size, _, _ in segments
            if base <= va and va + count <= base + size]
    if len(hits) != 1:
        raise SystemExit(f"VMA {va:#x} is not in exactly one section")
    formula = va - SECTION3_BASE + SECTION3_FILE
    if hits[0] != formula:
        raise SystemExit(f"section map {hits[0]:#x} disagrees with formula {formula:#x}")
    return image[hits[0]:hits[0] + count]


def check_curve(name, inputs, outputs):
    if len(inputs) != 31 or len(outputs) != 33:
        raise SystemExit(f"{name}: expected 31 inputs and 33 outputs")
    if any(not isinstance(value, int) or not 1 <= value <= 4094 for value in inputs):
        raise SystemExit(f"{name}: an input is outside 1..4094")
    if any(inputs[i] >= inputs[i + 1] for i in range(30)):
        raise SystemExit(f"{name}: inputs are not strictly increasing")
    if any(not isinstance(value, int) or not 0 <= value <= 255 for value in outputs):
        raise SystemExit(f"{name}: an output is outside 0..255")
    if any(outputs[i] > outputs[i + 1] for i in range(32)):
        raise SystemExit(f"{name}: outputs decrease")


def unpack_tone(blob_a, blob_b):
    return list(struct.unpack(">31H", blob_a)), list(blob_b)


def pack_tone(inputs, outputs):
    check_curve("tone", inputs, outputs)
    return struct.pack(">31H", *inputs), bytes(outputs)


def array(name, blob):
    lines = []
    for start in range(0, len(blob), 16):
        lines.append("    " + ",".join(f"0x{byte:02x}" for byte in blob[start:start + 16]) + ",")
    return "static const uint8_t " + name + "[] = {\n" + "\n".join(lines) + "\n};\n"


def recipes():
    colour = {name: 5 for name in COLOR_FIELDS}
    rows = [
        {"slot": 1, "name": "01 Posi", "base_mode": "color", "parameters": dict(colour), "wb": [0, 0]},
        {"slot": 2, "name": "02 Nega", "base_mode": "color", "parameters": dict(colour), "wb": [0, 0]},
        {"slot": 3, "name": "03 HC BW", "base_mode": "bw",
         "parameters": {"contrast": 5, "sharpness": 6}, "wb": [0, 0]},
        {"slot": 4, "name": "04 Std", "base_mode": "standard", "parameters": {}, "wb": [0, 0]},
    ]
    for row in rows:
        if not 1 <= len(row["name"]) <= 8:
            raise SystemExit(f"name longer than 8: {row['name']}")
    return {"format_version": 2, "generation": 1, "recipes": rows}


def legacy_v1(document):
    """Color-only companion. Native Standard has no v1 encoding, so slot 4 stays empty."""
    legacy = {"format_version": 1, "generation": 1, "recipes": []}
    for entry in document["recipes"]:
        if entry["base_mode"] == "standard":
            continue
        copied = {"slot": entry["slot"], "name": entry["name"], "wb": list(entry["wb"]),
                  "parameters": {name: 5 for name in COLOR_FIELDS}}
        if entry["base_mode"] != "color":
            copied["parameters"].update(contrast=entry["parameters"]["contrast"],
                                        sharpness=entry["parameters"]["sharpness"], vividness=1)
        else:
            copied["parameters"] = dict(entry["parameters"])
        legacy["recipes"].append(copied)
    return legacy


def main():
    make = load_make()
    document = recipes()
    surface = make.compile_recipes(document)
    legacy = make.compile_recipes(legacy_v1(document))
    if surface[:8] != b"GXRRV201" or legacy[:8] != b"GXRRV101":
        raise SystemExit("recipe container magic mismatch")
    (HERE / "examples").mkdir(exist_ok=True)
    (HERE / "examples" / "phase1_recipes.json").write_text(json.dumps(document, indent=2) + "\n")
    for name in ("DEEPISP0.DAT", "DEEPISP1.DAT", "RECIPE20.DAT", "RECIPE21.DAT"):
        (HERE / "examples" / name).write_bytes(surface)
    (HERE / "examples" / "RECIPES0.DAT").write_bytes(legacy)
    names = []
    for slot in range(4):
        record = surface[32 + slot * 64:96 + slot * 64]
        names.append(record[4:4 + record[2]].decode("ascii"))
    if names != ["01 Posi", "02 Nega", "03 HC BW", "04 Std"]:
        raise SystemExit("DAT names diverged")
    if any(surface[33 + slot * 64] for slot in range(4, 16)):
        raise SystemExit("slots 5..16 must be empty")

    image = JLAUNCH.read_bytes()
    if sha(image) != JLAUNCH_SHA:
        raise SystemExit("jlaunch3 hash mismatch")
    stock = [read_image(image, address, count) for address, count in TARGETS]
    check_curve("stock", *unpack_tone(stock[0], stock[1]))
    curves = json.loads(CURVES.read_text())
    fit = json.loads(FIT.read_text())
    native_a, native_b = unpack_tone(read_image(image, ROW20[0], 62), read_image(image, ROW20[1], 33))
    if native_a != fit["gxr_native_row20"]["input31_u16"] or native_b != fit["gxr_native_row20"]["output33_u8"]:
        raise SystemExit("row 20 does not match firmware_and_fit.json")
    if native_a[-1] != 4095 or not native_a[-2] < 4094:
        raise SystemExit("row 20 endpoint is not the expected full-scale sentinel")
    hc_inputs = list(native_a)
    hc_inputs[-1] = 4094
    profiles = [stock]
    for key in ("positive", "negative"):
        tone_a, tone_b = pack_tone(curves[key]["input31_u16"], curves[key]["output33_u8"])
        profiles.append([tone_a, tone_b, stock[2]])
    hc_a, hc_b = pack_tone(hc_inputs, native_b)
    profiles.append([hc_a, hc_b, stock[2]])
    if len(profiles) != 4 or any(len(row) != 3 for row in profiles):
        raise SystemExit("profile shape")

    text = ['#include "deep_isp.h"\n',
            "/* Generated by tools/generate_deep_tables.py.\n",
            " * HC input endpoint: native 4095 is stored as 4094.\n",
            " * Colour row of every profile is stock row 1. */\n"]
    text.append("const Rv1Recipe rfw_defaults[RV1_SLOT_COUNT] = {\n")
    for slot in range(16):
        record = surface[32 + slot * 64:96 + slot * 64]
        if record[1] == 0:
            text.append("    {0},\n")
            continue
        raw = ",".join(str(value) for value in record[36:49])
        wb = ",".join(str(value if value < 128 else value - 256) for value in record[49:51])
        name = json.dumps(record[4:4 + record[2]].decode("ascii"))
        text.append(f"    {{{record[2]},{name},{record[3]},{{{raw}}},{{{wb}}}}},\n")
    text.append("};\n#if RFW_DEEP_ENABLED\n")
    text.append("const uint8_t rfw_deep_slots[RFW_DEEP_PROFILES] = {1,2,3};\n")
    shared = {}
    for profile, rows in enumerate(profiles):
        for index, blob in enumerate(rows):
            if blob not in shared:
                shared[blob] = f"table_{profile}_{index}"
                text.append(array(shared[blob], blob))
    text.append("const RfwDeepRow rfw_deep_rows[RFW_DEEP_ROWS] = {\n")
    for index, (address, length) in enumerate(TARGETS):
        pointers = ",".join(shared[rows[index]] for rows in profiles)
        text.append(f"    {{{address:#x},{length},{{{pointers}}}}},\n")
    text.append("};\n#endif\n")
    (HERE / "deep_tables.c").write_text("".join(text))

    labels = ("a5", "b5", "colour")
    profile_names = ("stock", "01 Posi", "02 Nega", "03 HC BW")
    RESEARCH.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "stage2d-phase1-tables-v1",
        "deep_slots": [1, 2, 3],
        "colour_policy": "every profile writes stock colour row 1",
        "hc_tone": "GXR native row 20",
        "hc_last_input_adjusted": {
            "native": 4095,
            "stored": 4094,
            "reason": "stored inputs must be inside 1..4094; 0 and 4095 are the implicit endpoints",
        },
        "monotonic": True,
        "jlaunch3_sha256": sha(image),
        "curves_json_sha256": sha(CURVES.read_bytes()),
        "table_sha256": {
            f"{profile_names[profile]}.{labels[index]}": sha(blob)
            for profile, rows in enumerate(profiles)
            for index, blob in enumerate(rows)
        },
        "dat_sha256": {
            name: sha((HERE / "examples" / name).read_bytes())
            for name in ("DEEPISP0.DAT", "DEEPISP1.DAT", "RECIPE20.DAT", "RECIPE21.DAT", "RECIPES0.DAT")
        },
        "names": names,
    }
    (RESEARCH / "tables_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"profiles": 4, "unique_tables": len(shared),
                      "surface_sha256": sha(surface), "legacy_sha256": sha(legacy)}))


if __name__ == "__main__":
    main()
