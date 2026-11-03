/* Independent public-entry assertions over frozen product/resident C.
 * Native file, allocator, UI and RPC boundaries use the inspected fixture. */
#include "local/review_support.c"
#include "local/native_enum.h"

static void parent_menu(int remembered)
{
    uint32_t first[32]={0},second[32]={0};unsigned mode,row;
    installed();CHECK(unit!=1);
    if(remembered)save_cont(3,2);
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
    /* Native Image Settings constructs its tag 33 only at 0x202871A4,
     * after both H01 and H02. UI_LIST accepts a parent tag at H01. */
    RV_BYTE(RV_NATIVE_VIEWS)=32;first[15]=99;
    rv_hook_observe(&root,1,first);
    CHECK(root.state==RV_READY&&RV_BYTE(0x2022f5ac)==8);
    CHECK(!first[1]&&first[15]==99);
    if(remembered)current_slot(3,2);else CHECK(!has_current());
    mode=RV_BYTE(0x2050036e);CHECK(mode<11);
    second[7]=mode;rv_hook_observe(&root,2,second);
    CHECK(!second[1]&&second[7]==mode);
    /* Projection of the byte-executed native enum and its literal stores at
     * 0x20287158/164. Other native callees are not executed here. */
    row=native_mode_rows[mode];
    RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=row;
    RV_BYTE(RV_NATIVE_VIEWS)=33;
    printf("PARENT_MENU remembered=%d S_mode=%u engine_cursor=%u native_cursor=%u engine_recipe=%u H01_skip=0 H02_skip=0\n",
        remembered,mode,eng_list()->cursor,row,remembered?3:0);
    CHECK(row!=eng_list()->cursor);
    if(remembered)CHECK(row==4&&eng_list()->cursor==3);
    else CHECK(row==2&&eng_list()->cursor==1);
    panel_open();current_slot(row,0);
    printf("FN2 changed_to_slot=%u S_mode=%u\n",row,RV_BYTE(0x2050036e));
    puts("COUNTEREXAMPLE native_initialization_overwrites_recipe_cursor_before_tag33");
}

static void preference_poison(unsigned op,int follow_panel)
{
    uint32_t frame[32]={0};unsigned flags,writes_before;int32_t saved_status;
    installed();CHECK(unit!=1);
    last_object=1;tracing=1;injected_op=op;injected_at=1;injected_code=-1;
    memset(counts,0,sizeof(counts));select_slot(5);tracing=0;
    CHECK(injected);saved_status=ig_host_last_store();flags=root.flags;
    current_slot(5,0);matches_recipe(new_raw,5,new_golden);
    CHECK(root.state==RV_READY&&saved_status!=RV_OK&&(flags&RF_UNCERTAIN));
    printf("AFTER_PREFERENCE_FAILURE op=%u last_store=%d state=%u flags=%u committed_slot=5\n",op,saved_status,root.state,flags);
    writes_before=rpc_w;
    if(follow_panel)rv_hook_observe(&root,6,frame);
    else {RV_BYTE(0x2022f726)=5;rv_hook_observe(&root,8,frame);}
    printf("FOLLOWUP action=%s state=%u flags=%u rpc_w_delta=%u engine_uncertain=%d panel_open=%u native_rows=%u\n",
           follow_panel?"Fn2":"same-row",root.state,root.flags,rpc_w-writes_before,eng_uncertain(),ig_host_panel()->open,RV_BYTE(0x2022f5ac));
    CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&RV_BYTE(0x2022f5ac)==7);
    CHECK(rpc_w==writes_before&&!eng_uncertain());
    puts("COUNTEREXAMPLE preference_IO_uncertainty_disables_next_unchanged_apply");
}

