"""Record the effective rerun options and every pytest outcome."""
import json
import os
from collections import Counter
from pathlib import Path
import pytest

counts = Counter()
rerun_max = 0

def pytest_sessionstart(session):
    if session.config.getoption("force_reruns") != 0:
        raise pytest.UsageError("This review requires --force-reruns 0")

def pytest_runtest_logreport(report):
    global rerun_max
    rerun_max = max(rerun_max, getattr(report, "rerun", 0))
    if report.when == "call" or report.outcome != "passed":
        counts[report.outcome] += 1

def pytest_sessionfinish(session, exitstatus):
    if counts["rerun"] or rerun_max:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    receipt = {"pid": os.getpid(), "host": os.uname().sysname,
               "nice": os.getpriority(os.PRIO_PROCESS, 0), "collected": session.testscollected,
               "outcomes": dict(counts), "rerun_max": rerun_max,
               "force_reruns": session.config.getoption("force_reruns"),
               "exit_code": int(session.exitstatus), "basetemp": session.config.getoption("basetemp")}
    target = Path(__file__).parent / (os.environ["REVIEW_LABEL"] + ".pytest.json")
    with target.open("x") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
        f.write("\n")
