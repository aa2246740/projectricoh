#!/usr/bin/env python3
"""List the TIFF/DNG directory structure of one file, read-only: IFDs, tags, data ranges."""

import argparse
import json
import struct
from pathlib import Path

TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 6: ("b", 1),
         7: ("B", 1), 8: ("h", 2), 9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8), 13: ("I", 4)}

NAMES = {
    254: "NewSubfileType", 256: "ImageWidth", 257: "ImageLength", 258: "BitsPerSample", 259: "Compression",
    262: "PhotometricInterpretation", 271: "Make", 272: "Model", 273: "StripOffsets", 274: "Orientation",
    277: "SamplesPerPixel", 278: "RowsPerStrip", 279: "StripByteCounts", 282: "XResolution", 283: "YResolution",
    284: "PlanarConfiguration", 296: "ResolutionUnit", 305: "Software", 306: "DateTime", 315: "Artist",
    322: "TileWidth", 323: "TileLength", 324: "TileOffsets", 325: "TileByteCounts", 330: "SubIFDs",
    513: "JPEGInterchangeFormat", 514: "JPEGInterchangeFormatLength", 529: "YCbCrCoefficients",
    530: "YCbCrSubSampling", 531: "YCbCrPositioning", 532: "ReferenceBlackWhite", 700: "XMP",
    33421: "CFARepeatPatternDim", 33422: "CFAPattern", 33432: "Copyright", 33434: "ExposureTime",
    33437: "FNumber", 34665: "ExifIFD", 34853: "GPSIFD", 34850: "ExposureProgram", 34855: "ISO",
    36864: "ExifVersion", 36867: "DateTimeOriginal", 36868: "DateTimeDigitized", 37377: "ShutterSpeedValue",
    37378: "ApertureValue", 37380: "ExposureBiasValue", 37381: "MaxApertureValue", 37383: "MeteringMode",
    37384: "LightSource", 37385: "Flash", 37386: "FocalLength", 37500: "MakerNote", 37510: "UserComment",
    40960: "FlashpixVersion", 40961: "ColorSpace", 40962: "PixelXDimension", 40963: "PixelYDimension",
    41495: "SensingMethod", 41728: "FileSource", 41729: "SceneType", 41985: "CustomRendered",
    41986: "ExposureMode", 41987: "WhiteBalance", 41988: "DigitalZoomRatio", 41989: "FocalLengthIn35mmFilm",
    41990: "SceneCaptureType", 41991: "GainControl", 41992: "Contrast", 41993: "Saturation", 41994: "Sharpness",
    50706: "DNGVersion", 50707: "DNGBackwardVersion", 50708: "UniqueCameraModel", 50709: "LocalizedCameraModel",
    50710: "CFAPlaneColor", 50711: "CFALayout", 50712: "LinearizationTable", 50713: "BlackLevelRepeatDim",
    50714: "BlackLevel", 50715: "BlackLevelDeltaH", 50716: "BlackLevelDeltaV", 50717: "WhiteLevel",
    50718: "DefaultScale", 50719: "DefaultCropOrigin", 50720: "DefaultCropSize", 50721: "ColorMatrix1",
    50722: "ColorMatrix2", 50723: "CameraCalibration1", 50724: "CameraCalibration2", 50727: "AnalogBalance",
    50728: "AsShotNeutral", 50729: "AsShotWhiteXY", 50730: "BaselineExposure", 50731: "BaselineNoise",
    50732: "BaselineSharpness", 50733: "BayerGreenSplit", 50734: "LinearResponseLimit",
    50735: "CameraSerialNumber", 50736: "LensInfo", 50737: "ChromaBlurRadius", 50738: "AntiAliasStrength",
    50739: "ShadowScale", 50740: "DNGPrivateData", 50741: "MakerNoteSafety", 50778: "CalibrationIlluminant1",
    50779: "CalibrationIlluminant2", 50780: "BestQualityScale", 50781: "RawDataUniqueID",
    50827: "OriginalRawFileName", 50829: "ActiveArea", 50830: "MaskedAreas", 50931: "CameraCalibrationSignature",
    50932: "ProfileCalibrationSignature", 50936: "ProfileName", 50937: "ProfileHueSatMapDims",
    50938: "ProfileHueSatMapData1", 50939: "ProfileHueSatMapData2", 50940: "ProfileToneCurve",
    50941: "ProfileEmbedPolicy", 50942: "ProfileCopyright", 50964: "ForwardMatrix1", 50965: "ForwardMatrix2",
    50966: "PreviewApplicationName", 50970: "PreviewColorSpace", 50981: "ProfileLookTableDims",
    50982: "ProfileLookTableData", 51008: "OpcodeList1", 51009: "OpcodeList2", 51022: "OpcodeList3",
    51041: "NoiseProfile",
}
SUB_IFD_TAGS = {330: "SubIFD", 34665: "ExifIFD", 34853: "GPSIFD"}


