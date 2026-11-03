import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
PRODUCT=ROOT/'firmware/engine_v54_g137/candidate/containers/product'
LOCAL=OUT/'local/native-events';LOCAL.mkdir(parents=True,exist_ok=True)
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v38-g137/native-events')
TEMP.mkdir(parents=True,exist_ok=True);os.environ['TMPDIR']=str(TEMP)
text=(PRODUCT/'ui_v2_data.c').read_text()
start=text.index('void __attribute__((noinline)) uv_window(')
end=text.index('\nconst uint8_t *uv_extension',start)
(LOCAL/'window_function.inc.c').write_text(text[start:end]+'\n')
program=LOCAL/'native-events'
sources=[str(PRODUCT/'kv2'/name) for name in ['kv_ui.c','kv_data.c','kv_math.c','kv_i64.c']]
command=['/usr/bin/clang','-std=c11','-O1','-g','-fsanitize=address,undefined',
         '-I'+str(PRODUCT),'-I'+str(PRODUCT/'kv2'),'-I'+str(LOCAL),
         str(OUT/'native_events.c'),*sources,'-o',str(program)]
subprocess.run(command,check=True)
result=json.loads(subprocess.check_output([str(program),str(ROOT/'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT')],text=True))
old=(ROOT/'firmware/engine_v53_g135/candidate/containers/product/kv2/kv_ui.c').read_text()
new=(PRODUCT/'kv2/kv_ui.c').read_text()
def native(text):
    a=text.index('int kv_ui_native_move(');b=text.index('\nstatic int open_value(',a);return text[a:b]
assert native(old)==native(new)
result['native_mapper_same_as_g135']=True
result['native_mapper_sha256']=hashlib.sha256(native(new).encode()).hexdigest()
result['dat_sha256']=hashlib.sha256((ROOT/'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT').read_bytes()).hexdigest()
(OUT/'evidence/native-events-resume.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
