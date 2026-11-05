#!/usr/bin/env python3
"""Merge validated, per-model JSONL labels into the private photo index."""
import argparse, json, math, re, sqlite3, sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
CONTENT = {"screen_chart","printed_chart","probe_page","natural","lcd_or_screen_photo","other","unknown"}
ENV = {"outdoor_sun","outdoor_shade","overcast","indoor_artificial","mixed","night","unknown"}
SUBJECTS = {"skin","sky","foliage","blue_object","red_object","saturated_colour","clipped_highlights","deep_shadow","neutral_grey","architecture","text_or_signage"}
MAPPING = {"screen":"screen_chart", "physical":"printed_chart", "probe":"probe_page", "natural":"natural"}

def validate(obj, line):
 if not isinstance(obj,dict) or set(obj) != {"sha256","content","environment","subjects","monochrome","confidence","model","notes"}: raise ValueError(f"line {line}: expected exactly sha256 and all label fields")
 if not isinstance(obj["sha256"],str) or not re.fullmatch(r"[0-9a-f]{64}",obj["sha256"]): raise ValueError(f"line {line}: invalid sha256")
 if obj["content"] not in CONTENT or obj["environment"] not in ENV: raise ValueError(f"line {line}: invalid content or environment")
 if not isinstance(obj["subjects"],list) or any(not isinstance(s,str) or s not in SUBJECTS for s in obj["subjects"]) or len(set(obj["subjects"]))!=len(obj["subjects"]): raise ValueError(f"line {line}: invalid subjects")
 if type(obj["monochrome"]) is not bool: raise ValueError(f"line {line}: monochrome must be boolean")
 c=obj["confidence"]
 if type(c) not in (int,float) or not math.isfinite(c) or not 0<=c<=1: raise ValueError(f"line {line}: invalid confidence")
 if not isinstance(obj["model"],str) or not obj["model"].strip() or not isinstance(obj["notes"],str): raise ValueError(f"line {line}: invalid model or notes")
 return obj

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("input",nargs="?",type=Path,default=BASE/"local/labels_gemini.jsonl"); args=p.parse_args()
 records=[]; seen=set()
 with args.input.open(encoding="utf-8") as f:
  for n,line in enumerate(f,1):
   if not line.strip(): raise ValueError(f"line {n}: empty line")
   x=validate(json.loads(line),n); key=(x["sha256"],x["model"])
   if key in seen: raise ValueError(f"line {n}: duplicate sha256 and model")
   seen.add(key); records.append(x)
 db=sqlite3.connect(BASE/"local/index.sqlite"); db.execute("PRAGMA foreign_keys=ON")
 db.executescript("""
 CREATE TABLE IF NOT EXISTS labels (sha256 TEXT PRIMARY KEY REFERENCES photos(sha256), content TEXT NOT NULL, environment TEXT NOT NULL, subjects TEXT NOT NULL, monochrome INTEGER, confidence REAL, model TEXT, notes TEXT);
 CREATE TABLE IF NOT EXISTS label_sources (sha256 TEXT NOT NULL REFERENCES photos(sha256), model TEXT NOT NULL, content TEXT NOT NULL, environment TEXT NOT NULL, subjects TEXT NOT NULL, monochrome INTEGER NOT NULL, confidence REAL NOT NULL, notes TEXT NOT NULL, source TEXT NOT NULL, PRIMARY KEY(sha256,model));
 CREATE TABLE IF NOT EXISTS conflicts (sha256 TEXT NOT NULL, field TEXT NOT NULL, value_a TEXT NOT NULL, source_a TEXT NOT NULL, value_b TEXT NOT NULL, source_b TEXT NOT NULL, PRIMARY KEY(sha256,field,value_a,source_a,value_b,source_b));
 """)
 source=str(args.input.resolve())
 with db:
  for x in records:
   h=x["sha256"]
   if not db.execute("SELECT 1 FROM photos WHERE sha256=?",(h,)).fetchone(): raise ValueError(f"unknown photo sha256: {h}")
   db.execute("INSERT INTO label_sources VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(sha256,model) DO UPDATE SET content=excluded.content,environment=excluded.environment,subjects=excluded.subjects,monochrome=excluded.monochrome,confidence=excluded.confidence,notes=excluded.notes,source=excluded.source",(h,x["model"],x["content"],x["environment"],json.dumps(x["subjects"],ensure_ascii=False),int(x["monochrome"]),x["confidence"],x["notes"],source))
  for h in sorted({x["sha256"] for x in records}):
   sources=db.execute("SELECT model,content,environment,subjects,monochrome,confidence,notes,source FROM label_sources WHERE sha256=? ORDER BY model",(h,)).fetchall()
   deterministic=db.execute("SELECT value,source FROM evidence WHERE sha256=? AND field=\"content\"",(h,)).fetchall()
   known={MAPPING.get(v,v) for v,s in deterministic if MAPPING.get(v,v) in CONTENT and v!="unknown"}
   db.execute("DELETE FROM conflicts WHERE sha256=? AND field IN (\"label_content\",\"label_environment\",\"label_monochrome\")",(h,))
   for model,content,env,subjects,mono,conf,notes,src in sources:
    for value,evsource in deterministic:
     mapped=MAPPING.get(value,value)
     if mapped in CONTENT and mapped!="unknown" and content!="unknown" and mapped!=content:
      db.execute("INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?)",(h,"label_content",mapped,evsource,content,src+"#"+model))
   for i,a in enumerate(sources):
    for b in sources[i+1:]:
     for idx,field in ((1,"label_content"),(2,"label_environment"),(4,"label_monochrome")):
      if a[idx]!=b[idx] and a[idx]!="unknown" and b[idx]!="unknown": db.execute("INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?)",(h,field,str(a[idx]),a[7]+"#"+a[0],str(b[idx]),b[7]+"#"+b[0]))
   def agreed(index,unknown):
    vals={a[index] for a in sources if a[index]!=unknown}
    return next(iter(vals)) if len(vals)==1 else unknown
   generated=agreed(1,"unknown"); content=next(iter(known)) if len(known)==1 else ("unknown" if known else generated)
   env=agreed(2,"unknown"); mono=agreed(4,None)
   subjects=sorted(set().union(*(set(json.loads(a[3])) for a in sources)))
   db.execute("INSERT OR REPLACE INTO labels VALUES(?,?,?,?,?,?,?,?)",(h,content,env,json.dumps(subjects),mono,min(a[5] for a in sources)," / ".join(a[0] for a in sources),"\n".join(a[6] for a in sources if a[6])))
  print("merged {} records for {} photos".format(len(records), len({x["sha256"] for x in records})))
 db.close()
if __name__=="__main__":
 try: main()
 except (ValueError, json.JSONDecodeError, sqlite3.Error, OSError) as e: print(f"merge failed: {e}",file=sys.stderr); sys.exit(1)
