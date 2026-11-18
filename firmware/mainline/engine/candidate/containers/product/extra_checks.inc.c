static const char *tweak_path(unsigned copy)
{
    static const char *paths[3][2]={{"/IROM/T5000A.BIN","/IROM/T5000B.BIN"},
        {"/IROM/T2800A.BIN","/IROM/T2800B.BIN"},{"/IROM/TM000A.BIN","/IROM/TM000B.BIN"}};
    return paths[unit][copy];
}
static void no_temporary_leases(void)
{
    unsigned i,work=0;
    for(i=1;i<RV_LEASES;++i)if(session()->leases[i].token) {
        CHECK(session()->leases[i].usage==4);++work;
        CHECK(session()->leases[i].length==ig_host_workspace_bytes());
    }
    CHECK(work==1);
}

static RvRequest fixed_request(unsigned kind,unsigned replica)
{
    RvRequest q={0};q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];
    q.args[2]=kind;q.args[5]=replica;return q;
}
static int32_t fixed_call(unsigned op,RvRequest *q,RvReply *r)
{
    int32_t status=rv_service(&root,RV_STORAGE,op,q,r);
    CHECK(r->status==status&&r->version==1&&r->bytes==32);return status;
}
static void native_boundary(void)
{
    RvRequest q;RvReply r;uint32_t token=0;int32_t status=RV_OK;unsigned op=0,i,j;
    native_fail_code=strstr(scenario,"neg2")?-2:-1;
    if(strstr(scenario,"open"))op=2;
    if(strstr(scenario,"create"))op=3;
    if(strstr(scenario,"read"))op=4;
    if(strstr(scenario,"write"))op=5;
    if(strstr(scenario,"close"))op=6;
    if(strstr(scenario,"rename"))op=7;
    if(strstr(scenario,"delete"))op=8;
    CHECK(op);root.inflight=1;
    if(op==2) {
        for(i=1;i<=5;++i) {
            q=fixed_request(PS_ENGINE,i);native_fail_op=2;native_fail_left=1;
            status=fixed_call(2,&q,&r);CHECK(status==(native_fail_code==-1?RV_UNAVAILABLE:RV_IO));
        }
        for(i=1;i<=3;++i)for(j=2;j<=4;++j) {
            q=fixed_request(PS_TWEAK,j);q.args[3]=i;q.args[4]=15;
            native_fail_left=1;status=fixed_call(2,&q,&r);
            CHECK(status==(native_fail_code==-1?RV_UNAVAILABLE:RV_IO));
        }
    } else if(op==3) {
        q=fixed_request(PS_ENGINE,PS_TEMP);q.args[8]=16;native_fail_op=3;native_fail_left=1;
        status=fixed_call(3,&q,&r);CHECK(status==RV_IO);
    } else if(op>=4&&op<=6) {
        q=fixed_request(PS_ENGINE,op==5?PS_TEMP:PS_CARD);if(op==5)q.args[8]=16;
        CHECK(fixed_call(op==5?3:2,&q,&r)==RV_OK);token=r.token;
        q=fixed_request(0,0);q.args[1]=token;
        if(op!=6){q.args[6]=session()->context.state_address+1024;q.args[7]=1;}
        native_fail_op=op;native_fail_left=1;status=fixed_call(op,&q,&r);CHECK(status==RV_IO);
        if(op!=6){q=fixed_request(0,0);q.args[1]=token;CHECK(fixed_call(6,&q,&r)==RV_OK);}
    } else {
        put_file("/IROM/GXRCE.TMP",base_raw,base_bytes);
        q=fixed_request(PS_ENGINE,PS_TEMP);if(op==7)q.args[9]=PS_A;
        native_fail_op=op;native_fail_left=1;status=fixed_call(op,&q,&r);
        CHECK(status==RV_UNCERTAIN&&(root.flags&RF_UNCERTAIN));
        CHECK(file("/IROM/GXRCE.TMP")&&!file("/IROM/GXRCE0.DAT"));
    }
    CHECK(!native_fail_left&&fault_used);root.inflight=0;
    printf("NATIVE_BOUNDARY_PASS op=%u raw=%d result=%d\n",op,native_fail_code,status);
}
static void seed_tweak_pair(void)
{
    PnGxts t;PsStore store;EngRecipeRef ref;uint8_t indices[6],bytes[GXTS_BYTES];GxtsState state;unsigned i;
    const Gxr2View *v=eng_validated_view();const uint8_t *d=v->bytes+v->sections[2].offset+64*unit;
    ref.unit=(uint8_t)unit;ref.slot=1;eng_identity(v->bytes+be32(d+16)+32,ref.identity);
    for(i=0;i<6;++i)indices[i]=(uint8_t)eng_parameter_index(i+1);
    CHECK(pn_gxts_bind(&t,&store,v,&ref,indices)==RV_OK);gxts_defaults(&t.binding,&state);state.generation=1;
    CHECK(gxts_encode(&t.binding,&state,bytes)==GXTS_OK);
    put_file(tweak_path(0),bytes,sizeof(bytes));put_file(tweak_path(1),bytes,sizeof(bytes));
}
static int extra_checks(void)
{
    uint32_t w,renamed,i;int32_t result;
    if(strncmp(scenario,"boundary-",9)&&strcmp(scenario,"firstboot-empty")&&
       strcmp(scenario,"gxts-read-failure")&&strcmp(scenario,"gxts-partial-io")&&
       strcmp(scenario,"install-readback-failure")&&strcmp(scenario,"install-readback-mismatch")&&
       strcmp(scenario,"install-readback-open")&&strcmp(scenario,"gxts-readback-open")&&
       strcmp(scenario,"gxts-readback-mismatch")&&strcmp(scenario,"lease-preload")&&strcmp(scenario,"lease-save"))return 0;
    for(i=0;i<64;++i)CHECK(!files[i].exists);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);CHECK(rv_load(&root,&rv_trust)==RV_OK);
    if(!strncmp(scenario,"boundary-",9)){native_boundary();return 1;}
    if(!strcmp(scenario,"gxts-read-failure")) {
        uint8_t bytes[GXTS_BYTES]={0};put_file(tweak_path(0),bytes,sizeof(bytes));
        fail_alloc=alloc_calls+1;native_fail_op=4;native_fail_left=1;native_fail_path=tweak_path(0);
        result=invoke(session()->entries.menu_open,0,0);
        CHECK(fault_used&&result==RV_CLOSE_AND_PASS&&root.state==RV_DISABLED_UNTIL_REBOOT);
        CHECK(RV_BYTE(0x2022f5ac)==7&&!writes&&!renames);return 1;
    }
    if(!strcmp(scenario,"install-readback-failure")) {
        native_fail_op=4;native_fail_left=1;native_fail_path="/IROM/GXRCE.TMP";
    }
    if(!strcmp(scenario,"install-readback-open")) {
        native_fail_op=2;native_fail_left=3;native_fail_skip=3;native_fail_path="/IROM/GXRCE.TMP";
    }
    if(!strcmp(scenario,"gxts-partial-io")) {
        seed_tweak_pair();native_fail_op=4;native_fail_left=1;native_fail_path=tweak_path(1);
    }
    if(!strcmp(scenario,"lease-preload"))fail_alloc=alloc_calls+3;
    result=invoke(session()->entries.menu_open,0,0);
    if(!strcmp(scenario,"lease-preload")) {
        CHECK(result==RV_CLOSE_AND_PASS&&root.state==RV_DISABLED_UNTIL_REBOOT);return 1;
    }
    if(unit==1 && !strncmp(scenario,"install-readback-",17)) {
        CHECK(result==RV_PASS&&root.state==RV_READY&&RV_BYTE(0x2022f5ac)==7);
        CHECK(fault_used&&ig_host_install_status()!=RV_OK&&file("/ATA1/GXRCE.DAT")&&!file("/ATA1/GXRCE.OK"));
        CHECK(!file("/IROM/GXRCE0.DAT")&&!file("/IROM/GXRCE1.DAT"));return 1;
    }
    CHECK(result==(unit==1?RV_PASS:RV_CONSUMED)&&root.state==RV_READY&&RV_BYTE(0x2022f5ac)==fixture_rows());
    no_temporary_leases();
    if(!strncmp(scenario,"install-readback-",17)) {
        CHECK(fault_used&&ig_host_install_status()!=RV_OK&&file("/ATA1/GXRCE.DAT")&&!file("/ATA1/GXRCE.OK"));
        CHECK(!file("/IROM/GXRCE0.DAT")&&!file("/IROM/GXRCE1.DAT"));return 1;
    }
    CHECK(ig_host_install_status()==RV_OK&&!file("/ATA1/GXRCE.DAT")&&file("/ATA1/GXRCE.OK"));
    CHECK(valid_irom(0)||valid_irom(1));
    if(!strcmp(scenario,"firstboot-empty")) {
        for(i=1;i<=fixture_rows();++i){select_slot(i);matches_recipe(new_raw,i,new_golden);}
        no_temporary_leases();reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
        CHECK(session()->selected_source==RV_SOURCE_A||session()->selected_source==RV_SOURCE_B);
        CHECK(session()->generation==be32(new_raw+28));menu();no_temporary_leases();
        printf("FIRSTBOOT_EMPTY_PASS rows=16 IROM_install=OK DAT_to_OK=OK IROM_reboot=OK raw_missing=-1 temporary_leases=0 session_workspace=1 main_request=%u\n",root.block_bytes);return 1;
    }
    select_slot(1);panel_open();select_slot(7);current(1);w=writes;renamed=renames;
    if(!strcmp(scenario,"gxts-readback-mismatch"))fault_used=0;
    if(!strcmp(scenario,"gxts-readback-open")) {
        static const char *paths[3]={"/IROM/T5000.TMP","/IROM/T2800.TMP","/IROM/TM000.TMP"};
        native_fail_op=2;native_fail_left=3;native_fail_skip=3;native_fail_path=paths[unit];
    }
    if(!strcmp(scenario,"lease-save")) {
        uint32_t before=alloc_calls;fail_alloc=alloc_calls+1;close_key(1);
        CHECK(root.state==RV_READY&&alloc_calls==before&&writes>w&&renames>renamed);
        CHECK(file(tweak_path(0)));current(1);no_temporary_leases();
        puts("SAVE_REUSES_SESSION_WORKSPACE no_alloc_or_free_on_save");return 1;
    }
    if(!strcmp(scenario,"gxts-readback-mismatch")||!strcmp(scenario,"gxts-readback-open")) {
        uint32_t frame[32]={0};frame[7]=0x23;frame[16]=0x202c2d84;rv_hook_observe(&root,7,frame);
        CHECK(frame[1]==(uint32_t)(uintptr_t)rv_close_07);
        CHECK(fault_used&&root.state==RV_DISABLED_UNTIL_REBOOT&&!file(tweak_path(0))&&!file(tweak_path(1)));
    } else {
        close_key(1);
        CHECK(root.state==RV_READY&&!ig_host_panel()->open&&writes==w&&renames==renamed);
        current(0);no_temporary_leases();
    }
    puts("TWEAK_FAILURE_PASS no_bad_formal_GXTS_published");return 1;
}
