"""核对结束文案和原模块的公开导入入口。"""

import ast
import json
import os
import subprocess

import pytest

from gxr_studio.cards import importer, messages
from gxr_studio.cards.coverage import Coverage

from review_support import OUT, REPO, record


@pytest.mark.parametrize("photos,videos,expected", [
    (0, 0, "这张存储卡上的照片都已导入"),
    (2, 0, "已导入 2 张照片。现在可以推出存储卡了。"),
    (0, 2, "已导入 2 个视频。现在可以推出存储卡了。"),
    (2, 1, "已导入 2 张照片和 1 个视频。现在可以推出存储卡了。"),
])
def test_message_imports_and_text(photos, videos, expected):
    progress = importer.ImportProgress(imported_shots=photos, imported_videos=videos)
    cov = Coverage(True, "present")
    result = importer.done_message(progress, cov)
    assert result == expected
    assert importer.DONE_ALL == messages.DONE_ALL == "这张存储卡上的照片都已导入"
    assert importer.CHECK_FAILED == messages.CHECK_FAILED == "无法核对存储卡上的照片，请勿格式化存储卡。"
    record("message_imports_and_text", {"photos": photos, "videos": videos, "result": result})


def test_existing_repository_callers():
    old = subprocess.check_output(["git", "cat-file", "blob", "HEAD:src/gxr_studio/cards/importer.py"],
                                  cwd=REPO, env=dict(os.environ, GIT_OPTIONAL_LOCKS="0")).decode()
    old_functions = {node.name for node in ast.parse(old).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    former = "_done_message"
    current_callers = []
    for root in (REPO / "src", REPO / "tests"):
        for path in root.rglob("*.py"):
            nodes = ast.walk(ast.parse(path.read_text()))
            used = any((isinstance(node, ast.Name) and node.id == former)
                       or (isinstance(node, ast.Attribute) and node.attr == former)
                       or (isinstance(node, ast.ImportFrom) and any(item.name == former for item in node.names))
                       for node in nodes)
            if used:
                current_callers.append(str(path.relative_to(REPO)))
    result = {"former_private_name_in_head": former in old_functions,
              "former_private_name_available": hasattr(importer, former),
              "current_callers": current_callers,
              "public_names_available": {name: hasattr(importer, name) for name in ("DONE_ALL", "CHECK_FAILED", "done_message", "run_import", "stage_file")}}
    (OUT / "compatibility.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    assert all(result["public_names_available"].values())
    assert current_callers == []
