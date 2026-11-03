/* Independent assertions over public resident hooks and frozen engine C.
 * Native file/UI/RPC/heap calls are host doubles, not camera execution. */
#include "local/attack_support.c"
#include "local/native_enum.h"
#include "local/native_get_mode.h"

static void preserve_s_reboot(void)
{
    uint8_t keep[0x1000];memcpy(keep,RV_PTR(0x20500000),sizeof(keep));
    reboot();memcpy(RV_PTR(0x20500000),keep,sizeof(keep));
}
static unsigned parent_entry(void)
{
    uint32_t a[32]={0},b[32]={0},draw[32]={0};unsigned mode,row;
    RV_BYTE(RV_NATIVE_VIEWS)=32;RV_WORD(RV_NATIVE_VIEWS+4)=0x2022f71c;RV_BYTE(0x205a27d4)=1;
    a[15]=99;rv_hook_observe(&root,1,a);CHECK(root.state==RV_READY&&!a[1]&&a[15]==99);
    mode=native_s_modes[RV_BYTE(0x2050036e)];RV_BYTE(0x2050036e)=mode;
    b[7]=mode;rv_hook_observe(&root,2,b);CHECK(!b[1]&&b[7]==mode);
    row=native_mode_rows[mode];RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=row;
    RV_BYTE(RV_NATIVE_VIEWS+8)=33;RV_WORD(RV_NATIVE_VIEWS+12)=0x2022f71c;RV_BYTE(0x205a27d4)=2;
    rv_hook_observe(&root,5,draw);CHECK(draw[1]==(uint32_t)(uintptr_t)rv_skip_05);
    return row;
}
static void s_plan_check(unsigned slot,const uint8_t before[0x1000])
{
    uint8_t want[0x1000];memcpy(want,before,sizeof(want));
    want[0x36e]=slot==3?3:1;want[0x6dd]=want[0x6de]=9;
    if(slot==3){want[0x645]=3;want[0x646]=4;}
    CHECK(!memcmp(want,RV_PTR(0x20500000),sizeof(want)));
}
static void reflexive(unsigned slot,unsigned action)
{
    uint32_t gen;unsigned row,memory;
    installed();select_slot(slot);close_key(0);CHECK(expected_record(&gen)==slot&&gen==1);
    preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);row=parent_entry();current_slot(slot,0);
    CHECK(row==(slot==3?4:2));
    last_object=1;tracing=1;memset(counts,0,sizeof(counts));
    if(action==2){panel_open();close_key(0);}else close_key(action==1);
    tracing=0;memory=expected_record(&gen);
    CHECK(memory==(action?row:slot));CHECK(gen==(unsigned)(action&&row!=slot?2:1));
    CHECK(counts[3]==(unsigned)(action&&row!=slot)&&counts[7]==counts[3]);
    preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();current_slot(memory,0);
    printf("REFLEXIVE prior=%u highlight=%u action=%s persisted=%u generation=%u creates=%u renames=%u cold_slot=%u\n",slot,row,action==0?"MENU":action==1?"OK":"Fn2_MENU",memory,gen,counts[3],counts[7],memory);
    if(action&&row!=slot)puts("COUNTEREXAMPLE inherited_highlight_newly_changes_persistent_last_recipe");
}
static void power(unsigned slot,unsigned closed)
{
    uint8_t before[0x1000],committed[410],after[410];unsigned same;
    installed();memcpy(before,RV_PTR(0x20500000),sizeof(before));select_slot(slot);s_plan_check(slot,before);actual_rows(committed);
    if(closed)close_key(0);
    preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);CHECK(!has_current());menu();actual_rows(after);
    if(closed){current_slot(slot,0);CHECK(!memcmp(committed,after,sizeof(after)));}
    else{CHECK(!has_current());matches_stock();CHECK(RV_BYTE(0x2050036e)==(slot==3?3:1));}
    same=!memcmp(committed,after,sizeof(after));
    CHECK(RV_BYTE(0x205006dd)==9&&RV_BYTE(0x205006de)==9);
    printf("POWER slot=%u GXLS_closed=%u rows_equal_committed=%u native_S=%u WB=%u,%u BW_params=%u,%u classification=%s\n",slot,closed,same,RV_BYTE(0x2050036e),RV_BYTE(0x205006dd),RV_BYTE(0x205006de),RV_BYTE(0x20500645),RV_BYTE(0x20500646),closed?"full_remembered":slot==3?"accepted_03_BW_residue":"pure_04");
}
static void deferred(unsigned prior,unsigned next)
{
    uint8_t before[0x1000],want[410],after[410];uint32_t gen;
    installed();select_slot(prior);close_key(0);menu();actual_rows(want);
    memcpy(before,RV_PTR(0x20500000),sizeof(before));select_slot(next);s_plan_check(next,before);
    CHECK(expected_record(&gen)==prior&&gen==1);
    preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();current_slot(prior,0);actual_rows(after);
    CHECK(!memcmp(want,after,sizeof(want)));
    CHECK(RV_BYTE(0x2050036e)==(prior==3?3:1)&&RV_BYTE(0x205006dd)==9&&RV_BYTE(0x205006de)==9);
    printf("DEFERRED prior=%u unclosed=%u cold=%u full_prior=1 changed_last_lost=%u latent_BW=%u,%u\n",prior,next,prior,prior!=next,RV_BYTE(0x20500645),RV_BYTE(0x20500646));
}
static void followup(void)
{
    CHECK(root.state==RV_READY&&!(root.flags&(RF_UNCERTAIN|RF_STOP))&&!eng_uncertain());
    menu();select_slot(5);panel_open();select_slot(9);close_key(1);
    CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);current_slot(5,3);
    menu();select_slot(5);current_slot(5,3);select_slot(6);panel_open();close_key(0);
    CHECK(root.state==RV_READY&&ig_host_last_store()==RV_OK);current_slot(6,0);
    preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();current_slot(6,0);
    CHECK(!(root.flags&RF_UNCERTAIN));puts("FOLLOWUP_PASS preview_same_other_Fn2_GXTS_close_reopen_cold=1");
}
static void read_fault(unsigned op,unsigned ordinal,int code,unsigned corrupt)
{
    unsigned i;
    installed();select_slot(5);close_key(0);preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
    last_object=1;tracing=1;memset(counts,0,sizeof(counts));
    injected_op=ordinal?op:0;injected_at=ordinal;injected_code=code;r7_corrupt_read=(int)corrupt;
    menu();tracing=0;r7_corrupt_read=0;if(ordinal)CHECK(injected);
    if(!ordinal){printf("LOAD_TRACE");for(i=2;i<=8;++i)printf(" op%u=%u",i,counts[i]);puts("");}
    CHECK(!(root.flags&RF_UNCERTAIN)&&root.state==RV_READY);
    printf("READ_RESULT op=%u ordinal=%u raw=%d corrupt=%u has_current=%d last_status=%d flags=%u\n",op,ordinal,code,corrupt,has_current(),ig_host_last_store(),root.flags);
    followup();
}
static void save_fault(unsigned op,unsigned ordinal,int code,unsigned effect)
{
    char tmp[32];uint32_t gen;
    installed();select_slot(1);close_key(0);menu();select_slot(2);close_key(0);menu();select_slot(5);
    path_for(tmp,1,0,2);put_file(tmp,(const uint8_t *)"stale",5);
    last_object=1;tracing=1;memset(counts,0,sizeof(counts));injected_op=op;injected_at=ordinal;injected_code=code;
    r7_side_effect=(int)effect;close_key(0);tracing=0;r7_side_effect=0;
    CHECK(injected&&root.state==RV_READY&&!(root.flags&RF_UNCERTAIN));current_slot(5,0);matches_recipe(new_raw,5,new_golden);
    printf("SAVE_RESULT op=%u raw=%d takes_effect_before_error=%u last_status=%d formal_slot=%u flags=%u\n",op,code,effect,ig_host_last_store(),expected_record(&gen),root.flags);
    followup();
}
static unsigned during_stage,during_hook,during_hits;
static void during(unsigned op,const char *path)
{
    uint32_t f[32]={0},serial;
    if(op!=during_stage||strncmp(path,"/IROM/L",7))return;
    native_observer=0;++during_hits;serial=root.entry_serial;
    CHECK(root.inflight&&(root.flags&RF_OWNER));f[16]=0x202b8d9c;
    rv_hook_observe(&root,during_hook,f);
    CHECK(!f[1]&&root.entry_serial==serial&&root.state==RV_READY);
}
static void reentry(unsigned stage,unsigned hook)
{
    uint32_t f[32]={0};uint8_t committed[410],after[410];
    installed();save_cont(5,2);menu();select_slot(6);actual_rows(committed);panel_open();select_slot(9);
    during_stage=stage;during_hook=hook;during_hits=0;native_observer=during;
    last_object=1;tracing=1;memset(counts,0,sizeof(counts));f[16]=0x202b8d9c;rv_hook_observe(&root,7,f);
    native_observer=0;tracing=0;CHECK(during_hits==1&&counts[3]==1&&counts[7]==1);
    CHECK(f[1]==(uint32_t)(uintptr_t)rv_close_07&&root.state==RV_READY&&!eng_list()->opened&&!ig_host_panel()->open);
    current_slot(6,0);actual_rows(after);CHECK(!memcmp(committed,after,sizeof(after)));
    CHECK(!(root.flags&(RF_OWNER|RF_UNCERTAIN))&&opens==closes);
    memset(f,0,sizeof(f));rv_hook_observe(&root,7,f);CHECK(!f[1]);
    preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();current_slot(6,0);
    printf("REENTRY_PASS stage=%u nested_hook=%u entries=0 one_save=1 committed_look_restored=1 cold_slot=6\n",stage,hook);
}
/* Capture only preference files at each operation boundary. This models a
 * restart from a file image, not filesystem durability or a physical cut. */
