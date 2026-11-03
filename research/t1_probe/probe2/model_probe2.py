"""Probe hypotheses and the explicit pre-lookup v2 colour chain. Analysis only."""
import importlib.util
import itertools
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location("probe2_core", Path(__file__).with_name("probe2_core.py"))
p = importlib.util.module_from_spec(sp)
sp.loader.exec_module(p)
import numpy as np


def hypotheses():
    out = []
    for semantics in ("absolute", "offset", "aux_offset"):
        for assignment in itertools.permutations("BCD"):
            out.append({"id": semantics + "_" + "".join(assignment),
                        "semantics": semantics, "RGB_tables": "".join(assignment)})
    for name in ("C", "D"):
        out.append({"id": "broadcast_" + name, "semantics": "absolute", "RGB_tables": name * 3})
    out.append({"id": "no_effect", "semantics": "absolute", "RGB_tables": "BBB"})
    return out


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, float) ** 2)))


class Engine:
    def __init__(self, display):
        self.src = p.generator()
        bank = (p.ROOT / "firmware/stage2j/examples/DEEPISP0.DAT").read_bytes()
        base = (p.BASE / "DEEPTBL0.DAT").read_bytes()
        p.require(p.sha(p.BASE / "DEEPTBL0.DAT") == p.BASE_SHA, "v3 source hash changed")
        self.entries = self.src.parse(base, bank)
        self.probe = self.src.parse((p.RAW_PACKAGE / "DEEPTBL0.DAT").read_bytes(), bank)
        self.mm = p.load("t1p2_matrix", p.ROOT / "research/color_table_fit/matrix_model.py")
        self.v2 = p.load("t1p2_v2", p.V2_CODE / "ring_model_v2.py")
        self.ar = self.v2.ar
        fs = p.load("t1p2_sector_fit", p.ROOT / "research/color_table_fit/fit_sectors.py")
        self.layout = self.ar.load_layout()
        self.grey = np.array([x["group"] == "gray" for x in self.layout["patches"]])
        self.ring = np.array([bool(x["ring"]) for x in self.layout["patches"]])
        self.model = json.loads(p.MODEL.read_text())
        p.require(self.model["schema"] == "gxr-sector-model/2" and
                  self.model["hue_coordinate"]["kind"] == "pre_table", "wrong model schema/coordinate")
        stock = self.entries[0]["rows"]
        self.row = self.mm.MatrixRow.from_bytes(stock[3][:28])
        p.require(self.row.to_bytes() == self.mm.read_stock_rows()["row1"].to_bytes(), "stock matrix differs")
        AB = np.asarray([fs.decode_word(stock[2][i:i + 4]) for i in range(0, 96, 4)])
        d0, d1 = fs.modifier(display)
        S = ((AB[:, 0] + d0) - 1j * (AB[:, 1] + d1)) / 32
        self.table = self.v2.PreTable(self.model, S)
        self.vivid = self.mm.read_vividness_table()["pct_by_level"][int(display["vividness"]) - 1]
        self.xs = np.array([0, *struct.unpack(">31H", stock[0]), 4095], float)
        self.curve = self.mm.Curve(self.xs, list(stock[1]))
        self.tables = {}
        for version, items in (("probe2", self.probe), ("v3", self.entries)):
            row = items[7]["rows"]
            self.tables[version] = {"B": np.array(list(row[1]), float),
                                    "C": np.array(list(row[6][:33]), float),
                                    "D": np.array(list(row[6][33:]), float)}
        self.hyps = hypotheses()

    def forward(self, x, hypothesis, version="probe2"):
        curves = self.tables[version]
        base = self.curve(x)
        columns = []
        for j, name in enumerate(hypothesis["RGB_tables"]):
            value = np.interp(np.clip(x[:, j], 0, 4095), self.xs, curves[name])
            if hypothesis["semantics"] == "offset" or (hypothesis["semantics"] == "aux_offset" and name != "B"):
                value = np.clip(base[:, j] + value, 0, 255)
            columns.append(value)
        rgbp = np.stack(columns, axis=1)
        y, c = self.row.apply(rgbp, self.vivid)
        co, _ = self.table.forward_stock(c)
        return np.clip(self.mm.rgb_from_ycc(y, co), 0, 255)

    def invert(self, rgb, camera_wb):
        hints = self.mm.hue_deg(self.row.apply(self.curve(camera_wb * 4095), self.vivid)[1])
        y, c = self.mm.ycbcr(rgb)
        ci, _ = self.table.inverse_stock(c, h_hint=hints)
        rgbp = self.row.invert(y, ci, self.vivid)
        x = self.curve.inverse(rgbp)
        check = self.forward(x, self.hyps[-1])
        return x, {"JPEG_roundtrip_max_codes": float(np.max(np.abs(check - rgb))),
                   "inverse_ambiguous_patches": self.table.last_ambiguity_count,
                   "out_of_stock_curve_range": int(np.sum(np.any((rgbp < self.curve.ys[0] - .5) |
                                                                    (rgbp > self.curve.ys[-1] + .5), axis=1)))}

    def predict(self, rgb, camera_wb, version="probe2"):
        x, quality = self.invert(rgb, camera_wb)
        stock = self.forward(x, self.hyps[-1], version)
        return {h["id"]: self.forward(x, h, version) - stock for h in self.hyps}, quality


