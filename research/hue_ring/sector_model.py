#!/usr/bin/env python3
"""GXR JPEG colour-table sector model: kernels, forward model, estimator, JSON I/O.

Shared by research/hue_ring/analyze_ring.py (estimates the model from a hue
ring) and research/color_table_fit/fit_sectors.py (solves a 24-sector row
against targets). No firmware bytes live in this file.

Conventions (same as stage 2e):
  * plane: JPEG Cb/Cr of the sRGB codes, BT.601 full range, c = Cb + i*Cr;
  * hue: atan2(Cr, Cb) in degrees, counter-clockwise; sector number grows with it;
  * hue coordinate of the model = CbCr hue of the 04 Std output (stock table)
    of the same scene. For another mode the fitter uses the hue of that mode's
    base (04 colour + new curve per channel) by default;
  * word [A, B, B^0x80, A] = matrix [a, b; -b, a]/32, i.e. complex multiplier
    (A - iB)/32 on c. Probe/stock ratio Z_s; effective ratio
    Zk = |Z| exp(i k arg Z) with angle/scale coupling k (stage 2e: 0.97);
  * observed change z = c_new / c_base:
        mix "linear":    z - 1 = sum_s g_s w_s(h) (Zk_s - 1)
        mix "geometric": z     = exp(sum_s g_s w_s(h) log Zk_s)
  * kernels over 24 nodes n_0 < ... < n_23 < n_0 + 360 (cyclic):
        "linear": tent, w_s = 1 at n_s, 0 at n_{s-1} and n_{s+1};
        "hard":   w_s = 1 on [n_s, n_{s+1}) (n_s is the start boundary);
    both optionally blurred by a Gaussian in hue (sigma in degrees), either a
    constant ("const") or sigma_p = sqrt(s0^2 + (kappa/|c_p|)^2) ("chroma"),
    which is what per-pixel noise before a hard lookup produces on ROI means.
"""
import json
import math

import numpy as np
from scipy.optimize import least_squares
from scipy.special import ndtr

SCHEMA = "gxr-sector-model/1"
N = 24
PROBE_SECTORS = {"07": (0, 4, 8, 12, 16, 20), "08": (2, 6, 10, 14, 18, 22)}
PROBE_ANGLES = (18, 12, 6, -6, -12, -18)
PROBE_SCALE = 1.30
SIGMA_ZERO = 1e-4  # degrees; "no blur" without a branch
RAD = math.pi / 180


# ----------------------------------------------------------------- colour helpers

