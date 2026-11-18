/* Shared read path: no native colour eligibility is consulted here. */
static unsigned memory_decode(uint8_t p[40],EngRecipeRef *ref,UvLevels *t,unsigned *user)
{
    const uint8_t *entry;const uint16_t *s;unsigned index,i,kind;uint16_t f[33];
    for(i=0;i<40&&!p[i];++i){}if(i==40)return 2;
    kind=mem_load(p,f);
    if(kind>2)return kind;
    /* The slot of this unit; a g172 record fills only the slot of its own unit. */
    s=f+11u*g->data.unit;index=s[0];
    if(!index)return 4;
    t->v[0]=s[1];for(i=1;i<10;++i)t->v[i]=(int16_t)((int)s[i+1]-9);
    clear(ref,sizeof(*ref));*user=0;ref->unit=g->data.unit;
    if(index>=1&&index<=8)ref->slot=(uint8_t)index;
    else if(index>=MEMORY_FX_FIRST&&index<MEMORY_FX_FIRST+GXR2_FX_MAX){
        index-=MEMORY_FX_FIRST;entry=fx_entry(&g->data.view,index);
        if(!entry)return 5;
        if(!(fx_unit_mask(&g->data.view,entry)>>g->data.unit&1u))return 4;
        ref->slot=entry[0];ref->effect=(uint16_t)(index+1);copy(ref->effect_crc,entry+4,4);
    }else if(index>=MEMORY_USER_FIRST&&index<MEMORY_USER_FIRST+MEMORY_USERS){
        index-=MEMORY_USER_FIRST;entry=uv_user(&g->data.view,index);
        if(!entry)return 5;
        ref->slot=entry[0];*user=index+1;
    }else return 5;
    eng_identity(eng_record(&g->data,ref->slot),ref->identity);
    if(kv_data_request(&g->data.knobs,g->data.unit,ref->slot,t,&g->work.request))return 6;
    return 1;
}
void eng_read_saved(void)
{
    EngRecipeRef ref;UvLevels levels;unsigned user=0;uint8_t record[40];int32_t status;
    if(g->restore_done)return;
    g->memory_result=7;
    status=settings_info();
    if(status!=RV_OK)return;
    if(io.info.header.version==1&&io.info.header.bytes==sizeof(io.info)&&!io.info.header.flags&&io.info.token&&
       io.info.length==0x1000&&io.info.settings_epoch==g->epoch.settings&&memory_op(4,0,0,0)==RV_OK){
        copy(record,io.request.record.record,40);
        g->memory_result=(uint8_t)memory_decode(record,&ref,&levels,&user);
        g->restore_done=1;
        if(g->memory_result==1){g->saved.ref=ref;g->saved.levels=levels;g->saved.user=(uint8_t)user;}
    }
    if(settings_release()!=RV_OK){g->memory_result=7;g->restore_done=0;}
}
static int boot_s_valid(void)
{
    const volatile uint8_t *S=eng_wire_pointer(io.info.address);
    return S&&io.info.length==0x1000&&io.info.settings_epoch==g->epoch.settings&&
        S[14]==0x0d&&S[15]==0x24&&!S[8]&&S[0x36e]==1&&S[0x6dd]==9&&S[0x6de]==9;
}
static int boot_plan_equal(const RvSettingsPlan *p)
{
    const volatile uint8_t *S=eng_wire_pointer(io.info.address);unsigned i;
    if(!S||!eng_boot_check())return 0;
    for(i=0;i<p->count;++i)if(S[p->writes[i].offset]!=p->writes[i].value)return 0;
    return 1;
}
static int boot_acquire(void)
{
    return settings_info()==RV_OK&&io.info.token&&
        io.info.header.version==1&&io.info.header.bytes==sizeof(io.info)&&!io.info.header.flags&&boot_s_valid();
}
static int boot_release(void)
{return settings_release()==RV_OK;}
static int boot_verify(const RvSettingsPlan *p)
{
    int mismatch=0;
    return live_check(&mismatch,0)==ENG_OK&&!mismatch&&boot_plan_equal(p)&&fresh();
}
/* 1: the sentence stands or the user text was left alone.
 * 2: colour was not changed, and the old 47 bytes were written back and read.
 * 0: stop. A copyright match after colour already changed is not a 2. */
