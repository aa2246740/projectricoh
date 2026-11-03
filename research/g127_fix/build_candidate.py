#!/usr/bin/python3
"""Build and bind the generation 127 package to its compiled engine."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
ENGINE=ROOT/'firmware/engine_v48_own'
PACKAGE=ROOT/'firmware/package_v36_g127'
if '--reuse-build' not in sys.argv:
    subprocess.run(['/usr/bin/python3','-I','-B',str(ENGINE/'candidate/build127.py')],cwd=ROOT,check=True)
full=ENGINE/'candidate/local/full-r13'
raw=(full/'GXRCE.DAT').read_bytes()
assert int.from_bytes(raw[28:32],'big')==127
shutil.copy2(full/'GXRCE.DAT',PACKAGE/'local/SD_ROOT/GXRCE.DAT')
fixed=[]
for p in sorted((ROOT/'firmware/package_v36_g120b/SD_ROOT').rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(ROOT/'firmware/package_v36_g120b/SD_ROOT')
    if str(rel)=='GXRCE.DAT':continue
    target=PACKAGE/'local/SD_ROOT'/rel
    assert p.read_bytes()==target.read_bytes(),str(rel)
    fixed.append(str(rel))
assert len(fixed)==29
files=[p for p in (PACKAGE/'local/SD_ROOT').rglob('*') if p.is_file()]
assert len(files)==30
assert (full/'effective-rows.bin').read_bytes()==(ROOT/'firmware/engine_v47_fix/candidate/local/full-r13/effective-rows.bin').read_bytes()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={'generation':127,'dat_sha256':sha(PACKAGE/'local/SD_ROOT/GXRCE.DAT'),'file_bytes':len(raw),'fixed_files_equal_g120b':fixed,'files':len(files),'effective_rows_equal_g126':True,'engine_sha256':sha(full/'engine.bin'),'elf_sha256':sha(full/'engine.elf')}
(WORK/'evidence/package.json').write_text(json.dumps(result,indent=2)+'\n')
(PACKAGE/'CARD_SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(PACKAGE/'local/SD_ROOT'))+'\n' for p in sorted(files)))
print(json.dumps(result))