def ycbcr(rgb):
    """BT.601 full range on sRGB codes (0..255). rgb (..., 3) -> (..., 3)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return np.stack([0.299 * r + 0.587 * g + 0.114 * b,
                     -0.168736 * r - 0.331264 * g + 0.5 * b,
                     0.5 * r - 0.418688 * g - 0.081312 * b], axis=-1)


def rgb_from_ycc(y, cb, cr):
    return np.stack([y + 1.402 * cr, y - 0.344136 * cb - 0.714136 * cr, y + 1.772 * cb], axis=-1)


def hue_deg(c):
    return np.degrees(np.angle(c)) % 360


def wrap180(x):
    return (np.asarray(x, dtype=np.float64) + 180) % 360 - 180


def circ_mean_deg(h, w):
    h, w = np.asarray(h, float), np.asarray(w, float)
    return float(np.degrees(np.arctan2((w * np.sin(h * RAD)).sum(), (w * np.cos(h * RAD)).sum())) % 360)


def nominal_design():
    """Probe/stock design ratio without the five-colour modifier (scale 1.30, +-6/12/18 deg)."""
    Z = {}
    for key, secs in PROBE_SECTORS.items():
        for s, a in zip(secs, PROBE_ANGLES):
            Z[s] = PROBE_SCALE * complex(math.cos(a * RAD), math.sin(a * RAD))
    return Z


def effective(Z, k):
    """Zk = |Z| exp(i k arg Z)."""
    Z = np.asarray(Z, dtype=np.complex128)
    return np.abs(Z) * np.exp(1j * k * np.angle(Z))


def probe_vectors(Zdesign, k):
    """24-vectors of Zk_s for each probe (1 for sectors the probe leaves at stock)."""
    out = {}
    for key, secs in PROBE_SECTORS.items():
        v = np.ones(N, dtype=np.complex128)
        for s in secs:
            v[s] = effective(Zdesign[s], k)
        out[key] = v
    return out


# ----------------------------------------------------------------- kernels

def _phi(t):
    return np.exp(-0.5 * t * t) * (1.0 / math.sqrt(2 * math.pi))


def _ramp(d, sigma):
    """E[(d + e)_+], e ~ N(0, sigma^2)."""
    t = d / sigma
    return d * ndtr(t) + sigma * _phi(t)


def _step(d, sigma):
    return ndtr(d / sigma)


def weights(h, nodes, kernel, sigma):
    """Kernel weights w_s(h), shape (P, 24).

    h: (P,) hue in degrees. nodes: (24,) increasing, n_23 < n_0 + 360.
    sigma: scalar or (P,) Gaussian blur in degrees (>= SIGMA_ZERO).
    """
    n = np.asarray(nodes, dtype=np.float64)
    # hue folded into [n_0, n_0 + 360): three turns then cover every support and blur tail
    h = (np.asarray(h, dtype=np.float64) - n[0]) % 360 + n[0]
    X = h[None, :, None] + _SHIFTS[:, None, None]                      # (3, P, 1)
    sig = np.maximum(np.asarray(sigma, dtype=np.float64), SIGMA_ZERO)
    sig = sig.reshape(1, 1, -1, 1) if sig.ndim else sig
    if kernel == "linear":
        a = np.concatenate([n[-1:] - 360, n[:-1]])   # n_{s-1}
        c = np.concatenate([n[1:], n[:1] + 360])     # n_{s+1}
        ba, cb = n - a, c - n
        R = _ramp(X[None] - np.stack([a, n, c])[:, None, None, :], sig)   # (3 knots, 3 turns, P, 24)
        W = (R[0] / ba - R[1] * (1 / ba + 1 / cb) + R[2] / cb).sum(0)
    elif kernel == "hard":
        hi = np.concatenate([n[1:], n[:1] + 360])
        S = _step(X[None] - np.stack([n, hi])[:, None, None, :], sig)
        W = (S[0] - S[1]).sum(0)
    else:
        raise ValueError(kernel)
    return np.clip(W, 0.0, None)


_SHIFTS = np.array([-360.0, 0.0, 360.0])


def blur_of(spec_blur, s0, kappa, cmag):
    if spec_blur == "zero":
        return SIGMA_ZERO
    if spec_blur == "const":
        return s0
    if spec_blur == "chroma":
        return np.sqrt(s0 ** 2 + (kappa / np.maximum(cmag, 1e-3)) ** 2)
    raise ValueError(spec_blur)


def sector_centres(nodes, kernel):
    n = np.asarray(nodes, float)
    if kernel == "linear":
        return n % 360
    hi = np.concatenate([n[1:], n[:1] + 360])
    return ((n + hi) / 2) % 360


# ----------------------------------------------------------------- model JSON

def model_predict_z(model, h, cmag, Zrow, ring=None):
    """Change z = c_new/c_base for colours at hue h under a sector row with
    *coefficient-domain* ratios Zrow (24 complex, 1 = stock). Uses k, gain, kernel."""
    nodes = np.asarray(model["nodes_deg"], float)
    kern = model["kernel"]
    sig = blur_of(kern.get("blur_mode", "const") if kern.get("blur_deg", 0) or kern.get("blur_kappa", 0) else "zero",
                  kern.get("blur_deg", 0.0), kern.get("blur_kappa", 0.0), np.asarray(cmag, float))
    W = weights(h, nodes, kern["type"], sig)
    g = np.asarray(model.get("gain_per_sector") or [model["gain"]] * N, float)
    W = W * g[None, :]
    if ring is not None and model.get("gain_ring_ratio"):
        rr = np.where(np.asarray(ring) == 2, model["gain_ring_ratio"], 1.0)
        W = W * rr[:, None]
    Zk = effective(Zrow, model.get("k_coupling", 1.0))
    if kern.get("mix", "linear") == "geometric":
        return np.exp(W @ np.log(Zk))
    return 1 + W @ (Zk - 1)


def save_model(path, model):
    path.write_text(json.dumps(jsonable(model), indent=1) + "\n")


def load_model(path):
    m = json.loads(path.read_text())
    if m.get("schema") != SCHEMA:
        raise SystemExit(f"{path}: schema {m.get('schema')} != {SCHEMA}")
    return m


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, np.ndarray):
        return jsonable(x.tolist())
    if isinstance(x, complex):
        return [x.real, x.imag]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


# ----------------------------------------------------------------- estimator

class Spec:
    """One model variant to fit. blur: "zero" | "const" | "chroma" | float (fixed, degrees)."""

    def __init__(self, kernel, blur="const", gain="global", k="free", offsets=True, mix="linear",
                 ring_gain=False, ring_shift=False, name=None):
        self.kernel, self.blur, self.gain, self.k = kernel, blur, gain, k
        self.offsets, self.mix, self.ring_gain, self.ring_shift = offsets, mix, ring_gain, ring_shift
        self.name = name or self.label()

    @property
    def fixed_blur(self):
        return isinstance(self.blur, (int, float)) and not isinstance(self.blur, bool)

    def label(self):
        parts = [self.kernel, "blur=" + (f"{self.blur:g}deg" if self.fixed_blur else self.blur)]
        if self.gain != "global":
            parts.append(f"gain={self.gain}")
        if self.ring_gain:
            parts.append("ring_gain")
        if self.ring_shift:
            parts.append("ring_shift")
        if self.mix != "linear":
            parts.append(f"mix={self.mix}")
        if self.k != "free":
            parts.append(f"k={self.k}")
        return "+".join(parts)

    def replace(self, **kw):
        d = {k: getattr(self, k) for k in ("kernel", "blur", "gain", "k", "offsets", "mix", "ring_gain",
                                            "ring_shift")}
        d.update(kw)
        return Spec(**d)

    def as_dict(self):
        return {k: getattr(self, k) for k in ("kernel", "blur", "gain", "k", "offsets", "mix", "ring_gain",
                                               "ring_shift", "name")}


class Layout:
    def __init__(self, spec, init):
        self.slices, self.x0, self.lo, self.hi = {}, [], [], []
        nodes = np.asarray(init["nodes"], float)
        n0 = nodes[0]
        gaps = np.diff(np.concatenate([nodes, [n0 + 360]]))
        q = np.log(np.maximum(gaps, 0.3) / 360)
        q -= q.mean()
        self.add("n0", [n0], [n0 - 90], [n0 + 90])
        self.add("q", q, [-6] * N, [6] * N)
        probed = sorted(PROBE_SECTORS["07"] + PROBE_SECTORS["08"])
        g0 = np.asarray(init.get("gain_sector") if spec.gain == "sector" and init.get("gain_sector") is not None
                        else [init["gain"]] * (len(probed) if spec.gain == "sector" else 1), float)
        if spec.gain == "sector" and len(g0) == N:
            g0 = g0[probed]
        g0 = np.clip(np.nan_to_num(g0, nan=init["gain"]), 0.06, 2.9)
        self.add("lg", np.log(g0), [math.log(0.05)] * len(g0), [math.log(3.0)] * len(g0))
        if spec.ring_gain:
            self.add("lg2", [0.0], [-1.5], [1.5])
        if spec.ring_shift:
            self.add("dn2", [0.0], [-20.0], [20.0])
        if spec.blur in ("const", "chroma"):
            self.add("ls0", [math.log(max(init.get("blur", 1.0), 0.03))], [math.log(0.02)], [math.log(40.0)])
        if spec.blur == "chroma":
            self.add("lkap", [math.log(max(init.get("kappa", 30.0), 0.6))], [math.log(0.5)], [math.log(3000.0)])
        if spec.k == "free":
            self.add("k", [init.get("k", 0.97)], [0.5], [1.5])
        if spec.offsets:
            self.add("eps", [0.0] * 4, [-0.3] * 4, [0.3] * 4)
        self.x0 = np.array(self.x0, float)
        self.lo, self.hi = np.array(self.lo, float), np.array(self.hi, float)
        self.x0 = np.clip(self.x0, self.lo + 1e-9, self.hi - 1e-9)
        self.probed = probed

    def add(self, name, x0, lo, hi):
        a = len(self.x0)
        self.x0 += list(x0)
        self.lo += list(lo)
        self.hi += list(hi)
        self.slices[name] = slice(a, len(self.x0))

    def get(self, x, name, default=None):
        sl = self.slices.get(name)
        return default if sl is None else x[sl]

    def set_nodes(self, x, nodes):
        x = x.copy()
        gaps = np.diff(np.concatenate([nodes, [nodes[0] + 360]]))
        q = np.log(np.maximum(gaps, 1e-6) / 360)
        x[self.slices["n0"]] = nodes[0]
        x[self.slices["q"]] = np.clip(q - q.mean(), self.lo[self.slices["q"]] + 1e-9, self.hi[self.slices["q"]] - 1e-9)
        return x


def nodes_from(n0, q):
    e = np.exp(q - q.max())
    gaps = 360 * e / e.sum()
    return n0 + np.concatenate([[0.0], np.cumsum(gaps[:-1])])


class Fitter:
    """Least-squares estimator of nodes / kernel / gain from probe changes.

    obs: dict with arrays h (deg, CbCr hue of the base), cmag (|c_base|), ring (1/2),
    sig (complex noise std of z), dz07, dz08 (complex z - 1), labels.
    """

    def __init__(self, obs, Zdesign, reg=1.0):
        self.obs = obs
        self.Z = Zdesign
        self.reg = reg
        self.P = len(obs["h"])

    def unpack(self, spec, L, x):
        n0 = L.get(x, "n0")[0]
        nodes = nodes_from(n0, L.get(x, "q"))
        lg = L.get(x, "lg")
        if spec.gain == "sector":
            gvals = np.exp(lg)
            gain = np.full(N, float(np.median(gvals)))
            gain[L.probed] = gvals
        else:
            gain = np.full(N, math.exp(lg[0]))
        if spec.fixed_blur:
            s0 = float(spec.blur)
        else:
            s0 = math.exp(L.get(x, "ls0", [math.log(SIGMA_ZERO)])[0])
        kap = math.exp(L.get(x, "lkap", [-50.0])[0])
        k = L.get(x, "k", [spec.k if spec.k != "free" else 1.0])[0]
        eps = L.get(x, "eps", [0, 0, 0, 0])
        return {"nodes": nodes, "gain": gain, "blur": s0, "kappa": kap, "k": float(k),
                "eps": {"07": complex(eps[0], eps[1]), "08": complex(eps[2], eps[3])},
                "ring_gain_ratio": math.exp(L.get(x, "lg2", [0.0])[0]),
                "ring2_shift": float(L.get(x, "dn2", [0.0])[0])}

    def sigma_of(self, spec, m, o):
        mode = "const" if spec.fixed_blur else spec.blur
        return blur_of(mode, m["blur"], m["kappa"], o["cmag"])

    def predict(self, spec, m, obs=None):
        o = self.obs if obs is None else obs
        P = len(o["h"])
        sig = np.broadcast_to(np.asarray(self.sigma_of(spec, m, o), float), (P,))
        if spec.ring_shift:
            r2 = o["ring"] == 2
            W = np.zeros((P, N))
            if (~r2).any():
                W[~r2] = weights(o["h"][~r2], m["nodes"], spec.kernel, sig[~r2])
            if r2.any():
                W[r2] = weights(o["h"][r2], m["nodes"] + m["ring2_shift"], spec.kernel, sig[r2])
        else:
            W = weights(o["h"], m["nodes"], spec.kernel, sig)
        W = W * m["gain"][None, :]
        if spec.ring_gain:
            W = W * np.where(o["ring"] == 2, m["ring_gain_ratio"], 1.0)[:, None]
        vec = probe_vectors(self.Z, m["k"])
        out = {}
        for key in ("07", "08"):
            if spec.mix == "geometric":
                z = np.exp(W @ np.log(vec[key]))
            else:
                z = 1 + W @ (vec[key] - 1)
            out[key] = (1 + m["eps"][key]) * z - 1
        return out, W

    def residuals(self, spec, L, x):
        m = self.unpack(spec, L, x)
        pred, _ = self.predict(spec, m)
        o = self.obs
        rs = []
        for key in ("07", "08"):
            # sig is the complex rms noise of z; each component has sig / sqrt(2)
            d = (o["dz" + key] - pred[key]) * (math.sqrt(2) / o["sig"])
            rs += [d.real, d.imag]
        q = L.get(x, "q")
        rs.append(self.reg * (np.roll(q, -1) - q))
        rs.append(np.array([10 * q.mean()]))
        return np.concatenate(rs)

    def n_data(self):
        return 4 * self.P

    def _result(self, spec, L, x, fun, jac=None, success=True):
        nd = self.n_data()
        n_par = len(L.x0) - 1  # one redundant degree of freedom in q
        return {"spec": spec, "layout": L, "x": x, "m": self.unpack(spec, L, x), "chi2": float(np.sum(fun[:nd] ** 2)),
                "n_data": nd, "n_par": n_par, "dof": nd - n_par, "success": bool(success), "jac": jac}

    def fit(self, spec, init, max_nfev=200):
        # max_nfev counts iterations here: finite-difference Jacobian calls are not included by SciPy
        L = Layout(spec, init)
        res = least_squares(lambda x: self.residuals(spec, L, x), L.x0, bounds=(L.lo, L.hi),
                            method="trf", x_scale="jac", max_nfev=max_nfev, ftol=1e-7, xtol=1e-7)
        r = self._result(spec, L, res.x, res.fun, res.jac, res.success)
        if spec.kernel == "hard" and (spec.fixed_blur or r["m"]["blur"] < 0.6):
            r = self.polish_hard(r)
        return r

    def fit_pure_hard(self, spec, init, steps=(3.0, 1.5, 0.7, 0.3, 0.1)):
        """Pure hard boundaries by continuation in a fixed blur, then a boundary search."""
        cur = dict(init)
        r = None
        for s in steps:
            r = self.fit(spec.replace(blur=float(s)), cur)
            cur = {"nodes": r["m"]["nodes"], "gain": float(np.median(r["m"]["gain"])), "k": r["m"]["k"],
                   "gain_sector": r["m"]["gain"]}
        r["spec"].name = f"hard+blur=pure({steps[-1]:g}deg)"
        return r

    def polish_hard(self, r, passes=3):
        """Coordinate search of each boundary over midpoints between sample hues, then a
        least-squares pass for the continuous parameters (the objective is piecewise
        constant in a hard boundary between samples)."""
        spec, L = r["spec"], r["layout"]
        x = r["x"].copy()
        hs = np.unique(np.concatenate([self.obs["h"] - 360, self.obs["h"], self.obs["h"] + 360]))

        def cost(xx):
            return float(np.sum(self.residuals(spec, L, xx) ** 2))

        best = cost(x)
        for _ in range(passes):
            improved = False
            nodes = self.unpack(spec, L, x)["nodes"].copy()
            for s in range(N):
                lo = nodes[s - 1] if s > 0 else nodes[-1] - 360
                hi = nodes[s + 1] if s < N - 1 else nodes[0] + 360
                cand = hs[(hs > lo) & (hs < hi)]
                pts = np.concatenate([[lo], cand, [hi]])
                mids = (pts[:-1] + pts[1:]) / 2
                for t in mids:
                    if t - lo < 0.05 or hi - t < 0.05:
                        continue
                    trial = nodes.copy()
                    trial[s] = t
                    if s == 0:
                        trial = trial  # n0 moves; others unchanged
                    xx = L.set_nodes(x, trial)
                    c = cost(xx)
                    if c < best - 1e-9:
                        best, x, nodes, improved = c, xx, trial, True
            if not improved:
                break
            # continuous parameters at the new boundaries
            res = least_squares(lambda xx: self.residuals(spec, L, xx), x, bounds=(L.lo, L.hi), method="trf",
                                x_scale="jac", max_nfev=100)
            if np.sum(res.fun ** 2) < best:
                x, best = res.x, float(np.sum(res.fun ** 2))
        out = self._result(spec, L, x, self.residuals(spec, L, x), r.get("jac"), r["success"])
        out["polished"] = True
        return out

    # ---- initialisation
    def init_from_data(self, kernel, k=0.97, min_w=0.12, min_nsig=3.0):
        o = self.obs
        vec = probe_vectors(self.Z, k)
        centres = np.full(N, np.nan)
        peak_w = []
        for key, secs in PROBE_SECTORS.items():
            dz = o["dz" + key]
            U = np.array([vec[key][s] - 1 for s in secs])
            w = (dz[:, None] * U.conj()[None, :]).real / np.abs(U)[None, :] ** 2
            res = np.abs(dz[:, None] - w * U[None, :])
            best = np.argmin(res, axis=1)
            wb = w[np.arange(len(dz)), best]
            ok = (wb > min_w) & (np.abs(dz) / o["sig"] > min_nsig)
            for j, s in enumerate(secs):
                sel = ok & (best == j)
                if sel.sum() >= 1:
                    centres[s] = circ_mean_deg(o["h"][sel], wb[sel] ** 4)
                    peak_w.append(float(np.max(wb[sel])))
        gain = float(np.clip(np.median(peak_w) if peak_w else 0.7, 0.2, 1.5))
        return {"nodes": fill_nodes(centres, kernel), "gain": gain, "k": k, "blur": 1.0, "kappa": 30.0}

    def multi_start(self, spec, inits):
        best = None
        for ini in inits:
            r = self.fit(spec, ini)
            if best is None or r["chi2"] < best["chi2"]:
                best = r
        return best


def fill_nodes(centres, kernel):
    """Monotone 24 nodes from sector centres (NaN where unknown)."""
    c = np.array(centres, float)
    known = np.where(np.isfinite(c))[0]
    if len(known) < 2:
        base = c[known[0]] - 15 * known[0] if len(known) else 0.0
        c = base + 15 * np.arange(N)
    else:
        # unwrap the known centres in sector order
        un = {known[0]: c[known[0]]}
        prev_s, prev = known[0], c[known[0]]
        for s in known[1:]:
            v = prev + ((c[s] - prev) % 360)
            # expected roughly 15 deg per sector; a large jump means a wrap ambiguity
            if v - prev > 15 * (s - prev_s) + 120:
                v -= 360
            if v <= prev:
                v = prev + 2.0 * (s - prev_s)
            un[s], prev_s, prev = v, s, v
        ks = np.array(sorted(un))
        vs = np.array([un[s] for s in ks])
        # cyclic interpolation in sector index with one turn = 360 deg
        ks_ext = np.concatenate([ks - N, ks, ks + N])
        vs_ext = np.concatenate([vs - 360, vs, vs + 360])
        c = np.interp(np.arange(N), ks_ext, vs_ext)
        if vs[-1] - vs[0] >= 360 - 2:
            c = vs[0] + np.linspace(0, 345, N)
    c = np.maximum.accumulate(c + np.arange(N) * 1e-3)
    if c[-1] - c[0] > 359:
        c = c[0] + (c - c[0]) * 345 / (c[-1] - c[0])
    if kernel == "hard":
        prev = np.concatenate([[c[-1] - 360], c[:-1]])
        return (prev + c) / 2
    return c


def jac_node_cov(fitter, r):
    """Node / gain / blur covariance from the Jacobian, scaled by chi2/dof."""
    L, x, spec = r["layout"], r["x"], r["spec"]
    J = r.get("jac")
    if J is None:
        return None
    nd = r["n_data"]
    Jd = np.asarray(J)
    try:
        cov = np.linalg.pinv(Jd.T @ Jd) * max(r["chi2"] / max(r["dof"], 1), 1e-9)
    except np.linalg.LinAlgError:
        return None
    # node derivatives
    eps = 1e-5
    base = fitter.unpack(spec, L, x)["nodes"]
    D = np.zeros((N, len(x)))
    for j in list(range(L.slices["n0"].start, L.slices["q"].stop)):
        xx = x.copy()
        xx[j] += eps
        D[:, j] = (fitter.unpack(spec, L, xx)["nodes"] - base) / eps
    cn = D @ cov @ D.T
    out = {"node_sd": np.sqrt(np.maximum(np.diag(cn), 0)).tolist()}
    sl = L.slices["lg"]
    gl = np.exp(x[sl])
    out["gain_sd"] = (gl * np.sqrt(np.maximum(np.diag(cov)[sl], 0))).tolist()
    if "ls0" in L.slices:
        j = L.slices["ls0"].start
        out["blur_sd"] = float(math.exp(x[j]) * math.sqrt(max(cov[j, j], 0)))
    if "k" in L.slices:
        j = L.slices["k"].start
        out["k_sd"] = float(math.sqrt(max(cov[j, j], 0)))
    return out


def bootstrap(fitter, r, B=100, seed=20261019, strata=None):
    """Patch bootstrap (stratified by ring). Refits from the best solution."""
    rng = np.random.default_rng(seed)
    o = fitter.obs
    spec = r["spec"]
    P = len(o["h"])
    strata = o["ring"] if strata is None else strata
    groups = [np.where(strata == g)[0] for g in np.unique(strata)]
    init = {"nodes": r["m"]["nodes"], "gain": float(np.nanmedian(r["m"]["gain"])), "k": r["m"]["k"], "gain_sector": r["m"]["gain"],
            "blur": max(r["m"]["blur"], 0.03), "kappa": max(r["m"]["kappa"], 0.6)}
    nodes, gains, blurs, kappas, ks, rgr, rsh, gsec = [], [], [], [], [], [], [], []
    for _ in range(B):
        idx = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups])
        sub = {k: (v[idx] if isinstance(v, np.ndarray) and len(v) == P else v) for k, v in o.items()}
        f2 = Fitter(sub, fitter.Z, fitter.reg)
        rr = f2.fit(spec, init, max_nfev=60)
        n = rr["m"]["nodes"]
        n = n + 360 * np.round((r["m"]["nodes"][0] - n[0]) / 360)
        nodes.append(n)
        gains.append(float(np.nanmedian(rr["m"]["gain"])))
        gsec.append(rr["m"]["gain"])
        blurs.append(rr["m"]["blur"])
        kappas.append(rr["m"]["kappa"])
        ks.append(rr["m"]["k"])
        rgr.append(rr["m"]["ring_gain_ratio"])
        rsh.append(rr["m"]["ring2_shift"])
    nodes = np.array(nodes)

    def ci(a):
        a = np.asarray(a, float)
        return [float(np.percentile(a, 5)), float(np.percentile(a, 95))]

    return {"B": B, "node_ci90": [ci(nodes[:, s]) for s in range(N)], "node_sd": nodes.std(axis=0).tolist(),
            "gain_ci90": ci(gains), "gain_sd": float(np.std(gains)),
            "gain_sector_ci90": [ci(np.array(gsec)[:, s]) for s in range(N)],
            "blur_ci90": ci(blurs), "kappa_ci90": ci(kappas), "k_ci90": ci(ks),
            "ring_gain_ratio_ci90": ci(rgr), "ring2_shift_ci90": ci(rsh)}


def bracket_intervals(h_samples, nodes):
    """For each node, the nearest sample hues on either side (unwrapped)."""
    hs = np.sort(np.concatenate([h_samples - 360, h_samples, h_samples + 360]))
    out = []
    for n in nodes:
        lo = hs[hs <= n]
        hi = hs[hs > n]
        out.append([float(lo[-1]) if len(lo) else None, float(hi[0]) if len(hi) else None])
    return out


def summarize_fit(fitter, r):
    spec, m = r["spec"], r["m"]
    lnN = math.log(max(r["n_data"], 2))
    return {"name": spec.name, "spec": spec.as_dict(), "chi2": r["chi2"], "n_data": r["n_data"], "n_par": r["n_par"],
            "dof": r["dof"], "chi2_per_dof": r["chi2"] / max(r["dof"], 1), "bic": r["chi2"] + r["n_par"] * lnN,
            "nodes_deg": (m["nodes"] % 360).tolist(), "nodes_unwrapped": m["nodes"].tolist(),
            "gain": float(np.nanmedian(m["gain"])),
            "gain_per_sector": m["gain"].tolist() if spec.gain == "sector" else None,
            "blur_deg": 0.0 if spec.blur == "zero" else float(m["blur"]),
            "blur_kappa": float(m["kappa"]) if spec.blur == "chroma" else 0.0,
            "blur_mode": "chroma" if spec.blur == "chroma" else "const",
            "k": m["k"], "eps": {k: [v.real, v.imag] for k, v in m["eps"].items()},
            "ring_gain_ratio": m["ring_gain_ratio"] if spec.ring_gain else None,
            "ring2_shift_deg": m["ring2_shift"] if spec.ring_shift else None}


def select_models(fits):
    """Scaled BIC: chi2 differences divided by the reduced chi2 of the most flexible fit."""
    ref = min(fits, key=lambda f: f["chi2_per_dof"] if f["dof"] > 0 else 1e9)
    s2 = max(ref["chi2_per_dof"], 1e-9)
    lnN = math.log(max(ref["n_data"], 2))
    for f in fits:
        f["bic_scaled"] = f["chi2"] / s2 + f["n_par"] * lnN
    best = min(fits, key=lambda f: f["bic_scaled"])
    for f in fits:
        f["delta_bic_scaled"] = f["bic_scaled"] - best["bic_scaled"]
    return best, s2
