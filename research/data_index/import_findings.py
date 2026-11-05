#!/usr/bin/env python3
"""Import explicit research findings without reading image files."""
import csv, json, sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LOCAL = Path(__file__).resolve().parent / "local"

def main():
 db = sqlite3.connect(LOCAL / "index.sqlite")
 db.execute("CREATE TABLE IF NOT EXISTS conflicts (sha256 TEXT NOT NULL, field TEXT NOT NULL, value_a TEXT NOT NULL, source_a TEXT NOT NULL, value_b TEXT NOT NULL, source_b TEXT NOT NULL, PRIMARY KEY (sha256,field,value_a,source_a,value_b,source_b))")
 before = db.execute("SELECT SUM(dat IS NULL OR dat=\"unknown\" OR dat=\"\"), SUM(recipe IS NULL OR recipe=\"unknown\" OR recipe=\"\"), SUM(content IS NULL OR content=\"unknown\" OR content=\"\") FROM photos").fetchone()
 initial = db.total_changes
 def add(h, field, value, source):
  if value and value != "unknown" and db.execute("SELECT 1 FROM photos WHERE sha256=?", (h,)).fetchone():
   db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)", (h,field,str(value),str(source)))
 def hashes(row):
  h=row.get("sha256")
  if not h: return []
  return [x[0] for x in db.execute("SELECT ? UNION SELECT jpg_sha256 FROM pairs WHERE dng_sha256=?",(h,h))]
 lib=ROOT/"research/library_28mm_r1/local/classification.csv"
 with lib.open(newline="") as f:
  for row in csv.DictReader(f):
   for h in hashes(row):
    add(h,"setting",row["selector_name"],lib)
    if row["dat_possibility"] == "excluded_by_owner_predat_backup_provenance": add(h,"dat_presence","absent_by_predat_backup_provenance",lib)
 hist=ROOT/"research/bluecyan_r1/local/history/identities.json"
 for row in json.loads(hist.read_text()):
  ident=row.get("identity") or {}; rec=ident.get("record") or {}
  if not ident.get("accepted"): continue
  cats=rec.get("catalogs") or []
  for h in (row.get("raw_sha256"), row.get("jpeg_sha256")):
   if not h: continue
   if rec.get("labels"): add(h,"recipe"," / ".join(sorted(rec["labels"])),hist)
   if cats and len({c.get("sha256") for c in cats})==1: add(h,"dat",cats[0]["name"]+" sha256:"+cats[0]["sha256"],hist)
 # Relate frame results only through the corresponding hashed inputs manifest.
 for rel, key in [("probe_pack_r2/local/field_probe2_20261103","response_identity"),("probe_pack_r3/field/local","identity")]:
  directory=ROOT/"research"/rel; manifest=directory/"inputs.json"; table=directory/"frame-identities.csv"
  byframe={}
  for item in json.loads(manifest.read_text())["files"]:
   byframe.setdefault(Path(item["file"]).stem.upper(),[]).append(item["sha256"])
  with table.open(newline="") as f:
   for row in csv.DictReader(f):
    for h in byframe.get(row["frame"].upper(),[]):
     add(h,"probe_response",row[key],table)
     if row.get("page"): add(h,"probe_page",row["page"],table)
 # Bracket labels are admitted only when the analysis marked them verified.
 bracket=ROOT/"research/probe_pack_r1/local/bracket_20261103"
 mapping={}
 for item in json.loads((bracket/"inputs.json").read_text())["files"]:
  mapping.setdefault(Path(item["file"]).stem.upper(),[]).append(item["sha256"])
 for row in json.loads((bracket/"identity.json").read_text()):
  if row.get("label_verified"):
   for h in mapping.get(row["frame"].upper(),[]): add(h,"probe_response",row.get("response_label"),bracket/"identity.json")
 # Owner-supplied chart-session assignments are attached by the listed hashes.
 report=ROOT/"research/chart_session_20261024/local/operator_reports/mount.frames.user-report-v2.json"
 for row in json.loads(report.read_text())["frames"].values():
  for h in row.get("hashes",{}).values():
   add(h,"owner_recipe_assignment",row.get("recipe_assignment"),report)
   add(h,"page",row.get("page"),report)
 # The field manifest includes natural-scene exposures as well as probe pages.
 field=ROOT/"research/probe_pack_r1/local/field_20261103"
 natural=field/"natural_identity.json"
 names={r["frame"] for r in json.loads(natural.read_text())["frames"] if r.get("role")=="natural_scene_identity_only"}
 for item in json.loads((field/"inputs.json").read_text())["files"]:
  if Path(item["file"]).stem.upper() in names:
   h=item["sha256"]
   db.execute("DELETE FROM evidence WHERE sha256=? AND field='content' AND value='probe' AND source=?",(h,str(field/"inputs.json")))
   add(h,"content","natural",natural)
 directory=ROOT/"research/probe_pack_r3/field/local"
 byframe={}
 for item in json.loads((directory/"inputs.json").read_text())["files"]:
  byframe.setdefault(Path(item["file"]).stem.upper(),[]).append(item["sha256"])
 with (directory/"frame-identities.csv").open(newline="") as f:
  for row in csv.DictReader(f):
   if row["label_conflict"]=="True":
    for h in byframe.get(row["frame"].upper(),[]):
     db.execute("INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?)",(h,"probe_label_response","A",str(ROOT/"research/probe_pack_r3/field/QUICK_VERDICT.md"),row["identity"],str(directory/"frame-identities.csv")))
 # Preserve existing evidence and expose disagreements. Content synonyms were used by the original index.
 for field in ("dat","recipe","content","page","setting","dat_presence","probe_response","probe_page"):
  rows=db.execute("SELECT sha256,value,source FROM evidence WHERE field=? ORDER BY sha256,value,source",(field,)).fetchall()
  grouped={}
  for h,v,s in rows: grouped.setdefault(h,[]).append((v,s))
  for h,items in grouped.items():
   for i,(a,sa) in enumerate(items):
    for b,sb in items[i+1:]:
     if a!=b: db.execute("INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?)",(h,field,a,sa,b,sb))
   if field in ("dat","recipe","content","page"):
    values={v for v,s in items}
    db.execute("UPDATE photos SET "+field+"=? WHERE sha256=?",(next(iter(values)) if len(values)==1 else "unknown",h))
 db.commit()
 print("before",before,"after",db.execute("SELECT SUM(dat IS NULL OR dat=\"unknown\" OR dat=\"\"), SUM(recipe IS NULL OR recipe=\"unknown\" OR recipe=\"\"), SUM(content IS NULL OR content=\"unknown\" OR content=\"\") FROM photos").fetchone())
 print("evidence",db.execute("SELECT field,count(*) FROM evidence GROUP BY field").fetchall())
 print("conflicts",db.execute("SELECT field,count(*),count(DISTINCT sha256) FROM conflicts GROUP BY field").fetchall())
 print("changes",db.total_changes-initial)
 db.close()
if __name__ == "__main__": main()
