"""核对最终源码、检查收据及覆盖率，生成复审清单。"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STUDIO = ROOT / "studio"


def read(name):
    return json.loads((OUT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    return subprocess.check_output(["git", *args], cwd=STUDIO, env=env).decode()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    run = read("make_check_final.result.json")
    assert run["exit_code"] == 0 and run["source_unchanged"]
    receipts = list(OUT.glob("make_check_final_pytest_*.json"))
    assert len(receipts) == 1
    tests = json.loads(receipts[0].read_text())
    assert tests["exit_code"] == tests["force_reruns"] == tests["rerun_max"] == 0
    assert tests["outcomes"] == {"passed": tests["collected"]}
    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    current = {name: sha(STUDIO / name) for name in names if name and (STUDIO / name).is_file()}
    assert current == run["source_sha256"]
    head = git("rev-parse", "HEAD").strip()
    branch = git("branch", "--show-current").strip()
    assert head == "f7bdc393f78940da612db916cfd11b95b44ff4b1" and branch == "main"
    assert not git("diff", "--cached", "--name-only").strip()
    assert not git("diff", "--check").strip()
    ui_run = read("focus_after.result.json")
    ui = read("focus_after_ui_check.json")
    assert ui_run["exit_code"] == 0 and ui_run["source_unchanged"]
    assert ui_run["source_sha256"] == current
    assert ui["status"] == "passed" and not ui["console_errors"]
    assert all(not check["overflow"] for check in ui["checks"])
    assert all(ui["confirmations"][name] == "passed" for name in ("lut", "group", "recipe"))
    assert ui["confirmations"]["default_focus"] == "取消"
    assert ui["confirmations"]["enter_confirms"] is False
    assert read("focus_after_ui_backend.json")["source_unchanged"] is True
    cache = read("cache_after.json")
    assert cache["url_changed"] and cache["thumb_changed"]
    assert cache["after_mean_rgb"] == cache["direct_mean_rgb"]
    baseline_path = ROOT / "research/studio_hdr_fix_r1/coverage.json"
    baseline = json.loads(baseline_path.read_text())["totals"]
    coverage = read("coverage.json")["totals"]
    assert coverage["percent_covered"] >= baseline["percent_covered"]
    save("coverage_comparison.json", {
        "baseline_file": str(baseline_path.relative_to(ROOT)), "baseline_sha256": sha(baseline_path),
        "baseline": baseline, "final": coverage,
        "difference_percentage_points": coverage["percent_covered"] - baseline["percent_covered"],
        "not_lower": True,
    })
    tracked = set(git("diff", "--name-only", "-z").split("\0")) - {""}
    added = set(git("ls-files", "--others", "--exclude-standard", "-z").split("\0")) - {""}
    rows = ["status\tpath\tsha256\tbytes"]
    for name in sorted(tracked | added):
        path = STUDIO / name
        rows.append(f"{'new' if name in added else 'modified'}\tstudio/{name}\t{sha(path)}\t{path.stat().st_size}")
    (OUT / "FILE_LIST.tsv").write_text("\n".join(rows) + "\n")
    save("final_evidence.json", {
        "head": head, "branch": branch, "host": os.uname().sysname,
        "index_unchanged": True, "diff_check": "passed", "source_matches_final_check": True,
        "source_file_count": len(current), "changed_file_count": len(tracked | added),
        "make_check_exit_code": run["exit_code"], "make_check_seconds": run["seconds"],
        "pytest_receipt": receipts[0].name, "pytest": tests,
        "ui_same_source_as_final_check": True, "ui_states": len(ui["checks"]),
        "ui_confirmations": ui["confirmations"], "coverage_not_lower": True,
    })
    print(json.dumps({"status": "passed", "tests": tests["collected"],
                      "coverage": coverage["percent_covered"], "changed_files": len(tracked | added)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
