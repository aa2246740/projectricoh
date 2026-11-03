#!/usr/bin/env python3
"""复核原扫描纯函数的识别范围，并以官方矩阵行作参照。"""
import ast
import csv
import json
import runpy
import struct
from pathlib import Path

x = runpy.run_path(str(Path(__file__).with_name("audit.py")))
im, OUT, ROOT, save = x["Image"](), x["OUT"], x["ROOT"], x["save"]
source = ROOT / "research/hw_mining_r2/grok/scan_ccm.py"
tree = ast.parse(source.read_text())
names = {"sm12", "row_sums", "classify_nine", "scan_strict"}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert {n.name for n in nodes} == names
scale_node = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "SCALES" for t in n.targets))
scales = ast.literal_eval(scale_node.value)
env = {"SCALES": scales, "struct": struct}
# 只载入已阅读的四个纯函数，不运行原脚本的入口或目录操作。
module = ast.Module(body=nodes, type_ignores=[])
exec(compile(module, str(source), "exec"), env)
sections = [{"index": s["index"], "vma": s["vma"], "end": s["vma"] + s["size"],
             "file_offset": s["file_offset"], "data": im.read(s["vma"], s["size"])}
            for s in im.sections]
stored = []
with (ROOT / "research/tooling_m32r/sections/jlaunch3-sections.csv").open() as f:
    for row in csv.DictReader(f):
        stored.append((int(row["index"]), int(row["load_address"]),
                       int(row["file_offset"]), int(row["initialized_size"])))
actual = [(s["index"], s["vma"], s["file_offset"], s["size"]) for s in im.sections]
assert stored == actual
hits = env["scan_strict"](sections)
original_hits = []
for filename in ("look_hits.json", "identity_hits.json"):
    original_hits.extend(json.loads((ROOT / "research/hw_mining_r2/grok/evidence" / filename).read_text()))
def core(row):
    address = int(row["vma"], 0) if isinstance(row["vma"], str) else row["vma"]
    return address, row["kinds"], row["s16"]

assert sorted(map(core, hits)) == sorted(map(core, original_hits))
save("evidence/k3-strict-repeated.json", {"source_sha256": x["sha"](source.read_bytes()),
    "mapped_sections": len(sections), "mapped_bytes": sum(s["size"] for s in im.sections),
    "section_csv_matches_header": True, "matches_original_output": True, "hits": hits,
    "comparison_fields": ["vma", "kinds", "s16"],
    "scope": "原四个纯函数加独立解析的官方数据；未运行原脚本入口。"})

rows = []
for i in range(8):
    a = 0x2012D0C0 + 28 * i
    raw = im.read(a, 28)
    coeffs = struct.unpack(">9h", raw[:18])
    kinds, sums, decoded = env["classify_nine"](coeffs)
    rows.append({"selector": i + 1, "vma": hex(a), "file_offset": hex(im.offset(a)),
                 "u16": list(struct.unpack(">14H", raw)), "sm12": decoded,
                 "sm12_row_sums": [sum(decoded[j:j + 3]) for j in (0, 3, 6)],
                 "original_predicate": kinds})
assert rows[2]["original_predicate"] == []
assert rows[3]["sm12"] == [1024, 0, 0, 0, 1024, 0, 0, 0, 1024]
save("evidence/k3-known-row-coverage.json", rows)

neutral = [1024, 32, -32, -16, 1040, 0, 8, -8, 1024]
assert [sum(neutral[j:j + 3]) for j in (0, 3, 6)] == [1024] * 3

def sample(label, raw, target, stored_fields):
    h = env["scan_strict"]([{"index": 0, "vma": 0x30000000, "file_offset": 0,
                              "data": raw}])
    return {"case": label, "bytes": raw.hex(), "stored_fields": stored_fields,
            "intended_start": hex(0x30000000 + target),
            "intended_start_found": any(z["vma"] == 0x30000000 + target for z in h),
            "other_hits": h}

packed = struct.pack(">9h", *neutral)
padded = struct.pack(">12h", *(neutral[:3] + [0] + neutral[3:6] + [0] + neutral[6:] + [0]))
examples = [sample("连续18字节，起点4字节对齐", packed, 0, neutral),
            sample("同一矩阵，起点只按2字节对齐", b"\x00\x00" + packed, 2, neutral),
            sample("同一矩阵，每行补一个半字", padded, 0, neutral),
            sample("同一矩阵，以32位字段保存", struct.pack(">9i", *neutral), 0, neutral),
            sample("六个非对角项，主对角由行和计算", struct.pack(">6h", 32, -32, -16, 0, 8, -8),
                   0, [32, -32, -16, 0, 8, -8])]
assert examples[0]["intended_start_found"]
assert all(not e["intended_start_found"] for e in examples[1:])
save("evidence/k3-layout-examples.json", {"coefficient_reference": neutral, "examples": examples,
     "limits": "这些是判据覆盖面的构造数据，不是新发现的固件矩阵。运行时生成、其他数值格式及非归一化矩阵还需从消费者追查。"})
print(f"Official segments match: {len(sections)}; repeated strict hits: {len(hits)}")
print("Official selector3 is outside the original predicate; four alternate layouts omitted")
