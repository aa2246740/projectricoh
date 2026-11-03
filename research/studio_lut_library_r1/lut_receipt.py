"""记录每轮实际收集数、结果及重跑设置。"""

import json
import os
from collections import Counter
from pathlib import Path

import pytest

COUNTS = Counter()
RERUN_MAX = 0


def pytest_sessionstart(session):
    if session.config.getoption("force_reruns") != 0:
        raise pytest.UsageError("Requires --force-reruns 0")


def pytest_runtest_logreport(report):
    global RERUN_MAX
    RERUN_MAX = max(RERUN_MAX, getattr(report, "rerun", 0))
    if report.when == "call" or report.outcome != "passed":
        COUNTS[report.outcome] += 1


def pytest_sessionfinish(session, exitstatus):
    if COUNTS["rerun"] or RERUN_MAX:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    record = {"host": os.uname().sysname, "pid": os.getpid(), "collected": session.testscollected, "outcomes": dict(COUNTS),
              "rerun_max": RERUN_MAX, "force_reruns": session.config.getoption("force_reruns"), "exit_code": int(session.exitstatus)}
    target = Path(__file__).resolve().parent / f"{os.environ['LUT_CHECK_LABEL']}_pytest_{os.getpid()}.json"
    with target.open("x") as stream:
        json.dump(record, stream, indent=2)
