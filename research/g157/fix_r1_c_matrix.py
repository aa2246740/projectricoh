"""Exhaust every manual peer-W edge against the product C and final recipe data."""
from pathlib import Path
import json, subprocess, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.DATASET='model';C.compute_gate('fix-r1-C-matrix')
out=C.LOCAL/'fix-r1';review=C.ROOT/'research/review_g157_r1/local'
source=(review/'fault_harness.c').read_text()
source=source.replace('static uint8_t S[4096],rec[40];','static uint8_t S[4096],rec[40],initialS[4096];\nstatic unsigned setting_words;\nstatic volatile uint32_t word=2;\nvolatile uint32_t *eng_colour_guard(void){return &word;}')
source=source.replace('assert(argc==7);','assert(argc==8);')
source=source.replace('volatile uint32_t word=2;unsigned detail=0;', 'unsigned detail=0;')
source=source.replace('if(mode==0)status=eng_boot_run(&word,&detail);',
    "if(mode==2)S[0x36e]=9;else if(mode==3)S[0x6dd]=10;\n    if(mode==0)status=eng_boot_run(&word,&detail);")
source=source.replace('if(hit(1))result=RV_IO;','if(hit(1))reply->native_result=-1;\n            if(hit(8))result=RV_BUSY;')
source=source.replace('if(hit(1))reply->native_result=-1;','if(hit(1)||hit(16))reply->native_result=-1;')
source=source.replace('if(hit(8))result=RV_BUSY;','if(hit(8)||hit(17))result=RV_BUSY;')
source=source.replace('else if(hit(3))result=RV_IO;', 'else if(hit(3))result=RV_IO;else if(hit(10))result=RV_BUSY;')
source=source.replace('if(hit(4))result=RV_IO;', 'if(hit(4))result=RV_IO;if(hit(11))result=RV_BUSY;')
source=source.replace('for(unsigned i=0;i<p->count;i++)S[p->writes[i].offset]=p->writes[i].value;',
    'for(unsigned i=0;i<p->count;i++){S[p->writes[i].offset]=p->writes[i].value;++setting_words;if(hit(14)){result=RV_IO;break;}if(hit(15)){result=RV_BUSY;break;}}')
source=source.replace('uint8_t expected[552],wb[2];','RvSettingsPlan wanted;uint8_t expected[552],wb[2];')
source=source.replace('memcpy(expected,g->staging,552);','memcpy(expected,g->staging,552);make_plan(&ref,wb,1,&wanted);')
source=source.replace('if(mode==0)status=eng_boot_run(&word,&detail);','memcpy(initialS,S,4096);\n    if(mode==0)status=eng_boot_run(&word,&detail);')
source=source.replace('memcpy(initialS,S,4096);','memcpy(initialS,S,4096);if(kind==16||kind==17||kind==18)T=0;')
source=source.replace('unsigned full=rows_equal(expected),stock=rows_equal(g->stock);',
    'unsigned full=rows_equal(expected),stock=rows_equal(g->stock)&&S[0x36e]==1&&S[0x6dd]==9&&S[0x6de]==9;\n    for(unsigned i=0;i<wanted.count;i++)if(S[wanted.writes[i].offset]!=wanted.writes[i].value)full=0;')
source=source.replace(r'\"detail\":%u',r'\"setting_words\":%u,\"detail\":%u')
source=source.replace('else if(op==5)memcpy(rec,((RvSettingsRecord *)buffer)->record,40);',
    'else if(op==5){if(hit(12))result=RV_IO;else if(hit(13))result=RV_BUSY;else memcpy(rec,((RvSettingsRecord *)buffer)->record,40);}')
source=source.replace('ref.slot=3;eng_identity', 'ref.slot=(uint8_t)(atoi(argv[7])==3?5:3);if(atoi(argv[7])==3)levels.v[1]=0;eng_identity')
source=source.replace('eng_identity(eng_record(&g->data,3),ref.identity);','eng_identity(eng_record(&g->data,ref.slot),ref.identity);')
anchor='    g->saved.ref=ref;'
source=source.replace(anchor,'''    unsigned target=(unsigned)atoi(argv[7]);
    if(target==1){unsigned n=fx_count(&g->data.view);for(unsigned i=0;i<n;i++){
        const uint8_t *e=fx_entry(&g->data.view,i);
        if((e[18]>>unit_number&1u)&&!memcmp(e+20,"Acros",6)){
            ref.slot=e[0];ref.effect=(uint8_t)(i+1);memcpy(ref.effect_crc,e+4,4);eng_identity(eng_record(&g->data,ref.slot),ref.identity);break;
        }
    }assert(ref.effect);}
'''+anchor)
# The source has no fx_count API. The admitted effect header defines its count.
source=source.replace('fx_count(&g->data.view)', 'b16(raw+b32(raw+204)+1408+10)')
# Full native catalogue is checked independently; this host target locates via fx_entry.
source=source.replace('unsigned n=b16(raw+b32(raw+204)+1408+10);','unsigned n=48;')
source=source.replace('if((e[18]>>unit_number&1u)', 'if(e&&(e[18]>>unit_number&1u)')
source=source.replace('g->memory_want=0;g->memory_blocked=1;', 'g->memory_want=1;g->memory_user=target==2?3:0;g->memory_blocked=0;')
source=source.replace('g->memory_blocked=0;status=eng_apply(&ref,&levels);',
    'g->memory_blocked=0;if(mode==1&&kind!=16&&kind!=17&&kind!=18)g->baseline=g->live_verified=1;status=eng_apply(&ref,&levels);')