def calibration(engine):
    folder = p.ROOT / "research/hue_ring/local/calibration_20261020"
    frames = []
    for n in (1179, 1182):
        f = json.loads((folder / f"R805{n}_frame.json").read_text())
        r = json.loads((folder / f"R805{n}_robust.json").read_text())
        frames.append({"rgb": np.array([q["stats"]["40"]["trim"] for q in r["patches"]]),
                       "cam_wb": np.array([q["cam_wb"] for q in f["patches"]]),
                       "meta": f["meta"], "H": np.array(f["H"])})
    return frames


def separation(predictions, repeat, engine):
    noise = max(rms(repeat), .25)
    pairs = []
    for a, b in itertools.combinations(predictions, 2):
        delta = predictions[a] - predictions[b]
        pairs.append({"a": a, "b": b, "RMS_codes": rms(delta),
                      "greys_RMS_codes": rms(delta[engine.grey]),
                      "repeatability_ratio": rms(delta) / noise})
    return {"repeatability_RMS_codes": rms(repeat), "noise_floor_codes": noise,
            "minimum_pair": min(pairs, key=lambda x: x["RMS_codes"]), "pairs": pairs}


def main():
    p.preflight()
    folder = p.ROOT / "research/hue_ring/local/calibration_20261020"
    meta = json.loads((folder / "R8051179_frame.json").read_text())["meta"]
    engine = Engine(meta["display"])
    a, b = calibration(engine)
    repeat = b["rgb"] - a["rgb"]
    results = {"model_sha256": p.sha(p.MODEL), "hypotheses": engine.hyps,
               "excluded": "R8051178", "patch_count": 155, "ring_count": 144, "grey_count": 9,
               "repeatability": {"all_RMS_codes": rms(repeat), "grey_max_abs_codes": float(abs(repeat[engine.grey]).max()),
                                 "grey_RMS_codes": rms(repeat[engine.grey])}, "versions": {}}
    for version in ("probe2", "v3"):
        pa, qa = engine.predict(a["rgb"], a["cam_wb"], version)
        pb, qb = engine.predict(b["rgb"], b["cam_wb"], version)
        pred = {key: .5 * (pa[key] + pb[key]) for key in pa}
        sep = separation(pred, repeat, engine)
        results["versions"][version] = {"grey_mean_dRGB": {key: value[engine.grey].mean(0) for key, value in pred.items()},
            "separation": sep, "prediction_04a_04b_max_RMS": max(rms(pa[k] - pb[k]) for k in pa),
            "inversion_quality": [qa, qb], "delta": pred}
        print(version, "min pair RMS", round(sep["minimum_pair"]["RMS_codes"], 3),
              "repeat ratio", round(sep["minimum_pair"]["repeatability_ratio"], 2), flush=True)
    p.dump(p.LOCAL / "predictions.json", results)
    p.dump(p.LOCAL / "baseline.json", {"04a": a, "04b": b})
    rows = ["hypothesis\tgrey_delta_R\tgrey_delta_G\tgrey_delta_B"]
    for key, rgb in results["versions"]["probe2"]["grey_mean_dRGB"].items():
        rows.append(key + "\t" + "\t".join(f"{v:.4f}" for v in rgb))
    p.save(p.HERE / "prediction_metrics.tsv", "\n".join(rows) + "\n")
    print("repeat RMS", round(rms(repeat), 4), "grey max", round(float(abs(repeat[engine.grey]).max()), 4))


if __name__ == "__main__":
    main()
