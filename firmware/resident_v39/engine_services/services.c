#include "engine_services.h"


static int header(const void *p,uint32_t n)
{ const RvBufferHeader *h=p;return n>=8&&h->version==1&&h->bytes==n&&!h->flags; }
static uint32_t token(RvRoot *r)
{ if(r->next_token==~0u){r->state=RV_FENCED;r->fault=RV_RANGE;r->flags|=RF_STOP;return 0;}return ++r->next_token; }
static int identity(RvRoot *r,const RvRequest *q)
{
    GxrceUnit unit;const uint8_t *p=RV_PTR(0x2040f81c);
    memcpy(unit.name,p,8);unit.main_version=rv_be16(p+44);unit.cmp_version=rv_be16(p+46);
    return !(r->flags&RF_STOP)&&rv_session(r)&&rv_equal(&unit,&r->unit,sizeof(unit))&&q->args[0]==r->lease&&q->args[2]==r->epoch[RV_BOOT_E]&&
        q->args[3]==r->epoch[RV_HEAP_E];
}
static int current(RvRoot *r,const RvRequest *q)
{return identity(r,q)&&q->args[4]==r->epoch[RV_LINK_E]&&q->args[5]==r->epoch[RV_UNIT_E]&&
        q->args[6]==r->epoch[RV_VIEW_E]&&q->args[7]==r->epoch[RV_S_E];}
static int32_t free_session_work(RvRoot *r,RvLease *l,uint32_t *detail)
{
    *detail=0;
    if(!rv_allocation(l->base,l->length,0))return RV_VERIFY;
    /* Usage 4 is private session work. The service has already checked the
     * current session, epochs, token, inverse and absence of a UI reference.
     * Keep lease_entry as the allocation's original ownership evidence. */
    *detail=0x101;rv_native_free(l->base);*detail=0x100|RV_BYTE(l->base-8);
    (void)r;return (*detail&255)==0?RV_OK:RV_IO;
}
/* g139: file_buffer, path, sd_current and storage are removed with the
 * storage service (no file client in this profile). */
