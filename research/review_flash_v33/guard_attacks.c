/* Real public hooks and frozen product C. Only native calls are doubles. */
#include "first_frame_support.c"

static void init(int argc,char **argv)
{
    uint8_t wire[232];unsigned i;
    CHECK(argc==11);scenario=argv[1];unit=(unsigned)atoi(argv[2]);CHECK(unit==0||unit==2);
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    CHECK(load_file(argv[5],wire,sizeof(wire))==232);
    CHECK(load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,wire+8,32);memcpy(trust.resident_build_id,wire+40,32);memcpy(trust.resident_abi_id,wire+72,16);
    for(i=0;i<3;++i){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(wire+100+48*i);memcpy(trust.modules[i].stock_sha256,wire+104+48*i,32);}
    rename_refuse_existing=(unsigned)atoi(argv[8]);reboot();
}
static void fault(unsigned op,int code)
{
    native_fail_op=op;native_fail_left=1;native_fail_code=code;native_fail_path="/ATA1/GXRCE.DAT";
}
int main(int argc,char **argv)
{
    unsigned i,op,before_writes,before_renames;int code;uint32_t flags;
    init(argc,argv);op=(unsigned)atoi(argv[9]);code=atoi(argv[10]);
    put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_A);
    CHECK(first_frame_entry(1)==1);select_slot(8);
    printf("GUARD_SETUP old_generation=%u active_generation=%u selected_source=%u one_native_error=1\n",
        be32(base_raw+28),session()->generation,session()->selected_source);
    memcpy(durable_before,files,sizeof(files));before_writes=writes;before_renames=renames;
    if(!strcmp(scenario,"explicit")){panel_open();select_slot(9);}
    fault(op,code);close_key(!strcmp(scenario,"explicit"));
    CHECK(fault_used&&native_fail_left==0);
    flags=root.flags;native_fail_left=0;
    printf("GUARD_AFTER op=%u raw=%d state=%u flags=%u current=%u writes=%u renames=%u last=%d\n",op,code,
        root.state,flags,has_current(),writes-before_writes,renames-before_renames,ig_host_last_store());
    if(code!=-1||op!=2) {no_files_changed();CHECK(writes==before_writes&&renames==before_renames);}
    else {
        CHECK(writes-before_writes==3&&renames-before_renames==1);
        for(i=0;i<64;++i)if(files[i].exists&&memcmp(&files[i],&durable_before[i],sizeof(File))) {
            printf("GUARD_CHANGED path=%s bytes=%u generation=%u\n",files[i].path,files[i].length,
                be32(files[i].bytes+(!memcmp(files[i].bytes,"GXLS",4)?8:12)));
            if(!memcmp(files[i].bytes,"GXLS",4))CHECK(files[i].bytes[16]==8);
        }
        if(!strcmp(scenario,"explicit"))CHECK(ig_host_panel()->last_store==RV_OK);
    }
    /* Continue after the read-only guard error. No other native fault remains. */
    if(root.state==RV_READY)menu();
    if(root.state==RV_READY)select_slot(8);
    printf("GUARD_FOLLOWUP state=%u flags=%u panel_open=%u\n",root.state,root.flags,ig_host_panel()->open);
    if(root.state==RV_READY){panel_open();close_key(0);}
    if(op==2&&code==-1) {
        int explicit_save=!strcmp(scenario,"explicit");
        file("/ATA1/GXRCE.DAT")->exists=0;reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
        CHECK(first_frame_entry(1)==(explicit_save?1u:8u));
        if(explicit_save)select_slot(8);
        current_slot(8,explicit_save?3:0);
        printf("GUARD_PERSISTED object=%s slot=8 Cont=%u after_clean_reboot=1\n",explicit_save?"GXTS":"GXLS",explicit_save?3u:0u);
    }
    printf("OK scenario=%s unit=%u assertions=%u state=%u poison=%u\n",scenario,unit,assertions,root.state,
        !!(flags&RF_UNCERTAIN));
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    return 0;
}
