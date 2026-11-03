"""Keep GPIO delivery, ordinary UI entry, ADJ construction and close as separate gates."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "local"
sys.path.insert(0, str(HERE))
from census import read as checkpoint_state
from storage_run import sha
from timeline import message_fields


def load(name):
    return json.loads((OUT / (name+".json")).read_text()) if name else {}


def producer(rows, key):
    return [((r["args"][1] >> 16) & 255) for r in rows
            if r["kind"] == "event-submit-call" and r["task"] == 3
            and r["args"][0] == 2 and r["args"][1] >> 24 == key]


def consumer(rows, key):
    return [message_fields(r).get("phase") for r in rows
            if r["kind"] == "queue1-wait-return" and r["task"] == 6
            and message_fields(r).get("message_type") == 0x700B
            and message_fields(r).get("key") == key]


def kinds(rows, name):
    return [row for row in rows if row["kind"] == name and row["task"] == 6]


def idle_states_recorded():
    rows = load("state-census-r1")["states"][:2]
    for row, expected in zip(rows, (0, 8)):
        current = checkpoint_state(ROOT / row["checkpoint"])
        if current["sha256"] != row["sha256"] or current["steps"] != 55000000 \
                or next(t["state"] for t in current["tasks"] if t["id"] == 6) != expected:
            return False
    return len(rows) == 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--keys", required=True)
    parser.add_argument("--adj", required=True)
    parser.add_argument("--close")
    parser.add_argument("--ready")
    parser.add_argument("--entry")
    parser.add_argument("--regression", default="regression-final-r2")
    parser.add_argument("--m2b", default="m2b-final-r2")
    parser.add_argument("--m2c", default="m2c-final-r2")
    args = parser.parse_args()
    target = OUT / (args.name+".json")
    if target.exists() or target.resolve().parent != OUT:
        raise ValueError("choose a fresh milestone result")
    key_run, adj, close = map(load, (args.keys, args.adj, args.close))
    rows = adj.get("flow", [])+close.get("flow", [])
    all_rows = load(args.entry).get("flow", [])+load(args.ready).get("flow", [])+rows
    panel, peer = load("panel-checks-final-r9"), load("peer-checks-final-r9")
    regression, cumulative_b, cumulative_c = map(load, (args.regression, args.m2b, args.m2c))
    key_codes = {"ADJ": 23, "OK": 24, "DISP": 21, "UP": 15, "DOWN": 18,
                 "LEFT": 17, "RIGHT": 16, "HALF": 13, "FULL": 14}
    phases = {name: producer(key_run.get("flow", []), code) for name, code in key_codes.items()}
    table_seen = any(row["kind"] == "watch-202b1220-point" and row["task"] == 6
                     and row.get("result") == 0x203764C8 for row in rows)
    dispatch_seen = any(row["kind"] == "watch-202b12a4-point" and row["task"] == 6
                        and row.get("result") == 0x202BA5C8 and row["args"][0] == 1 for row in rows)
    closed, states = False, None
    if args.ready:
        before = checkpoint_state(OUT / (args.ready+"-stop.pkl"))
        after_adj = checkpoint_state(OUT / (args.adj+"-stop.pkl"))
        before_state, adj_state = (state["native_words"]["0x205d9c00"] for state in (before, after_adj))
        states = {"before_ADJ": before_state, "after_ADJ": adj_state}
    if args.ready and args.close:
        after = checkpoint_state(OUT / (args.close+"-stop.pkl"))
        after_state = after["native_words"]["0x205d9c00"]
        states["after_close"] = after_state
        close_rows = close.get("flow", [])
        close_keys = [code for code, label in ((24, "adj-confirm"), (13, "adj-half-close"))
                      if 1 in producer(close_rows, code) and 1 in consumer(close_rows, code)
                      and kinds(close_rows, label+"-call") and kinds(close_rows, label+"-return")]
        closed = bool(close_keys) and adj_state == 56 and after_state == before_state != 56 \
            and bool(kinds(close_rows, "ui-event-return"))
    checks = {
        "original_Task6_idle_states_recorded": idle_states_recorded(),
        "GPIO_matrix_and_register_boundary": panel.get("passed") == panel.get("total") == 12,
        "native_Task3_all_nine_keys": all(1 in value and 0 in value for value in phases.values()),
        "native_ADJ_Task3_press_release": producer(rows, 23) == [1, 0],
        "native_ADJ_Task6_press_release": consumer(rows, 23) == [1, 0],
        "ordinary_UI_main_and_event": bool(kinds(all_rows, "ui-main-call")) and bool(kinds(all_rows, "ui-event-call")),
        "ADJ_table_event1_dispatch": table_seen and dispatch_seen,
        "ADJ_constructor_call_and_return": bool(kinds(rows, "adj-build-call")) and bool(kinds(rows, "adj-build-return")),
        "native_OK_or_HALF_close": closed,
        "finite_unit_model_checks": peer.get("passed") == peer.get("total") == 21,
        "four_cumulative_scripts": len(regression.get("checks", [])) == 4
                                   and all(row["returncode"] == 0 for row in regression.get("checks", [])),
        "M2b_22_of_22": cumulative_b.get("passed") == cumulative_b.get("total") == 22,
        "M2c_21_of_21": cumulative_c.get("passed") == cumulative_c.get("total") == 21,
    }
    result = {"milestone": "M2d", "verdict": "达成" if all(checks.values()) else "部分",
              "checks": checks, "passed": sum(checks.values()), "total": len(checks),
              "native_key_phases": phases, "ADJ_Task3_phases": producer(rows, 23),
              "ADJ_Task6_phases": consumer(rows, 23), "UI_states": states,
              "runs": {"keys": args.keys, "adj": args.adj, "close": args.close, "ready": args.ready, "entry": args.entry},
              "scope": "offline original-firmware execution with declared peripheral inputs"}
    result["unmet"] = {key: ("NOT_RUN_PRECONDITION" if key == "native_OK_or_HALF_close"
                               and not args.close else "NOT_OBSERVED")
                       for key, passed in checks.items() if not passed}
    names = {args.keys, args.adj, args.close, args.ready, args.entry,
             args.regression, args.m2b, args.m2c, "panel-checks-final-r9", "peer-checks-final-r9"}
    result["evidence_sha256"] = {name: sha(OUT / (name+".json")) for name in sorted(names-{None})}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("milestone", "verdict", "passed", "total")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