typedef struct {unsigned exists,length;uint8_t bytes[256];} SmallFile;
typedef struct {SmallFile f[3];unsigned op;} Crash;
static Crash images[128];static unsigned image_count;
static void capture(unsigned op,const char *path)
{
    unsigned j;char p[32];File *f;Crash *x;
    if(strncmp(path,"/IROM/L",7))return;CHECK(image_count<128);x=&images[image_count++];x->op=op;
    for(j=0;j<3;++j){path_for(p,1,0,j);f=file(p);x->f[j].exists=f!=0;x->f[j].length=f?f->length:0;
        CHECK(x->f[j].length<=256);if(f)memcpy(x->f[j].bytes,f->bytes,f->length);}
}
static void crash_snapshots(void)
{
    unsigned i,j,expected;uint32_t gen;char path[32];
    installed();select_slot(1);close_key(0);menu();select_slot(2);close_key(0);menu();select_slot(5);
    image_count=0;native_observer=capture;close_key(0);native_observer=0;
    memcpy(durable_before,files,sizeof(files));CHECK(image_count>20);
    for(i=0;i<image_count;++i){
        memcpy(files,durable_before,sizeof(files));
        for(j=0;j<3;++j){File *f;path_for(path,1,0,j);f=file(path);if(f)f->exists=0;
            if(images[i].f[j].exists)put_file(path,images[i].f[j].bytes,images[i].f[j].length);}
        expected=expected_record(&gen);CHECK(expected==2||expected==5);
        preserve_s_reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();current_slot(expected,0);matches_recipe(new_raw,expected,new_golden);
        CHECK(root.state==RV_READY&&!(root.flags&RF_UNCERTAIN));
        printf("CRASH_IMAGE index=%u op=%u expected=%u generation=%u exact_cold_recipe=1\n",i,images[i].op,expected,gen);
    }
    printf("CRASH_PASS images=%u TMP_never_loaded=1 old_or_new_formal_full_recipe=1\n",image_count);
}
static void older_explicit_save(void)
{
    unsigned before;installed();save_cont(5,2);
    put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);reboot();
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==be32(base_raw+28));
    menu();CHECK(ig_host_install_status()==RV_CONFLICT);select_slot(5);panel_open();select_slot(9);
    before=writes;last_object=0;tracing=1;memset(counts,0,sizeof(counts));close_key(1);tracing=0;
    CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);current_slot(5,3);
    CHECK(counts[3]==1&&counts[7]==1&&writes>before);
    printf("OLD_DAT_EXPLICIT_GXTS generation=%u creates=%u writes=%u renames=%u memory_status=%d engine_ready=1\n",session()->generation,counts[3],counts[5],counts[7],ig_host_last_store());
    file("/ATA1/GXRCE.DAT")->exists=0;cold109();current_slot(5,3);
    puts("OLD_DAT_EXPLICIT_SAVE persists_after_returning_to_109=1 all_interactions_zero_writes_is_false=1");
}
int main(int argc,char **argv)
{
    uint8_t wire[232];unsigned i,policy;
    CHECK(argc>=9);scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit<3);
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    CHECK(load_file(argv[5],wire,sizeof(wire))==232&&load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,wire+8,32);memcpy(trust.resident_build_id,wire+40,32);memcpy(trust.resident_abi_id,wire+72,16);
    for(i=0;i<3;++i){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(wire+100+48*i);memcpy(trust.modules[i].stock_sha256,wire+104+48*i,32);}
    policy=(unsigned)strtoul(argv[8],0,10);rename_refuse_existing=policy;reboot();CHECK(unit!=1);
    if(!strcmp(scenario,"reflexive")){CHECK(argc==11);reflexive((unsigned)atoi(argv[9]),(unsigned)atoi(argv[10]));}
    else if(!strcmp(scenario,"power")){CHECK(argc==11);power((unsigned)atoi(argv[9]),(unsigned)atoi(argv[10]));}
    else if(!strcmp(scenario,"deferred")){CHECK(argc==11);deferred((unsigned)atoi(argv[9]),(unsigned)atoi(argv[10]));}
    else if(!strcmp(scenario,"read-fault")){CHECK(argc==13);read_fault((unsigned)atoi(argv[9]),(unsigned)atoi(argv[10]),atoi(argv[11]),(unsigned)atoi(argv[12]));}
    else if(!strcmp(scenario,"save-fault")){CHECK(argc==13);save_fault((unsigned)atoi(argv[9]),(unsigned)atoi(argv[10]),atoi(argv[11]),(unsigned)atoi(argv[12]));}
    else if(!strcmp(scenario,"reentry")){CHECK(argc==11);reentry((unsigned)atoi(argv[9]),(unsigned)atoi(argv[10]));}
    else if(!strcmp(scenario,"crash-snapshots"))crash_snapshots();
    else if(!strcmp(scenario,"older-explicit-save"))older_explicit_save();
    else CHECK(0);
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    printf("OK scenario=%s unit=%u assertions=%u policy=%u\n",scenario,unit,assertions,policy);return 0;
}
