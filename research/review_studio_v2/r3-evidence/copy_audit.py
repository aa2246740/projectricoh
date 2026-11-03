"""List Chinese API error literals with deterministic COPY checks; comments are ignored.

Only fixed COPY exceptions are exempted. Dynamic exception details stay visible
in the inventory because they can reach API messages. Final review adds the
separate note/status strings whose flow is traced manually.
"""
from __future__ import annotations
import ast
import csv
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
STUDIO = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
SLOTS = {"ApiError": 2, "EditError": 1, "CropError": 1, "ExportError": 1, "IntakeError": 2,
         "RenderUnavailable": 1, "LutError": 2, "RevealError": 2, "deny": 2}
EXEMPT = {"裁剪框超出画面范围", "近似效果只支持默认参数", "暂不支持写入存储卡",
          "存储卡上没有相机配方文件（GXRCE.DAT）", "无法读取编辑记录，已按原图显示",
          "校准数据与相机配方文件不匹配"}
FORBIDDEN = ("调节", "裁切", "画框", "日期戳", "印字", "亮度挡", "画面对比", "黑色色阶", "鲜艳度",
             "冷暖", "偏色", "晕影", "压暗四角", "色调曲线", "主曲线", "镜头畸变", "扭曲度", "纵横比",
             "长宽比", "原比例", "正方形", "横竖", "构图辅助线", "左右翻转", "镜像", "一键摆正", "还原",
             "清零", "全部还原", "恢复原图", "底子", "整体强度", "微调", "另存一份", "写回相机", "推到相机",
             "导入相机数据", "相机数据", "调色文件", "标定", "质量", "存到", "导出文件夹", "弹出", "拔卡", "归零")
MANUAL = {
    "src/gxr_studio/api/finish_routes.py": {35: "两句教学式说明；状态应只保留动作所需的一句"},
    "src/gxr_studio/api/render_routes.py": {244: "说明引擎来源与实测限制；含 knobs v2 内部名称"},
    "src/gxr_studio/api/lut_routes.py": {77: "教学句，仍使用禁用术语调色文件与输入空间是猜的"},
    "src/gxr_studio/api/camdata_routes.py": {58: "状态说明句，且一句话末带句号"},
    "src/gxr_studio/render/service.py": {
        270: "相机配方文件损坏时拼接出四句，超过两短句上限",
    },
    "src/gxr_studio/api/routes.py": {560: "长解释句、含 id 内部键，未按两短句给出行动"},
    "src/gxr_studio/camdata/intake.py": {35: "教学式说明；随多个错误响应拼进主句"},
    "src/gxr_studio/finish/serve.py": {151: "返回给调用方的标签仍写照片本身，COPY 3.10-6 要求原图"},
    "src/gxr_studio/library/thumbs.py": {
        108: "中性转换后附说明句；应只用中性转换",
        109: "内嵌预览后附解释句；应只用内嵌预览",
    },
    "src/gxr_studio/lut/worker.py": {154: "拟合未按前端生成配方术语；改为无法生成配方。请重试。"},
    "src/gxr_studio/lut/fit.py": {
        506: "长解释句，出现最不像的自造说法，并解释相机内部旋钮限制",
        509: "安慰式说明；相似度已有接近标签，不再追加整体已经很接近",
    },
    "src/gxr_studio/lut/service.py": {
        438: "拟合程序为内部实现；改为无法生成配方。请重试。",
        440: "生成配方的中断错误未写成两短句，含内部拟合术语",
    },
}


def main() -> None:
    inventory = []
    problems = []
    for file in sorted((STUDIO / "src/gxr_studio").rglob("*.py")):
        text = file.read_text()
        tree = ast.parse(text)
        rel = str(file.relative_to(STUDIO))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else ""
            idx = SLOTS.get(name)
            if idx is None or len(node.args) <= idx:
                continue
            message = node.args[idx]
            if not isinstance(message, (ast.Constant, ast.JoinedStr, ast.BoolOp)):
                continue
            segment = ast.get_source_segment(text, message) or ""
            if not re.search(r"[\u4e00-\u9fff]", segment):
                continue
            value = message.value if isinstance(message, ast.Constant) else segment
            record = {"file": rel, "line": message.lineno, "string": segment.replace("\n", " "), "reason": []}
            inventory.append(record)
            if value in EXEMPT:
                continue
            if segment.count("。") < 2:
                record["reason"].append("错误未写成两短句")
            words = [word for word in FORBIDDEN if word in segment]
            if words:
                record["reason"].append("禁用术语：" + "、".join(words))
            literal = " ".join(n.value for n in ast.walk(message) if isinstance(n, ast.Constant) and isinstance(n.value, str))
            if re.search(r"max_edge|jlaunch|qlaunch|l08firm|memory|recipe|levels|adjust|\bwb\b|\bwarm\b|\btint\b|\bids\b|\bwhich\b|\bprofile\b|\bfull\b|\blegal\b|\bthumb\b|\bpreview\b", literal):
                record["reason"].append("主句含内部接口键或枚举值")
            if ("{exc" in segment and "{exc.current}" not in segment) or "{last" in segment or ("{bad}" in segment and "export.py" in rel):
                record["reason"].append("直接拼接异常原文或文件路径")
            if record["reason"]:
                problems.append(record)
        for lineno, reason in MANUAL.get(rel, {}).items():
            line = text.splitlines()[lineno - 1].strip()
            assert line and not line.startswith("#"), (rel, lineno, line)
            # Manual rows are explicit source pointers and are checked against the current file.
            problems.append({"file": rel, "line": lineno, "string": line, "reason": [reason]})
    seen = set()
    unique = []
    for record in sorted(problems, key=lambda r: (r["file"], r["line"])):
        key = (record["file"], record["line"], record["string"])
        if key not in seen:
            seen.add(key)
            unique.append(record)
    (HERE / "copy-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    with (HERE / "COPY_VIOLATIONS.tsv").open("w") as out:
        writer = csv.writer(out, delimiter="\t")
        writer.writerow(["文件:行", "字符串", "不合规原因"])
        for r in unique:
            writer.writerow([f"{r['file']}:{r['line']}", r["string"], "；".join(r["reason"])])
    print(json.dumps({"error_expressions": len(inventory), "flagged_locations": len(unique)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
