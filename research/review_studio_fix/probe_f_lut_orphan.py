"""review-studio-fix-r1 探针 F：拟合子进程在服务被杀（SIGKILL / SIGHUP / SIGINT / SIGTERM）后会不会残留；上传限制；路径穿越。
真启动 gxr-studio（只监听 127.0.0.1，所有目录在临时目录），不联网、不碰真实卡。
  studio/.venv/bin/python -I probe_f_lut_orphan.py <临时目录> <仓库根>
"""
import json, os, signal, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

T = Path(sys.argv[1]); REPO = Path(sys.argv[2])
sys.path.insert(0, str(REPO / "studio/tests"))
import e0_support as t
from gxr_studio.camdata import calib, store
from gxr_studio.lut.cube import write_cube
from gxr_studio.cards.importer import run_import
from gxr_studio.cards.discovery import find_cards
from gxr_studio.devtools import synthetic_card as sy
from gxr_studio.library.store import Library

bad = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (("  | " + str(detail)[:240]) if detail else ""))
    if not ok: bad.append(name)

def ps_workers():
    out = subprocess.run(["ps", "-eo", "pid,ppid,etime,command"], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if "gxr_studio.lut.worker" in l and str(T) in l]

def prepare(name):
    d = T / name
    home, lib_dir, vols = d / "home", d / "lib", d / "vols"
    raw = t.fixture_dat(127)
    store.import_from_dat(raw, home)
    calib.import_calibration(home, calib.dev_sources(t.REPO))
    sy.make_card(vols, "C", samples=sy.DEFAULT_SAMPLES)
    lib = Library(lib_dir).open()
    run_import(lib, find_cards([vols])[0])
    lib.close()
    cube = d / "c.cube"
    write_cube(cube, lambda x: x ** 0.9, 17)
    return d, home, lib_dir, vols, cube

def start_server(d, home, lib_dir, vols):
    env = {**os.environ, "GXR_STUDIO_HOME": str(home), "GXR_STUDIO_LIBRARY": str(lib_dir), "GXR_STUDIO_VOLUMES": str(d / "emptyvols"),
           "GXR_STUDIO_EXPORT": str(d / "exp"), "GXR_STUDIO_TOKEN": "tok-" + "z" * 40}
    (d / "emptyvols").mkdir(exist_ok=True)
    p = subprocess.Popen([str(REPO / "studio/.venv/bin/gxr-studio"), "--no-browser"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         start_new_session=True)
    line = p.stdout.readline()
    port = int(line.split("127.0.0.1:")[1].split("/")[0])
    return p, port

def call(port, method, path, body=None, headers=None, raw=None):
    h = {"X-GXR-Token": "tok-" + "z" * 40, "Host": f"127.0.0.1:{port}", **(headers or {})}
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if body is not None: h["Content-Type"] = "application/json"
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def scenario(name, sig):
    d, home, lib_dir, vols, cube = prepare(name)
    p, port = start_server(d, home, lib_dir, vols)
    try:
        s, b = call(port, "POST", "/api/lut/upload", raw=cube.read_bytes(), headers={"X-GXR-Filename": "c.cube"})
        cid = json.loads(b)["cube_id"]
        s, b = call(port, "POST", "/api/lut/fit", {"cube_id": cid, "profile": "normal"})
        job = json.loads(b); print(name, "fit start", s, str(job)[:100])
        time.sleep(4)
        w = ps_workers()
        check(f"{name}: 拟合子进程在跑", len(w) == 1, w)
        os.killpg(p.pid, sig) if sig in (signal.SIGHUP,) else os.kill(p.pid, sig)
        t0 = time.time()
        try: p.wait(15)
        except subprocess.TimeoutExpired: print("   server did not exit in 15s"); 
        time.sleep(4)
        w2 = ps_workers()
        print(f"   {name}: server exit={p.poll()} 信号后 4s 仍在的拟合子进程：{len(w2)}")
        if w2:
            print("   ", w2[0])
        return name, w2
    finally:
        if p.poll() is None:
            p.kill(); p.wait()

res = {}
for name, sig in (("term", signal.SIGTERM), ("int", signal.SIGINT)):
    n, w = scenario(name, sig)
    check(f"{name}: 服务退出后没有残留的拟合进程", not w, w)
    for l in w: os.kill(int(l.split()[0]), signal.SIGKILL)
for name, sig in (("hup", signal.SIGHUP), ("kill9", signal.SIGKILL)):
    n, w = scenario(name, sig)
    res[name] = w
    # 记录：这两种是否残留；残留的我们手动清理，并记下它多久之后自己结束
    print(f"   [{name}] 残留 = {len(w)}")
    for l in w:
        pid = int(l.split()[0]); t0 = time.time()
        while time.time() - t0 < 120:
            try: os.kill(pid, 0)
            except OSError: break
            time.sleep(2)
        alive = True
        try: os.kill(pid, 0)
        except OSError: alive = False
        print(f"   [{name}] 子进程 {pid} 120 秒内{'自己结束了' if not alive else '仍然在跑，我手动结束'}（{time.time()-t0:.0f}s）")
        if alive: os.kill(pid, signal.SIGKILL)
print("\n== FAIL", len(bad), bad)
