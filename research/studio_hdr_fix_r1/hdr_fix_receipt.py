"""Record actual pytest completion and reject any rerun."""
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

counts = Counter()
rerun_max = 0
start = None


def pytest_sessionstart(session):
    global start
    start = datetime.now(timezone.utc).isoformat()
    if session.config.getoption("force_reruns") != 0:
        raise pytest.UsageError("This check requires --force-reruns 0")


def pytest_runtest_logreport(report):
    global rerun_max
    rerun_max = max(rerun_max, getattr(report, "rerun", 0))
    if report.when == "call" or report.outcome != "passed":
        counts[report.outcome] += 1


def pytest_sessionfinish(session, exitstatus):
    if counts["rerun"] or rerun_max:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    record = {
        "pid": os.getpid(), "utc_start": start, "utc_end": datetime.now(timezone.utc).isoformat(),
        "host": os.uname().sysname, "collected": session.testscollected,
        "outcomes": dict(counts), "rerun_max": rerun_max, "exit_code": int(session.exitstatus),
        "force_reruns": session.config.getoption("force_reruns"),
    }
    label = os.environ["HDR_FIX_RUN_LABEL"]
    path = Path(__file__).resolve().parent / f"{label}_pytest_{os.getpid()}.json"
    with path.open("x") as stream:
        json.dump(record, stream, indent=2)
