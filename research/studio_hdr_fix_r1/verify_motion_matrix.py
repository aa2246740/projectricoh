"""Vary object position, size, motion and local texture using generated scenes."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(OUT), str(ROOT / "studio/src"), str(ROOT / "studio/tests")]
from finish_evidence import current_source
import hdr_support as hs
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

audit.forbid_volumes()
audit.forbid_network(True)
rows = []
source = current_source()
for seed in (0, 2):
    for x in (180, 300, 420):
        for size in (8, 16, 40):
            for distance in (8, 24, 64, 80):
                for quiet in (False, True):
                    first = hs.scene(seed=seed)
                    if quiet:
                        first[64:224, x-20:x+140] = .22
                    second = first.copy()
                    first[96:96+size, x:x+size] = .035
                    second[96:96+size, x+distance:x+distance+size] = .035
                    raw = g.raw_luma(open_dng(hs.camera_dng(first)))
                    row = {"seed":seed,"x":x,"size":size,"distance":distance,"quiet":quiet}
                    try:
                        _, stats = g.hdr_from_camera_jpeg(hs.camera_jpeg(second), raw)
                        row.update(rejected=False, alignment=stats["alignment"])
                    except g.HdrUnsupported as error:
                        row.update(rejected=True,reason=error.reason)
                    rows.append(row)
accepted = [row for row in rows if not row["rejected"]]
result = {"total":len(rows),"rejected":len(rows)-len(accepted),"accepted":accepted,"cases":rows,"source_sha256":source}
name = sys.argv[1] if len(sys.argv)>1 else "motion_matrix"
with (OUT/(name+".json")).open("x") as stream:
    json.dump(result,stream,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ("cases","source_sha256")}),flush=True)
assert audit.network_attempts() == []
assert source == current_source()
raise SystemExit(bool(accepted))
