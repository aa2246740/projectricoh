"""Recompute review conclusions from retained evidence; never changes inputs."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,ROOT,save

cases=json.loads((HERE/"adversarial.json").read_text())
fault=json.loads((HERE/"h08-retire-adversarial.json").read_text())[0]
masked=json.loads((HERE/"initial_stubbed_evidence/h08-retire-adversarial.json").read_text())[0]
table=[]
for name in ("i","ii","iii","iv","v","vii","viii"):
    r=next(c for c in cases if c["name"]==name);a=r["final"]
    assert not r.get("error")
    table.append(dict(sequence=name,mode=a["mode"],state=a["root"]["state"],flags=hex(a["root"]["flags"]),
        diag=a["diag_early"],native_H07=a["native_visits"]["H07_native"],native_H08=a["native_visits"]["H08_native"],
        deep_sha256=a["deep_sha256"],deep_cells=a["deep_cells"],
        calls_ok=all(not isinstance(s["result"],dict) or s["result"].get("ok",True) for s in r["steps"])))
save("scenario-table.json",table)
after=fault["final"]
assert after["mode"]==5 and after["root"]["state"]==6 and after["root"]["flags"]==163
assert after["native_visits"]["H07_native"]==0 and after["native_visits"]["H08_native"]==1
assert fault["steps"][2]["after"]["mode"]==1
assert fault["steps"][2]["after"]["deep_sha256"]==after["deep_sha256"]
assert any(x["value"]==5 and x["writer_pc"]=="0x20268774" for x in fault["settings_writes"])
assert masked["final"]["mode"]==1
assert any(x["value"]==5 and x["writer_pc"]=="0x20268774" for x in masked["settings_writes"])
assert "image_mode_getter" not in fault["stub_hits"]
save("counterexample.json",dict(verdict="不可以上卡",mode_before=1,mode_after=5,
    native_writer="0x20268774",H08_continuation="0x202bb96c",root_state=6,flags="0xa3",
    diag_at_failure=next(s["after"]["diag_early"] for s in fault["steps"] if s["action"]=="scroll down"),
    final_diag=after["diag_early"],deep_before_sha256=fault["steps"][2]["after"]["deep_sha256"],
    deep_after_sha256=after["deep_sha256"],initial_stubbed_final_mode=masked["final"]["mode"],
    real_getter_final_mode=after["mode"],input_ui_fault="one bit in detached UI snapshot magic",
    native_UI_hand_seeded=False,physical_reproduction=False))
inherited=json.loads((HERE/"inherited.json").read_text())
assert len(inherited)==20 and not any(c["violations"] or c["error"] for c in inherited)
power=json.loads((HERE/"power02-adversarial.json").read_text())[1]
assert power["cold_before_H01"]["mode"]==1 and power["cold_before_H01"]["deep_cells"]==0
assert power["steps"][0]["after"]["ui"]["cursor"]==2
assert power["steps"][0]["after"]["deep_cells"]==0 and power["same_full02_after_OK"]
deep=json.loads((HERE/"deep-rows-comparison.json").read_text())
assert [x["slot"] for x in deep]==[1,2,4]
assert all(x["all_bytes_equal"] and x["t"]==x["expected_t"] and sum(r["bytes"] for r in x["rows"])==503 for x in deep)
registers=json.loads((HERE/"h07-register-balance.json").read_text())
assert len(registers)==2 and all(x["stack_balanced"] and x["r8_to_r13_preserved"] for x in registers)
dat=(ROOT/"firmware/image_v35/local/package/SD_ROOT/GXRCE.DAT").read_bytes()
save("package-identities.json",dict(dat_sha256=hashlib.sha256(dat).hexdigest(),
    official_body_pin=dat[48:80].hex(),build_id=dat[80:112].hex(),abi_id=dat[212:228].hex()))
before=json.loads((HERE/"protected-before.json").read_text())
changed=[]
for name,digest in before.items():
    p=ROOT/name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:changed.append(name)
save("protected-after.json",dict(frozen_inputs=len(before),changed=changed,unchanged=not changed))
assert not changed,changed
print("REVIEW_EVIDENCE_OK",len(table),"scenario rows; P0 confirmed; 20 inherited clean; frozen inputs",len(before))