static RvUiSnapshot *ui_prepare(RvRoot *r)
{
    uint32_t address;RvUiSnapshot *u=rv_ui_snapshot(r);
    if(u||r->ui_block)return u;
    address=rv_native_alloc(sizeof(RvUiSnapshot));
    if(!address||!rv_session(r)||!rv_allocation(address,sizeof(RvUiSnapshot),0))return 0;
    rv_clear(RV_PTR(address),sizeof(RvUiSnapshot));
    {RvUiSnapshot *u=RV_PTR(address);u->magic=RV_UI_MAGIC;u->inverse=~address;}
    r->ui_block=address;r->ui_inverse=~address;r->ui_alloc_bytes=RV_WORD(address-4);
    return RV_PTR(address);
}
static int ui_seed(RvRoot *r,RvUiSnapshot *u,uint32_t source)
{
    uint32_t table=RV_WORD(0x2022f720);
    if(RV_BYTE(source)!=5||table<0x20000000u||table>0x20704800u-72||
       (RV_BYTE(0x2022f71c)!=5&&table!=0x2022f56c))return 0;
    memcpy(u->state,RV_PTR(0x2022f71c),32);memcpy(u->descriptors,RV_PTR(table),72);
    u->state[0]=5;
    RV_WORD(r->ui_block+4)=r->ui_block+offsetof(RvUiSnapshot,descriptors);
    u->state[9]=RV_BYTE(source+9);u->state[10]=RV_BYTE(source+10);
    return 1;
}
static int32_t ui_list(RvRoot *,uint32_t,RvUiList *) __attribute__((noinline));
static int32_t ui_list(RvRoot *r,uint32_t op,RvUiList *u)
{
    RvSession *s=rv_session(r);RvUiSnapshot *native;uint32_t i,j,x,y,*lengths=s->ui_lengths,irq;
    if(op==4)return rv_ui_abort(r);
    /* The fixed resident suppresses an inflight Image continuation only
     * while exactly eight physical rows remain published. */
    if(!s||u->rows!=8||u->cursor>=u->rows||u->state_bytes<16||
       !rv_range(r,u->lease_token,u->state_address,u->state_bytes)||
       !rv_range(r,u->lease_token,u->label_table,u->rows*4)||
       !rv_range(r,u->lease_token,u->details,u->rows*12))return RV_RANGE;
    /* This profile publishes the same empty details as Stage2l. Reject any
     * embedded pointer layout that has no reviewed deep-copy contract. */
    for(i=0;i<u->rows*3;++i)if(RV_WORD(u->details+4*i))return RV_UNSUPPORTED;
    for(i=0;i<u->rows;++i){
        x=RV_WORD(u->label_table+4*i);if(!rv_range(r,u->lease_token,x,4))return RV_RANGE;
        y=RV_WORD(x);
        for(j=0;j<96;++j){if(!rv_range(r,u->lease_token,y+j,1))return RV_RANGE;if(!RV_BYTE(y+j))break;}
        if(j==96)return RV_RANGE;
        lengths[i]=j+1;
    }
    if(op!=1&&(u->view_token!=r->epoch[RV_VIEW_E]||
       (op!=2&&s->view_source!=u->state_address)))return RV_STALE;
    native=ui_prepare(r);if(!native)return RV_IO;
    irq=rv_irq_save();
    /* A constructor may yield before this publication. Only Image ADJ may
     * receive this list; preserve a different current native item. */
    if(RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56){rv_irq_restore(irq);return RV_STALE;}
    /* op 3 must still own the native list at the write boundary. RPC can
     * yield to another constructor without changing the resident epoch. */
    if(op==1) {
        uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4),top;
        if((!count&&(s->context.input_fields!=1||s->context.input_sequence!=r->entry_serial))||
           ((uint32_t)RV_BYTE(0x205a280f)-1u>1u)||
           array!=RV_NATIVE_VIEWS||count>2){rv_irq_restore(irq);return RV_STALE;}
        if(count){
            top=array+8*(count-1);
            if(!(count==1&&RV_BYTE(array)==32)&&
               (RV_BYTE(top)!=33||(RV_WORD(top+4)!=0x2022f71c&&RV_WORD(top+4)!=r->ui_block)))
                {rv_irq_restore(irq);return RV_STALE;}
        }
        if(RV_WORD(0x2022f5a8)!=(r->ui_restore[0]?s->list:0x2022d610)||
           RV_BYTE(0x2022f5ac)!=(r->ui_restore[0]?8u:7u))
            {rv_irq_restore(irq);return RV_STALE;}
    }
    if(op==2) {
        /* Update may replace rows/source in the same lease. Validate the
         * previous live owner under IRQ before publishing the new shape. */
        RvUiList previous;
        memcpy(&previous,u,sizeof(previous));
        previous.state_address=s->view_source;previous.rows=s->rows;
        if(!rv_view_owned(r,&previous,0)){rv_irq_restore(irq);return RV_STALE;}
    }
    if(op==3&&!rv_view_owned(r,u,0)){rv_irq_restore(irq);return RV_STALE;}
    if(!rv_ui_capture(r,op==1)){rv_irq_restore(irq);return RV_STALE;}
    if(!ui_seed(r,native,u->state_address)){rv_irq_restore(irq);return RV_UNAVAILABLE;}
    for(i=0;i<u->rows;++i){
        y=RV_WORD(RV_WORD(u->label_table+4*i));memcpy(native->glyphs[i],RV_PTR(y),lengths[i]);
        native->refs[i]=r->ui_block+offsetof(RvUiSnapshot,glyphs)+96*i;
        native->labels[i]=r->ui_block+offsetof(RvUiSnapshot,refs)+4*i;
    }
    s->view_source=u->state_address;s->view_state=r->ui_block;s->view_lease=u->lease_token;
    s->list=r->ui_block+offsetof(RvUiSnapshot,labels);s->details=r->ui_block+offsetof(RvUiSnapshot,details);
    s->rows=u->rows;s->cursor=u->cursor;native->state[9]=native->state[10]=u->cursor+1;
    RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=u->cursor+1;
    RV_WORD(r->ui_block+offsetof(RvUiSnapshot,descriptors)+60)=s->list;
    RV_BYTE(r->ui_block+offsetof(RvUiSnapshot,descriptors)+64)=u->rows;
    RV_WORD(r->ui_block+offsetof(RvUiSnapshot,descriptors)+68)=0;
    r->ui_restore[6]=s->list;r->ui_restore[7]=s->details;
    RV_WORD(0x2022f5a8)=s->list;RV_BYTE(0x2022f5ac)=u->rows;
    u->view_token=r->epoch[RV_VIEW_E];rv_irq_restore(irq);
    if(op==3){
        if(!rv_view_owned(r,u,0))return RV_STALE;
        s->redraw=1;rv_native_draw(2,s->view_state,0);if(rv_session(r))s->redraw=0;
    }
    return RV_OK;
}
static int32_t ui_view(RvRoot *r,uint32_t op,RvUiView *u)
{
    uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4),top,irq;
    RvUiSnapshot *native;
    if(op==2||op==3){if(op==2&&u->view_token!=r->epoch[RV_VIEW_E])return RV_STALE;return rv_ui_abort(r);}
    if(op!=1)return RV_UNSUPPORTED;
    if(u->part!=2||u->tag!=33||u->state_bytes<16||!rv_range(r,u->lease_token,u->state_address,u->state_bytes))return RV_RANGE;
    if(array!=RV_NATIVE_VIEWS||count==0||count>2||array!=u->expected_array||count!=u->expected_count||
       RV_WORD(0x205d9bf8)!=8||(RV_BYTE(0x205a280f)!=2&&RV_BYTE(0x205a280f)!=1))return RV_STALE;
    top=array+8*(count-1);
    if(RV_BYTE(top)!=u->expected_top_tag||RV_WORD(top+4)!=u->expected_top_state)return RV_STALE;
    native=ui_prepare(r);if(!native)return RV_IO;
    irq=rv_irq_save();
    if(!rv_ui_capture(r,0)){rv_irq_restore(irq);return RV_STALE;}
    if(!r->ui_restore[6]&&!ui_seed(r,native,u->state_address)){rv_irq_restore(irq);return RV_UNAVAILABLE;}
    r->ui_restore[5]=r->epoch[RV_VIEW_E];r->ui_restore[12]=r->ui_block;
    RV_WORD(top+4)=r->ui_block;u->view_token=r->ui_restore[5];rv_irq_restore(irq);return RV_OK;
}
void rv_settings_entry(RvRoot *r,unsigned entry)
{
    RvSession *s=rv_session(r);
    if(!s)return;
    /* These context input fields have no other reader or writer in this profile.
     * Bind the rule to the resident's current entry, outside the request. */
    s->context.input_fields=entry;s->context.input_sequence=r->entry_serial;
}
int __attribute__((noinline)) rv_settings_owned(RvRoot *r,uint32_t view)
{
    RvSession *s=rv_session(r);RvUiList u;
    if(!s||r->inflight!=1||s->context.input_sequence!=r->entry_serial||s->context.nonce!=r->lease||
       (s->context.input_fields!=1&&s->context.input_fields!=6&&s->context.input_fields!=7&&s->context.input_fields!=8))return 0;
    rv_clear(&u,sizeof(u));u.lease_token=s->view_lease;
    u.view_token=view;u.state_address=s->view_source;u.rows=s->rows;
    return rv_view_owned(r,&u,s->context.input_fields==1);
}
static int32_t settings(RvRoot *r,uint32_t op,void *buffer,uint32_t view)
{
    RvSession *s=rv_session(r);uint32_t address=RV_WORD(0x200c0dac),bytes=RV_WORD(0x200c0db0),i,j,mode=0,off,val,irq;
    RvSettingsInfo *u=buffer;RvSettingsPlan *plan=buffer;RvSettingsRecord *m=buffer;
    volatile uint8_t *native=RV_PTR(address);volatile uint32_t *tail=RV_PTR(address+0xfd4);
    const uint32_t *words=(const uint32_t *)m->record;uint32_t old[10];int32_t result=RV_OK;
    if(op==3){s->settings=0;return RV_OK;}
    if(!address||bytes<0xc9e)return RV_RANGE;
    if(op==1){s->settings=address;s->settings_bytes=bytes;s->settings_epoch=r->epoch[RV_S_E];
        u->token=token(r);s->settings_token=u->token;u->address=address;u->length=bytes;u->settings_epoch=s->settings_epoch;return RV_OK;}
    /* The dispatcher admits only op 2 and op 6 (plan), op 4 and op 5 (record)
     * here. op 6 checks the stock lock under the op 2 rules and writes nothing. */
    if(r->state!=RV_READY||!(s->capabilities&CAP_S)||(r->flags&RF_UNCERTAIN))return RV_CAPABILITY;
    if(plan->settings_token!=s->settings_token||!s->settings||s->settings!=address||s->settings_bytes!=bytes||
       s->settings_epoch!=r->epoch[RV_S_E])return RV_STALE;
    if(op==2||op==6) {
        if(!plan->count||plan->count>16)return RV_STALE;
        mode=plan->writes[plan->count-1].offset==0x36e?plan->writes[plan->count-1].value:native[0x36e];
        if(mode!=1&&mode!=3&&mode!=4&&mode!=6)return RV_RANGE;
        for(i=0;i<plan->count;++i) {
            off=plan->writes[i].offset;val=plan->writes[i].value;
            if(plan->writes[i].reserved||off>=bytes)return RV_RANGE;
            for(j=0;j<i;++j)if(plan->writes[j].offset==off)return RV_ARGUMENT;
            if(off==0x36e){if(i!=plan->count-1)return RV_ARGUMENT;continue;}
            if(off==0x6dd||off==0x6de){if(val<1||val>17)return RV_RANGE;continue;}
            if(val<1||val>9)return RV_RANGE;
            if(mode==4&&((off>=0x36f&&off<=0x371)||(off>=0x8ac&&off<=0x8b5)))continue;
            if(mode==3&&(off==0x645||off==0x646))continue;
            if(mode==6&&off>=0x641&&off<=0x644&&
               (off!=0x643||val==1||val==2||val==3||val==4||val==6))continue;
            return RV_RANGE;
        }
    } else {
        /* The 40-byte record S+0xFD4..0xFFB lies after the 0xD24 extension
         * and before the stock sum at S+0xFFC. op 4 reads it; op 5 replaces
         * it whole with forty zeros (forget) or one complete GXR2 v1. */
        if(m->settings_epoch!=s->settings_epoch||m->reserved[0]||m->reserved[1])return RV_STALE;
        if(bytes!=0x1000||native[14]!=0x0d||native[15]!=0x24)return RV_RANGE;
        if(op==4){memcpy(m->record,(const void *)tail,40);return RV_OK;}
        for(i=0;i<40&&!m->record[i];++i){}
        /* words[] are the record's big-endian fields on this target. */
        if(i<40&&(words[0]!=0x47585232u||m->record[4]!=1||m->record[5]-1u>7u||m->record[6]>2||
                  m->record[7]!=1||gxrce_crc32(m->record,36)!=words[9]))return RV_ARGUMENT;
        /* P1-02: only forty zeros or one of our own GXR2 v1 records may be
         * replaced. Snapshot here; the critical section checks it is unchanged. */
        memcpy(old,(const void *)tail,40);
        for(i=0;i<10&&!old[i];++i){}
        if(i<10&&(old[0]!=0x47585232u||(old[1]>>24)!=1||gxrce_crc32((const uint8_t *)old,36)!=old[9]))return RV_CONFLICT;
    }
    irq=rv_irq_save();
    /* P2-04: length and extension version are re-read in this section. */
    if(!rv_settings_owned(r,view)||address!=RV_WORD(0x200c0dac)||bytes!=RV_WORD(0x200c0db0)||s->settings_epoch!=r->epoch[RV_S_E]||
       (op-4u<2u&&(native[14]!=0x0d||native[15]!=0x24))){rv_irq_restore(irq);return RV_STALE;}
    if(op==5)for(i=0;i<10;++i)if(tail[i]!=old[i]){rv_irq_restore(irq);return RV_CONFLICT;}
    /* Stock parameter lock 0x204104f0: s32 fast count (-1 idle), then the
     * semaphore ID 55. Take it once, only when idle; busy writes nothing and
     * never waits or queues. Take, write and release share this IRQ section,
     * so no waiter can arrive and release is the plain store back to -1. */
    if(RV_WORD(0x204104f4)!=55||RV_WORD(0x204104f0)!=~0u){rv_irq_restore(irq);return RV_BUSY;}
    /* op 6: idle now; nothing is taken or written. */
    if(op==6){rv_irq_restore(irq);return RV_OK;}
    RV_WORD(0x204104f0)=0;
    if(op==2){for(i=0;i<plan->count;++i)native[plan->writes[i].offset]=plan->writes[i].value;
        for(i=0;i<plan->count;++i)if(native[plan->writes[i].offset]!=plan->writes[i].value)result=RV_VERIFY;}
    else {
        for(i=0;i<10;++i)tail[i]=words[i];
        for(i=0;i<10;++i)if(tail[i]!=words[i])result=RV_VERIFY;
    }
    RV_WORD(0x204104f0)=~0u;rv_irq_restore(irq);
    return result;
}
int32_t rv_service(RvRoot *r,uint32_t id,uint32_t op,const RvRequest *q,RvReply *p)
{
    RvSession *s=rv_session(r);void *buffer=0;uint32_t bytes,a,b,i,n,x,irq,used=0,observe;int32_t result=RV_UNSUPPORTED;
    if(!q||!p||((uintptr_t)q&3)||((uintptr_t)p&3))return RV_ARGUMENT;
    rv_clear(p,32);p->version=1;p->bytes=32;
    if(q->version!=1||q->bytes!=64||q->flags){result=RV_ARGUMENT;goto finish;}
    /* This profile has no file client (PsStore is unused): storage stays closed. */
    if(id==RV_STORAGE)goto finish;
    if(id<1||id>16||id==RV_SHA256)goto finish;
    if(id==RV_QUERY&&op==3){
        for(i=9;i<14;++i)if(q->args[i]){result=RV_ARGUMENT;goto finish;}
        a=q->args[8];if(a<1||a>3){result=RV_ARGUMENT;goto finish;}
        p->actual=4;p->detail=r->pins[a-1];result=RV_OK;goto finish;
    }
    if(id==RV_QUERY&&op<=1){for(i=8;i<14;++i)if(q->args[i]){result=RV_ARGUMENT;goto finish;}}
    if(id==RV_QUERY&&op<=2) {
        p->actual=16;p->capabilities=s?s->capabilities:RV_READ_CAPS;p->detail=sizeof(rv_api);result=RV_OK;
        if(op!=2)goto finish;
    }
    observe=id==RV_EPOCHS||id==RV_EVENTS||(op==1&&(id==RV_UNIT||id==RV_SD_ID||id==RV_SETTINGS))||id==RV_QUERY;
    if(!(observe?identity(r,q):current(r,q))){result=RV_STALE;goto finish;}
    if(!r->inflight||rv_native_context()!=0){result=RV_OWNER;goto finish;}
    if((r->flags&RF_OWNER)){result=RV_BUSY;goto finish;}
    s=rv_session(r);a=q->args[8];b=q->args[9];bytes=q->args[11];
    switch(id){
    case RV_LEASE:used=op==1?15:op==3?13:0;break;
    case RV_CACHE:case RV_UNIT:case RV_SD_ID:case RV_UI_VIEW:case RV_CRC32:used=12;break;
    case RV_RPC8:used=op>=2&&op<=4?1:0;break;
    case RV_SETTINGS:used=op==3?0:op==2||op==6?28:12;break;
    case RV_EPOCHS:used=op==12?12:0;break;
    case RV_UI_LIST:used=op==4?31:30;break;
    case RV_UI_TEXT:used=op==1?12:0;break;
    case RV_EVENTS:used=op==1?13:3;break;
    case RV_QUERY:used=12;break;
    }
    for(i=0;i<6;++i)if(q->args[8+i]&&!(used&(1u<<i))){result=RV_ARGUMENT;goto finish;}
    if(q->args[13]||(q->args[12]&&id!=RV_SETTINGS&&id!=RV_UI_LIST)||(!bytes&&q->args[10])){result=RV_ARGUMENT;goto finish;}
    if(bytes) {
        if(!rv_range(r,q->args[1],q->args[10],bytes)||(q->args[10]&3)){result=RV_RANGE;goto finish;}
        buffer=RV_PTR(q->args[10]);
        if(id!=RV_SD_ID&&id!=RV_CRC32&&id!=RV_CACHE&&!header(buffer,bytes)){result=RV_ARGUMENT;goto finish;}
    }
    r->flags|=RF_OWNER;
    switch(id) {
    case RV_LEASE:
        if(op==1) {
            if(bytes!=32||!a||a>73728u||b<2||b>5){result=RV_ARGUMENT;break;}
            for(i=1;i<RV_LEASES&&s->leases[i].token;++i){}if(i==RV_LEASES){result=RV_BUSY;break;}
            n=token(r);if(!n){result=RV_FAULTED;break;}
            x=rv_native_alloc(a);if(!current(r,q)){result=RV_STALE;break;}if(!x||!rv_heap_span(x,a)){result=RV_IO;break;}
            s->leases[i]=(RvLease){n,~n,x,a,b};s->lease_entry[i]=r->entry_serial;
        } else {
            if(!(op==3?a:q->args[1])){result=RV_STALE;break;}
            for(i=0;i<RV_LEASES&&s->leases[i].token!=(op==3?a:q->args[1]);++i){}
            if(i==RV_LEASES||s->leases[i].inverse!=~s->leases[i].token){result=RV_STALE;break;}
        }
        if(op==2) {
            if(!i||r->inflight>1||s->view_lease==s->leases[i].token||(r->ui_restore[0]&&s->leases[i].usage==3)){result=RV_BUSY;break;}
            x=s->leases[i].base;
            result=s->leases[i].usage==4?free_session_work(r,&s->leases[i],&p->detail):rv_free_checked(r,x,&p->detail);
            if(result==RV_OK){s->leases[i].token=0;p->token=0;}
            break;
        }
        if((op==1||op==3)&&bytes==32) {
            RvLeaseInfo *u=buffer;RvLease *l=&s->leases[i];u->token=l->token;u->base=l->base;u->length=l->length;u->usage=l->usage;
            u->boot_epoch=r->epoch[RV_BOOT_E];u->heap_epoch=r->epoch[RV_HEAP_E];p->token=l->token;p->actual=32;result=RV_OK;
        }break;
    case RV_CACHE:if(op==1&&bytes){rv_cache_sync();result=RV_OK;}break;
    case RV_RPC8:
        if(op<1||op>5)break;
        if(a>65535||(op!=5&&(rv_native_rpc_ready()==0||rv_native_rpc_limit()<=8))||s->bindings[RV_LINK_E]!=r->epoch[RV_LINK_E]||s->bindings[RV_UNIT_E]!=r->epoch[RV_UNIT_E]){result=RV_STALE;break;}
        if(op==1) {if(s->rpc_token){result=RV_BUSY;break;}s->rpc_token=token(r);s->rpc_phase=0;p->token=s->rpc_token;result=RV_OK;break;}
        if(q->args[1]!=s->rpc_token||!s->rpc_token){result=RV_STALE;break;}
        if(op==5){if(s->rpc_phase==2)r->flags&=~RF_UNCERTAIN;s->rpc_token=0;result=(r->flags&RF_UNCERTAIN)?RV_UNCERTAIN:RV_OK;break;}
        if(op==3&&(r->state!=RV_READY||!(s->capabilities&CAP_W))){result=RV_CAPABILITY;break;}
        if(op==3){r->flags|=RF_UNCERTAIN;s->rpc_phase=1;p->detail=1;}
        result=rv_rpc8_native(op==2?21:op==3?22:23,a);p->native_result=result;
        if(!current(r,q)){result=RV_STALE;break;}
        if(result<0||result>65535){s->rpc_phase=3;result=RV_IO;}
        else if(op==3&&(uint32_t)result!=a){s->rpc_phase=3;result=RV_UNCERTAIN;}
        else {if(op==2||op==3)s->rpc_phase=2;result=RV_OK;}break;
    case RV_PREVIEW:
        if(op==1&&a==0&&r->state==RV_READY&&!(r->flags&RF_UNCERTAIN)&&!s->rpc_token){
            irq=rv_irq_save();
            if(!rv_settings_owned(r,q->args[6])){rv_irq_restore(irq);result=RV_STALE;break;}
            rv_irq_restore(irq);
            p->native_result=rv_native_preview(0);result=p->native_result?RV_IO:RV_OK;}break;
    case RV_SETTINGS:
        if((op==1&&bytes==24)||((op==2||op==6)&&bytes==80)||op==3||(op-4u<2u&&bytes==64))result=settings(r,op,buffer,q->args[6]);
        if(result==RV_OK&&op==1)p->actual=24;
        break;
    case RV_UNIT:
        if(op==1&&bytes==36) {RvUnitInfo *u=buffer;GxrceUnit unit;result=rv_unit(r,&unit);if(!identity(r,q)){result=RV_STALE;break;}if(!result){memcpy(u->name,&unit,12);p->actual=36;}u->unit_epoch=r->epoch[RV_UNIT_E];u->link_epoch=r->epoch[RV_LINK_E];u->rx_sequence=r->rx;u->valid=result==RV_OK;}break;
    case RV_SD_ID:
        if(op==1&&bytes==16) {uint32_t before=r->epoch[RV_SD_E];if(!(r->flags&RF_SD)){result=RV_STALE;break;}result=rv_native_sd_id(buffer);if(!result){const uint32_t *idp=buffer;result=(idp[0]|idp[1]|idp[2]|idp[3])?RV_OK:RV_UNAVAILABLE;}p->epoch=r->epoch[RV_SD_E];if(before!=p->epoch||!(r->flags&RF_SD))result=RV_STALE;if(result==RV_OK)p->actual=16;}break;
    case RV_EPOCHS:
        if(op<12){p->epoch=r->epoch[op];result=RV_OK;}
        else if(op==12&&bytes==60){RvEpochSnapshot *u=buffer;irq=rv_irq_save();u->session_token=r->lease;memcpy(u->epochs,r->epoch,48);rv_irq_restore(irq);p->actual=60;result=RV_OK;}
        break;
    case RV_UI_LIST:case RV_UI_VIEW:case RV_UI_TEXT:
        if(r->state!=RV_READY||!(s->capabilities&CAP_UI)){result=RV_CAPABILITY;break;}
        if(id==RV_UI_LIST&&op==4){
            x=bytes==40?((RvUiList *)buffer)->view_token:a;
            result=x==r->epoch[RV_VIEW_E]?rv_ui_abort(r):RV_STALE;
        }
        if(id==RV_UI_LIST&&op>=1&&op<=3&&bytes==40){
            RvUiList *u=buffer;
            result=b==u->rows&&(!q->args[12]||q->args[12]==u->rows)?ui_list(r,op,u):RV_ARGUMENT;
            if(!result){p->token=u->view_token;p->epoch=r->epoch[RV_VIEW_E];}
        }
        if(id==RV_UI_VIEW&&bytes==48)result=ui_view(r,op,buffer);
        if(id==RV_UI_TEXT&&op==2){p->detail=rv_native_language();result=RV_OK;}
        if(id==RV_UI_TEXT&&op==1&&bytes==40) {
            RvUiText *u=buffer;
            if(!u->source_bytes||u->source_bytes>255||u->glyph_capacity<2*u->source_bytes+1||
               !rv_range(r,u->source_lease,u->source_address,u->source_bytes+1)||!rv_range(r,u->glyph_lease,u->glyph_address,u->glyph_capacity)){result=RV_RANGE;break;}
            for(i=0;i<u->source_bytes;++i){x=RV_BYTE(u->source_address+i);if(x<32||x>126)break;}
            if(i!=u->source_bytes||RV_BYTE(u->source_address+i)){result=RV_ARGUMENT;break;}
            if(u->source_address>=u->glyph_address?u->source_address-u->glyph_address<u->glyph_capacity:u->glyph_address-u->source_address<u->source_bytes+1){result=RV_ARGUMENT;break;}
            p->native_result=rv_native_ascii(RV_PTR(u->source_address),u->source_bytes,RV_PTR(u->glyph_address),u->language);
            if(!current(r,q)){result=RV_STALE;break;}
            for(i=0;i<u->glyph_capacity&&RV_BYTE(u->glyph_address+i);++i){}
            if(i==u->glyph_capacity){result=RV_VERIFY;break;}
            u->actual_bytes=i+1;result=RV_OK;
        }break;
    case RV_EVENTS:
        if(op==2){rv_record(r,0,0,a,b);result=RV_OK;}
        else if(op==1&&bytes>=24) {
            RvEventSnapshot *u=buffer;irq=rv_irq_save();n=r->event_head;
            x=n>RV_RING_COUNT?n-RV_RING_COUNT+1:1;if(a>=x)x=a==~0u?0:a+1;
            u->first_sequence=x;u->last_sequence=n;u->dropped=r->dropped;u->count=0;
            for(i=x;i&&i<=n&&u->count<(bytes-24)/16;++i){
                RvRingEvent *e=&r->events[(i-1)&(RV_RING_COUNT-1)];RvEvent *out=&u->events[u->count++];
                out->sequence=i;out->hook=e->hook;out->phase=e->phase;out->a=e->a;out->b=e->b;
            }
            rv_irq_restore(irq);p->actual=24+16*u->count;result=RV_OK;
        }break;
    case RV_QUERY:
        if(op==2&&bytes==72){RvApiInfo *u=buffer;u->service_count=16;u->capabilities=s->capabilities;u->root_bytes=256;
            u->api_address=(uint32_t)(uintptr_t)&rv_api;memcpy(u->resident_build_id,RV_PTR(s->image_address+80),32);memcpy(u->resident_abi_id,RV_PTR(s->image_address+212),16);p->actual=72;result=RV_OK;}break;
    case RV_CRC32:if(op==1){p->detail=gxrce_crc32(buffer,bytes);result=RV_OK;}break;
    }
    r->flags&=~RF_OWNER;
    if(!(observe?identity(r,q):current(r,q)))result=RV_STALE;
finish:
    if(id==RV_STORAGE)p->epoch=op==6?q->args[0]:r->epoch[RV_IO_E];
    p->status=result;return result;
}
