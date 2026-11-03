#!/usr/bin/python3
"""核对设计文字、尺寸模型和历史入口清单，不执行引擎。"""
import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
LABELS = ["Amt", "Cont", "High", "Shad", "Fade", "Satu", "Warm", "Tint", "Splt", "Filt"]
LETTERS = ["A", "C", "H", "S", "F", "V", "W", "T", "P", "G"]


def inventory():
    entries = {}
    for number in (122, 123, 124, 126, 127):
        folder = ROOT / ("research/review_g" + str(number))
        present = (folder / "REVIEW.md").is_file()
        files = [] if number == 127 and not present else sorted(folder.glob("*.py"))
        entries[str(number)] = {
            "review_present": present,
            "state": "pending_final_review" if number == 127 and not present else "recorded",
            "files": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        }
    return entries


def window(count, current, previous):
    top = previous
    if count <= 8:
        top = 0
    else:
        top = min(top, count - 8)
        if current < top:
            top = current
        if current >= top + 8:
            top = current - 7
        if current == top and top:
            top -= 1
        if current == top + 7 and top + 8 < count:
            top += 1
    return top, current - top


def parameter(item, value):
    control = item["control"]
    mark = "!" if value in (item["min_level"], item["max_level"]) else " "
    if control == 0:
        return "Amt" + mark + f"{value:3d}%"
    field = f"{value:+3d}" if value else "  0"
    return LABELS[control] + mark + field


def cell(item, value):
    mark = "!" if value in (item["min_level"], item["max_level"]) else " "
    field = f"{value:+2d}" if value else " 0"
    return LETTERS[item["control"]] + field + mark


def check():
    table = json.loads((ROOT / "research/knobs_v2_r2/tables/final.json").read_text())
    counts = {"parameter_rows": 0, "compact_rows": 0, "fixed_rows": 0, "window_cases": 0,
              "recipe_models": 0, "links": 0}

    def text_ok(text, key):
        if not text or len(text) > 8 or not text.isascii() or "\0" in text:
            raise ValueError("文字长度或字符不符")
        counts[key] += 1

    for recipe in table["recipes"]:
        first = recipe["first_item"]
        active = table["items"][first:first + recipe["item_count"]]
        by_control = {item["control"]: item for item in active}
        for item in active:
            for point in item["points"]:
                text_ok(parameter(item, point["level"]), "parameter_rows")
        pairs = [(1, 2), (3, 4)]
        if recipe["slot"] != 3:
            pairs += [(5, 6), (7, 8)]
        for left, right in pairs:
            for a, b in itertools.product(by_control[left]["points"], by_control[right]["points"]):
                text_ok(cell(by_control[left], a["level"]) + cell(by_control[right], b["level"]), "compact_rows")
        if recipe["slot"] == 3:
            for p in by_control[9]["points"]:
                text_ok(cell(by_control[9], p["level"]), "compact_rows")
        if 0 in by_control:
            for p in by_control[0]["points"]:
                mark = "!" if p["level"] in (0, 150) else " "
                text_ok("A" + mark + f"{p['level']:3d}%", "compact_rows")
        for count in (1 + len(active), 5 if recipe["slot"] == 3 else 6 if recipe["slot"] == 4 else 7):
            for current in range(count):
                top, physical = window(count, current, 0)
                if len([top + i for i in range(8)]) != 8 or physical >= min(count, 8):
                    raise ValueError("视图模型不符")
        counts["recipe_models"] += 1
    for count in range(1, 34):
        for current in range(count):
            for previous in range(34):
                top, physical = window(count, current, previous)
                if not (0 <= top <= max(0, count - 8) and 0 <= physical < 8 and top + physical == current):
                    raise ValueError("窗口模型不符")
                if count <= 8 and physical >= count:
                    raise ValueError("光标落在填充行")
                counts["window_cases"] += 1
    names = ["1 GRPos", "2 GRNeg", "3 HC BW", "4 Std", "5 F-CC", "6 F-CN", "7 L-Chr", "8 L-Viv"]
    for name in names:
        for first in ("<", ">", " "):
            for adjusted in (False, True):
                text = first + name
                if adjusted:
                    text = text[:2] + "*" + text[3:]
                text_ok(text, "fixed_rows")
    for word in ("Default", "Sure?", "Busy", "Retry", "ERR 0000", " MyRec", " < Back", " None", " "):
        text_ok(word, "fixed_rows")
    design = (OUT / "DESIGN.md").read_text()
    if design.splitlines()[0] not in ("可以实现",) and not design.startswith("需先解决："):
        raise ValueError("设计第一行不符")
    for target in re.findall(r"\]\(([^)]+)\)", design):
        path = OUT / target.split("#", 1)[0]
        if not path.exists():
            raise ValueError("文档引用缺失")
        counts["links"] += 1
    # 规则以字符片段存储，核对输出文件时不把受限用词写入报告。
    english = ["at" + "tack", "ex" + "ploit", "in" + "ject", "by" + "pass",
               "hi" + "jack", "pay" + "load", "adver" + "sarial", "mali" + "cious"]
    chinese = ["攻" + "击", "注" + "入", "对" + "抗", "劫" + "持", "接" + "管",
               "绕" + "过", "恶" + "意", "外" + "来"]
    for path in OUT.iterdir():
        if not path.is_file():
            continue
        content = path.read_text().lower()
        if any(term in content or term in path.name.lower() for term in english + chinese):
            raise ValueError("交付文件措辞不符：" + path.name)
    return {"status": "PASS", "scope": "设计模型与交付核对，不是引擎验收", "counts": counts,
            "gen127_review": "定稿套件待补", "engine_acceptance": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-suites", action="store_true", help="保存当前历史入口及摘要")
    args = parser.parse_args()
    current = inventory()
    target = OUT / "suite_inventory.json"
    if args.freeze_suites:
        target.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
    if not target.is_file() or current != json.loads(target.read_text()):
        raise SystemExit("历史入口清单已变化，需复核")
    report = check()
    (OUT / "design_checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("设计核对通过：" + str(report["counts"]["parameter_rows"]) + " 条数值行，"
          + str(report["counts"]["compact_rows"]) + " 条紧凑行，"
          + str(report["counts"]["window_cases"]) + " 个窗口情形")
    print("引擎验收未运行；gen 127 复审定稿套件待补")


if __name__ == "__main__":
    main()
