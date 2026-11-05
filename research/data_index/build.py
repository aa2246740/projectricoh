#!/opt/homebrew/bin/python3
"""Build a local index from read-only sources. Run with python -I under taskpolicy/nice."""
import ast, collections, csv, datetime, hashlib, io, json, os, re, sqlite3, struct, sys
from pathlib import Path
sys.dont_write_bytecode = True
assert sys.flags.isolated
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent/'local'
# The same bounded TIFF reader and MakerNote decoder used by library_28mm_r1.
ns={'io':io, 'struct':struct, '__builtins__':__builtins__}
source=ROOT/'research/recipe_redo_r1/inventory.py'
names={'TYPES','DISPLAY','SELECTORS','Tiff','jpeg_tiff','scalar','metadata'}
nodes=ast.parse(source.read_text()).body
selected=[n for n in nodes if (isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))]
exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),ns)
common=ROOT/'research/library_28mm_r1/local/common.py'
detail=next(n for n in ast.parse(common.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='details')
exec(compile(ast.Module(body=[detail],type_ignores=[]),str(common),'exec'),ns)
PARAMS=['contrast','sharpness','vividness']+[x+'_saturation' for x in ('orange','green','blue','red','magenta')]+[x+'_hue' for x in ('orange','green','blue','red','magenta')]
WB={0:'Auto',1:'Daylight',2:'Cloudy',3:'Tungsten',4:'Fluorescent',5:'Manual',7:'Detail',9:'Multi-pattern Auto'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def walk(base):
 if not base.exists(): return
 for root,dirs,files in os.walk(base,followlinks=False):
  dirs[:]=[d for d in dirs if d not in ('.git','node_modules','.venv') and not (Path(root)/d).is_symlink()]
  for name in files:
   p=Path(root)/name
   if not p.is_symlink(): yield p

def main():
 db=sqlite3.connect(OUT/'index.sqlite'); db.executescript('''
 CREATE TABLE IF NOT EXISTS photos(sha256 TEXT PRIMARY KEY, bytes INTEGER, format TEXT, exif_time TEXT, exif_time_trust TEXT, unit TEXT, focal_mm REAL, unit_maker TEXT, unit_conflict INTEGER, iso REAL, shutter_s REAL, aperture REAL, exposure_compensation REAL, wb_mode TEXT, wb_compensation TEXT, setting TEXT, parameters_json TEXT, maker_firmware TEXT, body_firmware TEXT, lens_firmware TEXT, dat TEXT, recipe TEXT, content TEXT, page TEXT);
 CREATE TABLE IF NOT EXISTS paths(sha256 TEXT, path TEXT UNIQUE, source TEXT, mtime TEXT);
 CREATE TABLE IF NOT EXISTS pairs(dng_sha256 TEXT, jpg_sha256 TEXT, basis TEXT, PRIMARY KEY(dng_sha256,jpg_sha256));
 CREATE TABLE IF NOT EXISTS uses(sha256 TEXT, research TEXT, evidence TEXT, PRIMARY KEY(sha256,research,evidence));
 CREATE TABLE IF NOT EXISTS evidence(sha256 TEXT, field TEXT, value TEXT, source TEXT, PRIMARY KEY(sha256,field,value,source));
 CREATE TABLE IF NOT EXISTS color_sources(sha256 TEXT, path TEXT UNIQUE, source TEXT, format TEXT, bytes INTEGER);
 CREATE TABLE IF NOT EXISTS errors(path TEXT, operation TEXT, error TEXT);
 ''')
 candidates={}
 bases=[(ROOT/'captures','captures'),(ROOT/'artifacts/card-b-archive-20261104','card_archive'),(Path('/Users/wu/Pictures/GXR-SD-backup-2026-10-13'),'backup'),(Path('/Users/wu/Pictures/GXR Studio/2026'),'studio')]
 for base,kind in bases:
  for p in walk(base):
   if p.suffix.lower() in ('.dng','.jpg','.jpeg','.png','.tif','.tiff'): candidates[str(p)]=kind
 for line in (OUT/'spotlight.txt').read_text().splitlines():
  p=Path(line)
  if p.is_absolute() and not str(p).startswith('/Volumes/') and p.suffix.lower() in ('.dng','.jpg','.jpeg','.tif','.tiff') and p.is_file() and not p.is_symlink(): candidates.setdefault(str(p),'spotlight')
 previous={row[0] for row in db.execute('SELECT path FROM paths')}
 if previous-set(candidates):
  raise RuntimeError('Previously indexed paths are missing; a fresh rebuild is required')
 print('photo paths',len(candidates),flush=True)
 bypath={}; meta={}; bystem=collections.defaultdict(list)
 for i,(s,kind) in enumerate(sorted(candidates.items())):
  p=Path(s)
  try:
   st=p.stat(); mtime=datetime.datetime.fromtimestamp(st.st_mtime,datetime.timezone.utc).isoformat()
   prior=db.execute('SELECT paths.sha256, paths.mtime, photos.bytes FROM paths JOIN photos USING(sha256) WHERE path=?',(s,)).fetchone()
   if prior and (prior[1]!=mtime or prior[2]!=st.st_size): raise RuntimeError('Previously indexed source changed; a fresh rebuild is required')
   digest=prior[0] if prior else sha(p); bypath[s]=digest
   db.execute('INSERT OR IGNORE INTO paths VALUES(?,?,?,?)',(digest,s,kind,mtime))
   bystem[(str(p.parent),p.stem.upper())].append((p,digest))
   if digest not in meta:
    try:
     m=ns['details'](p)
     # Exposure compensation is already selected by the reused EXIF reader; retrieve only its tag.
     with p.open('rb') as f:
      t=ns['jpeg_tiff'](f) if p.suffix.lower() in ('.jpg','.jpeg') else ns['Tiff'](f)
      root=t.ifd(t.root,only={34665}); ex=t.ifd(ns['scalar'](root,34665),only={37380}) if 34665 in root else {}
      m['ev']=ns['scalar'](ex,37380)
    except Exception as e:
     m={}; db.execute('INSERT INTO errors VALUES(?,?,?)',(s,'metadata',str(e)))
    focal=m.get('focal_mm'); unit='28mm' if focal==18.3 else '50mm' if focal==33.0 else 'MOUNT' if m.get('unit')=='mount-a12' else 'unknown'
    maker={'a12-28':'28mm','a12-50':'50mm','mount-a12':'MOUNT'}.get(m.get('unit'),'unknown')
    code=m.get('lens_unit_code'); maker={'RL5':'28mm','RL1':'50mm','RL8':'MOUNT'}.get(code,'unknown')
    conflict=int(unit!='unknown' and maker!='unknown' and unit!=maker)
    when=m.get('when'); trust='unknown' if not when else 'untrusted' if str(when)[:4] in ('2000','2009') else 'recorded'
    raw=m.get('color_raw13',[]); params=dict(zip(PARAMS,[ns['DISPLAY'].get(x) for x in raw])) if len(raw)==13 else None
    vals=(digest,st.st_size,p.suffix.lower().lstrip('.'),when,trust,unit,focal,maker,conflict,m.get('iso'),m.get('exposure'),m.get('aperture'),m.get('ev'),WB.get(m.get('wb_mode'),'unknown'),'unknown',m.get('selector_name','unknown'),json.dumps(params,ensure_ascii=False) if params else 'unknown',m.get('firmware') or 'unknown',m.get('body_firmware') or 'unknown',m.get('lens_firmware') or 'unknown','unknown','unknown','unknown','unknown')
    db.execute('INSERT OR IGNORE INTO photos VALUES('+','.join('?'*len(vals))+')',vals); meta[digest]=m
  except (OSError,ValueError) as e: db.execute('INSERT INTO errors VALUES(?,?,?)',(s,'read',str(e)))
  if i%200==0: print('scanned',i,'/',len(candidates),flush=True); db.commit()
 for group in bystem.values():
  for p,a in group:
   if p.suffix.lower()!='.dng': continue
   for q,b in group:
    if q.suffix.lower() not in ('.jpg','.jpeg'): continue
    x,y=meta[a],meta[b]; keys=('when','iso','exposure','selector','color_raw13')
    if all(x.get(k) is not None and x.get(k)==y.get(k) for k in keys): db.execute('INSERT OR IGNORE INTO pairs VALUES(?,?,?)',(a,b,'same directory and stem; matching EXIF and MakerNote'))
 # Noon intake is explicitly confirmed. Match stem and EXIF time to avoid unrelated reused names.
 intake=ROOT/'research/noon_sweep_r1/local/noon-20261104-r2/intake-confirmed.json'
 if intake.exists():
  data=json.loads(intake.read_text())
  for group in bystem.values():
   for p,h in group:
    frame=data.get('frames',{}).get(p.stem.upper())
    if frame and frame.get('exif',{}).get('time') and frame['exif']['time']==meta[h].get('when'):
     for field,value in [('content',frame.get('kind')),('page',frame.get('page')),('recipe',frame.get('setting'))]:
      if value and value!='unknown':
       db.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)',(h,field,str(value),str(intake)))
 # Explicit references to full paths or hashes, limited to manifests, inputs and SHA lists.
 hashset=set(meta); pathmap=bypath
 for study in (ROOT/'research').iterdir():
  if not study.is_dir() or study.name=='data_index': continue
  print('research',study.name,flush=True)
  for root,dirs,files in os.walk(study,followlinks=False):
   dirs[:]=[d for d in dirs if d not in ('.git','node_modules','.venv','raw_samples','calibration_samples','scratch') and not (Path(root)/d).is_symlink()]
   for name0 in files:
    name=name0.lower(); parts={x.lower() for x in Path(root).relative_to(study).parts}
    if not ('manifest' in name or name=='sha256sums' or 'inputs' in parts): continue
    p=Path(root)/name0
    if p.is_symlink(): continue
    scan_manifest(p,study,name,parts,db,hashset,pathmap)
  db.commit()
 for h,field,value in db.execute('SELECT sha256,field,MIN(value) FROM evidence GROUP BY sha256,field HAVING COUNT(DISTINCT value)=1').fetchall(): db.execute('UPDATE photos SET '+field+'=? WHERE sha256=?',(value,h))
 print('color sources',flush=True)
 downloads=Path('/Users/wu/Downloads')
 for base,kind in [(downloads,'Downloads'),(ROOT/'research/fotufilm_bake','fotufilm_bake'),(ROOT/'research/spektrafilm_bake','spektrafilm_bake')]:
  for p in walk(base):
   low=str(p).lower(); ext=p.suffix.lower()
   allowed=ext in ('.cube','.3dl','.csp','.look','.lut','.vlt','.zip','.7z','.tar','.tgz')
   named=any(x in low for x in ('lut','waiting ','eterna','leica-sl2-s','leica-sl2','fotufilm','spektrafilm'))
   if not allowed or not (named or ext in ('.cube','.3dl','.csp','.look','.lut','.vlt')): continue
   if kind!='Downloads' and not any(x in p.parts for x in ('local','artifacts')): continue
   try: db.execute('INSERT OR IGNORE INTO color_sources VALUES(?,?,?,?,?)',(sha(p),str(p),kind,ext.lstrip('.'),p.stat().st_size))
   except OSError as e: db.execute('INSERT INTO errors VALUES(?,?,?)',(str(p),'color',str(e)))
 db.commit()
 for table in ('photos','paths','pairs','uses','evidence','color_sources','errors'):
  cur=db.execute('SELECT * FROM '+table)
  with (OUT/(table+'.csv')).open('w',newline='',encoding='utf-8') as f:
   w=csv.writer(f); w.writerow([x[0] for x in cur.description]); w.writerows(cur)
 print('COMPLETE',flush=True)

def scan_manifest(p,study,name,parts,db,hashset,pathmap):
   name=p.name.lower()
   if p.suffix.lower() not in ('','.json','.csv','.tsv','.txt','.md','.sha256'): return
   try:
    if p.stat().st_size>30_000_000: return
    text=p.read_text(errors='replace')
    found=set(re.findall(r'(?i)\b[0-9a-f]{64}\b',text)) & hashset
    # Include literal absolute paths; avoid making assertions from bare filenames.
    for match in re.findall(r'(?:/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh|/Users/wu/Pictures)/[^\n\r"\t,]+',text):
     h=pathmap.get(match.strip())
     if h: found.add(h)
    for h in found: db.execute('INSERT OR IGNORE INTO uses VALUES(?,?,?)',(h,study.name,str(p)))
   except (OSError,UnicodeError) as e: db.execute('INSERT INTO errors VALUES(?,?,?)',(str(p),'evidence',str(e)))
if __name__=='__main__': main()
