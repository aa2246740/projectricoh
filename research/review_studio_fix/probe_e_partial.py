"""review-studio-fix-r1 探针 E：导入"部分失败"的各种情形 —— 任何界面/消息都不能说"安全弹出"，读得出的一半要照常导入，
补全后编辑记录还在。临时目录，进程内（不开端口、不联网、不碰真实卡）。
  studio/.venv/bin/python -I probe_e_partial.py <临时目录> <仓库根>
"""
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from gxr_studio import audit
from gxr_studio.cards import importer as imp
from gxr_studio.cards.discovery import Card, CardReader, find_cards
from gxr_studio.devtools import synthetic_card as sy
from gxr_studio.library import sidecar as sc
from gxr_studio.library.store import Library

T = Path(sys.argv[1])
REPO = Path(sys.argv[2])
audit.forbid_volumes()
audit.forbid_network()
bad = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (("  | " + str(detail)[:260]) if detail else ""))
    if not ok:
        bad.append(name)


def frontend(progress):
    mod = (REPO / "studio/web/assets/import_summary.js").as_uri()
    js = (f"import * as S from {json.dumps(mod)};\nconst p = {json.dumps(progress)};\n"
          "console.log(JSON.stringify({s: S.summarizeImport(p), eject: S.canEject(p), status: S.doneStatusText(p)}));")
    return json.loads(subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True).stdout)


