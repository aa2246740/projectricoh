#include "resident.h"
const uint8_t rv4_blank_details[192]={0};

static int owner(const Rv4Root *r)
{
    uint32_t task=rv4_native_context();
    return task&&task==rv4_native_profile.ui_owner&&(!r->view.owner||r->view.owner==task);
}
static uint32_t native_slot(void)
{
    uint32_t n=RV4_BYTE(RV4_VIEW_COUNT);
    if(RV4_WORD(RV4_VIEW_ARRAY)!=RV4_VIEWS||n<1||n>2)return 0;
    n=RV4_VIEWS+8*(n-1);
    return RV4_BYTE(n)==33?n+4:0;
}
static int native_match(const Rv4Root *r)
{
    uint32_t slot=native_slot();
    return slot&&slot==r->draw.stack_slot&&RV4_WORD(slot)==r->view.state&&
        RV4_WORD(RV4_UI_NAMES)==r->view.names&&RV4_WORD(RV4_ACTIVITY)==r->draw.activity&&
        RV4_WORD(RV4_STATE)==r->draw.state&&RV4_BYTE(RV4_PART)==r->draw.part;
}
static int snapshot_valid(const Rv4Root *r)
{
    const Rv4Snapshot *s;uint32_t base=r->view.allocation;
    if(!base||base!=r->view.state||r->view.rows<1||r->view.rows>16||
       r->view.allocation_epoch!=r->epochs[RV4_E_HEAP]||
       r->view.names!=base+offsetof(Rv4Snapshot,labels)||r->view.details!=base+offsetof(Rv4Snapshot,details)||
       !rv4_allocation(base,sizeof(*s),r->view.alloc_bytes))return 0;
    s=RV4_PTR(base);
    return s->magic==RV4_SNAPSHOT_MAGIC&&s->inverse==~base&&s->ticket==r->view.ticket&&
        s->generation==r->view.generation&&s->generation==r->draw.snapshot_generation;
}
uint32_t rv4_protect(const Rv4Root *r,uint32_t frame_ticket)
{
    /* Row count does not participate, even if native memory says 7 or 19. */
    if(!rv4_root_valid(r))return 1;
    return frame_ticket||r->view.ticket||r->view.retiring||r->draw.frame_pins||
        r->draw.readers||r->draw.constructor||r->draw.pending||r->header.inflight||
        r->header.state==RV4_DISABLED||(r->header.flags&(RV4_RESTORING|RV4_STOP))||
        !(r->header.flags&RV4_RESTORED)||!owner(r);
}
int32_t rv4_constructor(Rv4Root *r,uint32_t token)
{
    uint32_t irq,task;
    if(!rv4_root_valid(r))return RV4_ARGUMENT;
    irq=rv4_irq_save();task=rv4_native_context();
    if(!owner(r)||!(rv4_native_profile.proof_flags&RV4_UI_PROTOCOL_PROVEN)){
        rv4_irq_restore(irq);return RV4_UNKNOWN;
    }
    if(token){
        if(token!=r->draw.constructor||task!=r->draw.constructor_owner){rv4_irq_restore(irq);return RV4_STALE;}
        r->draw.constructor=0;r->draw.constructor_owner=0;
    }else{
        if(r->draw.constructor||r->draw.readers||r->header.inflight||(r->header.flags&RV4_STOP)){
            rv4_irq_restore(irq);return RV4_BUSY;
        }
        if(r->header.next_token>=0x7fffffffu||r->header.serial==~0u){
            rv4_irq_restore(irq);rv4_retire(r,RV4_RANGE);return RV4_RANGE;
        }
        r->draw.constructor=++r->header.next_token;r->draw.constructor_owner=task;
        r->draw.constructor_serial=++r->header.serial;token=r->draw.constructor;
    }
    rv4_irq_restore(irq);return (int32_t)token;
}
int32_t rv4_view_publish(Rv4Root *r,const Rv4ViewInput *u,uint32_t *ticket)
{
    uint32_t i,j,address,irq,slot,table,epoch;Rv4Snapshot *s;
    if(!rv4_root_valid(r)||!u||!ticket)return RV4_ARGUMENT;
    if(u->version!=4||u->bytes!=sizeof(*u)||u->rows<1||u->rows>16||u->cursor>=u->rows)return RV4_RANGE;
    if(!(r->header.capabilities&RV4_CAP_UI_PUBLISH)||
       !(rv4_native_profile.proof_flags&RV4_UI_PROTOCOL_PROVEN))return RV4_UNSUPPORTED;
    if(!owner(r)||rv4_binding(r)||r->header.state!=RV4_READY||u->generation!=r->epochs[RV4_E_VIEW])return RV4_STALE;
    if(r->view.ticket||r->view.retiring||r->draw.readers||r->draw.pending)return RV4_BUSY;
    if(!rv4_span(RV4_ADDRESS(u),sizeof(*u),r->image.base,r->image.file_bytes+r->image.bss_bytes))return RV4_RANGE;
    for(i=0;i<u->rows;++i){
        for(j=0;j<96&&u->glyphs[i][j];++j){}
        if(j==96)return RV4_RANGE;
    }
    epoch=r->epochs[RV4_E_HEAP];address=r->view.allocation;
    if(!address){
        address=rv4_native_alloc(sizeof(*s));
        if(epoch!=r->epochs[RV4_E_HEAP]||!address||!rv4_allocation(address,sizeof(*s),0))return RV4_STALE;
        r->view.allocation=address;r->view.alloc_bytes=RV4_WORD(address-4);r->view.allocation_epoch=epoch;
    }
    if(r->view.allocation_epoch!=epoch||!rv4_allocation(address,sizeof(*s),r->view.alloc_bytes))return RV4_STALE;
    /* All copying and glyph checks precede the publication critical section. */
    table=RV4_WORD(RV4_UI_STATE+4);
    if(RV4_BYTE(RV4_UI_STATE)!=5||(table&3)||!rv4_span(table,72,0x20000000,0x704800))return RV4_STALE;
    s=RV4_PTR(address);rv4_clear(s,sizeof(*s));
    memcpy(s->state,RV4_PTR(RV4_UI_STATE),32);memcpy(s->descriptors,RV4_PTR(table),72);
    memcpy(s->glyphs,u->glyphs,u->rows*96);
    rv4_put32(s->state+4,address+offsetof(Rv4Snapshot,descriptors));
    s->state[9]=s->state[10]=u->cursor+1;
    for(i=0;i<u->rows;++i){
        s->refs[i]=address+offsetof(Rv4Snapshot,glyphs)+96*i;
        s->labels[i]=address+offsetof(Rv4Snapshot,refs)+4*i;
    }
    rv4_put32(s->descriptors+60,address+offsetof(Rv4Snapshot,labels));
    s->descriptors[64]=(uint8_t)u->rows;rv4_put32(s->descriptors+68,0);
    irq=rv4_irq_save();slot=native_slot();
    if(!owner(r)||(r->header.flags&RV4_STOP)||epoch!=r->epochs[RV4_E_HEAP]||
       u->generation!=r->epochs[RV4_E_VIEW]||r->view.ticket||r->view.retiring||r->draw.readers||
       !slot||RV4_WORD(slot)!=RV4_UI_STATE||RV4_WORD(RV4_UI_NAMES)!=RV4_STOCK_NAMES||
       RV4_BYTE(RV4_UI_ROWS)!=7||RV4_WORD(RV4_ACTIVITY)!=8||RV4_WORD(RV4_STATE)!=56||RV4_BYTE(RV4_PART)!=2){
        rv4_irq_restore(irq);return RV4_STALE;
    }
    if(r->header.next_token==~0u||r->epochs[RV4_E_VIEW]==~0u){
        rv4_irq_restore(irq);rv4_retire(r,RV4_RANGE);return RV4_RANGE;
    }
    r->view.ticket=++r->header.next_token;r->view.generation=++r->epochs[RV4_E_VIEW];
    r->view.names=address+offsetof(Rv4Snapshot,labels);r->view.details=address+offsetof(Rv4Snapshot,details);
    r->view.state=address;r->view.rows=u->rows;r->view.owner=rv4_native_context();
    r->view.stock_names=RV4_STOCK_NAMES;r->view.stock_state=RV4_UI_STATE;r->view.stock_rows=7;
    r->view.stock_cursor=RV4_BYTE(RV4_UI_CURSOR);r->view.stock_marker=RV4_BYTE(RV4_UI_MARKER);
    if(r->view.stock_cursor<1||r->view.stock_cursor>7)r->view.stock_cursor=1;
    if(r->view.stock_marker<1||r->view.stock_marker>7)r->view.stock_marker=1;
    r->draw.activity=8;r->draw.state=56;r->draw.part=2;r->draw.stack_slot=slot;
    r->draw.snapshot_generation=r->view.generation;
    s->magic=RV4_SNAPSHOT_MAGIC;s->inverse=~address;s->ticket=r->view.ticket;s->generation=r->view.generation;
    r->header.flags&=~RV4_RESTORED;RV4_BARRIER();
    RV4_WORD(slot)=address;RV4_WORD(RV4_UI_NAMES)=r->view.names;RV4_BYTE(RV4_UI_ROWS)=u->rows;
    RV4_BYTE(RV4_UI_CURSOR)=RV4_BYTE(RV4_UI_MARKER)=u->cursor+1;*ticket=r->view.ticket;
    rv4_irq_restore(irq);return RV4_OK;
}
int32_t rv4_view_withdraw(Rv4Root *r,uint32_t ticket)
{
    uint32_t irq;
    if(!rv4_root_valid(r))return RV4_ARGUMENT;
    irq=rv4_irq_save();
    if(!r->view.ticket){rv4_irq_restore(irq);return ticket?RV4_STALE:RV4_OK;}
    if(ticket!=r->view.ticket){rv4_irq_restore(irq);return RV4_STALE;}
    r->view.retiring=ticket;r->draw.pending=1;r->header.flags|=RV4_RESTORING;
    if(r->draw.readers){rv4_irq_restore(irq);return RV4_BUSY;}
    /* Never dereference an expired allocation to restore native slots. */
    if(!owner(r)||!native_match(r)||r->view.stock_names!=RV4_STOCK_NAMES||
       r->view.stock_state!=RV4_UI_STATE||r->view.stock_rows!=7||
       r->view.stock_cursor<1||r->view.stock_cursor>7||r->view.stock_marker<1||r->view.stock_marker>7){
        r->header.flags|=RV4_STOP;r->header.state=RV4_DISABLED;
        rv4_irq_restore(irq);return RV4_STALE;
    }
    RV4_WORD(r->draw.stack_slot)=r->view.stock_state;RV4_WORD(RV4_UI_NAMES)=r->view.stock_names;
    RV4_BYTE(RV4_UI_ROWS)=r->view.stock_rows;RV4_BYTE(RV4_UI_CURSOR)=r->view.stock_cursor;
    RV4_BYTE(RV4_UI_MARKER)=r->view.stock_marker;
    if(RV4_WORD(r->draw.stack_slot)!=r->view.stock_state||RV4_WORD(RV4_UI_NAMES)!=r->view.stock_names||
       RV4_BYTE(RV4_UI_ROWS)!=r->view.stock_rows){
        r->header.flags|=RV4_STOP;r->header.state=RV4_DISABLED;rv4_irq_restore(irq);return RV4_STALE;
    }
    r->view.ticket=0;r->draw.pending=0;
    r->header.flags=(r->header.flags&~RV4_RESTORING)|RV4_RESTORED;
    if(!r->draw.frame_pins)r->view.retiring=0;
    RV4_BARRIER();rv4_irq_restore(irq);return RV4_OK;
}
void rv4_ui_drain(Rv4Root *r)
{
    uint32_t irq;
    if(!rv4_root_valid(r))return;
    if(r->draw.pending&&r->view.ticket)(void)rv4_view_withdraw(r,r->view.ticket);
    irq=rv4_irq_save();
    if(!r->view.ticket&&!r->draw.frame_pins&&!r->draw.readers&&(r->header.flags&RV4_RESTORED))r->view.retiring=0;
    rv4_irq_restore(irq);
}
int32_t rv4_ui_mutation(Rv4Root *r,uint32_t ticket)
{
    if(!rv4_root_valid(r)||!ticket)return RV4_ARGUMENT;
    return rv4_view_withdraw(r,ticket);
}
uint32_t rv4_details(Rv4Root *r,uint32_t ticket)
{
    uint32_t irq=rv4_irq_save(),address=RV4_ADDRESS(rv4_blank_details);
    /* Always use resident blanks unless a pinned renderer owns the snapshot. */
    if(rv4_root_valid(r)&&ticket&&r->draw.readers&&r->draw.reader_ticket==ticket&&
       r->view.ticket==ticket&&r->view.allocation_epoch==r->epochs[RV4_E_HEAP]&&
       owner(r)&&native_match(r)&&!(r->header.flags&RV4_STOP))address=r->view.details;
    rv4_irq_restore(irq);return address;
}
int32_t rv4_view_draw(Rv4Root *r,uint32_t ticket,uint32_t generation)
{
    uint32_t irq,serial,state;int32_t result;
    if(!rv4_root_valid(r)||!ticket)return RV4_ARGUMENT;
    if((rv4_native_profile.proof_flags&(RV4_UI_PROTOCOL_PROVEN|RV4_RENDER_PROTOCOL_PROVEN))!=
       (RV4_UI_PROTOCOL_PROVEN|RV4_RENDER_PROTOCOL_PROVEN))return RV4_UNSUPPORTED;
    if(rv4_binding(r)||!snapshot_valid(r))return RV4_STALE;
    irq=rv4_irq_save();
    if(!owner(r)||r->view.ticket!=ticket||r->view.retiring||r->draw.pending||r->draw.readers||
       generation!=r->view.generation||generation!=r->epochs[RV4_E_VIEW]||
       r->view.allocation_epoch!=r->epochs[RV4_E_HEAP]||!native_match(r)||(r->header.flags&RV4_STOP)){
        rv4_irq_restore(irq);return RV4_STALE;
    }
    if(r->header.serial==~0u){rv4_irq_restore(irq);rv4_retire(r,RV4_RANGE);return RV4_RANGE;}
    serial=++r->header.serial;r->draw.readers=1;r->draw.reader_ticket=ticket;
    r->draw.reader_serial=serial;state=r->view.state;RV4_BARRIER();rv4_irq_restore(irq);
    result=rv4_native_draw(2,state,0);
    irq=rv4_irq_save();
    if(r->draw.reader_ticket!=ticket||r->draw.reader_serial!=serial||r->draw.readers!=1){
        rv4_irq_restore(irq);rv4_retire(r,RV4_STALE);return RV4_STALE;
    }
    r->draw.readers=0;r->draw.reader_ticket=0;RV4_BARRIER();rv4_irq_restore(irq);
    rv4_ui_drain(r);return result;
}
