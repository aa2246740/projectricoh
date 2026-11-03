"""记录每一条测试结果，单独保留重跑事件。"""

import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent


def pytest_runtest_logreport(report):
    row = {"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome, "duration": report.duration}
    with (OUT / (os.environ.get("REVIEW_RUN_NAME", "pytest") + "-results.jsonl")).open("a") as fh:
        fh.write(json.dumps(row) + "\n")