static int boot_put_back(volatile uint32_t *word,const uint8_t saved[47],int *wrote,unsigned colour_changed)
{
    if(!*wrote)return 0;
    if((*word&4u)&&io.info.token&&fresh()&&eng_boot_check()&&copyright_store(saved)==RV_OK&&copyright_matches(saved)){
        *wrote=0;
        /* The saved rows were replaced when the new colour was accepted.
         * Putting the copyright back does not put that colour back. */
        return colour_changed?0:2;
    }
    *wrote=0;return 0;
}
static int boot_copyright_settle(volatile uint32_t *word,const EngRecipeRef *ref,const UvLevels *levels,uint8_t saved[47],int *wrote,unsigned colour_changed)
{
    uint8_t expect[47];
    *word|=4u;__asm__ __volatile__("":::"memory");
    if(!copyright_publish(ref,levels,saved,wrote))return boot_put_back(word,saved,wrote,colour_changed);
    if(!*wrote)return (fresh()&&eng_boot_check())?1:0;
    copyright_sentence(ref,levels,expect);
    if(copyright_matches(expect)&&fresh()&&eng_boot_check())return 1;
    return boot_put_back(word,saved,wrote,colour_changed);
}
static int boot_release_committed(volatile uint32_t *word,unsigned *acquired)
{
    if(!boot_release()){g->uncertain=1;g->bound=0;*acquired=0;return 0;}
    *acquired=0;*word&=~4u;return 1;
}
static void boot_commit(const EngRecipeRef *ref,const UvLevels *t,unsigned user)
{
    g->current=g->confirmed=*ref;g->tweak=g->confirmed_tweak=*t;
    g->current_user=g->confirmed_user=(uint8_t)user;
    g->baseline=g->live_verified=g->committed=g->confirmed_valid=1;
    g->boot_committed=1;g->auto_result=1;diag_engine(4);
    g->uncertain=g->write_started=g->snapshot_fault=g->settings_pending=g->s_unwritten=g->previewing=0;
    g->stage=ENG_STAGE_COMMITTED;publish();
}
EngStatus __attribute__((noinline)) eng_boot_run(volatile uint32_t *word,unsigned *detail)
{
    EngRecipeRef ref={0};UvLevels levels;RvSettingsPlan restore;uint8_t record[40],wb[2],csaved[47];
    unsigned user=0,i,acquired=0,finished=0;int mismatch=0,cwrote=0;EngStatus status=ENG_OK;
    *detail=2;diag_engine(1);eng_read_saved();
    if(!g->ready||!g->bound||g->busy||g->uncertain||!eng_boot_check())return ENG_STALE;
    /* This power cycle already committed. A repeat entry must not rewrite
     * settings or colour; a new cycle starts with boot_committed clear. */
    if(g->boot_committed){*detail=1;return ENG_OK;}
    g->busy=g->boot_active=1;w_count=0;t_seen=-1;
    acquired=1;
    if(!boot_acquire()){diag_reason(20,BF_NATIVE);goto clean;}
    if(memory_op(4,0,0,0)!=RV_OK){diag_reason(21,BF_RECORD);goto clean;}
    copy(record,io.request.record.record,40);
    if(memory_op(4,0,0,0)!=RV_OK||!equal(record,io.request.record.record,40)){diag_reason(30,BF_EPOCH);goto clean;}
    if(!boot_release()){status=ENG_STALE;acquired=0;goto clean;}acquired=0;
    /* Empty slot or a retained older catalogue has no saved recipe. Apply 04.
     * Corrupt and unknown tails are stopped by the outer record gate. */
    if(g->saved.ref.slot){ref=g->saved.ref;levels=g->saved.levels;user=g->saved.user;}
    else{
        clear(&ref,sizeof(ref));ref.unit=g->data.unit;ref.slot=4;user=0;
        eng_identity(eng_record(&g->data,4),ref.identity);
        clear(&levels,sizeof(levels));levels.v[0]=100;
    }
    if(compute(&ref,&levels,wb)!=ENG_OK){diag_reason(21,BF_RECORD);goto clean;}
    acquired=1;
    if(!boot_acquire()){diag_reason(20,BF_NATIVE);goto clean;}
    if(memory_op(4,0,0,0)!=RV_OK||!equal(record,io.request.record.record,40)){diag_reason(30,BF_EPOCH);goto clean;}
    /* Read both the complete unit state and S twice before any colour write. */
    if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2||!boot_s_valid()){diag_reason(22,BF_ROWS);goto clean;}
    mismatch=0;
    if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2||!boot_s_valid()||!fresh()){diag_reason(22,BF_ROWS);goto clean;}
    g->baseline=g->live_verified=1;
    make_plan(&ref,wb,io.info.token,&io.request.plan);restore=io.request.plan;
    for(i=0;i<restore.count;++i)restore.writes[i].value=((volatile uint8_t *)eng_wire_pointer(io.info.address))[restore.writes[i].offset];
    /* A full plan is retained even when its delta is empty. op 6 always
     * checks the stock lock before the first possible W. */
    if(svc(RV_SETTINGS,6,0,0,&io.request.plan,sizeof(io.request.plan),io.request.plan.count,&io.reply)!=RV_OK){diag_reason(23,BF_LOCK);goto clean;}
    if(equal(g->staging,g->live,552)&&boot_plan_equal(&io.request.plan)){
        /* Colour and settings still match the captured state. Protection
         * stays up through the store, the preimage restore, and release.
         * It drops only after release returns success. */
        {int settled=boot_copyright_settle(word,&ref,&levels,csaved,&cwrote,0);
         if(!settled){status=ENG_UNCERTAIN;g->uncertain=1;g->bound=0;goto clean;}
         if(settled==2){if(!boot_release_committed(word,&acquired)){status=ENG_UNCERTAIN;goto clean;}*detail=2;status=ENG_OK;finished=1;goto clean;}
         if(!boot_release_committed(word,&acquired)){status=ENG_UNCERTAIN;goto clean;}}
        finished=1;boot_commit(&ref,&levels,user);*detail=1;goto clean;
    }
    if(!eng_boot_check()){status=ENG_STALE;goto clean;}
    *word|=4u;__asm__ __volatile__("":::"memory");
    diag_engine(2);status=deep(1);
    if(status==ENG_OK&&svc(RV_SETTINGS,2,0,0,&io.request.plan,sizeof(io.request.plan),io.request.plan.count,&io.reply)==RV_OK&&
       svc(RV_PREVIEW,1,0,0,0,0,0,&io.reply)==RV_OK){
        copy(g->live,g->staging,552);
        if(boot_verify(&io.request.plan)){
            /* Colour and settings now match the new plan. A torn copyright
             * can be put back, but that does not put the colour back, so it
             * is not a finished restore of the old state. */
            {int settled=boot_copyright_settle(word,&ref,&levels,csaved,&cwrote,1);
             if(!settled){status=ENG_UNCERTAIN;g->uncertain=1;g->bound=0;goto clean;}
             if(settled==2){if(!boot_release_committed(word,&acquired)){status=ENG_UNCERTAIN;goto clean;}*detail=3;status=ENG_OK;finished=1;boot_commit(&ref,&levels,0);goto clean;}
             if(!boot_release_committed(word,&acquired)){status=ENG_UNCERTAIN;goto clean;}}
            finished=1;boot_commit(&ref,&levels,user);*detail=1;status=ENG_OK;goto clean;
        }
    }
    /* CANCEL has one compensation pass, and only while release has not run.
     * A release that already returned is not a token for another store. */
    if(!acquired){status=ENG_UNCERTAIN;g->uncertain=1;goto clean;}
    status=ENG_UNCERTAIN;diag_reason(31,BF_COLOUR);diag_engine(3);
    if(!eng_boot_check())goto clean;
    copy(g->staging,g->stock,552);
    if(deep(1)!=ENG_OK)goto clean;
    io.request.plan=restore;
    if(svc(RV_SETTINGS,2,0,0,&io.request.plan,sizeof(io.request.plan),io.request.plan.count,&io.reply)!=RV_OK||
       svc(RV_PREVIEW,1,0,0,0,0,0,&io.reply)!=RV_OK)goto clean;
    copy(g->live,g->stock,552);
    if(!boot_verify(&io.request.plan)||!boot_s_valid())goto clean;
    clear(&ref,sizeof(ref));ref.unit=g->data.unit;ref.slot=4;
    eng_identity(eng_record(&g->data,4),ref.identity);clear(&levels,sizeof(levels));levels.v[0]=100;
    {int settled=boot_copyright_settle(word,&ref,&levels,csaved,&cwrote,0);
     if(!settled){status=ENG_UNCERTAIN;g->uncertain=1;g->bound=0;goto clean;}
     /* Colour, settings and copyright were each put back and read. The
      * active recipe stays uncommitted: this pass cancelled the change. */
     if(settled==2){if(!boot_release_committed(word,&acquired)){status=ENG_UNCERTAIN;goto clean;}*detail=2;status=ENG_OK;finished=1;goto clean;}
     if(!boot_release_committed(word,&acquired)){status=ENG_UNCERTAIN;goto clean;}}
    finished=1;boot_commit(&ref,&levels,0);*detail=3;status=ENG_OK;
 clean:
    /* The preimage store is legal only before release, with the token and
     * the protection bit still valid. It uses that same token and does not
     * acquire another. After release, leave the bytes alone. A matching
     * copyright read still leaves colour and settings where they are. */
    if(cwrote>0&&status!=ENG_OK&&acquired&&(*word&4u)&&io.info.token&&fresh()&&eng_boot_check()&&
       copyright_store(csaved)==RV_OK&&copyright_matches(csaved))cwrote=0;
    else if(cwrote>0&&status!=ENG_OK){cwrote=0;g->uncertain=1;g->bound=0;status=ENG_UNCERTAIN;}
    if(acquired&&!boot_release()){g->uncertain=1;g->bound=0;status=ENG_UNCERTAIN;}
    acquired=0;cwrote=0;
    if(*word&4u){g->uncertain=1;status=ENG_UNCERTAIN;}
    /* An unfinished boot must not be retried by a later call as if it never started. */
    if(!finished){g->uncertain=1;if(status==ENG_OK)status=ENG_UNCERTAIN;}
    if(status!=ENG_OK)diag_reason(status==ENG_STALE?30:31,status==ENG_STALE?BF_EPOCH:BF_COLOUR);
    g->busy=g->boot_active=0;return status;
}
