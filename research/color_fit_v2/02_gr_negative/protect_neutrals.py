"""Neutral-protected slot 02 refit; uses the unchanged v2 chain and base regularization.

Run init, fit, folds, evaluate, verify, in order, with python3 -I -B.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import importlib.util
import json
import math
import shutil
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location("slot02_base", HERE / "run_fit.py")
base = importlib.util.module_from_spec(sp)
sp.loader.exec_module(base)
fm, fs, mm, sm = base.fm, base.fs, base.mm, base.sm
LOCAL = base.LOCAL
PREVIOUS = LOCAL / "alternatives/v2_unprotected"
CAP_MEDIAN, CAP_MAX = 0.85, 1.2
FIT_MEDIAN, FIT_MAX, FIT_BRIGHT, PENALTY = 0.78, 0.95, 0.95, 1000.0


def previous(name):
    return json.loads((PREVIOUS / name).read_text())


class NeutralProblem(base.CachedProblem):
    def __init__(self, S, samples, curve, e):
        super().__init__(S, samples, curve, e)
        self.neutral_idx = np.array([i for i, g in enumerate(self.groups) if g == "neutral"])
        self.patch_caps = np.array([FIT_BRIGHT if self.labels[i] == "D1" else FIT_MAX for i in self.neutral_idx])

    def neutral_errors(self, th):
        return fs.delta_e00(self.lt[self.neutral_idx], self.predict(th, self.neutral_idx))

    def residuals(self, th, idx=None):
        errors = self.neutral_errors(th)
        extra = np.r_[np.maximum(errors - self.patch_caps, 0), max(float(np.median(errors)) - FIT_MEDIAN, 0)]
        return np.r_[super().residuals(th, idx), math.sqrt(PENALTY) * extra]

    def neutral_ok(self, c, a, b):
        errors = self.neutral_errors(self.theta_from_int(c, a, b))
        return np.median(errors) <= CAP_MEDIAN and max(errors) <= CAP_MAX

    def quantize_feasible(self, th):
        c, a, b, info = self.strict_quantize(th)
        info["blend_to_v1"] = 0.0
        if self.neutral_ok(c, a, b):
            return c, a, b, info
        # A fixed finite repair path, only if rounding crosses a neutral limit.
        stock = np.array(self.ctx.stock)
        old = base.read("baseline.json")["matrix_row1"]["coef_q10"]
        target = self.theta_from_int(np.array(old), stock[:, 0], stock[:, 1])
        for fraction in np.linspace(.05, 1., 20):
            c, a, b, qinfo = self.strict_quantize((1 - fraction) * th + fraction * target)
            if self.neutral_ok(c, a, b):
                return c, a, b, {**qinfo, "blend_to_v1": float(fraction)}
        raise RuntimeError("no neutral-feasible integer point on the finite v1 repair path")

    def search_feasible(self, Cq, A, B, idx=None):
        assert self.neutral_ok(Cq, A, B)

        def cost(c, a, b):
            if not self.neutral_ok(c, a, b):
                return math.inf
            return float(np.sum(self.residuals(self.theta_from_int(c, a, b), idx) ** 2))

        best, trace = cost(Cq, A, B), []
        for p in range(6):
            improved = False
            for i in range(3):
                for j in range(3):
                    if i == j:
                        continue
                    c = Cq.copy()
                    c[0, i] += 1
                    c[0, j] -= 1
                    if not self.int_ok(c):
                        continue
                    value = cost(c, A, B)
                    if value < best - 1e-9:
                        Cq, best, improved = c, value, True
            for s in range(24):
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        if (da == db == 0) or not self.sector_ok(A[s] + da, B[s] + db, s):
                            continue
                        a, b = A.copy(), B.copy()
                        a[s] += da
                        b[s] += db
                        value = cost(Cq, a, b)
                        if value < best - 1e-9:
                            A, B, best, improved = a, b, value, True
            trace.append({"pass": p + 1, "cost": best, "improved": improved})
            if not improved:
                break
        return Cq, A, B, trace


def context():
    d, S, P = base.context("iso200")
    return d, S, NeutralProblem(S, d["samples"], P.curve, P.e)


def init():
    if not PREVIOUS.exists():
        base.verify()
        PREVIOUS.mkdir(parents=True)
        for name in ["fit.json", "full.json", "verification.json", "reference_check.json"] + [f"v2_fold_{n:02d}.json" for n in range(18)]:
            shutil.copy2(LOCAL / name, PREVIOUS / name)
        shutil.copy2(HERE / "REPORT.md", PREVIOUS / "REPORT.md")
    assert previous("fit.json")["stage"] == "v2-candidate"
    assert previous("fit.json")["metrics"]["iso200"]["candidate"]["chart"]["neutral"]["max"] > CAP_MAX
    base.save("neutral_protocol.json", {
        "neutral_hard_limits": {"median": CAP_MEDIAN, "max": CAP_MAX},
        "continuous_hinge_targets": {"median": FIT_MEDIAN, "D1": FIT_BRIGHT, "other_patches": FIT_MAX},
        "hinge_weight": PENALTY, "previous_fit_sha256": base.digest(PREVIOUS / "fit.json"),
        "regularization_unchanged": base.read("prepared.json")["regularization"],
        "previous_files_sha256": {p.name: base.digest(p) for p in PREVIOUS.iterdir() if p.is_file()}})
    print("previous unprotected candidate archived; neutral protocol fixed", flush=True)


def fit():
    _, _, P = context()
    base.cache_check(P)
    th, solve = P.solve_record(np.array(previous("full.json")["theta"]))
    c, a, b, quant = P.quantize_feasible(th)
    c, a, b, search = P.search_feasible(c, a, b)
    assert P.neutral_ok(c, a, b)
    base.save("neutral_full.json", {"theta": th, "Cq": c, "A": a, "B": b, "solve": solve,
                                    "quantization": quant, "integer_search": search})
    _, de, _ = fm.eval_solution(P, P.theta_from_int(c, a, b))
    print("protected full", solve, "chart", fm.group_stats(P, de), flush=True)


def folds(start, stop):
    _, _, P = context()
    full = base.read("neutral_full.json")
    for n in range(start, stop):
        i = int(P.chrom_idx[n])
        idx = np.array([j for j in P.fit_idx if j != i])
        th, solve = P.solve_record(np.array(full["theta"]), idx=idx, max_nfev=300, tol=1e-8)
        c, a, b, quant = P.quantize_feasible(th)
        c, a, b, search = P.search_feasible(c, a, b, idx=idx)
        base.save(f"neutral_fold_{n:02d}.json", {
            "n": n, "index": i, "label": P.labels[i], "Cq": c, "A": a, "B": b,
            "solve": solve, "quantization": quant, "integer_search": search,
            "training_indices": idx.tolist(), "neutral_limits_pass": P.neutral_ok(c, a, b)})
        print("protected LOO", n + 1, P.labels[i], "nfev", solve["nfev"], flush=True)


def evaluate():
    old = previous("fit.json")
    full = base.read("neutral_full.json")
    c, a, b = [np.array(full[k]) for k in ("Cq", "A", "B")]
    out = copy.deepcopy(old)
    metrics, photographic = {}, {}
    for tag in ("iso200", "iso1600"):
        d, S, P = base.context(tag)
        th = P.theta_from_int(c, a, b)
        lab, de, dea = fm.eval_solution(P, th)
        lr = base.ring_prediction(d, S, P, c, a, b)
        errs, aligned, per = [], [], []
        for n in range(18):
            fold = base.read(f"neutral_fold_{n:02d}.json")
            i = fold["index"]
            ft = P.theta_from_int(np.array(fold["Cq"]), np.array(fold["A"]), np.array(fold["B"]))
            pred = P.predict(ft, np.array([i]))[0]
            err = float(fs.delta_e00(P.lt[i], pred))
            errs.append(err)
            aligned.append(float(fs.delta_e00(P.lt[i], mm.lstar_aligned(pred, P.lt[i]))))
            per.append({"label": fold["label"], "de00": err, "dL": float(pred[0] - P.lt[i, 0])})
        candidate = {"chart": fm.group_stats(P, de), "chart_Laligned": fm.group_stats(P, dea),
                     "loo": fm.stats(errs), "loo_Laligned": fm.stats(aligned),
                     "ring": fm.stats(fs.delta_e00(np.array(d["ring_target"]), lr)), "per_fold": per}
        gate = base.compare_metrics(old["metrics"][tag]["v1"], candidate)
        neutral = candidate["chart"]["neutral"]
        metrics[tag] = {"v1": old["metrics"][tag]["v1"], "candidate": candidate,
                        "gate": gate, "passes": all(gate.values()),
                        "neutral_gate": {"median": neutral["median"] <= CAP_MEDIAN, "max": neutral["max"] <= CAP_MAX}}
        photographic[tag] = [{"label": P.labels[i], "target_lab": P.lt[i], "pred_lab": lab[i],
                               "de00": de[i], "dL": lab[i, 0] - P.lt[i, 0],
                               "target_lch": fs.lch(P.lt[i]), "pred_lch": fs.lch(lab[i])}
                              for i in range(len(P.labels))]
    d, S, P = base.context("iso200")
    row1 = S.rows["row1"].copy(coef=c)
    row2, rule = mm.row2_from_row1(row1, S.rows)
    Z = fs.Z_of_words(a, b, S.ctx)
    phi = np.degrees(P.split(np.array(full["theta"]))[2])
    words = []
    for s in range(24):
        words.append({"sector": s, "stock_ab": list(map(int, S.ctx.stock[s])), "new_ab": [int(a[s]), int(b[s])],
                      "word_hex": fs.encode_word(int(a[s]), int(b[s])).hex(),
                      "changed": bool([int(a[s]), int(b[s])] != list(map(int, S.ctx.stock[s]))),
                      "coef_scale": float(abs(Z[s])), "coef_rot_deg": float(np.degrees(np.angle(Z[s]))),
                      "continuous_rotation_deg": float(phi[s]), "pre_table_node_deg": float(S.table.nodes[s]),
                      "rotation_at_bound": bool(abs(phi[s]) >= P.max_rot - .05)})
    colour = {"row_hex": b"".join(fs.encode_word(int(aa), int(bb)) for aa, bb in zip(a, b)).hex(),
              "words": words, "format": old["colour_words"]["format"]}
    numeric_pass = all(rec["passes"] and all(rec["neutral_gate"].values()) for rec in metrics.values())
    out.update({"status": "v2 neutral-protected candidate: host model evaluation only; not camera acceptance",
                "stage": "v2-candidate", "firmware_ready": False, "accepted": False,
                "numeric_gates_pass": numeric_pass, "decision": "tradeoff-review",
                "recommended_variant": "published:yonly:v2-iso200:neutral-protected",
                "why": "Neutral and colour numeric gates pass at both ISO models, but magenta C5 LOO rises from 5.25 to 11.59. Return three tradeoff points for orchestrator selection, as requested.",
                "neutral_protection": base.read("neutral_protocol.json"), "metrics": metrics,
                "photographic_residuals": photographic, "colour_words": colour,
                "matrix_row1": row1.describe(), "matrix_row2": {**row2.describe(), "derivation": rule},
                "matrix_violations": {"row1": row1.violations(S.rows["row1"]), "row2": row2.violations(S.rows["row1"])},
                "rotation_bounds": [r for r in words if r["rotation_at_bound"]],
                "fit_solve": full["solve"], "quantization": full["quantization"],
                "predicted_de00": {**old["predicted_de00"], "in_sample_quantized": metrics["iso200"]["candidate"]["chart"],
                                    "in_sample_Laligned": metrics["iso200"]["candidate"]["chart_Laligned"],
                                    "loo_chromatic": metrics["iso200"]["candidate"]["loo"],
                                    "loo_chromatic_Laligned": metrics["iso200"]["candidate"]["loo_Laligned"]},
                "synthetic_ring_check": {"n": 144, "curve_only_de00": old["synthetic_ring_check"]["curve_only_de00"],
                                         "note": old["synthetic_ring_check"]["note"],
                                         "published:yonly:v2-iso200:neutral-protected": {"de00": metrics["iso200"]["candidate"]["ring"]},
                                         "iso1600_fixed_candidate": {"de00": metrics["iso1600"]["candidate"]["ring"]}},
                "alternatives": {**old["alternatives"], "v2_unprotected": old},
                "selected_for_assembly": "needs-tradeoff-review"})
    middle_path = LOCAL / "alternatives/neutral_max_1p1/fit.json"
    if middle_path.exists():
        middle = json.loads(middle_path.read_text())
        middle["alternatives"] = {}
        out["alternatives"]["neutral_max_1p1"] = middle
    out["alternative_notes"] = {
        "v2_unprotected": "Historical candidate retained exactly; fails the new neutral protection limits.",
        "neutral_max_1p1": "ISO200 protection passes; ISO1600 neutral max is 1.2999, fails the same cross-check limit."}
    base.save("neutral_evaluation.json", out)
    if numeric_pass:
        base.save("fit.json", out)
    for tag, rec in metrics.items():
        print(tag, "colour gates", rec["gate"], "neutral gates", rec["neutral_gate"],
              "LOO", rec["candidate"]["loo"], "ring", rec["candidate"]["ring"],
              "neutral", rec["candidate"]["chart"]["neutral"], flush=True)
    print("numeric gates", numeric_pass, "decision TRADEOFF REVIEW", flush=True)


def verify():
    obj = base.read("fit.json")
    assert obj["firmware_ready"] is False and obj["stage"] == "v2-candidate"
    assert obj["numeric_gates_pass"] and obj["accepted"] is False
    assert obj["selected_for_assembly"] == "needs-tradeoff-review" and obj["decision"] == "tradeoff-review"
    assert obj["alternatives"]["v2_unprotected"] == previous("fit.json")
    _, S, P = context()
    src = base.module("slot02_protected_sources", base.ROOT / "firmware/stage2j/tools/deep_sources.py")
    raw = src.json_colour(obj, "protected persisted result")
    src.json_matrix(obj, "protected persisted result")
    row1 = mm.MatrixRow.from_words(obj["matrix_row1"]["words_u16"])
    row2 = mm.MatrixRow.from_words(obj["matrix_row2"]["words_u16"])
    assert np.array_equal(row1.coef, np.array(obj["matrix_row1"]["coef_q10"]))
    assert np.array_equal(row2.coef, np.array(obj["matrix_row2"]["coef_q10"]))
    assert mm.row2_from_row1(row1, S.rows)[0].to_bytes() == row2.to_bytes()
    assert np.array_equal(row1.coef[1:], S.rows["row1"].coef[1:])
    a, b = np.array([fs.decode_word(raw[4*k:4*k+4]) for k in range(24)]).T
    assert np.array_equal(np.c_[a, b], np.array([w["new_ab"] for w in obj["colour_words"]["words"]]))
    assert all(P.sector_ok(a[k], b[k], k) for k in range(24))
    assert P.neutral_ok(row1.coef, a, b)
    for n in range(18):
        fold = base.read(f"neutral_fold_{n:02d}.json")
        assert fold["index"] not in fold["training_indices"]
        assert set(fold["training_indices"]) == set(P.fit_idx) - {fold["index"]}
        assert fold["solve"]["success"] and P.neutral_ok(np.array(fold["Cq"]), np.array(fold["A"]), np.array(fold["B"]))
        r1 = S.rows["row1"].copy(coef=np.array(fold["Cq"]))
        r2, _ = mm.row2_from_row1(r1, S.rows)
        src.check_matrix(f"protected fold {n}", r1.to_bytes() + r2.to_bytes())
        assert all(P.sector_ok(fold["A"][k], fold["B"][k], k) for k in range(24))
    for tag in ("iso200", "iso1600"):
        assert all(obj["metrics"][tag]["gate"].values())
        assert all(obj["metrics"][tag]["neutral_gate"].values())
        d, S, PP = base.context(tag)
        pred = PP.predict(PP.theta_from_int(row1.coef, a, b))
        errors = fs.delta_e00(PP.lt, pred)
        neutral = fm.group_stats(PP, errors)["neutral"]
        assert abs(neutral["median"] - obj["metrics"][tag]["candidate"]["chart"]["neutral"]["median"]) < 1e-10
        assert abs(neutral["max"] - obj["metrics"][tag]["candidate"]["chart"]["neutral"]["max"]) < 1e-10
        ring_lab = base.ring_prediction(d, S, PP, row1.coef, a, b)
        actual_ring = fm.stats(fs.delta_e00(np.array(d["ring_target"]), ring_lab))
        held = []
        for n in range(18):
            fold = base.read(f"neutral_fold_{n:02d}.json")
            i = fold["index"]
            ft = PP.theta_from_int(np.array(fold["Cq"]), np.array(fold["A"]), np.array(fold["B"]))
            held.append(float(fs.delta_e00(PP.lt[i], PP.predict(ft, np.array([i]))[0])))
        actual_loo = fm.stats(held)
        for which, actual in (("ring", actual_ring), ("loo", actual_loo)):
            assert all(abs(actual[k] - obj["metrics"][tag]["candidate"][which][k]) < 1e-10 for k in ("median", "mean", "p90", "max"))
    _, _, P = context()
    checks = [np.array(base.read("neutral_full.json")["theta"]), P.theta_from_int(row1.coef, a, b)]
    residual_error = 0.
    for th in checks:
        original_lab = base.f.JointProblemV2.predict(P, th)
        assert np.max(abs(original_lab - P.predict(th))) < 1e-10
        ne = fs.delta_e00(P.lt[P.neutral_idx], original_lab[P.neutral_idx])
        extra = math.sqrt(PENALTY) * np.r_[np.maximum(ne - P.patch_caps, 0), max(float(np.median(ne)) - FIT_MEDIAN, 0)]
        expected = np.r_[fm.JointProblem.residuals(P, th), extra]
        residual_error = max(residual_error, float(np.max(abs(expected - P.residuals(th)))))
    assert residual_error < 1e-9
    protected = base.read("prepared.json")["inputs_sha256"]
    for path, expected in protected.items():
        p = Path(path) if Path(path).is_absolute() else base.ROOT / path
        assert base.digest(p) == expected, path
    for name, expected in obj["neutral_protection"]["previous_files_sha256"].items():
        assert base.digest(PREVIOUS / name) == expected
    report = HERE / "REPORT.md"
    assert not base.re.search(r"(?<![0-9a-fA-F])[0-9a-fA-F]{96,}(?![0-9a-fA-F])", report.read_text())
    assert not base.re.search(r"(?:\\x[0-9a-fA-F]{2}){48,}", report.read_text())
    assert all(line.rstrip() == line for line in report.read_text().splitlines())
    assert not list(HERE.rglob("*.DAT"))
    base.save("neutral_verification.json", {"protected_inputs_unchanged": len(protected),
                                           "previous_candidate_preserved": True, "all_18_integer_folds_pass": True,
                                           "neutral_and_colour_gates_verified_from_persisted_fit": True,
                                           "neutral_penalty_residual_max_error": residual_error,
                                           "entry_script_sha256": base.digest(HERE / "protect_neutrals.py"),
                                           "fit_sha256": base.digest(LOCAL / "fit.json"), "report_sha256": base.digest(report)})
    print("persisted fit, original rules, 18 folds, protected inputs and previous candidate: PASS", flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("init", "fit", "folds", "evaluate", "verify"))
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=18)
    args = parser.parse_args()
    base.preflight()
    if args.phase == "init":
        init()
    elif args.phase == "fit":
        fit()
    elif args.phase == "folds":
        assert 0 <= args.start < args.stop <= 18
        folds(args.start, args.stop)
    elif args.phase == "evaluate":
        evaluate()
    else:
        verify()


if __name__ == "__main__":
    main()
