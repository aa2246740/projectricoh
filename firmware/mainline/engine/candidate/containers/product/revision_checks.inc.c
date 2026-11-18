static const char *engine_path(unsigned copy)
{return copy?"/IROM/GXRCE1.DAT":"/IROM/GXRCE0.DAT";}
static RvLease *workspace_lease(RvSession *s)
{
    unsigned i;RvLease *work=0;
    for(i=1;i<RV_LEASES;++i)if(s->leases[i].token&&s->leases[i].usage==4) {
        CHECK(!work);work=&s->leases[i];
    }
    CHECK(work&&work->length==ig_host_workspace_bytes());return work;
}
static void unchanged_file(const char *path,const uint8_t *raw,unsigned n)
{File *f=file(path);CHECK(f&&f->length==n&&!memcmp(f->bytes,raw,n));}
static void next_entry_stays_disabled(uint32_t allocations,uint32_t frees)
{
    uint32_t frame[32]={0};rv_hook_observe(&root,1,frame);
    CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&alloc_calls==allocations&&free_attempts==frees);
}
static void workspace_release_case(unsigned saves,int fail)
{
    RvSession *s;RvLease saved,*work;unsigned i,allocations,frees,birth,main_base,ui_base;
    review_free_length=ig_host_workspace_bytes();review_free_left=fail?1:0;
    menu();s=session();work=workspace_lease(s);saved=*work;
    birth=s->lease_entry[work-s->leases];main_base=root.block;ui_base=root.ui_block;
    allocations=alloc_calls;frees=free_attempts;
    for(i=0;i<saves;++i) {
        if(i)menu();select_slot(1);panel_open();select_slot(i%2?8:7);close_key(1);
        CHECK(root.state==RV_READY&&alloc_calls==allocations&&free_attempts==frees);
        CHECK(work->token==saved.token&&work->base==saved.base&&review_free_hits==0);
        CHECK(file(tweak_path(i&1))&&be32(file(tweak_path(i&1))->bytes+12)==i+1);
        CHECK(be32(file(tweak_path(i&1))->bytes+196)==(i%2?2u:1u));
    }
    if(saves)menu();select_slot(1);CHECK(root.entry_serial>birth);
    CHECK(invoke(s->entries.shutdown,0,0)==(fail?RV_FAULT:RV_CONSUMED));
    CHECK(alloc_calls==allocations&&free_attempts==frees+1);
    if(fail) {
        CHECK(review_free_hits==1&&root.state==RV_DISABLED_UNTIL_REBOOT);
        CHECK(!memcmp(work,&saved,sizeof(saved))&&RV_BYTE(saved.base-8)==1);
        CHECK(s->lease_entry[work-s->leases]==birth);
    } else CHECK(!work->token&&RV_BYTE(saved.base-8)==0);
    CHECK(owned(main_base,1)&&owned(ui_base,1)&&RV_BYTE(main_base-8)==1&&RV_BYTE(ui_base-8)==1);
    next_entry_stays_disabled(allocations,frees+1);
    printf("WORKSPACE_PASS saves=%u stable_token=%u host_bytes=%u release_calls=1 release_failed=%d owner_retained=%d main_and_UI_live=1 next_entry_no_alloc=1\n",
        saves,saved.token,saved.length,fail,fail);
}
static int revision_checks(void)
{
    uint32_t allocations,frees,w,r,frame[32]={0};unsigned i,copy=0;
    int32_t result;RvSession *s;
    static uint8_t old[73729],old_b[73729];unsigned old_n,old_bn;
    if(strncmp(scenario,"review-",7)&&strncmp(scenario,"r3-",3))return 0;
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);CHECK(rv_load(&root,&rv_trust)==RV_OK);
    CHECK(session()->selected_source==RV_SOURCE_CARD);
    if(!strcmp(scenario,"review-free-preload")){workspace_release_case(0,1);return 1;}
    if(!strcmp(scenario,"review-free-save")){workspace_release_case(1,1);return 1;}
    if(!strcmp(scenario,"review-free-repeat")){workspace_release_case(8,1);return 1;}
    if(!strcmp(scenario,"r3-workspace-release")){workspace_release_case(2,0);return 1;}
    if(!strncmp(scenario,"r3-install-free-",16)) {
        s=session();review_free_length=73728;review_free_left=1;
        review_free_skip=strstr(scenario,"raw")?1:0;
        if(strstr(scenario,"alloc")){fail_alloc=alloc_calls+2;review_free_skip=0;}
        allocations=alloc_calls;frees=free_attempts;
        CHECK(invoke(s->entries.menu_open,0,0)==RV_FAULT);
        CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&review_free_hits==1);
        CHECK(ig_host_install_status()==RV_FAULTED&&alloc_calls==allocations+2);
        w=0;for(i=1;i<RV_LEASES;++i)if(s->leases[i].token) {
            ++w;CHECK(s->leases[i].usage==2&&s->leases[i].inverse==~s->leases[i].token);
            CHECK(RV_BYTE(s->leases[i].base-8)==1);
        }
        CHECK(w==1&&free_attempts==frees+(strstr(scenario,"alloc")?1u:2u));
        next_entry_stays_disabled(alloc_calls,free_attempts);
        puts("INSTALL_FREE_FAILURE_PASS disabled_until_reboot=1 failed_owner_retained=1 no_workspace_alloc=1 no_retry=1");return 1;
    }
    if(!strcmp(scenario,"review-hidden-engine")||!strcmp(scenario,"r3-hidden-engine-B")||
       !strcmp(scenario,"r3-newer-generation")||!strcmp(scenario,"r3-rename-preserves")||!strcmp(scenario,"r3-rename-source-loss")||
       !strcmp(scenario,"r3-target-exists")||!strcmp(scenario,"r3-both-unknown")) {
        copy=!strcmp(scenario,"r3-hidden-engine-B");
        memcpy(old,base_raw,base_bytes);old_n=base_bytes;
        if(!strcmp(scenario,"r3-newer-generation")) {
            memcpy(old,new_raw,new_bytes);old_n=new_bytes;rv_put32(old+28,be32(new_raw+28)+1);
            rv_put32(old+20,0);rv_put32(old+20,gxrce_crc32(old,256));
        }
        put_file(engine_path(copy),old,old_n);
        hidden_path[0]=engine_path(copy);hidden_left[0]=2;
        if(!strcmp(scenario,"r3-target-exists")) {hidden_left[0]=3;rename_refuse_existing=1;}
        if(!strcmp(scenario,"r3-both-unknown")) {
            put_file(engine_path(1),old,old_n);hidden_left[0]=3;
            hidden_path[1]=engine_path(1);hidden_left[1]=3;
        }
        if(!strcmp(scenario,"r3-rename-preserves")||!strcmp(scenario,"r3-rename-source-loss")) {
            native_fail_op=7;native_fail_left=1;native_fail_path="/IROM/GXRCE.TMP";
            rename_drop_source=!strcmp(scenario,"r3-rename-source-loss");
        }
        w=writes;r=renames;result=invoke(session()->entries.menu_open,0,0);
        if(!strcmp(scenario,"r3-newer-generation")) {
            CHECK(result==(unit==1?RV_PASS:RV_CONSUMED)&&ig_host_install_status()==RV_CONFLICT&&writes==w&&renames==r);
            unchanged_file(engine_path(0),old,old_n);CHECK(file("/ATA1/GXRCE.DAT"));
        } else if(!strcmp(scenario,"r3-target-exists")||!strcmp(scenario,"r3-rename-preserves")||!strcmp(scenario,"r3-rename-source-loss")) {
            CHECK(result!=RV_CONSUMED&&root.state==RV_DISABLED_UNTIL_REBOOT);
            CHECK(ig_host_install_status()==RV_UNCERTAIN&&file("/ATA1/GXRCE.DAT")&&!file("/ATA1/GXRCE.OK"));
            unchanged_file(engine_path(0),old,old_n);CHECK(!file(engine_path(1)));
            if(rename_drop_source)CHECK(!file("/IROM/GXRCE.TMP"));else unchanged_file("/IROM/GXRCE.TMP",new_raw,new_bytes);
        } else if(!strcmp(scenario,"r3-both-unknown")) {
            CHECK(result==(unit==1?RV_PASS:RV_CONSUMED)&&ig_host_install_status()==RV_OK&&hidden_hits==6);
            unchanged_file(engine_path(0),new_raw,new_bytes);unchanged_file(engine_path(1),old,old_n);
        } else {
            CHECK(result==(unit==1?RV_PASS:RV_CONSUMED)&&ig_host_install_status()==RV_OK&&hidden_hits==2);
            unchanged_file(engine_path(copy),old,old_n);unchanged_file(engine_path(1-copy),new_raw,new_bytes);
        }
        printf("ENGINE_REPLICA_PASS hidden_retries=%u old_generation=%u card_generation=%u result=%d install=%d native_rename=%s\n",
            hidden_hits,be32(old+28),be32(new_raw+28),result,ig_host_install_status(),rename_refuse_existing?"reject-existing":"replace-existing");return 1;
    }
    if(!strcmp(scenario,"r3-sticky-read")||!strcmp(scenario,"r3-sticky-open")) {
        seed_tweak_pair();memcpy(old,file(tweak_path(0))->bytes,GXTS_BYTES);
        native_fail_op=!strcmp(scenario,"r3-sticky-open")?2:4;native_fail_left=1;native_fail_code=-2;
        native_fail_path=tweak_path(1);menu();CHECK(fault_used&&root.state==RV_READY);
        allocations=alloc_calls;frees=free_attempts;w=writes;r=renames;
        for(i=0;i<2;++i) {
            if(i)menu();select_slot(i+1);panel_open();CHECK(!strcmp(ig_host_panel()->text[0],"SaveFail"));
            CHECK(RV_BYTE(root.ui_block+offsetof(RvUiSnapshot,glyphs)+1)=='S');
            select_slot(7);close_key(1);CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_IO);
        }
        CHECK(alloc_calls==allocations&&free_attempts==frees&&writes==w&&renames==r);
        unchanged_file(tweak_path(0),old,GXTS_BYTES);unchanged_file(tweak_path(1),old,GXTS_BYTES);
        puts("GXTS_STICKY_ERROR_PASS two_saves_blocked=1 different_slots=1 SaveFail_rendered=1 old_bytes_retained=1");return 1;
    }
    menu();select_slot(1);panel_open();select_slot(9);close_key(1);
    CHECK(file(tweak_path(0))&&!file(tweak_path(1)));
    CHECK(be32(file(tweak_path(0))->bytes+196)==3);
    if(!strcmp(scenario,"r3-empty-gxts")) {
        CHECK(be32(file(tweak_path(0))->bytes+12)==1);
        puts("EMPTY_GXTS_PASS first_save=OK generation=1 raw_missing=-1");return 1;
    }
    if(!strcmp(scenario,"r3-hidden-tweak-B")) {
        put_file(tweak_path(1),file(tweak_path(0))->bytes,GXTS_BYTES);file(tweak_path(0))->exists=0;copy=1;
    }
    memcpy(old,file(tweak_path(copy))->bytes,GXTS_BYTES);old_n=GXTS_BYTES;
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
    hidden_path[0]=tweak_path(copy);
    hidden_left[0]=!strcmp(scenario,"r3-gxts-persistent-minus1")?3:2;
    menu();CHECK(hidden_hits==(!strcmp(scenario,"r3-gxts-persistent-minus1")?3u:2u));
    select_slot(1);current(!strcmp(scenario,"r3-gxts-persistent-minus1")?0:3);panel_open();select_slot(7);
    hidden_left[0]=!strcmp(scenario,"r3-gxts-persistent-minus1")?3:2;w=writes;r=renames;
    if(!strcmp(scenario,"r3-gxts-persistent-minus1")) {
        close_key(1);CHECK(root.state==RV_READY&&hidden_hits==6);
        CHECK(file(tweak_path(0))&&!file(tweak_path(1))&&be32(file(tweak_path(0))->bytes+196)==1);
        CHECK(memcmp(file(tweak_path(0))->bytes,old,GXTS_BYTES));
        puts("RESIDUAL_RISK persistent_open_minus1=1 native_rename=replace-existing defaults_loaded=1 old_Cont=3 old_bytes_lost=1 generation_reset=1");return 1;
    }
    if(!strncmp(scenario,"r3-sticky-save-",15)) {
        native_fail_op=strstr(scenario,"open")?2:4;native_fail_left=1;native_fail_code=-2;
        native_fail_path=tweak_path(0);close_key(1);
        CHECK(root.state==RV_READY&&fault_used&&ig_host_panel()->last_store==RV_IO);
        unchanged_file(tweak_path(0),old,old_n);CHECK(!file(tweak_path(1))&&writes==w&&renames==r);
        menu();select_slot(1);panel_open();CHECK(!strcmp(ig_host_panel()->text[0],"SaveFail"));
        select_slot(8);close_key(1);CHECK(writes==w&&renames==r);
        unchanged_file(tweak_path(0),old,old_n);
        puts("GXTS_SAVE_READ_ERROR_PASS first_save_blocked=1 next_save_blocked=1 SaveFail_rendered=1 old_bytes_retained=1");return 1;
    }
    if(!strcmp(scenario,"r3-gxts-rename-preserves")||!strcmp(scenario,"r3-gxts-source-loss")) {
        native_fail_op=7;native_fail_left=1;native_fail_path=unit==0?"/IROM/T5000.TMP":unit==1?"/IROM/T2800.TMP":"/IROM/TM000.TMP";
        rename_drop_source=!strcmp(scenario,"r3-gxts-source-loss");
        frame[7]=0x23;frame[16]=0x202c2d84;rv_hook_observe(&root,7,frame);
        CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&fault_used);
        unchanged_file(tweak_path(copy),old,old_n);CHECK(!file(tweak_path(1-copy)));
        if(rename_drop_source)CHECK(!file(native_fail_path));
        puts("GXTS_RENAME_FAILURE_PASS old_bytes_retained=1 disabled=1");return 1;
    }
    close_key(1);CHECK(root.state==RV_READY&&writes>w&&renames>r&&hidden_hits==4);
    unchanged_file(tweak_path(copy),old,old_n);old_bn=file(tweak_path(1-copy))->length;
    memcpy(old_b,file(tweak_path(1-copy))->bytes,old_bn);
    CHECK(old_bn==GXTS_BYTES&&be32(old_b+196)==1&&be32(old_b+12)==2);
    puts("GXTS_HIDDEN_PASS old_Cont=3 preserved=1 saved_Cont=1 generation=2 both_retries_exercised=1");return 1;
}