static void same_boot_swap(unsigned target)
{
    uint32_t frame[32]={0};unsigned before;
    installed();CHECK(unit==0);select_slot(5);before=rpc_w;
    unit=target;
    memcpy(RV_PTR(0x2040f81c),units[unit].name,8);
    RV_BYTE(0x2040f848)=1;RV_BYTE(0x2040f849)=0x51;
    rv_hook_observe(&root,1,frame);
    printf("UNIT_SWAP target=%u root_state=%u check_failure=%u native_rows=%u rpc_w_delta=%u\n",target,root.state,root.check_failure,RV_BYTE(0x2022f5ac),rpc_w-before);
    CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&root.check_failure==RV_CHECK_UNIT);
    CHECK(RV_BYTE(0x2022f5ac)==7&&rpc_w==before);
    puts("LIMITATION resident_retires_on_unit_change_no_rebind_or_auto_apply");
}

static void valid_survivor(unsigned layout)
{
    char a[32],b[32];uint8_t keep[GXTS_BYTES];File *f;
    installed();CHECK(unit!=1);select_slot(5);
    seed_tweak(new_raw,new_bytes,5,layout==2?2:1,2);
    path_for(a,0,5,0);path_for(b,0,5,1);
    if(layout==1) {f=file(a);put_file(b,f->bytes,f->length);f->bytes[20]^=1;}
    f=file(layout?b:a);CHECK(f&&f->length==GXTS_BYTES);memcpy(keep,f->bytes,GXTS_BYTES);
    cold108();current_slot(5,2);
    save_cont(5,3);
    f=file(layout?b:a);CHECK(f&&!memcmp(f->bytes,keep,GXTS_BYTES));
    cold108();current_slot(5,3);
    puts("PASS selected_valid_copy_preserved_and_new_tweak_cold_loaded");
}

static void write_frequency(void)
{
    unsigned i;installed();CHECK(unit!=1);
    last_object=1;tracing=1;memset(counts,0,sizeof(counts));
    for(i=1;i<=8;++i)select_slot(i);
    for(i=7;i>=1;--i)select_slot(i);
    tracing=0;
    printf("FLASH_FREQUENCY transitions=15 creates=%u writes=%u renames=%u deletes=%u confirmed_saves=0\n",counts[3],counts[5],counts[7],counts[8]);
    CHECK(counts[3]==15&&counts[7]==15);
}

int main(int argc,char **argv)
{
    uint8_t wire[232];unsigned i,policy;
    CHECK(argc==9);scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit<3);
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    CHECK(load_file(argv[5],wire,sizeof(wire))==232&&load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,wire+8,32);memcpy(trust.resident_build_id,wire+40,32);memcpy(trust.resident_abi_id,wire+72,16);
    for(i=0;i<3;++i){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(wire+100+48*i);memcpy(trust.modules[i].stock_sha256,wire+104+48*i,32);}
    policy=(unsigned)strtoul(argv[8],0,10);rename_refuse_existing=policy;reboot();
    if(!strcmp(scenario,"parent-empty"))parent_menu(0);
    else if(!strcmp(scenario,"parent-remember03"))parent_menu(1);
    else if(!strcmp(scenario,"poison-write-panel"))preference_poison(5,1);
    else if(!strcmp(scenario,"poison-write-same"))preference_poison(5,0);
    else if(!strcmp(scenario,"poison-rename-panel"))preference_poison(7,1);
    else if(!strcmp(scenario,"poison-close-same"))preference_poison(6,0);
    else if(!strcmp(scenario,"unit-swap28"))same_boot_swap(1);
    else if(!strcmp(scenario,"unit-swapM0"))same_boot_swap(2);
    else if(!strcmp(scenario,"survivor-A"))valid_survivor(0);
    else if(!strcmp(scenario,"survivor-B"))valid_survivor(1);
    else if(!strcmp(scenario,"survivor-AB"))valid_survivor(2);
    else if(!strcmp(scenario,"write-frequency"))write_frequency();
    else CHECK(0);
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    printf("OK scenario=%s unit=%u assertions=%u policy=%u\n",scenario,unit,assertions,policy);return 0;
}
