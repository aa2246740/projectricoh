#!/usr/bin/env python3
"""Slot-01 follow-up. Fixed regularization plus training-only skin/neutral penalties."""
import sys
sys.dont_write_bytecode = True
import argparse
import importlib.util
from pathlib import Path
import shutil
import signal
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("slot01_base",HERE / "run_fit.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
np = b.np
ARCHIVE = b.LOCAL / "round1"
PENALTY = 1000.0
SKIN_MARGIN = 0.03
NEUTRAL_MARGIN = 0.02


def inputs_unchanged():
    state = b.read(b.SCRATCH / "state.json")
    for path,expected in state["inputs_sha256"].items():
        assert b.sha(b.ROOT/path)==expected,path
    return state


def archive():
    if not ARCHIVE.exists():
        ARCHIVE.mkdir()
        for path in b.LOCAL.glob("*.json"):
            shutil.copy2(path,ARCHIVE/path.name)
        shutil.copy2(HERE / "REPORT.md",ARCHIVE / "REPORT.md")
    assert b.read(ARCHIVE/"fit.json")["decision"]=="reject_keep_v1"


class SkinProblem(b.CachedYProblem):
    def __init__(self,plain):
        state = b.read(b.SCRATCH / "state.json")
        super().__init__(plain.S,plain.samples,plain.curve,plain.e,state["regularization"])
        stock = np.array(self.ctx.stock)
        baseline = self.theta_from_int(np.array(state["baseline"]["Cq"]),stock[:,0],stock[:,1])
        base_error = b.fs.delta_e00(self.lt,self.predict(baseline))
        self.base_error = base_error
        self.skin_idx = [self.labels.index(label) for label in ("A1","A2")]
        self.neutral_idx = np.array([i for i,g in enumerate(self.groups) if g=="neutral"])
        self.skin_limits = base_error[self.skin_idx]+0.3
        self.neutral_limits = np.array([np.median(base_error[self.neutral_idx]),np.max(base_error[self.neutral_idx])])

    def protection_residuals(self,theta,idx):
        active = set(int(i) for i in idx)
        # Only training targets can enter these residuals or their thresholds.
        present = [i for i in self.skin_idx if i in active]
        residual = []
        if present:
            error = b.fs.delta_e00(self.lt[present],self.predict(theta,np.array(present)))
            residual.extend(np.maximum(error-(self.base_error[present]+0.3-SKIN_MARGIN),0.0))
        neutral = np.array([i for i in self.neutral_idx if int(i) in active])
        if len(neutral):
            error = b.fs.delta_e00(self.lt[neutral],self.predict(theta,neutral))
            baseline = self.base_error[neutral]
            residual.extend(np.maximum(np.array([np.median(error),np.max(error)])-
                                        np.array([np.median(baseline),np.max(baseline)])+NEUTRAL_MARGIN,0.0))
        return np.sqrt(PENALTY)*np.asarray(residual)

    def residuals(self,theta,idx=None):
        active = self.fit_idx if idx is None else idx
        return np.r_[super().residuals(theta,idx),self.protection_residuals(theta,active)]


def fit():
    inputs_unchanged()
    archive()
    P = SkinProblem(b.problem("200"))
    initial = np.array(b.read(ARCHIVE / "candidate_full.json")["theta"])
    theta,cost = P.solve(initial,max_nfev=500)
    quantized = b.quantize(P,theta)
    full = {"theta":theta,"cost_continuous":cost,"solver":P.last_solve,**quantized,
            "skin_penalty":PENALTY,"skin_fit_margin":SKIN_MARGIN,"neutral_fit_margin":NEUTRAL_MARGIN}
    b.save(b.SCRATCH / "skin_full.json",full)
    tq = P.theta_from_int(quantized["Cq"],quantized["A"],quantized["B"])
    error = b.fs.delta_e00(P.lt,P.predict(tq))
    print("full skin A1/A2",error[P.skin_idx].tolist(),"limits",P.skin_limits.tolist(),
          "neutral median/max",np.median(error[P.neutral_idx]),np.max(error[P.neutral_idx]),flush=True)


def folds(start,count):
    inputs_unchanged()
    P = SkinProblem(b.problem("200"))
    full = b.read(b.SCRATCH / "skin_full.json")
    originals = b.read(ARCHIVE / "loo_solutions.json")
    for position in range(start,min(start+count,len(P.chrom_idx))):
        i = int(P.chrom_idx[position])
        idx = np.array([j for j in P.fit_idx if j!=i])
        theta,cost = P.solve(np.array(full["theta"]),idx=idx,max_nfev=300,tol=1e-8)
        quantized = b.quantize(P,theta,idx=idx)
        original = originals[position]
        assert original["label"]==P.labels[i]
        b.save(b.SCRATCH / f"skin_fold_{position:02d}.json",{
            "index":i,"label":P.labels[i],"theta":theta,"cost_continuous":cost,
            "solver":P.last_solve,"quantized":quantized,"legacy_Cq":original["legacy_Cq"],
            "legacy_cost":original["legacy_cost"],
            "protected_training_skin":[P.labels[j] for j in P.skin_idx if j!=i]})
        print("skin fold",position,P.labels[i],"saved",flush=True)


def evaluate():
    inputs_unchanged()
    protections = {}
    def gate(P,tag,candidate,baseline,loo,ring):
        ce = b.fs.delta_e00(P.lt,candidate)
        be = b.fs.delta_e00(P.lt,baseline)
        ni = [i for i,g in enumerate(P.groups) if g=="neutral"]
        measures = {label:{"v1":float(be[P.labels.index(label)]),
                            "candidate":float(ce[P.labels.index(label)]),
                            "limit":float(be[P.labels.index(label)]+0.3)} for label in ("A1","A2")}
        measures["neutral"] = {"v1":b.fm.stats(be[ni]),"candidate":b.fm.stats(ce[ni])}
        protections[tag] = measures
        return {"loo_median_within_0_05":loo["candidate"]["median"]<=loo["v1"]["median"]+0.05,
                "loo_p90_does_not_worsen":loo["candidate"]["p90"]<=loo["v1"]["p90"],
                "ring_median_improves":ring["candidate"]["stats"]["median"]<ring["v1"]["stats"]["median"],
                "ring_p90_does_not_worsen":ring["candidate"]["stats"]["p90"]<=ring["v1"]["stats"]["p90"],
                "A1_within_v1_plus_0_3":measures["A1"]["candidate"]<=measures["A1"]["limit"],
                "A2_within_v1_plus_0_3":measures["A2"]["candidate"]<=measures["A2"]["limit"],
                "neutral_median_not_worse":np.median(ce[ni])<=np.median(be[ni]),
                "neutral_max_not_worse":np.max(ce[ni])<=np.max(be[ni])}
    settings={"round":"skin-protected-followup","loo_median_tolerance":0.05,"skin_tolerance":0.3,
              "protection_penalty":PENALTY,"skin_margin":SKIN_MARGIN,"neutral_margin":NEUTRAL_MARGIN,
              "model_used_for_training":"200","held_out_skin_protection_removed":True}
    b.evaluate(gate_builder=gate,round_info=settings,full_path=b.SCRATCH/"skin_full.json",
               fold_paths=[b.SCRATCH/f"skin_fold_{i:02d}.json" for i in range(18)])
    result = b.read(b.LOCAL / "evaluation.json")
    for tag,measure in protections.items():
        result["models"][tag]["protections"] = measure
    b.save(b.LOCAL / "evaluation.json",result)
    document = b.read(b.LOCAL / "fit.json")
    document["round_info"] = settings
    document["protections"] = protections
    document["why"] = ("Skin-protected integer fit passes LOO median tolerance 0.05, ring improvement, both p90, skin and neutral guards"
                        if result["accepted"] else "Skin-protected refit fails the follow-up gate; selected entry remains v1")
    document["model_gates"] = {tag:r["gate"] for tag,r in result["models"].items()}
    if result["accepted"]:
        previous = b.read(ARCHIVE/"fit.json")
        document["alternatives"] = {"v1_baseline":{key:previous[key] for key in ("matrix_row1","matrix_row2","colour_words")}}
    else:
        document["alternatives"]["skin_protected_refit"] = document["alternatives"].pop("rejected_v2_candidate")
    b.save(b.LOCAL / "fit.json",document)
    print("skin follow-up",document["decision"],"ISO1600 gate",result["models"]["1600"]["gate_passes"],flush=True)


def verify():
    inputs_unchanged()
    b.verify()
    P = SkinProblem(b.problem("200"))
    full = b.read(b.LOCAL / "candidate_full.json")
    theta = np.array(full["theta"])
    for label in ("A1","A2"):
        i = P.labels.index(label)
        idx = np.array([j for j in P.fit_idx if j!=i])
        before = P.residuals(theta,idx)
        P.lt[i] += [17.0,-23.0,31.0]
        after = P.residuals(theta,idx)
        P.lt[i] -= [17.0,-23.0,31.0]
        assert np.array_equal(before,after),"held-out skin target leaked into training"
    result = b.read(b.LOCAL / "evaluation.json")
    chosen = b.read(b.LOCAL / "fit.json")
    assert (chosen["decision"]=="accept")==all(result["models"]["200"]["gate"].values())
    if result["accepted"]:
        expected = b.validate(P,np.array(full["Cq"]),np.array(full["A"]),np.array(full["B"]))
        assert b.ds.json_matrix(chosen,"selected")==expected[0].to_bytes()+expected[1].to_bytes()
        assert b.ds.json_colour(chosen,"selected")==b"".join(
            b.fs.encode_word(a,bb) for a,bb in zip(full["A"],full["B"]))
    record = b.read(b.LOCAL / "verification.json")
    record["held_out_skin_target_perturbation_unchanged_residuals"] = True
    record["followup_gate_consistent"] = True
    b.save(b.LOCAL / "verification.json",record)
    print("PASS: selected follow-up entry, gate, and held-out skin target perturbation",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=("fit","folds","evaluate","verify"))
    parser.add_argument("--start",type=int,default=0)
    parser.add_argument("--count",type=int,default=6)
    args=parser.parse_args()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError("bounded follow-up stage exceeded 55 seconds")))
    signal.alarm(55)
    start=time.monotonic()
    if args.stage=="folds":folds(args.start,args.count)
    else:globals()[args.stage]()
    print("seconds",round(time.monotonic()-start,2),flush=True)
