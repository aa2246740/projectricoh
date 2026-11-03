/* Included by the original fault-injection harness. No native code executes. */
static uint32_t scratch_address(void)
{return rv_session(&root)->context.state_address+5200;}
static RvLeaseInfo new_lease(uint32_t bytes,uint32_t usage)
{
    RvRequest q=request();RvReply p;uint32_t address=scratch_address();RvLeaseInfo result;
    buffer_header(RV_PTR(address),32);q.args[8]=bytes;q.args[9]=usage;q.args[10]=address;q.args[11]=32;
    CHECK(rv_api.call(RV_LEASE,1,&q,&p)==RV_OK&&p.status==RV_OK&&p.actual==32&&p.token);
    memcpy(&result,RV_PTR(address),sizeof(result));
    CHECK(result.token==p.token&&result.length==bytes&&result.usage==usage&&result.heap_epoch==root.epoch[RV_HEAP_E]);
    return result;
}
static void service_fix_checks(void)
{
    RvRequest q;RvReply p;RvSession *s;RvLeaseInfo l,*info;RvEpochSnapshot *epochs;
    uint32_t scratch,before,i,original;uint8_t saved[60];
    setup();CHECK(load()==RV_OK);root.inflight=1;s=rv_session(&root);scratch=scratch_address();
    l=new_lease(256,2);q=request();q.args[8]=l.token;q.args[10]=scratch;q.args[11]=32;
    buffer_header(RV_PTR(scratch),32);
    CHECK(rv_api.call(RV_LEASE,3,&q,&p)==RV_OK&&p.actual==32&&p.token==l.token);
    info=RV_PTR(scratch);CHECK(info->base==l.base&&info->length==256&&info->boot_epoch==root.epoch[RV_BOOT_E]);
    /* Target lease and output lease are independent. */
    q.args[1]=l.token;CHECK(rv_api.call(RV_LEASE,3,&q,&p)==RV_RANGE);
    q.args[1]=root.lease;q.args[8]=0;CHECK(rv_api.call(RV_LEASE,3,&q,&p)==RV_STALE);
    q.args[8]=l.token;s->leases[1].inverse^=1;CHECK(rv_api.call(RV_LEASE,3,&q,&p)==RV_STALE);s->leases[1].inverse^=1;
    q=request();q.args[1]=l.token;before=free_calls;
    s->view_lease=l.token;CHECK(rv_api.call(RV_LEASE,2,&q,&p)==RV_BUSY&&free_calls==before);s->view_lease=0;
    root.inflight=2;CHECK(rv_api.call(RV_LEASE,2,&q,&p)==RV_BUSY&&free_calls==before);root.inflight=1;
    for(i=0;i<7;++i){
        original=s->leases[1].base;
        switch(i){
        case 0:RV_BYTE(l.base-8)=0;break;
        case 1:RV_BYTE(l.base-8)=2;break;
        case 2:RV_WORD(l.base-12)=l.base;break;
        case 3:RV_WORD(l.base-4)=0;break;
        case 4:RV_WORD(l.base-4)=RV_WORD(0x200c0dc4);break;
        case 5:s->leases[1].base=l.base+1;break;
        case 6:s->leases[1].base=RV_WORD(0x200d348c);break;
        }
        CHECK(rv_api.call(RV_LEASE,2,&q,&p)!=RV_OK&&p.status<0&&free_calls==before&&s->leases[1].token==l.token);
        s->leases[1].base=original;RV_BYTE(l.base-8)=1;RV_WORD(l.base-12)=0;RV_WORD(l.base-4)=256;
    }
    free_refuse=1;CHECK(rv_api.call(RV_LEASE,2,&q,&p)==RV_IO&&p.status==RV_IO&&p.detail==0x101);
    CHECK(free_calls==before+1&&frees==0&&s->leases[1].token==l.token&&RV_BYTE(l.base-8)==1);
    free_refuse=0;CHECK(rv_api.call(RV_LEASE,2,&q,&p)==RV_OK&&p.status==RV_OK&&p.detail==0x100);
    CHECK(frees==1&&s->leases[1].token==0&&RV_BYTE(l.base-8)==0);
    before=free_calls;CHECK(rv_api.call(RV_LEASE,2,&q,&p)==RV_STALE&&free_calls==before);
    /* Old binding epochs must not hide fresh snapshots. */
    q=request();rv_notify(&root,19,0,1);rv_notify(&root,13,0,1);
    q.args[10]=scratch;q.args[11]=60;buffer_header(RV_PTR(scratch),60);
    CHECK(rv_api.call(RV_EPOCHS,12,&q,&p)==RV_OK&&p.status==RV_OK&&p.actual==60);
    epochs=RV_PTR(scratch);CHECK(epochs->session_token==root.lease&&!memcmp(epochs->epochs,root.epoch,48));
    q.args[11]=36;buffer_header(RV_PTR(scratch),36);
    CHECK(rv_api.call(RV_UNIT,1,&q,&p)==RV_OK&&p.actual==36);
    {RvUnitInfo *u=RV_PTR(scratch);CHECK(u->valid&&u->unit_epoch==root.epoch[RV_UNIT_E]&&u->link_epoch==root.epoch[RV_LINK_E]&&!memcmp(u->name,units[0].name,8));}
    q.args[11]=16;CHECK(rv_api.call(RV_SD_ID,1,&q,&p)==RV_OK&&p.actual==16&&p.epoch==root.epoch[RV_SD_E]);
    CHECK(RV_WORD(scratch)==1&&RV_WORD(scratch+12)==4);
    q.args[11]=24;buffer_header(RV_PTR(scratch),24);
    CHECK(rv_api.call(RV_SETTINGS,1,&q,&p)==RV_OK&&p.actual==24);
    {RvSettingsInfo *u=RV_PTR(scratch);CHECK(u->token&&u->address==0x20600000&&u->length==4096&&u->settings_epoch==root.epoch[RV_S_E]);}
    q.args[8]=32;q.args[9]=2;q.args[11]=32;buffer_header(RV_PTR(scratch),32);before=allocs;
    CHECK(rv_api.call(RV_LEASE,1,&q,&p)==RV_STALE&&allocs==before);
    q=request();q.args[10]=scratch;q.args[11]=60;buffer_header(RV_PTR(scratch),60);memcpy(saved,RV_PTR(scratch),60);
    --q.args[2];CHECK(rv_api.call(RV_EPOCHS,12,&q,&p)==RV_STALE&&!memcmp(saved,RV_PTR(scratch),60));
    q=request();q.args[10]=scratch;q.args[11]=36;buffer_header(RV_PTR(scratch),36);unit_inject=1;
    CHECK(rv_api.call(RV_UNIT,1,&q,&p)==RV_STALE&&p.actual==0&&!rv_session(&root));
    /* A heap notification during free must not read the old header again. */
    setup();CHECK(load()==RV_OK);root.inflight=1;l=new_lease(256,2);q=request();q.args[1]=l.token;
    inject_kind=7;inject_n=kind_counts[7]+1;inject_hook=16;
    CHECK(rv_api.call(RV_LEASE,2,&q,&p)==RV_STALE&&!rv_session(&root)&&!stale_frees);
    setup();CHECK(load()==RV_OK);root.inflight=1;s=rv_session(&root);
    CHECK(s->context.lease_max_bytes==65536);
    l=new_lease(65536,2);scratch=scratch_address();q=request();q.args[8]=l.token;q.args[10]=scratch;q.args[11]=32;
    buffer_header(RV_PTR(scratch),32);CHECK(rv_api.call(RV_LEASE,3,&q,&p)==RV_OK&&p.actual==32&&((RvLeaseInfo *)RV_PTR(scratch))->length==65536);
    q=request();q.args[1]=l.token;CHECK(rv_api.call(RV_LEASE,2,&q,&p)==RV_OK&&p.detail==0x100);
    q=request();q.args[8]=65537;q.args[9]=2;q.args[10]=scratch;q.args[11]=32;buffer_header(RV_PTR(scratch),32);before=allocs;
    CHECK(rv_api.call(RV_LEASE,1,&q,&p)==RV_ARGUMENT&&allocs==before);
    q=request();q.args[10]=scratch;q.args[11]=9;memcpy(RV_PTR(scratch),"123456789",9);
    CHECK(rv_api.call(RV_CRC32,1,&q,&p)==RV_OK&&p.detail==0xcbf43926u);
    CHECK(rv_api.call(RV_CACHE,1,&q,&p)==RV_OK);
}
static RvRequest file_request(uint32_t token)
{RvRequest q={1,64,0,{0}};q.args[0]=root.epoch[RV_IO_E];q.args[1]=token;return q;}
static void eof_checks(void)
{
    unsigned over;RvRequest q;RvReply p;uint32_t token,done,n,io,before;
    for(over=0;over<2;++over){
        setup();CHECK(load()==RV_OK);root.inflight=1;io=rv_session(&root)->context.state_address;
        memset(files[0]+length,0,65536u+1-length);file_length[0]=65536u+over;
        q=file_request(0);q.args[2]=1;q.args[5]=2;
        CHECK(rv_api.call(RV_STORAGE,2,&q,&p)==RV_OK&&p.token);token=p.token;done=0;
        while(done<65536u){
            q=file_request(token);n=65536u-done;if(n>512)n=512;q.args[6]=io;q.args[7]=n;
            CHECK(rv_api.call(RV_STORAGE,4,&q,&p)==RV_OK&&p.actual&&p.actual<=n);done+=p.actual;
        }
        CHECK(done==65536u);q=file_request(token);q.args[6]=io;q.args[7]=2;
        before=kind_counts[3];CHECK(rv_api.call(RV_STORAGE,4,&q,&p)==RV_RANGE&&kind_counts[3]==before);
        q.args[7]=1;
        CHECK(rv_api.call(RV_STORAGE,4,&q,&p)==(over?RV_RANGE:RV_EOF)&&p.actual==0);
        before=kind_counts[3];CHECK(rv_api.call(RV_STORAGE,4,&q,&p)==(over?RV_RANGE:RV_EOF)&&kind_counts[3]==before);
        q=file_request(token);before=closes;CHECK(rv_api.call(RV_STORAGE,6,&q,&p)==RV_OK&&closes==before+1);
        CHECK(rv_api.call(RV_STORAGE,6,&q,&p)==RV_STALE&&closes==before+1&&active==0);
    }
}
static void private_context_checks(void)
{
    RvSession *s;RvPrivateContext *c,copy;RvRequest q;RvReply p;uint32_t nonce,address,state,ui,i;
    setup();CHECK(load()==RV_OK);s=rv_session(&root);c=&s->context;address=root.block+offsetof(RvSession,context);
    nonce=c->nonce;state=c->state_address;ui=c->ui_state_address;
    CHECK(nonce&&c->root_address==RV_ROOT&&c->root_bytes==256&&c->session_bytes==sizeof(*s));
    CHECK(c->lease_max_bytes==65536);
    CHECK(c->state_bytes==6144&&c->ui_state_capacity==256&&c->ui_state_bytes==0);
    RV_WORD(state)=0x12345678;RV_WORD(state+6140)=0x87654321;RV_WORD(ui)=0xaabbccdd;
    for(i=0;i<8;++i){
        q=request();engine_result=RV_PASS;
        CHECK(rv_engine(&root,264+4*i,&q,&p)==RV_PASS&&q.args[10]==address&&q.args[11]==sizeof(*c));
        CHECK(c==&s->context&&c->nonce==nonce&&c->state_address==state&&c->ui_state_address==ui);
        CHECK(RV_WORD(state)==0x12345678&&RV_WORD(state+6140)==0x87654321&&RV_WORD(ui)==0xaabbccdd);
    }
    copy=*c;CHECK(rv_services_init(&copy)==0);c->nonce=0;CHECK(rv_services_init(c)==0);c->nonce=nonce;
    c->image_bytes++;CHECK(rv_services_init(c)==0);c->image_bytes--;
    c->ui_state_bytes=257;CHECK(rv_services_init(c)==0);c->ui_state_bytes=0;
    rv_notify(&root,19,0,0);CHECK(load()==RV_OK&&&rv_session(&root)->context==c&&c->nonce==nonce);
    CHECK(RV_WORD(state)==0x12345678&&RV_WORD(ui)==0xaabbccdd);
    rv_notify(&root,16,0,0);CHECK(load()==RV_OK);
    CHECK(rv_session(&root)->context.nonce!=nonce&&rv_session(&root)->context.state_address!=state);
}
static void tier_two_checks(void)
{
    static const unsigned ids[6]={13,14,23,25,31,32};
    static const uint32_t masks[6]={
        (1u<<RV_S_E)|(1u<<RV_VIEW_E),(1u<<RV_S_E)|(1u<<RV_VIEW_E),
        (1u<<RV_MODE_E)|(1u<<RV_S_E)|(1u<<RV_VIEW_E),(1u<<RV_POWER_E)|(1u<<RV_LINK_E),
        (1u<<RV_IROM_E)|(1u<<RV_SD_E)|(1u<<RV_IO_E),(1u<<RV_IROM_E)|(1u<<RV_IO_E)|(1u<<RV_UNIT_E)};
    unsigned i,j;RvRoot before;uint32_t count,frame[32]={0};
    for(i=0;i<6;++i){
        setup();CHECK(load()==RV_OK);root.grain=0x84;root.ui_restore[6]=0x20710000;before=root;count=calls;
        frame[11]=17;rv_hook_observe(&root,ids[i],frame);
        CHECK(root.state==before.state&&root.flags==before.flags&&root.grain==before.grain&&root.block==before.block&&root.event_head==before.event_head+1&&calls==count);
        CHECK(!memcmp(root.ui_restore,before.ui_restore,32)&&!memcmp(root.post,before.post,16));
        for(j=0;j<RV_EPOCH_COUNT;++j)CHECK(root.epoch[j]==before.epoch[j]+((masks[i]>>j)&1));
        CHECK(root.events[(root.event_head-1)&7].hook==ids[i]);
    }
}
static void claim_stock_view(void)
{
    root.ui_restore[0]=0x205a3000;root.ui_restore[1]=1;root.ui_restore[2]=tag_word(33);
    root.ui_restore[4]=0x20740000;root.ui_restore[6]=0x20741000;
    RV_WORD(0x205a3004)=root.ui_restore[4];RV_WORD(0x2022f5a8)=root.ui_restore[6];RV_BYTE(0x2022f5ac)=16;
}
static void stock_view(void)
{CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7&&RV_WORD(0x205a3004)==0x2022f71c);}
static void factory_checks(void)
{
    uint32_t f[32],original[32],i,n;
    setup();file_enabled[0]=file_enabled[1]=file_enabled[2]=0;
    for(i=0;i<32;++i)original[i]=0x10203040u+i;
    memcpy(f,original,sizeof(f));rv_hook_observe(&root,1,f);CHECK(!memcmp(f,original,sizeof(f))&&!engine_calls);stock_view();
    for(i=2;i<=10;++i){
        if(i==3||i==4||i==9)continue;
        memcpy(f,original,sizeof(f));rv_hook_observe(&root,i,f);CHECK(!memcmp(f,original,sizeof(f))&&!engine_calls);stock_view();
    }
    CHECK(active==0&&opens==closes&&!write_calls&&!rpc_w);
    setup();claim_stock_view();root.state=RV_FAILED;root.flags|=RF_STOP;
    memcpy(f,original,sizeof(f));rv_hook_observe(&root,1,f);CHECK(!memcmp(f,original,sizeof(f)));stock_view();
    setup();claim_stock_view();root.block=0x20704800;root.inverse=0;
    memcpy(f,original,sizeof(f));rv_hook_observe(&root,2,f);CHECK(!memcmp(f,original,sizeof(f)));stock_view();
    setup();CHECK(load()==RV_OK);rv_session(&root)->entries.menu_open=128;claim_stock_view();n=engine_calls;
    memcpy(f,original,sizeof(f));rv_hook_observe(&root,1,f);CHECK(!memcmp(f,original,sizeof(f))&&engine_calls==n);stock_view();
    setup();CHECK(load()==RV_OK);claim_stock_view();bad_reply=1;
    memcpy(f,original,sizeof(f));rv_hook_observe(&root,1,f);CHECK(!memcmp(f,original,sizeof(f))&&root.state==RV_FENCED);stock_view();
    setup();CHECK(load()==RV_OK);claim_stock_view();rv_notify(&root,16,0,0);stock_view();CHECK(!rv_session(&root));
    CHECK(!memcmp(root.pins,rv_pins,12));rv_reset(&root);CHECK(!memcmp(root.pins,rv_pins,12));
}
static void allocation_case(const char *name)
{
    CHECK(!allocated_without_header&&!allocation_with_fd&&max_active<=1&&!active&&opens==closes);
    printf("ALLOCATION %s declared=%u actual=%u bss=%u requested=%u attempts=%u allocations=%u frees=%u first=%u second=%u max_fd=%u opens=%u closes=%u ready=%u\n",
           name,rv_be32(files[0]+16),file_length[0],rv_be32(files[0]+116),last_requested,
           allocation_attempts,allocs,frees,allocations[0].length,allocations[1].length,max_active,opens,closes,root.state==RV_READY);
}
static void dynamic_allocation_checks(void)
{
    uint32_t expected,base,reloc,i;RvSession *s;RvRequest q;RvReply p;
    setup();CHECK(load()==RV_OK);s=rv_session(&root);expected=RV_SESSION_BYTES+((length+64+3)&~3u)+6144+256;
    CHECK(allocation_attempts==1&&last_requested==expected&&allocations[0].length==expected&&s->leases[0].length==expected&&expected<88836);
    CHECK(!allocated_without_header&&!allocation_with_fd&&max_active==1&&!active&&opens==closes);
    CHECK(s->context.state_address==s->image_address+((length+64+3)&~3u));
    CHECK(s->context.ui_state_address+256==root.block+expected);
    CHECK(s->generation==7&&s->source_bytes==length&&s->entry_offset==256);
    root.inflight=1;q=request();q.args[10]=s->context.ui_state_address+256;q.args[11]=1;
    CHECK(rv_api.call(RV_CRC32,1,&q,&p)==RV_RANGE);root.inflight=0;
    allocation_case("small");
    setup();rv_put32(files[0]+116,65);seal(files[0],length);CHECK(load()==RV_OK);s=rv_session(&root);base=s->image_address;
    CHECK(last_requested==RV_SESSION_BYTES+length+68+6144+256&&s->context.state_address==base+length+68);
    for(i=0;i<68;++i)CHECK(RV_BYTE(base+length+i)==0);
    CHECK(!(s->context.state_address&3)&&!(s->context.ui_state_address&3));
    allocation_case("bss_65");
    setup();rv_put32(files[0]+116,0);reloc=rv_be32(files[0]+144);rv_put32(files[0]+352,256);rv_put32(files[0]+reloc+4,256);seal(files[0],length);
    CHECK(load()==RV_OK&&last_requested==RV_SESSION_BYTES+length+6144+256);
    allocation_case("bss_zero");
    setup();files[0][length]=0x5a;file_length[0]=length+1;rv_put32(files[0]+16,length+1);rv_put32(files[0]+116,0);seal(files[0],length+1);
    CHECK(load()==RV_OK&&last_requested==RV_SESSION_BYTES+((length+4)&~3u)+6144+256);
    allocation_case("unaligned_file");
    setup();file_length[0]=length-1;CHECK(load()!=RV_OK);check_no_publish();
    CHECK(last_requested==expected&&allocs==1&&frees==1&&!allocation_with_fd);
    allocation_case("truncated");
    setup();file_length[0]=length+1;files[0][length]=0xa5;CHECK(load()!=RV_OK);check_no_publish();
    CHECK(last_requested==expected&&allocs==1&&frees==1);
    allocation_case("extra_byte");
    setup();rv_put32(files[0]+16,length+4);seal(files[0],length);CHECK(load()!=RV_OK);check_no_publish();
    CHECK(last_requested==expected+4&&allocs==1&&frees==1);
    allocation_case("declared_larger");
    setup();rv_put32(files[0]+16,65537);seal(files[0],length);CHECK(load()!=RV_OK);check_no_publish();CHECK(allocation_attempts==0);
    allocation_case("file_over_limit");
    setup();rv_put32(files[0]+116,81921-length);seal(files[0],length);CHECK(load()!=RV_OK);check_no_publish();CHECK(allocation_attempts==0);
    allocation_case("image_over_limit");
    setup();alloc_failure=1;CHECK(load()!=RV_OK);check_no_publish();CHECK(last_requested==expected&&allocation_attempts==1&&!allocation_with_fd&&!allocs&&opens==1&&closes==1);
    allocation_case("alloc_failure");
    setup();failed_full_open=1;CHECK(load()!=RV_OK);check_no_publish();CHECK(allocs==1&&frees==1&&opens==1&&closes==1);
    allocation_case("reopen_failure");
    setup();reopen_bss=81920-length;CHECK(load()!=RV_OK);check_no_publish();CHECK(last_requested==expected&&allocs==1&&frees==1);
    allocation_case("reopen_bss_change");
    setup();file_enabled[2]=1;files[2][320]^=1;CHECK(load()==RV_OK);s=rv_session(&root);
    CHECK(s->selected_source==RV_SOURCE_A&&allocs==2&&frees==1&&allocations[0].length==expected&&allocations[1].length==expected&&root.lease==2&&s->leases[0].token==2);
    CHECK(!allocation_with_fd&&opens==closes&&max_active==1);
    allocation_case("card_fallback");
    setup();file_enabled[1]=1;file_length[1]=length+16;memset(files[1]+length,0,16);rv_put32(files[1]+16,length+16);rv_put32(files[1]+116,257);rv_put32(files[1]+28,8);seal(files[1],length+16);files[1][320]^=1;
    CHECK(load()==RV_OK&&rv_session(&root)->selected_source==RV_SOURCE_A&&allocs==2&&frees==1);
    CHECK(allocations[0].length==RV_SESSION_BYTES+((length+16+257+3)&~3u)+6144+256&&allocations[1].length==expected);
    allocation_case("larger_irom_fallback");
    for(i=0;i<2;++i){
        setup();memset(files[0]+length,0,65536-length);file_length[0]=65536;rv_put32(files[0]+16,65536);rv_put32(files[0]+116,i?16384:0);seal(files[0],65536);
        CHECK(load()==RV_OK);s=rv_session(&root);
        CHECK(s->image_bytes==65536&&s->bss_bytes==(i?16384:0)&&last_requested==(i?88836:72452)&&s->leases[0].length==last_requested);
        CHECK(!allocation_with_fd&&max_active==1&&opens==closes&&!active);
        allocation_case(i?"file_64k_bss_16k":"file_64k_bss_zero");
    }
}
