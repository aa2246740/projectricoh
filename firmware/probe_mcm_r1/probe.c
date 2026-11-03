#include "probe.h"
static ProbeState n;
typedef struct {uint32_t before;uint32_t pairs[P0_PAIRS];uint32_t after;} ProbeWork;
_Static_assert(sizeof(ProbeWork)<=65536,"private scratch lease limit");
static const uint32_t lcounts[4]={4,64,512,4096},dcounts[4]={16384,65536,262144,1048576};
static const uint32_t binding_epochs[7]={RV_BOOT_E,RV_HEAP_E,RV_LINK_E,RV_UNIT_E,RV_MODE_E,RV_POWER_E,RV_S_E};

static uint32_t address(const void *p){return (uint32_t)(uintptr_t)p;}
static void error(unsigned code){n.error=code;n.phase=ERROR;n.ref_start=0;n.ref_count=0;n.budget=0;}
static int ingress(const RvApi *a,uint32_t token,const RvRequest *q,RvReply *r)
{
    RvPrivateContext *c;const RvApi *api;unsigned i;RvRoot *root;
    if(a||!q||!r||q->version!=1||q->bytes!=64||q->flags||q->args[0]!=token||
       !q->args[10]||q->args[11]!=sizeof(RvPrivateContext))return 0;
    pn_zero(r,sizeof(*r));r->version=1;r->bytes=32;r->status=RV_ARGUMENT;
    c=RV_PTR(q->args[10]);api=rv_services_init(c);
    if(!api||c->nonce!=token||(n.ctx&&n.ctx!=c)||n.busy)return 0;
    n.ctx=c;n.api=api;n.request=*q;r->status=RV_OK;
    root=RV_PTR(c->root_address);
    if(n.run)for(i=0;i<7;++i)if(n.binding[i]!=root->epoch[binding_epochs[i]]){n.ref_count=0;n.used=0;error(ERR_INVALID);break;}
    return 1;
}
static int call(unsigned id,unsigned op,void *buffer,uint32_t bytes,RvReply *r)
{
    RvRequest q=n.request;unsigned i;int32_t result;
    for(i=8;i<14;++i)q.args[i]=0;
    q.args[1]=n.ctx->state_lease;
    if(bytes){pn_copy(n.wire.bytes,buffer,bytes);q.args[10]=address(n.wire.bytes);q.args[11]=bytes;}
    if(id==RV_UI_LIST){q.args[9]=8;q.args[12]=8;}
    result=n.api->call(id,op,&q,r);
    if(result!=RV_OK||r->status!=RV_OK){if(result==RV_CONFLICT)n.error=ERR_P1;return 0;}
    if(bytes)pn_copy(buffer,n.wire.bytes,bytes);
    return 1;
}
static void text(unsigned row,const char *s){unsigned i;for(i=0;i<39&&s[i];++i)n.rows[row][i]=s[i];n.rows[row][i]=0;}
static void number(unsigned row,const char *prefix,uint32_t value)
{
    char rev[10];unsigned i=0,j=0;text(row,prefix);while(n.rows[row][j])++j;
    do{rev[i++]=(char)('0'+value%10);value/=10;}while(value);
    while(i&&j<39)n.rows[row][j++]=rev[--i];
    n.rows[row][j]=0;
}
static void status(unsigned row,const char *prefix,unsigned code)
{
    static const char *const names[]={"READY","OK","CHANGED","READ ERROR"};
    unsigned j=0,k=0;text(row,prefix);while(n.rows[row][j])++j;
    if(code>3)code=3;
    while(names[code][k]&&j<39)n.rows[row][j++]=names[code][k++];
    n.rows[row][j]=0;
}
static unsigned result_count(void){return n.admit_l+n.admit_d+n.used;}
static ProbeSample *result_at(unsigned index)
{
    if(index<n.admit_l)return &n.admission[index];
    index-=n.admit_l;
    if(index<n.admit_d)return &n.admission[4+index];
    return &n.samples[index-n.admit_d];
}
static void rows(void)
{
    ProbeSample *sample;ProbeReference *ref;unsigned i;
    for(i=0;i<8;++i)text(i," ");
    if(!n.is50){for(i=0;i<8;++i)text(i,"50MM ONLY");return;}
    if(n.page==PAGE_MAIN){
        status(0,"BASE ",n.baseline_status);number(1,"TIME refs ",n.ref_count);
        text(2,n.phase==DONE?(n.low_res?"LUT DONE LOW RES":"LUT DONE"):n.ref_count<2?"LUT NEED 2 REFS":"LUT DOWN TO RUN");
        number(3,"RESULTS ",result_count());text(4,"REF HISTORY");text(5,"33 NOT FIT");
        text(6,"MCM OMITTED");text(7,"MCM1 " PROBE_ID);
        if(n.error)number(7,n.error==ERR_P1?"P1 REJECT ":"ERROR ",n.error);
        return;
    }
    if(n.page==PAGE_REF){
        text(0,n.phase==REF_RUN?"REF RUN RAW TICK":"REF INVALID");number(1,"RUN ",n.run);
        text(2,"PHONE about 30 seconds");text(3,"START saved in REF HISTORY");
        text(4,"OK stop, then reopen ADJ");text(5,"MENU cancels this run");
        text(6,"Tick unit needs stopwatch");text(7,"MCM1 " PROBE_ID);return;
    }
    if(n.page==PAGE_HISTORY){
        if(!n.ref_count){text(0,"REF NONE");text(1,"TIME needs a new reference");text(6,"OK main");number(7,"ERROR ",n.error);return;}
        if(n.history_index>=n.ref_count)n.history_index=0;
        ref=&n.refs[n.history_index];text(0,ref->valid?"REF DONE RAW TICK":"REF NONE");
        number(1,"RUN ",ref->run);number(2,"START ",ref->start);number(3,"END ",ref->end);
        number(4,"DELTA ",ref->delta);number(5,"REF INDEX ",n.history_index+1);
        text(6,"DOWN next / OK main");number(7,"ERROR ",n.error);return;
    }
    if(n.page==PAGE_RESULT&&result_count()){
        if(n.result_index>=result_count())n.result_index=0;
        sample=result_at(n.result_index);
        number(0,sample->valid?(sample->kind==2?"L17 RAW TICK RUN ":sample->kind==1?"D RAW TICK RUN ":"E RAW TICK RUN "):"INVALID SAMPLE RUN ",n.run);
        if(n.error)number(0,sample->kind==2?"INVALID L17 RAW TICK RUN ":sample->kind==1?"INVALID D RAW TICK RUN ":"INVALID E RAW TICK RUN ",n.run);
        number(1,"N ",sample->count);number(2,"START ",sample->start);number(3,"END ",sample->end);
        number(4,"DELTA ",sample->end-sample->start);number(5,"CRC ",sample->crc);
        number(6,"INDEX ",n.result_index+1);number(7,n.error?"ERROR ":"TARGET 1 D / 2 L = ",n.error?n.error:sample->target);return;
    }
    if(n.page==PAGE_RESULT){text(0,"NO SAMPLES");text(6,"OK main");number(7,"ERROR ",n.error);return;}
    text(0,n.phase==ADMISSION?"LUT ADMISSION":n.phase==DONE?(n.low_res?"LUT DONE LOW RES":"LUT DONE"):n.phase==ERROR?"LUT ERROR":"LUT BENCH");
    number(1,"L LEVELS ",n.admit_l);number(2,"D LEVELS ",n.admit_d);number(3,"SAMPLES ",n.used);
    number(4,"BUDGET TICKS ",n.budget);number(5,"ERROR ",n.error);
    text(6,n.phase==DONE?"OK results / reopen ADJ":"DOWN one sample");text(7,"33 NOT FIT");
}
static int publish(void)
{
    RvUiText t;RvUiList list;RvReply r;unsigned i,len;uint32_t language;
    if(!p0_irq_enabled()){error(ERR_IRQ);return 0;}
    rows();
    if(rv_native_seed(n.ctx)!=RV_OK||!call(RV_UI_TEXT,2,0,0,&r))return 0;
    language=r.detail;
    for(i=0;i<8;++i){
        for(len=0;n.rows[i][len];++len){}
        pn_zero(&t,sizeof(t));t.header=(RvBufferHeader){1,sizeof(t),0};
        t.source_address=address(n.rows[i]);t.source_bytes=len;t.source_lease=n.ctx->state_lease;
        t.glyph_address=address(n.glyphs[i]);t.glyph_capacity=84;t.glyph_lease=n.ctx->state_lease;t.language=language;
        if(!call(RV_UI_TEXT,1,&t,sizeof(t),&r))return 0;
        n.refs_ui[i]=address(n.glyphs[i]);n.labels[i]=address(&n.refs_ui[i]);
    }
    pn_zero(&list,sizeof(list));list.header=(RvBufferHeader){1,sizeof(list),0};list.view_token=n.view;
    list.state_address=n.ctx->ui_state_address;list.state_bytes=n.ctx->ui_state_bytes;list.rows=8;list.cursor=n.cursor;
    list.label_table=address(n.labels);list.details=address(n.details);list.lease_token=n.ctx->state_lease;
    RV_WORD(list.state_address+4)=list.state_address+32;RV_WORD(list.state_address+92)=list.label_table;
    RV_BYTE(list.state_address+96)=8;RV_WORD(list.state_address+100)=0;
    if(!call(RV_UI_LIST,1,&list,sizeof(list),&r))return 0;
    n.view=r.token;return 1;
}
static void withdraw(void)
{
    RvRoot *root=RV_PTR(n.ctx->root_address);RvSession *s=es_session(root);
    uint32_t *v=root->ui_restore,array,count,top,names;
    if(!s||!v[0]||v[9]!=n.ctx->state_lease||root->lease!=n.ctx->nonce)return;
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);names=RV_WORD(0x2022f5a8);
    if(array!=RV_NATIVE_VIEWS||count<1||count>2)return;
    top=array+8*(count-1);
    if(!(count==1&&RV_BYTE(top)==32)&&
       (RV_BYTE(top)!=33||(RV_WORD(top+4)!=0x2022f71c&&RV_WORD(top+4)!=root->ui_block)))return;
    if(v[6]&&v[6]!=s->list)return;
    if(names!=v[0]&&names!=v[6])return;
    /* A failed publication may have stale request epochs. The shared local
     * abort restores our captured bytes without authorizing a new publish. */
    (void)es_ui_abort(root);n.view=0;
}
static void publish_failed(void){if(!n.error)n.error=ERR_IO;error(n.error);withdraw();}
static int work_ok(void)
{
    RvRoot *root=RV_PTR(n.ctx->root_address);
    if(!n.work_base||n.work_bytes!=sizeof(ProbeWork)||n.work_token==n.ctx->state_lease||
       !es_range(root,n.work_token,n.work_base,n.work_bytes))return 0;
    return n.work_base>=root->block+root->block_bytes||n.work_base+n.work_bytes<=root->block;
}
static int allocate_work(void)
{
    RvRequest q=n.request;RvReply reply;RvLeaseInfo *lease=(RvLeaseInfo *)n.wire.bytes;unsigned i;
    if(n.work_base)return work_ok();
    for(i=8;i<14;++i)q.args[i]=0;
    pn_zero(lease,sizeof(*lease));lease->header=(RvBufferHeader){1,sizeof(*lease),0};
    q.args[1]=n.ctx->state_lease;q.args[8]=sizeof(ProbeWork);q.args[9]=4;
    q.args[10]=address(lease);q.args[11]=sizeof(*lease);
    if(n.api->call(RV_LEASE,1,&q,&reply)!=RV_OK||reply.status!=RV_OK||reply.actual!=sizeof(*lease)||
       lease->header.version!=1||lease->header.bytes!=sizeof(*lease)||lease->header.flags||
       !lease->token||lease->length!=sizeof(ProbeWork)||lease->usage!=4)return 0;
    n.work_base=lease->base;n.work_token=lease->token;n.work_bytes=lease->length;
    return work_ok();
}
static int guards(void)
{
    ProbeWork *work=RV_PTR(n.work_base);
    return work->before==0x913ba27du&&work->after==0xd3e68a41u;
}
static uint32_t output_crc(uint32_t count)
{ProbeWork *work=RV_PTR(n.work_base);return gxr2_crc32((const uint8_t *)work->pairs,count*4);}
static unsigned crc_index(uint32_t count){return count==4096?0:count==4?1:count==64?2:3;}
static int timed(unsigned kind,uint32_t count,ProbeSample *sample)
{
    uint32_t i,delta;unsigned level=crc_index(count);ProbeWork *work;sample->valid=0;
    if(!p0_irq_enabled()){error(ERR_IRQ);return 0;}
    if(!work_ok()||(sample->target==2&&count>P0_PAIRS)){error(ERR_IO);return 0;}
    work=RV_PTR(n.work_base);work->before=0x913ba27du;work->after=0xd3e68a41u;
    if(sample->target==2)for(i=0;i<count;++i)work->pairs[i]=p0_input(i);
    sample->start=p0_tick();
    if(kind==2)p0_kernel(work->pairs,count,p0_table,p0_coord);
    else if(kind==1)p0_decrement(work->pairs,count,p0_table,p0_coord);
    else p0_empty(work->pairs,count,p0_table,p0_coord);
    sample->end=p0_tick();delta=sample->end-sample->start;
    if(!p0_irq_enabled()){error(ERR_IRQ);return 0;}
    if(delta>=0x80000000u){error(ERR_TICK);return 0;}
    if(!guards()){error(ERR_GUARD);return 0;}
    sample->crc=sample->target==2?output_crc(count):0;
    if(sample->target==2&&sample->crc!=(kind==2?p0_expected_crc[level]:p0_input_crc[level])){error(ERR_CRC);return 0;}
    if(delta>n.budget){error(ERR_BUDGET);return 0;}
    sample->count=count;sample->kind=kind;__asm__ __volatile__("":::"memory");sample->valid=1;return 1;
}
static void advance(void)
{
    ProbeSample *sample;uint32_t count,delta;unsigned level,rep,index,target,nonempty,i;
    if(n.phase==ADMISSION){
        target=n.admit_l_done?1:2;level=target==2?n.admit_l:n.admit_d;
        if((target==1&&n.admit_d_done)||level>=4){error(ERR_INVALID);return;}
        count=target==2?lcounts[level]:dcounts[level];sample=&n.admission[(target==2?0:4)+level];
        pn_zero(sample,sizeof(*sample));sample->target=target;
        if(!timed(target,count,sample))return;
        delta=sample->end-sample->start;
        if(target==2){n.admission_l[level]=delta;++n.admit_l;if(n.admit_l==4||delta>n.budget/2)n.admit_l_done=1;}
        else{n.admission_d[level]=delta;++n.admit_d;if(n.admit_d==4||delta>n.budget/2)n.admit_d_done=1;}
        if(n.admit_l_done&&n.admit_d_done){
            if(n.admit_l<2||n.admit_d<2)error(ERR_BUDGET);else n.phase=BENCH;
        }
        return;
    }
    if(n.phase!=BENCH)return;
    index=n.used;rep=index/(2*(n.admit_l+n.admit_d));index%=2*(n.admit_l+n.admit_d);
    target=index<2*n.admit_l?2:1;if(target==1)index-=2*n.admit_l;
    level=index/2;nonempty=(index&1)^((rep+level)&1);
    count=target==2?lcounts[level]:dcounts[level];sample=&n.samples[n.used];sample->target=target;
    if(timed(nonempty?target:0,count,sample)){
        ++n.used;
        if(n.used==6*(n.admit_l+n.admit_d)){
            n.phase=DONE;n.low_res=0;
            for(i=0;i<n.used;i+=2)if(n.samples[i].target==2&&n.samples[i].count==lcounts[n.admit_l-1]){
                ProbeSample *x=&n.samples[i],*y=&n.samples[i+1];
                uint32_t l=x->kind==2?x->end-x->start:y->end-y->start;
                uint32_t e=x->kind==0?x->end-x->start:y->end-y->start;
                if(l<=e||l-e<16)n.low_res=1;
            }
        }
    }
}
int32_t p0_bootstrap(const RvApi *a,uint32_t token,const RvRequest *q,RvReply *r)
{
    RvEngineEntries *entries;uint32_t *p;unsigned i;
    if(!ingress(a,token,q,r))return RV_FAULT;
    entries=RV_PTR(n.ctx->entries_address);entries->version=1;entries->bytes=40;p=&entries->init;
    for(i=0;i<9;++i)p[i]=272+16*i;
    r->actual=40;return RV_CONSUMED;
}
int32_t p0_init(const RvApi *a,uint32_t token,const RvRequest *q,RvReply *r)
{
    RvSession *s;static const uint8_t name[8]={'j','l','a','u','n','c','h',0};RvReply reply;
    if(!ingress(a,token,q,r))return RV_FAULT;
    s=RV_PTR(n.ctx->session_address);n.is50=pn_equal(s->unit.name,name,8)&&s->unit.main_version==0x0151&&s->unit.cmp_version==0;
    if(n.is50){RvRequest query=*q;unsigned i;for(i=8;i<14;++i)query.args[i]=0;query.args[8]=1;
        if(n.api->call(RV_QUERY,3,&query,&reply)!=RV_OK||reply.detail!=0xf09fe7b4u)n.is50=0;}
    r->capabilities=CAP_UI;return RV_CONSUMED;
}
int32_t p0_menu(const RvApi *a,uint32_t token,const RvRequest *q,RvReply *r)
{
    int start;
    if(!ingress(a,token,q,r))return RV_FAULT;
    if(!p0_irq_enabled()){error(ERR_IRQ);withdraw();return RV_CONSUMED;}
    if(n.phase==REF_RUN){error(ERR_INVALID);n.page=PAGE_MAIN;}
    start=n.phase==REF_ARMED&&!n.error;n.view=0;
    if(n.is50&&!n.baseline_valid&&!n.baseline_status&&!probe_baseline(&n,1))error(ERR_IO);
    if(start){n.page=PAGE_REF;n.phase=REF_RUN;n.cursor=0;}
    if(!publish()){publish_failed();return RV_CONSUMED;}
    if(start){n.ref_start=p0_tick();if(!p0_irq_enabled())error(ERR_IRQ);}
    return RV_CONSUMED;
}
int32_t p0_event(const RvApi *a,uint32_t token,const RvRequest *q,RvReply *r)
{
    int confirm;unsigned i;ProbeReference *ref;RvRoot *root;
    if(!ingress(a,token,q,r))return RV_FAULT;
    confirm=q->args[13]==0x23&&(q->args[12]==0x202c2d74||q->args[12]==0x202c2d84);
    if(!n.is50)return RV_CLOSE_AND_PASS;
    if(n.phase==REF_RUN){
        uint32_t end=p0_tick(),delta=end-n.ref_start;
        if(!confirm){error(ERR_INVALID);n.page=PAGE_MAIN;return RV_CLOSE_AND_PASS;}
        if(!delta||delta>=0x80000000u||!p0_irq_enabled()){error(ERR_TICK);n.page=PAGE_MAIN;return RV_CLOSE_AND_PASS;}
        if(n.ref_count==MAX_REFS){for(i=1;i<MAX_REFS;++i)n.refs[i-1]=n.refs[i];--n.ref_count;}
        ref=&n.refs[n.ref_count];ref->valid=0;ref->start=n.ref_start;ref->end=end;ref->delta=delta;ref->run=n.run;
        __asm__ __volatile__("":::"memory");ref->valid=1;++n.ref_count;n.budget=delta/600;
        n.phase=REF_DONE;n.page=PAGE_HISTORY;n.history_index=n.ref_count-1;return RV_CLOSE_AND_PASS;
    }
    if(!confirm)return RV_CLOSE_AND_PASS;
    if(n.page!=PAGE_MAIN){n.page=n.page==PAGE_BENCH&&result_count()?PAGE_RESULT:PAGE_MAIN;return RV_CLOSE_AND_PASS;}
    if(n.cursor==0){if(!probe_baseline(&n,0))error(ERR_BASE);}
    else if(n.cursor==1){
        root=RV_PTR(n.ctx->root_address);for(i=0;i<7;++i)n.binding[i]=root->epoch[binding_epochs[i]];
        ++n.run;n.error=0;n.used=n.low_res=n.admit_l=n.admit_d=n.admit_l_done=n.admit_d_done=0;n.phase=REF_ARMED;
    }else if(n.cursor==2&&!n.error&&n.ref_count>=2&&n.budget){
        if(!allocate_work()){error(ERR_IO);return RV_CLOSE_AND_PASS;}
        if(n.phase!=BENCH&&n.phase!=ADMISSION&&n.phase!=DONE){n.used=n.admit_l=n.admit_d=n.admit_l_done=n.admit_d_done=0;n.phase=ADMISSION;}
        n.page=PAGE_BENCH;n.cursor=0;
    }else if(n.cursor==3){n.page=PAGE_RESULT;n.result_index=0;n.cursor=0;}
    else if(n.cursor==4){n.page=PAGE_HISTORY;n.history_index=0;n.cursor=0;}
    return RV_CLOSE_AND_PASS;
}
int32_t p0_apply(const RvApi *a,uint32_t token,const RvRequest *q,RvReply *r)
{
    int down;
    if(!ingress(a,token,q,r)||q->args[8]>=8)return RV_FAULT;
    /* H08's r4 is zero, not a key code. The native DOWN handler advances
     * exactly one row before this shared caller; UP moves the other way. */
    down=q->args[12]==0x202bb4e8&&q->args[13]==0&&q->args[8]==((n.cursor+1)&7);
    n.cursor=q->args[8];
    if(n.phase==REF_RUN){error(ERR_INVALID);n.page=PAGE_MAIN;}
    if(n.is50&&down){
        if(n.page==PAGE_BENCH){n.busy=1;advance();n.busy=0;}
        else if(n.page==PAGE_RESULT&&result_count())n.result_index=(n.result_index+1)%result_count();
        else if(n.page==PAGE_HISTORY&&n.ref_count)n.history_index=(n.history_index+1)%n.ref_count;
    }
    if(!publish())publish_failed();
    return RV_CONSUMED;
}
int32_t p0_close(const RvApi *a,uint32_t token,const RvRequest *q,RvReply *r)
{
    if(!ingress(a,token,q,r))return RV_FAULT;
    if(n.phase==REF_RUN||n.phase==REF_ARMED){error(ERR_INVALID);n.page=PAGE_MAIN;}
    withdraw();return RV_CONSUMED;
}
