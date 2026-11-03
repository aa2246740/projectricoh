/* Independent checks through the actual public hooks; inherited native doubles. */
#define main fixture_main
#include "driver.c"
#undef main

static void cold_probe(void)
{
    const unsigned hooks[]={2,5,6,7,8,9};
    unsigned h,k,mode;uint32_t f[32],before[32];RvRoot oldroot;
    for(mode=0;mode<2;mode++)for(h=0;h<6;h++){
        clean();opens=closes=alloc_calls=0;memset(kind_count,0,sizeof(kind_count));
        memset(&root,255,244);memcpy(root.pins,rv_pins,12);
        if(mode)root.state=RV_DISABLED_UNTIL_REBOOT;
        oldroot=root;
        for(k=0;k<32;k++)f[k]=before[k]=0x91827500u+k;
        rv_hook_observe(&root,hooks[h],f);
        CHECK(!memcmp(f,before,sizeof(f))&&!memcmp(&root,&oldroot,sizeof(root)));
        CHECK(!opens&&!closes&&!alloc_calls&&!rpc_calls&&!writes&&!previews);
        CHECK(!kind_count[2]);
    }
    clean();memset(kind_count,0,sizeof(kind_count));memset(&root,255,244);memcpy(root.pins,rv_pins,12);memset(f,0,sizeof(f));
    rv_hook_observe(&root,1,f);
    CHECK(kind_count[2]==3&&root.state==RV_DISABLED_UNTIL_REBOOT&&!rpc_calls&&!writes);
    printf("AUDIT_COLD six_hooks_zero_side_effect=12 H01_file_open_attempts=%u no_token_gate=1\n",kind_count[2]);
}

static void ctl_fuzz(void)
{
    uint8_t ctl[64]={0};unsigned length,bit,part,k;unsigned cases=0;
    memcpy(ctl,"GXRC3401",8);rv_put32(ctl+12,gxrce_crc32(ctl,12));
    for(length=0;length<64;length++){
        clean();put_file("/ATA1/GXRCE.CTL",ctl,length);
        CHECK(ig_control_off()==(length==16));CHECK(opens==closes);cases++;
    }
    for(bit=0;bit<128;bit++){
        clean();ctl[bit/8]^=(uint8_t)(1u<<(bit%8));put_file("/ATA1/GXRCE.CTL",ctl,16);
        CHECK(!ig_control_off());ctl[bit/8]^=(uint8_t)(1u<<(bit%8));CHECK(opens==closes);cases++;
    }
    for(part=1;part<=17;part++){
        clean();chunk=part;put_file("/ATA1/GXRCE.CTL",ctl,16);
        CHECK(ig_control_off());CHECK(opens==closes);cases++;
    }
    for(k=1;k<=16;k++){
        clean();chunk=1;put_file("/ATA1/GXRCE.CTL",ctl,16);
        memset(kind_count,0,sizeof(kind_count));fault_kind=3;fault_at=k;fault_action=31;
        CHECK(!ig_control_off());CHECK(opens==closes);cases++;
    }
    for(k=2;k<=6;k+=2){
        clean();put_file("/ATA1/GXRCE.CTL",ctl,16);native_fail_op=k;
        native_fail_path="/ATA1/GXRCE.CTL";native_fail_left=1;
        CHECK(!ig_control_off());CHECK(opens==closes&&fault_used);cases++;
    }
    clean();put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);put_file("/ATA1/GXRCE.CTL",ctl,16);
    CHECK(rv_load(&root,&rv_trust)!=RV_OK&&root.state==RV_DISABLED_UNTIL_REBOOT);
    CHECK(!rpc_calls&&!rpc_w&&!writes&&!previews&&!log_writes&&!internal_mutations);
    CHECK(!root.block&&!root.lease);
    printf("AUDIT_CTL parser_cases=%u OFF_precedes_init_install_publish=1\n",cases);
}

