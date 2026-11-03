#!/usr/bin/env python3
"""Read-only source inputs; all outputs stay in this folder or /tmp/bw03_r2.

Run each phase with python3 -I -B. Photo and firmware derived arrays are local.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import csv
import io
import tarfile
import time
import plistlib
import subprocess
import numpy as np
from scipy import optimize, sparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
TMP = Path("/tmp/bw03_r2")
STOCK = np.array([306, 601, 117])
DOMAIN = (-128, 1280)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dump(path, obj):
    target=Path(path).resolve()
    assert target.is_relative_to(HERE) or target.is_relative_to(TMP.resolve()),target
    def default(v):
        if isinstance(v, np.ndarray): return v.tolist()
        if isinstance(v, np.generic): return v.item()
        raise TypeError(type(v).__name__)
    Path(path).write_text(json.dumps(obj, indent=2, default=default, allow_nan=False) + "\n")


def guard():
    info=plistlib.loads(subprocess.check_output(["diskutil","info","-plist","/Volumes/Workspace"]))
    assert info["MountPoint"]=="/Volumes/Workspace" and info["FilesystemType"]=="apfs"
    assert info["VolumeUUID"].upper()=="14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert info["Writable"] and info["WritableMedia"] and info["WritableVolume"]
    assert not LOCAL.is_symlink() and not TMP.is_symlink()
    assert "local/" in (HERE/".gitignore").read_text().splitlines()
    assert subprocess.run(["git","check-ignore","-q",str(LOCAL/"guard")],cwd=ROOT).returncode==0


def read(path):
    return json.loads(Path(path).read_text())


def data():
    with np.load(TMP / "blocks.npz", allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def stats(e):
    a = np.abs(e)
    if not len(a): return {"n": 0}
    return {"n": len(a), "median_abs": float(np.median(a)),
            "p90_abs": float(np.percentile(a, 90)), "max_abs": float(a.max()),
            "rms": float(np.sqrt(np.mean(e * e))), "mean": float(np.mean(e))}


def selected_weights(D, s):
    cnt=np.bincount(D["bin"][s],minlength=len(D["keys"]))
    return 1.0/cnt[D["bin"][s]]


def metrics(D, pred, select=None, rebalance=False):
    s = np.ones(len(D["j"]), bool) if select is None else select
    e = pred[s] - D["j"][s]
    w = selected_weights(D,s) if rebalance else D["wt"][s]
    return {"bin_weighted_rms": float(np.sqrt(np.sum(w * e * e) / w.sum())),
            "all": stats(e), "chromatic": stats(e[D["chrom"][s]])}


def gate(m, ref, tol=1e-10):
    return all(m["chromatic"][k] <= ref["chromatic"][k] + tol
               for k in ("median_abs", "p90_abs"))


def bin_ids(lab):
    L, a, b = lab.T
    C = np.hypot(a, b)
    h = np.degrees(np.arctan2(b, a)) % 360
    cb = np.digitize(C, [5, 10, 20, 40])
    hb = np.where(C < 5, 0, (h // 15).astype(int) + 1)
    lb = np.clip((L // 10).astype(int), 0, 10)
    key = lb * 1000 + cb * 100 + hb
    keys, ids, cnt = np.unique(key, return_inverse=True, return_counts=True)
    return keys, ids, cnt


def prepare():
    LOCAL.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    bw = module("r2_bw", ROOT / "research/color_table_fit/bw_mix.py")
    gr = ROOT / "research/gr4_modes/local"
    candidate, hc, tone = (read(gr / s) for s in ("candidates.json", "hcbw.json", "tone_curves.json"))
    row = candidate["modes"]["hc_bw"]["row_jpeg_domain"]
    K = bw.mm.Curve.from_rows(row["input31_u16"], row["output33_u8"])
    dd = [bw.gr4_blocks(k, candidate["gr4_standard_118_u_c"][a],
                        np.asarray(hc["gxr_mix"]["gxr_to_c_from_linsrgb"]),
                        np.asarray(tone["radial"]["gr4_coef_natural_log"]))
          for k, a in bw.FRAMES.items()]
    D = {k: np.concatenate([d[k] for d in dd]) for k in ("x", "j", "lab")}
    D["frame"] = np.concatenate([np.full(len(d["j"]), i, np.int8) for i, d in enumerate(dd)])
    D["F"] = K(D["x"])
    D["wt"], nbin, C = bw.bin_weights(D["lab"])
    D["chrom"] = C >= 15
    D["keys"], D["bin"], D["cnt"] = bin_ids(D["lab"])
    D["nodes"], D["curve"] = K.xs, K.ys
    assert (len(D["j"]), nbin, int(D["chrom"].sum())) == (601340, 308, 190116)
    np.savez(TMP / "blocks.npz", **D)
    old = read(ROOT / "research/color_table_fit/local/bw_mix.json")
    refs = {}
    for name, w in (("stock", STOCK), ("prior_fit", [541, 288, 195]),
                    ("equal", [341, 341, 342]), ("prior_sim", [405, 306, 313])):
        refs[name] = {"Y_q10": list(map(int, w)), **metrics(D, D["F"] @ (np.asarray(w) / 1024))}
    for k, oldk in (("stock", "stock_Y_row"), ("prior_fit", "fitted_541_288_195")):
        o = old["gr4_blocks"]["errors_codes"][oldk]
        assert abs(refs[k]["bin_weighted_rms"] - o["bin_weighted_rms"]) < 1e-8
        for q in ("median_abs", "p90_abs", "max_abs"):
            assert abs(refs[k]["chromatic"][q] - o["chromatic_C>=15"][q]) < 1e-8
    paths = [ROOT / "research/color_table_fit" / n for n in
             ("bw_mix.py", "matrix_model.py", "fit_sectors.py", "local/bw_mix.json")]
    paths += [gr / n for n in ("candidates.json", "hcbw.json", "tone_curves.json", "hdf_hc.npz", "hc_bw.npz")]
    paths += [ROOT / p for p in ("research/gr4_modes/core.py", "research/gr4_modes/gr4io.py",
                                "research/color_references/colour_math.py", "artifacts/firmware/gxr-1.51/jlaunch3")]
    snapshot = {str(p.relative_to(ROOT)): {"sha256": sha(p), "size": p.stat().st_size,
                                          "mtime_ns": p.stat().st_mtime_ns} for p in paths}
    dump(LOCAL / "input_snapshot.json", snapshot)
    dump(LOCAL / "baseline.json", {"n": len(D["j"]), "bins": nbin,
         "chromatic_n": int(D["chrom"].sum()), "frames": list(bw.FRAMES),
         "frame_counts": {k: int(len(d["j"])) for k, d in zip(bw.FRAMES, dd)},
         "reproduces_old_to_1e-8": True, "references": refs})
    print(json.dumps({"n": len(D["j"]), "bins": nbin, "chromatic": int(D["chrom"].sum()),
                      "stock": refs["stock"], "frames": [len(d["j"]) for d in dd]}))


class MixProblem:
    def __init__(self, D, select=None):
        s = np.ones(len(D["j"]), bool) if select is None else select
        F, j, wt = D["F"][s], D["j"][s], selected_weights(D,s)
        self.A = F[:, :2] - F[:, 2:3]
        self.b = F[:, 2] - j
        self.H = self.A.T @ (wt[:, None] * self.A) / wt.sum()
        self.g = self.A.T @ (wt * self.b) / wt.sum()
        self.c = float(np.dot(wt, self.b * self.b) / wt.sum())
        self.Ac, self.bc = self.A[D["chrom"][s]], self.b[D["chrom"][s]]
        self.ref = np.percentile(np.abs(self.Ac @ (STOCK[:2] / 1024) + self.bc), [50, 90])
        self.last = None

    def objective(self, u):
        return float(u @ self.H @ u + 2 * self.g @ u + self.c) / 100

    def gradient(self, u):
        return 2 * (self.H @ u + self.g) / 100

    def quantiles(self, u):
        if self.last is not None and np.array_equal(self.last, u):
            return self.val, self.jac
        e = self.Ac[:, 0] * u[0] + self.Ac[:, 1] * u[1] + self.bc
        a = np.abs(e)
        pos = (len(a) - 1) * np.array([.5, .9])
        lo, hi = np.floor(pos).astype(int), np.ceil(pos).astype(int)
        ix = np.argpartition(a, np.r_[lo, hi])
        il, ih = ix[lo], ix[hi]
        t = pos - lo
        self.val = a[il] * (1 - t) + a[ih] * t
        self.jac = (np.sign(e[il])[:, None] * self.Ac[il] * (1 - t[:, None]) +
                    np.sign(e[ih])[:, None] * self.Ac[ih] * t[:, None])
        self.last = np.asarray(u).copy()
        return self.val, self.jac

    def solve(self, start=None, caps=None, maxiter=100):
        if start is None: start = STOCK[:2] / 1024
        cap = self.ref if caps is None else np.asarray(caps)
        cons = [{"type": "ineq", "fun": lambda u: (cap - self.quantiles(u)[0]) / 10,
                 "jac": lambda u: -self.quantiles(u)[1] / 10},
                {"type": "ineq", "fun": lambda u: np.array([1.125 - u.sum(), u.sum() + .25]),
                 "jac": lambda u: np.array([[-1., -1.], [1., 1.]])}]
        return optimize.minimize(self.objective, start, jac=self.gradient,
                method="SLSQP", bounds=[(-.125, 1.25)] * 2, constraints=cons,
                options={"ftol": 1e-11, "maxiter": maxiter})


def mixfit(start, stop):
    D = data()
    P = MixProblem(D)
    uls = -np.linalg.solve(P.H, P.g)
    seeds = [STOCK[:2] / 1024, uls, [0.35, .55], [.4, .5], [.5, .3], [.25, .65],
             [.6, .3], [.3, .6], [.4, .4], [.65, .5]]
    path = LOCAL / "mix_continuous.json"
    out = read(path) if path.exists() else []
    for i in range(start, min(stop, len(seeds))):
        t = time.monotonic()
        sol = P.solve(np.asarray(seeds[i]), maxiter=80)
        u = np.r_[sol.x, 1 - sol.x.sum()]
        m = metrics(D, D["F"] @ u)
        rec = {"start": i, "success": bool(sol.success), "message": str(sol.message),
               "iterations": sol.nit, "Y_continuous_q10": (u * 1024).tolist(),
               "gate": bool(np.all(P.quantiles(sol.x)[0] <= P.ref + 1e-8)), **m}
        out = [r for r in out if r["start"] != i] + [rec]
        dump(path, out)
        print(json.dumps({"start": i, "q10": rec["Y_continuous_q10"],
                          "rms": m["bin_weighted_rms"], "gate": rec["gate"],
                          "median": m["chromatic"]["median_abs"], "p90": m["chromatic"]["p90_abs"],
                          "success": bool(sol.success), "seconds": round(time.monotonic()-t, 2)}), flush=True)


def integer_near(start, stop):
    D = data()
    P = MixProblem(D)
    cc = read(LOCAL / "mix_continuous.json")
    centers = [r["Y_continuous_q10"][:2] for r in cc if r["gate"]]
    centers += [STOCK[:2].tolist()]
    pairs = set()
    for u in centers:
        r, g = np.rint(u).astype(int)
        pairs.update((int(r+a), int(g+b)) for a in range(-10, 11) for b in range(-10, 11))
    pairs = sorted(pairs)
    ref = read(LOCAL / "baseline.json")["references"]["stock"]
    path = LOCAL / "mix_integer_near.json"
    out = read(path) if path.exists() else []
    for r, g in pairs[start:stop]:
        q = np.array([r, g, 1024-r-g])
        if q.min() < DOMAIN[0] or q.max() > DOMAIN[1]: continue
        u = q[:2] / 1024
        vals, _ = P.quantiles(u)
        rec = {"Y_q10": q.tolist(), "rms": float(np.sqrt(max(0, P.objective(u)*100))),
               "median_abs": float(vals[0]), "p90_abs": float(vals[1]),
               "gate": bool(np.all(vals <= P.ref + 1e-10))}
        out.append(rec)
    unique = {tuple(r["Y_q10"]): r for r in out}
    out = list(unique.values())
    dump(path, out)
    good = [r for r in out if r["gate"]]
    best = min(good, key=lambda r: r["rms"]) if good else None
    print(json.dumps({"processed": len(out), "total_pairs": len(pairs), "best": best}))


def lattice_prepare():
    D=data();P=MixProblem(D)
    best=min((v for v in read(LOCAL/"mix_integer_near.json") if v["gate"]),key=lambda v:v["rms"])
    grid=np.mgrid[-128:1281,-128:1281].reshape(2,-1).T
    b=1024-grid.sum(axis=1);grid=grid[(b>=-128)&(b<=1280)]
    u=grid/1024
    loss=np.einsum("ni,ij,nj->n",u,P.H,u)+2*u@P.g+P.c
    below=loss<best["rms"]**2-1e-8
    near=loss[(loss<best["rms"]**2+1e-8)&~below]
    # No untested point may hide in the numerical exclusion margin below the incumbent.
    assert np.all(near>=best["rms"]**2-1e-10)
    np.savez(TMP/"lower_lattice.npz",q=grid[below],mse=loss[below])
    dump(LOCAL/"global_integer_proof.json",{"incumbent":best,"domain_points":len(grid),
         "lower_points":int(below.sum()),"closest_strictly_lower_mse_gap":float(best["rms"]**2-loss[below].max()),
         "margin_checked":True,"lower_points_min_coefficients":np.min(np.c_[grid[below],1024-grid[below].sum(axis=1)],axis=0),
         "lower_points_max_coefficients":np.max(np.c_[grid[below],1024-grid[below].sum(axis=1)],axis=0)})
    print(json.dumps({"lower_points":int(below.sum()),"margin_checked":True}))


def lattice(start, stop):
    D = data()
    P = MixProblem(D)
    z = np.load(TMP / "lower_lattice.npz", allow_pickle=False)
    order = np.argsort(z["mse"], kind="stable")
    pairs = z["q"][order]
    path = LOCAL / f"lattice_{start:06d}_{min(stop,len(pairs)):06d}.json"
    out = []
    for r, g in pairs[start:stop]:
        q = np.array([r, g, 1024-r-g], int)
        vals, _ = P.quantiles(q[:2] / 1024)
        out.append({"Y_q10": q.tolist(), "rms": float(np.sqrt(max(0, P.objective(q[:2]/1024)*100))),
                    "median_abs": float(vals[0]), "p90_abs": float(vals[1]),
                    "gate": bool(np.all(vals <= P.ref + 1e-10))})
    dump(path, out)
    good = [r for r in out if r["gate"]]
    print(json.dumps({"range": [start, min(stop,len(pairs))], "gate_n": len(good),
                      "best": min(good,key=lambda r:r["rms"]) if good else None}))


def pareto_grid(start, stop):
    D = data()
    P = MixProblem(D)
    pairs = [(r,g) for r in range(-128,1281,16) for g in range(-128,1281,16)
             if -128 <= 1024-r-g <= 1280]
    out = []
    for r,g in pairs[start:stop]:
        u = np.array([r,g])/1024
        vals,_ = P.quantiles(u)
        out.append({"Y_q10": [r,g,1024-r-g], "rms": float(np.sqrt(max(0,P.objective(u)*100))),
                    "median_abs": float(vals[0]), "p90_abs": float(vals[1]),
                    "gate": bool(np.all(vals<=P.ref+1e-10))})
    dump(LOCAL / f"pareto_grid_{start:06d}_{min(stop,len(pairs)):06d}.json",out)
    print(json.dumps({"range": [start,min(stop,len(pairs))], "grid_n":len(pairs)}))


def interpolation(x, nodes):
    k = np.clip(np.searchsorted(nodes, x, side="right") - 1, 0, len(nodes)-2)
    t = (np.clip(x, nodes[0], nodes[-1]) - nodes[k]) / (nodes[k+1] - nodes[k])
    rows = np.repeat(np.arange(len(x)), 2)
    return sparse.csr_matrix((np.stack([1-t,t],axis=1).ravel(),
             (rows, np.stack([k,k+1],axis=1).ravel())),shape=(len(x),len(nodes)))


def t1_prepare():
    D = data()
    W = [interpolation(D["x"][:,c],D["nodes"]) for c in range(3)]
    for c in range(3):
        assert np.max(np.abs(W[c] @ D["curve"] - D["F"][:,c])) < 1e-10
        sparse.save_npz(TMP/f"W{c}.npz",W[c])
    free = np.flatnonzero((D["curve"]>0)&(D["curve"]<255))
    Z = sparse.hstack([W[0][:,free]-W[2][:,free],W[1][:,free]-W[2][:,free]],format="csr")
    sparse.save_npz(TMP/"Z.npz",Z)
    H = (Z.T @ Z.multiply(D["wt"][:,None])).toarray()/D["wt"].sum()
    # Per-bin moments make a genuine refit after removal inexpensive.
    order = np.argsort(D["bin"],kind="stable")
    offsets = np.r_[0,np.cumsum(D["cnt"])]
    np.savez(TMP/"t1_moments.npz",H=H,free=free,order=order,offsets=offsets)
    print(json.dumps({"variables": len(free)*2, "interpolation_max_difference": 1e-10,
                      "gram_rank":int(np.linalg.matrix_rank(H)), "gram_min_eigenvalue":float(np.linalg.eigvalsh(H)[0])}))


class T1Problem:
    def __init__(self,D,select=None):
        self.D=D
        self.s = np.ones(len(D["j"]),bool) if select is None else select
        self.wt=selected_weights(D,self.s)
        W=[sparse.load_npz(TMP/f"W{c}.npz")[self.s] for c in range(3)]
        Z=sparse.hstack([W[0]-W[2],W[1]-W[2]],format="csr")
        self.H0=(Z.T@Z.multiply(self.wt[:,None])).toarray()/self.wt.sum()
        b=D["F"][self.s,2]-D["j"][self.s]
        self.g0=np.asarray(Z.T@(self.wt*b)).ravel()/self.wt.sum()
        self.c=float(np.dot(self.wt,b*b)/self.wt.sum())
        dk=np.diff(D["curve"]);active=np.flatnonzero(dk>0)
        self.dk=dk[active]
        self.T=(np.arange(33)[:,None]>active[None,:])*self.dk[None,:]
        self.nf=len(active)
        self.J=sparse.block_diag([self.T,self.T]).toarray()
        self.H=self.J.T@self.H0@self.J
        self.g=self.J.T@self.g0
        self.triangle=np.hstack([np.eye(self.nf),np.eye(self.nf)])
        self.end=np.block([[self.dk[None,:]/255,np.zeros((1,self.nf))],
                           [np.zeros((1,self.nf)),self.dk[None,:]/255]])

    def solve(self,q=None,ridge=0.0):
        w=np.array([.5,.25,.25]) if q is None else np.asarray(q)/1024
        assert np.min(w)>0 and abs(w.sum()-1)<1e-12
        H=self.H;g=self.g;c=self.c
        constraints=[optimize.LinearConstraint(self.triangle,-np.inf,1)]
        if q is not None: constraints.append(optimize.LinearConstraint(self.end,w[:2],w[:2]))
        sol=optimize.minimize(lambda v:(v@H@v+2*g@v+c)/100,
             np.r_[np.full(self.nf,w[0]),np.full(self.nf,w[1])],
             jac=lambda v:2*(H@v+g)/100,method="SLSQP",bounds=[(0.,1.)]*(2*self.nf),
             constraints=constraints,options={"maxiter":1000,"ftol":1e-12})
        # A linear minimization gives a Frank-Wolfe gap, hence a convex lower bound.
        grad=2*(H@sol.x+g)
        lp=optimize.linprog(grad,A_ub=self.triangle,b_ub=np.ones(self.nf),
              A_eq=self.end if q is not None else None,b_eq=w[:2] if q is not None else None,
              bounds=(0.,1.),method="highs")
        assert lp.success
        gap=max(0.,float(grad@(sol.x-lp.x)))
        sol.convex_gap_mse=gap
        sol.convex_lower_bound_rms=float(np.sqrt(max(0,(sol.x@H@sol.x+2*g@sol.x+c)-gap)))
        P=np.zeros((33,3));P[:,0]=self.T@sol.x[:self.nf];P[:,1]=self.T@sol.x[self.nf:]
        P[:,2]=self.D["curve"]-P[:,0]-P[:,1]
        if q is None: w=P[-1]/255
        sol.weights=w
        curves=P/w[None,:]
        assert np.min(np.diff(curves,axis=0))>-1e-6
        assert np.min(curves)>-1e-6 and np.max(curves)<255+1e-6
        assert np.max(np.abs(curves@w-self.D["curve"]))<1e-9
        return curves,sol


def curves_predict(D,curves,q):
    return sum(np.interp(D["x"][:,c],D["nodes"],curves[:,c])*(q[c]/1024) for c in range(3))


def exact_integer_curves(curves,q,K,radius=5):
    # Integer dynamic program: enforce the original grey curve exactly at every node.
    q=np.asarray(q,int)
    levels=[]
    for target,row in zip(K,curves):
        choices=[]
        center=np.rint(row).astype(int)
        for r in range(max(0,center[0]-radius),min(255,center[0]+radius)+1):
            for g in range(max(0,center[1]-radius),min(255,center[1]+radius)+1):
                rem=int(1024*target)-int(q[0]*r+q[1]*g)
                if rem%q[2]: continue
                b=rem//q[2]
                if not 0<=b<=255 or abs(b-row[2])>2*radius+1: continue
                choices.append((r,g,b))
        # The unchanged curve is always an exactly feasible fallback.
        choices.append((int(target),)*3)
        levels.append(np.unique(choices,axis=0))
    costs=np.sum((levels[0]-curves[0])**2,axis=1)
    back=[]
    for n in range(1,33):
        prev,curr=levels[n-1],levels[n]
        valid=np.all(prev[:,None,:]<=curr[None,:,:],axis=2)
        trans=np.where(valid,costs[:,None],np.inf)
        ix=np.argmin(trans,axis=0)
        costs=trans[ix,np.arange(len(curr))]+np.sum((curr-curves[n])**2,axis=1)
        back.append(ix)
    k=int(np.argmin(costs))
    if not np.isfinite(costs[k]): raise RuntimeError("no integer monotone path")
    out=[levels[-1][k]]
    for n in range(31,-1,-1):
        k=int(back[n][k]);out.append(levels[n][k])
    out=np.asarray(out[::-1],int)
    assert np.all(np.diff(out,axis=0)>=0) and np.array_equal(out@q,K.astype(int)*1024)
    return out


T1_MIXES = [list(map(int,s.split("/"))) for s in (
    "306/601/117 495/416/113 512/256/256 384/256/384 "
    "512/128/384 384/384/256 256/512/256 512/64/448 "
    "448/320/256 448/256/320 576/256/192 512/192/320").split()]
T1_MIXES += [list(q) for r in range(64,960,64) for g in range(64,1024-r,64)
            if (q:=(r,g,1024-r-g)) not in [tuple(v) for v in T1_MIXES]]


def t1fit(start,stop):
    D=data();P=T1Problem(D)
    path=LOCAL/"t1_fits.json"
    out=read(path) if path.exists() else []
    stock=read(LOCAL/"baseline.json")["references"]["stock"]
    for i in range(start,min(stop,len(T1_MIXES))):
        q=np.asarray(T1_MIXES[i]);t=time.monotonic()
        curves,sol=P.solve(q)
        m=metrics(D,curves_predict(D,curves,q))
        quant=exact_integer_curves(curves,q,D["curve"],radius=22)
        mi=metrics(D,curves_predict(D,quant,q))
        rec={"index":i,"Y_q10":q.tolist(),"success":bool(sol.success),"message":str(sol.message),
             "iterations":sol.nit,"convex_gap_mse":sol.convex_gap_mse,
             "convex_lower_bound_rms":sol.convex_lower_bound_rms,
             "curves_float":curves.tolist(),"curves_u8":quant.tolist(),
             "float":m,"integer":mi,"float_gate":gate(m,stock),"integer_gate":gate(mi,stock),
             "neutral_axis_max_error_float":float(np.max(np.abs(curves@(q/1024)-D["curve"]))),
             "neutral_axis_error_integer_numerator":int(np.max(np.abs(quant@q-D["curve"].astype(int)*1024)))}
        out=[r for r in out if r["index"]!=i]+[rec];dump(path,out)
    good=[r for r in out if r["integer_gate"]]
    best=min(good,key=lambda r:r["integer"]["bin_weighted_rms"])
    print(json.dumps({"range":[start,min(stop,len(T1_MIXES))],"total":len(T1_MIXES),
          "processed":len(out),"best_q":best["Y_q10"],
          "best_rms":best["integer"]["bin_weighted_rms"],"best_color":best["integer"]["chromatic"]}))


def refit_mix(D,select):
    P=MixProblem(D,select)
    ls=-np.linalg.solve(P.H,P.g)
    seeds=[STOCK[:2]/1024,ls,np.array([.35,.55]),np.array([.5,.3])]
    pairs={tuple(STOCK[:2])}
    sols=[]
    for seed in seeds:
        sol=P.solve(seed,maxiter=80)
        sols.append({"success":bool(sol.success),"iterations":sol.nit})
        center=np.rint(sol.x*1024).astype(int)
        pairs.update((int(center[0]+r),int(center[1]+g)) for r in range(-3,4) for g in range(-3,4))
    candidates=[]
    for r,g in pairs:
        q=np.array([r,g,1024-r-g])
        if q.min() < -128 or q.max()>1280: continue
        vals,_=P.quantiles(q[:2]/1024)
        if np.all(vals<=P.ref+1e-10): candidates.append((P.objective(q[:2]/1024),q))
    _,best=min(candidates,key=lambda v:v[0])
    return best,{"method":"four fixed starts SLSQP plus radius-3 integer refinement; not globally certified per fold",
                 "solves":sols,"integer_candidates_n":len(pairs)}


def loo_frames(start,stop):
    D=data();names=read(LOCAL/"baseline.json")["frames"]
    out=[]
    for f in range(start,min(stop,2)):
        test=D["frame"]==f;train=~test
        q,search=refit_mix(D,train)
        pred=D["F"]@(q/1024);stockpred=D["F"]@(STOCK/1024)
        rec={"held_out":names[f],"trained_on":names[1-f],"Y_q10":q.tolist(),"search":search,
             "train":metrics(D,pred,train,True),"test":metrics(D,pred,test,True),
             "stock_train":metrics(D,stockpred,train,True),"stock_test":metrics(D,stockpred,test,True)}
        rec["train_gate"]=gate(rec["train"],rec["stock_train"])
        rec["test_gate"]=gate(rec["test"],rec["stock_test"])
        out.append(rec)
    dump(LOCAL/f"loo_frames_{start}_{stop}.json",out)
    print(json.dumps([{k:r[k] for k in ("held_out","Y_q10","train_gate","test_gate","test","stock_test")} for r in out]))


def loo_bins(start,stop):
    D=data();out=[];stockpred=D["F"]@(STOCK/1024)
    for i in range(start,min(stop,len(D["keys"]))):
        test=D["bin"]==i;train=~test
        q,search=refit_mix(D,train)
        pred=D["F"]@(q/1024)
        rec={"held_out_bin":int(D["keys"][i]),"index":i,"Y_q10":q.tolist(),"search":search,
             "train":metrics(D,pred,train),"test":metrics(D,pred,test),
             "stock_train":metrics(D,stockpred,train),"stock_test":metrics(D,stockpred,test)}
        rec["train_gate"]=gate(rec["train"],rec["stock_train"])
        rec["test_gate"]=gate(rec["test"],rec["stock_test"]) if rec["test"]["chromatic"]["n"] else None
        out.append(rec)
    dump(LOCAL/f"loo_bins_{start:03d}_{min(stop,len(D['keys'])):03d}.json",out)
    print(json.dumps({"range":[start,min(stop,len(D["keys"]))],
          "held_out_rms_better":sum(r["test"]["bin_weighted_rms"]<r["stock_test"]["bin_weighted_rms"] for r in out),
          "train_gate_n":sum(r["train_gate"] for r in out)}))


def t1_free():
    D=data();P=T1Problem(D);curves,sol=P.solve();w=sol.weights
    m=metrics(D,curves_predict(D,curves,w*1024))
    rec={"success":bool(sol.success),"message":str(sol.message),"iterations":sol.nit,
         "Y_continuous_q10":(w*1024).tolist(),"curves_float":curves.tolist(),"metrics":m,
         "convex_gap_mse":sol.convex_gap_mse,"convex_lower_bound_rms":sol.convex_lower_bound_rms,
         "gram_rank":int(np.linalg.matrix_rank(P.H)),"n_variables":2*P.nf,
         "min_monotone_increment":float(np.min(np.diff(curves,axis=0))),
         "neutral_max_error":float(np.max(np.abs(curves@w-D["curve"])))}
    dump(LOCAL/"t1_free_float.json",rec)
    print(json.dumps({k:rec[k] for k in ("success","Y_continuous_q10","metrics","neutral_max_error")}))


def additive_bound():
    D=data();W=[sparse.load_npz(TMP/f"W{c}.npz") for c in range(3)]
    Z=sparse.hstack([W[0]-W[2],W[1]-W[2]],format="csr")
    wt=D["wt"];b=D["F"][:,2]-D["j"]
    H=(Z.T@Z.multiply(wt[:,None])).toarray()/wt.sum()
    g=np.asarray(Z.T@(wt*b)).ravel()/wt.sum()
    eigen,V=np.linalg.eigh(H);keep=eigen>eigen.max()*1e-12
    v=-V[:,keep]@((V[:,keep].T@g)/eigen[keep])
    pred=D["F"][:,2]+Z@v
    rec={"model":"neutral-preserving additive 33-node curves; no monotonicity, range or sign restriction",
         "rank":int(keep.sum()),"variables":66,"metrics":metrics(D,pred),
         "normal_equation_residual_inf":float(np.max(np.abs(H@v+g))),
         "contributions_R":v[:33].tolist(),"contributions_G":v[33:].tolist()}
    dump(LOCAL/"additive_relaxed_bound.json",rec)
    print(json.dumps({k:rec[k] for k in ("model","rank","metrics","normal_equation_residual_inf")}))


def robust_mix():
    D=data();P=MixProblem(D)
    problems=[P,MixProblem(D,D["frame"]==0),MixProblem(D,D["frame"]==1)]
    cons=[{"type":"ineq","fun":lambda u,p=p:(p.ref-p.quantiles(u)[0])/10,
           "jac":lambda u,p=p:-p.quantiles(u)[1]/10} for p in problems]
    cons.append({"type":"ineq","fun":lambda u:np.array([1.125-u.sum(),u.sum()+.25]),
                 "jac":lambda u:np.array([[-1.,-1.],[1.,1.]])})
    rows=[];pairs={tuple(STOCK[:2])}
    for seed in [STOCK[:2]/1024,[.35,.55],[.4,.5],[.5,.3],[.3,.6]]:
        sol=optimize.minimize(P.objective,seed,jac=P.gradient,method="SLSQP",
                bounds=[(-.125,1.25)]*2,constraints=cons,options={"maxiter":100,"ftol":1e-11})
        center=np.rint(sol.x*1024).astype(int)
        pairs.update((int(center[0]+r),int(center[1]+g)) for r in range(-5,6) for g in range(-5,6))
    for r,g in pairs:
        q=np.array([r,g,1024-r-g]);u=q[:2]/1024
        if all(np.all(p.quantiles(u)[0]<=p.ref+1e-10) for p in problems):
            rows.append({"Y_q10":q.tolist(),"rms":float(np.sqrt(P.objective(u)*100))})
    best=min(rows,key=lambda r:r["rms"])
    pred=D["F"]@(np.asarray(best["Y_q10"])/1024)
    rec={"method":"pooled plus both within-frame gates; multistart sensitivity search, no global certificate",
         "selected":best,"metrics":metrics(D,pred),"per_frame":{
         str(f):metrics(D,pred,D["frame"]==f,True) for f in (0,1)}}
    dump(LOCAL/"mix_robust_alternative.json",rec)
    print(json.dumps(rec))


def t1_loo(start,stop):
    D=data();stockpred=D["F"]@(STOCK/1024)
    baseline=read(LOCAL/"baseline.json")
    fits=read(LOCAL/"t1_fits.json")
    chosen=min((r for r in fits if r["integer_gate"]),key=lambda r:r["integer"]["bin_weighted_rms"])
    chosen_q=np.asarray(chosen["Y_q10"])
    out=[]
    for f in range(start,min(stop,2)):
        test=D["frame"]==f;train=~test;P=T1Problem(D,train)
        stocktrain=metrics(D,stockpred,train,True);stocktest=metrics(D,stockpred,test,True)
        configs=[]
        for q in [chosen_q,None]:
            curves,sol=P.solve(q)
            qq=np.asarray(q) if q is not None else sol.weights*1024
            if q is not None: curves=exact_integer_curves(curves,qq,D["curve"],radius=22)
            pred=curves_predict(D,curves,qq)
            tr=metrics(D,pred,train,True);te=metrics(D,pred,test,True)
            configs.append({"kind":"fixed_integer_config" if q is not None else "free_float_config",
                  "Y_q10":qq.tolist(),"curves":curves.tolist(),"success":bool(sol.success),
                  "convex_gap_mse":sol.convex_gap_mse,"train":tr,"test":te,
                  "train_gate":gate(tr,stocktrain),"test_gate":gate(te,stocktest)})
        out.append({"held_out":baseline["frames"][f],"stock_train":stocktrain,
                    "stock_test":stocktest,"fits":configs})
    dump(LOCAL/f"t1_loo_{start}_{stop}.json",out)
    print(json.dumps([{ "held_out":r["held_out"],"fits":[{k:v[k] for k in
          ("kind","Y_q10","train_gate","test_gate","test")} for v in r["fits"]]} for r in out]))


def t1_loo_grid(start,stop,fold):
    D=data();test=D["frame"]==fold;train=~test;P=T1Problem(D,train)
    stockpred=D["F"]@(STOCK/1024)
    ref=metrics(D,stockpred,train,True)
    out=[]
    for i in range(start,min(stop,len(T1_MIXES))):
        if i==1: continue  # The pooled fitted mix must not enter a held-out model's candidate grid.
        q=np.asarray(T1_MIXES[i]);curves,sol=P.solve(q)
        quant=exact_integer_curves(curves,q,D["curve"],radius=22)
        pred=curves_predict(D,quant,q)
        mt=metrics(D,pred,train,True)
        out.append({"index":i,"Y_q10":q.tolist(),"curves_u8":quant.tolist(),
                    "train":mt,"test":metrics(D,pred,test,True),
                    "train_gate":gate(mt,ref),"success":bool(sol.success),
                    "convex_gap_mse":sol.convex_gap_mse})
    dump(LOCAL/f"t1_loo_grid_{fold}_{start:03d}_{min(stop,len(T1_MIXES)):03d}.json",out)
    good=[r for r in out if r["train_gate"]]
    best=min(good,key=lambda r:r["train"]["bin_weighted_rms"]) if good else None
    print(json.dumps({"fold":fold,"range":[start,min(stop,len(T1_MIXES))],"train_pass_n":len(good),
                      "best_q":best["Y_q10"] if best else None,
                      "best_train_rms":best["train"]["bin_weighted_rms"] if best else None}))


def candidate_matrix(q):
    mm=module("r2_matrix",ROOT/"research/color_table_fit/matrix_model.py")
    stock=mm.read_stock_rows()
    c=stock["row1"].coef.copy();c[0]=q
    r1=stock["row1"].copy(coef=c)
    r2,rule=mm.row2_from_row1(r1,stock)
    assert not r1.violations(stock["row1"]) and not r2.violations(stock["row1"])
    assert r1.neutral_preserving() and r2.neutral_preserving()
    assert r1.offsets[0]==0 and r2.offsets[0]==0
    for r in (r1,r2): assert mm.MatrixRow.from_bytes(r.to_bytes()).to_bytes()==r.to_bytes()
    return {"row1":r1.describe(),"row2":r2.describe(),"row2_derivation":rule}


def characterize():
    D=data();base=read(LOCAL/"baseline.json");mix,rows=choose_mix()
    fits=read(LOCAL/"t1_fits.json")
    assert len(fits)==len(T1_MIXES) and all("convex_gap_mse" in r for r in fits)
    t1=min((r for r in fits if r["integer_gate"]),key=lambda r:r["integer"]["bin_weighted_rms"])
    free=read(LOCAL/"t1_free_float.json")
    preds={"stock":D["F"]@(STOCK/1024),"mix":D["F"]@(np.asarray(mix["Y_q10"])/1024),
           "T1":curves_predict(D,np.asarray(t1["curves_u8"]),np.asarray(t1["Y_q10"])),
           "T1_float":curves_predict(D,np.asarray(free["curves_float"]),np.asarray(free["Y_continuous_q10"]))}
    hc=read(ROOT/"research/gr4_modes/local/hcbw.json")
    to_c=np.asarray(hc["gxr_mix"]["gxr_to_c_from_linsrgb"])
    v=np.asarray(hc["mix_used"]["w_linear_srgb"])@np.linalg.inv(to_c);v/=v.sum()
    preds["pre_curve_reference"]=np.interp(D["x"]@v,D["nodes"],D["curve"])
    assert abs(metrics(D,preds["pre_curve_reference"])["bin_weighted_rms"]-3.8990226419759555)<1e-8
    allmetrics={k:metrics(D,p) for k,p in preds.items()}
    selected={"recipe_slot":"03","firmware_ready":False,"camera_acceptance":"not_run",
        "curve_domain":"white-balanced GXR camera RGB, per-channel interpolation on unchanged A5 nodes",
        "grain_mask":0,"colour_table":"existing row 28 zeroes chroma"}
    ydoc={**selected,"kind":"Y-row only; pooled gate passes, scene holdouts fail",
          "Y_q10":mix["Y_q10"],"matrix":candidate_matrix(mix["Y_q10"]),
          "A5_nodes_u12":D["nodes"].astype(int),"shared_curve_u8":D["curve"].astype(int),
          "extension_mask_if_integrated":1,"metrics":allmetrics["mix"]}
    tdoc={**selected,"kind":"T1 conditional logical RGB; channel assignment pending camera probe",
          "Y_q10":t1["Y_q10"],"matrix":candidate_matrix(t1["Y_q10"]),
          "A5_nodes_u12":D["nodes"].astype(int),"logical_RGB_curves_u8":t1["curves_u8"],
          "T_control":0,"extension_mask_if_integrated":7,"physical_B5_C_D_assignment":None,
          "neutral_axis_max_error_codes":0,"metrics":allmetrics["T1"]}
    dump(LOCAL/"candidate_y_only.json",ydoc)
    dump(LOCAL/"candidate_t1_integer.json",tdoc)
    dump(LOCAL/"candidate_t1_float_bound.json",{**selected,"kind":"floating convex bound, not an integer firmware table",**free})
    fields=["rms","median_abs","p90_abs","gate"]
    with (LOCAL/"pareto_evaluated.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["R_q10","G_q10","B_q10",*fields])
        for r in sorted(rows,key=lambda r:(r["rms"],r["Y_q10"])): w.writerow([*r["Y_q10"],*[r[k] for k in fields]])
    front=read(LOCAL/"pareto_front.json")
    with (LOCAL/"pareto_front.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["R_q10","G_q10","B_q10",*fields])
        for r in front:w.writerow([*r["Y_q10"],*[r[k] for k in fields]])
    binrec=[]
    for i,key in enumerate(D["keys"]):
        s=D["bin"]==i
        binrec.append({"key":int(key),"n":int(s.sum()),**{k:metrics(D,p,s) for k,p in preds.items() if k!="T1_float"}})
    frame={name:{k:metrics(D,p,D["frame"]==f,True) for k,p in preds.items()}
           for f,name in enumerate(base["frames"])}
    thresholds={}
    for minimum in (1,20,100,1000):
        s=D["cnt"][D["bin"]]>=minimum
        thresholds[str(minimum)]={"n_blocks":int(s.sum()),"n_bins":int((D["cnt"]>=minimum).sum()),
                                 **{k:metrics(D,p,s) for k,p in preds.items() if k!="T1_float"}}
    h=np.degrees(np.arctan2(D["lab"][:,2],D["lab"][:,1]))%360
    C=np.hypot(D["lab"][:,1],D["lab"][:,2])
    groups={"red_h330_30":((h>=330)|(h<30))&(C>=15),
            "warm_h30_90":(h>=30)&(h<90)&(C>=15),
            "green_h90_180":(h>=90)&(h<180)&(C>=15),
            "blue_h180_300":(h>=180)&(h<300)&(C>=15)}
    hues={name:{"n":int(s.sum()),**{k:stats((p-D["j"])[s]) for k,p in preds.items()}}
          for name,s in groups.items()}
    # Deliberately authored colours, not semantic labels inferred from contributor photos.
    tests={"sky_blue":(.08,.25,.65),"foliage_green":(.08,.30,.04),
           "skin_warm":(.45,.25,.16),"red":(.65,.04,.025)}
    visible={}
    for name,lin in tests.items():
        x=to_c@np.asarray(lin)*(320/.18)
        rec={"synthetic_colour":True,"min_GXR_input":float(x.min()),"max_GXR_input":float(x.max())}
        ff=np.interp(x,D["nodes"],D["curve"])
        old=float(ff@(STOCK/1024));new=float(ff@(np.asarray(mix["Y_q10"])/1024))
        newt=float(sum(np.interp(x[c],D["nodes"],np.asarray(t1["curves_u8"])[:,c])*(t1["Y_q10"][c]/1024) for c in range(3)))
        ref=float(np.interp(x@v,D["nodes"],D["curve"]))
        rec.update(stock_J=old,mix_J=new,T1_J=newt,reference_J=ref,
                   mix_minus_stock=new-old,T1_minus_stock=newt-old)
        visible[name]=rec
    pure=allmetrics["mix"]["bin_weighted_rms"];tval=allmetrics["T1"]["bin_weighted_rms"]
    ref=allmetrics["pre_curve_reference"]["bin_weighted_rms"]
    closure={"reference_rms":ref,"RMS_gap_closed_fraction":(pure-tval)/(pure-ref),
             "MSE_gap_closed_fraction":(pure*pure-tval*tval)/(pure*pure-ref*ref),
             "RMS_remaining_gap":tval-ref,
             "definition":"same mapped sample; optimal gated shared curve versus unavailable pre-curve reference"}
    rec={"mix":mix,"t1_index":t1["index"],"t1_Y_q10":t1["Y_q10"],"metrics":allmetrics,
         "frame":frame,"bin":binrec,"minimum_bin_size_sensitivity":thresholds,
         "hue_proxy_groups":hues,"visible_synthetic":visible,"closure":closure}
    dump(LOCAL/"characterization.json",rec)
    print(json.dumps({"T1":allmetrics["T1"],"closure":closure,"synthetic":visible,
        "hue_counts":{k:r["n"] for k,r in hues.items()},"solver_failed_n":sum(not r["success"] for r in fits),
        "max_convex_gap_mse":max(r["convex_gap_mse"] for r in fits)}))


def choose_mix():
    rows=read(LOCAL/"mix_integer_near.json")
    for p in sorted(LOCAL.glob("lattice_*.json")): rows.extend(read(p))
    for p in sorted(LOCAL.glob("pareto_grid_*.json")): rows.extend(read(p))
    rows=list({tuple(r["Y_q10"]):r for r in rows}.values())
    best=min((r for r in rows if r["gate"]),key=lambda r:r["rms"])
    return best,rows


def summarize_mix():
    D=data();best,rows=choose_mix()
    ordered=sorted(rows,key=lambda r:(r["rms"],r["median_abs"],r["p90_abs"]))
    front=[]
    for r in ordered:
        if not any(f["median_abs"]<=r["median_abs"] and f["p90_abs"]<=r["p90_abs"] for f in front):
            front.append(r)
    dump(LOCAL/"pareto_front.json",front)
    preds={"stock":D["F"]@(STOCK/1024),"mix":D["F"]@(np.asarray(best["Y_q10"])/1024)}
    out={"selected":best,"evaluated_unique_n":len(rows),"sampled_front_n":len(front),
         "frame":{},"bin":[],"leave_bin_out_fixed":[]}
    for f,name in enumerate(read(LOCAL/"baseline.json")["frames"]):
        s=D["frame"]==f
        out["frame"][name]={k:metrics(D,p,s,rebalance=True) for k,p in preds.items()}
        out["frame"][name]["selected_passes_local_gate"]=gate(out["frame"][name]["mix"],out["frame"][name]["stock"])
    for i,key in enumerate(D["keys"]):
        s=D["bin"]==i
        st={k:metrics(D,p,s) for k,p in preds.items()}
        out["bin"].append({"key":int(key),"n":int(s.sum()),**st})
        ss=~s
        # This is sensitivity for the fixed selected candidate, not a refit.
        out["leave_bin_out_fixed"].append({"key":int(key),
              **{k:metrics(D,p,ss) for k,p in preds.items()}})
    P=MixProblem(D);u=-np.linalg.solve(P.H,P.g);Hi=np.linalg.inv(P.H)
    delta=best["rms"]**2-P.objective(u)*100
    bounds=[]
    for v in (np.array([1,0]),np.array([0,1]),np.array([-1,-1])):
        cen=(v@u+(1 if v[0]<0 else 0))*1024;radius=np.sqrt(delta*(v@Hi@v))*1024
        bounds.append([float(cen-radius),float(cen+radius)])
    out["lower_objective_ellipse_coefficient_bounds"]=bounds
    out["all_lower_rms_integer_points_tested"]=sum(len(read(p)) for p in LOCAL.glob("lattice_*.json"))
    out["all_lower_rms_points_failed_gate"]=all(not r["gate"] for p in LOCAL.glob("lattice_*.json") for r in read(p))
    improved=sum(r["mix"]["bin_weighted_rms"]<r["stock"]["bin_weighted_rms"] for r in out["bin"])
    leavepass=sum(gate(r["mix"],r["stock"]) for r in out["leave_bin_out_fixed"])
    out["bin_summary"]={"improved":improved,"worse":len(out["bin"])-improved,
                        "fixed_candidate_leave_one_bin_gate_pass":leavepass}
    dump(LOCAL/"mix_summary.json",out)
    print(json.dumps({"selected":best,"unique":len(rows),"front":len(front),
                      "bin_summary":out["bin_summary"],"frame":out["frame"]}))


if __name__ == "__main__":
    guard()
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["prepare", "mixfit", "integer_near", "lattice_prepare", "lattice", "pareto_grid", "t1_prepare", "t1fit", "summarize_mix", "loo_frames", "loo_bins", "t1_free", "additive_bound", "robust_mix", "t1_loo", "t1_loo_grid", "characterize"])
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--stop", type=int, default=1)
    p.add_argument("--fold", type=int, default=0)
    a = p.parse_args()
    if a.phase in ("prepare","lattice_prepare","t1_prepare","summarize_mix","t1_free","additive_bound","robust_mix","characterize"): globals()[a.phase]()
    elif a.phase=="t1_loo_grid": t1_loo_grid(a.start,a.stop,a.fold)
    else: globals()[a.phase](a.start, a.stop)
