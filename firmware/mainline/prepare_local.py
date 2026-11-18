#!/usr/bin/env python3
"""Copy local-only engine inputs from this machine. No network and no git writes.

The public tree under firmware/mainline/engine/ includes eng_core.c. This
script fills firmware/mainline/local/ from GXR_PRIVATE_ROOT and writes
eng_core_private.h from that profile's eng_core.c. Run it before build.py.
A clean checkout has no local/ directory until this runs.

It also writes l2n_orig_private.h from the official GXR 1.51 ZIP. The public
L2N tables name byte runs as L2N_ORIG_<VA>_<N>: the N bytes of the official
MAIN image (ilaunch3) at load address VA. The header defines each name as
that byte list. The script then refuses to continue if a tracked engine file
still spells out a run of 8 or more bytes that an official file contains: all
29 files of the ZIP (or of the extracted directory), or only the MAIN image
when --official-main is given. Runs are read from 0xNN tokens with or without
u/U/l/L suffixes, 16- and 32-bit words in both byte orders, \\xNN escapes,
assembler .byte/.short/.word lists, contiguous hex strings and Python bytes or
bytes.fromhex literals; comments and line breaks between tokens do not end a
run. Every text file under engine/ is checked, whatever its suffix.

GXR_PRIVATE_ROOT defaults to the main checkout of the Git repository this
script lives in (the parent of `git rev-parse --git-common-dir`). A clean
export without .git must pass --private-root or set GXR_PRIVATE_ROOT.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zipfile


MAIN = Path(__file__).resolve().parent
HEADER_REL = Path("research/build_g178_r1/local/model/GXRCE.DAT")
# Official GXR 1.51 inputs, as pinned in scripts/build_drill.py.
OFFICIAL_ZIP_REL = Path("artifacts/downloads/gxr-151.zip")
OFFICIAL_DIR_REL = Path("artifacts/firmware/gxr-1.51")
OFFICIAL_MAIN_NAME = "ilaunch3"
OFFICIAL_MAIN_SHA256 = "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
ORIG_HEADER_REL = Path("candidate/containers/product/l2n_orig_private.h")
ORIG_NAME = re.compile(r"\bL2N_ORIG_([0-9A-F]{8})_([1-9][0-9]*)\b")
ORIG_MIN_RUN = 8
# Relative to the engine tree. These files failed the public-sync review.
# They are coefficient tables, official-module pins, or test fixtures that
# are not separate link units. When unsure, they stay here.
# eng_core.c itself is public. Its camera-setting offsets and catalogue
# identity bytes are extracted into eng_core_private.h below.
LOCAL_FILES = (
    "candidate/containers/product/host_checks.c",
    "candidate/containers/product/pack.py",
    "candidate/containers/product/src/firmware/engine/panel/tests/host_checks.c",
    "candidate/containers/product/src/research/recipe_tweak/r2/tweak_int.c",
    "resident/v3_checks.c",
)
CORE_REL = Path("candidate/containers/product/src/firmware/engine/core/eng_core.c")
PRIVATE_HEADER_REL = Path(
    "candidate/containers/product/src/firmware/engine/core/eng_core_private.h")
PROFILES = {
    "daily": "research/xpan_realfix_r3/local/engine",
    "g188-r2": "research/boot_copyright_g188_r2/local/engine",
    "feat-hf2d": "research/xpan_realfix_r3/local/engine",
    "feat-hf2": "research/xpan_realfix_r3/local/engine",
    "feat-hf3d": "research/xpan_realfix_r3/local/engine",
    "feat-hf3": "research/xpan_realfix_r3/local/engine",
    "feat-hf4d": "research/xpan_realfix_r3/local/engine",
    "feat-hf4": "research/xpan_realfix_r3/local/engine",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def default_private_root():
    """The main checkout of the repository holding this script, or None outside Git."""
    try:
        common = subprocess.run(["git", "-C", str(MAIN), "rev-parse", "--path-format=absolute",
                                 "--git-common-dir"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return str(Path(common).parent) if common else None


def private_root(args):
    chosen = args.private_root or os.environ.get("GXR_PRIVATE_ROOT") or default_private_root()
    if not chosen:
        raise SystemExit("set GXR_PRIVATE_ROOT or pass --private-root (no Git checkout found)")
    root = Path(chosen).resolve()
    if not (root / "tools/loadgate.py").is_file():
        raise SystemExit("GXR_PRIVATE_ROOT is not the project checkout: " + str(root))
    return root


def one_match(pattern, text, label):
    found = pattern.findall(text)
    if len(found) != 1:
        raise SystemExit(label + ": expected 1 match, found " + str(len(found)))
    return found[0]


def unique_token(found, label):
    values = {item for item in found if item}
    if len(values) != 1:
        raise SystemExit(label + ": expected 1 value, found " + str(sorted(values)))
    return values.pop()


def private_header_text(source):
    """Pull factory-derived constants out of a profile's eng_core.c.

    The numbers stay in the generated header. This script does not contain them.
    """
    colour = one_match(
        re.compile(r"^([ \t]*static const uint16_t colour\[13\]=\{[^}]+\};)[ \t]*$", re.M),
        source, "colour offsets").strip()
    bw = one_match(
        re.compile(
            r"^([ \t]*static const uint16_t bw\[4\]=\{[^}]+\},te\[4\]=\{[^}]+\};)[ \t]*$",
            re.M),
        source, "bw/te offsets").strip()
    rows = one_match(
        re.compile(r"^([ \t]*static const uint16_t at\[10\]=\{[^}]+\};)[ \t]*$", re.M),
        source, "record row offsets").strip()
    wb0 = one_match(
        re.compile(r"\.offset=(0x[0-9a-fA-F]+); p->writes\[n\+\+\]\.value=wb\[0\]"),
        source, "wb0 offset")
    wb1 = one_match(
        re.compile(r"\.offset=(0x[0-9a-fA-F]+); p->writes\[n\+\+\]\.value=wb\[1\]"),
        source, "wb1 offset")
    recipe = one_match(
        re.compile(r"\.offset=(0x[0-9a-fA-F]+); p->writes\[n\+\+\]\.value=r\[3\]"),
        source, "recipe offset")
    span = unique_token(
        re.findall(r"io\.info\.length<(0x[0-9a-fA-F]+)\b", source), "settings span")
    copyright_at = unique_token(
        re.findall(r"settings\[(0x[0-9a-fA-F]+u)", source)
        + re.findall(r"settings\+(0x[0-9a-fA-F]+u)", source)
        + re.findall(r"(0x[0-9a-fA-F]+u)\+47u", source),
        "copyright offset")
    remembered = unique_token(re.findall(r"S\+(0x[0-9A-Fa-f]+)", source), "remembered offset")
    lines = [
        "#ifndef ENG_CORE_PRIVATE_H",
        "#define ENG_CORE_PRIVATE_H",
        "/* Generated by prepare_local.py from this profile's eng_core.c.",
        " * Camera setting offsets, record row offsets, and catalogue identity bytes.",
        " * The public eng_core.c includes this file and does not carry the values. */",
        "#define ENG_PLAN_COLOUR " + colour,
        "#define ENG_PLAN_BW_TE " + bw,
        "#define ENG_OFF_WB0 " + wb0,
        "#define ENG_OFF_WB1 " + wb1,
        "#define ENG_OFF_RECIPE " + recipe,
        "#define ENG_SETTINGS_SPAN " + span,
        "#define ENG_COPYRIGHT_AT " + copyright_at,
        "#define ENG_REMEMBERED_AT " + remembered,
        "#define ENG_ROW_AT " + rows,
    ]
    if "migration_tag" in source:
        block = one_match(
            re.compile(r"static const uint8_t known\[\]\[5\]=\{(.*?)\};", re.S),
            source, "catalogue identity")
        tags = [row.strip() for row in re.findall(r"\{[^{}]+\}", block)]
        if not tags:
            raise SystemExit("catalogue identity rows are empty")
        for row in tags:
            if not re.fullmatch(r"\{(?:\s*0x[0-9a-fA-F]{2}\s*,)*\s*0x[0-9a-fA-F]{2}\s*\}", row):
                raise SystemExit("catalogue identity row is not a byte list")
        lines.append("#define ENG_MIGRATION_TAG_ROWS \\")
        for index, row in enumerate(tags):
            tail = " \\" if index + 1 < len(tags) else ""
            comma = "," if index + 1 < len(tags) else ""
            lines.append("    " + row + comma + tail)
    lines.extend(["#endif", ""])
    return "\n".join(lines), "migration_tag" in source


def official_main(args, root):
    """Return the verified official MAIN image, its source and every official file for the guard."""
    others = []
    if args.official_main:
        path = Path(args.official_main).resolve()
        data, source = path.read_bytes(), str(path)
    else:
        archive = Path(args.official_zip).resolve() if args.official_zip else root / OFFICIAL_ZIP_REL
        if archive.is_file():
            with zipfile.ZipFile(archive) as bundle:
                members = [m for m in bundle.infolist()
                           if not m.is_dir() and Path(m.filename).name == OFFICIAL_MAIN_NAME]
                if len(members) != 1 or members[0].file_size > 32 * 1024 * 1024:
                    raise SystemExit("official ZIP needs exactly one " + OFFICIAL_MAIN_NAME + ": " + str(archive))
                data = bundle.read(members[0])
                others = [bundle.read(m) for m in bundle.infolist()
                          if not m.is_dir() and m is not members[0] and m.file_size <= 32 * 1024 * 1024]
            source = str(archive) + ":" + members[0].filename
        elif args.official_zip:
            raise SystemExit("missing official ZIP: " + str(archive))
        else:
            path = root / OFFICIAL_DIR_REL / OFFICIAL_MAIN_NAME
            if not path.is_file():
                raise SystemExit("missing official GXR 1.51 ZIP: " + str(archive)
                                 + " (or pass --official-zip / --official-main)")
            data, source = path.read_bytes(), str(path)
            others = [p.read_bytes() for p in sorted(path.parent.iterdir())
                      if p.is_file() and p.name != OFFICIAL_MAIN_NAME and not p.name.startswith(".")]
    if hashlib.sha256(data).hexdigest() != OFFICIAL_MAIN_SHA256:
        raise SystemExit("not the official GXR 1.51 MAIN image: " + source)
    return data, source, [data] + others


def image_sections(image):
    rows = []
    for index in range(16):
        source, load, size, bss, bss_size = struct.unpack_from(">5I", image, 0x20 + 20 * index)
        if not any((source, load, size, bss, bss_size)):
            break
        rows.append((0x200 + source, load, size))
    return rows


def image_bytes(image, sections, va, length):
    found = [start + va - load for start, load, size in sections
             if size and load <= va and va + length <= load + size]
    if len(found) != 1:
        raise SystemExit("L2N_ORIG_%08X_%d is not inside one MAIN image section" % (va, length))
    return image[found[0]:found[0] + length]


def engine_sources():
    """Every text file under engine/ (any suffix); binary files are skipped."""
    for path in sorted((MAIN / "engine").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        yield path, text


GUARD_TOKEN = re.compile(
    r"\\[xX]([0-9a-fA-F]{2})"
    r"|(?<![0-9A-Za-z_])0[xX]([0-9a-fA-F]{1,8})(?:[uU](?:[lL]{1,2})?|[lL]{1,2}[uU]?)?(?![0-9A-Za-z_])")
GUARD_GAP = re.compile(
    r"(?:[\s,;{}()\[\]|:+\-\"'`<>=]|\\\n|/\*.*?\*/|//[^\n]*|#[^\n]*"
    r"|\.(?:byte|short|hword|half|word|long|int|2byte|4byte)\b)*", re.S)
GUARD_HEXSTR = re.compile(r"(?<![0-9A-Za-z_])[0-9a-fA-F]{16,}(?![0-9A-Za-z_])")


def byte_runs(text, suffix=""):
    """Yield (line, bytes) for spelled-out byte runs; see the module docstring for the forms."""
    def line_of(pos):
        return text.count("\n", 0, pos) + 1

    def width_of(token, escaped):
        # 1-2 digits: byte; 3-4 digits: 16-bit word; 5-8 digits: 32-bit word.
        return 1 if escaped or len(token) <= 2 else (2 if len(token) <= 4 else 4)

    def emit(toks, width, start):
        if len(toks) * width < ORIG_MIN_RUN:
            return
        for order in (("big",) if width == 1 else ("big", "little")):
            yield line_of(start), b"".join(int(t, 16).to_bytes(width, order) for t in toks)

    toks, escaped, width, start, end = [], False, 1, 0, 0
    for match in GUARD_TOKEN.finditer(text):
        esc, pref = match.groups()
        token_width = width_of(esc or pref, bool(esc))
        if toks and (bool(esc) != escaped or token_width != width or match.start() - end > 240
                     or GUARD_GAP.fullmatch(text, end, match.start()) is None):
            yield from emit(toks, width, start)
            toks = []
        if not toks:
            escaped, width, start = bool(esc), token_width, match.start()
        toks.append(esc or pref)
        end = match.end()
    if toks:
        yield from emit(toks, width, start)
    for match in GUARD_HEXSTR.finditer(text):
        digits = match.group(0)
        for shift in (0, 1):
            part = digits[shift:shift + (len(digits) - shift) // 2 * 2]
            if len(part) >= 2 * ORIG_MIN_RUN:
                yield line_of(match.start()), bytes.fromhex(part)
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
                yield node.lineno, node.value
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "fromhex"
                  and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                try:
                    yield node.lineno, bytes.fromhex(node.args[0].value)
                except ValueError:
                    pass


def spelled_out_offenders(files, official):
    """Return 'path:line' for every run of >= ORIG_MIN_RUN bytes (3+ distinct) found in an official file."""
    haystack = (b"\0" * ORIG_MIN_RUN).join(official)
    offenders = []
    for label, text, suffix in files:
        for line, data in byte_runs(text, suffix):
            for begin in range(len(data) - ORIG_MIN_RUN + 1):
                window = data[begin:begin + ORIG_MIN_RUN]
                if len(set(window)) >= 3 and haystack.find(window) >= 0:
                    offenders.append(label + ":" + str(line))
                    break
    return sorted(set(offenders), key=lambda x: (x.rsplit(":", 1)[0], int(x.rsplit(":", 1)[1])))


def orig_header_text(image, official):
    """Define every L2N_ORIG_<VA>_<N> the public engine tree uses; check for spelled-out runs."""
    sections = image_sections(image)
    wanted, files = set(), []
    for path, text in engine_sources():
        wanted.update((int(va, 16), int(length)) for va, length in ORIG_NAME.findall(text))
        files.append((str(path.relative_to(MAIN)), text, path.suffix.lower()))
    offenders = spelled_out_offenders(files, official)
    if offenders:
        raise SystemExit("tracked engine files spell out byte runs found in the official MAIN image; "
                         "name them as L2N_ORIG_<VA>_<N> instead: " + ", ".join(offenders))
    lines = [
        "#ifndef L2N_ORIG_PRIVATE_H",
        "#define L2N_ORIG_PRIVATE_H",
        "/* Generated by prepare_local.py from the official GXR 1.51 MAIN image (ilaunch3).",
        " * L2N_ORIG_<VA>_<N> is the N bytes the official image holds at load address VA.",
        " * Local only: do not add this file to Git. */",
    ]
    for va, length in sorted(wanted):
        data = image_bytes(image, sections, va, length)
        lines.append("#define L2N_ORIG_%08X_%d %s" % (va, length, ",".join("0x%02x" % b for b in data)))
    lines.extend(["#endif", ""])
    return "\n".join(lines), len(wanted)


def copy_file(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return {"src": str(src), "dest": str(dest.relative_to(MAIN)), "bytes": dest.stat().st_size, "sha256": sha256(dest)}


def main():
    parser = argparse.ArgumentParser(description="Prepare local-only engine inputs")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="daily")
    parser.add_argument("--private-root", help="defaults to $GXR_PRIVATE_ROOT or the main checkout of this repository")
    parser.add_argument("--official-zip",
                        help="official GXR 1.51 ZIP; defaults to <private root>/" + str(OFFICIAL_ZIP_REL))
    parser.add_argument("--official-main", help="already extracted official ilaunch3 instead of the ZIP")
    args = parser.parse_args()
    root = private_root(args)
    engine = root / PROFILES[args.profile]
    local = MAIN / "local"
    rows = []
    for rel in LOCAL_FILES:
        src = engine / rel
        if not src.is_file():
            raise SystemExit("missing local source: " + str(src))
        rows.append(copy_file(src, local / "engine" / rel))
    core_src = engine / CORE_REL
    if not core_src.is_file():
        raise SystemExit("missing eng_core.c used to extract private constants: " + str(core_src))
    private_text, has_tags = private_header_text(core_src.read_text())
    private_dest = local / "engine" / PRIVATE_HEADER_REL
    private_dest.parent.mkdir(parents=True, exist_ok=True)
    private_dest.write_text(private_text)
    stale_core = local / "engine" / CORE_REL
    if stale_core.is_file():
        stale_core.unlink()
    rows.append({
        "src": str(core_src),
        "dest": str(private_dest.relative_to(MAIN)),
        "bytes": private_dest.stat().st_size,
        "sha256": sha256(private_dest),
        "note": "constants extracted from eng_core.c; catalogue tags " + ("present" if has_tags else "absent"),
    })
    image, image_source, official = official_main(args, root)
    orig_text, orig_names = orig_header_text(image, official)
    orig_dest = local / "engine" / ORIG_HEADER_REL
    orig_dest.parent.mkdir(parents=True, exist_ok=True)
    orig_dest.write_text(orig_text)
    rows.append({
        "src": image_source,
        "dest": str(orig_dest.relative_to(MAIN)),
        "bytes": orig_dest.stat().st_size,
        "sha256": sha256(orig_dest),
        "note": str(orig_names) + " L2N_ORIG names from the official MAIN image " + OFFICIAL_MAIN_SHA256[:8]
                + "; spelled-out run guard over " + str(len(official)) + " official files",
    })
    header_src = root / HEADER_REL
    if not header_src.is_file():
        raise SystemExit("missing g178 DAT used as the header template: " + str(header_src))
    header = header_src.read_bytes()[:256]
    if len(header) != 256 or not header.startswith(b"GXRCE001"):
        raise SystemExit("g178 DAT prefix is not a 256-byte GXRCE001 header")
    header_dest = local / "inputs" / "g178-header.bin"
    header_dest.parent.mkdir(parents=True, exist_ok=True)
    header_dest.write_bytes(header)
    rows.append({
        "src": str(header_src),
        "dest": str(header_dest.relative_to(MAIN)),
        "bytes": 256,
        "sha256": hashlib.sha256(header).hexdigest(),
        "note": "first 256 bytes only",
    })
    manifest = {"profile": args.profile, "engine": str(engine), "files": rows}
    (local / "PREPARED.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({
        "profile": args.profile,
        "files": len(rows),
        "header_sha256": rows[-1]["sha256"],
        "private_header": str(private_dest.relative_to(MAIN)),
        "orig_header": str(orig_dest.relative_to(MAIN)),
        "orig_names": orig_names,
        "catalogue_tags": has_tags,
    }, indent=2))


if __name__ == "__main__":
    main()
