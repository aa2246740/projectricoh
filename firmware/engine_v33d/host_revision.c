/* Public hooks use real engine/services/resident C. Native enum and stores
 * are projected from the official bytes; native UI/M32R are not executed. */
#include "local/review_support.c"
#include "local/native_enum.h"
#include "local/native_get_mode.h"

static void force_close(uint32_t pc)
{
    uint32_t frame[32]={0};frame[16]=pc;rv_hook_observe(&root,7,frame);
    CHECK(frame[1]==(uint32_t)(uintptr_t)rv_close_07&&root.state==RV_READY);
    CHECK(!eng_list()->opened&&!ig_host_panel()->open&&RV_BYTE(0x2022f5ac)==7);
}
static void begin_count(void)
{last_object=1;tracing=1;memset(counts,0,sizeof(counts));}
static void cycles(unsigned want)
{
    CHECK(counts[3]==want&&counts[7]==want);
    printf("WRITE_CYCLES creates=%u writes=%u renames=%u deletes=%u\n",counts[3],counts[5],counts[7],counts[8]);
    tracing=0;
}
static void write_policy(void)
{
    unsigned i;uint32_t frame[32]={0};installed();select_slot(1);close_key(0);menu();
    begin_count();
    for(i=1;i<=8;++i)select_slot(i);
    for(i=7;i>=1;--i)select_slot(i);
    CHECK(!counts[3]&&!counts[5]&&!counts[7]&&!counts[8]);
    puts("POLICY scroll_01_08_01_before_close=0");close_key(0);cycles(0);
    menu();begin_count();close_key(0);cycles(0);puts("POLICY reopen_without_change=0");
    menu();begin_count();select_slot(8);CHECK(!counts[3]);close_key(1);cycles(1);puts("POLICY OK_changed=1");
    menu();begin_count();select_slot(7);CHECK(!counts[3]);close_key(0);cycles(1);puts("POLICY MENU_changed=1");
    menu();begin_count();select_slot(6);force_close(0x202b8d9c);cycles(1);puts("POLICY forced_changed=1");
    /* A non-closing confirmation is allowed to keep editing. Only the final
     * close writes, even when more commits follow that confirmation. */
    menu();begin_count();RV_BYTE(0x2022f726)=5;
    frame[7]=0x23;frame[11]=1;frame[16]=0x202c2d74;rv_hook_observe(&root,7,frame);
    CHECK(root.state==RV_READY&&eng_list()->opened&&!counts[3]);current_slot(5,0);
    select_slot(8);close_key(0);cycles(1);puts("POLICY keep_open_OK_then_change_close=1");
    menu();begin_count();select_slot(7);CHECK(!counts[3]);cycles(0);
    cold109();current_slot(8,0);puts("POLICY power_loss_before_close_keeps_last_verified=8");
}
static unsigned projected_entry(unsigned mode)
{
    uint32_t first[32]={0},second[32]={0},draw[32]={0},serial;unsigned row,raw_mode;
    RV_BYTE(RV_NATIVE_VIEWS)=32;RV_WORD(RV_NATIVE_VIEWS+4)=0x2022f71c;
    RV_BYTE(0x205a27d4)=1;RV_BYTE(0x2050036e)=mode;
    first[15]=99;rv_hook_observe(&root,1,first);
    CHECK(root.state==RV_READY&&!first[1]&&first[15]==99);
    raw_mode=RV_BYTE(0x2050036e);mode=native_s_modes[raw_mode];
    RV_BYTE(0x2050036e)=mode;CHECK(mode<11);
    second[7]=mode;rv_hook_observe(&root,2,second);
    CHECK(!second[1]&&second[7]==mode);
    row=native_mode_rows[mode];
    RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=row;
    RV_BYTE(RV_NATIVE_VIEWS+8)=33;RV_WORD(RV_NATIVE_VIEWS+12)=0x2022f71c;
    RV_BYTE(0x205a27d4)=2;serial=root.entry_serial;
    draw[13]=0xabcdef00;rv_hook_observe(&root,5,draw);
    CHECK(draw[1]==(uint32_t)(uintptr_t)rv_skip_05&&draw[13]==root.ui_restore[7]);
    CHECK(root.entry_serial==serial&&RV_BYTE(0x2022f726)==row&&RV_BYTE(0x2022f725)==row);
    printf("NATIVE_HIGHLIGHT parent_tag=32 raw_S=%u normalized_S=%u row=%u engine_cursor=%u H01_skip=0 H02_skip=0 H05_engine_entries=0\n",raw_mode,mode,row,eng_list()->cursor);
    return row;
}
static void highlighted_action(unsigned row,int panel)
{
    if(panel){panel_open();CHECK(ig_host_panel()->recipe.slot==row);close_key(0);}
    else close_key(1);
    {EngRecipeRef ref;EngTweak t;root.inflight=1;CHECK(eng_current(&ref,&t)==ENG_OK);root.inflight=0;
     CHECK(ref.slot==row&&ref.unit==unit);}
    CHECK(root.state==RV_READY&&!eng_uncertain());
    printf("HIGHLIGHT_ACTION action=%s applied_slot=%u\n",panel?"Fn2":"OK",row);
}
static void boundary(unsigned mode,int panel,unsigned remembered)
{
    unsigned row;put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    if(remembered){load109();save_cont(remembered,remembered==3?2:0);}
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);CHECK(!has_current());
    row=projected_entry(mode);if(remembered)current_slot(remembered,remembered==3?2:0);else CHECK(!has_current());
    highlighted_action(row,panel);
    row=projected_entry(RV_BYTE(0x2050036e));highlighted_action(row,panel);
    puts("KNOWN_LIMITATION_CHECK native_highlight_is_authoritative_on_each_parent_entry=1");
}
static unsigned close_stage,close_during_hits;
static void nested_close(unsigned op,const char *path)
{
    uint32_t frame[32]={0},serial;
    if(op!=close_stage||strncmp(path,"/IROM/L",7))return;
    native_observer=0;++close_during_hits;serial=root.entry_serial;
    CHECK(root.inflight&&(root.flags&RF_OWNER));frame[16]=0x202b8d9c;
    rv_hook_observe(&root,7,frame);
    CHECK(!frame[1]&&root.entry_serial==serial&&root.state==RV_READY);
}
static void forced_during(unsigned stage,unsigned key)
{
    uint32_t frame[32]={0};installed();select_slot(1);close_key(0);menu();select_slot(5);
    close_stage=stage;close_during_hits=0;native_observer=nested_close;begin_count();
    if(key==2)force_close(0x202b8d9c);else close_key(key==1);
    native_observer=0;CHECK(close_during_hits==1);cycles(1);
    CHECK(root.state==RV_READY&&!(root.flags&(RF_UNCERTAIN|RF_OWNER))&&opens==closes);
    rv_hook_observe(&root,7,frame);CHECK(!frame[1]&&root.state==RV_READY);
    menu();begin_count();force_close(0x202bea54);cycles(0);cold109();current_slot(5,0);
    printf("FORCED_CLOSE stage=%u outer_key=%u nested_deferred_by_inflight=1 outer_close_finishes=1 after_write_no_duplicate=1\n",stage,key);
}
static void seed_last(const uint8_t *raw,unsigned bytes,unsigned slot)
{
    uint8_t record[192]={0};Gxr2View view;GxtsBinding binding;char path[32];
    CHECK(gxr2_validate(raw,bytes,&trust,&units[unit],0,&view)==GXR2_OK);
    CHECK(gxts_bind(&view,unit,slot,&binding)==GXTS_OK);
    memcpy(record,"GXLS",4);record[5]=1;record[7]=192;rv_put32(record+8,1);
    record[16]=slot;record[17]=unit;memcpy(record+24,binding.identity,160);
    rv_put32(record+12,gxrce_crc32(record,sizeof(record)));path_for(path,1,0,0);put_file(path,record,sizeof(record));
}
static void upgrade_saved_memory(void)
{
    char path[32];uint8_t saved[192];
    put_file("/IROM/GXRCE0.DAT",base_raw,base_bytes);
    if(unit!=1){seed_tweak(base_raw,base_bytes,5,1,2);seed_last(base_raw,base_bytes,5);path_for(path,1,0,0);memcpy(saved,file(path)->bytes,192);}
    CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();
    if(unit!=1)current_slot(5,2);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);reboot();load109();
    CHECK(ig_host_install_status()==RV_OK&&!file("/ATA1/GXRCE.DAT")&&file("/ATA1/GXRCE.OK"));
    if(unit!=1){current_slot(5,2);CHECK(!memcmp(saved,file(path)->bytes,192));}
    cold109();CHECK(session()->generation==109);
    if(unit!=1)current_slot(5,2);else CHECK(!has_current()&&RV_BYTE(0x2022f5ac)==7);
    puts("UPGRADE_PASS last_memory_and_GXTS_retained=1 removed_DAT_cold_109=1");
}
static void older_card_close(void)
{
    put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
    memcpy(durable_before,files,sizeof(files));CHECK(rv_load(&root,&rv_trust)==RV_OK);
    menu();CHECK(ig_host_install_status()==RV_CONFLICT);
    if(unit!=1){select_slot(5);panel_open();close_key(0);menu();select_slot(8);force_close(0x202b8d9c);}
    no_files_changed();file("/ATA1/GXRCE.DAT")->exists=0;cold109();
    CHECK(session()->generation==109&&session()->selected_source==RV_SOURCE_A&&!has_current());
    puts("OLD_DAT_PASS browse_Fn2_MENU_forced_close_all_zero_writes=1 DAT_removed_cold_109=1");
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
    policy=(unsigned)strtoul(argv[8],0,10);rename_refuse_existing=policy;reboot();
    if(!strcmp(scenario,"write-policy")){CHECK(unit!=1);write_policy();}
    else if(!strcmp(scenario,"boundary")){CHECK(argc==12&&unit!=1);boundary((unsigned)strtoul(argv[9],0,10),atoi(argv[10]),(unsigned)strtoul(argv[11],0,10));}
    else if(!strcmp(scenario,"forced-during")){CHECK(argc==11&&unit!=1);forced_during((unsigned)strtoul(argv[9],0,10),(unsigned)strtoul(argv[10],0,10));}
    else if(!strcmp(scenario,"upgrade-memory"))upgrade_saved_memory();
    else if(!strcmp(scenario,"older-card-close"))older_card_close();
    else CHECK(0);
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    printf("OK scenario=%s unit=%u assertions=%u policy=%u\n",scenario,unit,assertions,policy);return 0;
}