def read_ifd(data, offset, endian, label, out, seen):
    if offset in seen or offset <= 0 or offset + 2 > len(data):
        return
    seen.add(offset)
    count = struct.unpack_from(endian + "H", data, offset)[0]
    entries = []
    children = []
    for k in range(count):
        base = offset + 2 + 12 * k
        tag, typ, n = struct.unpack_from(endian + "HHI", data, base)
        fmt, size = TYPES.get(typ, ("B", 1))
        total = size * n
        value_offset = base + 8 if total <= 4 else struct.unpack_from(endian + "I", data, base + 8)[0]
        entry = {"tag": tag, "name": NAMES.get(tag, f"tag_{tag}"), "type": typ, "count": n,
                 "bytes": total, "data_offset": value_offset if total > 4 else None}
        raw = data[value_offset:value_offset + total]
        if typ == 2:
            entry["value"] = raw.split(b"\0")[0].decode("latin-1")
        elif typ in (5, 10):
            vals = struct.unpack_from(endian + fmt[0] * (2 * n), raw) if len(raw) == total else ()
            entry["value"] = [round(vals[i] / vals[i + 1], 6) if vals[i + 1] else None for i in range(0, len(vals), 2)][:12]
        elif typ in (1, 3, 4, 6, 8, 9, 11, 12, 13) and n <= 16:
            entry["value"] = list(struct.unpack_from(endian + fmt * n, raw)) if len(raw) == total else None
        elif typ == 7 and n <= 8:
            entry["value"] = raw.hex()
        if tag in SUB_IFD_TAGS:
            if typ in (4, 13):
                ptrs = struct.unpack_from(endian + "I" * n, data, value_offset) if total > 4 else [struct.unpack_from(endian + "I", data, base + 8)[0]]
                children += [(p, f"{label}/{SUB_IFD_TAGS[tag]}{i}") for i, p in enumerate(ptrs)]
        entries.append(entry)
    next_ifd = struct.unpack_from(endian + "I", data, offset + 2 + 12 * count)[0]
    out.append({"ifd": label, "offset": offset, "entries": entries, "next_ifd": next_ifd})
    for ptr, child in children:
        read_ifd(data, ptr, endian, child, out, seen)
    if next_ifd:
        read_ifd(data, next_ifd, endian, f"IFD{len([o for o in out if o['ifd'].count('/') == 0])}", out, seen)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dng", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = args.dng.read_bytes()
    endian = {b"II": "<", b"MM": ">"}[data[:2]]
    magic, first = struct.unpack_from(endian + "HI", data, 2)
    out = []
    read_ifd(data, first, endian, "IFD0", out, set())
    result = {"file": str(args.dng), "bytes": len(data), "byte_order": data[:2].decode(), "magic": magic, "ifds": out}
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.output:
        args.output.write_text(text + "\n")
    for ifd in out:
        print(f"== {ifd['ifd']} @0x{ifd['offset']:x}  next=0x{ifd['next_ifd']:x}")
        for e in ifd["entries"]:
            loc = f"@0x{e['data_offset']:x}" if e["data_offset"] is not None else ""
            val = e.get("value", "")
            print(f"  {e['tag']:5d} {e['name']:<28} n={e['count']:<8} {e['bytes']:>9}B {loc:<12} {str(val)[:90]}")


if __name__ == "__main__":
    main()
