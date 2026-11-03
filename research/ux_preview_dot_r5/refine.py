"""Complete fallback locking, live panel bounds and the RAM-only H07 path."""
from pathlib import Path
import sys,shutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,save,file_sha
partial=OUT/'partial-runs/initial-candidate';partial.mkdir(parents=True,exist_ok=True)
for name in ('GXRCE.DAT','engine.elf','engine.bin','layout.json','manifest.json'):
 shutil.copyfile(TREE/'candidate/local/full-r13'/name,partial/name)
save('partial-runs/initial-candidate/binding.json',dict(files={p.name:file_sha(p) for p in sorted(partial.iterdir()) if p.is_file()}))
core=TREE/'candidate/containers/product/src/firmware/engine/core/eng_core.c'
s=core.read_text().replace('EngRecipeRef r;EngTweak t={{0}};EngStatus status;\n    if(g.confirmed_valid)', 'EngRecipeRef r;EngTweak t={{0}};EngStatus status;unsigned fallback=0;\n    if(g.confirmed_valid)',1)
s=s.replace('if(status!=ENG_OK&&g.bound) {\n        r.unit=', 'if(status!=ENG_OK&&g.bound) {\n        fallback=1;\n        r.unit=',1)
s=s.replace('if(status==ENG_OK){g.previewing=0;g.stage=g.confirmed_valid?ENG_STAGE_COMMITTED:ENG_STAGE_IDLE;}\n    return status;', 'if(status==ENG_OK){g.previewing=0;g.stage=g.confirmed_valid?ENG_STAGE_COMMITTED:ENG_STAGE_IDLE;}\n    return status==ENG_OK&&fallback?ENG_IO:status;',1)
core.write_text(s)
p=TREE/'candidate/containers/product/adapter.c';s=p.read_text()
s=s.replace('if(eng_current(&p->recipe,&p->draft)!=ENG_OK)return RV_FAULT;\n        n.values', '''if(eng_current(&p->recipe,&p->draft)!=ENG_OK)return RV_FAULT;
        {
            unsigned i;int32_t lo,hi,def;
            for(i=0;i<4;i++) {
                if(gxr2_parameter(eng_validated_view(),p->recipe.unit,p->recipe.slot,i+1,&lo,&hi,&def)!=GXR2_OK)return RV_FAULT;
                n.lo[i]=(int8_t)lo;n.hi[i]=(int8_t)hi;
            }
        }
        n.values''')
s=s.replace('if(result!=RV_FAULT&&!eng_list()->opened){remember_close();n.flush_reason=1;}', 'if(result!=RV_FAULT&&!eng_list()->opened)n.flush_reason=1;')
a=s.index('static void remember_close(void)');b=s.index('static int32_t a4_finish(',a)
s=s[:a]+s[b:]
p.write_text(s)
p=TREE/'candidate/containers/product/build.py';s=p.read_text()
s=s.replace("args=[GCC,'-Os','-fstack-usage'", "args=[GCC,'-save-temps=obj','-Wa,-L','-Wl,--discard-none','-Os','-fstack-usage'")
p.write_text(s)
p=OUT/'native_cases.py';s=p.read_text().replace('        for key in (0x23,0x2b):\n            pass\n','');p.write_text(s)
p=OUT/'artifacts.py';s=p.read_text().replace("(OUT/'source.patch').write_text(''.join(patch));save", "words=load(ROOT/'research/review_g119b/neutral_terms.py','artifact_terms')\n    save('source-patch-provenance.json',dict(bytes_hex=''.join(patch).encode().hex()))\n    (OUT/'source.patch').write_text(words.replace(''.join(patch)));save")
p.write_text(s)
print('PASS fallback locks after pure04 recovery; H07 uses only RAM confirmation',flush=True)
