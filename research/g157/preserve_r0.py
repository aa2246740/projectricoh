"""Keep the complete pre-formatting stage and its exact original diagnostic source."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.compute_gate('preserve-r0')
out=C.LOCAL/'stages/r0';assert not out.exists();out.mkdir(parents=True)
for dataset in ('control','model'):
    for profile in ('test','release'):
        item=C.artifact(profile,dataset);target=out/dataset/profile;target.mkdir(parents=True)
        shutil.copytree(item['build'],target/'build')
        shutil.copytree(item['package'],target/'package')
frozen=json.loads((C.LOCAL/'control-freeze.json').read_text())
s=(C.PRODUCT/'diagnostic.c').read_text()
s=s.replace('DF(1,failed,1,8,4),DF(4,record,12,1,1)','DF(1,failed,1,8,4),DF(1,record,10,2,1)')
s=s.replace('DF(4,stage,10,1,1)','DF(4,stage,10,2,1)')
s=s.replace('"G157B00R00","F00000000A--"','"G157B00R00A--","F00000000R00"').replace('"V00000000T0R0"','"V00000000T00"')
s=s.replace('''    if(!row){
        out[5]='0'+d->reason/10;out[6]='0'+d->reason%10;hex(out+8,eng_saved_code(),2);
    }else if(row==1){unsigned active=eng_active_code();
        if(!active&&eng_baseline())active=4;
        if(active)hex(out+10,active,2);
''','''    if(!row){unsigned active=eng_active_code();
        out[5]='0'+d->reason/10;out[6]='0'+d->reason%10;hex(out+8,eng_saved_code(),2);
        if(active)hex(out+11,active,2);
        else if(eng_baseline())pn_copy(out+11,"04",2);
''')
assert C.sha(s.encode())==frozen['source_C']['candidate/containers/product/diagnostic.c']
(out/'diagnostic.c').write_text(s)
C.save(out/'source-freeze.json',frozen)
C.save(out/'matrix-progress.json',json.loads((C.LOCAL/'cold.queue.progress.json').read_text()))
print('r0 control/model DATs and ELF files retained')
