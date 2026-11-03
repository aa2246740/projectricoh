/* Independent checks of the mutation boundary, snapshot lifetime and card state. */
static void review_cases(const uint8_t *old,unsigned old_bytes)
{
    unsigned kind,depth,capacity,before,i;uint32_t f[32],g[32],snapshot;
    uint8_t state[32],desc[72],views[64];
    for(kind=0;kind<4;kind++)for(depth=1;depth<=2;depth++){
        clean();ready(0);
        if(kind==1)native_writer_exposure();
        if(kind==2)native_writer_white_balance();
        if(kind==3)native_writer_image();
        RV_BYTE(RV_NATIVE_VIEWS)=depth==1?32:33;
        RV_BYTE(RV_NATIVE_VIEWS+8)=33;RV_WORD(RV_NATIVE_VIEWS+12)=0x2022f71c;
        RV_BYTE(0x205a27d4)=depth;
        memcpy(state,RV_PTR(0x2022f71c),32);memcpy(desc,RV_PTR(0x2022f56c),72);
        memcpy(views,RV_PTR(RV_NATIVE_VIEWS),64);
        before=rpc_calls;memset(f,0,sizeof(f));rv_hook_observe(&root,1,f);
        CHECK(rpc_calls==before&&!rpc_w&&!previews);
        CHECK(!memcmp(views,RV_PTR(RV_NATIVE_VIEWS),64));
        for(i=0;i<32;i++)if(unit==1||(i!=9&&i!=10))CHECK(state[i]==RV_BYTE(0x2022f71c+i));
        for(i=0;i<72;i++)if(unit==1||(i<60||i>64))CHECK(desc[i]==RV_BYTE(0x2022f56c+i));
        if(unit==1){CHECK(!f[1]&&RV_BYTE(0x2022f5ac)==7);continue;}
        CHECK(f[1]&&RV_BYTE(0x2022f5ac)==8&&session()->rows==8);
        snapshot=root.ui_block;CHECK(snapshot&&rv_ui_snapshot(&root)->state[0]==5);
        memset(g,0,sizeof(g));rv_hook_observe(&root,2,g);CHECK(g[7]==f[15]);
        /* The complete native writer/consumer trace is replayed separately. */
        native_writer_image();RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=g[7];
        RV_BYTE(RV_NATIVE_VIEWS)=33;
        RV_WORD(RV_NATIVE_VIEWS+4)=0x2022f71c;RV_BYTE(0x205a27d4)=1;
        RV_BYTE(0x2022f727)=0x61;RV_BYTE(0x2022f728)=0x62;
        for(i=0;i<5;i++)RV_BYTE(0x2022f729+i)=(uint8_t)(0x70+i);
        open_fn2();CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==snapshot);
        CHECK(rv_ui_snapshot(&root)->state[11]==0x61&&rv_ui_snapshot(&root)->state[12]==0x62);
        for(i=0;i<5;i++)CHECK(rv_ui_snapshot(&root)->state[13+i]==0x70+i);
        close_menu();CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==0x2022f71c);
        CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7);
        CHECK(owned(snapshot,1968));rv_retire(&root,RV_CHECK_SESSION);CHECK(owned(snapshot,1968));
    }
    for(capacity=236;capacity<=256;capacity++){
        clean();ready(0);session()->context.ui_state_capacity=capacity;
        memset(RV_PTR(session()->context.ui_state_address),0xa5,256);
        CHECK(rv_native_seed(&session()->context)==RV_OK);
        for(i=236;i<256;i++)CHECK(RV_BYTE(session()->context.ui_state_address+i)==0xa5);
    }
    /* Preserve the first H01 diagnostic by closing without a cursor event. */
    if(unit!=1){
        clean();ready(0);menu();native_writer_image();close_menu();
        CHECK(!rpc_calls&&!has_recipe()&&file("/ATA1/GXRBX0.BIN"));
        CHECK(file("/ATA1/GXRBX0.BIN")->bytes[2460]==0);
        clean();ready(0);menu();native_writer_image();select_slot(2);close_menu();
        CHECK(!rpc_calls&&!has_recipe()&&file("/ATA1/GXRBX0.BIN")->bytes[2460]==5);
        puts("REVIEW first_MENU_exit seed_kind=0 no_RPC=1; after_cursor seed_kind=5 last_seed_only=1");
    }
    /* Mirror today's stale OK, then show the corrected procedure converges. */
    clean();CHECK(be32(old+28)==113);put_file("/IROM/GXRCE0.DAT",old,old_bytes);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
    put_file("/ATA1/GXRCE.OK",old,old_bytes);rename_refuse_existing=1;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_CARD);
    memset(f,0,sizeof(f));flush_allowed=1;rv_hook_observe(&root,1,f);flush_allowed=0;
    CHECK(ig_host_install_status()==RV_UNCERTAIN&&root.state==RV_DISABLED_UNTIL_REBOOT);
    CHECK(file("/IROM/GXRCE0.DAT")&&!memcmp(file("/IROM/GXRCE0.DAT")->bytes,old,old_bytes));
    CHECK(file("/IROM/GXRCE1.DAT")&&!memcmp(file("/IROM/GXRCE1.DAT")->bytes,new_raw,new_bytes));
    CHECK(file("/ATA1/GXRCE.OK")&&!memcmp(file("/ATA1/GXRCE.OK")->bytes,old,old_bytes));
    printf("REVIEW stale_OK install=%d state=%u DAT_exists=%u OK_exists=%u\n",
        ig_host_install_status(),root.state,file("/ATA1/GXRCE.DAT")!=0,file("/ATA1/GXRCE.OK")!=0);
    printf("REVIEW bounded_private_seed capacities=21 mutation_cases=8 snapshot_retained=1\n");
}