static void panel_cancel_probe(void)
{
    unsigned slot,p,base_calls,base_mutations;uint8_t rows_before[505],s_before[4096];
    if(unit==1)return;
    for(slot=1;slot<=8;slot++){
        clean();ready(0);menu();apply_ok(slot);menu();open_fn2();
        memcpy(s_before,RV_PTR(0x20500000),4096);base_calls=rpc_calls;base_mutations=internal_mutations;
        /* Build a literal concatenation of all nine native rows. */
        {Gxr2View v;unsigned map,at=0,row;CHECK(gxr2_validate(new_raw,new_bytes,&trust,&units[unit],0,&v)==GXR2_OK);
         map=be32(new_raw+v.sections[2].offset+64*unit+12);
         for(row=0;row<9;row++){const uint8_t *d=new_raw+map+32+12*row;memcpy(rows_before+at,RV_PTR(be32(d)),be16(d+4));at+=be16(d+4);}CHECK(at==503);}
        for(p=0;p<4;p++){select_slot(6);open_fn2();}
        CHECK(rpc_calls==base_calls&&!memcmp(s_before,RV_PTR(0x20500000),4096));
        close_menu();CHECK(rpc_calls==base_calls&&internal_mutations==base_mutations);
        matches_recipe(new_raw,slot,new_golden);CHECK(root.state==RV_READY);
    }
    puts("AUDIT_PANEL all_eight_slots_draft_and_MENU_leave_committed_rows_and_S=1");
}

static void late_card_probe(int argc,char **argv)
{
    uint8_t old[65537];unsigned bytes,before;char path[32];
    if(unit==1)return;
    bytes=load_file(argv[6],old,sizeof(old));(void)argc;
    clean();ready(0);menu();CHECK(!(root.flags&RF_QUARANTINE));
    put_file("/ATA1/GXRCE.DAT",old,bytes);before=internal_mutations;
    apply_ok(8);menu();open_fn2();select_slot(9);explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
    CHECK(root.state==RV_READY&&!(root.flags&RF_QUARANTINE)&&internal_mutations>before);
    tweak_path(path,8,0);CHECK(file(path));CHECK(file("/ATA1/GXRCE.DAT"));
    puts("OBSERVED late_inserted_older_DAT_is_not_rescanned saves_current_engine_state=1 positive_rejection_not_seen=1");
}

static void quarantine_reset_probe(int argc,char **argv)
{
    uint8_t old[65537];unsigned bytes,before;char path[32];
    if(unit==1)return;
    bytes=load_file(argv[6],old,sizeof(old));(void)argc;
    clean();put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);put_file("/ATA1/GXRCE.DAT",old,bytes);
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&(root.flags&RF_QUARANTINE));menu();before=internal_mutations;
    file("/ATA1/GXRCE.DAT")->exists=0;apply_ok(8);menu();open_fn2();select_slot(9);
    explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
    CHECK(internal_mutations==before&&(root.flags&RF_QUARANTINE));
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK&&!(root.flags&RF_QUARANTINE));
    menu();select_slot(8);open_fn2();select_slot(9);explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
    tweak_path(path,8,0);CHECK(file(path)&&ig_host_panel()->last_store==RV_OK);
    puts("AUDIT_QUARANTINE sticky_after_removal=1 cold_boot_reenables_normal_saving=1");
}

int main(int argc,char **argv)
{
    char *task=argv[1];argv[1]="basic";CHECK(fixture_main(argc,argv)==0);argv[1]=task;
    if(!strcmp(task,"cold"))cold_probe();
    else if(!strcmp(task,"ctl-fuzz"))ctl_fuzz();
    else if(!strcmp(task,"panel-cancel"))panel_cancel_probe();
    else if(!strcmp(task,"late-card"))late_card_probe(argc,argv);
    else if(!strcmp(task,"quarantine-reset"))quarantine_reset_probe(argc,argv);
    else CHECK(0);
    printf("OK audit=%s unit=%u assertions=%u\n",task,unit,assertions);return 0;
}
