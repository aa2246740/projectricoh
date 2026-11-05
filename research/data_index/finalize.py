#!/opt/homebrew/bin/python3
"""Add explicit per-frame research identifications and export the private index."""
import collections, csv, hashlib, json, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; LOCAL=Path(__file__).resolve().parent/'local'
db=sqlite3.connect(LOCAL/'index.sqlite')
db.execute('CREATE TABLE IF NOT EXISTS archived_files (sha256 TEXT, path TEXT UNIQUE, format TEXT, bytes INTEGER)')
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
for p in (ROOT/'artifacts/card-b-archive-20261104/root').iterdir():
 if p.is_file() and not p.is_symlink(): db.execute('INSERT OR IGNORE INTO archived_files VALUES(?,?,?,?)',(digest(p),str(p),p.suffix.lower().lstrip('.'),p.stat().st_size))
# A manifest's skip is an instruction, not a content class.
db.execute("DELETE FROM evidence WHERE field='content' AND value='skip'")
db.execute("UPDATE photos SET content='unknown' WHERE content='skip'")
# Classification records explicitly enumerate files used by this research.
lib=ROOT/'research/library_28mm_r1/local/classification.csv'
with lib.open(newline='') as f:
 for row in csv.DictReader(f):
  h=row['sha256']
  for (x,) in db.execute('SELECT ? UNION SELECT jpg_sha256 FROM pairs WHERE dng_sha256=?',(h,h)).fetchall():
   if db.execute('SELECT 1 FROM photos WHERE sha256=?',(x,)).fetchone():
    db.execute('INSERT OR IGNORE INTO uses VALUES(?,?,?)',(x,'library_28mm_r1',str(lib)))
# Per-photo accepted record identities, including equivalent DAT catalogues, not guesses from filenames.
hist=ROOT/'research/bluecyan_r1/local/history/identities.json'
for row in json.loads(hist.read_text()):
 ident=row.get('identity') or {}; record=ident.get('record') or {}
 for key in ('raw_sha256','jpeg_sha256'):
  h=row.get(key)
  if not h or not db.execute('SELECT 1 FROM photos WHERE sha256=?',(h,)).fetchone(): continue
  db.execute('INSERT OR IGNORE INTO uses VALUES(?,?,?)',(h,'bluecyan_r1',str(hist)))
  if ident.get('accepted'):
   labels=record.get('labels') or []
   if labels: db.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)',(h,'recipe',' / '.join(sorted(labels)),str(hist)))
   cats=record.get('catalogs') or []
   if len({c.get('sha256') for c in cats})==1 and cats:
    db.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)',(h,'dat',cats[0]['name']+' sha256:'+cats[0]['sha256'],str(hist)))
# The bluecyan report binds the confirmed noon screen and physical frames to this DAT.
report=ROOT/'research/bluecyan_r1/REPORT.md'
for (h,) in db.execute("SELECT DISTINCT sha256 FROM evidence WHERE field='content' AND value IN ('screen','physical')").fetchall():
 db.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)',(h,'dat','g156 test sha256:0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7',str(report)))
 db.execute('INSERT OR IGNORE INTO uses VALUES(?,?,?)',(h,'bluecyan_r1',str(report)))
for study, rel in [
 ('probe_pack_r1','local/field_20261103/inputs.json'),
 ('probe_pack_r1','local/bracket_20261103/inputs.json'),
 ('probe_pack_r2','local/field_probe2_20261103/inputs.json'),
 ('probe_pack_r3','field/local/inputs.json'),
]:
 source=ROOT/'research'/study/rel
 natural_names=set()
 if rel=='local/field_20261103/inputs.json':
  natural_names={r['frame'] for r in json.loads((source.parent/'natural_identity.json').read_text())['frames'] if r.get('role')=='natural_scene_identity_only'}
 for item in json.loads(source.read_text()).get('files',[]):
  if Path(item.get('file','')).stem.upper() in natural_names: continue
  h=item.get('sha256')
  if not h or not db.execute('SELECT 1 FROM photos WHERE sha256=?',(h,)).fetchone(): continue
  db.execute('INSERT OR IGNORE INTO uses VALUES(?,?,?)',(h,study,str(source)))
  db.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)',(h,'content','probe',str(source)))
for field in ('dat','recipe','content','page'):
 for h,value,n in db.execute('SELECT sha256,MIN(value),COUNT(DISTINCT value) FROM evidence WHERE field=? GROUP BY sha256',(field,)).fetchall():
  db.execute('UPDATE photos SET '+field+'=? WHERE sha256=?',(value if n==1 else 'unknown',h))
# Repeated runs must not inflate the error ledger.
db.execute('DELETE FROM errors WHERE rowid NOT IN (SELECT MIN(rowid) FROM errors GROUP BY path,operation,error)')
db.commit()
for table in ('photos','paths','pairs','uses','evidence','color_sources','archived_files','errors'):
 cur=db.execute('SELECT * FROM '+table)
 with (LOCAL/(table+'.csv')).open('w',newline='',encoding='utf8') as f:
  w=csv.writer(f);w.writerow([x[0] for x in cur.description]);w.writerows(cur)
print('COUNTS',db.execute('SELECT (SELECT COUNT(*) FROM photos),(SELECT COUNT(*) FROM pairs),(SELECT COUNT(*) FROM color_sources),(SELECT COUNT(*) FROM paths),(SELECT COUNT(*) FROM archived_files)').fetchone())
for col in ('unit','setting','content'):
 print(col,db.execute('SELECT '+col+',COUNT(*) FROM photos GROUP BY 1 ORDER BY 1').fetchall())
print('sources',db.execute('SELECT source,COUNT(*),COUNT(DISTINCT sha256) FROM paths GROUP BY 1').fetchall())
print('unknown',db.execute('SELECT SUM(unit="unknown"),SUM(setting="unknown"),SUM(wb_mode="unknown"),SUM(wb_compensation="unknown"),SUM(dat="unknown"),SUM(recipe="unknown"),SUM(content="unknown"),SUM(page="unknown"),SUM(exif_time IS NULL),SUM(exif_time_trust="untrusted"),SUM(unit_conflict) FROM photos').fetchone())
print('errors',db.execute('SELECT operation,COUNT(*) FROM errors GROUP BY 1').fetchall())
print('unpaired',db.execute('SELECT format,COUNT(*) FROM photos p WHERE format IN ("dng","jpg","jpeg") AND NOT EXISTS(SELECT 1 FROM pairs WHERE dng_sha256=p.sha256 OR jpg_sha256=p.sha256) GROUP BY format').fetchall())
print('research',db.execute('SELECT research,COUNT(DISTINCT sha256) FROM uses WHERE research IN ("library_28mm_r1","bluecyan_r1","noon_sweep_r1") GROUP BY 1').fetchall())
print('check',db.execute('PRAGMA integrity_check').fetchone()[0])
