#define main original_main
#include "../../firmware/lut_p0_timing/host_checks.c"
#undef main
#include "native-extra.h"
static const char *directory;
static void save_slot(const char *name,unsigned slot)
{
    char path[2048];FILE *f;CHECK(slot<5&&files[slot].exists&&files[slot].n==4096);
    CHECK(snprintf(path,sizeof(path),"%s/%s.BIN",directory,name)>0);
    f=fopen(path,"wb");CHECK(f);CHECK(fwrite(files[slot].bytes,1,4096,f)==4096&&!fclose(f));
}
static unsigned latest_slot(void)
{
    unsigned i,best=5;uint32_t gen=0;
    for(i=3;i<5;++i)if(files[i].exists&&files[i].n==4096&&rv_be32(files[i].bytes+16)>gen){best=i;gen=rv_be32(files[i].bytes+16);}
    CHECK(best<5);return best;
}
static void finish_run(void)
{
    unsigned i;admit_all();for(i=0;i<72;++i)hook(8,0,0,1);
    CHECK(p0_host_state()->phase==P0_DONE&&p0_host_state()->flush_ok);unchanged();
}
static void cursor_counterexample(void)
{
    unsigned cursor,exit_kind;
    for(cursor=8;cursor<=13;++cursor)for(exit_kind=0;exit_kind<3;++exit_kind){
        uint32_t regs[16]={0};RvSession *s;
        reset();CHECK(RV_BYTE(0x2022f71c)==0&&RV_BYTE(0x2022f56c+4)==13);
        regs[10]=cursor;native_instructions(extra_adj_cursor,sizeof(extra_adj_cursor),regs);
        CHECK(RV_BYTE(0x2022f725)==cursor&&RV_BYTE(0x2022f726)==cursor);
        CHECK(cursor<=RV_BYTE(0x2022f56c+4));
        enter();s=rv_session(&root);CHECK(s&&root.ui_restore[10]==1&&root.ui_restore[11]==1);
        if(exit_kind==0)hook(7,0x29,0x202bd890,0);
        else if(exit_kind==1){tick_value=p0_host_state()->reference_start+10000;hook(7,0x23,0x202c2d84,0);}
        else hook(6,0,0,1);
        CHECK(!root.ui_restore[0]&&RV_BYTE(0x2022f725)==1&&RV_BYTE(0x2022f726)==1);
        CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7);
        unchanged();
        printf("COUNTEREXAMPLE gen=%u prior_type=0 prior_rows=13 cursor=%u/%u exit=%s restored=1/1 exact=0\n",
               installed_generation,cursor,cursor,exit_kind==0?"MENU":exit_kind==1?"OK":"H06");
    }
}
static void lifecycle(void)
{
    static File kept[2];unsigned i;uint32_t generation;
    reset();enter();calibrate();finish_run();
    for(i=0;i<2;++i)kept[i]=files[3+i];generation=rv_be32(files[latest_slot()].bytes+16);
    reset();for(i=0;i<2;++i)files[3+i]=kept[i];
    tick_value=30000;enter();CHECK(p0_host_state()->phase==P0_REFERENCE);
    CHECK(rv_be32(files[latest_slot()].bytes+16)==generation);
    save_slot("new-reference-old-slot0",3);save_slot("new-reference-old-slot1",4);
    hook(7,0x29,0x202bd890,0);CHECK(p0_host_state()->error==7);
    save_slot("interrupted-newest-slot0",3);save_slot("interrupted-newest-slot1",4);
    CHECK(rv_be32(files[latest_slot()].bytes+16)==generation+1);
    printf("OBS completed generation=%u survives new REF without flush; MENU emits invalid generation=%u while old DONE remains\n",generation,generation+1);
    reset();tick_value=0xfffffff0u;enter();calibrate();finish_run();save_slot("wrapped-valid",latest_slot());
    for(i=0;i<3;++i){static const uint32_t delta[]={0,0x80000000u,0xfffffffcu};
        reset();enter();tick_value=p0_host_state()->reference_start+delta[i];hook(7,0x23,0x202c2d84,0);
        CHECK(p0_host_state()->error==5&&p0_host_state()->phase==P0_ERROR);
        save_slot(i==0?"reference-zero":i==1?"reference-half-wrap":"reference-reversed",latest_slot());unchanged();}
    printf("PASS single-wrap valid; zero/half-wrap/reversed reference rejects\n");
}
int main(int argc,char **argv)
{
    CHECK(argc==4);probe_bytes=read_file(argv[1],probe_raw);full_bytes=read_file(argv[2],full_raw);
    installed_generation=rv_be32(full_raw+28);directory=argv[3];
    cursor_counterexample();lifecycle();return 0;
}
