#include "resident.h"
RvSession *rv_session(RvRoot *r)
{
    RvSession *s;uint32_t bytes;
    if(!r->block||r->inverse!=~r->block||!rv_heap_span(r->block,RV_SESSION_BYTES)||
       r->boot_epoch!=r->epoch[RV_BOOT_E]||r->heap_epoch!=r->epoch[RV_HEAP_E])return 0;
    s=RV_PTR(r->block);
#ifndef RV_ENGINE_SERVICES
    if(!(r->flags&RF_BUSY)&&!rv_equal(s->bindings,r->epoch,48))return 0;
#endif
    bytes=s->leases[0].length;
    if(bytes-RV_MIN_BLOCK_BYTES>RV_MAX_BLOCK_BYTES-RV_MIN_BLOCK_BYTES||!rv_heap_span(r->block,bytes))return 0;
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
        RvRingEvent *e=&r->events[(seq-1)&7];e->hook=hook;e->phase=phase;e->a=a;e->b=b;
        __asm__ __volatile__("" ::: "memory");r->event_head=seq;
        if(seq>8)++r->dropped;
    }
    rv_irq_restore(irq);
}
void rv_ui_abort(RvRoot *r)
{
    uint32_t irq=rv_irq_save(),*v=r->ui_restore;
    if(v[6]&&RV_WORD(0x2022f5a8)==v[6]){
        RV_WORD(0x2022f5a8)=0x2022d610;RV_BYTE(0x2022f5ac)=7;
        if(RV_BYTE(0x2022f726)>6)RV_BYTE(0x2022f726)=0;
    }
    if(v[0]&&v[1]&&v[1]<=2&&RV_WORD(0x205a27d8)==v[0]&&RV_BYTE(0x205a27d4)==v[1]){
        volatile uint32_t *top=RV_PTR(v[0]+8*(v[1]-1));
        if(top[0]==v[2]&&top[1]==v[4])top[1]=0x2022f71c;
    }
    rv_clear(v,32);r->grain=0;rv_irq_restore(irq);
}
void rv_grain_commit(RvRoot *r,uint32_t mode,uint32_t enabled)
{
    uint32_t irq=rv_irq_save();
    r->grain=r->state==RV_READY&&!(r->flags&(RF_UNCERTAIN|RF_STOP))&&enabled&&mode<=6?0x80|mode:0;
    rv_irq_restore(irq);
}
int32_t rv_free_checked(RvRoot *r,uint32_t base,uint32_t *detail)
{
    uint32_t boot=r->epoch[RV_BOOT_E],heap=r->epoch[RV_HEAP_E],size;
    *detail=0;
    if(base<12||!rv_heap_span(base,1)||!rv_heap_span(base-12,12))return RV_RANGE;
    size=RV_WORD(base-4);
    if(!size||size>=RV_WORD(0x200c0dc4)||RV_WORD(base-12)||RV_BYTE(base-8)!=1)return RV_VERIFY;
    *detail=0x101;rv_native_free(base);
    if(boot!=r->epoch[RV_BOOT_E]||heap!=r->epoch[RV_HEAP_E])return RV_STALE;
    *detail=0x100|RV_BYTE(base-8);
    return (*detail&255)==0?RV_OK:RV_IO;
}