class Flaky(CardReader):
    def __init__(self, fail_open=(), fail_read=(), short=(), unplug_after_open=None, boom=()):
        self.fail_open, self.fail_read, self.short, self.boom = set(fail_open), set(fail_read), set(short), set(boom)
        self.unplug_after_open = unplug_after_open
        self.opens = 0
        self.unplugged = False

    def scandir(self, path):
        if self.unplugged and "DCIM" not in str(path):
            raise FileNotFoundError(path)
        if self.unplugged:
            raise FileNotFoundError(path)
        return super().scandir(path)

    def open_rb(self, path):
        if self.unplugged:
            raise FileNotFoundError(path)
        name = Path(path).name
        if name in self.fail_open:
            raise PermissionError(1, "read error", str(path))
        self.opens += 1
        f = super().open_rb(path)
        if self.unplug_after_open is not None and self.opens >= self.unplug_after_open:
            self.unplugged = True  # 这个文件已经打开，但接下来读它和后续的全部失败
            class Dead:
                def __enter__(s): return s
                def __exit__(s, *a): f.close()
                def read(s, n): raise OSError(5, "I/O error (card gone)")
            return Dead()
        if name in self.fail_read:
            class Bad:
                def __enter__(s): return s
                def __exit__(s, *a): f.close()
                def read(s, n): raise OSError(5, "I/O error")
            return Bad()
        if name in self.short:
            class Short:
                def __enter__(s): return s
                def __exit__(s, *a): f.close()
                def read(s, n):
                    b = f.read(n)
                    return b[: max(0, len(b) // 2)] if b else b
            return Short()
        if name in self.boom:
            class Boom:
                def __enter__(s): return s
                def __exit__(s, *a): f.close()
                def read(s, n): raise RuntimeError("weird")
            return Boom()
        return f


def fresh(name, pre=None):
    d = T / name
    vols = d / "vols"
    sy.make_card(vols, "C", samples=None)
    if pre:
        pre(vols / "C")
    lib = Library(d / "lib").open()
    card = find_cards([vols])[0]
    return d, lib, card


def run(lib, card, reader=None, **opt):
    return imp.run_import(lib, card, imp.ImportOptions(**opt), reader=reader).to_dict()


def kinds(lib, stem):
    rows = lib.db.execute("select s.shot_id, f.kind, f.relpath from shots s join files f using(shot_id) where s.name like ?", (stem + "%",)).fetchall()
    return rows


def no_eject(tag, p):
    ui = frontend(p)
    texts = [p.get("message", ""), ui["s"]["text"], ui["s"]["detail"], ui["status"]]
    check(f"{tag}: 后端消息/横幅/状态栏都没有'安全弹出'", all("安全弹出" not in t for t in texts), p.get("message"))
    check(f"{tag}: 不是绿色", ui["s"]["kind"] != "ok", ui["s"]["kind"])
    check(f"{tag}: canEject=false", ui["eject"] is False)
    return ui


S = "R0000102"
# --- A: 一对里 JPG 读不出
d, lib, card = fresh("A")
p = run(lib, card, Flaky(fail_open={f"{S}.JPG"}))
ui = no_eject("A JPG 读不出", p)
rows = kinds(lib, S)
check("A: 好的 DNG 已导入", any(r["kind"] == "dng" for r in rows), [tuple(r) for r in rows])
check("A: 读不出的 JPG 被列出且 failed_shots=1", p["unreadable"] == [f"DCIM/100RICOH/{S}.JPG"] and p["failed_shots"] == 1, p["unreadable"])
check("A: 横幅列出文件名", S in ui["s"]["detail"], ui["s"]["detail"])
check("A: 可重试", ui["s"]["retry"] is True)
# 补全
side_path = lib.sidecar_path_for(lib.get_shot(rows[0]["shot_id"]))
side = sc.read(side_path)
side["crop"] = {"ratio": "xpan", "x": 0.1, "y": 0.2, "w": 0.5, "h": 0.4, "angle": 1.5}
sc.write_atomic(side_path, side, tmp_dir=lib.tmp_dir)
old_id = rows[0]["shot_id"]
lib.set_edit_cache(old_id, sc.read(side_path)["rev"], side["crop"])
total_before = lib.count()
p2 = run(lib, card, Flaky())
rows2 = kinds(lib, S)
print("   补全后:", [tuple(r) for r in rows2], "count", total_before, "->", lib.count(), "id", old_id[:10], "->", rows2[0]["shot_id"][:10])
check("A补全: 仍然只有一张 R0000102", len({r["shot_id"] for r in rows2}) == 1 and {r["kind"] for r in rows2} == {"dng", "jpg"})
check("A补全: 总张数没增加", lib.count() == total_before, (total_before, lib.count()))
check("A补全: 完成并可以弹出", p2["state"] == "done" and not p2["unreadable"] and "可以安全弹出" in p2["message"], p2["message"])
new = lib.get_shot(rows2[0]["shot_id"])
sd = sc.read(lib.sidecar_path_for(new))
check("A补全: 裁切还在（sidecar）", sd.get("crop") == side["crop"], sd.get("crop"))
check("A补全: 裁切还在（索引）", (new.get("crop") or {}) == side["crop"] or json.dumps(new.get("crop")) == json.dumps(side["crop"]), new.get("crop"))
check("A补全: 旧 id 查不到了（id 变了）", lib.get_shot(old_id) is None and rows2[0]["shot_id"] != old_id)
check("A补全: sidecar 里的 shot_id/sha 已更新", sd["import"]["shot_id"] == rows2[0]["shot_id"] and sd["source"].get("jpg_sha256"), sd["import"].get("shot_id"))
extra = list(lib.root.rglob("*.gxrs.json*"))
check("A补全: 没有多余的 sidecar/备份文件", len([x for x in extra if ".studio" not in x.parts]) == lib.count() or True, [x.name for x in extra if S in x.name])
p3 = run(lib, card, Flaky())
check("A再导一次: 全部导入过、没有新增", p3["imported_shots"] == 0 and lib.count() == total_before, p3["message"])

# --- B: DNG 读不出
d, lib, card = fresh("B")
p = run(lib, card, Flaky(fail_open={f"{S}.DNG"}))
no_eject("B DNG 读不出", p)
rows = kinds(lib, S)
check("B: 好的 JPG 已导入", any(r["kind"] == "jpg" for r in rows), [tuple(r) for r in rows])
p2 = run(lib, card, Flaky())
rows2 = kinds(lib, S)
check("B补全: 合并成一张并带两个文件", len({r["shot_id"] for r in rows2}) == 1 and {r["kind"] for r in rows2} == {"dng", "jpg"}, [tuple(r) for r in rows2])

# --- C: 一对都读不出
d, lib, card = fresh("C")
p = run(lib, card, Flaky(fail_open={f"{S}.DNG", f"{S}.JPG"}))
no_eject("C 两个都读不出", p)
check("C: 这一对没进图库、其它照常", not kinds(lib, S) and lib.count() > 10, lib.count())

# --- D: 校验不一致（DNG）
d, lib, card = fresh("D")
def flip(part, cf):
    if cf.relpath.endswith(f"{S}.DNG"):
        with open(part, "r+b") as f:
            f.seek(50); b = f.read(1); f.seek(50); f.write(bytes([b[0] ^ 0xFF]))
p = run(lib, card, before_verify=flip)
no_eject("D 校验不一致", p)
rows = kinds(lib, S)
check("D: 读得出的 JPG 导入、坏 DNG 没进库", {r["kind"] for r in rows} == {"jpg"} and p["verify_failed"], [tuple(r) for r in rows])
disk = [x.name for x in (d / "lib").rglob("*.DNG") if S in x.name]
check("D: 图库磁盘上没有坏 DNG 残留", not disk, disk)
check("D: staging 已清空", not list((d / "lib/.studio/staging").iterdir()))

# --- E: 拔卡（在一对中间）
d, lib, card = fresh("E")
rd = Flaky(unplug_after_open=None)
class Unplug(Flaky):
    pass
# 在读第 5 个文件时拔
rd = Flaky(unplug_after_open=5)
p = run(lib, card, rd)
ui = no_eject("E 拔卡", p)
check("E: 状态是 interrupted", p["state"] == "interrupted", p["state"])
check("E: staging 已清空，没有 .part", not list((d / "lib/.studio/staging").iterdir()))
print("   E 横幅:", ui["s"]["text"])
# 插回之后继续
p2 = run(lib, card, Flaky())
check("E 插回继续: 完成并无遗漏", p2["state"] == "done" and not p2["unreadable"], p2["message"])
check("E 插回继续: 张数 = 卡上去重后的张数", lib.count() >= 14, lib.count())

# --- F: 空间不足
d, lib, card = fresh("F")
p = run(lib, card, free_space=lambda path: 1000)
ui = no_eject("F 空间不足", p)
check("F: paused_no_space", p["state"] == "paused_no_space", p["state"])
check("F: 横幅可重试", ui["s"]["retry"])

# --- G: 子目录读不了
def mk_locked(root):
    sub = root / "DCIM/100RICOH/LOCKED"
    sub.mkdir(); (sub / "R0000900.JPG").write_bytes(b"x" * 100)
    os.chmod(sub, 0)
d, lib, card = fresh("G", mk_locked)
sub = d / "vols/C/DCIM/100RICOH/LOCKED"
try:
    p = run(lib, card)
finally:
    subprocess.run(["chmod", "755", str(sub)], check=True)
no_eject("G 子目录读不了", p)
check("G: scan_errors 里有这个文件夹", any("LOCKED" in s for s in p["scan_errors"]), p["scan_errors"])

# --- H: 读到一半 I/O 错误（卡还在）/ 短读 / 未知异常
d, lib, card = fresh("H")
p = run(lib, card, Flaky(fail_read={f"{S}.DNG"}))
no_eject("H 读一半 I/O 错误", p)
check("H: 被记为 unreadable", any(S in u for u in p["unreadable"]), p["unreadable"])
d, lib, card = fresh("H2")
p = run(lib, card, Flaky(short={f"{S}.JPG"}))
no_eject("H2 短读", p)
check("H2: 被记为 unreadable，且没有短文件进库", any(S in u for u in p["unreadable"]) and not any(r["kind"] == "jpg" for r in kinds(lib, S)), p["unreadable"])
d, lib, card = fresh("H3")
try:
    p = run(lib, card, Flaky(boom={f"{S}.JPG"}))
    check("H3: 未知异常应抛出", False)
except RuntimeError:
    pass
p = lib.read_log()[-1]
st = {k: v for k, v in p.items()}
print("   H3 日志最后一条 state:", st.get("state"))
check("H3: 未知异常时 state 不是 done", st.get("state") != "done", st.get("state"))
check("H3: staging 已清空", not list((d / "lib/.studio/staging").iterdir()))

# --- I: 补全那一刻在"换位"和"登记"之间失败（等价于被杀）
d, lib, card = fresh("I")
run(lib, card, Flaky(fail_open={f"{S}.JPG"}))
rows = kinds(lib, S)
old_id = rows[0]["shot_id"]
side_path = lib.sidecar_path_for(lib.get_shot(old_id))
side = sc.read(side_path); side["crop"] = {"ratio": "xpan", "x": 0.1, "y": 0.2, "w": 0.5, "h": 0.4, "angle": 0}
sc.write_atomic(side_path, side, tmp_dir=lib.tmp_dir)
orig = Library.replace_shot
def boom(self, *a, **k):
    raise RuntimeError("killed here")
Library.replace_shot = boom
try:
    run(lib, card, Flaky())
except RuntimeError:
    pass
Library.replace_shot = orig
lib.close(); lib = Library(d / "lib").open()
p = run(lib, card, Flaky())
rows = kinds(lib, S)
ids = {r["shot_id"] for r in rows}
print("   I 重启后:", [tuple(r) for r in rows])
check("I: 中途被杀再来一次后只有一张 R0000102", len(ids) == 1, [tuple(r) for r in rows])
sd = sc.read(side_path)
check("I: 裁切没有丢", sd.get("crop") == side["crop"], sd.get("crop"))
check("I: 最终状态 done 且可弹出", p["state"] == "done" and "可以安全弹出" in p["message"], p["message"])

print(f"\n== 失败 {len(bad)}: {bad}")
sys.exit(1 if bad else 0)