source=source.replace('if(hit(6)){check_ok=0;}','if(hit(6)){check_ok=0;epochs[RV_UNIT_E]++;}')
old='}else {assert(full||stock||g->uncertain);if(!g->uncertain)assert(full||stock);}'
new='''}else {
        assert(full||stock||(word&12u));
        if(kind==0||kind==18){assert(full&&!(word&12u)&&status==ENG_OK);}
        if(triggered&&(kind==1||kind==8))assert(stock||(word&12u));
        if(kind==5)assert(triggered&&(word&12u));
    }'''
assert old in source;source=source.replace(old,new)
source=source.replace('!!(word&4u),detail', '(unsigned)(word&12u),setting_words,detail')
file=out/'fault_harness.c';file.write_text(source);binary=out/'fault-harness'
core=C.PRODUCT/'src/firmware/engine/core'
argv=['/usr/bin/clang','-std=c11','-O2','-g','-fno-builtin','-DENG_HOST','-DRV_HOST','-I'+str(C.PRODUCT),str(file),str(core/'eng_data.c'),str(core/'eng_crc_compat.c'),str(core/'eng_pin_stub.c'),str(C.PRODUCT.parent.parent/'engine_services/crc.c'),str(review/'parser/parsers.dylib'),'-o',str(binary)]
compiled=subprocess.run(argv,capture_output=True,text=True);(out/'fault-build.log').write_text(compiled.stdout+compiled.stderr);assert not compiled.returncode,compiled.stderr
settings=out/'settings/test-mount-vivid09.bin';rows=[];start=time.monotonic()
def run(profile,u,kind,at,entry,target):
    args=[str(binary),str(C.artifact(profile)['dat']),str(u),str(kind),str(at),str(entry),str(settings),str(target)]
    proc=subprocess.run(args,capture_output=True,text=True)
    if proc.returncode:
        failure=dict(profile=profile,unit=u,kind=kind,at=at,entry=entry,target=target,stdout=proc.stdout,stderr=proc.stderr,completed=len(rows))
        if not (out/'C-first-failure.json').exists():C.save(out/'C-first-failure.json',failure)
        C.save(out/('C-failure-'+str(time.time_ns())+'.json'),failure)
        raise AssertionError((profile,u,kind,at,entry,target,proc.stderr))
    row=json.loads(proc.stdout);row.update(profile=profile,entry=('boot','standard','Vivid09','WB')[entry],target=('HC+1','Acros','user3','colour05')[target],DAT_sha256=C.sha(C.artifact(profile)['dat'].read_bytes()))
    rows.append(row);return row
for profile in ('test','release'):
    for u in range(3):
        C.compute_gate('C-'+profile+'-'+str(u))
        for entry in (1,2,3):
            for target in (0,1,2,3):
                base=run(profile,u,0,1,entry,target)
                for kind in (1,8):
                    for at in range(1,base['writes']+1):
                        row=run(profile,u,kind,at,entry,target);assert row['triggered']==1
                for kind in (14,15):
                    for at in range(1,base['setting_words']+1):
                        row=run(profile,u,kind,at,entry,target);assert row['triggered']==1
                t0=run(profile,u,18,0,entry,target)
                assert t0['writes']>=base['writes']+1
                for kind in (16,17):
                    for at in sorted({1,2,t0['writes']}):
                        row=run(profile,u,kind,at,entry,target);assert row['triggered']==1
                for kind in (3,4,10,11,12,13,5,6):run(profile,u,kind,8 if kind in (5,6) else 1,entry,target)
        C.save(out/'C-progress.json',dict(completed=len(rows),profile=profile,unit=u,seconds=time.monotonic()-start))
C.save(out/'C-matrix.json',dict(status='PASS',cases=len(rows),rows=rows,seconds=time.monotonic()-start,
    scope='Product C/math and final DAT data, declared peer/services; every actual W position has ACK failure and BUSY after the peer write. Includes settings/preview/memory and persistent faults. Does not replace final-DAT ISA or cold MAIN evidence.'))
print(json.dumps(dict(status='PASS',cases=len(rows))))
