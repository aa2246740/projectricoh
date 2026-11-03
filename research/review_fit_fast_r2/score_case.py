"""Rebuild holdout scores and fixtures for one out-of-corpus paired fit."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated as iso
from isolated import rt
from engine import Problem
np = rt.np


def arrays(path):
    with rt.np.load(path, allow_pickle=False) as values:
        return dict(values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="start-07-3")
    ap.add_argument("--index", type=int, default=7)
    args = ap.parse_args()
    gate = iso.gate_module()
    folder = rt.PRIVATE / "solver_probes" / args.case
    paired = rt.read(folder / "result.json")
    saved = arrays(folder / "states.npz")
    index = args.index
    meta = rt.read(rt.SOURCE_LOCAL / f"target_{index:02d}.json")
    data = arrays(rt.SOURCE_LOCAL / f"target_{index:02d}.npz")
    groups = {group: arrays(rt.SOURCE_LOCAL / meta.get("group_files", {}).get(group, "samples_"+group+".npz"))
              for group in ("train", "synthetic", "a12-50", "a12-28", "mount-a12")}
    c = rt.camera_for_unit(meta.get("camera_ui", 0))
    p = Problem(c, saved["x"], saved["want"], saved["sw"], paired["config"])
    fixture = rt.ref_module("review_quality", "quality.py")
    gradients, rings = fixture.fixtures(c)
    results = {}
    for mode, name in (("exact", "exact_theta"), ("guarded_normal", "guard_theta")):
        packed = rt.plain(p.packed(saved[name]))
        gate.CHECK.integer_fields(packed)
        offsets = np.asarray(packed["matrix_offset_integer_hypothesis"])
        assert abs(np.r_[offsets[:3]+c.row.offsets, offsets[3:]]).max() <= 255
        state = p.unpack(packed)
        training_prediction = p.predict_state(state, saved["x"])
        assert np.array_equal(training_prediction, saved["exact_prediction" if mode == "exact" else "guard_prediction"])
        scores = {}
        for group, values in groups.items():
            if not len(values["x"]):
                scores[group] = None
                continue
            pred = p.predict_state(state, values["x"])
            scores[group] = rt.score(data[group+"_base"], pred, data[group+"_target"])
            if "photo_id" in values:
                scores[group]["per_photo"] = {}
                for photo in rt.np.unique(values["photo_id"]):
                    mask = values["photo_id"] == photo
                    scores[group]["per_photo"][str(photo)] = rt.score(data[group+"_base"][mask], pred[mask], data[group+"_target"][mask])
        quality = fixture.diagnostics(c, lambda x, rounding: p.predict_state(state, x, rounding), gradients, rings)
        results[mode] = dict(scores=scores, quality=quality, integer_fields_valid=True,
                             packed_state_rebuild_matches=True,
                             parameters=packed)
    old, new = results["exact"], results["guarded_normal"]
    fixtures, changes = gate.fixture_changes(old["quality"], new["quality"], {}, {})
    op, np_ = gate.photo_scores(old), gate.photo_scores(new)
    old_median, new_median = gate.median([v[0] for v in op.values()]), gate.median([v[0] for v in np_.values()])
    result = dict(case=args.case, target_index=index, training_delta=paired["objective_delta"],
                  old_photo_similarity_median=old_median, new_photo_similarity_median=new_median,
                  photo_similarity_delta_pp=None if old_median is None else new_median-old_median,
                  new_fixture_failures=fixtures, fixture_metric_deltas=changes,
                  photo_pairs=[dict(photo=photo, reference=op[photo], actual=np_[photo]) for photo in op],
                  results=results)
    iso.write("scored_"+args.case+".json", result)
    print(json.dumps({key: value for key, value in result.items() if key not in ("results", "photo_pairs")}))


if __name__ == "__main__":
    main()
