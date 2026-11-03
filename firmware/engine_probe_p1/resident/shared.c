#include "resident.h"
int rv_allocation(uint32_t base,uint32_t bytes,uint32_t expected)
{
    uint32_t size;
    if(base<12||!bytes||!rv_heap_span(base-12,12)||!rv_heap_span(base,bytes))return 0;
    size=RV_WORD(base-4);
    return !RV_WORD(base-12)&&RV_BYTE(base-8)==1&&size>=bytes+12&&
        size<RV_WORD(0x200c0dc4)&&rv_heap_span(base-12,size)&&(!expected||size==expected);
}
RvSession *rv_session(RvRoot *r)
{
    RvSession *s;
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION||!r->lease||r->lease_inverse!=~r->lease||
       !r->block||r->inverse!=~r->block||r->heap_begin!=RV_WORD(0x200d3488)||
       r->heap_end!=RV_WORD(0x200d348c)||
       r->block_bytes-RV_MIN_BLOCK_BYTES>RV_MAX_BLOCK_BYTES-RV_MIN_BLOCK_BYTES||
       !rv_allocation(r->block,r->block_bytes,r->alloc_bytes))return 0;
    s=RV_PTR(r->block);
    if(s->leases[0].token!=r->lease||s->leases[0].inverse!=~r->lease||
       s->leases[0].base!=r->block||s->leases[0].length!=r->block_bytes||
       s->image_address!=r->block+RV_SESSION_BYTES)return 0;
    if(r->code_bytes&&(s->code_begin>s->code_end||s->code_end>s->image_bytes||
       s->image_address+s->code_begin!=r->code_address||s->code_end-s->code_begin!=r->code_bytes))return 0;
    if(s->context.header.version&&(s->context.header.version!=1||s->context.header.bytes!=sizeof(RvPrivateContext)||
       s->context.nonce!=r->lease||s->context.session_address!=r->block))return 0;
    return s;
}
int rv_range(RvRoot *r,uint32_t token,uint32_t base,uint32_t bytes)
{
    RvSession *s=rv_session(r);unsigned i;
    if(s)for(i=0;i<RV_LEASES;++i){
        RvLease *l=&s->leases[i];
        if(l->token&&l->token==token&&l->inverse==~token&&base>=l->base&&
           base-l->base<=l->length&&bytes<=l->length-(base-l->base))return 1;
    }
    return 0;
}
void rv_record(RvRoot *r,uint32_t hook,uint32_t phase,uint32_t a,uint32_t b)
{
    uint32_t irq=rv_irq_save(),seq=r->event_head+1;
    if(!seq){r->state=RV_FENCED;r->fault=RV_RANGE;r->grain=0;r->flags|=RF_STOP;}
    else {
        RvRingEvent *e=&r->events[(seq-1)&(RV_RING_COUNT-1)];e->hook=hook;e->phase=phase;e->a=a;e->b=b;
        __asm__ __volatile__("" ::: "memory");r->event_head=seq;
        if(seq>RV_RING_COUNT)++r->dropped;
    }
    rv_irq_restore(irq);
}
static RvUiSnapshot *ui_at(uint32_t base)
{
    RvUiSnapshot *u;
    if(!rv_allocation(base,sizeof(RvUiSnapshot),0))return 0;
    u=RV_PTR(base);
    return u->magic==RV_UI_MAGIC&&u->inverse==~base?u:0;
}
RvUiSnapshot *rv_ui_snapshot(RvRoot *r)
{
    return r->ui_block&&r->ui_inverse==~r->ui_block&&
        rv_allocation(r->ui_block,sizeof(RvUiSnapshot),r->ui_alloc_bytes)?ui_at(r->ui_block):0;
}
int rv_ui_capture(RvRoot *r,unsigned constructing)
{
    uint32_t *v=r->ui_restore,array,count;
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);
    if(array!=RV_NATIVE_VIEWS||count>2||(!count&&constructing!=1))return 0;
    if(!v[0]) {
        v[0]=RV_WORD(0x2022f5a8);v[1]=RV_BYTE(0x2022f5ac);
        v[2]=0x2023fd38;v[10]=RV_BYTE(0x2022f725);v[11]=RV_BYTE(0x2022f726);
        if(v[10]<1||v[10]>7)v[10]=1;
        if(v[11]<1||v[11]>7)v[11]=1;
    }
    return 1;
}
int32_t rv_ui_abort(RvRoot *r)
{
    uint32_t irq=rv_irq_save(),*v=r->ui_restore;int32_t result=RV_OK;
    /* v[2] keeps the stock H05 details pointer. With names withdrawn, H05
     * replays its original r2 construction. No stock descriptor was modified.
     * Recovery reads only resident records and fixed native pointer slots.
     * It never reads the expired UI allocation or a session. */
    if(v[0]&&(v[0]!=0x2022d610||v[1]!=7)){result=RV_STALE;}
    else if(v[0]) {
        RV_WORD(0x2022f5a8)=v[0];RV_BYTE(0x2022f5ac)=v[1];
        RV_BYTE(0x2022f725)=v[10];RV_BYTE(0x2022f726)=v[11];
        {uint32_t slot;for(slot=RV_NATIVE_VIEWS+4;v[12]&&slot<=RV_NATIVE_VIEWS+12;slot+=8) {
            if(RV_BYTE(slot-4)==33&&RV_WORD(slot)==v[12]) {
                RV_WORD(slot)=0x2022f71c;if(RV_WORD(slot)!=0x2022f71c)result=RV_STALE;
            }
        }}
        if(RV_WORD(0x2022f5a8)!=v[0]||RV_BYTE(0x2022f5ac)!=v[1])result=RV_STALE;
        if(!result)rv_clear(v,sizeof(r->ui_restore));
    }
    if(result){r->grain=0;r->state=RV_DISABLED_UNTIL_REBOOT;r->flags|=RF_STOP|RF_ATTEMPTED;}
    rv_irq_restore(irq);return result;
}
void rv_grain_commit(RvRoot *r,uint32_t mode,uint32_t enabled)
{
    uint32_t irq=rv_irq_save();
    r->grain=0;
    if(r->state==RV_READY&&!(r->flags&(RF_UNCERTAIN|RF_STOP))&&enabled&&mode<=6)
        r->grain=0x80|mode;
    rv_irq_restore(irq);
}
int32_t rv_free_checked(RvRoot *r,uint32_t base,uint32_t *detail)
{
    RvSession *s=rv_session(r);uint32_t i;
    *detail=0;
    if(r->state==RV_DISABLED_UNTIL_REBOOT||(r->flags&RF_STOP)||!s)return RV_STALE;
    for(i=1;i<RV_LEASES;++i)if(s->leases[i].token&&s->leases[i].base==base&&s->lease_entry[i]==r->entry_serial)break;
    if(i==RV_LEASES)return RV_STALE;
    if(!rv_allocation(base,s->leases[i].length,0))return RV_VERIFY;
    *detail=0x101;rv_native_free(base);*detail=0x100|RV_BYTE(base-8);
    return (*detail&255)==0?RV_OK:RV_IO;
}
