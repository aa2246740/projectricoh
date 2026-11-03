"""Measure P3 removal and H08 guards with the unchanged 200 B linker gate."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=module(HERE/'resident_builder.py','size_builder')
sys.path.insert(0,str(ROOT/'tools/native_harness'));from image_loader import Elf
out=HERE/'byte-accounting';out.mkdir(exist_ok=True)
base=(ROOT/'firmware/resident_v35/resident/hooks.c').read_text()
a=base.index('/* pack is gate');z=base.index('static void close_owned',a)
p3=base[:a]+'''static void __attribute__((noinline)) early(RvRoot *r,uint32_t hook,uint32_t *f)
{
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION)return;
    if(hook==7&&(r->flags&RF_PUBLISHED))f[1]=(uint32_t)(uintptr_t)rv_close_07;
}
'''+base[z:]
import re
p3=re.sub(r'early\(r,hook,f,[^;]*?\);','early(r,hook,f);',p3)
assert 'diag_early' not in p3 and 'pack' not in p3
records=[]; final=(ROOT/'firmware/resident_v36/resident/hooks.c').read_text()
for name,source in [('v35',base),('drop_p3',p3),('v36',final)]:
 dest=out/name;dest.mkdir(exist_ok=True);src=dest/'hooks.c';src.write_text(source);obj=dest/'hooks.o'
 b.run([b.GCC,*b.FLAGS,'-mmodel=medium','-I',b.HERE,'-c',src,'-o',obj],'measure-'+name+'-compile')
 hooks=json.loads((b.LOCAL/'hooks.json').read_text());enabled=[h for h in hooks if h['number'] not in set(range(10,38))]
 extra=[f'--defsym=rv_skip_target_{i:02}={t:#x}' for i,t in {1:0x202870a8,2:0x20287118,5:0x201febec,6:0x202be6a8,8:0x202bcf58}.items()]
 defs=[f'--defsym=rv_resume_{h["number"]:02}={int(h["replay_resume"],16):#x}' for h in enabled if h['number'] not in (3,4)]
 objects=[b.LOCAL/'build'/(Path(n).stem+'.o') for n in b.SOURCES]+[b.LOCAL/'build/trust.o',b.LOCAL/'build/linked_hooks.o']
 objects=[obj if o.name=='hooks.o' else o for o in objects]
 elf=dest/'resident.elf'
 b.run([b.LD,'--gc-sections','--no-undefined','--orphan-handling=error',*extra,*defs,'-T',b.HERE/'resident.ld',f'-Map={dest/"resident.map"}','-o',elf,*objects],'measure-'+name+'-link')
 e=Elf(elf);end=e.symbols['__resident_code_end'];payload=next(s for s in e.sections if s['name']=='.payload')['size']
 records.append(dict(name=name,payload=payload,code_end=hex(end),root_gap=0x20054700-end,under_limit=0x20054638-end))
print(json.dumps(records,indent=2));(out/'size.json').write_text(json.dumps(records,indent=2)+'\n')
